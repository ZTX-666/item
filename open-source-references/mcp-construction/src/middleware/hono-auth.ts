import { createMiddleware } from 'hono/factory';
import type { Context, Next } from 'hono';
import { verifyAccessToken, type UserContext } from '../auth/jwt.js';

export type AppEnv = {
  Variables: {
    userContext: UserContext;
  };
};

/**
 * Hono middleware that extracts a Bearer JWT from the Authorization header
 * and attaches the decoded UserContext to c.set('userContext', ...).
 */
export const honoAuth = createMiddleware<AppEnv>(async (c, next) => {
  const authHeader = c.req.header('authorization');

  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return c.json({ error: 'Missing or invalid Authorization header' }, 401);
  }

  const token = authHeader.slice(7);

  try {
    const userContext = await verifyAccessToken(token);
    c.set('userContext', userContext);
    await next();
  } catch {
    return c.json({ error: 'Invalid or expired access token' }, 401);
  }
});

/**
 * Require the caller to have 'admin' in their scopes.
 */
export const requireAdmin = createMiddleware<AppEnv>(async (c, next) => {
  const userContext = c.get('userContext') as UserContext | undefined;
  if (!userContext) {
    return c.json({ error: 'Authentication required' }, 401);
  }
  if (!userContext.scopes.includes('admin')) {
    return c.json({ error: 'Admin scope required' }, 403);
  }
  await next();
});
