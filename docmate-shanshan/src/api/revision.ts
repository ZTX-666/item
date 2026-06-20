import type { RevisionResult } from '@/types'
export { processRevision } from './ai'

export async function callRevisionAPI(
  documentText: string,
  selectedText: string,
  command: string,
): Promise<RevisionResult> {
  const { processRevision } = await import('./ai')
  return processRevision(documentText, selectedText, command)
}

export function isElectronApp(): boolean {
  return !!window.electronAPI?.isElectron
}
