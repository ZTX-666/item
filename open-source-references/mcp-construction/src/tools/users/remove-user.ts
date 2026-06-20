import { z } from 'zod';
import { eq, and } from 'drizzle-orm';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import { users } from '../../db/schema.js';
import { requireContext, executeWithMiddleware, textContent, errorContent } from '../../lib/tool-helpers.js';

const RemoveUserInput = z.object({
  user_id: z.string().uuid().describe('User UUID to remove'),
});

export function register(server: McpServer): void {
  server.tool(
    'remove_user',
    'Remove a user from the organization. Cannot remove the last owner. Requires admin scope.',
    RemoveUserInput.shape,
    async (args, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'remove_user', async () => {
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

        // Cannot remove yourself
        if (user.id === ctx.userId) {
          return errorContent('Cannot remove yourself from the organization');
        }

        // Protect last owner
        if (user.role === 'owner') {
          const owners = await db
            .select({ id: users.id })
            .from(users)
            .where(and(eq(users.orgId, ctx.orgId), eq(users.role, 'owner')));

          if (owners.length <= 1) {
            return errorContent('Cannot remove the last owner. Assign another owner first.');
          }
        }

        await db.delete(users).where(eq(users.id, args.user_id));

        return textContent({
          success: true,
          message: `User ${user.email} removed from organization`,
        });
      });
    },
  );
}
