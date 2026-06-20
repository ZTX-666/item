import { z } from 'zod';
import { eq, and, sql } from 'drizzle-orm';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import {
  projects,
  changeOrders,
  rfis,
  budgetLines,
  scheduleTasks,
  safetyIncidents,
  dailyLogs,
} from '../../db/schema.js';
import { textContent, errorContent, requireContext, executeWithMiddleware, validateProjectAccess } from '../../lib/tool-helpers.js';
import { notFound } from '../../lib/errors.js';

const GetProjectDashboardInput = z.object({
  project_id: z.string().uuid().describe('Unique project identifier'),
});

export function register(server: McpServer): void {
  server.tool(
    'get_project_dashboard',
    'Aggregated project health metrics: budget consumed, schedule complete, open RFIs, pending COs, safety incidents, and alerts',
    GetProjectDashboardInput.shape,
    async (args, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'get_project_dashboard', async () => {
        await validateProjectAccess(args.project_id, ctx.orgId);
        try {
          const db = getDb();
          const projectId = args.project_id;

          // Verify project exists
          const [project] = await db
            .select({
              id: projects.id,
              name: projects.name,
              status: projects.status,
              contractAmount: projects.contractAmount,
              startDate: projects.startDate,
              estimatedCompletion: projects.estimatedCompletion,
            })
            .from(projects)
            .where(eq(projects.id, projectId))
            .limit(1);

          if (!project) {
            throw notFound('Project');
          }

          // Run all aggregate queries in parallel for performance
          const [
            budgetAgg,
            scheduleAgg,
            rfiAgg,
            coAgg,
            safetyAgg,
            recentLogAgg,
          ] = await Promise.all([
            // ── Budget aggregation ──
            db
              .select({
                total_original_budget: sql<string>`coalesce(sum(${budgetLines.originalBudget}), '0')`,
                total_revised_budget: sql<string>`coalesce(sum(${budgetLines.revisedBudget}), '0')`,
                total_committed: sql<string>`coalesce(sum(${budgetLines.committedCosts}), '0')`,
                total_actual: sql<string>`coalesce(sum(${budgetLines.actualCosts}), '0')`,
                total_etc: sql<string>`coalesce(sum(${budgetLines.estimatedCostToComplete}), '0')`,
                total_eac: sql<string>`coalesce(sum(${budgetLines.estimatedCostAtCompletion}), '0')`,
                total_variance: sql<string>`coalesce(sum(${budgetLines.variance}), '0')`,
                line_count: sql<string>`count(*)::text`,
              })
              .from(budgetLines)
              .where(eq(budgetLines.projectId, projectId)),

            // ── Schedule aggregation ──
            db
              .select({
                total_tasks: sql<string>`count(*)::text`,
                completed_tasks: sql<string>`count(*) filter (where ${scheduleTasks.status} = 'complete')::text`,
                in_progress_tasks: sql<string>`count(*) filter (where ${scheduleTasks.status} = 'in_progress')::text`,
                not_started_tasks: sql<string>`count(*) filter (where ${scheduleTasks.status} = 'not_started')::text`,
                avg_percent_complete: sql<string>`coalesce(avg(${scheduleTasks.percentComplete}), 0)::text`,
                critical_path_tasks: sql<string>`count(*) filter (where ${scheduleTasks.isCriticalPath} = true)::text`,
                delayed_critical: sql<string>`count(*) filter (where ${scheduleTasks.isCriticalPath} = true and ${scheduleTasks.endDate} < current_date and ${scheduleTasks.status} != 'complete')::text`,
              })
              .from(scheduleTasks)
              .where(eq(scheduleTasks.projectId, projectId)),

            // ── RFI aggregation ──
            db
              .select({
                total_rfis: sql<string>`count(*)::text`,
                open_rfis: sql<string>`count(*) filter (where ${rfis.status} = 'open')::text`,
                overdue_rfis: sql<string>`count(*) filter (where ${rfis.status} = 'open' and ${rfis.dueDate} < current_date)::text`,
                closed_rfis: sql<string>`count(*) filter (where ${rfis.status} = 'closed')::text`,
                with_cost_impact: sql<string>`count(*) filter (where ${rfis.costImpact} = true)::text`,
                with_schedule_impact: sql<string>`count(*) filter (where ${rfis.scheduleImpact} = true)::text`,
              })
              .from(rfis)
              .where(eq(rfis.projectId, projectId)),

            // ── Change Order aggregation ──
            db
              .select({
                total_cos: sql<string>`count(*)::text`,
                pending_cos: sql<string>`count(*) filter (where ${changeOrders.status} = 'pending')::text`,
                approved_cos: sql<string>`count(*) filter (where ${changeOrders.status} = 'approved')::text`,
                rejected_cos: sql<string>`count(*) filter (where ${changeOrders.status} = 'rejected')::text`,
                total_approved_amount: sql<string>`coalesce(sum(${changeOrders.costAmount}) filter (where ${changeOrders.status} = 'approved'), '0')`,
                total_pending_amount: sql<string>`coalesce(sum(${changeOrders.costAmount}) filter (where ${changeOrders.status} = 'pending'), '0')`,
                total_schedule_days: sql<string>`coalesce(sum(${changeOrders.scheduleDays}) filter (where ${changeOrders.status} = 'approved'), 0)::text`,
              })
              .from(changeOrders)
              .where(eq(changeOrders.projectId, projectId)),

            // ── Safety aggregation ──
            db
              .select({
                total_incidents: sql<string>`count(*)::text`,
                open_incidents: sql<string>`count(*) filter (where ${safetyIncidents.status} = 'open')::text`,
                osha_recordable: sql<string>`count(*) filter (where ${safetyIncidents.oshaRecordable} = true)::text`,
                total_days_away: sql<string>`coalesce(sum(${safetyIncidents.daysAway}), 0)::text`,
                recent_30d: sql<string>`count(*) filter (where ${safetyIncidents.incidentDate} >= current_date - interval '30 days')::text`,
              })
              .from(safetyIncidents)
              .where(eq(safetyIncidents.projectId, projectId)),

            // ── Recent daily log count (last 7 days) ──
            db
              .select({
                logs_last_7d: sql<string>`count(*) filter (where ${dailyLogs.logDate} >= current_date - interval '7 days')::text`,
                latest_log_date: sql<string>`max(${dailyLogs.logDate})`,
              })
              .from(dailyLogs)
              .where(eq(dailyLogs.projectId, projectId)),
          ]);

          const budget = budgetAgg[0];
          const schedule = scheduleAgg[0];
          const rfi = rfiAgg[0];
          const co = coAgg[0];
          const safety = safetyAgg[0];
          const logs = recentLogAgg[0];

          // Parse numeric aggregates
          const totalRevisedBudget = parseFloat(budget.total_revised_budget);
          const totalActual = parseFloat(budget.total_actual);
          const totalEac = parseFloat(budget.total_eac);
          const originalContract = project.contractAmount
            ? parseFloat(project.contractAmount)
            : 0;
          const approvedCOsAmount = parseFloat(co.total_approved_amount);
          const currentContractTotal = originalContract + approvedCOsAmount;
          const budgetConsumedPct = totalRevisedBudget > 0
            ? Math.round((totalActual / totalRevisedBudget) * 10000) / 100
            : 0;

          const totalTasks = parseInt(schedule.total_tasks, 10);
          const completedTasks = parseInt(schedule.completed_tasks, 10);
          const scheduleCompletePct = totalTasks > 0
            ? Math.round((completedTasks / totalTasks) * 10000) / 100
            : 0;

          // ── Generate alerts ──
          const alerts: Array<{ severity: string; category: string; message: string }> = [];

          // Budget alert: over 90% consumed
          if (budgetConsumedPct > 90) {
            alerts.push({
              severity: 'high',
              category: 'budget',
              message: `Budget is ${budgetConsumedPct}% consumed (${formatCurrency(totalActual)} of ${formatCurrency(totalRevisedBudget)})`,
            });
          }

          // Budget alert: EAC exceeds revised budget
          if (totalEac > totalRevisedBudget && totalRevisedBudget > 0) {
            const overage = totalEac - totalRevisedBudget;
            alerts.push({
              severity: 'high',
              category: 'budget',
              message: `Estimated cost at completion exceeds budget by ${formatCurrency(overage)}`,
            });
          }

          // Schedule alert: delayed critical path tasks
          const delayedCritical = parseInt(schedule.delayed_critical, 10);
          if (delayedCritical > 0) {
            alerts.push({
              severity: 'critical',
              category: 'schedule',
              message: `${delayedCritical} critical path task(s) past due end date`,
            });
          }

          // RFI alert: overdue RFIs
          const overdueRfis = parseInt(rfi.overdue_rfis, 10);
          if (overdueRfis > 0) {
            alerts.push({
              severity: 'medium',
              category: 'rfi',
              message: `${overdueRfis} RFI(s) past due date without response`,
            });
          }

          // Safety alert: open incidents
          const openIncidents = parseInt(safety.open_incidents, 10);
          if (openIncidents > 0) {
            alerts.push({
              severity: 'high',
              category: 'safety',
              message: `${openIncidents} open safety incident(s) require resolution`,
            });
          }

          // Pending COs alert
          const pendingCos = parseInt(co.pending_cos, 10);
          const pendingAmount = parseFloat(co.total_pending_amount);
          if (pendingCos > 0) {
            alerts.push({
              severity: 'medium',
              category: 'change_order',
              message: `${pendingCos} pending change order(s) totaling ${formatCurrency(pendingAmount)} awaiting approval`,
            });
          }

          // Missing daily logs alert
          const logsLast7d = parseInt(logs.logs_last_7d, 10);
          if (logsLast7d < 5 && project.status === 'active') {
            alerts.push({
              severity: 'low',
              category: 'daily_log',
              message: `Only ${logsLast7d} daily log(s) filed in the past 7 days`,
            });
          }

          return textContent({
            project_id: project.id,
            project_name: project.name,
            project_status: project.status,
            contract: {
              original_amount: originalContract,
              approved_changes: approvedCOsAmount,
              current_total: currentContractTotal,
            },
            budget: {
              total_original: parseFloat(budget.total_original_budget),
              total_revised: totalRevisedBudget,
              total_committed: parseFloat(budget.total_committed),
              total_actual: totalActual,
              estimated_to_complete: parseFloat(budget.total_etc),
              estimated_at_completion: totalEac,
              total_variance: parseFloat(budget.total_variance),
              percent_consumed: budgetConsumedPct,
              line_count: parseInt(budget.line_count, 10),
            },
            schedule: {
              total_tasks: totalTasks,
              completed: completedTasks,
              in_progress: parseInt(schedule.in_progress_tasks, 10),
              not_started: parseInt(schedule.not_started_tasks, 10),
              avg_percent_complete: Math.round(parseFloat(schedule.avg_percent_complete) * 100) / 100,
              percent_tasks_complete: scheduleCompletePct,
              critical_path_tasks: parseInt(schedule.critical_path_tasks, 10),
              delayed_critical_tasks: delayedCritical,
            },
            rfis: {
              total: parseInt(rfi.total_rfis, 10),
              open: parseInt(rfi.open_rfis, 10),
              overdue: overdueRfis,
              closed: parseInt(rfi.closed_rfis, 10),
              with_cost_impact: parseInt(rfi.with_cost_impact, 10),
              with_schedule_impact: parseInt(rfi.with_schedule_impact, 10),
            },
            change_orders: {
              total: parseInt(co.total_cos, 10),
              pending: pendingCos,
              approved: parseInt(co.approved_cos, 10),
              rejected: parseInt(co.rejected_cos, 10),
              total_approved_amount: approvedCOsAmount,
              total_pending_amount: pendingAmount,
              total_schedule_impact_days: parseInt(co.total_schedule_days, 10),
            },
            safety: {
              total_incidents: parseInt(safety.total_incidents, 10),
              open_incidents: openIncidents,
              osha_recordable: parseInt(safety.osha_recordable, 10),
              total_days_away: parseInt(safety.total_days_away, 10),
              incidents_last_30d: parseInt(safety.recent_30d, 10),
            },
            daily_logs: {
              logs_last_7_days: logsLast7d,
              latest_log_date: logs.latest_log_date,
            },
            alerts,
          });
        } catch (err: any) {
          if (err.code === -32004) {
            return errorContent(err.message);
          }
          return errorContent(err.message ?? 'Failed to generate project dashboard');
        }
      });
    },
  );
}

/** Format a number as US currency string for alert messages */
function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}
