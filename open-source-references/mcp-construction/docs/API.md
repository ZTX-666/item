# CMCP — Construction AI MCP Server

**Base URL:** `https://cmcp.us`
**Protocol:** MCP (Model Context Protocol) over Streamable HTTP
**Auth:** OAuth 2.1 with PKCE (S256)

---

## Quick Start

### 1. Create an Account

```
POST /signup
Content-Type: application/json

{
  "org_name": "Your Company",
  "email": "you@example.com",
  "password": "securepassword"
}
```

**Response (201):**
```json
{
  "org_id": "uuid",
  "user_id": "uuid",
  "client_id": "uuid",
  "client_secret": "hex-string",
  "plan": "trial",
  "trial_ends_at": "2026-02-20T00:00:00.000Z",
  "next_steps": {
    "authorization_url": "https://cmcp.us/oauth/authorize",
    "token_url": "https://cmcp.us/oauth/token",
    "mcp_endpoint": "https://cmcp.us/mcp",
    "oauth_metadata": "https://cmcp.us/.well-known/oauth-authorization-server"
  }
}
```

Save `client_id` and `client_secret` — you need them for all subsequent steps.

### 2. Get an Access Token

CMCP uses OAuth 2.1 with PKCE. Generate a code verifier and challenge:

```python
import hashlib, base64, secrets
code_verifier = secrets.token_urlsafe(64)
code_challenge = base64.urlsafe_b64encode(
    hashlib.sha256(code_verifier.encode()).digest()
).rstrip(b'=').decode()
```

**Authorize:**
```
POST /oauth/authorize
Content-Type: application/x-www-form-urlencoded

client_id=YOUR_CLIENT_ID
&redirect_uri=http://localhost:8080/callback
&response_type=code
&scope=projects:read projects:write estimates:read estimates:write
&code_challenge=BASE64URL_CHALLENGE
&code_challenge_method=S256
&email=you@example.com
&password=securepassword
```

This returns a redirect with `?code=AUTHORIZATION_CODE`.

**Exchange code for tokens:**
```
POST /oauth/token
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code
&code=AUTHORIZATION_CODE
&redirect_uri=http://localhost:8080/callback
&code_verifier=YOUR_CODE_VERIFIER
&client_id=YOUR_CLIENT_ID
&client_secret=YOUR_CLIENT_SECRET
```

**Response:**
```json
{
  "access_token": "eyJhbGci...",
  "refresh_token": "hex-string",
  "token_type": "Bearer",
  "expires_in": 3600,
  "scope": "projects:read projects:write estimates:read estimates:write"
}
```

### 3. Connect via MCP

**Initialize session:**
```
POST /mcp
Authorization: Bearer YOUR_ACCESS_TOKEN
Content-Type: application/json
Accept: application/json, text/event-stream

{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2025-03-26",
    "capabilities": {},
    "clientInfo": { "name": "your-agent", "version": "1.0.0" }
  }
}
```

Capture the `mcp-session-id` response header — include it in all subsequent requests.

**Call a tool:**
```
POST /mcp
Authorization: Bearer YOUR_ACCESS_TOKEN
Content-Type: application/json
Accept: application/json, text/event-stream
mcp-session-id: SESSION_ID_FROM_INIT

{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "create_project",
    "arguments": {
      "name": "Office Tower",
      "project_type": "commercial",
      "contract_type": "gmp",
      "start_date": "2026-04-01"
    }
  }
}
```

### 4. Refresh Tokens

Access tokens expire after 1 hour. Use the refresh token:

```
POST /oauth/token
Content-Type: application/x-www-form-urlencoded

grant_type=refresh_token
&refresh_token=YOUR_REFRESH_TOKEN
&client_id=YOUR_CLIENT_ID
&client_secret=YOUR_CLIENT_SECRET
```

---

## Authentication

### OAuth 2.1 with PKCE

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/.well-known/oauth-authorization-server` | GET | RFC 8414 server metadata |
| `/oauth/register` | POST | Dynamic client registration (RFC 7591) |
| `/oauth/authorize` | GET/POST | Authorization endpoint |
| `/oauth/token` | POST | Token endpoint |

**Supported flows:** `authorization_code`, `refresh_token`
**Code challenge method:** `S256` only
**Token lifetime:** 1 hour (access), long-lived (refresh)

### Scopes

Request only the scopes your agent needs:

| Scope | Access |
|-------|--------|
| `projects:read` | View projects |
| `projects:write` | Create/update projects |
| `estimates:read` | View estimates |
| `estimates:write` | Create/update estimates |
| `rfis:read` | View RFIs |
| `rfis:write` | Create/respond to RFIs |
| `change_orders:read` | View change orders |
| `change_orders:write` | Create/approve change orders |
| `daily_logs:read` | View daily logs |
| `daily_logs:write` | Create daily logs |
| `budget:read` | View budgets |
| `budget:write` | Update budgets |
| `schedule:read` | View schedules |
| `schedule:write` | Update schedules |
| `subcontractors:read` | View subcontractors |
| `subcontractors:write` | Manage subcontractors |
| `documents:read` | Search documents |
| `documents:write` | Create documents |
| `safety:read` | View safety data |
| `safety:write` | Log incidents |
| `users:read` | View users |
| `users:write` | Manage users |
| `org:read` | View org settings |
| `org:write` | Update org settings |
| `admin` | Admin operations |

---

## MCP Protocol

All MCP communication happens over `POST /mcp` using JSON-RPC 2.0 with SSE responses.

**Required headers on every request:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
Accept: application/json, text/event-stream
mcp-session-id: <session_id>          (after initialize)
```

**Response format:** Server-Sent Events (SSE)
```
event: message
data: {"result": {...}, "jsonrpc": "2.0", "id": 1}
```

Parse by stripping `event: message\ndata: ` prefix, then JSON parse the data line.

### MCP Methods

| Method | Description |
|--------|-------------|
| `initialize` | Start session, get server capabilities |
| `tools/list` | List all available tools |
| `tools/call` | Execute a tool |
| `resources/list` | List available resources |
| `prompts/list` | List available prompts |

---

## Tools Reference

### Projects

#### `create_project`
Create a new construction project.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | yes | Project name |
| `project_number` | string | no | Project number/code |
| `address` | string | no | Street address |
| `city` | string | no | City |
| `state` | string(2) | no | State abbreviation |
| `zip` | string(10) | no | ZIP code |
| `project_type` | enum | no | `commercial`, `residential`, `industrial`, `infrastructure`, `renovation`, `tenant_improvement` |
| `contract_type` | enum | no | `lump_sum`, `cost_plus`, `gmp`, `t_and_m`, `design_build`, `cmar` |
| `contract_amount` | number | no | Contract value (>= 0) |
| `start_date` | string | no | YYYY-MM-DD |
| `estimated_completion` | string | no | YYYY-MM-DD |
| `owner_name` | string | no | Project owner |
| `architect_name` | string | no | Architect of record |
| `superintendent` | string | no | Site superintendent |
| `project_manager` | string | no | Project manager |

#### `get_project`
Get full project details.

| Parameter | Type | Required |
|-----------|------|----------|
| `project_id` | UUID | yes |

#### `list_projects`
List projects with filters.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `status` | enum | no | `preconstruction`, `active`, `on_hold`, `punch_list`, `closed_out`, `warranty` |
| `project_type` | enum | no | Same as create_project |
| `search` | string | no | Partial match on name/number |
| `page` | int | no | Default 1 |
| `per_page` | int | no | 1-50, default 20 |

#### `update_project`
Update project fields. Same parameters as `create_project` plus `project_id` (required) and `status` (optional enum).

#### `get_project_dashboard`
Aggregated health metrics: budget, schedule completion, open RFIs, pending COs, safety incidents, alerts.

| Parameter | Type | Required |
|-----------|------|----------|
| `project_id` | UUID | yes |

---

### Estimates

#### `create_estimate`
Create a cost estimate with optional CSI MasterFormat line items.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project_id` | UUID | yes | |
| `name` | string | yes | Estimate name |
| `line_items` | array | no | See line item schema below |
| `markup_percentage` | number | no | 0-100 |
| `contingency_percentage` | number | no | 0-100 |

**Line item schema:**
| Field | Type | Required |
|-------|------|----------|
| `cost_code` | string | yes |
| `description` | string | yes |
| `quantity` | number (>0) | yes |
| `unit` | enum | yes |
| `unit_cost` | number (>=0) | yes |
| `category` | enum | yes |
| `notes` | string | no |

**Units:** `SF`, `LF`, `CY`, `EA`, `LS`, `HR`, `TON`, `GAL`, `SY`, `MBF`, `SQ`, `LB`
**Categories:** `labor`, `material`, `equipment`, `subcontractor`, `overhead`

#### `get_estimate`
Get estimate with line items, division subtotals, markup breakdown.

| Parameter | Type | Required |
|-----------|------|----------|
| `estimate_id` | UUID | yes |

#### `update_line_item`
Modify a specific line item.

| Parameter | Type | Required |
|-----------|------|----------|
| `line_item_id` | UUID | yes |
| `quantity` | number | no |
| `unit_cost` | number | no |
| `description` | string | no |
| `cost_code` | string | no |
| `category` | enum | no |
| `notes` | string | no |

#### `compare_estimates`
Side-by-side comparison showing delta per cost code.

| Parameter | Type | Required |
|-----------|------|----------|
| `estimate_ids` | UUID[] | yes (2-5) |

#### `generate_estimate_report`
AI-enhanced formatted summary with industry benchmark comparison.

| Parameter | Type | Required |
|-----------|------|----------|
| `estimate_id` | UUID | yes |
| `format` | enum | yes |

**Formats:** `summary`, `detailed`, `executive`

#### `import_cost_data`
Bulk import RSMeans-style cost reference data.

| Parameter | Type | Required |
|-----------|------|----------|
| `project_id` | UUID | yes |
| `data` | array | yes (min 1) |
| `source` | string | no |

**Data item:** `{ cost_code, description, unit, unit_cost, region?, year? }`

---

### RFIs

#### `create_rfi`
Create an RFI. Auto-numbers sequentially per project.

| Parameter | Type | Required |
|-----------|------|----------|
| `project_id` | UUID | yes |
| `subject` | string | yes |
| `question` | string | yes |
| `assigned_to` | string | no |
| `priority` | enum | no |
| `due_date` | string | no |
| `cost_impact` | boolean | no |
| `schedule_impact` | boolean | no |

**Priorities:** `low`, `normal`, `high`, `urgent`

#### `list_rfis`
List RFIs with filters. Default sort: newest first.

| Parameter | Type | Required |
|-----------|------|----------|
| `project_id` | UUID | yes |
| `status` | enum | no |
| `priority` | enum | no |
| `assigned_to` | string | no |
| `overdue_only` | boolean | no |
| `page` | int | no |
| `per_page` | int | no (max 100) |

**Statuses:** `draft`, `open`, `answered`, `closed`, `void`

#### `get_rfi`
Full RFI details including linked change orders.

| Parameter | Type | Required |
|-----------|------|----------|
| `rfi_id` | UUID | yes |

#### `respond_to_rfi`
Submit response. Updates status to answered.

| Parameter | Type | Required |
|-----------|------|----------|
| `rfi_id` | UUID | yes |
| `answer` | string | yes |
| `cost_impact_amount` | number | no |
| `schedule_impact_days` | int | no |

#### `draft_rfi_response`
AI-generated draft response using project context and similar past RFIs.

| Parameter | Type | Required |
|-----------|------|----------|
| `rfi_id` | UUID | yes |
| `context` | string | no |
| `reference_spec_sections` | string[] | no |
| `tone` | enum | no |

**Tones:** `formal`, `concise`, `detailed`

---

### Change Orders

#### `create_change_order`
Create a change order. Auto-numbers. Can link to originating RFI.

| Parameter | Type | Required |
|-----------|------|----------|
| `project_id` | UUID | yes |
| `title` | string | yes |
| `description` | string | no |
| `reason` | enum | yes |
| `cost_amount` | number | yes (can be negative) |
| `schedule_days` | int | no (default 0) |
| `markup_percentage` | number | no (0-100) |
| `related_rfi_id` | UUID | no |

**Reasons:** `owner_request`, `design_error`, `unforeseen_condition`, `code_change`, `value_engineering`, `other`

#### `evaluate_change_order_impact`
Analyzes financial and schedule impact against current budget and critical path.

| Parameter | Type | Required |
|-----------|------|----------|
| `change_order_id` | UUID | yes |

#### `approve_change_order`
Approve a pending CO. Updates budget. **Requires admin scope.**

| Parameter | Type | Required |
|-----------|------|----------|
| `change_order_id` | UUID | yes |
| `approved_amount` | number | no |
| `notes` | string | no |

#### `get_change_order_log`
Full CO log with running contract total.

| Parameter | Type | Required |
|-----------|------|----------|
| `project_id` | UUID | yes |
| `status_filter` | enum | no |

**Statuses:** `draft`, `pending`, `approved`, `rejected`, `void`

---

### Daily Logs

#### `create_daily_log`
Record daily construction log entry.

| Parameter | Type | Required |
|-----------|------|----------|
| `project_id` | UUID | yes |
| `log_date` | string | yes (YYYY-MM-DD) |
| `weather_conditions` | enum | no |
| `temperature_high` | number | no |
| `temperature_low` | number | no |
| `workers_on_site` | array | no |
| `equipment_on_site` | array | no |
| `work_performed` | string | yes |
| `materials_received` | string | no |
| `delays` | string | no |
| `delay_hours` | number | no |
| `notes` | string | no |

**Weather:** `clear`, `partly_cloudy`, `overcast`, `rain`, `snow`, `fog`, `extreme_heat`, `extreme_cold`
**Worker:** `{ company, trade, headcount }`
**Equipment:** `{ type, hours, idle? }`

#### `get_daily_log`
Retrieve log for a specific date.

| Parameter | Type | Required |
|-----------|------|----------|
| `project_id` | UUID | yes |
| `log_date` | string | yes (YYYY-MM-DD) |

#### `summarize_daily_logs`
AI-generated executive summary over a date range.

| Parameter | Type | Required |
|-----------|------|----------|
| `project_id` | UUID | yes |
| `start_date` | string | yes |
| `end_date` | string | yes |

#### `generate_weekly_report`
AI-generated comprehensive weekly report from daily logs, RFIs, COs, budget, and schedule.

| Parameter | Type | Required |
|-----------|------|----------|
| `project_id` | UUID | yes |
| `week_ending` | string | yes (YYYY-MM-DD) |

---

### Budget

#### `get_budget_by_cost_code`
Budget by CSI cost code: original, changes, committed, actual, projected variance.

| Parameter | Type | Required |
|-----------|------|----------|
| `project_id` | UUID | yes |
| `cost_code_filter` | string | no |
| `show_only_overruns` | boolean | no (default false) |

#### `flag_budget_overruns`
Identifies cost codes where actual+committed exceeds threshold.

| Parameter | Type | Required |
|-----------|------|----------|
| `project_id` | UUID | yes |
| `threshold_percentage` | number | no (default 90) |

#### `forecast_completion_cost`
Projects Estimate at Completion using CPI, bottom-up, and trend methods.

| Parameter | Type | Required |
|-----------|------|----------|
| `project_id` | UUID | yes |
| `method` | enum | no (default `all`) |

**Methods:** `cpi`, `bottom_up`, `trend`, `all`

#### `track_committed_costs`
All committed costs (contracts + POs) by cost code.

| Parameter | Type | Required |
|-----------|------|----------|
| `project_id` | UUID | yes |
| `cost_code_filter` | string | no |

---

### Schedule

#### `get_schedule`
Full project schedule with dependencies and status.

| Parameter | Type | Required |
|-----------|------|----------|
| `project_id` | UUID | yes |
| `wbs_filter` | string | no |
| `status_filter` | enum | no |

**Statuses:** `not_started`, `in_progress`, `complete`, `delayed`

#### `check_critical_path`
Critical path tasks (zero total float). Optionally includes near-critical.

| Parameter | Type | Required |
|-----------|------|----------|
| `project_id` | UUID | yes |
| `include_near_critical` | boolean | no (default false) |

#### `flag_delayed_tasks`
Tasks behind schedule with impact assessment.

| Parameter | Type | Required |
|-----------|------|----------|
| `project_id` | UUID | yes |
| `threshold_days` | number | no (default 0) |

#### `calculate_float`
Total and free float for all schedule tasks.

| Parameter | Type | Required |
|-----------|------|----------|
| `project_id` | UUID | yes |

---

### Subcontractors

#### `list_subcontractors`
List subs with filters.

| Parameter | Type | Required |
|-----------|------|----------|
| `trade` | string | no |
| `prequalification_status` | string | no |
| `min_rating` | number | no (0-5) |
| `search` | string | no |

#### `get_sub_performance`
Performance metrics across all projects.

| Parameter | Type | Required |
|-----------|------|----------|
| `subcontractor_id` | UUID | yes |

#### `compare_bids`
Bid comparison matrix, normalized for inclusions/exclusions.

| Parameter | Type | Required |
|-----------|------|----------|
| `project_id` | UUID | yes |
| `scope_description` | string | no |
| `subcontractor_ids` | UUID[] | no |
| `trade` | string | no |

#### `generate_sub_scorecard`
AI-generated scorecard: quality, schedule adherence, safety, cooperation.

| Parameter | Type | Required |
|-----------|------|----------|
| `subcontractor_id` | UUID | yes |
| `project_id` | UUID | no |

---

### Documents

#### `search_project_docs`
Full-text search across project documents.

| Parameter | Type | Required |
|-----------|------|----------|
| `project_id` | UUID | yes |
| `query` | string | yes |
| `doc_type` | enum | no (default `all`) |

**Types:** `rfi`, `co`, `daily_log`, `estimate`, `submittal`, `all`

#### `get_submittal_status`
Submittal log with review tracking.

| Parameter | Type | Required |
|-----------|------|----------|
| `project_id` | UUID | yes |
| `status_filter` | enum | no |

**Statuses:** `pending`, `approved`, `approved_as_noted`, `revise_resubmit`, `rejected`

#### `generate_aia_payment_app`
AIA G702/G703 payment application data.

| Parameter | Type | Required |
|-----------|------|----------|
| `project_id` | UUID | yes |
| `application_number` | int | yes (>= 1) |
| `period_to` | string | yes (YYYY-MM-DD) |
| `include_stored_materials` | boolean | no (default false) |

#### `create_lien_waiver`
Generate lien waiver data.

| Parameter | Type | Required |
|-----------|------|----------|
| `project_id` | UUID | yes |
| `waiver_type` | enum | yes |
| `claimant_name` | string | yes |
| `through_date` | string | yes (YYYY-MM-DD) |
| `amount` | number | yes (>= 0) |

**Waiver types:** `conditional_progress`, `unconditional_progress`, `conditional_final`, `unconditional_final`

---

### Safety

#### `log_safety_incident`
Record safety incident with OSHA classification.

| Parameter | Type | Required |
|-----------|------|----------|
| `project_id` | UUID | yes |
| `incident_date` | string | yes (ISO datetime) |
| `incident_type` | enum | yes |
| `severity` | enum | yes |
| `description` | string | yes (min 10 chars) |
| `location_on_site` | string | no |
| `persons_involved` | array | no |
| `root_cause` | string | no |
| `corrective_actions` | string | no |
| `osha_recordable` | boolean | no |

**Incident types:** `near_miss`, `first_aid`, `recordable`, `lost_time`, `fatality`, `property_damage`, `environmental`
**Severities:** `low`, `medium`, `high`, `critical`
**Person:** `{ name, company, role, injury_description? }`

#### `get_osha_compliance_status`
OSHA dashboard: recordable rate, DART rate, EMR, days since last incident.

| Parameter | Type | Required |
|-----------|------|----------|
| `project_id` | UUID | no |
| `period` | enum | no (default `ytd`) |

**Periods:** `ytd`, `trailing_12`, `all_time`

#### `generate_toolbox_talk`
AI-generated safety talk tailored to project conditions.

| Parameter | Type | Required |
|-----------|------|----------|
| `project_id` | UUID | yes |
| `topic` | string | no |
| `target_trades` | string[] | no |
| `language` | enum | no (default `english`) |

**Languages:** `english`, `spanish`, `bilingual`

#### `track_certifications`
Worker certification expiration tracking.

| Parameter | Type | Required |
|-----------|------|----------|
| `project_id` | UUID | no |
| `expiring_within_days` | int | no (default 30) |

---

### Users & Organization

#### `create_user`
Add a user. **Requires admin scope.**

| Parameter | Type | Required |
|-----------|------|----------|
| `email` | string | yes |
| `name` | string | yes |
| `password` | string | yes (min 8) |
| `role` | enum | no (default `member`) |

**Roles:** `owner`, `admin`, `member`, `viewer`

#### `list_users`
List all org users. No parameters.

#### `update_user_role`
Change a user's role. **Requires admin scope.**

| Parameter | Type | Required |
|-----------|------|----------|
| `user_id` | UUID | yes |
| `role` | enum | yes |

#### `remove_user`
Remove user from org. **Requires admin scope.**

| Parameter | Type | Required |
|-----------|------|----------|
| `user_id` | UUID | yes |

#### `get_org_settings`
Get org name, plan, subscription status. No parameters.

#### `update_org_settings`
Update org settings. **Requires admin scope.**

| Parameter | Type | Required |
|-----------|------|----------|
| `name` | string | no |
| `settings` | object | no |

---

## Billing

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/billing/checkout` | POST | yes | Create Stripe checkout session |
| `/billing/portal` | POST | yes | Open Stripe billing portal |
| `/billing/success` | GET | no | Post-payment success page |
| `/billing/cancel` | GET | no | Payment cancelled page |

**Checkout request:**
```json
{
  "plan": "starter",
  "success_url": "https://your-app.com/success",
  "cancel_url": "https://your-app.com/cancel"
}
```

**Checkout response:**
```json
{
  "checkout_url": "https://checkout.stripe.com/...",
  "session_id": "cs_live_..."
}
```

### Plans

| Plan | Price | Included Calls | Overage |
|------|-------|----------------|---------|
| Trial | Free (7 days) | 2,000 | — |
| Starter | $49/mo | 500 | $0.05/call |
| Pro | $149/mo | 2,000 | $0.03/call |
| Enterprise | $499/mo | 10,000 | $0.02/call |

---

## Error Codes

MCP tool errors use JSON-RPC error codes:

| Code | Name | Description |
|------|------|-------------|
| -32001 | UNAUTHORIZED | Missing or invalid auth |
| -32002 | RATE_LIMIT | Too many requests |
| -32003 | SUBSCRIPTION_REQUIRED | Trial expired or no subscription |
| -32004 | NOT_FOUND | Resource not found |
| -32005 | VALIDATION | Input validation failed |
| -32006 | INTEGRATION_ERROR | External service error |
| -32602 | INVALID_PARAMS | Invalid tool parameters |

**Error response format:**
```json
{
  "result": {
    "content": [{ "type": "text", "text": "Error message" }],
    "isError": true
  },
  "jsonrpc": "2.0",
  "id": 1
}
```

---

## Other Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/health` | GET | no | Liveness check |
| `/status` | GET | no | Detailed health metrics (CPU, RAM, DB, Redis) |
| `/.well-known/oauth-authorization-server` | GET | no | OAuth server metadata |
