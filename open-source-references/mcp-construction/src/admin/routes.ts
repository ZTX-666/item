import { Hono } from 'hono';
import { eq, sql, and, gte } from 'drizzle-orm';
import { honoAuth, requireAdmin, type AppEnv } from '../middleware/hono-auth.js';
import { getDb } from '../db/index.js';
import { usageLogs, organizations } from '../db/schema.js';
import { getPlanConfig } from '../billing/plans.js';
import { createSubscription, getStripe } from '../billing/stripe.js';
import { logger } from '../lib/logger.js';

export const adminRoutes = new Hono<AppEnv>();

// All admin routes require auth + admin scope
adminRoutes.use('/admin/*', honoAuth, requireAdmin);

/**
 * GET /admin/usage
 * Usage stats by tool, by day, success rate.
 */
adminRoutes.get('/admin/usage', async (c) => {
  const userContext = c.get('userContext');
  const db = getDb();

  const thirtyDaysAgo = new Date(Date.now() - 30 * 86_400_000);

  // Tool usage breakdown
  const toolStats = await db
    .select({
      tool_name: usageLogs.toolName,
      total_calls: sql<string>`count(*)::text`,
      success_count: sql<string>`count(*) filter (where ${usageLogs.success} = true)::text`,
      failure_count: sql<string>`count(*) filter (where ${usageLogs.success} = false)::text`,
      avg_duration_ms: sql<string>`round(avg(${usageLogs.durationMs}))::text`,
    })
    .from(usageLogs)
    .where(
      and(
        eq(usageLogs.orgId, userContext.orgId),
        gte(usageLogs.createdAt, thirtyDaysAgo),
      ),
    )
    .groupBy(usageLogs.toolName)
    .orderBy(sql`count(*) desc`);

  // Daily usage (last 30 days)
  const dailyStats = await db
    .select({
      day: sql<string>`date_trunc('day', ${usageLogs.createdAt})::date::text`,
      total_calls: sql<string>`count(*)::text`,
      success_count: sql<string>`count(*) filter (where ${usageLogs.success} = true)::text`,
    })
    .from(usageLogs)
    .where(
      and(
        eq(usageLogs.orgId, userContext.orgId),
        gte(usageLogs.createdAt, thirtyDaysAgo),
      ),
    )
    .groupBy(sql`date_trunc('day', ${usageLogs.createdAt})`)
    .orderBy(sql`date_trunc('day', ${usageLogs.createdAt}) desc`);

  // Overall stats
  const [overall] = await db
    .select({
      total_calls: sql<string>`count(*)::text`,
      success_rate: sql<string>`round(100.0 * count(*) filter (where ${usageLogs.success} = true) / nullif(count(*), 0), 1)::text`,
      avg_duration_ms: sql<string>`round(avg(${usageLogs.durationMs}))::text`,
    })
    .from(usageLogs)
    .where(
      and(
        eq(usageLogs.orgId, userContext.orgId),
        gte(usageLogs.createdAt, thirtyDaysAgo),
      ),
    );

  return c.json({
    period: 'last_30_days',
    overall: {
      total_calls: parseInt(overall.total_calls, 10),
      success_rate: parseFloat(overall.success_rate ?? '0'),
      avg_duration_ms: parseInt(overall.avg_duration_ms ?? '0', 10),
    },
    by_tool: toolStats.map((s) => ({
      tool_name: s.tool_name,
      total_calls: parseInt(s.total_calls, 10),
      success_count: parseInt(s.success_count, 10),
      failure_count: parseInt(s.failure_count, 10),
      success_rate:
        parseInt(s.total_calls, 10) > 0
          ? Math.round(
              (parseInt(s.success_count, 10) / parseInt(s.total_calls, 10)) * 1000,
            ) / 10
          : 0,
      avg_duration_ms: parseInt(s.avg_duration_ms ?? '0', 10),
    })),
    by_day: dailyStats.map((d) => ({
      day: d.day,
      total_calls: parseInt(d.total_calls, 10),
      success_count: parseInt(d.success_count, 10),
    })),
  });
});

/**
 * GET /admin/billing
 * Plan info, current month calls, estimated cost.
 */
adminRoutes.get('/admin/billing', async (c) => {
  const userContext = c.get('userContext');
  const db = getDb();

  // Get org info
  const [org] = await db
    .select({
      plan: organizations.plan,
      subscriptionStatus: organizations.subscriptionStatus,
      stripeCustomerId: organizations.stripeCustomerId,
      stripeSubscriptionId: organizations.stripeSubscriptionId,
      trialEndsAt: organizations.trialEndsAt,
    })
    .from(organizations)
    .where(eq(organizations.id, userContext.orgId))
    .limit(1);

  if (!org) {
    return c.json({ error: 'Organization not found' }, 404);
  }

  const planConfig = getPlanConfig(org.plan);

  // Count calls this month
  const startOfMonth = new Date();
  startOfMonth.setDate(1);
  startOfMonth.setHours(0, 0, 0, 0);

  const [monthStats] = await db
    .select({
      total_calls: sql<string>`count(*)::text`,
      success_calls: sql<string>`count(*) filter (where ${usageLogs.success} = true)::text`,
    })
    .from(usageLogs)
    .where(
      and(
        eq(usageLogs.orgId, userContext.orgId),
        gte(usageLogs.createdAt, startOfMonth),
      ),
    );

  const totalCalls = parseInt(monthStats.total_calls, 10);
  const overageCalls = Math.max(0, totalCalls - planConfig.includedCalls);
  const estimatedOverageCost = (overageCalls * planConfig.overageRateCents) / 100;
  const estimatedTotalCost = planConfig.basePriceAmount + estimatedOverageCost;

  return c.json({
    plan: {
      name: planConfig.name,
      key: org.plan,
      base_price: planConfig.basePriceAmount,
      included_calls: planConfig.includedCalls,
      overage_rate_cents: planConfig.overageRateCents,
      rate_limit_per_hour: planConfig.rateLimit,
    },
    subscription: {
      status: org.subscriptionStatus,
      stripe_customer_id: org.stripeCustomerId,
      trial_ends_at: org.trialEndsAt,
    },
    current_month: {
      total_calls: totalCalls,
      included_remaining: Math.max(0, planConfig.includedCalls - totalCalls),
      overage_calls: overageCalls,
      estimated_overage_cost: estimatedOverageCost,
      estimated_total_cost: estimatedTotalCost,
    },
  });
});

/**
 * POST /admin/subscription/upgrade
 * Upgrade plan via Stripe.
 */
adminRoutes.post('/admin/subscription/upgrade', async (c) => {
  const userContext = c.get('userContext');
  const db = getDb();

  try {
    const body = await c.req.json();
    const newPlan = (body as any).plan as string;

    if (!['starter', 'pro', 'enterprise'].includes(newPlan)) {
      return c.json({ error: 'Invalid plan. Choose: starter, pro, enterprise' }, 400);
    }

    const [org] = await db
      .select()
      .from(organizations)
      .where(eq(organizations.id, userContext.orgId))
      .limit(1);

    if (!org) {
      return c.json({ error: 'Organization not found' }, 404);
    }

    if (org.plan === newPlan) {
      return c.json({ error: `Already on the ${newPlan} plan` }, 400);
    }

    if (!org.stripeCustomerId) {
      return c.json({ error: 'No Stripe customer on file. Contact support.' }, 400);
    }

    // If there's an existing subscription, cancel it first
    if (org.stripeSubscriptionId) {
      const stripe = getStripe();
      await stripe.subscriptions.cancel(org.stripeSubscriptionId);
    }

    // Create new subscription
    const subscription = await createSubscription(org.stripeCustomerId, newPlan);

    // Update org
    await db
      .update(organizations)
      .set({
        plan: newPlan,
        stripeSubscriptionId: subscription.id,
        subscriptionStatus: subscription.status,
        updatedAt: new Date(),
      })
      .where(eq(organizations.id, userContext.orgId));

    return c.json({
      success: true,
      plan: newPlan,
      subscription_id: subscription.id,
      status: subscription.status,
    });
  } catch (err) {
    logger.error({ err }, 'Subscription upgrade failed');
    return c.json({ error: 'Failed to upgrade subscription' }, 500);
  }
});
