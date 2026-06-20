import { z } from 'zod';
import { eq, and, desc, sql, sum } from 'drizzle-orm';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import { changeOrders, projects, budgetLines, scheduleTasks, rfis } from '../../db/schema.js';
import { requireContext, executeWithMiddleware, validateProjectAccess, textContent, errorContent } from '../../lib/tool-helpers.js';

export function register(server: McpServer) {
  server.tool(
    'approve_change_order',
    'Approve a pending change order. Updates budget lines with approved changes. Requires admin scope.',
    {
      change_order_id: z.string().uuid(),
      approved_amount: z.number().optional().describe('Override the cost amount with an approved amount'),
      notes: z.string().optional().describe('Approval notes or conditions'),
    },
    async (params, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'approve_change_order', async () => {
        try {
          const db = getDb();

          // Get the change order
          const [co] = await db
            .select()
            .from(changeOrders)
            .where(eq(changeOrders.id, params.change_order_id))
            .limit(1);

          if (!co) {
            return errorContent(`Change order not found: ${params.change_order_id}`);
          }

          await validateProjectAccess(co.projectId, ctx.orgId);

          // Verify status is pending
          if (co.status !== 'pending') {
            return errorContent(
              `Change order cannot be approved. Current status is '${co.status}', expected 'pending'.`,
            );
          }

          const today = new Date().toISOString().split('T')[0];

          // Determine final amounts
          let finalCostAmount = parseFloat(co.costAmount);
          let finalMarkupAmount = parseFloat(co.markupAmount ?? '0');
          let finalTotalWithMarkup = parseFloat(co.totalWithMarkup ?? '0');

          if (params.approved_amount !== undefined) {
            finalCostAmount = params.approved_amount;
            // Recalculate markup using the original markup percentage
            const originalCost = parseFloat(co.costAmount);
            const originalMarkup = parseFloat(co.markupAmount ?? '0');
            const markupPercentage = originalCost !== 0
              ? (originalMarkup / originalCost) * 100
              : 0;
            finalMarkupAmount = finalCostAmount * markupPercentage / 100;
            finalTotalWithMarkup = finalCostAmount + finalMarkupAmount;
          }

          // Update the change order to approved
          const [updated] = await db
            .update(changeOrders)
            .set({
              status: 'approved',
              approvedDate: today,
              approvedBy: 'system',
              costAmount: finalCostAmount.toFixed(2),
              markupAmount: finalMarkupAmount.toFixed(2),
              totalWithMarkup: finalTotalWithMarkup.toFixed(2),
              description: params.notes
                ? `${co.description ?? ''}\n\n--- Approval Notes ---\n${params.notes}`.trim()
                : co.description,
              updatedAt: new Date(),
            })
            .where(eq(changeOrders.id, params.change_order_id))
            .returning();

          // Update budget lines: distribute the approved amount
          // Find existing budget lines for this project and update the first relevant one
          const projectBudgetLines = await db
            .select()
            .from(budgetLines)
            .where(eq(budgetLines.projectId, co.projectId))
            .limit(10);

          let budgetLineUpdated = false;

          if (projectBudgetLines.length > 0) {
            // Update the first budget line's approved_changes by adding the CO total
            const targetLine = projectBudgetLines[0];
            const currentApprovedChanges = parseFloat(targetLine.approvedChanges ?? '0');
            const newApprovedChanges = currentApprovedChanges + finalTotalWithMarkup;
            const originalBudget = parseFloat(targetLine.originalBudget);
            const newRevisedBudget = originalBudget + newApprovedChanges;

            await db
              .update(budgetLines)
              .set({
                approvedChanges: newApprovedChanges.toFixed(2),
                revisedBudget: newRevisedBudget.toFixed(2),
                updatedAt: new Date(),
              })
              .where(eq(budgetLines.id, targetLine.id));

            budgetLineUpdated = true;
          }

          return textContent({
            message: `Change order CO-${String(co.coNumber).padStart(3, '0')} approved successfully`,
            change_order: updated,
            budget_update: budgetLineUpdated
              ? {
                  status: 'updated',
                  amount_distributed: finalTotalWithMarkup,
                  note: 'Approved amount distributed to first matching budget line',
                }
              : {
                  status: 'skipped',
                  note: 'No budget lines found for this project. Approved amount not distributed.',
                },
          });
        } catch (err) {
          return errorContent(`Failed to approve change order: ${err instanceof Error ? err.message : String(err)}`);
        }
      });
    },
  );
}
