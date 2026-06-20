import type { AgentMode, RevisionResult, RiskItem, TableResult } from '@/types'
import { serializeForIpc } from '@/utils/ipc'

export interface RouteResult {
  task: AgentMode | 'route' | 'clarify'
  result: RevisionResult | string | { risks: RiskItem[] } | TableResult | { question: string; candidates?: { index: number; preview: string }[] }
}

function api() {
  if (!window.electronAPI?.isElectron) throw new Error('NOT_ELECTRON')
  return window.electronAPI
}

function withStream(onChunk?: (chunk: string) => void) {
  const electron = api()
  const unsubChunk = onChunk ? electron.onStreamChunk(onChunk) : undefined
  return () => unsubChunk?.()
}

async function invokeAI(task: AgentMode | 'route', payload: Record<string, unknown>) {
  return api().processAI(task, serializeForIpc(payload))
}

export async function processRoute(
  documentText: string,
  selectedText: string,
  userInput: string,
  history: { role: string; content: string }[],
  onChunk?: (chunk: string) => void,
): Promise<RouteResult> {
  const cleanup = withStream(onChunk)
  try {
    return (await invokeAI('route', {
      user_input: userInput,
      document_text: documentText,
      selected_text: selectedText,
      history,
    })) as RouteResult
  } finally {
    cleanup()
  }
}

export async function processRevision(
  documentText: string,
  selectedText: string,
  command: string,
  history: { role: string; content: string }[] = [],
  onChunk?: (chunk: string) => void,
  options?: { temperature?: number },
): Promise<RevisionResult> {
  const cleanup = withStream(onChunk)
  try {
    return (await invokeAI('revise', {
      document_text: documentText,
      selected_text: selectedText,
      command,
      history,
      temperature: options?.temperature,
    })) as RevisionResult
  } finally {
    cleanup()
  }
}

export async function processPolish(
  documentText: string,
  selectedText: string,
  tone: string,
  history: { role: string; content: string }[] = [],
  onChunk?: (chunk: string) => void,
): Promise<RevisionResult> {
  const cleanup = withStream(onChunk)
  try {
    return (await invokeAI('polish', {
      document_text: documentText,
      selected_text: selectedText,
      tone,
      history,
    })) as RevisionResult
  } finally {
    cleanup()
  }
}

export async function processQA(
  documentText: string,
  question: string,
  history: { role: string; content: string }[],
  onChunk?: (chunk: string) => void,
): Promise<string> {
  const cleanup = withStream(onChunk)
  try {
    const result = (await invokeAI('qa', {
      document_text: documentText,
      question,
      history,
    })) as string
    return result || ''
  } finally {
    cleanup()
  }
}

export async function processRisk(documentText: string, onChunk?: (chunk: string) => void): Promise<RiskItem[]> {
  const cleanup = withStream(onChunk)
  try {
    const result = (await invokeAI('risk', {
      document_text: documentText,
    })) as { risks: RiskItem[] }
    return result.risks
  } finally {
    cleanup()
  }
}

export async function processOral(
  oralText: string,
  style?: string,
  onChunk?: (chunk: string) => void,
): Promise<RevisionResult> {
  const cleanup = withStream(onChunk)
  try {
    return (await invokeAI('oral', {
      oral_text: oralText,
      style: style || '公文风格',
    })) as RevisionResult
  } finally {
    cleanup()
  }
}

export async function processTable(selectedText: string, onChunk?: (chunk: string) => void): Promise<TableResult> {
  const cleanup = withStream(onChunk)
  try {
    return (await invokeAI('table', {
      selected_text: selectedText,
    })) as TableResult
  } finally {
    cleanup()
  }
}

export function isElectronApp(): boolean {
  return !!window.electronAPI?.isElectron
}

export type { AgentMode }
