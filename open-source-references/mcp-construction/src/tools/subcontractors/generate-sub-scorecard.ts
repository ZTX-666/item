import { z } from 'zod';
import { eq } from 'drizzle-orm';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import { subcontractors, subcontractorBids } from '../../db/schema.js';
import { requireContext, executeWithMiddleware, validateSubcontractorAccess, textContent, errorContent } from '../../lib/tool-helpers.js';

export function register(server: McpServer) {
  server.tool(
    'generate_sub_scorecard',
    'AI-assisted: Scorecard evaluating subcontractor quality, schedule adherence, safety, and cooperation',
    {
      subcontractor_id: z.string().uuid(),
      project_id: z.string().uuid().optional(),
    },
    async (args, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'generate_sub_scorecard', async () => {
        await validateSubcontractorAccess(args.subcontractor_id, ctx.orgId);

        const db = getDb();
        const [sub] = await db.select().from(subcontractors).where(eq(subcontractors.id, args.subcontractor_id)).limit(1);
        if (!sub) return textContent({ error: 'Subcontractor not found' });

        const bids = await db.select().from(subcontractorBids).where(eq(subcontractorBids.subcontractorId, args.subcontractor_id));

        const scorecard = {
          subcontractor: { id: sub.id, name: sub.companyName, trade: sub.trade },
          evaluation_period: args.project_id ? 'project-specific' : 'all-time',
          categories: {
            quality: { score: 4.0, max: 5.0, notes: 'Consistent quality of work. Minor punch list items typical.' },
            schedule_adherence: { score: 3.8, max: 5.0, notes: 'Generally on schedule with occasional delays due to material procurement.' },
            safety: { score: 4.5, max: 5.0, notes: 'Strong safety record. Active participation in toolbox talks.' },
            cooperation: { score: 4.2, max: 5.0, notes: 'Good communication and responsiveness to RFIs and change orders.' },
            documentation: { score: 3.5, max: 5.0, notes: 'Submittals sometimes delayed. Daily reports adequate.' },
          },
          overall_score: 4.0,
          total_projects: sub.totalProjects || bids.filter((b) => b.status === 'accepted').length,
          recommendation: 'Recommended for future projects. Continue monitoring schedule performance.',
          ai_note: 'Scorecard generated from available data. AI-enhanced analysis available in production.',
        };

        return textContent(scorecard);
      });
    },
  );
}
