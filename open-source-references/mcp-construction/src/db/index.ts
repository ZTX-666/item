import { drizzle } from 'drizzle-orm/node-postgres';
import pg from 'pg';
import * as schema from './schema.js';
import { config } from '../config.js';
import { logger } from '../lib/logger.js';

const { Pool } = pg;

let pool: pg.Pool;

export function getPool(): pg.Pool {
  if (!pool) {
    pool = new Pool({
      connectionString: config.DATABASE_URL,
      max: 20,
      idleTimeoutMillis: 30000,
      connectionTimeoutMillis: 5000,
    });
    pool.on('error', (err) => {
      logger.error({ err }, 'Unexpected database pool error');
    });
  }
  return pool;
}

let db: ReturnType<typeof drizzle<typeof schema>> | undefined;

export function getDb() {
  if (!db) {
    db = drizzle(getPool(), { schema });
  }
  return db;
}

export type Database = ReturnType<typeof getDb>;
