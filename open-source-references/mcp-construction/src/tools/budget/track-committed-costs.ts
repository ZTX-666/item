import { z } from 'zod';
import { eq, and, like } from 'drizzle-orm';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import { budgetLines } from '../../db/schema.js';
import { requireContext, executeWithMiddleware, validateProjectAccess, textContent, errorContent } from '../../lib/tool-helpers.js';

export function register(server: McpServer) {
  server.tool(
    'track_committed_costs',
    'All committed costs (contracts + POs) by cost code',
    {
      project_id: z.string().uuid(),
      cost_code_filter: z.string().optional(),
    },
    async (args, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'track_committed_costs', async () => {
        await validateProjectAccess(args.project_id, ctx.orgId);

        const db = getDb();
        const conditions: any[] = [eq(budgetLines.projectId, args.project_id)];
        if (args.cost_code_filter) {
          conditions.push(like(budgetLines.costCode, `${args.cost_code_filter}%`));
        }

        const rows = await db.select().from(budgetLines).where(and(...conditions));

        const items = rows.map((r) => ({
          cost_code: r.costCode,
          description: r.description,
          committed_costs: Number(r.committedCosts || 0),
          actual_costs: Number(r.actualCosts || 0),
          remaining_committed: Number(r.committedCosts || 0) - Number(r.actualCosts || 0),
          revised_budget: Number(r.originalBudget || 0) + Number(r.approvedChanges || 0),
        }));

        return textContent({
          committed_costs: items,
          totals: {
            total_committed: items.reduce((s, i) => s + i.committed_costs, 0),
            total_actual: items.reduce((s, i) => s + i.actual_costs, 0),
            total_remaining_committed: items.reduce((s, i) => s + i.remaining_committed, 0),
          },
        });
      });
    },
  );
}
