import { z } from 'zod';
import { eq, and, desc, sql, sum } from 'drizzle-orm';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import { changeOrders, projects, budgetLines, scheduleTasks, rfis } from '../../db/schema.js';
import { requireContext, executeWithMiddleware, validateProjectAccess, textContent, errorContent } from '../../lib/tool-helpers.js';

export function register(server: McpServer) {
  server.tool(
    'create_change_order',
    'Create a change order. Auto-numbers. Links to originating RFI if applicable. Calculates markup.',
    {
      project_id: z.string().uuid(),
      title: z.string(),
      description: z.string().optional(),
      reason: z.enum([
        'owner_request',
        'design_error',
        'unforeseen_condition',
        'code_change',
        'value_engineering',
        'other',
      ]),
      cost_amount: z.number().describe('Cost amount in dollars. Can be negative for deductive change orders.'),
      schedule_days: z.number().int().default(0).describe('Schedule impact in calendar days'),
      markup_percentage: z.number().min(0).max(100).optional().describe('Markup percentage (0-100)'),
      related_rfi_id: z.string().uuid().optional().describe('UUID of the originating RFI, if applicable'),
    },
    async (params, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'create_change_order', async () => {
        await validateProjectAccess(params.project_id, ctx.orgId);
        try {
          const db = getDb();

          // Verify project exists
          const [project] = await db
            .select()
            .from(projects)
            .where(eq(projects.id, params.project_id))
            .limit(1);

          if (!project) {
            return errorContent(`Project not found: ${params.project_id}`);
          }

          // If related_rfi_id is provided, verify it exists and belongs to the same project
          if (params.related_rfi_id) {
            const [rfi] = await db
              .select()
              .from(rfis)
              .where(
                and(
                  eq(rfis.id, params.related_rfi_id),
                  eq(rfis.projectId, params.project_id),
                ),
              )
              .limit(1);

            if (!rfi) {
              return errorContent(
                `RFI not found or does not belong to this project: ${params.related_rfi_id}`,
              );
            }
          }

          // Get the max CO number for this project and increment
          const [maxResult] = await db
            .select({ maxNum: sql<number>`coalesce(max(${changeOrders.coNumber}), 0)` })
            .from(changeOrders)
            .where(eq(changeOrders.projectId, params.project_id));

          const nextCoNumber = (maxResult?.maxNum ?? 0) + 1;

          // Calculate markup
          const markupPercentage = params.markup_percentage ?? 0;
          const markupAmount = params.cost_amount * markupPercentage / 100;
          const totalWithMarkup = params.cost_amount + markupAmount;

          // Insert the change order
          const today = new Date().toISOString().split('T')[0];

          const [created] = await db
            .insert(changeOrders)
            .values({
              projectId: params.project_id,
              coNumber: nextCoNumber,
              title: params.title,
              description: params.description ?? null,
              reason: params.reason,
              status: 'pending',
              costAmount: params.cost_amount.toFixed(2),
              scheduleDays: params.schedule_days,
              markupAmount: markupAmount.toFixed(2),
              totalWithMarkup: totalWithMarkup.toFixed(2),
              relatedRfiId: params.related_rfi_id ?? null,
              submittedDate: today,
            })
            .returning();

          return textContent({
            message: `Change order CO-${String(nextCoNumber).padStart(3, '0')} created successfully`,
            change_order: created,
          });
        } catch (err) {
          return errorContent(`Failed to create change order: ${err instanceof Error ? err.message : String(err)}`);
        }
      });
    },
  );
}
