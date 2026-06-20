import { z } from 'zod';
import { eq, and, like } from 'drizzle-orm';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import { scheduleTasks } from '../../db/schema.js';
import { requireContext, executeWithMiddleware, validateProjectAccess, textContent, errorContent } from '../../lib/tool-helpers.js';

export function register(server: McpServer) {
  server.tool(
    'get_schedule',
    'Full project schedule with task dependencies and status',
    {
      project_id: z.string().uuid(),
      wbs_filter: z.string().optional(),
      status_filter: z.enum(['not_started', 'in_progress', 'complete', 'delayed']).optional(),
    },
    async (args, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'get_schedule', async () => {
      await validateProjectAccess(args.project_id, ctx.orgId);
      const db = getDb();
      const conditions: any[] = [eq(scheduleTasks.projectId, args.project_id)];
      if (args.wbs_filter) conditions.push(like(scheduleTasks.wbsCode, `${args.wbs_filter}%`));
      if (args.status_filter) conditions.push(eq(scheduleTasks.status, args.status_filter));

      const tasks = await db.select().from(scheduleTasks).where(and(...conditions));

      const summary = {
        total_tasks: tasks.length,
        not_started: tasks.filter((t) => t.status === 'not_started').length,
        in_progress: tasks.filter((t) => t.status === 'in_progress').length,
        complete: tasks.filter((t) => t.status === 'complete').length,
        delayed: tasks.filter((t) => t.status === 'delayed').length,
        critical_path_tasks: tasks.filter((t) => t.isCriticalPath).length,
        overall_percent_complete: tasks.length > 0
          ? Math.round(tasks.reduce((s, t) => s + Number(t.percentComplete || 0), 0) / tasks.length * 100) / 100
          : 0,
      };

      return textContent({ tasks, summary });
      });
    },
  );
}
