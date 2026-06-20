import { z } from 'zod';
import { eq } from 'drizzle-orm';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import { estimates, estimateLineItems, projects } from '../../db/schema.js';
import { requireContext, executeWithMiddleware, validateProjectAccess, textContent, errorContent } from '../../lib/tool-helpers.js';

const costDataItemSchema = z.object({
  cost_code: z.string().describe('CSI MasterFormat cost code'),
  description: z.string(),
  unit: z.string().describe('Unit of measure (e.g. SF, LF, CY, EA)'),
  unit_cost: z.number().nonnegative().describe('Unit cost from reference database'),
  region: z.string().optional().describe('Geographic region for cost adjustment'),
  year: z.number().int().optional().describe('Cost data year for inflation tracking'),
});

const inputSchema = {
  project_id: z.string().uuid().describe('Project UUID to associate the cost reference with'),
  data: z.array(costDataItemSchema).min(1).describe('Array of cost data entries to import'),
  source: z.string().optional().describe('Source of cost data (e.g. "RSMeans 2025", "Internal Database")'),
};

export function register(server: McpServer) {
  server.tool(
    'import_cost_data',
    'Bulk import cost database (RSMeans-style) as reference for estimation',
    inputSchema,
    async (params, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'import_cost_data', async () => {
        await validateProjectAccess(params.project_id, ctx.orgId);
        const db = getDb();

        // Verify the project exists
        const [project] = await db.select().from(projects).where(eq(projects.id, params.project_id));
      if (!project) {
        return errorContent(`Project not found: ${params.project_id}`);
      }

      const sourceName = params.source ?? 'External Cost Data';
      const estimateName = `Cost Reference - ${sourceName}`;

      // Create a reference estimate to hold the imported cost data
      const [refEstimate] = await db
        .insert(estimates)
        .values({
          projectId: params.project_id,
          name: estimateName,
          status: 'reference',
          totalAmount: '0.00',
          notes: `Imported cost reference data from: ${sourceName}. Contains ${params.data.length} items.`,
        })
        .returning();

      // Build line item records for bulk insert
      const lineItemValues = params.data.map((item, index) => {
        // Store region and year metadata in the notes field
        const noteParts: string[] = [];
        if (item.region) noteParts.push(`Region: ${item.region}`);
        if (item.year) noteParts.push(`Year: ${item.year}`);

        return {
          estimateId: refEstimate.id,
          costCode: item.cost_code,
          description: item.description,
          quantity: '1.000', // Reference items default to quantity 1
          unit: item.unit,
          unitCost: item.unit_cost.toFixed(4),
          category: 'material' as const, // Default category for reference data
          notes: noteParts.length > 0 ? noteParts.join(' | ') : null,
          sortOrder: index,
          laborCost: '0.00',
          materialCost: item.unit_cost.toFixed(2),
          equipmentCost: '0.00',
          subcontractorCost: '0.00',
        };
      });

      // Bulk insert all line items
      const insertedItems = await db.insert(estimateLineItems).values(lineItemValues).returning();

      // Update estimate total to reflect sum of imported unit costs
      const totalAmount = params.data.reduce((sum, item) => sum + item.unit_cost, 0);
      await db
        .update(estimates)
        .set({ totalAmount: totalAmount.toFixed(2) })
        .where(eq(estimates.id, refEstimate.id));

      // Summarize what was imported by division
      const divisionCounts: Record<string, number> = {};
      for (const item of params.data) {
        const divCode = item.cost_code.replace(/\s/g, '').substring(0, 2);
        divisionCounts[divCode] = (divisionCounts[divCode] ?? 0) + 1;
      }

      // Collect unique regions and years
      const regions = [...new Set(params.data.map((d) => d.region).filter(Boolean))];
      const years = [...new Set(params.data.map((d) => d.year).filter(Boolean))];

      return textContent({
        reference_estimate: {
          id: refEstimate.id,
          name: estimateName,
          project_id: params.project_id,
          project_name: project.name,
          status: 'reference',
        },
        import_summary: {
          source: sourceName,
          items_imported: insertedItems.length,
          total_reference_cost: totalAmount.toFixed(2),
          divisions_covered: Object.keys(divisionCounts).length,
          division_breakdown: divisionCounts,
          regions: regions.length > 0 ? regions : undefined,
          years: years.length > 0 ? years : undefined,
        },
      });
      });
    },
  );
}
