import { Hono } from 'hono';
import { eq } from 'drizzle-orm';
import { honoAuth, type AppEnv } from '../middleware/hono-auth.js';
import { getDb } from '../db/index.js';
import { organizations } from '../db/schema.js';
import { getStripe } from './stripe.js';
import { getPlanConfig } from './plans.js';
import { config } from '../config.js';
import { logger } from '../lib/logger.js';

export const checkoutRoutes = new Hono<AppEnv>();

// All billing routes require auth
checkoutRoutes.use('/billing/*', honoAuth);

/**
 * POST /billing/checkout
 * Creates a Stripe Checkout session for subscribing to a plan.
 * Returns a checkout_url that the bot can pass to a human operator.
 */
checkoutRoutes.post('/billing/checkout', async (c) => {
  try {
    const userContext = c.get('userContext');
    const body = await c.req.json();
    const plan = (body as any).plan as string;

    if (!plan || !['starter', 'pro', 'enterprise'].includes(plan)) {
      return c.json({ error: 'Invalid plan. Choose: starter, pro, enterprise' }, 400);
    }

    const db = getDb();
    const [org] = await db
      .select()
      .from(organizations)
      .where(eq(organizations.id, userContext.orgId))
      .limit(1);

    if (!org) {
      return c.json({ error: 'Organization not found' }, 404);
    }

    if (!org.stripeCustomerId) {
      return c.json({ error: 'No Stripe customer on file' }, 400);
    }

    const planConfig = getPlanConfig(plan);

    if (!planConfig.basePrice || !planConfig.meteredPrice) {
      return c.json({ error: 'Stripe prices not configured for this plan' }, 500);
    }

    const stripe = getStripe();
    const session = await stripe.checkout.sessions.create({
      customer: org.stripeCustomerId,
      mode: 'subscription',
      payment_method_types: ['card'],
      line_items: [
        { price: planConfig.basePrice, quantity: 1 },
        { price: planConfig.meteredPrice },
      ],
      success_url: (body as any).success_url || `${config.SERVER_URL}/billing/success?session_id={CHECKOUT_SESSION_ID}`,
      cancel_url: (body as any).cancel_url || `${config.SERVER_URL}/billing/cancel`,
      subscription_data: {
        metadata: { org_id: org.id, plan },
      },
    });

    return c.json({
      checkout_url: session.url,
      session_id: session.id,
    });
  } catch (err) {
    logger.error({ err }, 'Checkout session creation failed');
    return c.json({ error: 'Failed to create checkout session' }, 500);
  }
});

/**
 * POST /billing/portal
 * Creates a Stripe Billing Portal session for subscription management.
 */
checkoutRoutes.post('/billing/portal', async (c) => {
  try {
    const userContext = c.get('userContext');
    const db = getDb();

    const [org] = await db
      .select({ stripeCustomerId: organizations.stripeCustomerId })
      .from(organizations)
      .where(eq(organizations.id, userContext.orgId))
      .limit(1);

    if (!org?.stripeCustomerId) {
      return c.json({ error: 'No Stripe customer found' }, 400);
    }

    const stripe = getStripe();
    const session = await stripe.billingPortal.sessions.create({
      customer: org.stripeCustomerId,
      return_url: `${config.SERVER_URL}/health`,
    });

    return c.json({ portal_url: session.url });
  } catch (err) {
    logger.error({ err }, 'Portal session creation failed');
    return c.json({ error: 'Failed to create portal session' }, 500);
  }
});

/**
 * GET /billing/success
 * Simple success page after Stripe Checkout.
 */
checkoutRoutes.get('/billing/success', (c) => {
  return c.html(`<!DOCTYPE html>
<html>
<head><title>Payment Successful</title></head>
<body>
  <h1>Payment Successful</h1>
  <p>Your subscription is now active. You can close this page and continue using the MCP API.</p>
</body>
</html>`);
});

/**
 * GET /billing/cancel
 * Cancellation page when user backs out of Stripe Checkout.
 */
checkoutRoutes.get('/billing/cancel', (c) => {
  return c.html(`<!DOCTYPE html>
<html>
<head><title>Payment Canceled</title></head>
<body>
  <h1>Payment Canceled</h1>
  <p>No charges were made. Your trial will continue until it expires.</p>
</body>
</html>`);
});
