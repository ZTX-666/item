export interface FileNode {
  id: string
  name: string
  type: 'folder' | 'file'
  path?: string
  extension?: string
  children?: FileNode[]
  content?: string
}

export type AgentMode = 'revise' | 'polish' | 'qa' | 'risk' | 'oral' | 'table'

export interface RevisionOption {
  id: string
  label: string
  text: string
}

export interface RevisionResult {
  old_text: string
  options: RevisionOption[]
  reason: string
  match_confidence?: 'ok' | 'failed'
  operation?: 'replace' | 'insert' | 'delete'
  insert_anchor?: string
  insert_position?: 'start' | 'end' | 'after'
  paragraph_index?: number
  paragraph_text?: string
}

export interface RevisionHistoryEntry {
  id: string
  time: string
  command: string
  oldText: string
  newText: string
  status: 'accepted' | 'rejected' | 'pending'
}

export interface SelectionAnchor {
  from: number
  to: number
  text: string
}

export interface RevisionProposal {
  id: string
  oldText: string
  options: RevisionOption[]
  command: string
  reason: string
  selectedOptionId: string | null
  status: 'pending' | 'accepted' | 'rejected'
  operation?: 'replace' | 'insert' | 'delete'
  insert_anchor?: string
  insert_position?: 'start' | 'end' | 'after'
  paragraph_index?: number
  paragraph_text?: string
  anchor?: SelectionAnchor
}

export interface RiskItem {
  id: string
  level: 'high' | 'medium' | 'low'
  excerpt: string
  reason: string
  suggestion: string
  resolved?: boolean
}

export interface TableResult {
  headers: string[]
  rows: string[][]
  reason?: string
}

export interface KbDocumentMeta {
  doc_id: string
  doc_name: string
  file_type: string
  chunk_count: number
  total_chars: number
  created_at: string
  status: string
}

export interface UserPreferences {
  version: number
  updated_at: string | null
  auto_learn?: boolean
  learning?: {
    enabled: boolean
    apply_mode: 'suggest' | 'auto'
    learn_from: {
      accepted: boolean
      rejected: boolean
      manual_terms: boolean
      commands: boolean
    }
    digest_threshold: number
    retention_limit: number
    privacy: {
      store_examples: boolean
      store_rejected_text: boolean
    }
  }
  style: {
    formality: 'formal' | 'balanced' | 'casual'
    conciseness?: 'concise' | 'balanced' | 'verbose' | string
    tone?: string
    document_style?: 'hr' | 'party' | 'general'
    risk_sensitivity?: 'standard' | 'strict' | 'highest'
    preferred_phrases: string[]
    avoided_phrases: string[]
  }
  domain: {
    industry?: string
    org?: string
    terms: string[]
  }
  habits?: {
    common_commands?: string[]
    reject_triggers?: string[]
  }
  digest?: {
    interactions_count?: number
    last_digest_at?: string | null
    next_digest_at?: number
  }
}

export interface InteractionRecord {
  command: string
  old_text: string
  new_text: string
  action: 'accept' | 'reject' | 'regenerate'
  reject_reason?: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  streaming?: boolean
  proposal?: RevisionProposal
  risks?: RiskItem[]
  table?: TableResult
  thinkingLog?: string[]
  userContext?: { selection?: string }
  locateCandidates?: { index: number; preview: string }[]
  pendingCommand?: string
}

export interface LlmSettings {
  apiUrl: string
  apiKey: string
  model: string
  useApi: boolean
  optionCount: number
  speechMode?: 'online-first' | 'local' | 'online'
  speechApiUrl?: string
  speechModel?: string
}

export type AiStatus = 'ready' | 'listening' | 'thinking'

export interface ElectronAPI {
  isElectron: boolean
  minimize: () => Promise<void>
  maximize: () => Promise<void>
  close: () => Promise<void>
  isMaximized: () => Promise<boolean>
  getSettings: () => Promise<LlmSettings & { apiKey: string }>
  saveSettings: (settings: Partial<LlmSettings>) => Promise<{ ok: boolean }>
  testConnection: () => Promise<{ ok: boolean; message: string }>
  processRevision: (payload: {
    document_text: string
    selected_text: string
    command: string
  }) => Promise<RevisionResult>
  processAI: (task: AgentMode | 'route', payload: Record<string, unknown>) => Promise<unknown>
  cancelAI: () => Promise<{ ok: boolean }>
  onStreamChunk: (cb: (chunk: string) => void) => () => void
  onStreamEnd: (cb: () => void) => () => void
  transcribeSpeech: (arrayBuffer: ArrayBuffer) => Promise<{ ok: boolean; text?: string; error?: string }>
  onSpeechStatus: (cb: (status: string) => void) => () => void
  getKnowledgeBase: () => Promise<string>
  saveKnowledgeBase: (content: string) => Promise<{ ok: boolean }>
  listKbDocs: () => Promise<KbDocumentMeta[]>
  importKbDoc: () => Promise<{ ok: boolean; doc_id?: string; chunk_count?: number; doc_name?: string; reason?: string }>
  importKbText: (payload: { name: string; content: string }) => Promise<{ ok: boolean; doc_id?: string; chunk_count?: number; doc_name?: string }>
  deleteKbDoc: (docId: string) => Promise<{ ok: boolean }>
  onKbImportProgress: (cb: (progress: { current: number; total: number; message: string }) => void) => () => void
  getPreferences: () => Promise<UserPreferences>
  updatePreferences: (updates: Partial<UserPreferences>) => Promise<UserPreferences>
  resetPreferences: () => Promise<UserPreferences>
  logInteraction: (record: InteractionRecord) => Promise<{ ok: boolean; count?: number }>
  getFileTree: () => Promise<FileNode[]>
  readFile: (path: string) => Promise<string>
  writeFile: (path: string, content: string) => Promise<{ ok: boolean }>
  createFile: (folder: string, name: string) => Promise<{ path: string; name: string }>
  deleteFile: (path: string) => Promise<{ ok: boolean }>
  renameFile: (path: string, name: string) => Promise<{ ok: boolean; path: string; name: string }>
  exportFile: (path: string, format: 'docx' | 'pdf') => Promise<{ ok: boolean; path?: string; reason?: string }>
  importFile: () => Promise<{ ok: boolean; path?: string; reason?: string }>
  openWorkspaceFolder: () => Promise<void>
  getVersion: () => Promise<string>
}

type SpeechRecognitionConstructor = new () => unknown

declare global {
  interface Window {
    electronAPI?: ElectronAPI
    SpeechRecognition?: SpeechRecognitionConstructor
    webkitSpeechRecognition?: SpeechRecognitionConstructor
  }
}

export {}
