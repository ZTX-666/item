import { z } from 'zod';
import { eq } from 'drizzle-orm';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import { budgetLines } from '../../db/schema.js';
import { requireContext, executeWithMiddleware, validateProjectAccess, textContent, errorContent } from '../../lib/tool-helpers.js';

export function register(server: McpServer) {
  server.tool(
    'flag_budget_overruns',
    'Scans all cost codes, identifies lines where actual+committed exceed revised budget threshold',
    {
      project_id: z.string().uuid(),
      threshold_percentage: z.number().min(0).max(100).optional().default(90),
    },
    async (args, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'flag_budget_overruns', async () => {
        await validateProjectAccess(args.project_id, ctx.orgId);

        const db = getDb();
        const rows = await db.select().from(budgetLines).where(eq(budgetLines.projectId, args.project_id));

        const flagged = rows
          .map((r) => {
            const revised = Number(r.originalBudget || 0) + Number(r.approvedChanges || 0);
            const actual = Number(r.actualCosts || 0);
            const committed = Number(r.committedCosts || 0);
            const consumed = actual + committed;
            const pct = revised > 0 ? (consumed / revised) * 100 : 0;
            const overAmount = consumed - revised;

            let severity: string;
            let recommendation: string;
            if (pct >= 100) {
              severity = 'over_budget';
              recommendation = `Over budget by $${overAmount.toFixed(2)}. Immediate review required. Consider change order or reallocation.`;
            } else if (pct >= 95) {
              severity = 'critical';
              recommendation = `At ${pct.toFixed(1)}% consumption. Will likely exceed budget. Review remaining scope and committed costs.`;
            } else {
              severity = 'warning';
              recommendation = `Approaching threshold at ${pct.toFixed(1)}%. Monitor closely for remaining work.`;
            }

            return {
              cost_code: r.costCode,
              description: r.description,
              revised_budget: revised,
              actual,
              committed,
              percent_consumed: Math.round(pct * 100) / 100,
              over_amount: overAmount > 0 ? overAmount : 0,
              severity,
              recommendation,
            };
          })
          .filter((item) => item.percent_consumed >= args.threshold_percentage)
          .sort((a, b) => b.percent_consumed - a.percent_consumed);

        return textContent({
          flagged_items: flagged,
          summary: {
            total_lines_checked: rows.length,
            lines_flagged: flagged.length,
            over_budget: flagged.filter((f) => f.severity === 'over_budget').length,
            critical: flagged.filter((f) => f.severity === 'critical').length,
            warning: flagged.filter((f) => f.severity === 'warning').length,
          },
        });
      });
    },
  );
}
