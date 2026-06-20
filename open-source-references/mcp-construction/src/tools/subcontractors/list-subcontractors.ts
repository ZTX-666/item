import { z } from 'zod';
import { eq, and, gte, ilike, or, sql } from 'drizzle-orm';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import { subcontractors } from '../../db/schema.js';
import { requireContext, executeWithMiddleware, validateSubcontractorAccess, textContent, errorContent } from '../../lib/tool-helpers.js';

export function register(server: McpServer) {
  server.tool(
    'list_subcontractors',
    'List subcontractors with filters by trade, prequalification status, rating, or search',
    {
      trade: z.string().optional(),
      prequalification_status: z.string().optional(),
      min_rating: z.number().min(0).max(5).optional(),
      search: z.string().optional(),
    },
    async (args, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'list_subcontractors', async () => {
        const db = getDb();
        const conditions: any[] = [eq(subcontractors.orgId, ctx.orgId)];

        if (args.trade) conditions.push(eq(subcontractors.trade, args.trade));
        if (args.prequalification_status) conditions.push(eq(subcontractors.prequalificationStatus, args.prequalification_status));
        if (args.min_rating !== undefined) conditions.push(gte(subcontractors.averageRating, String(args.min_rating)));
        if (args.search) {
          conditions.push(
            or(
              ilike(subcontractors.companyName, `%${args.search}%`),
              ilike(subcontractors.contactName, `%${args.search}%`),
            ),
          );
        }

        const rows = await db.select().from(subcontractors).where(and(...conditions));

        return textContent({ subcontractors: rows, total: rows.length });
      });
    },
  );
}
