import { z } from 'zod';
import { eq, and, gte, sql } from 'drizzle-orm';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import { safetyIncidents } from '../../db/schema.js';
import { requireContext, executeWithMiddleware, validateProjectAccess, textContent, errorContent } from '../../lib/tool-helpers.js';

export function register(server: McpServer) {
  server.tool(
    'get_osha_compliance_status',
    'OSHA compliance dashboard: recordable rate, DART rate, EMR, days since last incident',
    {
      project_id: z.string().uuid().optional(),
      period: z.enum(['ytd', 'trailing_12', 'all_time']).optional().default('ytd'),
    },
    async (args, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'get_osha_compliance_status', async () => {
      if (args.project_id) await validateProjectAccess(args.project_id, ctx.orgId);
      const db = getDb();

      let startDate: Date;
      const now = new Date();
      if (args.period === 'ytd') {
        startDate = new Date(now.getFullYear(), 0, 1);
      } else if (args.period === 'trailing_12') {
        startDate = new Date(now);
        startDate.setFullYear(startDate.getFullYear() - 1);
      } else {
        startDate = new Date(2000, 0, 1);
      }

      const conditions: any[] = [gte(safetyIncidents.incidentDate, startDate)];
      if (args.project_id) conditions.push(eq(safetyIncidents.projectId, args.project_id));

      const incidents = await db.select().from(safetyIncidents).where(and(...conditions));

      const totalIncidents = incidents.length;
      const recordableIncidents = incidents.filter((i) => i.oshaRecordable).length;
      const dartCases = incidents.filter((i) => ['recordable', 'lost_time'].includes(i.incidentType)).length;
      const totalDaysAway = incidents.reduce((s, i) => s + (i.daysAway || 0), 0);
      const estimatedHours = 100000; // Placeholder

      const lastIncident = incidents.sort((a, b) => new Date(b.incidentDate).getTime() - new Date(a.incidentDate).getTime())[0];
      const daysSinceLast = lastIncident
        ? Math.floor((now.getTime() - new Date(lastIncident.incidentDate).getTime()) / 86400000)
        : null;

      return textContent({
        period: args.period,
        scope: args.project_id ? 'project' : 'organization',
        total_incidents: totalIncidents,
        by_type: {
          near_miss: incidents.filter((i) => i.incidentType === 'near_miss').length,
          first_aid: incidents.filter((i) => i.incidentType === 'first_aid').length,
          recordable: incidents.filter((i) => i.incidentType === 'recordable').length,
          lost_time: incidents.filter((i) => i.incidentType === 'lost_time').length,
          fatality: incidents.filter((i) => i.incidentType === 'fatality').length,
          property_damage: incidents.filter((i) => i.incidentType === 'property_damage').length,
          environmental: incidents.filter((i) => i.incidentType === 'environmental').length,
        },
        osha_metrics: {
          recordable_incident_rate: Math.round((recordableIncidents * 200000 / estimatedHours) * 100) / 100,
          dart_rate: Math.round((dartCases * 200000 / estimatedHours) * 100) / 100,
          total_days_away: totalDaysAway,
          emr: 1.0,
          emr_note: 'EMR requires insurance carrier data. Placeholder value shown.',
        },
        days_since_last_incident: daysSinceLast,
        estimated_work_hours: estimatedHours,
      });
      });
    },
  );
}
