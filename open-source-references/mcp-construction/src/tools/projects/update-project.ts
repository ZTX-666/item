import { z } from 'zod';
import { eq } from 'drizzle-orm';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import { projects } from '../../db/schema.js';
import { textContent, errorContent, requireContext, executeWithMiddleware, validateProjectAccess } from '../../lib/tool-helpers.js';
import { notFound } from '../../lib/errors.js';

const PROJECT_STATUSES = [
  'preconstruction',
  'active',
  'on_hold',
  'punch_list',
  'closed_out',
  'warranty',
] as const;

const PROJECT_TYPES = [
  'commercial',
  'residential',
  'industrial',
  'infrastructure',
  'renovation',
  'tenant_improvement',
] as const;

const CONTRACT_TYPES = [
  'lump_sum',
  'cost_plus',
  'gmp',
  't_and_m',
  'design_build',
  'cmar',
] as const;

const UpdateProjectInput = z.object({
  project_id: z.string().uuid().describe('Unique project identifier'),
  name: z.string().min(1).optional().describe('Project name'),
  project_number: z.string().optional().describe('Internal project number / job code'),
  address: z.string().optional().describe('Street address'),
  city: z.string().optional().describe('City'),
  state: z.string().max(2).optional().describe('Two-letter state abbreviation'),
  zip: z.string().max(10).optional().describe('ZIP / postal code'),
  project_type: z.enum(PROJECT_TYPES).optional().describe('Project classification'),
  contract_type: z.enum(CONTRACT_TYPES).optional().describe('Contract delivery method'),
  contract_amount: z.number().nonnegative().optional().describe('Original contract value in dollars'),
  start_date: z.string().optional().describe('Planned start date (YYYY-MM-DD)'),
  estimated_completion: z.string().optional().describe('Estimated completion date (YYYY-MM-DD)'),
  status: z.enum(PROJECT_STATUSES).optional().describe('Project lifecycle status'),
  owner_name: z.string().optional().describe('Property owner or client name'),
  architect_name: z.string().optional().describe('Architect of record'),
  superintendent: z.string().optional().describe('Field superintendent'),
  project_manager: z.string().optional().describe('Project manager'),
});

export function register(server: McpServer): void {
  server.tool(
    'update_project',
    'Update project fields. Tracks field changes for audit log.',
    UpdateProjectInput.shape,
    async (args, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'update_project', async () => {
        await validateProjectAccess(args.project_id, ctx.orgId);
        try {
          const db = getDb();

          // Fetch the current project first to validate existence and track changes
          const [existing] = await db
            .select()
            .from(projects)
            .where(eq(projects.id, args.project_id))
            .limit(1);

          if (!existing) {
            throw notFound('Project');
          }

          // Build the update payload from only the fields that were provided
          const updates: Record<string, unknown> = {};
          const changes: Array<{ field: string; old_value: unknown; new_value: unknown }> = [];

          const fieldMap: Record<string, { dbColumn: string; currentValue: unknown }> = {
            name:                 { dbColumn: 'name',                currentValue: existing.name },
            project_number:       { dbColumn: 'projectNumber',       currentValue: existing.projectNumber },
            address:              { dbColumn: 'address',              currentValue: existing.address },
            city:                 { dbColumn: 'city',                 currentValue: existing.city },
            state:                { dbColumn: 'state',                currentValue: existing.state },
            zip:                  { dbColumn: 'zip',                  currentValue: existing.zip },
            project_type:         { dbColumn: 'projectType',          currentValue: existing.projectType },
            contract_type:        { dbColumn: 'contractType',         currentValue: existing.contractType },
            start_date:           { dbColumn: 'startDate',            currentValue: existing.startDate },
            estimated_completion: { dbColumn: 'estimatedCompletion',  currentValue: existing.estimatedCompletion },
            status:               { dbColumn: 'status',               currentValue: existing.status },
            owner_name:           { dbColumn: 'ownerName',            currentValue: existing.ownerName },
            architect_name:       { dbColumn: 'architectName',        currentValue: existing.architectName },
            superintendent:       { dbColumn: 'superintendent',       currentValue: existing.superintendent },
            project_manager:      { dbColumn: 'projectManager',       currentValue: existing.projectManager },
          };

          for (const [inputKey, { dbColumn, currentValue }] of Object.entries(fieldMap)) {
            const newValue = (args as Record<string, unknown>)[inputKey];
            if (newValue !== undefined && newValue !== currentValue) {
              updates[dbColumn] = newValue;
              changes.push({ field: inputKey, old_value: currentValue, new_value: newValue });
            }
          }

          // Handle contract_amount separately because it needs string conversion
          if (args.contract_amount !== undefined) {
            const newAmountStr = String(args.contract_amount);
            if (newAmountStr !== existing.contractAmount) {
              updates.contractAmount = newAmountStr;
              changes.push({
                field: 'contract_amount',
                old_value: existing.contractAmount ? parseFloat(existing.contractAmount) : null,
                new_value: args.contract_amount,
              });
            }
          }

          if (Object.keys(updates).length === 0) {
            return textContent({
              success: true,
              message: 'No fields changed',
              changes: [],
            });
          }

          // Always bump updatedAt
          updates.updatedAt = new Date();

          const [updated] = await db
            .update(projects)
            .set(updates)
            .where(eq(projects.id, args.project_id))
            .returning();

          return textContent({
            success: true,
            project: {
              id: updated.id,
              org_id: updated.orgId,
              name: updated.name,
              project_number: updated.projectNumber,
              address: updated.address,
              city: updated.city,
              state: updated.state,
              zip: updated.zip,
              project_type: updated.projectType,
              contract_type: updated.contractType,
              contract_amount: updated.contractAmount
                ? parseFloat(updated.contractAmount)
                : null,
              start_date: updated.startDate,
              estimated_completion: updated.estimatedCompletion,
              actual_completion: updated.actualCompletion,
              status: updated.status,
              owner_name: updated.ownerName,
              architect_name: updated.architectName,
              superintendent: updated.superintendent,
              project_manager: updated.projectManager,
              metadata: updated.metadata,
              created_at: updated.createdAt,
              updated_at: updated.updatedAt,
            },
            changes,
          });
        } catch (err: any) {
          if (err.code === -32004) {
            return errorContent(err.message);
          }
          return errorContent(err.message ?? 'Failed to update project');
        }
      });
    },
  );
}
