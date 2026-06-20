import { z } from 'zod';
import { eq, and, desc, sql, sum, gte, lte, between } from 'drizzle-orm';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import { dailyLogs } from '../../db/schema.js';
import { requireContext, executeWithMiddleware, validateProjectAccess, textContent, errorContent } from '../../lib/tool-helpers.js';

export function register(server: McpServer) {
  server.tool(
    'create_daily_log',
    'Record daily construction log entry with weather, workforce, equipment, and work details',
    {
      project_id: z.string().uuid(),
      log_date: z.string().describe('Date in YYYY-MM-DD format'),
      weather_conditions: z
        .enum([
          'clear',
          'partly_cloudy',
          'overcast',
          'rain',
          'snow',
          'fog',
          'extreme_heat',
          'extreme_cold',
        ])
        .optional(),
      temperature_high: z.number().optional(),
      temperature_low: z.number().optional(),
      workers_on_site: z
        .array(
          z.object({
            company: z.string(),
            trade: z.string(),
            headcount: z.number(),
          }),
        )
        .optional(),
      equipment_on_site: z
        .array(
          z.object({
            type: z.string(),
            hours: z.number(),
            idle: z.boolean().optional(),
          }),
        )
        .optional(),
      work_performed: z.string(),
      materials_received: z.string().optional(),
      delays: z.string().optional(),
      delay_hours: z.number().optional(),
      notes: z.string().optional(),
    },
    async (params, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'create_daily_log', async () => {
        await validateProjectAccess(params.project_id, ctx.orgId);

        const db = getDb();

        // Calculate total headcount from workers_on_site
        const totalHeadcount = params.workers_on_site
          ? params.workers_on_site.reduce((sum, w) => sum + w.headcount, 0)
          : 0;

        const [created] = await db
          .insert(dailyLogs)
          .values({
            projectId: params.project_id,
            logDate: params.log_date,
            weatherConditions: params.weather_conditions ?? null,
            temperatureHigh: params.temperature_high ?? null,
            temperatureLow: params.temperature_low ?? null,
            workersOnSite: params.workers_on_site ?? [],
            totalHeadcount: totalHeadcount,
            equipmentOnSite: params.equipment_on_site ?? [],
            workPerformed: params.work_performed,
            materialsReceived: params.materials_received ?? null,
            delays: params.delays ?? null,
            delayHours: params.delay_hours?.toString() ?? null,
            notes: params.notes ?? null,
          })
          .returning();

        return textContent({
          message: 'Daily log created successfully',
          daily_log: created,
        });
      });
    },
  );
}
