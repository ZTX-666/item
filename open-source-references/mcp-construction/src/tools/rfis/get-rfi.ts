import { z } from 'zod';
import { eq } from 'drizzle-orm';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import { rfis, changeOrders } from '../../db/schema.js';
import { requireContext, executeWithMiddleware, validateProjectAccess, textContent, errorContent } from '../../lib/tool-helpers.js';

export function register(server: McpServer) {
  server.tool(
    'get_rfi',
    'Full RFI details including linked change orders',
    {
      rfi_id: z.string().uuid(),
    },
    async (params, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'get_rfi', async () => {
        try {
          const db = getDb();

          // Get the RFI by id
          const [rfi] = await db
            .select()
            .from(rfis)
            .where(eq(rfis.id, params.rfi_id));

          if (!rfi) {
            return errorContent(`RFI not found: ${params.rfi_id}`);
          }

          await validateProjectAccess(rfi.projectId, ctx.orgId);

          // Get linked change orders where related_rfi_id matches
          const linkedChangeOrders = await db
            .select()
            .from(changeOrders)
            .where(eq(changeOrders.relatedRfiId, params.rfi_id));

          return textContent({
            ...rfi,
            linked_change_orders: linkedChangeOrders,
          });
        } catch (err) {
          return errorContent(err instanceof Error ? err.message : 'Failed to get RFI');
        }
      });
    },
  );
}
