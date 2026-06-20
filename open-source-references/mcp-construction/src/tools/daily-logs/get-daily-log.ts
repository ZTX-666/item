import { z } from 'zod';
import { eq, and, desc, sql, sum, gte, lte, between } from 'drizzle-orm';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import { dailyLogs } from '../../db/schema.js';
import { requireContext, executeWithMiddleware, validateProjectAccess, textContent, errorContent } from '../../lib/tool-helpers.js';

export function register(server: McpServer) {
  server.tool(
    'get_daily_log',
    'Retrieve daily log for a specific date',
    {
      project_id: z.string().uuid(),
      log_date: z.string().describe('Date in YYYY-MM-DD format'),
    },
    async (params, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'get_daily_log', async () => {
        await validateProjectAccess(params.project_id, ctx.orgId);

        const db = getDb();

        const [log] = await db
          .select()
          .from(dailyLogs)
          .where(
            and(
              eq(dailyLogs.projectId, params.project_id),
              eq(dailyLogs.logDate, params.log_date),
            ),
          )
          .limit(1);

        if (!log) {
          return errorContent(
            `No daily log found for project ${params.project_id} on ${params.log_date}`,
          );
        }

        return textContent(log);
      });
    },
  );
}
