import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js';
import type { IncomingMessage, ServerResponse } from 'node:http';
import { getRedis } from '../lib/redis.js';
import { authenticateRequest, setRequestContext, clearRequestContext } from '../auth/middleware.js';
import { logger } from '../lib/logger.js';

const SESSION_TTL = 1800;
const transports = new Map<string, StreamableHTTPServerTransport>();

export function getMcpRequestHandler(createServer: () => McpServer) {
  return async (req: IncomingMessage, res: ServerResponse) => {
    const redis = getRedis();

    // Authenticate
    const authHeader = req.headers['authorization'] as string | undefined;
    let userContext;
    try {
      userContext = await authenticateRequest(authHeader);
    } catch (err: any) {
      res.writeHead(401, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ jsonrpc: '2.0', error: { code: -32001, message: err.message } }));
      return;
    }

    const sessionId = req.headers['mcp-session-id'] as string | undefined;

    if (req.method === 'DELETE') {
      if (sessionId && transports.has(sessionId)) {
        const transport = transports.get(sessionId)!;
        await transport.close();
        transports.delete(sessionId);
        await redis.del(`mcp:session:${sessionId}`);
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ closed: true }));
      } else {
        res.writeHead(404, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Session not found' }));
      }
      return;
    }

    if (req.method === 'GET') {
      // SSE stream for notifications
      if (sessionId && transports.has(sessionId)) {
        const transport = transports.get(sessionId)!;
        setRequestContext(sessionId, userContext);
        await transport.handleRequest(req, res);
        return;
      }
      res.writeHead(400, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Invalid session' }));
      return;
    }

    // POST — handle MCP messages
    if (sessionId && transports.has(sessionId)) {
      const transport = transports.get(sessionId)!;
      setRequestContext(sessionId, userContext);

      await redis.set(
        `mcp:session:${sessionId}`,
        JSON.stringify({ userId: userContext.userId, orgId: userContext.orgId }),
        'EX',
        SESSION_TTL,
      );

      await transport.handleRequest(req, res);
      clearRequestContext(sessionId);
      return;
    }

    // New session
    const transport = new StreamableHTTPServerTransport({
      sessionIdGenerator: () => crypto.randomUUID(),
      onsessioninitialized: (sid: string) => {
        transports.set(sid, transport);
        logger.info({ sessionId: sid }, 'MCP session initialized');
      },
    });

    transport.onclose = () => {
      const sid = transport.sessionId;
      if (sid) {
        transports.delete(sid);
        redis.del(`mcp:session:${sid}`).catch(() => {});
        logger.info({ sessionId: sid }, 'MCP session closed');
      }
    };

    const server = createServer();
    await server.connect(transport);

    const sid = transport.sessionId || 'pending';
    setRequestContext(sid, userContext);

    await transport.handleRequest(req, res);
    clearRequestContext(sid);
  };
}
