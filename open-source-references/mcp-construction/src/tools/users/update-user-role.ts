import { z } from 'zod';
import { eq, and } from 'drizzle-orm';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import { users } from '../../db/schema.js';
import { requireContext, executeWithMiddleware, textContent, errorContent } from '../../lib/tool-helpers.js';

const UpdateUserRoleInput = z.object({
  user_id: z.string().uuid().describe('User UUID'),
  role: z.enum(['owner', 'admin', 'member', 'viewer']).describe('New role'),
});

export function register(server: McpServer): void {
  server.tool(
    'update_user_role',
    'Change a user\'s role within the organization. Cannot demote the last owner. Requires admin scope.',
    UpdateUserRoleInput.shape,
    async (args, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'update_user_role', async () => {
        const db = getDb();

        // Verify user belongs to this org
        const [user] = await db
          .select()
          .from(users)
          .where(and(eq(users.id, args.user_id), eq(users.orgId, ctx.orgId)))
          .limit(1);

        if (!user) {
          return errorContent('User not found in this organization');
        }

        // Protect last owner
        if (user.role === 'owner' && args.role !== 'owner') {
          const owners = await db
            .select({ id: users.id })
            .from(users)
            .where(and(eq(users.orgId, ctx.orgId), eq(users.role, 'owner')));

          if (owners.length <= 1) {
            return errorContent('Cannot demote the last owner. Assign another owner first.');
          }
        }

        const [updated] = await db
          .update(users)
          .set({ role: args.role })
          .where(eq(users.id, args.user_id))
          .returning({
            id: users.id,
            email: users.email,
            name: users.name,
            role: users.role,
          });

        return textContent({ success: true, user: updated });
      });
    },
  );
}
