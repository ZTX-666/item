import { z } from 'zod';
import { eq, and, inArray } from 'drizzle-orm';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import { subcontractorBids, subcontractors } from '../../db/schema.js';
import { requireContext, executeWithMiddleware, validateSubcontractorAccess, validateProjectAccess, textContent, errorContent } from '../../lib/tool-helpers.js';

export function register(server: McpServer) {
  server.tool(
    'compare_bids',
    'Bid comparison matrix for a scope of work. Normalizes for inclusions/exclusions.',
    {
      project_id: z.string().uuid(),
      scope_description: z.string().optional(),
      subcontractor_ids: z.array(z.string().uuid()).optional(),
      trade: z.string().optional(),
    },
    async (args, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'compare_bids', async () => {
        await validateProjectAccess(args.project_id, ctx.orgId);

        const db = getDb();
        const conditions: any[] = [eq(subcontractorBids.projectId, args.project_id)];

        if (args.subcontractor_ids?.length) {
          conditions.push(inArray(subcontractorBids.subcontractorId, args.subcontractor_ids));
        }

        const bids = await db.select().from(subcontractorBids).where(and(...conditions));

        // Get subcontractor details
        const subIds = [...new Set(bids.map((b) => b.subcontractorId))];
        let subs: any[] = [];
        if (subIds.length > 0) {
          subs = await db.select().from(subcontractors).where(inArray(subcontractors.id, subIds));
          if (args.trade) subs = subs.filter((s) => s.trade === args.trade);
        }

        const subMap = new Map(subs.map((s) => [s.id, s]));
        const relevantBids = bids.filter((b) => subMap.has(b.subcontractorId));

        const comparison = relevantBids.map((b) => {
          const sub = subMap.get(b.subcontractorId)!;
          return {
            subcontractor: { id: sub.id, name: sub.companyName, trade: sub.trade, rating: sub.averageRating },
            bid_amount: Number(b.bidAmount),
            scope_description: b.scopeDescription,
            inclusions: b.inclusions,
            exclusions: b.exclusions,
            alternates: b.alternates,
            status: b.status,
            validity_days: b.validityDays,
          };
        }).sort((a, b) => a.bid_amount - b.bid_amount);

        const amounts = comparison.map((c) => c.bid_amount);
        const lowest = comparison[0] || null;

        return textContent({
          bids: comparison,
          lowest_bidder: lowest ? { name: lowest.subcontractor.name, amount: lowest.bid_amount } : null,
          bid_spread: amounts.length >= 2 ? amounts[amounts.length - 1] - amounts[0] : 0,
          average_bid: amounts.length > 0 ? Math.round(amounts.reduce((s, a) => s + a, 0) / amounts.length * 100) / 100 : 0,
          total_bids: comparison.length,
        });
      });
    },
  );
}
