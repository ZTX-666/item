import { z } from 'zod';
import { inArray } from 'drizzle-orm';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import { estimates, estimateLineItems } from '../../db/schema.js';
import { requireContext, executeWithMiddleware, validateProjectAccess, textContent, errorContent } from '../../lib/tool-helpers.js';

const inputSchema = {
  estimate_ids: z
    .array(z.string().uuid())
    .min(2)
    .max(5)
    .describe('Array of 2-5 estimate UUIDs to compare side-by-side'),
};

export function register(server: McpServer) {
  server.tool(
    'compare_estimates',
    'Side-by-side comparison of estimate versions showing delta per cost code',
    inputSchema,
    async (params, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'compare_estimates', async () => {
        const db = getDb();

        // Fetch all requested estimates
        const fetchedEstimates = await db
          .select()
          .from(estimates)
          .where(inArray(estimates.id, params.estimate_ids));

        if (fetchedEstimates.length < 2) {
          return errorContent(
            `Need at least 2 valid estimates to compare. Found ${fetchedEstimates.length} of ${params.estimate_ids.length} requested.`,
          );
        }

        // Validate all fetched estimates belong to org's projects
        for (const est of fetchedEstimates) {
          await validateProjectAccess(est.projectId, ctx.orgId);
        }

        // Verify all requested IDs were found
      const foundIds = new Set(fetchedEstimates.map((e) => e.id));
      const missingIds = params.estimate_ids.filter((id) => !foundIds.has(id));

      // Fetch all line items for these estimates
      const allLineItems = await db
        .select()
        .from(estimateLineItems)
        .where(inArray(estimateLineItems.estimateId, params.estimate_ids));

      // Group line items by cost_code, then by estimate_id
      const costCodeMap: Record<
        string,
        {
          cost_code: string;
          description: string;
          estimates: Record<string, { quantity: number; unit_cost: number; total: number; unit: string | null; category: string | null }>;
        }
      > = {};

      for (const item of allLineItems) {
        if (!costCodeMap[item.costCode]) {
          costCodeMap[item.costCode] = {
            cost_code: item.costCode,
            description: item.description,
            estimates: {},
          };
        }

        const entry = costCodeMap[item.costCode];
        const existingForEstimate = entry.estimates[item.estimateId];

        if (existingForEstimate) {
          // Aggregate multiple items with the same cost code in the same estimate
          existingForEstimate.quantity += parseFloat(item.quantity ?? '0');
          existingForEstimate.total += parseFloat(item.totalCost ?? '0');
        } else {
          entry.estimates[item.estimateId] = {
            quantity: parseFloat(item.quantity ?? '0'),
            unit_cost: parseFloat(item.unitCost ?? '0'),
            total: parseFloat(item.totalCost ?? '0'),
            unit: item.unit,
            category: item.category,
          };
        }
      }

      // Build the comparison matrix with deltas
      // Use the first estimate as the baseline for delta calculations
      const baselineId = params.estimate_ids[0];
      const comparisonRows = Object.values(costCodeMap)
        .sort((a, b) => a.cost_code.localeCompare(b.cost_code))
        .map((entry) => {
          const baselineTotal = entry.estimates[baselineId]?.total ?? 0;
          const estimateColumns: Record<string, { total: string; delta: string; delta_pct: string | null }> = {};

          for (const estId of params.estimate_ids) {
            const estData = entry.estimates[estId];
            const total = estData?.total ?? 0;
            const delta = total - baselineTotal;
            const deltaPct = baselineTotal !== 0 ? ((delta / baselineTotal) * 100).toFixed(1) : null;

            estimateColumns[estId] = {
              total: total.toFixed(2),
              delta: delta.toFixed(2),
              delta_pct: deltaPct ? `${deltaPct}%` : null,
            };
          }

          return {
            cost_code: entry.cost_code,
            description: entry.description,
            estimates: estimateColumns,
          };
        });

      // Estimate-level summary
      const estimateSummaries = fetchedEstimates.map((est) => {
        const total = parseFloat(est.totalAmount ?? '0');
        const markup = parseFloat(est.markupPercentage ?? '0');
        const contingency = parseFloat(est.contingencyPercentage ?? '0');
        const markupAmt = total * (markup / 100);
        const contingencyAmt = total * (contingency / 100);
        const grandTotal = total + markupAmt + contingencyAmt;

        return {
          id: est.id,
          name: est.name,
          version: est.version,
          status: est.status,
          subtotal: total.toFixed(2),
          markup_percentage: markup,
          markup_amount: markupAmt.toFixed(2),
          contingency_percentage: contingency,
          contingency_amount: contingencyAmt.toFixed(2),
          grand_total: grandTotal.toFixed(2),
        };
      });

      // Compute overall deltas relative to the baseline
      const baselineSummary = estimateSummaries.find((s) => s.id === baselineId)!;
      const overallDeltas = estimateSummaries.map((s) => {
        const delta = parseFloat(s.grand_total) - parseFloat(baselineSummary.grand_total);
        const deltaPct =
          parseFloat(baselineSummary.grand_total) !== 0
            ? ((delta / parseFloat(baselineSummary.grand_total)) * 100).toFixed(1)
            : null;
        return {
          estimate_id: s.id,
          estimate_name: s.name,
          grand_total: s.grand_total,
          delta_from_baseline: delta.toFixed(2),
          delta_pct: deltaPct ? `${deltaPct}%` : null,
        };
      });

      return textContent({
        baseline_estimate_id: baselineId,
        missing_ids: missingIds.length > 0 ? missingIds : undefined,
        estimates: estimateSummaries,
        overall_deltas: overallDeltas,
        comparison_by_cost_code: comparisonRows,
        total_cost_codes: comparisonRows.length,
      });
      });
    },
  );
}
