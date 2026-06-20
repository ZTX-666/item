import {
  pgTable,
  uuid,
  text,
  timestamp,
  boolean,
  integer,
  numeric,
  jsonb,
  date,
  uniqueIndex,
  index,
} from 'drizzle-orm/pg-core';
import { sql } from 'drizzle-orm';

// ── Organizations (multi-tenant) ──────────────────────────────────────────

export const organizations = pgTable('organizations', {
  id: uuid('id').primaryKey().defaultRandom(),
  name: text('name').notNull(),
  slug: text('slug').unique().notNull(),
  stripeCustomerId: text('stripe_customer_id').unique(),
  stripeSubscriptionId: text('stripe_subscription_id'),
  plan: text('plan').notNull().default('starter'),
  subscriptionStatus: text('subscription_status').notNull().default('trialing'),
  trialEndsAt: timestamp('trial_ends_at', { withTimezone: true }),
  settings: jsonb('settings').default({}),
  createdAt: timestamp('created_at', { withTimezone: true }).defaultNow(),
  updatedAt: timestamp('updated_at', { withTimezone: true }).defaultNow(),
});

// ── Users ─────────────────────────────────────────────────────────────────

export const users = pgTable(
  'users',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    orgId: uuid('org_id')
      .notNull()
      .references(() => organizations.id),
    email: text('email').notNull(),
    name: text('name').notNull(),
    passwordHash: text('password_hash'),
    role: text('role').notNull().default('member'),
    createdAt: timestamp('created_at', { withTimezone: true }).defaultNow(),
  },
  (table) => ({
    orgEmailIdx: uniqueIndex('users_org_email_idx').on(table.orgId, table.email),
  }),
);

// ── OAuth Clients ─────────────────────────────────────────────────────────

export const oauthClients = pgTable('oauth_clients', {
  id: uuid('id').primaryKey().defaultRandom(),
  clientId: text('client_id').unique().notNull(),
  clientSecretHash: text('client_secret_hash'),
  clientName: text('client_name').notNull(),
  redirectUris: text('redirect_uris').array().notNull(),
  grantTypes: text('grant_types')
    .array()
    .notNull()
    .default(sql`ARRAY['authorization_code']`),
  scope: text('scope'),
  createdAt: timestamp('created_at', { withTimezone: true }).defaultNow(),
});

// ── Authorization Codes ───────────────────────────────────────────────────

export const authorizationCodes = pgTable('authorization_codes', {
  id: uuid('id').primaryKey().defaultRandom(),
  code: text('code').unique().notNull(),
  clientId: text('client_id')
    .notNull()
    .references(() => oauthClients.clientId),
  userId: uuid('user_id')
    .notNull()
    .references(() => users.id),
  redirectUri: text('redirect_uri').notNull(),
  scope: text('scope').notNull(),
  codeChallenge: text('code_challenge').notNull(),
  codeChallengeMethod: text('code_challenge_method').notNull().default('S256'),
  used: boolean('used').default(false),
  expiresAt: timestamp('expires_at', { withTimezone: true }).notNull(),
  createdAt: timestamp('created_at', { withTimezone: true }).defaultNow(),
});

// ── Refresh Tokens ────────────────────────────────────────────────────────

export const refreshTokens = pgTable('refresh_tokens', {
  id: uuid('id').primaryKey().defaultRandom(),
  tokenHash: text('token_hash').unique().notNull(),
  userId: uuid('user_id')
    .notNull()
    .references(() => users.id),
  clientId: text('client_id')
    .notNull()
    .references(() => oauthClients.clientId),
  scope: text('scope').notNull(),
  revoked: boolean('revoked').default(false),
  expiresAt: timestamp('expires_at', { withTimezone: true }).notNull(),
  createdAt: timestamp('created_at', { withTimezone: true }).defaultNow(),
});

// ── Integrations ──────────────────────────────────────────────────────────

export const integrations = pgTable(
  'integrations',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    orgId: uuid('org_id')
      .notNull()
      .references(() => organizations.id),
    provider: text('provider').notNull(),
    accessTokenEncrypted: text('access_token_encrypted'),
    refreshTokenEncrypted: text('refresh_token_encrypted'),
    tokenExpiresAt: timestamp('token_expires_at', { withTimezone: true }),
    externalCompanyId: text('external_company_id'),
    settings: jsonb('settings').default({}),
    status: text('status').notNull().default('active'),
    createdAt: timestamp('created_at', { withTimezone: true }).defaultNow(),
    updatedAt: timestamp('updated_at', { withTimezone: true }).defaultNow(),
  },
  (table) => ({
    orgProviderIdx: uniqueIndex('integrations_org_provider_idx').on(
      table.orgId,
      table.provider,
    ),
  }),
);

// ── Projects ──────────────────────────────────────────────────────────────

export const projects = pgTable(
  'projects',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    orgId: uuid('org_id')
      .notNull()
      .references(() => organizations.id),
    externalId: text('external_id'),
    integrationId: uuid('integration_id').references(() => integrations.id),
    name: text('name').notNull(),
    projectNumber: text('project_number'),
    address: text('address'),
    city: text('city'),
    state: text('state'),
    zip: text('zip'),
    projectType: text('project_type'),
    contractType: text('contract_type'),
    contractAmount: numeric('contract_amount', { precision: 15, scale: 2 }),
    startDate: date('start_date'),
    estimatedCompletion: date('estimated_completion'),
    actualCompletion: date('actual_completion'),
    status: text('status').notNull().default('active'),
    ownerName: text('owner_name'),
    architectName: text('architect_name'),
    superintendent: text('superintendent'),
    projectManager: text('project_manager'),
    metadata: jsonb('metadata').default({}),
    createdAt: timestamp('created_at', { withTimezone: true }).defaultNow(),
    updatedAt: timestamp('updated_at', { withTimezone: true }).defaultNow(),
  },
  (table) => ({
    orgIdx: index('idx_projects_org').on(table.orgId),
    statusIdx: index('idx_projects_status').on(table.orgId, table.status),
  }),
);

// ── Estimates ─────────────────────────────────────────────────────────────

export const estimates = pgTable('estimates', {
  id: uuid('id').primaryKey().defaultRandom(),
  projectId: uuid('project_id')
    .notNull()
    .references(() => projects.id),
  name: text('name').notNull(),
  version: integer('version').notNull().default(1),
  status: text('status').notNull().default('draft'),
  totalAmount: numeric('total_amount', { precision: 15, scale: 2 }),
  markupPercentage: numeric('markup_percentage', { precision: 5, scale: 2 }),
  contingencyPercentage: numeric('contingency_percentage', {
    precision: 5,
    scale: 2,
  }),
  notes: text('notes'),
  createdBy: uuid('created_by').references(() => users.id),
  approvedBy: uuid('approved_by').references(() => users.id),
  approvedAt: timestamp('approved_at', { withTimezone: true }),
  createdAt: timestamp('created_at', { withTimezone: true }).defaultNow(),
  updatedAt: timestamp('updated_at', { withTimezone: true }).defaultNow(),
});

// ── Estimate Line Items ───────────────────────────────────────────────────

export const estimateLineItems = pgTable(
  'estimate_line_items',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    estimateId: uuid('estimate_id')
      .notNull()
      .references(() => estimates.id, { onDelete: 'cascade' }),
    costCode: text('cost_code').notNull(),
    description: text('description').notNull(),
    quantity: numeric('quantity', { precision: 12, scale: 3 }),
    unit: text('unit'),
    unitCost: numeric('unit_cost', { precision: 12, scale: 4 }),
    totalCost: numeric('total_cost', { precision: 15, scale: 2 }),
    laborCost: numeric('labor_cost', { precision: 15, scale: 2 }),
    materialCost: numeric('material_cost', { precision: 15, scale: 2 }),
    equipmentCost: numeric('equipment_cost', { precision: 15, scale: 2 }),
    subcontractorCost: numeric('subcontractor_cost', { precision: 15, scale: 2 }),
    category: text('category'),
    notes: text('notes'),
    sortOrder: integer('sort_order').default(0),
    createdAt: timestamp('created_at', { withTimezone: true }).defaultNow(),
  },
  (table) => ({
    estimateIdx: index('idx_estimate_items_estimate').on(table.estimateId),
  }),
);

// ── RFIs ──────────────────────────────────────────────────────────────────

export const rfis = pgTable(
  'rfis',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    projectId: uuid('project_id')
      .notNull()
      .references(() => projects.id),
    externalId: text('external_id'),
    rfiNumber: integer('rfi_number').notNull(),
    subject: text('subject').notNull(),
    question: text('question').notNull(),
    answer: text('answer'),
    status: text('status').notNull().default('open'),
    priority: text('priority').default('normal'),
    costImpact: boolean('cost_impact').default(false),
    costImpactAmount: numeric('cost_impact_amount', { precision: 15, scale: 2 }),
    scheduleImpact: boolean('schedule_impact').default(false),
    scheduleImpactDays: integer('schedule_impact_days'),
    assignedTo: text('assigned_to'),
    ballInCourt: text('ball_in_court'),
    dueDate: date('due_date'),
    respondedAt: timestamp('responded_at', { withTimezone: true }),
    closedAt: timestamp('closed_at', { withTimezone: true }),
    createdBy: uuid('created_by').references(() => users.id),
    createdAt: timestamp('created_at', { withTimezone: true }).defaultNow(),
    updatedAt: timestamp('updated_at', { withTimezone: true }).defaultNow(),
  },
  (table) => ({
    projectIdx: index('idx_rfis_project').on(table.projectId),
    statusIdx: index('idx_rfis_status').on(table.projectId, table.status),
    projectRfiIdx: uniqueIndex('rfis_project_rfi_number_idx').on(
      table.projectId,
      table.rfiNumber,
    ),
  }),
);

// ── Change Orders ─────────────────────────────────────────────────────────

export const changeOrders = pgTable(
  'change_orders',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    projectId: uuid('project_id')
      .notNull()
      .references(() => projects.id),
    externalId: text('external_id'),
    coNumber: integer('co_number').notNull(),
    title: text('title').notNull(),
    description: text('description'),
    reason: text('reason'),
    status: text('status').notNull().default('pending'),
    costAmount: numeric('cost_amount', { precision: 15, scale: 2 }).notNull(),
    scheduleDays: integer('schedule_days').default(0),
    markupAmount: numeric('markup_amount', { precision: 15, scale: 2 }),
    totalWithMarkup: numeric('total_with_markup', { precision: 15, scale: 2 }),
    relatedRfiId: uuid('related_rfi_id').references(() => rfis.id),
    submittedDate: date('submitted_date'),
    approvedDate: date('approved_date'),
    approvedBy: text('approved_by'),
    createdBy: uuid('created_by').references(() => users.id),
    createdAt: timestamp('created_at', { withTimezone: true }).defaultNow(),
    updatedAt: timestamp('updated_at', { withTimezone: true }).defaultNow(),
  },
  (table) => ({
    projectIdx: index('idx_change_orders_project').on(table.projectId),
    projectCoIdx: uniqueIndex('change_orders_project_co_number_idx').on(
      table.projectId,
      table.coNumber,
    ),
  }),
);

// ── Daily Logs ────────────────────────────────────────────────────────────

export const dailyLogs = pgTable(
  'daily_logs',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    projectId: uuid('project_id')
      .notNull()
      .references(() => projects.id),
    logDate: date('log_date').notNull(),
    weatherConditions: text('weather_conditions'),
    temperatureHigh: integer('temperature_high'),
    temperatureLow: integer('temperature_low'),
    windSpeed: text('wind_speed'),
    precipitation: text('precipitation'),
    workersOnSite: jsonb('workers_on_site').default([]),
    totalHeadcount: integer('total_headcount'),
    equipmentOnSite: jsonb('equipment_on_site').default([]),
    workPerformed: text('work_performed'),
    materialsReceived: text('materials_received'),
    visitors: jsonb('visitors').default([]),
    safetyIncidents: jsonb('safety_incidents').default([]),
    delays: text('delays'),
    delayHours: numeric('delay_hours', { precision: 5, scale: 1 }),
    photos: jsonb('photos').default([]),
    notes: text('notes'),
    createdBy: uuid('created_by').references(() => users.id),
    createdAt: timestamp('created_at', { withTimezone: true }).defaultNow(),
    updatedAt: timestamp('updated_at', { withTimezone: true }).defaultNow(),
  },
  (table) => ({
    projectDateIdx: index('idx_daily_logs_project_date').on(table.projectId, table.logDate),
    projectLogDateIdx: uniqueIndex('daily_logs_project_log_date_idx').on(
      table.projectId,
      table.logDate,
    ),
  }),
);

// ── Budget Lines ──────────────────────────────────────────────────────────

export const budgetLines = pgTable(
  'budget_lines',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    projectId: uuid('project_id')
      .notNull()
      .references(() => projects.id),
    costCode: text('cost_code').notNull(),
    description: text('description').notNull(),
    originalBudget: numeric('original_budget', { precision: 15, scale: 2 }).notNull(),
    approvedChanges: numeric('approved_changes', { precision: 15, scale: 2 }).default('0'),
    revisedBudget: numeric('revised_budget', { precision: 15, scale: 2 }),
    committedCosts: numeric('committed_costs', { precision: 15, scale: 2 }).default('0'),
    actualCosts: numeric('actual_costs', { precision: 15, scale: 2 }).default('0'),
    estimatedCostToComplete: numeric('estimated_cost_to_complete', {
      precision: 15,
      scale: 2,
    }),
    estimatedCostAtCompletion: numeric('estimated_cost_at_completion', {
      precision: 15,
      scale: 2,
    }),
    variance: numeric('variance', { precision: 15, scale: 2 }),
    percentComplete: numeric('percent_complete', { precision: 5, scale: 2 }),
    createdAt: timestamp('created_at', { withTimezone: true }).defaultNow(),
    updatedAt: timestamp('updated_at', { withTimezone: true }).defaultNow(),
  },
  (table) => ({
    projectIdx: index('idx_budget_lines_project').on(table.projectId),
    projectCostCodeIdx: uniqueIndex('budget_lines_project_cost_code_idx').on(
      table.projectId,
      table.costCode,
    ),
  }),
);

// ── Schedule Tasks ────────────────────────────────────────────────────────

export const scheduleTasks = pgTable(
  'schedule_tasks',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    projectId: uuid('project_id')
      .notNull()
      .references(() => projects.id),
    externalId: text('external_id'),
    taskName: text('task_name').notNull(),
    wbsCode: text('wbs_code'),
    startDate: date('start_date'),
    endDate: date('end_date'),
    actualStart: date('actual_start'),
    actualEnd: date('actual_end'),
    durationDays: integer('duration_days'),
    percentComplete: numeric('percent_complete', { precision: 5, scale: 2 }).default('0'),
    predecessorIds: uuid('predecessor_ids').array(),
    successorIds: uuid('successor_ids').array(),
    isCriticalPath: boolean('is_critical_path').default(false),
    totalFloatDays: integer('total_float_days'),
    freeFloatDays: integer('free_float_days'),
    assignedTo: text('assigned_to'),
    status: text('status').default('not_started'),
    notes: text('notes'),
    createdAt: timestamp('created_at', { withTimezone: true }).defaultNow(),
    updatedAt: timestamp('updated_at', { withTimezone: true }).defaultNow(),
  },
  (table) => ({
    projectIdx: index('idx_schedule_tasks_project').on(table.projectId),
  }),
);

// ── Subcontractors ────────────────────────────────────────────────────────

export const subcontractors = pgTable('subcontractors', {
  id: uuid('id').primaryKey().defaultRandom(),
  orgId: uuid('org_id')
    .notNull()
    .references(() => organizations.id),
  companyName: text('company_name').notNull(),
  contactName: text('contact_name'),
  email: text('email'),
  phone: text('phone'),
  trade: text('trade').notNull(),
  licenseNumber: text('license_number'),
  licenseState: text('license_state'),
  insuranceExpiry: date('insurance_expiry'),
  bondingCapacity: numeric('bonding_capacity', { precision: 15, scale: 2 }),
  prequalificationStatus: text('prequalification_status').default('pending'),
  averageRating: numeric('average_rating', { precision: 3, scale: 2 }),
  totalProjects: integer('total_projects').default(0),
  notes: text('notes'),
  createdAt: timestamp('created_at', { withTimezone: true }).defaultNow(),
  updatedAt: timestamp('updated_at', { withTimezone: true }).defaultNow(),
});

// ── Subcontractor Bids ────────────────────────────────────────────────────

export const subcontractorBids = pgTable(
  'subcontractor_bids',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    projectId: uuid('project_id')
      .notNull()
      .references(() => projects.id),
    subcontractorId: uuid('subcontractor_id')
      .notNull()
      .references(() => subcontractors.id),
    scopeDescription: text('scope_description').notNull(),
    bidAmount: numeric('bid_amount', { precision: 15, scale: 2 }).notNull(),
    alternates: jsonb('alternates').default([]),
    exclusions: text('exclusions'),
    inclusions: text('inclusions'),
    validityDays: integer('validity_days').default(30),
    status: text('status').default('received'),
    submittedAt: timestamp('submitted_at', { withTimezone: true }),
    notes: text('notes'),
    createdAt: timestamp('created_at', { withTimezone: true }).defaultNow(),
  },
  (table) => ({
    projectIdx: index('idx_subcontractor_bids_project').on(table.projectId),
  }),
);

// ── Safety Incidents ──────────────────────────────────────────────────────

export const safetyIncidents = pgTable(
  'safety_incidents',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    projectId: uuid('project_id')
      .notNull()
      .references(() => projects.id),
    incidentDate: timestamp('incident_date', { withTimezone: true }).notNull(),
    incidentType: text('incident_type').notNull(),
    severity: text('severity').notNull(),
    description: text('description').notNull(),
    locationOnSite: text('location_on_site'),
    personsInvolved: jsonb('persons_involved').default([]),
    rootCause: text('root_cause'),
    correctiveActions: text('corrective_actions'),
    oshaRecordable: boolean('osha_recordable').default(false),
    oshaReportNumber: text('osha_report_number'),
    daysAway: integer('days_away').default(0),
    status: text('status').default('open'),
    reportedBy: uuid('reported_by').references(() => users.id),
    createdAt: timestamp('created_at', { withTimezone: true }).defaultNow(),
    updatedAt: timestamp('updated_at', { withTimezone: true }).defaultNow(),
  },
  (table) => ({
    projectIdx: index('idx_safety_incidents_project').on(table.projectId),
  }),
);

// ── Usage Logs ────────────────────────────────────────────────────────────

export const usageLogs = pgTable(
  'usage_logs',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    orgId: uuid('org_id')
      .notNull()
      .references(() => organizations.id),
    userId: uuid('user_id')
      .notNull()
      .references(() => users.id),
    toolName: text('tool_name').notNull(),
    projectId: uuid('project_id').references(() => projects.id),
    durationMs: integer('duration_ms'),
    success: boolean('success').notNull(),
    errorCode: text('error_code'),
    stripeMeterEventId: text('stripe_meter_event_id'),
    metadata: jsonb('metadata').default({}),
    createdAt: timestamp('created_at', { withTimezone: true }).defaultNow(),
  },
  (table) => ({
    orgIdx: index('idx_usage_logs_org').on(table.orgId, table.createdAt),
    toolIdx: index('idx_usage_logs_tool').on(table.toolName, table.createdAt),
  }),
);
