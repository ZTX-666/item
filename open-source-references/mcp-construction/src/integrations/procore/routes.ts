import { Hono } from 'hono';
import { honoAuth, type AppEnv } from '../../middleware/hono-auth.js';
import { buildAuthUrl, exchangeCode, disconnect } from './oauth.js';
import { syncProjects, syncRfis, syncChangeOrders } from './sync.js';
import { logger } from '../../lib/logger.js';

export const procoreRoutes = new Hono<AppEnv>();

// All Procore routes require authentication
procoreRoutes.use('/integrations/procore/*', honoAuth);

/**
 * GET /integrations/procore/connect
 * Returns the Procore OAuth authorization URL.
 */
procoreRoutes.get('/integrations/procore/connect', (c) => {
  const userContext = c.get('userContext');
  const state = Buffer.from(JSON.stringify({ orgId: userContext.orgId })).toString('base64url');
  const url = buildAuthUrl(state);
  return c.json({ authorization_url: url });
});

/**
 * GET /integrations/procore/callback
 * Handles the OAuth callback from Procore.
 */
procoreRoutes.get('/integrations/procore/callback', async (c) => {
  try {
    const code = c.req.query('code');
    const state = c.req.query('state');

    if (!code || !state) {
      return c.json({ error: 'Missing code or state parameter' }, 400);
    }

    const decoded = JSON.parse(Buffer.from(state, 'base64url').toString());
    const orgId = decoded.orgId;

    if (!orgId) {
      return c.json({ error: 'Invalid state parameter' }, 400);
    }

    await exchangeCode(orgId, code);

    return c.json({ success: true, message: 'Procore connected successfully' });
  } catch (err) {
    logger.error({ err }, 'Procore callback failed');
    return c.json({ error: 'Failed to connect Procore' }, 500);
  }
});

/**
 * POST /integrations/procore/disconnect
 * Disconnects the Procore integration.
 */
procoreRoutes.post('/integrations/procore/disconnect', async (c) => {
  const userContext = c.get('userContext');

  try {
    await disconnect(userContext.orgId);
    return c.json({ success: true, message: 'Procore disconnected' });
  } catch (err) {
    logger.error({ err }, 'Procore disconnect failed');
    return c.json({ error: 'Failed to disconnect Procore' }, 500);
  }
});

/**
 * POST /integrations/procore/sync
 * Triggers a sync of projects, RFIs, and change orders from Procore.
 */
procoreRoutes.post('/integrations/procore/sync', async (c) => {
  const userContext = c.get('userContext');

  try {
    const body = await c.req.json().catch(() => ({}));
    const procoreProjectId = (body as any).procore_project_id as string | undefined;

    const results: Record<string, unknown> = {};

    // Always sync projects
    results.projects = await syncProjects(userContext.orgId);

    // Optionally sync RFIs and COs for a specific project
    if (procoreProjectId) {
      results.rfis = await syncRfis(userContext.orgId, procoreProjectId);
      results.change_orders = await syncChangeOrders(userContext.orgId, procoreProjectId);
    }

    return c.json({ success: true, sync_results: results });
  } catch (err) {
    logger.error({ err }, 'Procore sync failed');
    return c.json({ error: err instanceof Error ? err.message : 'Sync failed' }, 500);
  }
});
