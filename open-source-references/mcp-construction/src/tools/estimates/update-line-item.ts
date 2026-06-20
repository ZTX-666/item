import { z } from 'zod';
import { eq, sql } from 'drizzle-orm';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import { estimates, estimateLineItems } from '../../db/schema.js';
import { requireContext, executeWithMiddleware, validateProjectAccess, textContent, errorContent } from '../../lib/tool-helpers.js';

const inputSchema = {
  line_item_id: z.string().uuid().describe('Line item UUID'),
  quantity: z.number().positive().optional().describe('Updated quantity'),
  unit_cost: z.number().nonnegative().optional().describe('Updated unit cost'),
  description: z.string().min(1).optional().describe('Updated description'),
  cost_code: z.string().optional().describe('Updated CSI MasterFormat cost code'),
  category: z.enum(['labor', 'material', 'equipment', 'subcontractor', 'overhead']).optional().describe('Updated cost category'),
  notes: z.string().optional().describe('Updated notes'),
};

export function register(server: McpServer) {
  server.tool(
    'update_line_item',
    'Modify a specific estimate line item',
    inputSchema,
    async (params, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'update_line_item', async () => {
        const db = getDb();

        // Fetch the existing line item
        const [existing] = await db
          .select()
          .from(estimateLineItems)
          .where(eq(estimateLineItems.id, params.line_item_id));

        if (!existing) {
          return errorContent(`Line item not found: ${params.line_item_id}`);
        }

        // Fetch parent estimate to validate project access
        const [parentEstimate] = await db.select().from(estimates).where(eq(estimates.id, existing.estimateId));
        await validateProjectAccess(parentEstimate.projectId, ctx.orgId);

        // Build the update payload
      const quantity = params.quantity ?? parseFloat(existing.quantity ?? '0');
      const unitCost = params.unit_cost ?? parseFloat(existing.unitCost ?? '0');
      const totalCost = quantity * unitCost;
      const category = params.category ?? existing.category;

      const updateValues: Record<string, unknown> = {
        quantity: quantity.toFixed(3),
        unitCost: unitCost.toFixed(4),
        totalCost: totalCost.toFixed(2),
        // Reset category cost columns then set the appropriate one
        laborCost: '0.00',
        materialCost: '0.00',
        equipmentCost: '0.00',
        subcontractorCost: '0.00',
      };

      // Set the category-specific cost column
      switch (category) {
        case 'labor':
          updateValues.laborCost = totalCost.toFixed(2);
          break;
        case 'material':
          updateValues.materialCost = totalCost.toFixed(2);
          break;
        case 'equipment':
          updateValues.equipmentCost = totalCost.toFixed(2);
          break;
        case 'subcontractor':
          updateValues.subcontractorCost = totalCost.toFixed(2);
          break;
        // overhead has no dedicated column, stays in totalCost
      }

      if (params.description !== undefined) updateValues.description = params.description;
      if (params.cost_code !== undefined) updateValues.costCode = params.cost_code;
      if (params.category !== undefined) updateValues.category = params.category;
      if (params.notes !== undefined) updateValues.notes = params.notes;

      // Update the line item
      const [updated] = await db
        .update(estimateLineItems)
        .set(updateValues)
        .where(eq(estimateLineItems.id, params.line_item_id))
        .returning();

      // Recalculate the parent estimate total
      const allItems = await db
        .select()
        .from(estimateLineItems)
        .where(eq(estimateLineItems.estimateId, existing.estimateId));

      const newTotal = allItems.reduce((sum, item) => sum + parseFloat(item.totalCost ?? '0'), 0);

      const [updatedEstimate] = await db
        .update(estimates)
        .set({
          totalAmount: newTotal.toFixed(2),
          updatedAt: sql`now()`,
        })
        .where(eq(estimates.id, existing.estimateId))
        .returning();

      return textContent({
        line_item: updated,
        estimate_total_updated: {
          estimate_id: updatedEstimate.id,
          new_total_amount: updatedEstimate.totalAmount,
        },
      });
      });
    },
  );
}
