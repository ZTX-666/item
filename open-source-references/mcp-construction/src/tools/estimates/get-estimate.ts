import { z } from 'zod';
import { eq } from 'drizzle-orm';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import { estimates, estimateLineItems, projects } from '../../db/schema.js';
import { requireContext, executeWithMiddleware, validateProjectAccess, textContent, errorContent } from '../../lib/tool-helpers.js';

/** CSI MasterFormat division names keyed by two-digit prefix */
const CSI_DIVISIONS: Record<string, string> = {
  '01': 'General Requirements',
  '02': 'Existing Conditions',
  '03': 'Concrete',
  '04': 'Masonry',
  '05': 'Metals',
  '06': 'Wood, Plastics, and Composites',
  '07': 'Thermal and Moisture Protection',
  '08': 'Openings',
  '09': 'Finishes',
  '10': 'Specialties',
  '11': 'Equipment',
  '12': 'Furnishings',
  '13': 'Special Construction',
  '14': 'Conveying Equipment',
  '21': 'Fire Suppression',
  '22': 'Plumbing',
  '23': 'HVAC',
  '25': 'Integrated Automation',
  '26': 'Electrical',
  '27': 'Communications',
  '28': 'Electronic Safety and Security',
  '31': 'Earthwork',
  '32': 'Exterior Improvements',
  '33': 'Utilities',
  '34': 'Transportation',
  '35': 'Waterway and Marine Construction',
  '40': 'Process Interconnections',
  '41': 'Material Processing and Handling Equipment',
  '42': 'Process Heating, Cooling, and Drying Equipment',
  '43': 'Process Gas and Liquid Handling',
  '44': 'Pollution and Waste Control Equipment',
  '46': 'Water and Wastewater Equipment',
  '48': 'Electrical Power Generation',
};

const inputSchema = {
  estimate_id: z.string().uuid().describe('Estimate UUID'),
};

export function register(server: McpServer) {
  server.tool(
    'get_estimate',
    'Retrieve estimate with all line items, subtotals by division, and markup breakdown',
    inputSchema,
    async (params, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'get_estimate', async () => {
        const db = getDb();

        // Fetch the estimate
        const [estimate] = await db.select().from(estimates).where(eq(estimates.id, params.estimate_id));
        if (!estimate) {
          return errorContent(`Estimate not found: ${params.estimate_id}`);
        }

        await validateProjectAccess(estimate.projectId, ctx.orgId);

        // Fetch the parent project name for context
      const [project] = await db.select().from(projects).where(eq(projects.id, estimate.projectId));

      // Fetch all line items
      const lineItems = await db
        .select()
        .from(estimateLineItems)
        .where(eq(estimateLineItems.estimateId, params.estimate_id));

      // Group line items by CSI division (first 2 characters of cost_code)
      const divisionMap: Record<string, {
        division_code: string;
        division_name: string;
        items: typeof lineItems;
        subtotal: number;
        labor: number;
        material: number;
        equipment: number;
        subcontractor: number;
      }> = {};

      for (const item of lineItems) {
        const divCode = item.costCode.replace(/\s/g, '').substring(0, 2);
        if (!divisionMap[divCode]) {
          divisionMap[divCode] = {
            division_code: divCode,
            division_name: CSI_DIVISIONS[divCode] ?? `Division ${divCode}`,
            items: [],
            subtotal: 0,
            labor: 0,
            material: 0,
            equipment: 0,
            subcontractor: 0,
          };
        }

        const div = divisionMap[divCode];
        div.items.push(item);
        div.subtotal += parseFloat(item.totalCost ?? '0');
        div.labor += parseFloat(item.laborCost ?? '0');
        div.material += parseFloat(item.materialCost ?? '0');
        div.equipment += parseFloat(item.equipmentCost ?? '0');
        div.subcontractor += parseFloat(item.subcontractorCost ?? '0');
      }

      // Sort divisions by code
      const divisions = Object.values(divisionMap)
        .sort((a, b) => a.division_code.localeCompare(b.division_code))
        .map((div) => ({
          ...div,
          subtotal: div.subtotal.toFixed(2),
          labor: div.labor.toFixed(2),
          material: div.material.toFixed(2),
          equipment: div.equipment.toFixed(2),
          subcontractor: div.subcontractor.toFixed(2),
          item_count: div.items.length,
          items: div.items,
        }));

      // Calculate totals
      const subtotal = parseFloat(estimate.totalAmount ?? '0');
      const markupPct = parseFloat(estimate.markupPercentage ?? '0');
      const contingencyPct = parseFloat(estimate.contingencyPercentage ?? '0');
      const markupAmount = subtotal * (markupPct / 100);
      const contingencyAmount = subtotal * (contingencyPct / 100);
      const grandTotal = subtotal + markupAmount + contingencyAmount;

      // Category totals across all line items
      const categoryTotals = {
        labor: lineItems.reduce((s, i) => s + parseFloat(i.laborCost ?? '0'), 0).toFixed(2),
        material: lineItems.reduce((s, i) => s + parseFloat(i.materialCost ?? '0'), 0).toFixed(2),
        equipment: lineItems.reduce((s, i) => s + parseFloat(i.equipmentCost ?? '0'), 0).toFixed(2),
        subcontractor: lineItems.reduce((s, i) => s + parseFloat(i.subcontractorCost ?? '0'), 0).toFixed(2),
      };

      return textContent({
        estimate: {
          id: estimate.id,
          project_id: estimate.projectId,
          project_name: project?.name ?? null,
          name: estimate.name,
          version: estimate.version,
          status: estimate.status,
          created_at: estimate.createdAt,
          updated_at: estimate.updatedAt,
        },
        cost_breakdown: {
          subtotal: subtotal.toFixed(2),
          markup_percentage: markupPct,
          markup_amount: markupAmount.toFixed(2),
          contingency_percentage: contingencyPct,
          contingency_amount: contingencyAmount.toFixed(2),
          grand_total: grandTotal.toFixed(2),
        },
        category_totals: categoryTotals,
        divisions,
        total_line_items: lineItems.length,
      });
      });
    },
  );
}
