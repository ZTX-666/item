export const McpErrorCodes = {
  UNAUTHORIZED: -32001,
  RATE_LIMIT: -32002,
  SUBSCRIPTION_REQUIRED: -32003,
  NOT_FOUND: -32004,
  VALIDATION: -32005,
  INTEGRATION_ERROR: -32006,
  INVALID_PARAMS: -32602,
} as const;

export class McpError extends Error {
  code: number;
  data?: unknown;

  constructor(code: number, message: string, data?: unknown) {
    super(message);
    this.name = 'McpError';
    this.code = code;
    this.data = data;
  }
}

export function unauthorized(message = 'Unauthorized'): McpError {
  return new McpError(McpErrorCodes.UNAUTHORIZED, message);
}

export function rateLimited(retryAfter?: number): McpError {
  return new McpError(McpErrorCodes.RATE_LIMIT, 'Rate limit exceeded', {
    retry_after: retryAfter,
  });
}

export function subscriptionRequired(): McpError {
  return new McpError(
    McpErrorCodes.SUBSCRIPTION_REQUIRED,
    'Active subscription required. Use POST /billing/checkout to subscribe.',
    {
      checkout_endpoint: '/billing/checkout',
      plans: ['starter', 'pro', 'enterprise'],
    },
  );
}

export function notFound(resource: string): McpError {
  return new McpError(McpErrorCodes.NOT_FOUND, `${resource} not found`);
}

export function validationError(message: string, details?: unknown): McpError {
  return new McpError(McpErrorCodes.VALIDATION, message, details);
}

export function integrationError(message: string): McpError {
  return new McpError(McpErrorCodes.INTEGRATION_ERROR, message);
}

export function invalidParams(message: string): McpError {
  return new McpError(McpErrorCodes.INVALID_PARAMS, message);
}
