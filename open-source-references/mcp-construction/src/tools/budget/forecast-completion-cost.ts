import { z } from 'zod';
import { eq } from 'drizzle-orm';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import { budgetLines, projects } from '../../db/schema.js';
import { requireContext, executeWithMiddleware, validateProjectAccess, textContent, errorContent } from '../../lib/tool-helpers.js';

export function register(server: McpServer) {
  server.tool(
    'forecast_completion_cost',
    'Projects Estimate at Completion (EAC) using CPI-based, bottom-up, and trend methods',
    {
      project_id: z.string().uuid(),
      method: z.enum(['cpi', 'bottom_up', 'trend', 'all']).optional().default('all'),
    },
    async (args, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'forecast_completion_cost', async () => {
        await validateProjectAccess(args.project_id, ctx.orgId);

        const db = getDb();
        const [project] = await db.select().from(projects).where(eq(projects.id, args.project_id)).limit(1);
        if (!project) return textContent({ error: 'Project not found' });

        const rows = await db.select().from(budgetLines).where(eq(budgetLines.projectId, args.project_id));

        const BAC = rows.reduce((s, r) => s + Number(r.originalBudget || 0) + Number(r.approvedChanges || 0), 0);
        const AC = rows.reduce((s, r) => s + Number(r.actualCosts || 0), 0);
        const EV = rows.reduce((s, r) => {
          const revised = Number(r.originalBudget || 0) + Number(r.approvedChanges || 0);
          const pctComplete = Number(r.percentComplete || 0) / 100;
          return s + revised * pctComplete;
        }, 0);

        const forecasts: Record<string, any> = {};

        if (args.method === 'cpi' || args.method === 'all') {
          const CPI = AC > 0 ? EV / AC : 1;
          const EAC_cpi = CPI > 0 ? BAC / CPI : BAC;
          forecasts.cpi = {
            method: 'CPI-based (EAC = BAC / CPI)',
            budget_at_completion: BAC,
            earned_value: EV,
            actual_cost: AC,
            cost_performance_index: Math.round(CPI * 1000) / 1000,
            estimate_at_completion: Math.round(EAC_cpi * 100) / 100,
            variance_at_completion: Math.round((BAC - EAC_cpi) * 100) / 100,
          };
        }

        if (args.method === 'bottom_up' || args.method === 'all') {
          const ETC = rows.reduce((s, r) => s + Number(r.estimatedCostToComplete || 0), 0);
          const EAC_bu = AC + ETC;
          forecasts.bottom_up = {
            method: 'Bottom-up (EAC = AC + ETC)',
            actual_cost: AC,
            estimated_cost_to_complete: ETC,
            estimate_at_completion: Math.round(EAC_bu * 100) / 100,
            variance_at_completion: Math.round((BAC - EAC_bu) * 100) / 100,
          };
        }

        if (args.method === 'trend' || args.method === 'all') {
          const overallPct = BAC > 0 ? (EV / BAC) : 0;
          const EAC_trend = overallPct > 0 ? AC / overallPct : BAC;
          forecasts.trend = {
            method: 'Trend-based (EAC = AC / % Complete)',
            actual_cost: AC,
            percent_complete: Math.round(overallPct * 10000) / 100,
            estimate_at_completion: Math.round(EAC_trend * 100) / 100,
            variance_at_completion: Math.round((BAC - EAC_trend) * 100) / 100,
          };
        }

        return textContent({
          project: { id: project.id, name: project.name, contract_amount: project.contractAmount },
          budget_at_completion: BAC,
          forecasts,
        });
      });
    },
  );
}
