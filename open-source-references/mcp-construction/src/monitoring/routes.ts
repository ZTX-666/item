import { Hono } from 'hono';
import os from 'node:os';
import { execSync } from 'node:child_process';
import { getPool } from '../db/index.js';
import { getRedis } from '../lib/redis.js';
import { logger } from '../lib/logger.js';

const statusRoutes = new Hono();

async function checkService(name: string, fn: () => Promise<void>): Promise<{ status: string; latency_ms: number }> {
  const start = performance.now();
  try {
    await fn();
    return { status: 'ok', latency_ms: Math.round(performance.now() - start) };
  } catch (err) {
    logger.error({ err }, `Health check failed: ${name}`);
    return { status: 'error', latency_ms: Math.round(performance.now() - start) };
  }
}

statusRoutes.get('/status', async (c) => {
  // System metrics
  const loadAvg = os.loadavg();
  const totalMem = os.totalmem();
  const freeMem = os.freemem();
  const usedMem = totalMem - freeMem;
  const cpuCores = os.cpus().length;

  // Disk usage
  let disk = { total_gb: 0, used_gb: 0, percent: 0 };
  try {
    const dfOut = execSync("df -B1 / | tail -1", { timeout: 3000 }).toString().trim();
    const parts = dfOut.split(/\s+/);
    const totalBytes = parseInt(parts[1], 10);
    const usedBytes = parseInt(parts[2], 10);
    disk = {
      total_gb: Math.round(totalBytes / 1073741824 * 10) / 10,
      used_gb: Math.round(usedBytes / 1073741824 * 10) / 10,
      percent: Math.round((usedBytes / totalBytes) * 100),
    };
  } catch { /* ignore */ }

  // Process metrics
  const mem = process.memoryUsage();
  const processInfo = {
    rss_mb: Math.round(mem.rss / 1048576),
    heap_used_mb: Math.round(mem.heapUsed / 1048576),
    heap_total_mb: Math.round(mem.heapTotal / 1048576),
  };

  // Service health checks (with 5s timeout)
  const [database, redis] = await Promise.all([
    checkService('database', async () => {
      const client = await getPool().connect();
      try { await client.query('SELECT 1'); } finally { client.release(); }
    }),
    checkService('redis', async () => {
      await getRedis().ping();
    }),
  ]);

  // Determine overall status
  const memPercent = Math.round((usedMem / totalMem) * 100);
  const servicesDown = [database, redis].some(s => s.status !== 'ok');
  const highLoad = loadAvg[0] > cpuCores * 0.85;
  const highMem = memPercent > 80;

  let status: string;
  if (servicesDown) {
    status = 'unhealthy';
  } else if (highLoad || highMem) {
    status = 'degraded';
  } else {
    status = 'healthy';
  }

  return c.json({
    status,
    timestamp: new Date().toISOString(),
    version: '1.0.0',
    uptime_seconds: Math.round(process.uptime()),
    system: {
      cpu_load: loadAvg.map(v => Math.round(v * 100) / 100),
      cpu_cores: cpuCores,
      memory: {
        total_mb: Math.round(totalMem / 1048576),
        used_mb: Math.round(usedMem / 1048576),
        percent: memPercent,
      },
      disk,
    },
    services: { database, redis },
    process: processInfo,
  });
});

export { statusRoutes };
