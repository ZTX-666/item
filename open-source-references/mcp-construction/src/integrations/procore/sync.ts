import { procoreRequest } from './client.js';
import { getValidAccessToken } from './oauth.js';
import { logger } from '../../lib/logger.js';

/**
 * Placeholder: sync projects from Procore into the local database.
 */
export async function syncProjects(orgId: string): Promise<{ synced: number }> {
  const accessToken = await getValidAccessToken(orgId);

  const response = await procoreRequest<any[]>({
    path: '/rest/v1.0/projects',
    accessToken,
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch Procore projects: ${response.status}`);
  }

  logger.info({ orgId, count: response.data.length }, 'Procore projects fetched for sync');

  // TODO: Upsert projects into local DB, matching by externalId
  return { synced: response.data.length };
}

/**
 * Placeholder: sync RFIs from Procore for a specific project.
 */
export async function syncRfis(
  orgId: string,
  procoreProjectId: string,
): Promise<{ synced: number }> {
  const accessToken = await getValidAccessToken(orgId);

  const response = await procoreRequest<any[]>({
    path: `/rest/v1.0/projects/${procoreProjectId}/rfis`,
    accessToken,
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch Procore RFIs: ${response.status}`);
  }

  logger.info({ orgId, procoreProjectId, count: response.data.length }, 'Procore RFIs fetched for sync');

  // TODO: Upsert RFIs into local DB
  return { synced: response.data.length };
}

/**
 * Placeholder: sync change orders from Procore for a specific project.
 */
export async function syncChangeOrders(
  orgId: string,
  procoreProjectId: string,
): Promise<{ synced: number }> {
  const accessToken = await getValidAccessToken(orgId);

  const response = await procoreRequest<any[]>({
    path: `/rest/v1.0/projects/${procoreProjectId}/change_orders`,
    accessToken,
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch Procore change orders: ${response.status}`);
  }

  logger.info({ orgId, procoreProjectId, count: response.data.length }, 'Procore COs fetched for sync');

  // TODO: Upsert change orders into local DB
  return { synced: response.data.length };
}
