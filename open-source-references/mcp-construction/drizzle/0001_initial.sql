-- ConstructionAI MCP Server - Initial Migration
-- Generated from schema specification

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Organizations (multi-tenant)
CREATE TABLE IF NOT EXISTS organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    stripe_customer_id TEXT UNIQUE,
    stripe_subscription_id TEXT,
    plan TEXT NOT NULL DEFAULT 'starter' CHECK (plan IN ('starter', 'pro', 'enterprise', 'trial')),
    subscription_status TEXT NOT NULL DEFAULT 'trialing'
      CHECK (subscription_status IN ('active', 'trialing', 'past_due', 'canceled', 'paused')),
    trial_ends_at TIMESTAMPTZ,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Users
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    email TEXT NOT NULL,
    name TEXT NOT NULL,
    password_hash TEXT,
    role TEXT NOT NULL DEFAULT 'member'
      CHECK (role IN ('owner', 'admin', 'member', 'viewer')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(org_id, email)
);

-- OAuth Clients (dynamic registration)
CREATE TABLE IF NOT EXISTS oauth_clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id TEXT UNIQUE NOT NULL,
    client_secret_hash TEXT,
    client_name TEXT NOT NULL,
    redirect_uris TEXT[] NOT NULL,
    grant_types TEXT[] NOT NULL DEFAULT '{"authorization_code"}',
    scope TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Authorization Codes
CREATE TABLE IF NOT EXISTS authorization_codes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code TEXT UNIQUE NOT NULL,
    client_id TEXT NOT NULL REFERENCES oauth_clients(client_id),
    user_id UUID NOT NULL REFERENCES users(id),
    redirect_uri TEXT NOT NULL,
    scope TEXT NOT NULL,
    code_challenge TEXT NOT NULL,
    code_challenge_method TEXT NOT NULL DEFAULT 'S256',
    used BOOLEAN DEFAULT FALSE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Refresh Tokens
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token_hash TEXT UNIQUE NOT NULL,
    user_id UUID NOT NULL REFERENCES users(id),
    client_id TEXT NOT NULL REFERENCES oauth_clients(client_id),
    scope TEXT NOT NULL,
    revoked BOOLEAN DEFAULT FALSE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Connected Integrations (Procore, Buildertrend, etc.)
CREATE TABLE IF NOT EXISTS integrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    provider TEXT NOT NULL CHECK (provider IN ('procore', 'buildertrend', 'planswift', 'manual')),
    access_token_encrypted TEXT,
    refresh_token_encrypted TEXT,
    token_expires_at TIMESTAMPTZ,
    external_company_id TEXT,
    settings JSONB DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(org_id, provider)
);

-- Projects
CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    external_id TEXT,
    integration_id UUID REFERENCES integrations(id),
    name TEXT NOT NULL,
    project_number TEXT,
    address TEXT, city TEXT, state TEXT, zip TEXT,
    project_type TEXT,
    contract_type TEXT,
    contract_amount NUMERIC(15,2),
    start_date DATE,
    estimated_completion DATE,
    actual_completion DATE,
    status TEXT NOT NULL DEFAULT 'active'
      CHECK (status IN ('preconstruction','active','on_hold','punch_list','closed_out','warranty')),
    owner_name TEXT, architect_name TEXT, superintendent TEXT, project_manager TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Cost Estimates
CREATE TABLE IF NOT EXISTS estimates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id),
    name TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'draft'
      CHECK (status IN ('draft','review','approved','rejected','superseded')),
    total_amount NUMERIC(15,2),
    markup_percentage NUMERIC(5,2),
    contingency_percentage NUMERIC(5,2),
    notes TEXT,
    created_by UUID REFERENCES users(id),
    approved_by UUID REFERENCES users(id),
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Estimate Line Items
CREATE TABLE IF NOT EXISTS estimate_line_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    estimate_id UUID NOT NULL REFERENCES estimates(id) ON DELETE CASCADE,
    cost_code TEXT NOT NULL,
    description TEXT NOT NULL,
    quantity NUMERIC(12,3),
    unit TEXT,
    unit_cost NUMERIC(12,4),
    total_cost NUMERIC(15,2) GENERATED ALWAYS AS (quantity * unit_cost) STORED,
    labor_cost NUMERIC(15,2),
    material_cost NUMERIC(15,2),
    equipment_cost NUMERIC(15,2),
    subcontractor_cost NUMERIC(15,2),
    category TEXT,
    notes TEXT,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- RFIs
CREATE TABLE IF NOT EXISTS rfis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id),
    external_id TEXT,
    rfi_number INTEGER NOT NULL,
    subject TEXT NOT NULL,
    question TEXT NOT NULL,
    answer TEXT,
    status TEXT NOT NULL DEFAULT 'open'
      CHECK (status IN ('draft','open','answered','closed','void')),
    priority TEXT DEFAULT 'normal'
      CHECK (priority IN ('low','normal','high','urgent')),
    cost_impact BOOLEAN DEFAULT FALSE,
    cost_impact_amount NUMERIC(15,2),
    schedule_impact BOOLEAN DEFAULT FALSE,
    schedule_impact_days INTEGER,
    assigned_to TEXT,
    ball_in_court TEXT,
    due_date DATE,
    responded_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(project_id, rfi_number)
);

-- Change Orders
CREATE TABLE IF NOT EXISTS change_orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id),
    external_id TEXT,
    co_number INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    reason TEXT CHECK (reason IN (
      'owner_request','design_error','unforeseen_condition',
      'code_change','value_engineering','other'
    )),
    status TEXT NOT NULL DEFAULT 'pending'
      CHECK (status IN ('draft','pending','approved','rejected','void')),
    cost_amount NUMERIC(15,2) NOT NULL,
    schedule_days INTEGER DEFAULT 0,
    markup_amount NUMERIC(15,2),
    total_with_markup NUMERIC(15,2),
    related_rfi_id UUID REFERENCES rfis(id),
    submitted_date DATE,
    approved_date DATE,
    approved_by TEXT,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(project_id, co_number)
);

-- Daily Logs
CREATE TABLE IF NOT EXISTS daily_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id),
    log_date DATE NOT NULL,
    weather_conditions TEXT,
    temperature_high INTEGER,
    temperature_low INTEGER,
    wind_speed TEXT,
    precipitation TEXT,
    workers_on_site JSONB DEFAULT '[]',
    total_headcount INTEGER,
    equipment_on_site JSONB DEFAULT '[]',
    work_performed TEXT,
    materials_received TEXT,
    visitors JSONB DEFAULT '[]',
    safety_incidents JSONB DEFAULT '[]',
    delays TEXT,
    delay_hours NUMERIC(5,1),
    photos JSONB DEFAULT '[]',
    notes TEXT,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(project_id, log_date)
);

-- Budget Lines
CREATE TABLE IF NOT EXISTS budget_lines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id),
    cost_code TEXT NOT NULL,
    description TEXT NOT NULL,
    original_budget NUMERIC(15,2) NOT NULL,
    approved_changes NUMERIC(15,2) DEFAULT 0,
    revised_budget NUMERIC(15,2) GENERATED ALWAYS AS (original_budget + approved_changes) STORED,
    committed_costs NUMERIC(15,2) DEFAULT 0,
    actual_costs NUMERIC(15,2) DEFAULT 0,
    estimated_cost_to_complete NUMERIC(15,2),
    estimated_cost_at_completion NUMERIC(15,2),
    variance NUMERIC(15,2) GENERATED ALWAYS AS (original_budget + approved_changes - actual_costs) STORED,
    percent_complete NUMERIC(5,2),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(project_id, cost_code)
);

-- Schedule Tasks
CREATE TABLE IF NOT EXISTS schedule_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id),
    external_id TEXT,
    task_name TEXT NOT NULL,
    wbs_code TEXT,
    start_date DATE, end_date DATE,
    actual_start DATE, actual_end DATE,
    duration_days INTEGER,
    percent_complete NUMERIC(5,2) DEFAULT 0,
    predecessor_ids UUID[],
    successor_ids UUID[],
    is_critical_path BOOLEAN DEFAULT FALSE,
    total_float_days INTEGER,
    free_float_days INTEGER,
    assigned_to TEXT,
    status TEXT DEFAULT 'not_started'
      CHECK (status IN ('not_started','in_progress','complete','delayed')),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Subcontractors
CREATE TABLE IF NOT EXISTS subcontractors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    company_name TEXT NOT NULL,
    contact_name TEXT, email TEXT, phone TEXT,
    trade TEXT NOT NULL,
    license_number TEXT, license_state TEXT,
    insurance_expiry DATE,
    bonding_capacity NUMERIC(15,2),
    prequalification_status TEXT DEFAULT 'pending',
    average_rating NUMERIC(3,2),
    total_projects INTEGER DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Subcontractor Bids
CREATE TABLE IF NOT EXISTS subcontractor_bids (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id),
    subcontractor_id UUID NOT NULL REFERENCES subcontractors(id),
    scope_description TEXT NOT NULL,
    bid_amount NUMERIC(15,2) NOT NULL,
    alternates JSONB DEFAULT '[]',
    exclusions TEXT, inclusions TEXT,
    validity_days INTEGER DEFAULT 30,
    status TEXT DEFAULT 'received'
      CHECK (status IN ('invited','received','under_review','accepted','rejected')),
    submitted_at TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Safety Incidents
CREATE TABLE IF NOT EXISTS safety_incidents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id),
    incident_date TIMESTAMPTZ NOT NULL,
    incident_type TEXT NOT NULL CHECK (incident_type IN (
      'near_miss','first_aid','recordable','lost_time',
      'fatality','property_damage','environmental'
    )),
    severity TEXT NOT NULL CHECK (severity IN ('low','medium','high','critical')),
    description TEXT NOT NULL,
    location_on_site TEXT,
    persons_involved JSONB DEFAULT '[]',
    root_cause TEXT,
    corrective_actions TEXT,
    osha_recordable BOOLEAN DEFAULT FALSE,
    osha_report_number TEXT,
    days_away INTEGER DEFAULT 0,
    status TEXT DEFAULT 'open'
      CHECK (status IN ('open','investigating','corrective_action','closed')),
    reported_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Usage Logs (billing audit trail)
CREATE TABLE IF NOT EXISTS usage_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    user_id UUID NOT NULL REFERENCES users(id),
    tool_name TEXT NOT NULL,
    project_id UUID REFERENCES projects(id),
    duration_ms INTEGER,
    success BOOLEAN NOT NULL,
    error_code TEXT,
    stripe_meter_event_id TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_projects_org ON projects(org_id);
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(org_id, status);
CREATE INDEX IF NOT EXISTS idx_rfis_project ON rfis(project_id);
CREATE INDEX IF NOT EXISTS idx_rfis_status ON rfis(project_id, status);
CREATE INDEX IF NOT EXISTS idx_change_orders_project ON change_orders(project_id);
CREATE INDEX IF NOT EXISTS idx_daily_logs_project_date ON daily_logs(project_id, log_date DESC);
CREATE INDEX IF NOT EXISTS idx_budget_lines_project ON budget_lines(project_id);
CREATE INDEX IF NOT EXISTS idx_schedule_tasks_project ON schedule_tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_estimate_items_estimate ON estimate_line_items(estimate_id);
CREATE INDEX IF NOT EXISTS idx_usage_logs_org ON usage_logs(org_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_usage_logs_tool ON usage_logs(tool_name, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_subcontractor_bids_project ON subcontractor_bids(project_id);
CREATE INDEX IF NOT EXISTS idx_safety_incidents_project ON safety_incidents(project_id);
