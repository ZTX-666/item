import { z } from 'zod';
import { eq, and, gte, lte, desc, sql } from 'drizzle-orm';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import {
  dailyLogs,
  rfis,
  changeOrders,
  budgetLines,
  scheduleTasks,
  safetyIncidents,
  projects,
} from '../../db/schema.js';
import { requireContext, executeWithMiddleware, validateProjectAccess, textContent, errorContent } from '../../lib/tool-helpers.js';

export function register(server: McpServer) {
  server.tool(
    'generate_weekly_report',
    'AI-assisted: Comprehensive weekly report from daily logs, RFIs, COs, budget, schedule. Formatted for owner/stakeholder distribution.',
    {
      project_id: z.string().uuid(),
      week_ending: z.string().describe('Date string YYYY-MM-DD'),
    },
    async (args, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'generate_weekly_report', async () => {
        await validateProjectAccess(args.project_id, ctx.orgId);

        const db = getDb();
        const weekEnd = new Date(args.week_ending);
        const weekStart = new Date(weekEnd);
        weekStart.setDate(weekStart.getDate() - 6);
        const startStr = weekStart.toISOString().split('T')[0];
        const endStr = args.week_ending;

        const [project] = await db.select().from(projects).where(eq(projects.id, args.project_id)).limit(1);
        if (!project) return textContent({ error: 'Project not found' });

        const logs = await db.select().from(dailyLogs)
          .where(and(eq(dailyLogs.projectId, args.project_id), gte(dailyLogs.logDate, startStr), lte(dailyLogs.logDate, endStr)))
          .orderBy(dailyLogs.logDate);

        const weekRfis = await db.select().from(rfis)
          .where(and(eq(rfis.projectId, args.project_id), gte(rfis.createdAt, weekStart)));

        const weekCos = await db.select().from(changeOrders)
          .where(and(eq(changeOrders.projectId, args.project_id), gte(changeOrders.createdAt, weekStart)));

        const budget = await db.select().from(budgetLines).where(eq(budgetLines.projectId, args.project_id));

        const schedule = await db.select().from(scheduleTasks).where(eq(scheduleTasks.projectId, args.project_id));

        const incidents = await db.select().from(safetyIncidents)
          .where(and(eq(safetyIncidents.projectId, args.project_id), gte(safetyIncidents.incidentDate, weekStart)));

        const totalBudget = budget.reduce((s, b) => s + Number(b.originalBudget || 0) + Number(b.approvedChanges || 0), 0);
        const totalActual = budget.reduce((s, b) => s + Number(b.actualCosts || 0), 0);
        const totalWorkers = logs.reduce((s, l) => s + (l.totalHeadcount || 0), 0);
        const avgSchedule = schedule.length > 0 ? schedule.reduce((s, t) => s + Number(t.percentComplete || 0), 0) / schedule.length : 0;

        const report = {
          report_type: 'weekly',
          project: { name: project.name, number: project.projectNumber },
          period: { start: startStr, end: endStr },
          executive_summary: `Weekly report for ${project.name} covering ${startStr} to ${endStr}. ${logs.length} work days logged. ${weekRfis.length} RFIs, ${weekCos.length} change orders processed.`,
          work_completed: logs.map((l) => ({ date: l.logDate, summary: l.workPerformed })),
          workforce_summary: { total_worker_days: totalWorkers, daily_logs_count: logs.length, avg_daily_headcount: logs.length > 0 ? Math.round(totalWorkers / logs.length) : 0 },
          weather_impact: logs.filter((l) => l.weatherConditions && !['clear', 'partly_cloudy'].includes(l.weatherConditions)).map((l) => ({ date: l.logDate, condition: l.weatherConditions, delay_hours: l.delayHours })),
          rfi_activity: { new_this_week: weekRfis.length, open: weekRfis.filter((r) => r.status === 'open').length, answered: weekRfis.filter((r) => r.status === 'answered').length },
          co_activity: { new_this_week: weekCos.length, pending: weekCos.filter((c) => c.status === 'pending').length, total_pending_amount: weekCos.filter((c) => c.status === 'pending').reduce((s, c) => s + Number(c.totalWithMarkup || c.costAmount || 0), 0) },
          budget_status: { total_budget: totalBudget, spent_to_date: totalActual, percent_consumed: totalBudget > 0 ? Math.round((totalActual / totalBudget) * 100) : 0 },
          schedule_status: { overall_percent_complete: Math.round(avgSchedule), critical_tasks: schedule.filter((t) => t.isCriticalPath).length, delayed_tasks: schedule.filter((t) => t.status === 'delayed').length },
          safety_summary: { incidents_this_week: incidents.length, types: incidents.map((i) => i.incidentType) },
          look_ahead: 'Next week planning and priorities to be determined by project management team.',
          issues_requiring_attention: [
            ...(totalBudget > 0 && (totalActual / totalBudget) > 0.9 ? [{ type: 'budget', message: 'Budget consumption exceeds 90%' }] : []),
            ...schedule.filter((t) => t.status === 'delayed' && t.isCriticalPath).map((t) => ({ type: 'schedule', message: `Critical task delayed: ${t.taskName}` })),
          ],
          ai_note: 'This report was generated from project data. AI-enhanced narrative generation available in production.',
        };

        return textContent(report);
      });
    },
  );
}
