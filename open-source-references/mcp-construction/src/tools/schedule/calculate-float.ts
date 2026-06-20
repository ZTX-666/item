import { z } from 'zod';
import { eq } from 'drizzle-orm';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import { scheduleTasks } from '../../db/schema.js';
import { requireContext, executeWithMiddleware, validateProjectAccess, textContent, errorContent } from '../../lib/tool-helpers.js';

export function register(server: McpServer) {
  server.tool(
    'calculate_float',
    'Total and free float for all schedule tasks',
    {
      project_id: z.string().uuid(),
    },
    async (args, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'calculate_float', async () => {
      await validateProjectAccess(args.project_id, ctx.orgId);
      const db = getDb();
      const tasks = await db.select().from(scheduleTasks).where(eq(scheduleTasks.projectId, args.project_id));

      const taskFloats = tasks.map((t) => ({
        id: t.id,
        task_name: t.taskName,
        wbs_code: t.wbsCode,
        total_float_days: t.totalFloatDays ?? null,
        free_float_days: t.freeFloatDays ?? null,
        is_critical_path: t.isCriticalPath,
        status: t.status,
      }));

      const withFloat = taskFloats.filter((t) => t.total_float_days !== null);
      const zeroFloat = withFloat.filter((t) => t.total_float_days === 0);
      const nearCritical = withFloat.filter((t) => (t.total_float_days ?? 0) > 0 && (t.total_float_days ?? 0) < 5);
      const avgFloat = withFloat.length > 0
        ? Math.round(withFloat.reduce((s, t) => s + (t.total_float_days ?? 0), 0) / withFloat.length * 10) / 10
        : 0;

      return textContent({
        tasks: taskFloats,
        summary: {
          total_tasks: tasks.length,
          tasks_with_zero_float: zeroFloat.length,
          tasks_near_critical: nearCritical.length,
          average_float_days: avgFloat,
          max_float_days: withFloat.length > 0 ? Math.max(...withFloat.map((t) => t.total_float_days ?? 0)) : 0,
        },
      });
      });
    },
  );
}
