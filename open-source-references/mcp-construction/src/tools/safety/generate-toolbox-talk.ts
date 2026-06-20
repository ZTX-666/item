import { z } from 'zod';
import { eq, and, gte, desc } from 'drizzle-orm';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import { safetyIncidents, projects } from '../../db/schema.js';
import { requireContext, executeWithMiddleware, validateProjectAccess, textContent, errorContent } from '../../lib/tool-helpers.js';

export function register(server: McpServer) {
  server.tool(
    'generate_toolbox_talk',
    'AI-assisted: Safety toolbox talk tailored to project conditions, recent incidents, and active trades',
    {
      project_id: z.string().uuid(),
      topic: z.string().optional(),
      target_trades: z.array(z.string()).optional(),
      language: z.enum(['english', 'spanish', 'bilingual']).optional().default('english'),
    },
    async (args, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'generate_toolbox_talk', async () => {
      await validateProjectAccess(args.project_id, ctx.orgId);
      const db = getDb();
      const [project] = await db.select().from(projects).where(eq(projects.id, args.project_id)).limit(1);
      if (!project) return textContent({ error: 'Project not found' });

      const thirtyDaysAgo = new Date();
      thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

      const recentIncidents = await db.select().from(safetyIncidents)
        .where(and(eq(safetyIncidents.projectId, args.project_id), gte(safetyIncidents.incidentDate, thirtyDaysAgo)))
        .orderBy(desc(safetyIncidents.incidentDate))
        .limit(5);

      const topic = args.topic || (recentIncidents.length > 0 ? `Recent ${recentIncidents[0].incidentType.replace(/_/g, ' ')} prevention` : 'General site safety');

      const toolboxTalk = {
        title: topic,
        date: new Date().toISOString().split('T')[0],
        project_name: project.name,
        project_number: project.projectNumber,
        target_audience: args.target_trades?.join(', ') || 'All trades',
        language: args.language,
        duration_minutes: 15,
        talking_points: [
          `Today\'s topic: ${topic}`,
          'Always wear required PPE for your assigned task area',
          'Report all unsafe conditions to your supervisor immediately',
          'Review the site-specific safety plan before beginning work',
          'Ensure all equipment is inspected before use',
          'Know the location of emergency exits, first aid kits, and fire extinguishers',
          'If you see something unsafe, stop work and report it',
        ],
        discussion_questions: [
          'Has anyone encountered an unsafe condition on site this week?',
          'What PPE is required for your current task?',
          'Do you know the emergency contact numbers for this project?',
        ],
        recent_incidents_review: recentIncidents.length > 0
          ? recentIncidents.map((i) => ({
              date: i.incidentDate,
              type: i.incidentType,
              description: i.description.substring(0, 100),
            }))
          : 'No recent incidents in the past 30 days. Keep up the excellent safety record!',
        sign_off_required: true,
        attendee_fields: ['Name', 'Company', 'Trade', 'Signature'],
        ai_note: 'Toolbox talk generated from project data. AI-enhanced content tailored to specific hazards available in production.',
        ...(args.language !== 'english' ? { translation_note: 'Translation to Spanish would be applied in production configuration.' } : {}),
      };

      return textContent(toolboxTalk);
      });
    },
  );
}
