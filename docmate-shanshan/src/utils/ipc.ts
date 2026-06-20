import { toRaw } from 'vue'

/** Electron IPC 只能传递可结构化克隆的数据，需剥离 Vue Proxy */
export function serializeForIpc<T>(value: T): T {
  return JSON.parse(JSON.stringify(toRaw(value))) as T
}
