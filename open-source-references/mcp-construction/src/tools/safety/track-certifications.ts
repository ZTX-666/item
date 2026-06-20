import { z } from 'zod';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { requireContext, executeWithMiddleware, validateProjectAccess, textContent, errorContent } from '../../lib/tool-helpers.js';

export function register(server: McpServer) {
  server.tool(
    'track_certifications',
    'Worker certifications and expiration tracking',
    {
      project_id: z.string().uuid().optional(),
      expiring_within_days: z.number().int().min(1).optional().default(30),
    },
    async (args, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'track_certifications', async () => {
      if (args.project_id) await validateProjectAccess(args.project_id, ctx.orgId);
      return textContent({
        certifications: [],
        expiring_soon: [],
        expired: [],
        summary: {
          total_tracked: 0,
          expiring_within_period: 0,
          expired: 0,
          compliance_rate: 100,
        },
        note: 'Certification tracking requires worker records to be configured. Connect via Procore integration or manual entry to populate certification data.',
      });
      });
    },
  );
}
