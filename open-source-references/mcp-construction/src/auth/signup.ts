import bcrypt from 'bcrypt';
import { eq } from 'drizzle-orm';
import { getDb } from '../db/index.js';
import { organizations, users } from '../db/schema.js';
import { registerClient } from './oauth.js';
import { createStripeCustomer } from '../billing/stripe.js';
import { config } from '../config.js';
import { logger } from '../lib/logger.js';

interface SignupInput {
  org_name: string;
  email: string;
  password: string;
  plan?: string;
}

function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 60);
}

const DISCORD_WEBHOOK = process.env.DISCORD_WEBHOOK_URL || '';

async function notifyNewSignup(orgName: string, email: string, plan: string): Promise<void> {
  if (!DISCORD_WEBHOOK) return;
  await fetch(DISCORD_WEBHOOK, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      embeds: [{
        title: 'New Agent Signup',
        color: 3066993,
        fields: [
          { name: 'Organization', value: orgName, inline: true },
          { name: 'Email', value: email, inline: true },
          { name: 'Plan', value: plan, inline: true },
        ],
        footer: { text: 'CMCP' },
        timestamp: new Date().toISOString(),
      }],
    }),
  });
}

export async function handleSignup(input: SignupInput) {
  const { org_name, email, password, plan } = input;

  // Validate inputs
  if (!org_name || org_name.length < 2 || org_name.length > 100) {
    throw new Error('org_name must be 2-100 characters');
  }
  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    throw new Error('Invalid email address');
  }
  if (!password || password.length < 8) {
    throw new Error('Password must be at least 8 characters');
  }
  if (plan && !['trial', 'starter', 'pro', 'enterprise'].includes(plan)) {
    throw new Error('Invalid plan. Choose: trial, starter, pro, enterprise');
  }

  const db = getDb();
  const selectedPlan = plan || 'trial';
  const slug = slugify(org_name) + '-' + crypto.randomUUID().slice(0, 8);

  // Check if email already exists
  const [existingUser] = await db
    .select({ id: users.id })
    .from(users)
    .where(eq(users.email, email))
    .limit(1);

  if (existingUser) {
    throw new Error('An account with this email already exists');
  }

  // Create organization
  const trialEndsAt = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000);
  const [org] = await db
    .insert(organizations)
    .values({
      name: org_name,
      slug,
      plan: selectedPlan,
      subscriptionStatus: 'trialing',
      trialEndsAt,
    })
    .returning();

  try {
    // Create Stripe customer
    const stripeCustomer = await createStripeCustomer({
      id: org.id,
      name: org_name,
      email,
    });

    // Store Stripe customer ID
    await db
      .update(organizations)
      .set({ stripeCustomerId: stripeCustomer.id })
      .where(eq(organizations.id, org.id));

    // Hash password and create user
    const passwordHash = await bcrypt.hash(password, 10);
    const [user] = await db
      .insert(users)
      .values({
        orgId: org.id,
        email,
        name: email.split('@')[0],
        passwordHash,
        role: 'owner',
      })
      .returning();

    // Auto-register OAuth client
    const client = await registerClient({
      client_name: `${org_name} API Client`,
      redirect_uris: ['http://localhost:8080/callback', 'urn:ietf:wg:oauth:2.0:oob'],
      grant_types: ['authorization_code', 'refresh_token'],
      scope: 'admin projects:read projects:write estimates:read estimates:write rfis:read rfis:write change_orders:read change_orders:write daily_logs:read daily_logs:write budget:read budget:write schedule:read schedule:write subcontractors:read subcontractors:write documents:read documents:write safety:read safety:write users:read users:write org:read org:write',
    });

    logger.info({ orgId: org.id, email }, 'New signup completed');

    // Notify Discord of new signup (fire-and-forget)
    notifyNewSignup(org_name, email, selectedPlan).catch(() => {});

    return {
      org_id: org.id,
      user_id: user.id,
      email: user.email,
      client_id: client.client_id,
      client_secret: client.client_secret,
      plan: selectedPlan,
      trial_ends_at: trialEndsAt.toISOString(),
      next_steps: {
        authorization_url: `${config.SERVER_URL}/oauth/authorize`,
        token_url: `${config.SERVER_URL}/oauth/token`,
        mcp_endpoint: `${config.SERVER_URL}/mcp`,
        oauth_metadata: `${config.SERVER_URL}/.well-known/oauth-authorization-server`,
        note: 'Use OAuth 2.1 PKCE (S256) flow to obtain access tokens. Your 7-day trial includes 2,000 tool calls.',
      },
    };
  } catch (err) {
    // Clean up org if downstream steps fail
    await db.delete(organizations).where(eq(organizations.id, org.id));
    throw err;
  }
}
