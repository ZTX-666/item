import { eq, and } from 'drizzle-orm';
import type { UserContext } from '../auth/jwt.js';
import { getRequestContext } from '../auth/middleware.js';
import { checkToolScope } from '../auth/middleware.js';
import { billingMiddleware } from '../billing/middleware.js';
import { getDb } from '../db/index.js';
import { projects, subcontractors } from '../db/schema.js';
import { unauthorized, notFound } from './errors.js';

export function textContent(data: unknown) {
  return {
    content: [{ type: 'text' as const, text: JSON.stringify(data, null, 2) }],
  };
}

export function errorContent(message: string) {
  return {
    content: [{ type: 'text' as const, text: JSON.stringify({ error: message }) }],
    isError: true,
  };
}

export async function executeWithMiddleware(
  userContext: UserContext,
  toolName: string,
  handler: () => Promise<any>,
) {
  // Check scopes
  checkToolScope(userContext, toolName);

  // Run through billing middleware
  return billingMiddleware(userContext, toolName, handler);
}

/**
 * Extract UserContext from the MCP session. Throws unauthorized if missing.
 */
export function requireContext(sessionId: string | undefined): UserContext {
  if (!sessionId) {
    throw unauthorized('Session ID is required');
  }
  const ctx = getRequestContext(sessionId);
  if (!ctx) {
    throw unauthorized('No authenticated session found');
  }
  return ctx;
}

/**
 * Validate that a project belongs to the caller's organization.
 * Returns the project row on success, throws notFound otherwise.
 */
export async function validateProjectAccess(projectId: string, orgId: string) {
  const db = getDb();
  const [project] = await db
    .select({ id: projects.id, orgId: projects.orgId })
    .from(projects)
    .where(and(eq(projects.id, projectId), eq(projects.orgId, orgId)))
    .limit(1);

  if (!project) {
    throw notFound('Project');
  }
  return project;
}

/**
 * Validate that a subcontractor belongs to the caller's organization.
 */
export async function validateSubcontractorAccess(subId: string, orgId: string) {
  const db = getDb();
  const [sub] = await db
    .select({ id: subcontractors.id })
    .from(subcontractors)
    .where(and(eq(subcontractors.id, subId), eq(subcontractors.orgId, orgId)))
    .limit(1);

  if (!sub) {
    throw notFound('Subcontractor');
  }
  return sub;
}
