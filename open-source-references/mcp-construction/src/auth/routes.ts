import { Hono } from 'hono';
import { config } from '../config.js';
import { SCOPES_SUPPORTED } from './scopes.js';
import {
  registerClient,
  createAuthorizationCode,
  exchangeAuthorizationCode,
  refreshAccessToken,
  validateClient,
} from './oauth.js';
import { handleSignup } from './signup.js';
import { logger } from '../lib/logger.js';

export const authRoutes = new Hono();

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// ── Server Metadata Discovery (RFC 8414) ─────────────────────────────────

authRoutes.get('/.well-known/oauth-authorization-server', (c) => {
  return c.json({
    issuer: config.SERVER_URL,
    authorization_endpoint: `${config.SERVER_URL}/oauth/authorize`,
    token_endpoint: `${config.SERVER_URL}/oauth/token`,
    registration_endpoint: `${config.SERVER_URL}/oauth/register`,
    scopes_supported: SCOPES_SUPPORTED,
    grant_types_supported: ['authorization_code', 'refresh_token'],
    code_challenge_methods_supported: ['S256'],
    token_endpoint_auth_methods_supported: ['client_secret_post', 'none'],
    response_types_supported: ['code'],
  });
});

// ── Dynamic Client Registration (RFC 7591) ───────────────────────────────

authRoutes.post('/oauth/register', async (c) => {
  try {
    const body = await c.req.json();
    const result = await registerClient({
      client_name: body.client_name,
      redirect_uris: body.redirect_uris,
      grant_types: body.grant_types,
      scope: body.scope,
    });
    return c.json(result, 201);
  } catch (err) {
    logger.error({ err }, 'Client registration failed');
    return c.json({ error: 'invalid_client_metadata' }, 400);
  }
});

// ── Self-Service Signup ──────────────────────────────────────────────────

authRoutes.post('/signup', async (c) => {
  try {
    const body = await c.req.json();
    const result = await handleSignup({
      org_name: body.org_name,
      email: body.email,
      password: body.password,
      plan: body.plan,
    });
    return c.json(result, 201);
  } catch (err: any) {
    logger.error({ err }, 'Signup failed');
    return c.json(
      { error: 'signup_failed', error_description: err.message },
      400,
    );
  }
});

// ── Authorization Endpoint ───────────────────────────────────────────────

authRoutes.get('/oauth/authorize', async (c) => {
  const clientId = c.req.query('client_id');
  const redirectUri = c.req.query('redirect_uri');
  const responseType = c.req.query('response_type');
  const scope = c.req.query('scope') || '';
  const state = c.req.query('state') || '';
  const codeChallenge = c.req.query('code_challenge');
  const codeChallengeMethod = c.req.query('code_challenge_method') || 'S256';

  if (!clientId || !redirectUri || responseType !== 'code' || !codeChallenge) {
    return c.json(
      { error: 'invalid_request', error_description: 'Missing required parameters' },
      400,
    );
  }

  if (codeChallengeMethod !== 'S256') {
    return c.json(
      { error: 'invalid_request', error_description: 'Only S256 code challenge method supported' },
      400,
    );
  }

  const client = await validateClient(clientId);
  if (!client) {
    return c.json({ error: 'invalid_client' }, 400);
  }

  if (!client.redirectUris.includes(redirectUri)) {
    return c.json({ error: 'invalid_redirect_uri' }, 400);
  }

  // In a full implementation, this would render a login/consent page.
  // For MCP server usage, we return a simple HTML consent page.
  const html = `<!DOCTYPE html>
<html>
<head><title>Authorize - ConstructionAI MCP</title></head>
<body>
  <h1>Authorize ${escapeHtml(client.clientName)}</h1>
  <p>This application is requesting access to your ConstructionAI account.</p>
  <p>Requested scopes: ${escapeHtml(scope || 'all')}</p>
  <form method="POST" action="/oauth/authorize">
    <input type="hidden" name="client_id" value="${escapeHtml(clientId)}" />
    <input type="hidden" name="redirect_uri" value="${escapeHtml(redirectUri)}" />
    <input type="hidden" name="scope" value="${escapeHtml(scope)}" />
    <input type="hidden" name="state" value="${escapeHtml(state)}" />
    <input type="hidden" name="code_challenge" value="${escapeHtml(codeChallenge)}" />
    <input type="hidden" name="code_challenge_method" value="${escapeHtml(codeChallengeMethod)}" />
    <label>Email: <input type="email" name="email" required /></label><br/>
    <label>Password: <input type="password" name="password" required /></label><br/>
    <button type="submit">Authorize</button>
  </form>
</body>
</html>`;

  return c.html(html);
});

authRoutes.post('/oauth/authorize', async (c) => {
  try {
    const body = await c.req.parseBody();
    const clientId = body['client_id'] as string;
    const redirectUri = body['redirect_uri'] as string;
    const scope = body['scope'] as string;
    const state = body['state'] as string;
    const codeChallenge = body['code_challenge'] as string;
    const codeChallengeMethod = body['code_challenge_method'] as string;
    const email = body['email'] as string;
    const password = body['password'] as string;

    // In production, validate email/password against users table
    // For now, look up user by email across all orgs
    const { getDb } = await import('../db/index.js');
    const { users: usersTable } = await import('../db/schema.js');
    const { eq } = await import('drizzle-orm');
    const db = getDb();

    const [user] = await db
      .select()
      .from(usersTable)
      .where(eq(usersTable.email, email))
      .limit(1);

    if (!user) {
      return c.json({ error: 'access_denied', error_description: 'Invalid credentials' }, 403);
    }

    // Validate password — require password hash to exist
    if (!user.passwordHash) {
      return c.json({ error: 'access_denied', error_description: 'Invalid credentials' }, 403);
    }
    const bcrypt = await import('bcrypt');
    const valid = await bcrypt.compare(password, user.passwordHash);
    if (!valid) {
      return c.json({ error: 'access_denied', error_description: 'Invalid credentials' }, 403);
    }

    const code = await createAuthorizationCode({
      clientId,
      userId: user.id,
      redirectUri,
      scope,
      codeChallenge,
      codeChallengeMethod,
    });

    const redirectUrl = new URL(redirectUri);
    redirectUrl.searchParams.set('code', code);
    if (state) redirectUrl.searchParams.set('state', state);

    return c.redirect(redirectUrl.toString());
  } catch (err) {
    logger.error({ err }, 'Authorization failed');
    return c.json({ error: 'server_error' }, 500);
  }
});

// ── Token Endpoint ───────────────────────────────────────────────────────

authRoutes.post('/oauth/token', async (c) => {
  try {
    const body = await c.req.parseBody();
    const grantType = body['grant_type'] as string;

    if (grantType === 'authorization_code') {
      const result = await exchangeAuthorizationCode({
        code: body['code'] as string,
        redirectUri: body['redirect_uri'] as string,
        codeVerifier: body['code_verifier'] as string,
        clientId: body['client_id'] as string,
        clientSecret: body['client_secret'] as string | undefined,
      });
      return c.json(result);
    }

    if (grantType === 'refresh_token') {
      const result = await refreshAccessToken({
        refreshToken: body['refresh_token'] as string,
        clientId: body['client_id'] as string,
        clientSecret: body['client_secret'] as string | undefined,
      });
      return c.json(result);
    }

    return c.json({ error: 'unsupported_grant_type' }, 400);
  } catch (err: any) {
    logger.error({ err }, 'Token exchange failed');
    return c.json(
      { error: 'invalid_grant', error_description: err.message },
      400,
    );
  }
});
