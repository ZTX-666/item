import { z } from 'zod';
import { eq, and, like, sql } from 'drizzle-orm';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import { budgetLines } from '../../db/schema.js';
import { requireContext, executeWithMiddleware, validateProjectAccess, textContent, errorContent } from '../../lib/tool-helpers.js';

export function register(server: McpServer) {
  server.tool(
    'get_budget_by_cost_code',
    'Budget data by CSI cost code. Original budget, approved changes, committed, actual, projected variance.',
    {
      project_id: z.string().uuid(),
      cost_code_filter: z.string().optional().describe('e.g. "03" for Division 3'),
      show_only_overruns: z.boolean().optional().default(false),
    },
    async (args, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'get_budget_by_cost_code', async () => {
        await validateProjectAccess(args.project_id, ctx.orgId);

        const db = getDb();
        const conditions: any[] = [eq(budgetLines.projectId, args.project_id)];

        if (args.cost_code_filter) {
          conditions.push(like(budgetLines.costCode, `${args.cost_code_filter}%`));
        }

        let rows = await db.select().from(budgetLines).where(and(...conditions));

        const mapped = rows.map((r) => {
          const revised = Number(r.originalBudget || 0) + Number(r.approvedChanges || 0);
          const consumed = Number(r.actualCosts || 0) + Number(r.committedCosts || 0);
          return {
            ...r,
            revised_budget: revised,
            total_consumed: consumed,
            percent_consumed: revised > 0 ? Math.round((consumed / revised) * 10000) / 100 : 0,
            projected_variance: revised - consumed,
          };
        });

        const result = args.show_only_overruns
          ? mapped.filter((m) => m.total_consumed > m.revised_budget)
          : mapped;

        const totals = {
          total_original_budget: mapped.reduce((s, m) => s + Number(m.originalBudget || 0), 0),
          total_approved_changes: mapped.reduce((s, m) => s + Number(m.approvedChanges || 0), 0),
          total_revised_budget: mapped.reduce((s, m) => s + m.revised_budget, 0),
          total_committed: mapped.reduce((s, m) => s + Number(m.committedCosts || 0), 0),
          total_actual: mapped.reduce((s, m) => s + Number(m.actualCosts || 0), 0),
        };

        return textContent({ budget_lines: result, totals });
      });
    },
  );
}
