import { z } from 'zod';
import { eq, and, or, lt, ne } from 'drizzle-orm';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import { scheduleTasks } from '../../db/schema.js';
import { requireContext, executeWithMiddleware, validateProjectAccess, textContent, errorContent } from '../../lib/tool-helpers.js';

export function register(server: McpServer) {
  server.tool(
    'flag_delayed_tasks',
    'Tasks behind schedule with impact assessment',
    {
      project_id: z.string().uuid(),
      threshold_days: z.number().optional().default(0),
    },
    async (args, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'flag_delayed_tasks', async () => {
      await validateProjectAccess(args.project_id, ctx.orgId);
      const db = getDb();
      const today = new Date().toISOString().split('T')[0];

      const tasks = await db.select().from(scheduleTasks).where(
        and(
          eq(scheduleTasks.projectId, args.project_id),
          or(
            eq(scheduleTasks.status, 'delayed'),
            and(lt(scheduleTasks.endDate, today), ne(scheduleTasks.status, 'complete')),
          ),
        ),
      );

      const flagged = tasks
        .map((t) => {
          const endDate = t.endDate ? new Date(t.endDate) : null;
          const daysBehind = endDate ? Math.max(0, Math.floor((Date.now() - endDate.getTime()) / 86400000)) : 0;
          const impactLevel = t.isCriticalPath ? 'critical_impact' : daysBehind > 14 ? 'high_impact' : 'moderate_impact';

          return {
            id: t.id,
            task_name: t.taskName,
            wbs_code: t.wbsCode,
            planned_end: t.endDate,
            days_behind: daysBehind,
            is_critical_path: t.isCriticalPath,
            impact_level: impactLevel,
            percent_complete: Number(t.percentComplete || 0),
            assigned_to: t.assignedTo,
            successor_ids: t.successorIds || [],
          };
        })
        .filter((t) => t.days_behind >= args.threshold_days)
        .sort((a, b) => b.days_behind - a.days_behind);

      return textContent({
        delayed_tasks: flagged,
        summary: {
          total_delayed: flagged.length,
          critical_impact: flagged.filter((f) => f.impact_level === 'critical_impact').length,
          max_days_behind: flagged.length > 0 ? flagged[0].days_behind : 0,
          avg_days_behind: flagged.length > 0 ? Math.round(flagged.reduce((s, f) => s + f.days_behind, 0) / flagged.length) : 0,
        },
      });
      });
    },
  );
}
