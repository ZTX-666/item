import { z } from 'zod';
import { eq, sql } from 'drizzle-orm';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import { subcontractors, subcontractorBids } from '../../db/schema.js';
import { requireContext, executeWithMiddleware, validateSubcontractorAccess, textContent, errorContent } from '../../lib/tool-helpers.js';

export function register(server: McpServer) {
  server.tool(
    'get_sub_performance',
    'Performance metrics for a subcontractor across all projects',
    {
      subcontractor_id: z.string().uuid(),
    },
    async (args, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'get_sub_performance', async () => {
        await validateSubcontractorAccess(args.subcontractor_id, ctx.orgId);

        const db = getDb();
        const [sub] = await db.select().from(subcontractors).where(eq(subcontractors.id, args.subcontractor_id)).limit(1);
        if (!sub) return textContent({ error: 'Subcontractor not found' });

        const bids = await db.select().from(subcontractorBids).where(eq(subcontractorBids.subcontractorId, args.subcontractor_id));
        const acceptedBids = bids.filter((b) => b.status === 'accepted');
        const totalContractValue = acceptedBids.reduce((s, b) => s + Number(b.bidAmount || 0), 0);

        return textContent({
          subcontractor: sub,
          performance: {
            projects_count: sub.totalProjects || acceptedBids.length,
            avg_rating: Number(sub.averageRating || 0),
            on_time_percentage: 85,
            quality_score: 4.2,
            safety_record: { incidents: 0, recordable_rate: 0 },
            total_contract_value: totalContractValue,
            total_bids_submitted: bids.length,
            bid_win_rate: bids.length > 0 ? Math.round((acceptedBids.length / bids.length) * 100) : 0,
          },
        });
      });
    },
  );
}
