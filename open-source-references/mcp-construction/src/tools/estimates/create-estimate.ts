import { z } from 'zod';
import { eq, sql } from 'drizzle-orm';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import { estimates, estimateLineItems, projects } from '../../db/schema.js';
import { requireContext, executeWithMiddleware, validateProjectAccess, textContent, errorContent } from '../../lib/tool-helpers.js';

const unitEnum = z.enum(['SF', 'LF', 'CY', 'EA', 'LS', 'HR', 'TON', 'GAL', 'SY', 'MBF', 'SQ', 'LB']);
const categoryEnum = z.enum(['labor', 'material', 'equipment', 'subcontractor', 'overhead']);

const lineItemSchema = z.object({
  cost_code: z.string().describe('CSI MasterFormat cost code (e.g. "03 30 00")'),
  description: z.string(),
  quantity: z.number().positive(),
  unit: unitEnum,
  unit_cost: z.number().nonnegative(),
  category: categoryEnum,
  notes: z.string().optional(),
});

const inputSchema = {
  project_id: z.string().uuid().describe('Project UUID'),
  name: z.string().min(1).describe('Estimate name'),
  line_items: z.array(lineItemSchema).optional().describe('Bulk line items to include'),
  markup_percentage: z.number().min(0).max(100).optional().describe('Markup percentage (0-100)'),
  contingency_percentage: z.number().min(0).max(100).optional().describe('Contingency percentage (0-100)'),
};

export function register(server: McpServer) {
  server.tool(
    'create_estimate',
    'Create a cost estimate with CSI MasterFormat cost codes. Supports bulk line items.',
    inputSchema,
    async (params, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'create_estimate', async () => {
        await validateProjectAccess(params.project_id, ctx.orgId);
        const db = getDb();

        // Verify the project exists
        const [project] = await db.select().from(projects).where(eq(projects.id, params.project_id));
      if (!project) {
        return errorContent(`Project not found: ${params.project_id}`);
      }

      // Compute total amount from line items
      const lineItems = params.line_items ?? [];
      const totalAmount = lineItems.reduce((sum, item) => sum + item.quantity * item.unit_cost, 0);

      // Insert the estimate
      const [estimate] = await db
        .insert(estimates)
        .values({
          projectId: params.project_id,
          name: params.name,
          totalAmount: totalAmount.toFixed(2),
          markupPercentage: params.markup_percentage !== undefined ? params.markup_percentage.toFixed(2) : null,
          contingencyPercentage: params.contingency_percentage !== undefined ? params.contingency_percentage.toFixed(2) : null,
        })
        .returning();

      // Bulk insert line items if provided
      let insertedLineItems: typeof estimateLineItems.$inferSelect[] = [];
      if (lineItems.length > 0) {
        const lineItemValues = lineItems.map((item, index) => {
          const lineTotalCost = item.quantity * item.unit_cost;
          return {
            estimateId: estimate.id,
            costCode: item.cost_code,
            description: item.description,
            quantity: item.quantity.toFixed(3),
            unit: item.unit,
            unitCost: item.unit_cost.toFixed(4),
            category: item.category,
            notes: item.notes ?? null,
            sortOrder: index,
            // Distribute cost into the appropriate category column
            laborCost: item.category === 'labor' ? lineTotalCost.toFixed(2) : '0.00',
            materialCost: item.category === 'material' ? lineTotalCost.toFixed(2) : '0.00',
            equipmentCost: item.category === 'equipment' ? lineTotalCost.toFixed(2) : '0.00',
            subcontractorCost: item.category === 'subcontractor' ? lineTotalCost.toFixed(2) : '0.00',
          };
        });

        insertedLineItems = await db.insert(estimateLineItems).values(lineItemValues).returning();
      }

      // Calculate markup and contingency for the response
      const markup = params.markup_percentage ? totalAmount * (params.markup_percentage / 100) : 0;
      const contingency = params.contingency_percentage ? totalAmount * (params.contingency_percentage / 100) : 0;
      const grandTotal = totalAmount + markup + contingency;

      return textContent({
        estimate: {
          ...estimate,
          computed: {
            subtotal: totalAmount.toFixed(2),
            markup: markup.toFixed(2),
            contingency: contingency.toFixed(2),
            grand_total: grandTotal.toFixed(2),
          },
        },
        line_items: insertedLineItems,
        line_item_count: insertedLineItems.length,
      });
      });
    },
  );
}
