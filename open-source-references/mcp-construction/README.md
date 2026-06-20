# CMCP — Construction AI MCP Server

A production MCP server with **50 tools** for construction project management. Built for the **AEC industry** (Architecture, Engineering & Construction). Estimates, RFIs, change orders, daily logs, budgets, schedules, safety, subcontractors, and more — all accessible to AI agents via the [Model Context Protocol](https://modelcontextprotocol.io).

**Live at [cmcp.us](https://cmcp.us)**

> Categories: `construction` `project-management` `AEC` `MCP` `AI`

## Features

- **50 construction management tools** across 11 categories
- **AI-enhanced tools** — draft RFI responses, generate weekly reports, safety toolbox talks, subcontractor scorecards
- **OAuth 2.1 with PKCE** (S256) — standards-compliant authentication
- **Multi-tenant** — complete org-level data isolation
- **Scope-based access control** — 28 granular scopes
- **Stripe billing** — metered usage with overage pricing
- **MCP Streamable HTTP** — JSON-RPC 2.0 over SSE

## Tools

| Category | Tools | Highlights |
|----------|-------|------------|
| **Projects** | 5 | CRUD, dashboard with aggregated health metrics |
| **Estimates** | 6 | CSI MasterFormat, bulk line items, version comparison, AI reports |
| **RFIs** | 5 | Auto-numbering, AI-drafted responses, cost/schedule impact tracking |
| **Change Orders** | 4 | Impact analysis, approval workflow, running contract total |
| **Daily Logs** | 4 | Weather, crew, equipment tracking, AI weekly reports |
| **Budget** | 4 | Cost code breakdown, overrun alerts, EAC forecasting |
| **Schedule** | 4 | Critical path, float calculation, delay detection |
| **Subcontractors** | 4 | Bid comparison, performance metrics, AI scorecards |
| **Documents** | 4 | Full-text search, AIA G702/G703, lien waivers |
| **Safety** | 4 | OSHA compliance, incident logging, bilingual toolbox talks |
| **Users/Org** | 6 | User management, role-based access, org settings |

## Quick Start

### 1. Create an Account

```bash
curl -X POST https://cmcp.us/signup \
  -H "Content-Type: application/json" \
  -d '{"org_name":"Your Company","email":"you@example.com","password":"securepass"}'
```

Returns `client_id`, `client_secret`, and a 7-day free trial with 2,000 tool calls.

### 2. Authenticate (OAuth 2.1 + PKCE)

```bash
# Generate PKCE challenge
VERIFIER=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")
CHALLENGE=$(python3 -c "import hashlib,base64; print(base64.urlsafe_b64encode(hashlib.sha256('$VERIFIER'.encode()).digest()).rstrip(b'=').decode())")

# Authorize
curl -X POST https://cmcp.us/oauth/authorize \
  -d "client_id=YOUR_CLIENT_ID&redirect_uri=http://localhost:8080/callback&response_type=code&scope=projects:read+projects:write&code_challenge=$CHALLENGE&code_challenge_method=S256&email=you@example.com&password=securepass"

# Exchange code for token
curl -X POST https://cmcp.us/oauth/token \
  -d "grant_type=authorization_code&code=AUTH_CODE&redirect_uri=http://localhost:8080/callback&code_verifier=$VERIFIER&client_id=YOUR_CLIENT_ID&client_secret=YOUR_CLIENT_SECRET"
```

### 3. Connect via MCP

```bash
# Initialize session
curl -X POST https://cmcp.us/mcp \
  -H "Authorization: Bearer ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"your-agent","version":"1.0"}}}'

# Call a tool (include mcp-session-id from init response)
curl -X POST https://cmcp.us/mcp \
  -H "Authorization: Bearer ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: SESSION_ID" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"create_project","arguments":{"name":"Office Tower","project_type":"commercial","contract_type":"gmp"}}}'
```

## Pricing

| Plan | Price | Included Calls | Overage |
|------|-------|----------------|---------|
| Trial | Free (7 days) | 2,000 | — |
| Starter | $49/mo | 500 | $0.05/call |
| Pro | $149/mo | 2,000 | $0.03/call |
| Enterprise | $499/mo | 10,000 | $0.02/call |

## Scopes

Request only the scopes your agent needs:

`projects:read` `projects:write` `estimates:read` `estimates:write` `rfis:read` `rfis:write` `change_orders:read` `change_orders:write` `daily_logs:read` `daily_logs:write` `budget:read` `budget:write` `schedule:read` `schedule:write` `subcontractors:read` `subcontractors:write` `documents:read` `documents:write` `safety:read` `safety:write` `users:read` `users:write` `org:read` `org:write` `admin`

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /signup` | Create account |
| `GET /.well-known/oauth-authorization-server` | OAuth metadata |
| `POST /oauth/authorize` | Authorization |
| `POST /oauth/token` | Token exchange |
| `POST /mcp` | MCP endpoint |
| `POST /billing/checkout` | Stripe checkout |
| `POST /billing/portal` | Billing portal |
| `GET /health` | Liveness check |
| `GET /status` | System health metrics |

Full API documentation: [docs/API.md](docs/API.md)

## Tech Stack

- **Runtime:** Node.js + TypeScript
- **Framework:** [Hono](https://hono.dev)
- **Protocol:** [MCP SDK](https://github.com/modelcontextprotocol/typescript-sdk) (Streamable HTTP)
- **Database:** PostgreSQL ([Neon](https://neon.tech)) + [Drizzle ORM](https://orm.drizzle.team)
- **Cache:** Redis ([Upstash](https://upstash.com))
- **Auth:** OAuth 2.1 + PKCE, JWT (RS256)
- **Billing:** [Stripe](https://stripe.com) (subscriptions + metered usage)
- **Queue:** [BullMQ](https://bullmq.io) (usage reporting)

## License

Proprietary. See [cmcp.us](https://cmcp.us) for terms.
