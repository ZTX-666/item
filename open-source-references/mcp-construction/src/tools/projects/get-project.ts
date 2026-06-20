import { z } from 'zod';
import { eq, and, sql } from 'drizzle-orm';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import { projects, changeOrders } from '../../db/schema.js';
import { textContent, errorContent, requireContext, executeWithMiddleware, validateProjectAccess } from '../../lib/tool-helpers.js';
import { notFound } from '../../lib/errors.js';

const GetProjectInput = z.object({
  project_id: z.string().uuid().describe('Unique project identifier'),
});

export function register(server: McpServer): void {
  server.tool(
    'get_project',
    'Retrieve full project details by ID including current contract total (original + approved COs), key dates, and integration sync status',
    GetProjectInput.shape,
    async (args, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'get_project', async () => {
        await validateProjectAccess(args.project_id, ctx.orgId);
        try {
          const db = getDb();

          // Fetch the project record
          const [project] = await db
            .select()
            .from(projects)
            .where(eq(projects.id, args.project_id))
            .limit(1);

          if (!project) {
            throw notFound('Project');
          }

          // Compute the sum of approved change orders for this project
          const [coAgg] = await db
            .select({
              total_approved_cos: sql<string>`coalesce(sum(${changeOrders.costAmount}), '0')`,
              approved_co_count: sql<string>`count(*)::text`,
            })
            .from(changeOrders)
            .where(
              and(
                eq(changeOrders.projectId, args.project_id),
                eq(changeOrders.status, 'approved'),
              ),
            );

          const originalContract = project.contractAmount
            ? parseFloat(project.contractAmount)
            : 0;
          const approvedCOsTotal = parseFloat(coAgg.total_approved_cos);
          const currentContractTotal = originalContract + approvedCOsTotal;

          // Compute schedule days
          const today = new Date();
          const startDate = project.startDate ? new Date(project.startDate) : null;
          const estimatedCompletion = project.estimatedCompletion
            ? new Date(project.estimatedCompletion)
            : null;
          const actualCompletion = project.actualCompletion
            ? new Date(project.actualCompletion)
            : null;

          let days_elapsed: number | null = null;
          let days_remaining: number | null = null;

          if (startDate) {
            days_elapsed = Math.max(
              0,
              Math.floor((today.getTime() - startDate.getTime()) / 86_400_000),
            );
          }
          if (estimatedCompletion && !actualCompletion) {
            days_remaining = Math.floor(
              (estimatedCompletion.getTime() - today.getTime()) / 86_400_000,
            );
          }

          return textContent({
            project: {
              id: project.id,
              org_id: project.orgId,
              external_id: project.externalId,
              integration_id: project.integrationId,
              name: project.name,
              project_number: project.projectNumber,
              address: project.address,
              city: project.city,
              state: project.state,
              zip: project.zip,
              project_type: project.projectType,
              contract_type: project.contractType,
              original_contract_amount: originalContract,
              approved_cos_total: approvedCOsTotal,
              approved_co_count: parseInt(coAgg.approved_co_count, 10),
              current_contract_total: currentContractTotal,
              start_date: project.startDate,
              estimated_completion: project.estimatedCompletion,
              actual_completion: project.actualCompletion,
              status: project.status,
              owner_name: project.ownerName,
              architect_name: project.architectName,
              superintendent: project.superintendent,
              project_manager: project.projectManager,
              metadata: project.metadata,
              created_at: project.createdAt,
              updated_at: project.updatedAt,
            },
            computed: {
              days_elapsed,
              days_remaining,
              is_synced: project.externalId != null && project.integrationId != null,
            },
          });
        } catch (err: any) {
          if (err.code === -32004) {
            return errorContent(err.message);
          }
          return errorContent(err.message ?? 'Failed to retrieve project');
        }
      });
    },
  );
}
