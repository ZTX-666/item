import { randomBytes, createHash } from 'node:crypto';
import bcrypt from 'bcrypt';
import { eq, and } from 'drizzle-orm';
import { getDb } from '../db/index.js';
import {
  oauthClients,
  authorizationCodes,
  refreshTokens,
  users,
  organizations,
} from '../db/schema.js';
import { createAccessToken } from './jwt.js';
import { logger } from '../lib/logger.js';

// ── Dynamic Client Registration ──────────────────────────────────────────

export async function registerClient(input: {
  client_name: string;
  redirect_uris: string[];
  grant_types?: string[];
  scope?: string;
}) {
  const db = getDb();
  const clientId = crypto.randomUUID();
  const clientSecret = randomBytes(32).toString('hex');
  const clientSecretHash = await bcrypt.hash(clientSecret, 10);

  await db.insert(oauthClients).values({
    clientId,
    clientSecretHash,
    clientName: input.client_name,
    redirectUris: input.redirect_uris,
    grantTypes: input.grant_types || ['authorization_code'],
    scope: input.scope || '',
  });

  return {
    client_id: clientId,
    client_secret: clientSecret,
    client_id_issued_at: Math.floor(Date.now() / 1000),
    client_secret_expires_at: 0,
  };
}

// ── Authorization Code ───────────────────────────────────────────────────

export async function createAuthorizationCode(input: {
  clientId: string;
  userId: string;
  redirectUri: string;
  scope: string;
  codeChallenge: string;
  codeChallengeMethod: string;
}): Promise<string> {
  const db = getDb();
  const code = randomBytes(32).toString('hex');
  const expiresAt = new Date(Date.now() + 10 * 60 * 1000); // 10 min

  await db.insert(authorizationCodes).values({
    code,
    clientId: input.clientId,
    userId: input.userId,
    redirectUri: input.redirectUri,
    scope: input.scope,
    codeChallenge: input.codeChallenge,
    codeChallengeMethod: input.codeChallengeMethod,
    expiresAt,
  });

  return code;
}

// ── Token Exchange ───────────────────────────────────────────────────────

export async function exchangeAuthorizationCode(input: {
  code: string;
  redirectUri: string;
  codeVerifier: string;
  clientId: string;
  clientSecret?: string;
}) {
  const db = getDb();

  // Validate client secret if the client has one registered
  const [client] = await db
    .select()
    .from(oauthClients)
    .where(eq(oauthClients.clientId, input.clientId))
    .limit(1);

  if (!client) throw new Error('Invalid client');

  if (client.clientSecretHash) {
    if (!input.clientSecret) throw new Error('Client secret required');
    const secretValid = await bcrypt.compare(input.clientSecret, client.clientSecretHash);
    if (!secretValid) throw new Error('Invalid client secret');
  }

  const [authCode] = await db
    .select()
    .from(authorizationCodes)
    .where(
      and(
        eq(authorizationCodes.code, input.code),
        eq(authorizationCodes.clientId, input.clientId),
      ),
    )
    .limit(1);

  if (!authCode) throw new Error('Invalid authorization code');
  if (authCode.used) throw new Error('Authorization code already used');
  if (new Date() > authCode.expiresAt) throw new Error('Authorization code expired');
  if (authCode.redirectUri !== input.redirectUri) throw new Error('Redirect URI mismatch');

  // Verify PKCE
  const expectedChallenge = createHash('sha256')
    .update(input.codeVerifier)
    .digest('base64url');
  if (expectedChallenge !== authCode.codeChallenge) {
    throw new Error('PKCE verification failed');
  }

  // Mark code as used
  await db
    .update(authorizationCodes)
    .set({ used: true })
    .where(eq(authorizationCodes.id, authCode.id));

  // Get user + org info for JWT
  const [user] = await db
    .select()
    .from(users)
    .where(eq(users.id, authCode.userId))
    .limit(1);

  if (!user) throw new Error('User not found');

  const [org] = await db
    .select()
    .from(organizations)
    .where(eq(organizations.id, user.orgId))
    .limit(1);

  if (!org) throw new Error('Organization not found');

  // Create access token
  const accessToken = await createAccessToken({
    userId: user.id,
    orgId: org.id,
    scope: authCode.scope,
    plan: org.plan,
    clientId: input.clientId,
  });

  // Create refresh token
  const refreshTokenValue = randomBytes(32).toString('hex');
  const tokenHash = createHash('sha256').update(refreshTokenValue).digest('hex');

  await db.insert(refreshTokens).values({
    tokenHash,
    userId: user.id,
    clientId: input.clientId,
    scope: authCode.scope,
    expiresAt: new Date(Date.now() + 90 * 24 * 60 * 60 * 1000), // 90 days
  });

  return {
    access_token: accessToken,
    token_type: 'Bearer',
    expires_in: 3600,
    refresh_token: refreshTokenValue,
    scope: authCode.scope,
  };
}

// ── Refresh Token ────────────────────────────────────────────────────────

export async function refreshAccessToken(input: {
  refreshToken: string;
  clientId: string;
  clientSecret?: string;
}) {
  const db = getDb();

  // Validate client secret if the client has one registered
  const [client] = await db
    .select()
    .from(oauthClients)
    .where(eq(oauthClients.clientId, input.clientId))
    .limit(1);

  if (!client) throw new Error('Invalid client');

  if (client.clientSecretHash) {
    if (!input.clientSecret) throw new Error('Client secret required');
    const secretValid = await bcrypt.compare(input.clientSecret, client.clientSecretHash);
    if (!secretValid) throw new Error('Invalid client secret');
  }

  const tokenHash = createHash('sha256').update(input.refreshToken).digest('hex');

  const [storedToken] = await db
    .select()
    .from(refreshTokens)
    .where(
      and(
        eq(refreshTokens.tokenHash, tokenHash),
        eq(refreshTokens.clientId, input.clientId),
      ),
    )
    .limit(1);

  if (!storedToken) throw new Error('Invalid refresh token');
  if (storedToken.revoked) throw new Error('Refresh token revoked');
  if (new Date() > storedToken.expiresAt) throw new Error('Refresh token expired');

  // Revoke old token
  await db
    .update(refreshTokens)
    .set({ revoked: true })
    .where(eq(refreshTokens.id, storedToken.id));

  // Get user + org
  const [user] = await db
    .select()
    .from(users)
    .where(eq(users.id, storedToken.userId))
    .limit(1);
  if (!user) throw new Error('User not found');

  const [org] = await db
    .select()
    .from(organizations)
    .where(eq(organizations.id, user.orgId))
    .limit(1);
  if (!org) throw new Error('Organization not found');

  // New access token
  const accessToken = await createAccessToken({
    userId: user.id,
    orgId: org.id,
    scope: storedToken.scope,
    plan: org.plan,
    clientId: input.clientId,
  });

  // New refresh token (rotation)
  const newRefreshTokenValue = randomBytes(32).toString('hex');
  const newTokenHash = createHash('sha256').update(newRefreshTokenValue).digest('hex');

  await db.insert(refreshTokens).values({
    tokenHash: newTokenHash,
    userId: user.id,
    clientId: input.clientId,
    scope: storedToken.scope,
    expiresAt: new Date(Date.now() + 90 * 24 * 60 * 60 * 1000),
  });

  return {
    access_token: accessToken,
    token_type: 'Bearer',
    expires_in: 3600,
    refresh_token: newRefreshTokenValue,
    scope: storedToken.scope,
  };
}

// ── Validate Client ──────────────────────────────────────────────────────

export async function validateClient(clientId: string) {
  const db = getDb();
  const [client] = await db
    .select()
    .from(oauthClients)
    .where(eq(oauthClients.clientId, clientId))
    .limit(1);
  return client || null;
}
