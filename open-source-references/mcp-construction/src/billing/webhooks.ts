import { Hono } from 'hono';
import { eq } from 'drizzle-orm';
import { getStripe } from './stripe.js';
import { getDb } from '../db/index.js';
import { organizations } from '../db/schema.js';
import { getRedis } from '../lib/redis.js';
import { config } from '../config.js';
import { logger } from '../lib/logger.js';

export const webhookRoutes = new Hono();

webhookRoutes.post('/webhooks/stripe', async (c) => {
  const stripe = getStripe();
  const body = await c.req.text();
  const sig = c.req.header('stripe-signature');

  if (!sig) {
    return c.json({ error: 'Missing signature' }, 400);
  }

  let event;
  try {
    event = stripe.webhooks.constructEvent(body, sig, config.STRIPE_WEBHOOK_SECRET);
  } catch (err: any) {
    logger.error({ err }, 'Webhook signature verification failed');
    return c.json({ error: 'Invalid signature' }, 400);
  }

  const db = getDb();
  const redis = getRedis();

  try {
    switch (event.type) {
      case 'customer.subscription.created': {
        const subscription = event.data.object as any;
        const customerId = subscription.customer;

        await db
          .update(organizations)
          .set({
            stripeSubscriptionId: subscription.id,
            subscriptionStatus: 'active',
            updatedAt: new Date(),
          })
          .where(eq(organizations.stripeCustomerId, customerId));

        // Invalidate cache
        const [org] = await db
          .select({ id: organizations.id })
          .from(organizations)
          .where(eq(organizations.stripeCustomerId, customerId))
          .limit(1);
        if (org) await redis.del(`org:billing:${org.id}`);

        logger.info({ customerId, subscriptionId: subscription.id }, 'Subscription created');
        break;
      }

      case 'customer.subscription.updated': {
        const subscription = event.data.object as any;
        const customerId = subscription.customer;
        const status = subscription.status;

        // Determine plan from price items
        const updates: Record<string, any> = {
          subscriptionStatus: status === 'active' ? 'active' : status,
          updatedAt: new Date(),
        };

        await db
          .update(organizations)
          .set(updates)
          .where(eq(organizations.stripeCustomerId, customerId));

        const [org] = await db
          .select({ id: organizations.id })
          .from(organizations)
          .where(eq(organizations.stripeCustomerId, customerId))
          .limit(1);
        if (org) await redis.del(`org:billing:${org.id}`);

        logger.info({ customerId, status }, 'Subscription updated');
        break;
      }

      case 'customer.subscription.deleted': {
        const subscription = event.data.object as any;
        const customerId = subscription.customer;

        await db
          .update(organizations)
          .set({
            subscriptionStatus: 'canceled',
            updatedAt: new Date(),
          })
          .where(eq(organizations.stripeCustomerId, customerId));

        const [org] = await db
          .select({ id: organizations.id })
          .from(organizations)
          .where(eq(organizations.stripeCustomerId, customerId))
          .limit(1);
        if (org) await redis.del(`org:billing:${org.id}`);

        logger.info({ customerId }, 'Subscription deleted');
        break;
      }

      case 'customer.subscription.paused': {
        const subscription = event.data.object as any;
        const customerId = subscription.customer;

        await db
          .update(organizations)
          .set({
            subscriptionStatus: 'paused',
            updatedAt: new Date(),
          })
          .where(eq(organizations.stripeCustomerId, customerId));

        const [org] = await db
          .select({ id: organizations.id })
          .from(organizations)
          .where(eq(organizations.stripeCustomerId, customerId))
          .limit(1);
        if (org) await redis.del(`org:billing:${org.id}`);

        logger.info({ customerId }, 'Subscription paused');
        break;
      }

      case 'invoice.payment_succeeded': {
        const invoice = event.data.object as any;
        const customerId = invoice.customer;

        await db
          .update(organizations)
          .set({
            subscriptionStatus: 'active',
            updatedAt: new Date(),
          })
          .where(eq(organizations.stripeCustomerId, customerId));

        const [org] = await db
          .select({ id: organizations.id })
          .from(organizations)
          .where(eq(organizations.stripeCustomerId, customerId))
          .limit(1);
        if (org) await redis.del(`org:billing:${org.id}`);

        logger.info({ customerId, invoiceId: invoice.id }, 'Payment succeeded');
        break;
      }

      case 'invoice.payment_failed': {
        const invoice = event.data.object as any;
        const customerId = invoice.customer;

        await db
          .update(organizations)
          .set({
            subscriptionStatus: 'past_due',
            updatedAt: new Date(),
          })
          .where(eq(organizations.stripeCustomerId, customerId));

        const [org] = await db
          .select({ id: organizations.id })
          .from(organizations)
          .where(eq(organizations.stripeCustomerId, customerId))
          .limit(1);
        if (org) await redis.del(`org:billing:${org.id}`);

        logger.warn({ customerId, invoiceId: invoice.id }, 'Payment failed');
        break;
      }

      default:
        logger.debug({ type: event.type }, 'Unhandled webhook event');
    }
  } catch (err) {
    logger.error({ err, type: event.type }, 'Webhook handler error');
    return c.json({ error: 'Handler error' }, 500);
  }

  return c.json({ received: true });
});
