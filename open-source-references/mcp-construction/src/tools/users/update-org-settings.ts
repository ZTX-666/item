import { z } from 'zod';
import { eq } from 'drizzle-orm';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import { organizations } from '../../db/schema.js';
import { requireContext, executeWithMiddleware, textContent, errorContent } from '../../lib/tool-helpers.js';

const UpdateOrgSettingsInput = z.object({
  name: z.string().min(1).optional().describe('Organization name'),
  settings: z.record(z.unknown()).optional().describe('Organization settings object (merged with existing)'),
});

export function register(server: McpServer): void {
  server.tool(
    'update_org_settings',
    'Update organization name or settings. Requires admin scope.',
    UpdateOrgSettingsInput.shape,
    async (args, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'update_org_settings', async () => {
        const db = getDb();

        const [org] = await db
          .select()
          .from(organizations)
          .where(eq(organizations.id, ctx.orgId))
          .limit(1);

        if (!org) {
          return errorContent('Organization not found');
        }

        const updates: Record<string, unknown> = { updatedAt: new Date() };

        if (args.name !== undefined) {
          updates.name = args.name;
        }

        if (args.settings !== undefined) {
          // Merge new settings with existing
          const existingSettings = (org.settings as Record<string, unknown>) ?? {};
          updates.settings = { ...existingSettings, ...args.settings };
        }

        const [updated] = await db
          .update(organizations)
          .set(updates)
          .where(eq(organizations.id, ctx.orgId))
          .returning({
            id: organizations.id,
            name: organizations.name,
            slug: organizations.slug,
            plan: organizations.plan,
            settings: organizations.settings,
            updatedAt: organizations.updatedAt,
          });

        return textContent({ success: true, organization: updated });
      });
    },
  );
}
