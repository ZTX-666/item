export type RiskLevel = 'low' | 'medium' | 'high' | 'critical'

export interface StatusMetric {
  id: string
  label: string
  value: string | number
  tone: 'red' | 'orange' | 'green' | 'blue' | 'gray'
  helper: string
}

export interface HazardCase {
  id: string
  title: string
  area: string
  riskLevel: RiskLevel
  status: string
  dueText: string
}

export interface SafetyCaseRecord {
  id: number
  status?: string
  source_type?: string
  scene?: string
  risk_level?: RiskLevel | string
  area?: string
  contractor?: string
  description?: string
  recommended_action?: string
  created_at?: string
  updated_at?: string
}

export interface WorkflowStep {
  id: string
  label: string
  status: 'done' | 'active' | 'pending'
}

export interface ActivityItem {
  id: string
  time: string
  title: string
  description: string
  actionLabel?: string
}

export interface WorkbenchStatus {
  center_ok: boolean
  toolbox_ok: boolean
  toolbox_base_url: string
  llm_configured: boolean
}

export interface WorkbenchSummary {
  status: WorkbenchStatus
  metrics: StatusMetric[]
  hazards: HazardCase[]
  activities: ActivityItem[]
  workflow_steps: WorkflowStep[]
}

export interface PendingConfirmation {
  confirmation_id: string
  action_type: string
  title: string
  summary?: string
  status: string
  risk_level?: RiskLevel | string
  source_channel?: string
  source_user_id?: string
  payload?: Record<string, unknown>
  created_at?: string
  updated_at?: string
}

export interface LongTermMemoryDocument {
  ok: boolean
  content: string
  path: string
  updated_at?: string
  audit_id?: string
}

export interface LongTermMemorySummaryResult {
  ok: boolean
  message: string
  summary: string
  message_count: number
  audit_id?: string
  memory?: LongTermMemoryDocument
}

export interface ChatResponse {
  type: 'reply' | 'review_card' | 'workflow'
  message: string
  sessionId?: string
  workflowId?: string
  payload?: {
    intent?: ChatIntentResult
    cards: Array<Record<string, unknown>>
    toolResults: Array<Record<string, unknown>>
    auditId?: string
    sessionId?: string
    workflowName?: string
    workflowRunId?: string
    skill?: ChatSkillReference | null
    appliedSkill?: ChatAppliedSkill | null
    agentTrace?: AgentTraceItem[]
    richBlocks?: Array<Record<string, unknown>>
  }
}

export interface ChatIntentResult {
  intent: string
  confidence: number
  reason: string
  suggested_tools?: string[]
}

export interface ChatSkillReference {
  name: string
  path?: string
  summary?: string
  enabled?: boolean
  category?: string
  status?: string
  phase?: string
  tools?: string[]
  workflow?: string
  config?: Record<string, unknown>
}

export interface ChatAppliedSkill {
  skill?: string
  skill_path?: string
  reply?: string
  highlights?: string[]
  next_actions?: string[]
}

export interface AgentTraceItem {
  stage: string
  status: string
  title: string
  detail?: string
}

export interface CenterChatResponse {
  reply: string
  session_id?: string
  intent?: ChatIntentResult
  cards?: Array<Record<string, unknown>>
  tool_results?: Array<Record<string, unknown>>
  applied_skill?: ChatAppliedSkill | null
  agent_trace?: AgentTraceItem[]
  skill?: ChatSkillReference | null
  workflow_name?: string
  workflow_run_id?: string
  audit_id?: string
  rich_blocks?: Array<Record<string, unknown>>
}

export interface ChatSessionRecord {
  session_id: string
  title: string
  channel: string
  user_id: string
  route?: string
  module?: string
  metadata?: Record<string, unknown>
  created_at: string
  updated_at: string
  message_count: number
}

export interface ChatMessageRecord {
  message_id: string
  session_id: string
  role: 'user' | 'assistant'
  content: string
  status?: string
  intent?: ChatIntentResult | Record<string, unknown>
  tool_results?: Array<Record<string, unknown>>
  cards?: Array<Record<string, unknown>>
  metadata?: {
    applied_skill?: ChatAppliedSkill
    skill?: ChatSkillReference
    workflow_name?: string
    [key: string]: unknown
  }
  audit_id?: string
  workflow_run_id?: string
  created_at: string
}

export interface ChatHistoryResponse {
  session: ChatSessionRecord | null
  messages: ChatMessageRecord[]
}

export type DocumentDiffLineType = 'context' | 'added' | 'removed'

export interface DocumentDiffLine {
  id: string
  type: DocumentDiffLineType
  text: string
}

export interface DocumentRevisionPreview {
  id: string
  title: string
  source: string
  instruction: string
  additions: number
  deletions: number
  status: 'draft' | 'accepted' | 'rejected'
  llm?: Record<string, unknown>
  lines: DocumentDiffLine[]
}

export interface SmartFormTemplate {
  id: string
  title?: string
  policy_context?: string
  docx_path?: string
}

export interface SmartFormDraft {
  ok: boolean
  message: string
  requires_acceptance: boolean
  templates: SmartFormTemplate[]
  selected_template?: SmartFormTemplate
  prefill?: {
    fields: Record<string, unknown>
  }
  docx_draft?: {
    output_path?: string
    payload_path?: string
    files?: Array<Record<string, unknown>>
  }
  revision_preview?: DocumentRevisionPreview
  accept_payload?: {
    template_id: string
    fields: Record<string, unknown>
    output_path?: string
    case_id?: number | null
  }
}

export interface VisualPatrolCandidate {
  id: string
  title: string
  risk_level: RiskLevel
  area: string
  description: string
  labels: string[]
  task_id?: string
  source_mix?: string
  severity?: string
  suggested_action?: string
  detection_details?: Array<{
    bbox: number[]
    label: string
    confidence: number
    source: string
    description?: string
    severity?: string
    suggested_action?: string
  }>
}

export interface VisualPatrolDraft {
  ok: boolean
  message: string
  requires_confirmation: boolean
  source?: string
  patrol_id?: string
  camera_id?: string
  camera_name?: string
  snapshot_url?: string
  annotated_url?: string
  snapshot?: Record<string, unknown> | null
  vlm?: Record<string, unknown> | null
  candidates: VisualPatrolCandidate[]
  confirm_payload?: Record<string, unknown>
  analysis_mode?: string
  report?: PatrolRunReport
}

export interface PatrolRunSummary {
  patrol_id: string
  timestamp?: string
  camera_count?: number
  success_count?: number
  total_detections?: number
  high_risk_count?: number
  hybrid_cameras?: number
  vlm_enabled?: boolean
}

export interface PatrolCameraResult {
  camera_id: string
  camera_name: string
  area: string
  success: boolean
  snapshot_path?: string | null
  annotated_path?: string | null
  snapshot_url?: string
  annotated_url?: string
  detection_count?: number
  detections?: Array<Record<string, unknown>>
  error?: string
  yolo_time_ms?: number
  vlm_time_ms?: number
  source_mix?: string
}

export interface PatrolRunReport {
  patrol_id: string
  timestamp?: string
  camera_count?: number
  success_count?: number
  fail_count?: number
  total_detections?: number
  hybrid_cameras?: number
  high_risk_count?: number
  vlm_enabled?: boolean
  cameras?: PatrolCameraResult[]
  output_dir?: string
}

export interface WorkbenchVideoDetectionSummary {
  title: string
  text: string
  severity: RiskLevel | string
  detection_count: number
  labels: string[]
  suggested_action?: string
  camera_names?: string[]
}

export interface WorkbenchVideoDetectionCameraReport {
  camera_id: string
  camera_name: string
  area?: string
  success?: boolean
  patrol_id?: string
  snapshot_url?: string
  annotated_url?: string
  snapshot_path?: string
  annotated_path?: string
  detections?: Array<Record<string, unknown>>
  summary?: WorkbenchVideoDetectionSummary
  error?: string
  snapshot_source?: 'stream' | 'fallback' | 'failed' | string
  fallback_used?: boolean
  fallback_image?: string
  fallback_reason?: string
}

export interface WorkbenchVideoDetectionReport {
  ok: boolean
  report_id: string
  created_at: string
  direction: string
  refined_prompt: string
  prompt_source?: string
  policy_context?: string[]
  camera_id: string
  camera_name: string
  camera_ids?: string[]
  camera_names?: string[]
  camera_count?: number
  area?: string
  patrol_id?: string
  snapshot_url?: string
  annotated_url?: string
  snapshot_path?: string
  annotated_path?: string
  snapshot_source?: 'stream' | 'fallback' | 'failed' | string
  fallback_used?: boolean
  fallback_image?: string
  fallback_reason?: string
  summary: WorkbenchVideoDetectionSummary
  detections?: Array<Record<string, unknown>>
  cameras?: WorkbenchVideoDetectionCameraReport[]
  camera_errors?: Array<Record<string, string>>
  patrol_report?: PatrolRunReport
  patrol_reports?: PatrolRunReport[]
  error?: string
  message?: string
}

export interface WorkbenchVideoDetectionPrompt {
  ok: boolean
  detection_direction?: string
  camera_ids?: string[]
  camera_names?: string[]
  refined_prompt?: string
  prompt_source?: string
  policy_context?: string[]
  focus_items?: string[]
  risk_keywords?: string[]
  error?: string
  message?: string
}

export interface LlmSettingsStatus {
  configured: boolean
  base_url: string
  model: string
  api_key_masked: string
}

export interface LlmTestResult {
  ok: boolean
  message: string
  model: string
  raw_keys?: string[]
}

export interface ConnectorSettingsStatus {
  whatsapp: {
    configured: boolean
    archive_base_url: string
  }
  feishu: {
    configured: boolean
    webhook_configured: boolean
    app_id: string
    app_secret_masked: string
    webhook_url: string
    webhook_secret_masked: string
    verification_token_masked: string
    encrypt_key_masked: string
    api_base_url: string
  }
  requires_toolbox_restart: boolean
}

export interface RuntimeComponentStatus {
  name: string
  ok: boolean
  path?: string
  url?: string
  configured?: boolean
  error?: string
}

export interface RuntimeStatus {
  center: {
    ok: boolean
    service: string
    url: string
  }
  llm: LlmSettingsStatus
  toolbox: {
    ok: boolean
    base_url: string
    raw_ok: boolean
    required: RuntimeComponentStatus[]
    optional: RuntimeComponentStatus[]
  }
  ready: boolean
}

export interface JobRun {
  job_id: string
  job_type: string
  title: string
  status: 'queued' | 'running' | 'success' | 'failed' | string
  progress: number
  source_module?: string
  request?: Record<string, unknown>
  result?: Record<string, unknown>
  error?: string | null
  created_at: string
  started_at?: string | null
  finished_at?: string | null
  updated_at: string
}

export interface TaskEvent {
  event_id: string
  job_id: string
  event_type: string
  message?: string
  progress?: number | null
  payload?: Record<string, unknown>
  created_at: string
}

export interface JobStats {
  ok: boolean
  total: number
  by_status: Record<string, number>
  by_module: Record<string, number>
  by_type: Record<string, number>
}

export interface SystemDiagnostics {
  ok: boolean
  center: Record<string, unknown>
  agent_toolbox: Record<string, unknown>
  external_monitor: ExternalMonitorStatus
  jobs: {
    ok: boolean
    recent_count: number
    recent: JobRun[]
  }
  assets: {
    ok: boolean
    recent_count: number
    recent: Array<Record<string, unknown>>
  }
  rag: Record<string, unknown>
  dependencies: Record<string, unknown>
}

export interface CameraConfig {
  id: string
  name: string
  area: string
  rtmp_url?: string | null
  enabled: boolean
}

export interface ContractorConfig {
  id: string
  name: string
  contact?: string | null
  channel?: string | null
  default_due_days: number
}

export interface AppConfig {
  project: {
    name: string
    default_area: string
    location: string
  }
  cameras: CameraConfig[]
  contractors: ContractorConfig[]
}

export interface NotificationDraft {
  caseId: string
  contractor: string
  contact?: string | null
  channel?: string | null
  draftText: string
  status: 'draft' | 'confirmed'
}

export interface ExternalRiskBriefing {
  title: string
  summary: string
  items: string[]
}

export interface GeneratedOutputItem {
  id: string
  title: string
  kind: 'docx' | 'payload' | 'image' | 'report' | 'notification' | 'other'
  path?: string
  content?: string
  createdAt: string
}

export interface GeneratedReport {
  ok: boolean
  message: string
  report_type: 'community' | 'daily_safety' | 'rectification'
  output_path?: string
  files?: Array<Record<string, unknown>>
}

export interface HybridAction {
  action_id: string
  sequence_no: number
  tool_name: string
  payload: Record<string, unknown>
  risk_level: 'low' | 'medium' | 'high' | 'critical'
  requires_confirmation: boolean
  status: string
  retry_count: number
  max_retries: number
  result?: Record<string, unknown>
  last_error?: string | null
}

export interface HybridPlan {
  plan_id: string
  session_id: string
  user_input: string
  workflow: string
  planner_mode: string
  status: string
  fallback_used: boolean
  fallback_reason?: string | null
  selected_action_ids: string[]
  idempotency_key?: string | null
  result?: Record<string, unknown>
  last_error?: string | null
  actions: HybridAction[]
}

// ── DocMate (闪闪文档) 类型 ──────────────────────────────────────

export interface DocmateDocumentStructure {
  doc_id?: string
  source_path?: string
  filename?: string
  stats: {
    paragraph_count: number
    table_count: number
    image_count: number
    total_chars?: number
  }
  structure: {
    paragraphs: Array<{
      index: number
      text: string
      style: string
      type: string
    }>
    tables: Array<{
      index: number
      rows: number
      cols: number
      data: string[][]
      type: string
    }>
  }
}

export interface DocmateChange {
  change_id: string
  type: string
  target: string
  replacement?: string
  paragraph_index?: number
  context_before?: string
  occurrences?: number
  risk_level: RiskLevel
  confidence: number
  status?: string
  explanation?: string
  reason?: string
  source?: string
}

export interface DocmatePreviewCard {
  change_id: string
  title: string
  before: string
  after: string
  type: string
  risk_level: RiskLevel
  confidence: number
  explanation?: string
  reason?: string
  source?: string
  paragraph_index?: number
}

export interface AuditEntry {
  id: string
  timestamp: string
  operator: string
  action: 'accept' | 'reject' | 'edit' | 'retry' | 'generate' | 'upload' | 'download' | 'batch_accept' | 'batch_reject'
  target: string
  detail?: string
}

export type RejectReason = '修改过度' | '语义错误' | '不符合规范' | '其他'

export interface DocmateReadResult {
  ok: boolean
  tool?: string
  task_id?: string
  summary?: string
  data: DocmateDocumentStructure
  error?: string
}

export interface DocmateUploadResult {
  ok: boolean
  file_id: string
  file_name?: string
  file_path: string
  download_url?: string
  error?: string
  summary?: string
}

export interface DocmateGenerateResult {
  ok: boolean
  tool?: string
  task_id?: string
  summary?: string
  data: {
    changeset_id: string
    doc_id?: string
    instruction?: string
    changes: DocmateChange[]
    preview_cards: DocmatePreviewCard[]
    total_changes: number
  }
  error?: string
}

export interface DocmatePreviewResult {
  ok: boolean
  tool?: string
  task_id?: string
  summary?: string
  data: {
    changeset_id: string
    instruction?: string
    preview_cards: DocmatePreviewCard[]
    total_changes: number
  }
  error?: string
}

export interface DocmateApplyResult {
  ok: boolean
  tool?: string
  task_id?: string
  summary?: string
  data: {
    applied: number
    rejected: number
    errors: string[]
    output_path: string
    backup_path: string
    source_path?: string
    file_id?: string
    download_url?: string
  }
  error?: string
}

export interface DocmateSessionState {
  step: 'idle' | 'loaded' | 'generated' | 'previewed' | 'applied'
  docId: string
  sourcePath: string
  structure: DocmateDocumentStructure | null
  changesetId: string
  changes: DocmateChange[]
  previewCards: DocmatePreviewCard[]
  instruction: string
  outputPath: string
  error: string | null
}

export interface TableMappingFieldDef {
  name: string
  type?: string
  required?: boolean
}

export interface TableMappingForm {
  id: string
  name: string
  category?: string
  fields: TableMappingFieldDef[]
}

export interface TableMappingExtractedField {
  value: string
  source: string
  confidence: number
}

export interface TableMappingExtractResult {
  ok: boolean
  form: TableMappingForm
  source_path: string
  fields: Record<string, TableMappingExtractedField>
  matched_count: number
  document_preview: string
  script_available: boolean
}

export interface TableMappingRunResult {
  ok: boolean
  job_id: string
  dry_run: boolean
  form: TableMappingForm
  source_path: string
  fields: Record<string, string>
  extracted: Record<string, TableMappingExtractedField>
  command: string[]
  exit_code?: number
  duration_ms?: number
  stdout?: string
  stderr?: string
}

// ── Yaoyao (structured input / OCR) types ──────────────────────

export interface YaoyaoRegion {
  name: string
  x: number
  y: number
  width: number
  height: number
  angle: number
}

export interface YaoyaoFieldCandidate {
  field_name: string
  value: string
  confidence: number
  source_region: string
  page_number: number
}

export interface YaoyaoStructuredDraft {
  ok: boolean
  message: string
  draft_id: string
  preview_image_path?: string | null
  pages: Array<{
    page_number: number
    values: Record<string, string>
  }>
  field_candidates: YaoyaoFieldCandidate[]
  page_count: number
  elapsed_seconds: number
  requires_acceptance: boolean
  confirm_payload: {
    draft_id: string
    template_id?: string | null
    case_id?: number | null
  }
}

export interface YaoyaoPageRenderResult {
  ok: boolean
  preview_image_path?: string | null
  preview_url?: string
  page_index: number
  page_count?: number
  error?: string
  message?: string
}

export interface YaoyaoPageRow {
  pageNumber: number
  values: Record<string, string>
}

export interface YaoyaoExcelExportResult {
  ok: boolean
  file_id: string
  file_name: string
  output_path: string
  download_url: string
  row_count: number
  column_count: number
}

export interface YaoyaoConfirmResult {
  ok: boolean
  message: string
  record_id: string | number
  output_path: string
  audit_id: string
}

export interface YaoyaoTemplate {
  id: string
  name: string
  created_at: string
  regions: YaoyaoRegion[]
  rows: Array<{
    page: number
    values: Record<string, string>
  }>
}

export interface YaoyaoTemplateListItem {
  id: string
  name: string
  created_at: string
  region_count: number
  row_count: number
}

export interface SkillInfo {
  name: string
  path: string
  summary: string
  enabled?: boolean
  category?: string
  status?: 'done' | 'ready' | 'dep' | 'later'
  phase?: string
  tools?: string[]
  workflow?: string
  display_name?: string
  description?: string
  intents?: string[]
  triggers?: string[]
  example_prompts?: string[]
  config?: Record<string, unknown>
}

export interface SkillDetail {
  name: string
  content: string
  config?: Record<string, unknown>
  meta?: SkillInfo | null
  dependencies?: Array<Record<string, unknown>>
  recent_runs?: JobRun[]
  stats?: JobStats
}

export interface WorkflowTemplateInfo {
  workflow_name: string
  title: string
  description: string
  intent: string
  step_count: number
}

export interface WorkflowInfo {
  name: string
  path: string
  summary: string
  enabled: boolean
  category: string
  status: string
  phase: string
  priority?: string
  triggers?: string
  agents?: string
  steps?: Array<Record<string, unknown>>
  existing_tools?: string[]
  pending_tools?: string[]
}

export interface WorkflowDetail {
  name: string
  content: string
  meta?: WorkflowInfo | null
}

export interface RagDocument {
  doc_id: string
  file_name: string
  file_type: string
  chunk_count: number
  collection?: string
  created_at: string
}

export interface RagQueryMatch {
  text: string
  display_text?: string
  text_quality?: 'normal' | 'garbled' | string
  source_file_name: string
  doc_id: string
  chunk_index: number
  collection: string
  score?: number | null
}

export interface RagStats {
  ok: boolean
  document_count: number
  chunk_count: number
  vector_count: number
  chroma_dir?: string
}

export interface RagCitation {
  source_file_name: string
  chunk_index: number
}

export interface RagAskResponse {
  ok: boolean
  query: string
  answer: string
  citations: RagCitation[]
  matches: RagQueryMatch[]
  llm_error?: string
}

export interface ExternalRiskBriefingReport {
  report_id: number
  workflow_run_id: string
  title: string
  summary: string
  briefing_text: string
  report_images: Array<{ title: string; url: string; caption?: string }>
  report_links: Array<{ title: string; source: string; url?: string }>
  tool_results: Array<Record<string, unknown>>
  config: Record<string, unknown>
  payload: Record<string, unknown>
  created_at: string
  updated_at: string
}

export type SourceCategory = 'weather' | 'official' | 'media'
export type PriorityLevel = 'P0' | 'P1' | 'P2'

export interface RiskCard {
  card_id: string
  report_id: string | null
  source_category: SourceCategory
  source_name: string
  source_url: string | null
  title: string
  summary: string | null
  priority: PriorityLevel
  risk_level: string | null
  emoji_tag: string
  keywords: string[]
  location: string | null
  event_date: string | null
  recommended_action: string | null
  is_confirmed: boolean
  payload: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface RiskCardListResponse {
  cards: RiskCard[]
  total: number
}

export interface RiskCardStats {
  P0: number
  P1: number
  P2: number
  total: number
  by_category: {
    weather: number
    official: number
    media: number
  }
}

export interface ExternalMonitorSettings {
  enabled: boolean
  interval_minutes: number
  lookback_hours: number
  sources: string[]
  keywords: string[]
  area: string
  delivery_mode: 'draft' | 'feishu'
  recipient: string
  alert_p0: boolean
  alert_p1: boolean
  updated_at?: string
}

export interface ExternalMonitorRun {
  run_id: string
  status: string
  started_at: string
  finished_at?: string | null
  duration_ms?: number
  workflow_run_id?: string | null
  card_count: number
  new_raw_count: number
  new_event_count: number
  duplicate_count: number
  alert_count: number
  source_count: number
  error?: string | null
  summary?: Record<string, unknown>
}

export interface ExternalSourceState {
  source_key: string
  source_name?: string | null
  source_type?: string | null
  last_seen_at?: string | null
  last_success_at?: string | null
  last_error_at?: string | null
  last_error?: string | null
  failure_count: number
  cooldown_until?: string | null
  last_item_count: number
  updated_at: string
}

export interface ExternalMonitorStatus {
  ok: boolean
  running: boolean
  scheduler_active: boolean
  settings: ExternalMonitorSettings
  last_run?: ExternalMonitorRun | null
  last_success_run?: ExternalMonitorRun | null
  next_run_at?: string | null
  last_error?: string | null
  sources: ExternalSourceState[]
}

export interface ExternalInfoEvent {
  event_id: string
  title: string
  priority: PriorityLevel
  risk_score: number
  relevance_score: number
  confidence: number
  source_count: number
  recommended_action?: string | null
  reason_codes: string[]
  requires_human_review: boolean
  first_seen_at: string
  last_seen_at: string
}
