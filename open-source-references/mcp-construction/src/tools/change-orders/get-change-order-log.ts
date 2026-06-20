import { z } from 'zod';
import { eq, and, desc, sql, sum } from 'drizzle-orm';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import { changeOrders, projects, budgetLines, scheduleTasks, rfis } from '../../db/schema.js';
import { requireContext, executeWithMiddleware, validateProjectAccess, textContent, errorContent } from '../../lib/tool-helpers.js';

export function register(server: McpServer) {
  server.tool(
    'get_change_order_log',
    'Full change order log with running contract total',
    {
      project_id: z.string().uuid(),
      status_filter: z
        .enum(['draft', 'pending', 'approved', 'rejected', 'void'])
        .optional()
        .describe('Filter change orders by status'),
    },
    async (params, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'get_change_order_log', async () => {
        await validateProjectAccess(params.project_id, ctx.orgId);
        try {
          const db = getDb();

          // Get the project for original contract amount
          const [project] = await db
            .select()
            .from(projects)
            .where(eq(projects.id, params.project_id))
            .limit(1);

          if (!project) {
            return errorContent(`Project not found: ${params.project_id}`);
          }

          // Build conditions for the query
          const conditions = [eq(changeOrders.projectId, params.project_id)];
          if (params.status_filter) {
            conditions.push(eq(changeOrders.status, params.status_filter));
          }

          // Query all change orders for the project, ordered by co_number
          const cos = await db
            .select()
            .from(changeOrders)
            .where(and(...conditions))
            .orderBy(changeOrders.coNumber);

          // Calculate summary from ALL change orders (not filtered) for accurate totals
          const [approvedTotals] = await db
            .select({
              total: sql<string>`coalesce(sum(${changeOrders.totalWithMarkup}), '0')`,
              count: sql<number>`count(*)`,
            })
            .from(changeOrders)
            .where(
              and(
                eq(changeOrders.projectId, params.project_id),
                eq(changeOrders.status, 'approved'),
              ),
            );

          const [pendingTotals] = await db
            .select({
              total: sql<string>`coalesce(sum(${changeOrders.totalWithMarkup}), '0')`,
              count: sql<number>`count(*)`,
            })
            .from(changeOrders)
            .where(
              and(
                eq(changeOrders.projectId, params.project_id),
                eq(changeOrders.status, 'pending'),
              ),
            );

          const originalContract = parseFloat(project.contractAmount ?? '0');
          const totalApproved = parseFloat(approvedTotals?.total ?? '0');
          const totalPending = parseFloat(pendingTotals?.total ?? '0');
          const currentContract = originalContract + totalApproved;
          const projectedContract = currentContract + totalPending;

          // Build running total for each CO in the log
          let runningTotal = originalContract;
          const changeOrderLog = cos.map((co) => {
            const coTotal = parseFloat(co.totalWithMarkup ?? '0');
            if (co.status === 'approved') {
              runningTotal += coTotal;
            }
            return {
              id: co.id,
              co_number: `CO-${String(co.coNumber).padStart(3, '0')}`,
              title: co.title,
              description: co.description,
              reason: co.reason,
              status: co.status,
              cost_amount: co.costAmount,
              markup_amount: co.markupAmount,
              total_with_markup: co.totalWithMarkup,
              schedule_days: co.scheduleDays,
              related_rfi_id: co.relatedRfiId,
              submitted_date: co.submittedDate,
              approved_date: co.approvedDate,
              approved_by: co.approvedBy,
              running_contract_total: co.status === 'approved' ? runningTotal : null,
              created_at: co.createdAt,
            };
          });

          return textContent({
            project: {
              id: project.id,
              name: project.name,
              project_number: project.projectNumber,
            },
            change_orders: changeOrderLog,
            summary: {
              original_contract: originalContract,
              total_approved_changes: totalApproved,
              approved_co_count: approvedTotals?.count ?? 0,
              total_pending_changes: totalPending,
              pending_co_count: pendingTotals?.count ?? 0,
              current_contract: currentContract,
              projected_contract_with_pending: projectedContract,
              percent_change_from_original:
                originalContract > 0
                  ? parseFloat(((totalApproved / originalContract) * 100).toFixed(2))
                  : 0,
              total_change_orders_shown: cos.length,
              status_filter_applied: params.status_filter ?? 'none',
            },
          });
        } catch (err) {
          return errorContent(`Failed to retrieve change order log: ${err instanceof Error ? err.message : String(err)}`);
        }
      });
    },
  );
}
