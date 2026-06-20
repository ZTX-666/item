import { z } from 'zod';
import { eq } from 'drizzle-orm';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import { projects, budgetLines } from '../../db/schema.js';
import { requireContext, executeWithMiddleware, validateProjectAccess, textContent, errorContent } from '../../lib/tool-helpers.js';

export function register(server: McpServer) {
  server.tool(
    'generate_aia_payment_app',
    'Generates AIA G702/G703 payment application data matching form fields',
    {
      project_id: z.string().uuid(),
      application_number: z.number().int().min(1),
      period_to: z.string().describe('Date YYYY-MM-DD'),
      include_stored_materials: z.boolean().optional().default(false),
    },
    async (args, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'generate_aia_payment_app', async () => {
      await validateProjectAccess(args.project_id, ctx.orgId);
      const db = getDb();
      const [project] = await db.select().from(projects).where(eq(projects.id, args.project_id)).limit(1);
      if (!project) return textContent({ error: 'Project not found' });

      const budget = await db.select().from(budgetLines).where(eq(budgetLines.projectId, args.project_id));

      const retainageRate = 0.05;
      let itemNo = 0;

      const g703 = budget.map((line) => {
        itemNo++;
        const scheduledValue = Number(line.originalBudget || 0) + Number(line.approvedChanges || 0);
        const totalActual = Number(line.actualCosts || 0);
        const prevApplications = totalActual * 0.8;
        const thisPeriod = totalActual * 0.2;
        const materialsStored = args.include_stored_materials ? 0 : 0;
        const totalCompleted = prevApplications + thisPeriod + materialsStored;
        const pctComplete = scheduledValue > 0 ? Math.round((totalCompleted / scheduledValue) * 10000) / 100 : 0;
        const balanceToFinish = scheduledValue - totalCompleted;
        const retainage = totalCompleted * retainageRate;

        return {
          item_no: itemNo,
          description_of_work: line.description,
          cost_code: line.costCode,
          scheduled_value: scheduledValue,
          previous_applications: Math.round(prevApplications * 100) / 100,
          this_period: Math.round(thisPeriod * 100) / 100,
          materials_stored: materialsStored,
          total_completed: Math.round(totalCompleted * 100) / 100,
          percent_complete: pctComplete,
          balance_to_finish: Math.round(balanceToFinish * 100) / 100,
          retainage: Math.round(retainage * 100) / 100,
        };
      });

      const totalScheduled = g703.reduce((s, i) => s + i.scheduled_value, 0);
      const totalPrev = g703.reduce((s, i) => s + i.previous_applications, 0);
      const totalThis = g703.reduce((s, i) => s + i.this_period, 0);
      const totalCompleted = g703.reduce((s, i) => s + i.total_completed, 0);
      const totalRetainage = g703.reduce((s, i) => s + i.retainage, 0);

      const g702 = {
        application_number: args.application_number,
        period_to: args.period_to,
        project_name: project.name,
        project_number: project.projectNumber,
        contractor: project.projectManager || 'TBD',
        owner: project.ownerName || 'TBD',
        architect: project.architectName || 'TBD',
        contract_date: project.startDate,
        contract_for: project.name,
        original_contract_sum: Number(project.contractAmount || 0),
        net_change_by_change_orders: totalScheduled - Number(project.contractAmount || 0),
        contract_sum_to_date: totalScheduled,
        total_completed_and_stored: Math.round(totalCompleted * 100) / 100,
        retainage: Math.round(totalRetainage * 100) / 100,
        total_earned_less_retainage: Math.round((totalCompleted - totalRetainage) * 100) / 100,
        less_previous_certificates: Math.round(totalPrev * 100) / 100,
        current_payment_due: Math.round(totalThis * 100) / 100,
        balance_to_finish_including_retainage: Math.round((totalScheduled - totalCompleted + totalRetainage) * 100) / 100,
      };

      return textContent({ g702, g703 });
      });
    },
  );
}
