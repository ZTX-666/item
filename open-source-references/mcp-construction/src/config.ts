import 'dotenv/config';
import { z } from 'zod';
import { readFileSync } from 'node:fs';

const envSchema = z.object({
  PORT: z.coerce.number().default(3000),
  SERVER_URL: z.string().url().default('http://localhost:3000'),
  NODE_ENV: z.enum(['development', 'production', 'test']).default('development'),
  DATABASE_URL: z.string(),
  REDIS_URL: z.string().default('redis://localhost:6379'),
  JWT_PRIVATE_KEY_PATH: z.string().default('./keys/private.pem'),
  JWT_PUBLIC_KEY_PATH: z.string().default('./keys/public.pem'),
  JWT_ISSUER: z.string().default('https://construction-mcp.example.com'),
  JWT_AUDIENCE: z.string().default('construction-mcp'),
  STRIPE_SECRET_KEY: z.string(),
  STRIPE_WEBHOOK_SECRET: z.string(),
  STRIPE_TOOL_CALLS_METER_ID: z.string().default(''),
  STRIPE_AI_TOKENS_METER_ID: z.string().default(''),
  STRIPE_STARTER_BASE_PRICE: z.string().default(''),
  STRIPE_STARTER_METERED_PRICE: z.string().default(''),
  STRIPE_PRO_BASE_PRICE: z.string().default(''),
  STRIPE_PRO_METERED_PRICE: z.string().default(''),
  STRIPE_ENTERPRISE_BASE_PRICE: z.string().default(''),
  STRIPE_ENTERPRISE_METERED_PRICE: z.string().default(''),
  PROCORE_CLIENT_ID: z.string().default(''),
  PROCORE_CLIENT_SECRET: z.string().default(''),
  PROCORE_REDIRECT_URI: z.string().default(''),
  PROCORE_API_BASE: z.string().default('https://api.procore.com'),
  ENCRYPTION_KEY: z.string().min(64).default('0'.repeat(64)),
  LOG_LEVEL: z.string().default('info'),
});

export type Config = z.infer<typeof envSchema>;

function loadConfig(): Config {
  const result = envSchema.safeParse(process.env);
  if (!result.success) {
    console.error('Invalid environment variables:', result.error.format());
    process.exit(1);
  }
  return result.data;
}

export const config = loadConfig();

let _privateKey: string | undefined;
let _publicKey: string | undefined;

export function getJwtPrivateKey(): string {
  if (!_privateKey) {
    _privateKey = readFileSync(config.JWT_PRIVATE_KEY_PATH, 'utf-8');
  }
  return _privateKey;
}

export function getJwtPublicKey(): string {
  if (!_publicKey) {
    _publicKey = readFileSync(config.JWT_PUBLIC_KEY_PATH, 'utf-8');
  }
  return _publicKey;
}
