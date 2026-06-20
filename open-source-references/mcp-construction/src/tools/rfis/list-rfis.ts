import { z } from 'zod';
import { eq, and, desc, sql, count, lt } from 'drizzle-orm';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import { rfis } from '../../db/schema.js';
import { requireContext, executeWithMiddleware, validateProjectAccess, textContent, errorContent } from '../../lib/tool-helpers.js';

export function register(server: McpServer) {
  server.tool(
    'list_rfis',
    'List RFIs with filters. Default sort: newest first.',
    {
      project_id: z.string().uuid(),
      status: z.enum(['draft', 'open', 'answered', 'closed', 'void']).optional(),
      priority: z.enum(['low', 'normal', 'high', 'urgent']).optional(),
      assigned_to: z.string().optional(),
      overdue_only: z.boolean().optional(),
      page: z.number().int().positive().optional(),
      per_page: z.number().int().positive().max(100).optional(),
    },
    async (params, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'list_rfis', async () => {
        await validateProjectAccess(params.project_id, ctx.orgId);
        try {
          const db = getDb();
          const page = params.page ?? 1;
          const perPage = params.per_page ?? 25;
          const offset = (page - 1) * perPage;

          // Build filter conditions
          const conditions = [eq(rfis.projectId, params.project_id)];

          if (params.status) {
            conditions.push(eq(rfis.status, params.status));
          }

          if (params.priority) {
            conditions.push(eq(rfis.priority, params.priority));
          }

          if (params.assigned_to) {
            conditions.push(eq(rfis.assignedTo, params.assigned_to));
          }

          if (params.overdue_only) {
            const today = new Date().toISOString().split('T')[0];
            conditions.push(lt(rfis.dueDate, today));
            conditions.push(
              sql`${rfis.status} in ('draft', 'open')`,
            );
          }

          const whereClause = and(...conditions);

          // Get total count
          const [totalResult] = await db
            .select({ total: count() })
            .from(rfis)
            .where(whereClause);

          const total = totalResult?.total ?? 0;

          // Get paginated results, newest first
          const results = await db
            .select()
            .from(rfis)
            .where(whereClause)
            .orderBy(desc(rfis.createdAt))
            .limit(perPage)
            .offset(offset);

          return textContent({
            rfis: results,
            pagination: {
              page,
              per_page: perPage,
              total,
              total_pages: Math.ceil(total / perPage),
            },
          });
        } catch (err) {
          return errorContent(err instanceof Error ? err.message : 'Failed to list RFIs');
        }
      });
    },
  );
}
