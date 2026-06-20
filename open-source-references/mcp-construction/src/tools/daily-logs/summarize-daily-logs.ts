import { z } from 'zod';
import { eq, and, desc, sql, sum, gte, lte, between } from 'drizzle-orm';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import { dailyLogs } from '../../db/schema.js';
import { requireContext, executeWithMiddleware, validateProjectAccess, textContent, errorContent } from '../../lib/tool-helpers.js';

export function register(server: McpServer) {
  server.tool(
    'summarize_daily_logs',
    'AI-assisted: Summarizes daily logs over a date range into executive narrative',
    {
      project_id: z.string().uuid(),
      start_date: z.string().describe('Start date in YYYY-MM-DD format'),
      end_date: z.string().describe('End date in YYYY-MM-DD format'),
    },
    async (params, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'summarize_daily_logs', async () => {
        await validateProjectAccess(params.project_id, ctx.orgId);

        const db = getDb();

        // Fetch all daily logs in the date range
        const logs = await db
          .select()
          .from(dailyLogs)
          .where(
            and(
              eq(dailyLogs.projectId, params.project_id),
              gte(dailyLogs.logDate, params.start_date),
              lte(dailyLogs.logDate, params.end_date),
            ),
          )
          .orderBy(dailyLogs.logDate);

        if (logs.length === 0) {
          return errorContent(
            `No daily logs found for project ${params.project_id} between ${params.start_date} and ${params.end_date}`,
          );
        }

        // Aggregate: total work days
        const totalWorkDays = logs.length;

        // Aggregate: total headcount across days
        const totalHeadcount = logs.reduce((acc, log) => acc + (log.totalHeadcount ?? 0), 0);
        const avgDailyHeadcount = totalWorkDays > 0 ? Math.round(totalHeadcount / totalWorkDays) : 0;

        // Weather summary: count occurrences of each condition
        const weatherCounts: Record<string, number> = {};
        for (const log of logs) {
          const condition = log.weatherConditions ?? 'not_recorded';
          weatherCounts[condition] = (weatherCounts[condition] ?? 0) + 1;
        }

        // Temperature range across the period
        const tempHighs = logs
          .map((l) => l.temperatureHigh)
          .filter((t): t is number => t !== null);
        const tempLows = logs
          .map((l) => l.temperatureLow)
          .filter((t): t is number => t !== null);

        const temperatureRange = {
          highest: tempHighs.length > 0 ? Math.max(...tempHighs) : null,
          lowest: tempLows.length > 0 ? Math.min(...tempLows) : null,
        };

        // Delays summary
        const logsWithDelays = logs.filter((l) => l.delays && l.delays.trim().length > 0);
        const totalDelayHours = logs.reduce(
          (acc, log) => acc + (log.delayHours ? parseFloat(log.delayHours) : 0),
          0,
        );
        const delayDescriptions = logsWithDelays.map((l) => ({
          date: l.logDate,
          delay: l.delays,
          hours: l.delayHours ? parseFloat(l.delayHours) : 0,
        }));

        // Work performed aggregation
        const workEntries = logs
          .filter((l) => l.workPerformed && l.workPerformed.trim().length > 0)
          .map((l) => ({
            date: l.logDate,
            work: l.workPerformed,
          }));

        // Materials received aggregation
        const materialsEntries = logs
          .filter((l) => l.materialsReceived && l.materialsReceived.trim().length > 0)
          .map((l) => ({
            date: l.logDate,
            materials: l.materialsReceived,
          }));

        // Build narrative template (AI stub -- a real implementation would use LLM)
        const narrative =
          `Over the ${totalWorkDays}-day period from ${params.start_date} to ${params.end_date}, ` +
          `an average of ${avgDailyHeadcount} workers were on site daily (${totalHeadcount} total worker-days). ` +
          `Weather was predominantly ${Object.entries(weatherCounts).sort((a, b) => b[1] - a[1])[0]?.[0] ?? 'not recorded'}. ` +
          (totalDelayHours > 0
            ? `${logsWithDelays.length} day(s) experienced delays totaling ${totalDelayHours} hours. `
            : 'No significant delays were recorded. ') +
          `Detailed work activities and materials deliveries are included in the breakdown below.`;

        const summary = {
          project_id: params.project_id,
          period: {
            start_date: params.start_date,
            end_date: params.end_date,
          },
          total_work_days: totalWorkDays,
          workforce: {
            total_headcount: totalHeadcount,
            average_daily_headcount: avgDailyHeadcount,
          },
          weather: {
            condition_counts: weatherCounts,
            temperature_range: temperatureRange,
          },
          delays: {
            days_with_delays: logsWithDelays.length,
            total_delay_hours: totalDelayHours,
            details: delayDescriptions,
          },
          work_performed: workEntries,
          materials_received: materialsEntries,
          executive_narrative: narrative,
          _ai_note:
            'This is a structured summary. Connect to an LLM for enhanced executive narrative generation.',
        };

        return textContent(summary);
      });
    },
  );
}
