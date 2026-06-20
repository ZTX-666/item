import { z } from 'zod';
import { eq, and, like, sql, desc, count } from 'drizzle-orm';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import { projects } from '../../db/schema.js';
import { textContent, errorContent, requireContext, executeWithMiddleware, validateProjectAccess } from '../../lib/tool-helpers.js';
import { normalizePagination, paginatedResponse } from '../../lib/pagination.js';

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

const ListProjectsInput = z.object({
  status: z.enum(PROJECT_STATUSES).optional().describe('Filter by project status'),
  project_type: z.enum(PROJECT_TYPES).optional().describe('Filter by project type'),
  search: z.string().optional().describe('Search by project name or number (partial match)'),
  page: z.number().int().min(1).default(1).describe('Page number (starts at 1)'),
  per_page: z.number().int().min(1).max(50).default(20).describe('Results per page (max 50)'),
});

export function register(server: McpServer): void {
  server.tool(
    'list_projects',
    'List all projects for the organization with optional filters. Returns summary view.',
    ListProjectsInput.shape,
    async (args, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'list_projects', async () => {
        try {
          const db = getDb();
          const orgId = ctx.orgId;

          if (!orgId) {
            return errorContent('Organization context is required to list projects');
          }

          const { page, perPage } = normalizePagination(args.page, args.per_page);

          // Build WHERE conditions
          const conditions = [eq(projects.orgId, orgId)];

          if (args.status) {
            conditions.push(eq(projects.status, args.status));
          }

          if (args.project_type) {
            conditions.push(eq(projects.projectType, args.project_type));
          }

          if (args.search) {
            // Match against project name or project number (case-insensitive via ILIKE)
            conditions.push(
              sql`(${projects.name} ILIKE ${'%' + args.search + '%'} OR ${projects.projectNumber} ILIKE ${'%' + args.search + '%'})`,
            );
          }

          const whereClause = and(...conditions);

          // Count total matching rows
          const [totalRow] = await db
            .select({ total: count() })
            .from(projects)
            .where(whereClause);

          const total = totalRow?.total ?? 0;

          // Fetch paginated results
          const rows = await db
            .select({
              id: projects.id,
              name: projects.name,
              projectNumber: projects.projectNumber,
              city: projects.city,
              state: projects.state,
              projectType: projects.projectType,
              contractType: projects.contractType,
              contractAmount: projects.contractAmount,
              startDate: projects.startDate,
              estimatedCompletion: projects.estimatedCompletion,
              status: projects.status,
              ownerName: projects.ownerName,
              projectManager: projects.projectManager,
              createdAt: projects.createdAt,
            })
            .from(projects)
            .where(whereClause)
            .orderBy(desc(projects.createdAt))
            .limit(perPage)
            .offset((page - 1) * perPage);

          // Map to a cleaner response shape
          const data = rows.map((row) => ({
            id: row.id,
            name: row.name,
            project_number: row.projectNumber,
            city: row.city,
            state: row.state,
            project_type: row.projectType,
            contract_type: row.contractType,
            contract_amount: row.contractAmount ? parseFloat(row.contractAmount) : null,
            start_date: row.startDate,
            estimated_completion: row.estimatedCompletion,
            status: row.status,
            owner_name: row.ownerName,
            project_manager: row.projectManager,
            created_at: row.createdAt,
          }));

          return textContent(paginatedResponse(data, total, { page, perPage }));
        } catch (err: any) {
          return errorContent(err.message ?? 'Failed to list projects');
        }
      });
    },
  );
}
