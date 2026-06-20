import { z } from 'zod';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import { projects } from '../../db/schema.js';
import { textContent, errorContent, requireContext, executeWithMiddleware, validateProjectAccess } from '../../lib/tool-helpers.js';

const CreateProjectInput = z.object({
  name: z.string().min(1).describe('Project name'),
  project_number: z.string().optional().describe('Internal project number / job code'),
  address: z.string().optional().describe('Street address of the project site'),
  city: z.string().optional().describe('City'),
  state: z.string().max(2).optional().describe('Two-letter state abbreviation'),
  zip: z.string().max(10).optional().describe('ZIP / postal code'),
  project_type: z.enum([
    'commercial',
    'residential',
    'industrial',
    'infrastructure',
    'renovation',
    'tenant_improvement',
  ]).describe('Classification of the project'),
  contract_type: z.enum([
    'lump_sum',
    'cost_plus',
    'gmp',
    't_and_m',
    'design_build',
    'cmar',
  ]).describe('Contract delivery method'),
  contract_amount: z.number().nonnegative().optional().describe('Original contract value in dollars'),
  start_date: z.string().optional().describe('Planned start date (YYYY-MM-DD)'),
  estimated_completion: z.string().optional().describe('Estimated completion date (YYYY-MM-DD)'),
  owner_name: z.string().optional().describe('Property owner or client name'),
  architect_name: z.string().optional().describe('Architect of record'),
  superintendent: z.string().optional().describe('Field superintendent assigned'),
  project_manager: z.string().optional().describe('Project manager assigned'),
});

export function register(server: McpServer): void {
  server.tool(
    'create_project',
    'Create a new construction project with contract details, key personnel, and classification',
    CreateProjectInput.shape,
    async (args, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'create_project', async () => {
        try {
          const db = getDb();
          const orgId = ctx.orgId;

          if (!orgId) {
            return errorContent('Organization context is required to create a project');
          }

          const [project] = await db
            .insert(projects)
            .values({
              orgId,
              name: args.name,
              projectNumber: args.project_number,
              address: args.address,
              city: args.city,
              state: args.state,
              zip: args.zip,
              projectType: args.project_type,
              contractType: args.contract_type,
              contractAmount: args.contract_amount != null
                ? String(args.contract_amount)
                : undefined,
              startDate: args.start_date,
              estimatedCompletion: args.estimated_completion,
              status: 'preconstruction',
              ownerName: args.owner_name,
              architectName: args.architect_name,
              superintendent: args.superintendent,
              projectManager: args.project_manager,
            })
            .returning();

          return textContent({
            success: true,
            project: {
              id: project.id,
              org_id: project.orgId,
              name: project.name,
              project_number: project.projectNumber,
              address: project.address,
              city: project.city,
              state: project.state,
              zip: project.zip,
              project_type: project.projectType,
              contract_type: project.contractType,
              contract_amount: project.contractAmount
                ? parseFloat(project.contractAmount)
                : null,
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
          });
        } catch (err: any) {
          return errorContent(err.message ?? 'Failed to create project');
        }
      });
    },
  );
}
