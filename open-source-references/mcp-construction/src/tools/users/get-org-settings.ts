import { eq } from 'drizzle-orm';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import { organizations } from '../../db/schema.js';
import { requireContext, executeWithMiddleware, textContent, errorContent } from '../../lib/tool-helpers.js';

export function register(server: McpServer): void {
  server.tool(
    'get_org_settings',
    'Get organization name, plan, subscription status, and settings.',
    {},
    async (_args, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'get_org_settings', async () => {
        const db = getDb();

        const [org] = await db
          .select({
            id: organizations.id,
            name: organizations.name,
            slug: organizations.slug,
            plan: organizations.plan,
            subscriptionStatus: organizations.subscriptionStatus,
            trialEndsAt: organizations.trialEndsAt,
            settings: organizations.settings,
            createdAt: organizations.createdAt,
          })
          .from(organizations)
          .where(eq(organizations.id, ctx.orgId))
          .limit(1);

        if (!org) {
          return errorContent('Organization not found');
        }

        return textContent({
          organization: {
            id: org.id,
            name: org.name,
            slug: org.slug,
            plan: org.plan,
            subscription_status: org.subscriptionStatus,
            trial_ends_at: org.trialEndsAt,
            settings: org.settings,
            created_at: org.createdAt,
          },
        });
      });
    },
  );
}
