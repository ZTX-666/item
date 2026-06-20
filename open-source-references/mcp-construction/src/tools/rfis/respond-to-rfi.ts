import { z } from 'zod';
import { eq } from 'drizzle-orm';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import { rfis } from '../../db/schema.js';
import { requireContext, executeWithMiddleware, validateProjectAccess, textContent, errorContent } from '../../lib/tool-helpers.js';

export function register(server: McpServer) {
  server.tool(
    'respond_to_rfi',
    'Submit response to an RFI. Updates status to answered.',
    {
      rfi_id: z.string().uuid(),
      answer: z.string(),
      cost_impact_amount: z.number().optional(),
      schedule_impact_days: z.number().int().optional(),
    },
    async (params, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'respond_to_rfi', async () => {
        try {
          const db = getDb();

          // Verify the RFI exists
          const [existing] = await db
            .select()
            .from(rfis)
            .where(eq(rfis.id, params.rfi_id));

          if (!existing) {
            return errorContent(`RFI not found: ${params.rfi_id}`);
          }

          await validateProjectAccess(existing.projectId, ctx.orgId);

          // Build the update payload
          const updateData: Record<string, unknown> = {
            answer: params.answer,
            status: 'answered',
            respondedAt: new Date(),
            updatedAt: new Date(),
          };

          if (params.cost_impact_amount !== undefined) {
            updateData.costImpact = true;
            updateData.costImpactAmount = params.cost_impact_amount.toString();
          }

          if (params.schedule_impact_days !== undefined) {
            updateData.scheduleImpact = true;
            updateData.scheduleImpactDays = params.schedule_impact_days;
          }

          const [updated] = await db
            .update(rfis)
            .set(updateData)
            .where(eq(rfis.id, params.rfi_id))
            .returning();

          return textContent(updated);
        } catch (err) {
          return errorContent(err instanceof Error ? err.message : 'Failed to respond to RFI');
        }
      });
    },
  );
}
