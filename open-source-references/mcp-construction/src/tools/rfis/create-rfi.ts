import { z } from 'zod';
import { eq, sql } from 'drizzle-orm';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import { rfis } from '../../db/schema.js';
import { requireContext, executeWithMiddleware, validateProjectAccess, textContent, errorContent } from '../../lib/tool-helpers.js';

export function register(server: McpServer) {
  server.tool(
    'create_rfi',
    'Create an RFI. Auto-numbers sequentially per project. Tracks cost/schedule impact.',
    {
      project_id: z.string().uuid(),
      subject: z.string(),
      question: z.string(),
      assigned_to: z.string().optional(),
      priority: z.enum(['low', 'normal', 'high', 'urgent']).optional(),
      due_date: z.string().optional(),
      cost_impact: z.boolean().optional(),
      schedule_impact: z.boolean().optional(),
    },
    async (params, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'create_rfi', async () => {
        await validateProjectAccess(params.project_id, ctx.orgId);
        try {
          const db = getDb();

          // Get the max rfi_number for this project and increment by 1
          const maxResult = await db
            .select({ maxNum: sql<number>`coalesce(max(${rfis.rfiNumber}), 0)` })
            .from(rfis)
            .where(eq(rfis.projectId, params.project_id));

          const nextNumber = (maxResult[0]?.maxNum ?? 0) + 1;

          const [created] = await db
            .insert(rfis)
            .values({
              projectId: params.project_id,
              rfiNumber: nextNumber,
              subject: params.subject,
              question: params.question,
              assignedTo: params.assigned_to,
              priority: params.priority ?? 'normal',
              dueDate: params.due_date,
              costImpact: params.cost_impact ?? false,
              scheduleImpact: params.schedule_impact ?? false,
              status: 'draft',
            })
            .returning();

          return textContent(created);
        } catch (err) {
          return errorContent(err instanceof Error ? err.message : 'Failed to create RFI');
        }
      });
    },
  );
}
