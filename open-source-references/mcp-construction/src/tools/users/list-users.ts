import { z } from 'zod';
import { eq } from 'drizzle-orm';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import { users } from '../../db/schema.js';
import { requireContext, executeWithMiddleware, textContent } from '../../lib/tool-helpers.js';

export function register(server: McpServer): void {
  server.tool(
    'list_users',
    'List all users in the caller\'s organization. Never returns password hashes.',
    {},
    async (_args, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'list_users', async () => {
        const db = getDb();

        const rows = await db
          .select({
            id: users.id,
            orgId: users.orgId,
            email: users.email,
            name: users.name,
            role: users.role,
            createdAt: users.createdAt,
          })
          .from(users)
          .where(eq(users.orgId, ctx.orgId));

        return textContent({ users: rows, total: rows.length });
      });
    },
  );
}
