import { Queue, Worker } from 'bullmq';
import { config } from '../config.js';
import { reportToolCallUsage, reportAiTokenUsage } from './stripe.js';
import { logger } from '../lib/logger.js';

const connection = {
  url: config.REDIS_URL,
};

export const usageQueue = new Queue('stripe-usage', { connection });

interface UsageJob {
  type: 'tool_call' | 'ai_tokens';
  stripeCustomerId: string;
  tokenCount?: number;
}

export function enqueueUsageReport(data: UsageJob): void {
  usageQueue
    .add('report', data, {
      attempts: 5,
      backoff: { type: 'exponential', delay: 1000 },
      removeOnComplete: 1000,
      removeOnFail: 5000,
    })
    .catch((err) => {
      logger.error({ err }, 'Failed to enqueue usage report');
    });
}

export function startUsageWorker(): Worker {
  const worker = new Worker<UsageJob>(
    'stripe-usage',
    async (job) => {
      const { type, stripeCustomerId, tokenCount } = job.data;

      if (type === 'tool_call') {
        await reportToolCallUsage(stripeCustomerId);
      } else if (type === 'ai_tokens' && tokenCount) {
        await reportAiTokenUsage(stripeCustomerId, tokenCount);
      }
    },
    {
      connection,
      concurrency: 10,
    },
  );

  worker.on('failed', (job, err) => {
    logger.error({ err, jobId: job?.id }, 'Usage report job failed');
  });

  worker.on('completed', (job) => {
    logger.debug({ jobId: job.id }, 'Usage report job completed');
  });

  return worker;
}
