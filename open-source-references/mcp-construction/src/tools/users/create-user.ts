import { z } from 'zod';
import { eq, and } from 'drizzle-orm';
import bcrypt from 'bcrypt';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import { users } from '../../db/schema.js';
import { requireContext, executeWithMiddleware, textContent, errorContent } from '../../lib/tool-helpers.js';

const CreateUserInput = z.object({
  email: z.string().email().describe('User email address'),
  name: z.string().min(1).describe('Full name'),
  password: z.string().min(8).describe('Password (min 8 characters)'),
  role: z.enum(['owner', 'admin', 'member', 'viewer']).default('member').describe('User role within the organization'),
});

export function register(server: McpServer): void {
  server.tool(
    'create_user',
    'Add a new user to the caller\'s organization. Requires admin scope.',
    CreateUserInput.shape,
    async (args, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'create_user', async () => {
        const db = getDb();

        // Check if email already exists in this org
        const [existing] = await db
          .select({ id: users.id })
          .from(users)
          .where(and(eq(users.orgId, ctx.orgId), eq(users.email, args.email)))
          .limit(1);

        if (existing) {
          return errorContent(`A user with email ${args.email} already exists in this organization`);
        }

        const passwordHash = await bcrypt.hash(args.password, 12);

        const [created] = await db
          .insert(users)
          .values({
            orgId: ctx.orgId,
            email: args.email,
            name: args.name,
            passwordHash,
            role: args.role,
          })
          .returning({
            id: users.id,
            orgId: users.orgId,
            email: users.email,
            name: users.name,
            role: users.role,
            createdAt: users.createdAt,
          });

        return textContent({ success: true, user: created });
      });
    },
  );
}
