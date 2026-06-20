import { Redis } from 'ioredis';
import { config } from '../config.js';
import { logger } from './logger.js';

let redis: Redis | undefined;

export function getRedis(): Redis {
  if (!redis) {
    redis = new Redis(config.REDIS_URL, {
      maxRetriesPerRequest: 3,
      lazyConnect: true,
    });
    redis.on('error', (err: Error) => {
      logger.error({ err }, 'Redis connection error');
    });
    redis.on('connect', () => {
      logger.info('Redis connected');
    });
  }
  return redis;
}

export async function closeRedis(): Promise<void> {
  if (redis) {
    await redis.quit();
    redis = undefined;
  }
}
