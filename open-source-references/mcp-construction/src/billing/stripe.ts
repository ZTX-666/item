import Stripe from 'stripe';
import { config } from '../config.js';
import { getPlanConfig } from './plans.js';
import { logger } from '../lib/logger.js';

let stripe: Stripe | undefined;

export function getStripe(): Stripe {
  if (!stripe) {
    stripe = new Stripe(config.STRIPE_SECRET_KEY, {
      apiVersion: '2025-01-27.acacia' as any,
    });
  }
  return stripe;
}

export async function createStripeCustomer(org: {
  id: string;
  name: string;
  email?: string;
}): Promise<Stripe.Customer> {
  const s = getStripe();
  return s.customers.create({
    email: org.email,
    name: org.name,
    metadata: { org_id: org.id, source: 'construction-mcp' },
  });
}

export async function createSubscription(
  customerId: string,
  plan: string,
): Promise<Stripe.Subscription> {
  const s = getStripe();
  const planConfig = getPlanConfig(plan);

  return s.subscriptions.create({
    customer: customerId,
    items: [
      { price: planConfig.basePrice },
      { price: planConfig.meteredPrice },
    ],
    payment_behavior: 'default_incomplete',
    expand: ['latest_invoice.payment_intent'],
  });
}

export async function reportToolCallUsage(
  stripeCustomerId: string,
): Promise<void> {
  try {
    const s = getStripe();
    await (s as any).v2.billing.meterEvents.create({
      event_name: 'mcp_tool_call',
      payload: {
        stripe_customer_id: stripeCustomerId,
        value: '1',
      },
    });
  } catch (err) {
    logger.error({ err }, 'Failed to report tool call usage to Stripe');
  }
}

export async function reportAiTokenUsage(
  stripeCustomerId: string,
  tokenCount: number,
): Promise<void> {
  try {
    const s = getStripe();
    await (s as any).v2.billing.meterEvents.create({
      event_name: 'mcp_ai_tokens',
      payload: {
        stripe_customer_id: stripeCustomerId,
        value: String(tokenCount),
      },
    });
  } catch (err) {
    logger.error({ err }, 'Failed to report AI token usage to Stripe');
  }
}
