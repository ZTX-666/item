import { z } from 'zod';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { requireContext, executeWithMiddleware, validateProjectAccess, textContent, errorContent } from '../../lib/tool-helpers.js';

export function register(server: McpServer) {
  server.tool(
    'get_submittal_status',
    'Submittal log with review status tracking',
    {
      project_id: z.string().uuid(),
      status_filter: z.enum(['pending', 'approved', 'approved_as_noted', 'revise_resubmit', 'rejected']).optional(),
    },
    async (args, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'get_submittal_status', async () => {
      await validateProjectAccess(args.project_id, ctx.orgId);
      // Submittals are tracked via Procore integration or a future submittals table
      return textContent({
        submittals: [],
        total: 0,
        by_status: {
          pending: 0,
          approved: 0,
          approved_as_noted: 0,
          revise_resubmit: 0,
          rejected: 0,
        },
        note: 'Submittal tracking available through Procore integration. Configure integration in organization settings.',
      });
      });
    },
  );
}
