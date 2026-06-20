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
};

const inputSchema = {
  estimate_id: z.string().uuid().describe('Estimate UUID'),
  format: z.enum(['summary', 'detailed', 'executive']).describe('Report format level'),
};

export function register(server: McpServer) {
  server.tool(
    'generate_estimate_report',
    'AI-assisted formatted estimate summary with division subtotals, key cost drivers, and comparison to industry benchmarks',
    inputSchema,
    async (params, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'generate_estimate_report', async () => {
        const db = getDb();

        // Fetch estimate
        const [estimate] = await db.select().from(estimates).where(eq(estimates.id, params.estimate_id));
        if (!estimate) {
          return errorContent(`Estimate not found: ${params.estimate_id}`);
        }

        await validateProjectAccess(estimate.projectId, ctx.orgId);

        // Fetch project
      const [project] = await db.select().from(projects).where(eq(projects.id, estimate.projectId));

      // Fetch line items
      const lineItems = await db
        .select()
        .from(estimateLineItems)
        .where(eq(estimateLineItems.estimateId, params.estimate_id));

      // Calculate totals
      const subtotal = parseFloat(estimate.totalAmount ?? '0');
      const markupPct = parseFloat(estimate.markupPercentage ?? '0');
      const contingencyPct = parseFloat(estimate.contingencyPercentage ?? '0');
      const markupAmount = subtotal * (markupPct / 100);
      const contingencyAmount = subtotal * (contingencyPct / 100);
      const grandTotal = subtotal + markupAmount + contingencyAmount;

      // Build division subtotals
      const divisionTotals: Record<string, { name: string; total: number; item_count: number }> = {};
      const categoryTotals = { labor: 0, material: 0, equipment: 0, subcontractor: 0, overhead: 0 };

      for (const item of lineItems) {
        const divCode = item.costCode.replace(/\s/g, '').substring(0, 2);
        if (!divisionTotals[divCode]) {
          divisionTotals[divCode] = {
            name: CSI_DIVISIONS[divCode] ?? `Division ${divCode}`,
            total: 0,
            item_count: 0,
          };
        }
        divisionTotals[divCode].total += parseFloat(item.totalCost ?? '0');
        divisionTotals[divCode].item_count += 1;

        // Accumulate category totals
        categoryTotals.labor += parseFloat(item.laborCost ?? '0');
        categoryTotals.material += parseFloat(item.materialCost ?? '0');
        categoryTotals.equipment += parseFloat(item.equipmentCost ?? '0');
        categoryTotals.subcontractor += parseFloat(item.subcontractorCost ?? '0');
        if (item.category === 'overhead') {
          categoryTotals.overhead += parseFloat(item.totalCost ?? '0');
        }
      }

      // Identify top cost drivers (top 5 line items by total cost)
      const sortedItems = [...lineItems].sort(
        (a, b) => parseFloat(b.totalCost ?? '0') - parseFloat(a.totalCost ?? '0'),
      );
      const topCostDrivers = sortedItems.slice(0, 5).map((item) => ({
        cost_code: item.costCode,
        description: item.description,
        total_cost: item.totalCost,
        percentage_of_total: subtotal > 0 ? ((parseFloat(item.totalCost ?? '0') / subtotal) * 100).toFixed(1) + '%' : '0%',
      }));

      // Identify top divisions by cost
      const sortedDivisions = Object.entries(divisionTotals)
        .sort(([, a], [, b]) => b.total - a.total)
        .map(([code, div]) => ({
          division: `${code} - ${div.name}`,
          subtotal: div.total.toFixed(2),
          item_count: div.item_count,
          percentage_of_total: subtotal > 0 ? ((div.total / subtotal) * 100).toFixed(1) + '%' : '0%',
        }));

      // Build the formatted text summary based on the requested format
      const reportDate = new Date().toISOString().split('T')[0];
      const projectName = project?.name ?? 'Unknown Project';

      let textSummary: string;

      if (params.format === 'executive') {
        textSummary = [
          `EXECUTIVE ESTIMATE SUMMARY`,
          `==========================`,
          `Project: ${projectName}`,
          `Estimate: ${estimate.name} (v${estimate.version})`,
          `Date: ${reportDate}`,
          `Status: ${estimate.status}`,
          ``,
          `FINANCIAL OVERVIEW`,
          `  Base Cost:      $${subtotal.toLocaleString('en-US', { minimumFractionDigits: 2 })}`,
          `  Markup (${markupPct}%):  $${markupAmount.toLocaleString('en-US', { minimumFractionDigits: 2 })}`,
          `  Contingency (${contingencyPct}%): $${contingencyAmount.toLocaleString('en-US', { minimumFractionDigits: 2 })}`,
          `  ─────────────────────────`,
          `  GRAND TOTAL:    $${grandTotal.toLocaleString('en-US', { minimumFractionDigits: 2 })}`,
          ``,
          `TOP COST DRIVERS`,
          ...topCostDrivers.map((d, i) => `  ${i + 1}. ${d.description} (${d.cost_code}): $${parseFloat(d.total_cost ?? '0').toLocaleString('en-US', { minimumFractionDigits: 2 })} [${d.percentage_of_total}]`),
          ``,
          `NOTE: AI-enhanced analysis with industry benchmark comparison would be applied in production.`,
        ].join('\n');
      } else if (params.format === 'detailed') {
        textSummary = [
          `DETAILED ESTIMATE REPORT`,
          `========================`,
          `Project: ${projectName}`,
          `Estimate: ${estimate.name} (v${estimate.version})`,
          `Date: ${reportDate}`,
          `Status: ${estimate.status}`,
          `Line Items: ${lineItems.length}`,
          ``,
          `DIVISION BREAKDOWN`,
          ...sortedDivisions.map((d) => `  ${d.division}: $${parseFloat(d.subtotal).toLocaleString('en-US', { minimumFractionDigits: 2 })} (${d.percentage_of_total}, ${d.item_count} items)`),
          ``,
          `COST CATEGORY BREAKDOWN`,
          `  Labor:         $${categoryTotals.labor.toLocaleString('en-US', { minimumFractionDigits: 2 })}`,
          `  Material:      $${categoryTotals.material.toLocaleString('en-US', { minimumFractionDigits: 2 })}`,
          `  Equipment:     $${categoryTotals.equipment.toLocaleString('en-US', { minimumFractionDigits: 2 })}`,
          `  Subcontractor: $${categoryTotals.subcontractor.toLocaleString('en-US', { minimumFractionDigits: 2 })}`,
          `  Overhead:      $${categoryTotals.overhead.toLocaleString('en-US', { minimumFractionDigits: 2 })}`,
          ``,
          `FINANCIAL SUMMARY`,
          `  Base Cost:      $${subtotal.toLocaleString('en-US', { minimumFractionDigits: 2 })}`,
          `  Markup (${markupPct}%):  $${markupAmount.toLocaleString('en-US', { minimumFractionDigits: 2 })}`,
          `  Contingency (${contingencyPct}%): $${contingencyAmount.toLocaleString('en-US', { minimumFractionDigits: 2 })}`,
          `  ─────────────────────────`,
          `  GRAND TOTAL:    $${grandTotal.toLocaleString('en-US', { minimumFractionDigits: 2 })}`,
          ``,
          `TOP 5 COST DRIVERS`,
          ...topCostDrivers.map((d, i) => `  ${i + 1}. ${d.description} (${d.cost_code}): $${parseFloat(d.total_cost ?? '0').toLocaleString('en-US', { minimumFractionDigits: 2 })} [${d.percentage_of_total}]`),
          ``,
          `NOTE: AI-enhanced analysis with industry benchmark comparison would be applied in production.`,
        ].join('\n');
      } else {
        // summary format
        textSummary = [
          `ESTIMATE SUMMARY`,
          `================`,
          `Project: ${projectName}`,
          `Estimate: ${estimate.name} (v${estimate.version})`,
          `Date: ${reportDate} | Status: ${estimate.status} | Items: ${lineItems.length}`,
          ``,
          `  Base Cost:    $${subtotal.toLocaleString('en-US', { minimumFractionDigits: 2 })}`,
          `  Markup:       $${markupAmount.toLocaleString('en-US', { minimumFractionDigits: 2 })} (${markupPct}%)`,
          `  Contingency:  $${contingencyAmount.toLocaleString('en-US', { minimumFractionDigits: 2 })} (${contingencyPct}%)`,
          `  GRAND TOTAL:  $${grandTotal.toLocaleString('en-US', { minimumFractionDigits: 2 })}`,
          ``,
          `Top Divisions:`,
          ...sortedDivisions.slice(0, 3).map((d) => `  - ${d.division}: $${parseFloat(d.subtotal).toLocaleString('en-US', { minimumFractionDigits: 2 })} (${d.percentage_of_total})`),
          ``,
          `NOTE: AI-enhanced analysis with industry benchmark comparison would be applied in production.`,
        ].join('\n');
      }

      return textContent({
        report: {
          format: params.format,
          generated_at: new Date().toISOString(),
          ai_enhanced: false,
          ai_note: 'AI-enhanced analysis with industry benchmark comparison would be applied in production.',
        },
        estimate: {
          id: estimate.id,
          name: estimate.name,
          version: estimate.version,
          status: estimate.status,
          project: projectName,
        },
        financial_summary: {
          subtotal: subtotal.toFixed(2),
          markup_percentage: markupPct,
          markup_amount: markupAmount.toFixed(2),
          contingency_percentage: contingencyPct,
          contingency_amount: contingencyAmount.toFixed(2),
          grand_total: grandTotal.toFixed(2),
        },
        category_totals: {
          labor: categoryTotals.labor.toFixed(2),
          material: categoryTotals.material.toFixed(2),
          equipment: categoryTotals.equipment.toFixed(2),
          subcontractor: categoryTotals.subcontractor.toFixed(2),
          overhead: categoryTotals.overhead.toFixed(2),
        },
        division_subtotals: sortedDivisions,
        top_cost_drivers: topCostDrivers,
        formatted_text: textSummary,
      });
      });
    },
  );
}
