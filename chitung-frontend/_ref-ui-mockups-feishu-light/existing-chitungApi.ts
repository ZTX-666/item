import type {
  AppConfig,
  CenterChatResponse,
  ChatResponse,
  ConnectorSettingsStatus,
  DocumentRevisionPreview,
  GeneratedReport,
  HybridPlan,
  LlmTestResult,
  LlmSettingsStatus,
  RuntimeStatus,
  SafetyCaseRecord,
  SmartFormDraft,
  SmartFormTemplate,
  VisualPatrolDraft,
  WorkbenchSummary,
} from '../types/domain'

const CENTER_BASE_URL =
  import.meta.env.VITE_CHITUNG_CENTER_URL?.replace(/\/$/, '') || 'http://127.0.0.1:8999'

async function ensureOk(response: Response, message: string) {
  if (response.ok) return
  let detail = ''
  try {
    const data = await response.json()
    detail = String(data.message || data.detail || data.error || '')
  } catch {
    detail = await response.text().catch(() => '')
  }
  throw new Error(detail ? `${message}: ${detail}` : `${message}: ${response.status}`)
}

export interface SendMessageRequest {
  message: string
  channel?: 'local_chat' | 'feishu'
  context?: Record<string, unknown>
}

export async function sendChatMessage(request: SendMessageRequest): Promise<ChatResponse> {
  const response = await fetch(`${CENTER_BASE_URL}/api/chat/message`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      channel: request.channel ?? 'local_chat',
      message: request.message,
      metadata: request.context ?? {},
    }),
  })

  await ensureOk(response, 'Chitung Center request failed')

  const data = (await response.json()) as CenterChatResponse
  return {
    type: data.cards?.length ? 'review_card' : 'reply',
    message: data.reply,
    payload: {
      intent: data.intent,
      cards: data.cards ?? [],
      toolResults: data.tool_results ?? [],
      auditId: data.audit_id,
    },
  }
}

export async function getHealth(): Promise<Record<string, unknown>> {
  const response = await fetch(`${CENTER_BASE_URL}/health`)
  await ensureOk(response, 'Health check failed')
  return response.json() as Promise<Record<string, unknown>>
}

export async function getWorkbenchSummary(): Promise<WorkbenchSummary> {
  const response = await fetch(`${CENTER_BASE_URL}/api/workbench/summary`)
  await ensureOk(response, 'Workbench summary failed')
  return response.json() as Promise<WorkbenchSummary>
}

export async function getRuntimeStatus(): Promise<RuntimeStatus> {
  const response = await fetch(`${CENTER_BASE_URL}/api/runtime/status`)
  await ensureOk(response, 'Runtime status failed')
  return response.json() as Promise<RuntimeStatus>
}

export async function getAppConfig(): Promise<AppConfig> {
  const response = await fetch(`${CENTER_BASE_URL}/api/config/app`)
  await ensureOk(response, 'App config failed')
  return response.json() as Promise<AppConfig>
}

export async function saveAppConfig(config: AppConfig): Promise<{ ok: boolean; config: AppConfig }> {
  const response = await fetch(`${CENTER_BASE_URL}/api/config/app`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  })
  await ensureOk(response, 'App config save failed')
  return response.json() as Promise<{ ok: boolean; config: AppConfig }>
}

export async function getLlmSettings(): Promise<LlmSettingsStatus> {
  const response = await fetch(`${CENTER_BASE_URL}/api/settings/llm`)
  await ensureOk(response, 'LLM settings status failed')
  return response.json() as Promise<LlmSettingsStatus>
}

export async function saveLlmSettings(request: {
  baseUrl: string
  apiKey: string
  model: string
}): Promise<{ ok: boolean; message: string; status: LlmSettingsStatus }> {
  const response = await fetch(`${CENTER_BASE_URL}/api/settings/llm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      base_url: request.baseUrl,
      api_key: request.apiKey,
      model: request.model,
    }),
  })
  await ensureOk(response, 'LLM settings save failed')
  return response.json() as Promise<{ ok: boolean; message: string; status: LlmSettingsStatus }>
}

export async function testLlmSettings(): Promise<LlmTestResult> {
  const response = await fetch(`${CENTER_BASE_URL}/api/settings/llm/test`, {
    method: 'POST',
  })
  await ensureOk(response, 'LLM settings test failed')
  return response.json() as Promise<LlmTestResult>
}

export async function getConnectorSettings(): Promise<ConnectorSettingsStatus> {
  const response = await fetch(`${CENTER_BASE_URL}/api/settings/connectors`)
  await ensureOk(response, 'Connector settings status failed')
  return response.json() as Promise<ConnectorSettingsStatus>
}

export async function saveConnectorSettings(request: {
  whatsappArchiveBaseUrl: string
  feishuWebhookUrl: string
  feishuWebhookSecret: string
  feishuAppId: string
  feishuAppSecret: string
  feishuVerificationToken: string
  feishuEncryptKey: string
  feishuApiBaseUrl: string
}): Promise<{ ok: boolean; message: string; status: ConnectorSettingsStatus }> {
  const response = await fetch(`${CENTER_BASE_URL}/api/settings/connectors`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      whatsapp_archive_base_url: request.whatsappArchiveBaseUrl,
      feishu_webhook_url: request.feishuWebhookUrl,
      feishu_webhook_secret: request.feishuWebhookSecret,
      feishu_app_id: request.feishuAppId,
      feishu_app_secret: request.feishuAppSecret,
      feishu_verification_token: request.feishuVerificationToken,
      feishu_encrypt_key: request.feishuEncryptKey,
      feishu_api_base_url: request.feishuApiBaseUrl,
    }),
  })
  await ensureOk(response, 'Connector settings save failed')
  return response.json() as Promise<{ ok: boolean; message: string; status: ConnectorSettingsStatus }>
}

export async function updateHazardStatus(caseId: string, status = 'confirmed'): Promise<Record<string, unknown>> {
  const response = await fetch(`${CENTER_BASE_URL}/api/hazards/${encodeURIComponent(caseId)}/status`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      status,
      notes: 'Confirmed from Chitung desktop workbench.',
    }),
  })
  await ensureOk(response, 'Hazard status update failed')
  return response.json() as Promise<Record<string, unknown>>
}

export async function getHazards(status?: string): Promise<SafetyCaseRecord[]> {
  const params = new URLSearchParams()
  if (status) params.set('status', status)
  params.set('limit', '100')
  const response = await fetch(`${CENTER_BASE_URL}/api/hazards?${params.toString()}`)
  await ensureOk(response, 'Hazard list failed')
  const data = (await response.json()) as { items?: SafetyCaseRecord[] }
  return data.items ?? []
}

export async function draftDocumentRevision(request: {
  title: string
  source: string
  instruction: string
  originalText: string
  revisedText?: string
}): Promise<DocumentRevisionPreview> {
  const response = await fetch(`${CENTER_BASE_URL}/api/documents/revision-preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      title: request.title,
      source: request.source,
      instruction: request.instruction,
      original_text: request.originalText,
      revised_text: request.revisedText,
    }),
  })
  await ensureOk(response, 'Document revision preview failed')
  return response.json() as Promise<DocumentRevisionPreview>
}

export async function draftSmartForm(request: {
  query: string
  sourceText: string
  templateId?: string
  caseId?: number
  knownFields?: Record<string, unknown>
  instruction?: string
}): Promise<SmartFormDraft> {
  const response = await fetch(`${CENTER_BASE_URL}/api/forms/smart-draft`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query: request.query,
      source_text: request.sourceText,
      template_id: request.templateId,
      case_id: request.caseId,
      known_fields: request.knownFields ?? {},
      instruction: request.instruction ?? '???????????????????',
    }),
  })
  await ensureOk(response, 'Smart form draft failed')
  return response.json() as Promise<SmartFormDraft>
}

export async function searchFormTemplates(query = ''): Promise<SmartFormTemplate[]> {
  const params = new URLSearchParams()
  if (query.trim()) params.set('query', query.trim())
  params.set('limit', '20')
  const response = await fetch(`${CENTER_BASE_URL}/api/forms/templates?${params.toString()}`)
  await ensureOk(response, 'Form template search failed')
  const data = (await response.json()) as { items?: SmartFormTemplate[] }
  return data.items ?? []
}

export async function acceptSmartFormDraft(draft: SmartFormDraft): Promise<Record<string, unknown>> {
  if (!draft.accept_payload) {
    throw new Error('Smart form draft has no accept payload')
  }

  const response = await fetch(`${CENTER_BASE_URL}/api/forms/accept-draft`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      template_id: draft.accept_payload.template_id,
      fields: draft.accept_payload.fields,
      output_path: draft.accept_payload.output_path,
      case_id: draft.accept_payload.case_id,
      notes: 'Accepted from Chitung desktop document diff panel.',
    }),
  })
  await ensureOk(response, 'Smart form accept failed')
  return response.json() as Promise<Record<string, unknown>>
}

export async function draftVisualPatrol(request: {
  cameraUrl?: string
  source?: string
  area?: string
  contractor?: string
  count?: number
}): Promise<VisualPatrolDraft> {
  const response = await fetch(`${CENTER_BASE_URL}/api/visual/patrol-draft`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      camera_url: request.cameraUrl,
      source: request.source,
      area: request.area,
      contractor: request.contractor,
      count: request.count ?? 1,
    }),
  })
  await ensureOk(response, 'Visual patrol draft failed')
  return response.json() as Promise<VisualPatrolDraft>
}

export async function confirmVisualPatrolCandidate(draft: VisualPatrolDraft): Promise<Record<string, unknown>> {
  const response = await fetch(`${CENTER_BASE_URL}/api/visual/confirm-candidate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(draft.confirm_payload ?? {}),
  })
  await ensureOk(response, 'Visual patrol confirm failed')
  return response.json() as Promise<Record<string, unknown>>
}

export async function runCaseWorkflow(
  action: 'rectification-notice' | 'contractor-confirm' | 'close-review',
  request: {
    caseId: string
    contractor?: string
    dueDate?: string
    notes?: string
    reviewer?: string
    evidencePaths?: string[]
  },
): Promise<Record<string, unknown>> {
  const response = await fetch(`${CENTER_BASE_URL}/api/cases/${action}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      case_id: Number(request.caseId),
      contractor: request.contractor,
      due_date: request.dueDate,
      notes: request.notes,
      reviewer: request.reviewer,
      evidence_paths: request.evidencePaths ?? [],
    }),
  })
  await ensureOk(response, 'Case workflow failed')
  return response.json() as Promise<Record<string, unknown>>
}

export async function generateReport(request: {
  reportType: 'community' | 'daily_safety' | 'rectification'
  caseId?: number
  title?: string
}): Promise<GeneratedReport> {
  const response = await fetch(`${CENTER_BASE_URL}/api/reports/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      report_type: request.reportType,
      case_id: request.caseId,
      title: request.title,
    }),
  })
  await ensureOk(response, 'Report generation failed')
  return response.json() as Promise<GeneratedReport>
}

export async function sendCaseNotification(request: {
  caseId: string
  text: string
  contractor?: string
  channel: 'feishu' | 'whatsapp'
}): Promise<Record<string, unknown>> {
  const response = await fetch(`${CENTER_BASE_URL}/api/cases/send-notification`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      case_id: Number(request.caseId),
      text: request.text,
      contractor: request.contractor,
      channel: request.channel,
      confirmed_by: 'desktop_user',
    }),
  })
  await ensureOk(response, 'Notification send failed')
  return response.json() as Promise<Record<string, unknown>>
}

export async function searchWhatsAppMessages(request: {
  q: string
  chat?: string
  limit?: number
}): Promise<Record<string, unknown>> {
  const response = await fetch(`${CENTER_BASE_URL}/api/whatsapp/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      q: request.q,
      chat: request.chat,
      limit: request.limit ?? 20,
    }),
  })
  await ensureOk(response, 'WhatsApp search failed')
  return response.json() as Promise<Record<string, unknown>>
}

export async function getWhatsAppGroups(includeArchived = false): Promise<Record<string, unknown>> {
  const response = await fetch(`${CENTER_BASE_URL}/api/whatsapp/groups`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ include_archived: includeArchived }),
  })
  await ensureOk(response, 'WhatsApp groups query failed')
  return response.json() as Promise<Record<string, unknown>>
}

export async function createHybridPlan(request: {
  sessionId: string
  userInput: string
  preferCodex: boolean
  metadata?: Record<string, unknown>
}): Promise<{ ok: boolean; audit_id: string; plan: HybridPlan }> {
  const response = await fetch(`${CENTER_BASE_URL}/plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: request.sessionId,
      user_input: request.userInput,
      prefer_codex: request.preferCodex,
      metadata: request.metadata ?? {},
    }),
  })
  await ensureOk(response, 'Create hybrid plan failed')
  return response.json() as Promise<{ ok: boolean; audit_id: string; plan: HybridPlan }>
}

export async function confirmHybridPlan(request: {
  sessionId: string
  planId: string
  actionIds: string[]
  confirmedBy: string
  notes?: string
}): Promise<{ ok: boolean; audit_id: string; plan: HybridPlan }> {
  const response = await fetch(`${CENTER_BASE_URL}/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: request.sessionId,
      plan_id: request.planId,
      action_ids: request.actionIds,
      confirmed_by: request.confirmedBy,
      notes: request.notes,
    }),
  })
  await ensureOk(response, 'Confirm hybrid plan failed')
  return response.json() as Promise<{ ok: boolean; audit_id: string; plan: HybridPlan }>
}

export async function executeHybridPlan(request: {
  sessionId: string
  planId: string
  idempotencyKey?: string
  retryFailedOnly?: boolean
  dryRun?: boolean
}): Promise<{ ok: boolean; audit_id: string; plan: HybridPlan; action_results: Array<Record<string, unknown>> }> {
  const response = await fetch(`${CENTER_BASE_URL}/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: request.sessionId,
      plan_id: request.planId,
      idempotency_key: request.idempotencyKey,
      retry_failed_only: request.retryFailedOnly ?? true,
      dry_run: request.dryRun ?? false,
    }),
  })
  await ensureOk(response, 'Execute hybrid plan failed')
  return response.json() as Promise<{ ok: boolean; audit_id: string; plan: HybridPlan; action_results: Array<Record<string, unknown>> }>
}

export async function createAuditEvent(request: {
  eventType: string
  payload?: Record<string, unknown>
  sessionId?: string
  planId?: string
  actionId?: string
  status?: string
}): Promise<{ ok: boolean; audit_id: string }> {
  const response = await fetch(`${CENTER_BASE_URL}/audit/event`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      event_type: request.eventType,
      payload: request.payload ?? {},
      session_id: request.sessionId,
      plan_id: request.planId,
      action_id: request.actionId,
      status: request.status,
    }),
  })
  await ensureOk(response, 'Create audit event failed')
  return response.json() as Promise<{ ok: boolean; audit_id: string }>
}
