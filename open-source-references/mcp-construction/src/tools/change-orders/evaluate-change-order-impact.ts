import { z } from 'zod';
import { eq, and, desc, sql, sum } from 'drizzle-orm';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import { changeOrders, projects, budgetLines, scheduleTasks, rfis } from '../../db/schema.js';
import { requireContext, executeWithMiddleware, validateProjectAccess, textContent, errorContent } from '../../lib/tool-helpers.js';

export function register(server: McpServer) {
  server.tool(
    'evaluate_change_order_impact',
    'Analyzes financial and schedule impact of a change order against current budget and critical path',
    {
      change_order_id: z.string().uuid(),
    },
    async (params, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'evaluate_change_order_impact', async () => {
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

          // Get the project
          const [project] = await db
            .select()
            .from(projects)
            .where(eq(projects.id, co.projectId))
            .limit(1);

          if (!project) {
            return errorContent(`Project not found for change order`);
          }

          // Sum all approved change orders for this project
          const [approvedSum] = await db
            .select({
              total: sql<string>`coalesce(sum(${changeOrders.totalWithMarkup}), '0')`,
              count: sql<number>`count(*)`,
            })
            .from(changeOrders)
            .where(
              and(
                eq(changeOrders.projectId, co.projectId),
                eq(changeOrders.status, 'approved'),
              ),
            );

          const approvedChangesToDate = parseFloat(approvedSum?.total ?? '0');
          const approvedCount = approvedSum?.count ?? 0;

          // Get budget totals from budget_lines
          const [budgetTotals] = await db
            .select({
              totalOriginalBudget: sql<string>`coalesce(sum(${budgetLines.originalBudget}), '0')`,
              totalApprovedChanges: sql<string>`coalesce(sum(${budgetLines.approvedChanges}), '0')`,
              totalRevisedBudget: sql<string>`coalesce(sum(${budgetLines.revisedBudget}), '0')`,
              totalActualCosts: sql<string>`coalesce(sum(${budgetLines.actualCosts}), '0')`,
              totalCommittedCosts: sql<string>`coalesce(sum(${budgetLines.committedCosts}), '0')`,
            })
            .from(budgetLines)
            .where(eq(budgetLines.projectId, co.projectId));

          // Get critical path tasks
          const criticalTasks = await db
            .select()
            .from(scheduleTasks)
            .where(
              and(
                eq(scheduleTasks.projectId, co.projectId),
                eq(scheduleTasks.isCriticalPath, true),
              ),
            );

          // Compute budget impact
          const currentContract = parseFloat(project.contractAmount ?? '0');
          const proposedChange = parseFloat(co.totalWithMarkup ?? '0');
          const newTotal = currentContract + approvedChangesToDate + proposedChange;
          const percentChange = currentContract > 0
            ? (proposedChange / currentContract) * 100
            : 0;
          const cumulativePercentChange = currentContract > 0
            ? ((approvedChangesToDate + proposedChange) / currentContract) * 100
            : 0;

          // Compute schedule impact
          const currentCompletion = project.estimatedCompletion;
          let proposedNewCompletion: string | null = null;
          if (currentCompletion && co.scheduleDays && co.scheduleDays > 0) {
            const completionDate = new Date(currentCompletion);
            completionDate.setDate(completionDate.getDate() + co.scheduleDays);
            proposedNewCompletion = completionDate.toISOString().split('T')[0];
          }

          // Check if any critical tasks could be affected by the schedule delay
          const criticalPathAffected = criticalTasks.filter((task) => {
            if (!task.endDate || !currentCompletion) return false;
            // A critical task is affected if it hasn't completed and extends near project end
            const taskEnd = new Date(task.endDate);
            const projEnd = new Date(currentCompletion);
            const daysBeforeEnd = (projEnd.getTime() - taskEnd.getTime()) / (1000 * 60 * 60 * 24);
            return daysBeforeEnd <= (co.scheduleDays ?? 0) && parseFloat(task.percentComplete ?? '0') < 100;
          });

          // Risk assessment
          const absPercentChange = Math.abs(percentChange);
          let riskLevel: string;
          let riskFactors: string[] = [];

          if (absPercentChange > 5) {
            riskLevel = 'high';
            riskFactors.push(`Single CO represents ${absPercentChange.toFixed(2)}% of contract (>5%)`);
          } else if (absPercentChange > 2) {
            riskLevel = 'medium';
            riskFactors.push(`Single CO represents ${absPercentChange.toFixed(2)}% of contract (>2%)`);
          } else {
            riskLevel = 'low';
          }

          if (Math.abs(cumulativePercentChange) > 10) {
            riskLevel = 'high';
            riskFactors.push(`Cumulative changes would reach ${cumulativePercentChange.toFixed(2)}% of original contract`);
          }

          if (criticalPathAffected.length > 0) {
            if (riskLevel !== 'high') riskLevel = 'medium';
            riskFactors.push(`${criticalPathAffected.length} critical path task(s) may be affected`);
          }

          if ((co.scheduleDays ?? 0) > 14) {
            riskFactors.push(`Schedule impact of ${co.scheduleDays} days is significant`);
          }

          if (riskFactors.length === 0) {
            riskFactors.push('Change is within normal project variance');
          }

          // Query similar past change orders (same reason across this project)
          const similarCOs = await db
            .select()
            .from(changeOrders)
            .where(
              and(
                eq(changeOrders.projectId, co.projectId),
                eq(changeOrders.reason, co.reason ?? ''),
              ),
            )
            .orderBy(desc(changeOrders.coNumber));

          const similarPastCOs = similarCOs
            .filter((c) => c.id !== co.id)
            .map((c) => ({
              co_number: c.coNumber,
              title: c.title,
              status: c.status,
              total_with_markup: c.totalWithMarkup,
            }));

          return textContent({
            change_order: {
              id: co.id,
              co_number: co.coNumber,
              title: co.title,
              status: co.status,
              reason: co.reason,
            },
            budget_impact: {
              current_contract: currentContract,
              approved_changes_to_date: approvedChangesToDate,
              approved_co_count: approvedCount,
              proposed_change: proposedChange,
              new_contract_total: newTotal,
              percent_change_this_co: parseFloat(percentChange.toFixed(2)),
              cumulative_percent_change: parseFloat(cumulativePercentChange.toFixed(2)),
              budget_totals: {
                original_budget: parseFloat(budgetTotals?.totalOriginalBudget ?? '0'),
                approved_changes: parseFloat(budgetTotals?.totalApprovedChanges ?? '0'),
                revised_budget: parseFloat(budgetTotals?.totalRevisedBudget ?? '0'),
                actual_costs: parseFloat(budgetTotals?.totalActualCosts ?? '0'),
                committed_costs: parseFloat(budgetTotals?.totalCommittedCosts ?? '0'),
              },
            },
            schedule_impact: {
              current_completion: currentCompletion,
              schedule_days_change: co.scheduleDays ?? 0,
              proposed_new_completion: proposedNewCompletion,
              critical_path_affected: criticalPathAffected.map((t) => ({
                id: t.id,
                task_name: t.taskName,
                end_date: t.endDate,
                percent_complete: t.percentComplete,
                total_float_days: t.totalFloatDays,
              })),
            },
            risk_assessment: {
              level: riskLevel,
              factors: riskFactors,
            },
            similar_past_change_orders: similarPastCOs,
          });
        } catch (err) {
          return errorContent(`Failed to evaluate change order impact: ${err instanceof Error ? err.message : String(err)}`);
        }
      });
    },
  );
}
