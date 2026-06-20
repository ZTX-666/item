import { z } from 'zod';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import { safetyIncidents } from '../../db/schema.js';
import { requireContext, executeWithMiddleware, validateProjectAccess, textContent, errorContent } from '../../lib/tool-helpers.js';

export function register(server: McpServer) {
  server.tool(
    'log_safety_incident',
    'Record safety incident. Classifies severity, flags OSHA recordability.',
    {
      project_id: z.string().uuid(),
      incident_date: z.string().describe('ISO datetime'),
      incident_type: z.enum(['near_miss', 'first_aid', 'recordable', 'lost_time', 'fatality', 'property_damage', 'environmental']),
      severity: z.enum(['low', 'medium', 'high', 'critical']),
      description: z.string().min(10),
      location_on_site: z.string().optional(),
      persons_involved: z.array(z.object({
        name: z.string(),
        company: z.string(),
        role: z.string(),
        injury_description: z.string().optional(),
      })).optional(),
      root_cause: z.string().optional(),
      corrective_actions: z.string().optional(),
      osha_recordable: z.boolean().optional(),
    },
    async (args, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'log_safety_incident', async () => {
      await validateProjectAccess(args.project_id, ctx.orgId);
      const db = getDb();

      // Auto-determine OSHA recordability if not provided
      const oshaRecordable = args.osha_recordable ??
        ['recordable', 'lost_time', 'fatality'].includes(args.incident_type);

      const [incident] = await db.insert(safetyIncidents).values({
        projectId: args.project_id,
        incidentDate: new Date(args.incident_date),
        incidentType: args.incident_type,
        severity: args.severity,
        description: args.description,
        locationOnSite: args.location_on_site,
        personsInvolved: args.persons_involved || [],
        rootCause: args.root_cause,
        correctiveActions: args.corrective_actions,
        oshaRecordable: oshaRecordable,
        daysAway: 0,
        status: 'open',
      }).returning();

      return textContent({
        incident,
        osha_flags: {
          recordable: oshaRecordable,
          requires_osha_300_log: oshaRecordable,
          requires_osha_301_report: ['recordable', 'lost_time', 'fatality'].includes(args.incident_type),
          requires_immediate_report: args.incident_type === 'fatality',
        },
      });
      });
    },
  );
}
