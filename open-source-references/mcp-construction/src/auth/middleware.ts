import { verifyAccessToken, type UserContext } from './jwt.js';
import { hasRequiredScopes } from './scopes.js';
import { unauthorized } from '../lib/errors.js';
import { logger } from '../lib/logger.js';

// Store user context per request (keyed by session or request ID)
const requestContextMap = new Map<string, UserContext>();

export function setRequestContext(requestId: string, ctx: UserContext): void {
  requestContextMap.set(requestId, ctx);
}

export function getRequestContext(requestId: string): UserContext | undefined {
  return requestContextMap.get(requestId);
}

export function clearRequestContext(requestId: string): void {
  requestContextMap.delete(requestId);
}

export async function authenticateRequest(
  authHeader: string | undefined,
): Promise<UserContext> {
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    throw unauthorized('Missing or invalid Authorization header');
  }

  const token = authHeader.slice(7);

  try {
    const userContext = await verifyAccessToken(token);
    return userContext;
  } catch (err) {
    logger.warn({ err }, 'JWT verification failed');
    throw unauthorized('Invalid or expired access token');
  }
}

export function checkToolScope(userContext: UserContext, toolName: string): void {
  if (!hasRequiredScopes(userContext.scopes, toolName)) {
    throw unauthorized(
      `Insufficient scope for tool '${toolName}'. Required scopes not present.`,
    );
  }
}
