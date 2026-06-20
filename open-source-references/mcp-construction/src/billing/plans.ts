import { config } from '../config.js';

export interface PlanConfig {
  name: string;
  basePrice: string;
  meteredPrice: string;
  includedCalls: number;
  overageRateCents: number;
  rateLimit: number; // per hour
  basePriceAmount: number; // dollars
}

export const PLANS: Record<string, PlanConfig> = {
  starter: {
    name: 'Starter',
    basePrice: config.STRIPE_STARTER_BASE_PRICE,
    meteredPrice: config.STRIPE_STARTER_METERED_PRICE,
    includedCalls: 500,
    overageRateCents: 5,
    rateLimit: 100,
    basePriceAmount: 49,
  },
  pro: {
    name: 'Pro',
    basePrice: config.STRIPE_PRO_BASE_PRICE,
    meteredPrice: config.STRIPE_PRO_METERED_PRICE,
    includedCalls: 2000,
    overageRateCents: 3,
    rateLimit: 500,
    basePriceAmount: 149,
  },
  enterprise: {
    name: 'Enterprise',
    basePrice: config.STRIPE_ENTERPRISE_BASE_PRICE,
    meteredPrice: config.STRIPE_ENTERPRISE_METERED_PRICE,
    includedCalls: 10000,
    overageRateCents: 2,
    rateLimit: 2000,
    basePriceAmount: 499,
  },
  trial: {
    name: 'Trial (Pro)',
    basePrice: config.STRIPE_PRO_BASE_PRICE,
    meteredPrice: config.STRIPE_PRO_METERED_PRICE,
    includedCalls: 2000,
    overageRateCents: 0,
    rateLimit: 500,
    basePriceAmount: 0,
  },
};

export function getPlanConfig(plan: string): PlanConfig {
  return PLANS[plan] || PLANS.starter;
}
