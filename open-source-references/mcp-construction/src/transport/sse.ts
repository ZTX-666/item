import { Hono } from 'hono';
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { SSEServerTransport } from '@modelcontextprotocol/sdk/server/sse.js';
import { authenticateRequest, setRequestContext, clearRequestContext } from '../auth/middleware.js';
import { logger } from '../lib/logger.js';

const sseTransports = new Map<string, SSEServerTransport>();

export function createSseRoutes(createServer: () => McpServer): Hono {
  const app = new Hono();

  // SSE connection endpoint
  app.get('/sse', async (c) => {
    let userContext;
    try {
      userContext = await authenticateRequest(c.req.header('Authorization'));
    } catch (err: any) {
      return c.json({ error: err.message }, 401);
    }

    const sessionId = crypto.randomUUID();

    return new Response(
      new ReadableStream({
        start(controller) {
          const encoder = new TextEncoder();
          const transport = new SSEServerTransport('/messages', {
            send(data: string) {
              controller.enqueue(encoder.encode(`data: ${data}\n\n`));
            },
          } as any);

          sseTransports.set(sessionId, transport);
          setRequestContext(sessionId, userContext);

          transport.onclose = () => {
            sseTransports.delete(sessionId);
            clearRequestContext(sessionId);
            controller.close();
            logger.info({ sessionId }, 'SSE session closed');
          };

          const server = createServer();
          server.connect(transport).catch((err: Error) => {
            logger.error({ err }, 'SSE connect failed');
          });

          logger.info({ sessionId }, 'SSE session established');
        },
      }),
      {
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
          Connection: 'keep-alive',
        },
      },
    );
  });

  // Message endpoint for SSE transport
  app.post('/messages', async (c) => {
    const sessionId = c.req.query('sessionId');
    if (!sessionId || !sseTransports.has(sessionId)) {
      return c.json({ error: 'Invalid session' }, 400);
    }

    let userContext;
    try {
      userContext = await authenticateRequest(c.req.header('Authorization'));
    } catch (err: any) {
      return c.json({ error: err.message }, 401);
    }

    setRequestContext(sessionId, userContext);
    const transport = sseTransports.get(sessionId)!;
    const body = await c.req.json();

    // Handle the incoming message
    if (typeof (transport as any).handleMessage === 'function') {
      await (transport as any).handleMessage(body);
    }

    return c.json({ ok: true });
  });

  return app;
}
