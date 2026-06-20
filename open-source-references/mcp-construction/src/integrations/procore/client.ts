import { config } from '../../config.js';
import { logger } from '../../lib/logger.js';

interface ProcoreRequestOptions {
  method?: string;
  path: string;
  body?: unknown;
  accessToken: string;
}

interface ProcoreResponse<T = unknown> {
  ok: boolean;
  status: number;
  data: T;
}

/**
 * HTTP wrapper for Procore REST API with structured error handling.
 */
export async function procoreRequest<T = unknown>(
  options: ProcoreRequestOptions,
): Promise<ProcoreResponse<T>> {
  const url = `${config.PROCORE_API_BASE}${options.path}`;
  const method = options.method ?? 'GET';

  const headers: Record<string, string> = {
    Authorization: `Bearer ${options.accessToken}`,
    'Content-Type': 'application/json',
  };

  const fetchOptions: RequestInit = { method, headers };
  if (options.body) {
    fetchOptions.body = JSON.stringify(options.body);
  }

  logger.debug({ url, method }, 'Procore API request');

  const response = await fetch(url, fetchOptions);
  const data = (await response.json().catch(() => ({}))) as T;

  if (!response.ok) {
    logger.error(
      { url, method, status: response.status, data },
      'Procore API error',
    );
  }

  return {
    ok: response.ok,
    status: response.status,
    data,
  };
}

/**
 * Refresh an expired Procore access token.
 */
export async function refreshProcoreToken(refreshToken: string): Promise<{
  access_token: string;
  refresh_token: string;
  expires_in: number;
}> {
  const response = await fetch(`${config.PROCORE_API_BASE}/oauth/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      grant_type: 'refresh_token',
      client_id: config.PROCORE_CLIENT_ID,
      client_secret: config.PROCORE_CLIENT_SECRET,
      refresh_token: refreshToken,
    }),
  });

  if (!response.ok) {
    throw new Error(`Procore token refresh failed: ${response.status}`);
  }

  return response.json() as Promise<{ access_token: string; refresh_token: string; expires_in: number }>;
}
