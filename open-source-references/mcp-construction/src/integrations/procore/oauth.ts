import { eq, and } from 'drizzle-orm';
import { config } from '../../config.js';
import { getDb } from '../../db/index.js';
import { integrations } from '../../db/schema.js';
import { encrypt, decrypt } from '../../lib/encryption.js';
import { refreshProcoreToken } from './client.js';
import { logger } from '../../lib/logger.js';

/**
 * Build the Procore OAuth 2.0 authorization URL.
 */
export function buildAuthUrl(state: string): string {
  const params = new URLSearchParams({
    response_type: 'code',
    client_id: config.PROCORE_CLIENT_ID,
    redirect_uri: config.PROCORE_REDIRECT_URI,
    state,
  });
  return `${config.PROCORE_API_BASE}/oauth/authorize?${params}`;
}

/**
 * Exchange an authorization code for tokens and store them encrypted.
 */
export async function exchangeCode(
  orgId: string,
  code: string,
): Promise<{ success: boolean }> {
  const response = await fetch(`${config.PROCORE_API_BASE}/oauth/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      grant_type: 'authorization_code',
      client_id: config.PROCORE_CLIENT_ID,
      client_secret: config.PROCORE_CLIENT_SECRET,
      code,
      redirect_uri: config.PROCORE_REDIRECT_URI,
    }),
  });

  if (!response.ok) {
    const err = await response.text();
    logger.error({ status: response.status, err }, 'Procore code exchange failed');
    throw new Error('Failed to exchange authorization code');
  }

  const tokens = (await response.json()) as {
    access_token: string;
    refresh_token: string;
    expires_in: number;
  };

  const db = getDb();
  const expiresAt = new Date(Date.now() + tokens.expires_in * 1000);

  // Upsert integration record
  const [existing] = await db
    .select({ id: integrations.id })
    .from(integrations)
    .where(and(eq(integrations.orgId, orgId), eq(integrations.provider, 'procore')))
    .limit(1);

  const values = {
    accessTokenEncrypted: encrypt(tokens.access_token),
    refreshTokenEncrypted: encrypt(tokens.refresh_token),
    tokenExpiresAt: expiresAt,
    status: 'active' as const,
    updatedAt: new Date(),
  };

  if (existing) {
    await db
      .update(integrations)
      .set(values)
      .where(eq(integrations.id, existing.id));
  } else {
    await db.insert(integrations).values({
      orgId,
      provider: 'procore',
      ...values,
    });
  }

  return { success: true };
}

/**
 * Get a valid access token for the given org, refreshing if expired.
 */
export async function getValidAccessToken(orgId: string): Promise<string> {
  const db = getDb();

  const [integration] = await db
    .select()
    .from(integrations)
    .where(and(eq(integrations.orgId, orgId), eq(integrations.provider, 'procore')))
    .limit(1);

  if (!integration || !integration.accessTokenEncrypted) {
    throw new Error('Procore integration not connected');
  }

  // Check if token is still valid (with 5-min buffer)
  if (integration.tokenExpiresAt && integration.tokenExpiresAt > new Date(Date.now() + 300_000)) {
    return decrypt(integration.accessTokenEncrypted);
  }

  // Refresh the token
  if (!integration.refreshTokenEncrypted) {
    throw new Error('No refresh token available. Please reconnect Procore.');
  }

  const refreshToken = decrypt(integration.refreshTokenEncrypted);
  const newTokens = await refreshProcoreToken(refreshToken);

  const expiresAt = new Date(Date.now() + newTokens.expires_in * 1000);

  await db
    .update(integrations)
    .set({
      accessTokenEncrypted: encrypt(newTokens.access_token),
      refreshTokenEncrypted: encrypt(newTokens.refresh_token),
      tokenExpiresAt: expiresAt,
      updatedAt: new Date(),
    })
    .where(eq(integrations.id, integration.id));

  return newTokens.access_token;
}

/**
 * Disconnect the Procore integration for an org.
 */
export async function disconnect(orgId: string): Promise<void> {
  const db = getDb();
  await db
    .update(integrations)
    .set({
      accessTokenEncrypted: null,
      refreshTokenEncrypted: null,
      tokenExpiresAt: null,
      status: 'disconnected',
      updatedAt: new Date(),
    })
    .where(and(eq(integrations.orgId, orgId), eq(integrations.provider, 'procore')));
}
