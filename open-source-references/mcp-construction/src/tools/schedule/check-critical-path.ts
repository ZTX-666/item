import { z } from 'zod';
import { eq, and, lte, or } from 'drizzle-orm';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import { scheduleTasks } from '../../db/schema.js';
import { requireContext, executeWithMiddleware, validateProjectAccess, textContent, errorContent } from '../../lib/tool-helpers.js';

export function register(server: McpServer) {
  server.tool(
    'check_critical_path',
    'Critical path tasks (zero total float). Optionally includes near-critical tasks (<5 days float).',
    {
      project_id: z.string().uuid(),
      include_near_critical: z.boolean().optional().default(false),
    },
    async (args, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'check_critical_path', async () => {
      await validateProjectAccess(args.project_id, ctx.orgId);
      const db = getDb();
      let conditions: any[];

      if (args.include_near_critical) {
        conditions = [
          eq(scheduleTasks.projectId, args.project_id),
          or(eq(scheduleTasks.isCriticalPath, true), lte(scheduleTasks.totalFloatDays, 5)),
        ];
      } else {
        conditions = [
          eq(scheduleTasks.projectId, args.project_id),
          eq(scheduleTasks.isCriticalPath, true),
        ];
      }

      const tasks = await db.select().from(scheduleTasks).where(and(...conditions));

      const critical = tasks.filter((t) => t.isCriticalPath);
      const nearCritical = tasks.filter((t) => !t.isCriticalPath);

      const startDates = tasks.map((t) => t.startDate).filter(Boolean).sort();
      const endDates = tasks.map((t) => t.endDate).filter(Boolean).sort();

      return textContent({
        critical_path_tasks: critical,
        near_critical_tasks: args.include_near_critical ? nearCritical : undefined,
        summary: {
          total_critical: critical.length,
          total_near_critical: nearCritical.length,
          earliest_start: startDates[0] || null,
          latest_end: endDates[endDates.length - 1] || null,
          delayed_critical: critical.filter((t) => t.status === 'delayed').length,
        },
      });
      });
    },
  );
}
