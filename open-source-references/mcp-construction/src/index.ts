import { createServer } from 'node:http';
import { Hono } from 'hono';
import { serve } from '@hono/node-server';
import { config } from './config.js';
import { logger } from './lib/logger.js';
import { getRedis } from './lib/redis.js';
import { getPool } from './db/index.js';
import { createMcpServer } from './server.js';
import { getMcpRequestHandler } from './transport/http.js';
import { authRoutes } from './auth/routes.js';
import { webhookRoutes } from './billing/webhooks.js';
import { startUsageWorker } from './billing/queue.js';
import { procoreRoutes } from './integrations/procore/routes.js';
import { adminRoutes } from './admin/routes.js';
import { checkoutRoutes } from './billing/checkout-routes.js';
import { statusRoutes } from './monitoring/routes.js';

async function main() {
  logger.info('Starting ConstructionAI MCP Server...');

  // Connect Redis
  const redis = getRedis();
  try {
    await redis.connect();
  } catch {
    logger.warn('Redis connection deferred — will retry on first use');
  }

  // Test DB connection
  try {
    const pool = getPool();
    const client = await pool.connect();
    client.release();
    logger.info('Database connected');
  } catch (err) {
    logger.error({ err }, 'Database connection failed');
    process.exit(1);
  }

  // Start BullMQ usage worker
  const worker = startUsageWorker();
  logger.info('Usage billing worker started');

  // Hono app for non-MCP routes
  const app = new Hono();

  // Health check
  app.get('/health', (c) => c.json({ status: 'ok', version: '1.0.0' }));

  // Landing page
  app.get('/', (c) => c.html(`<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>CMCP - Construction AI MCP Server</title>
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  body{font-family:system-ui,-apple-system,sans-serif;background:#1a1a2e;color:#e2e8f0;min-height:100vh;display:flex;align-items:center;justify-content:center}
  .c{max-width:640px;padding:48px 32px;text-align:center}
  h1{font-size:3rem;font-weight:800;letter-spacing:-1px;margin-bottom:8px}
  h1 span{color:#f59e0b}
  .tag{color:#94a3b8;font-size:1.1rem;letter-spacing:3px;text-transform:uppercase;margin-bottom:32px}
  .desc{color:#cbd5e1;line-height:1.7;margin-bottom:40px}
  .plans{display:flex;gap:16px;justify-content:center;flex-wrap:wrap;margin-bottom:40px}
  .plan{background:#16213e;border:1px solid #334155;border-radius:12px;padding:20px 24px;min-width:140px}
  .plan h3{color:#f59e0b;font-size:1rem;margin-bottom:4px}
  .plan .price{font-size:1.5rem;font-weight:700}
  .plan .calls{color:#94a3b8;font-size:.85rem;margin-top:4px}
  .endpoints{text-align:left;background:#16213e;border-radius:12px;padding:24px 28px;margin-bottom:32px}
  .endpoints h2{font-size:1rem;color:#f59e0b;margin-bottom:12px}
  .endpoints code{display:block;color:#94a3b8;font-size:.9rem;margin-bottom:6px}
  .endpoints a{color:#60a5fa;text-decoration:none}
  .endpoints a:hover{text-decoration:underline}
  .cta{display:inline-block;background:#f59e0b;color:#1a1a2e;font-weight:700;padding:14px 32px;border-radius:8px;text-decoration:none;font-size:1rem}
  .cta:hover{background:#fbbf24}
  .foot{margin-top:40px;color:#64748b;font-size:.85rem}
</style>
</head>
<body>
<div class="c">
  <h1><span>CMCP</span></h1>
  <div class="tag">Construction AI</div>
  <p class="desc">50-tool MCP server for construction project management. Estimates, RFIs, change orders, daily logs, budgets, schedules, safety, subcontractors, and more — all accessible to AI agents via the Model Context Protocol.</p>
  <div class="plans">
    <div class="plan"><h3>Starter</h3><div class="price">$49<small>/mo</small></div><div class="calls">500 calls</div></div>
    <div class="plan"><h3>Pro</h3><div class="price">$149<small>/mo</small></div><div class="calls">2,000 calls</div></div>
    <div class="plan"><h3>Enterprise</h3><div class="price">$499<small>/mo</small></div><div class="calls">10,000 calls</div></div>
  </div>
  <div class="endpoints">
    <h2>Quick Start</h2>
    <code>POST <a href="/signup">/signup</a> — Create account (7-day free trial)</code>
    <code>GET <a href="/.well-known/oauth-authorization-server">/.well-known/oauth-authorization-server</a> — OAuth metadata</code>
    <code>POST /mcp — MCP endpoint (requires auth)</code>
    <code>GET <a href="/health">/health</a> — Server status</code>
  </div>
  <a class="cta" href="/.well-known/oauth-authorization-server">View API</a>
  <div class="foot">Powered by MCP &middot; OAuth 2.1 + PKCE &middot; Stripe Billing</div>
</div>
</body>
</html>`));

  // Mount auth routes (OAuth 2.1)
  app.route('/', authRoutes);

  // Mount Stripe webhook routes
  app.route('/', webhookRoutes);

  // Mount Procore integration routes
  app.route('/', procoreRoutes);

  // Mount admin API routes
  app.route('/', adminRoutes);

  // Mount billing checkout routes
  app.route('/', checkoutRoutes);

  // Mount monitoring routes
  app.route('/', statusRoutes);

  // Get MCP request handler (raw Node.js handler)
  const mcpHandler = getMcpRequestHandler(() => createMcpServer());

  // Create HTTP server
  const server = serve({
    fetch: app.fetch,
    port: config.PORT,
    createServer: ((...args: any[]) => {
      const requestListener = typeof args[0] === 'function' ? args[0] : args[1];
      const httpServer = createServer(requestListener);

      // Intercept /mcp requests before Hono
      const originalEmit = httpServer.emit.bind(httpServer);
      httpServer.emit = function (event: string, ...emitArgs: any[]) {
        if (event === 'request') {
          const [req, res] = emitArgs;
          if (req.url?.startsWith('/mcp')) {
            mcpHandler(req, res).catch((err: Error) => {
              logger.error({ err }, 'MCP handler error');
              if (!res.headersSent) {
                res.writeHead(500, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ error: 'Internal server error' }));
              }
            });
            return true;
          }
        }
        return originalEmit(event, ...emitArgs);
      } as any;

      return httpServer;
    }) as any,
  });

  logger.info(`ConstructionAI MCP Server running on port ${config.PORT}`);
  logger.info(`OAuth metadata: ${config.SERVER_URL}/.well-known/oauth-authorization-server`);
  logger.info(`MCP endpoint: ${config.SERVER_URL}/mcp`);

  // Graceful shutdown
  const shutdown = async () => {
    logger.info('Shutting down...');
    await worker.close();
    await redis.quit();
    const pool = getPool();
    await pool.end();
    process.exit(0);
  };

  process.on('SIGTERM', shutdown);
  process.on('SIGINT', shutdown);
}

main().catch((err) => {
  logger.fatal({ err }, 'Failed to start server');
  process.exit(1);
});
