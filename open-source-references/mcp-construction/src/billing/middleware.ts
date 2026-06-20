import { eq } from 'drizzle-orm';
import { getDb } from '../db/index.js';
import { organizations, usageLogs } from '../db/schema.js';
import { getRedis } from '../lib/redis.js';
import { rateLimited, subscriptionRequired } from '../lib/errors.js';
import { getPlanConfig } from './plans.js';
import { enqueueUsageReport } from './queue.js';
import { logger } from '../lib/logger.js';
import type { UserContext } from '../auth/jwt.js';

const ACTIVE_STATUSES = ['active', 'trialing'];

interface OrgBillingInfo {
  stripeCustomerId: string | null;
  plan: string;
  subscriptionStatus: string;
  trialEndsAt: Date | null;
}

async function getOrgBillingInfo(orgId: string): Promise<OrgBillingInfo> {
  const redis = getRedis();
  const cacheKey = `org:billing:${orgId}`;
  const cached = await redis.get(cacheKey);

  if (cached) {
    return JSON.parse(cached);
  }

  const db = getDb();
  const [org] = await db
    .select({
      stripeCustomerId: organizations.stripeCustomerId,
      plan: organizations.plan,
      subscriptionStatus: organizations.subscriptionStatus,
      trialEndsAt: organizations.trialEndsAt,
    })
    .from(organizations)
    .where(eq(organizations.id, orgId))
    .limit(1);

  if (!org) throw subscriptionRequired();

  const info: OrgBillingInfo = {
    stripeCustomerId: org.stripeCustomerId,
    plan: org.plan,
    subscriptionStatus: org.subscriptionStatus,
    trialEndsAt: org.trialEndsAt,
  };

  await redis.set(cacheKey, JSON.stringify(info), 'EX', 300); // 5-min TTL
  return info;
}

async function checkRateLimit(orgId: string, plan: string): Promise<void> {
  const redis = getRedis();
  const planConfig = getPlanConfig(plan);
  const window = Math.floor(Date.now() / 3600000); // hourly window
  const key = `ratelimit:${orgId}:${window}`;

  const current = await redis.incr(key);
  if (current === 1) {
    await redis.expire(key, 3600);
  }

  if (current > planConfig.rateLimit) {
    const ttl = await redis.ttl(key);
    throw rateLimited(ttl > 0 ? ttl : 3600);
  }
}

export async function billingMiddleware(
  userContext: UserContext,
  toolName: string,
  execute: () => Promise<any>,
): Promise<any> {
  const startTime = Date.now();

  // Get org billing info
  const orgInfo = await getOrgBillingInfo(userContext.orgId);

  // Check subscription status
  // First: reject expired trials (must check before ACTIVE_STATUSES pass-through)
  if (
    orgInfo.subscriptionStatus === 'trialing' &&
    orgInfo.trialEndsAt &&
    new Date() > new Date(orgInfo.trialEndsAt)
  ) {
    throw subscriptionRequired();
  }

  // Then: reject any non-active status
  if (!ACTIVE_STATUSES.includes(orgInfo.subscriptionStatus)) {
    throw subscriptionRequired();
  }

  // Check rate limit
  await checkRateLimit(userContext.orgId, orgInfo.plan);

  // Execute the tool
  let result: any;
  let success = true;
  let errorCode: string | undefined;

  try {
    result = await execute();
  } catch (err: any) {
    success = false;
    errorCode = String(err.code || 'UNKNOWN');
    throw err;
  } finally {
    const durationMs = Date.now() - startTime;

    // Report usage to Stripe (fire-and-forget via queue)
    if (success && orgInfo.stripeCustomerId) {
      enqueueUsageReport({
        type: 'tool_call',
        stripeCustomerId: orgInfo.stripeCustomerId,
      });

      // Estimate AI token usage from response content size and report
      if (result) {
        const estimatedTokens = Math.ceil(JSON.stringify(result.content ?? result).length / 4);
        if (estimatedTokens > 0) {
          enqueueUsageReport({
            type: 'ai_tokens',
            stripeCustomerId: orgInfo.stripeCustomerId,
            tokenCount: estimatedTokens,
          });
        }
      }
    }

    // Log to usage_logs table
    try {
      const db = getDb();
      await db.insert(usageLogs).values({
        orgId: userContext.orgId,
        userId: userContext.userId,
        toolName,
        durationMs,
        success,
        errorCode,
        metadata: {},
      });
    } catch (logErr) {
      logger.error({ err: logErr }, 'Failed to insert usage log');
    }
  }

  return result;
}
