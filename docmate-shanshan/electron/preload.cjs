const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
  minimize: () => ipcRenderer.invoke('window:minimize'),
  maximize: () => ipcRenderer.invoke('window:maximize'),
  close: () => ipcRenderer.invoke('window:close'),
  isMaximized: () => ipcRenderer.invoke('window:isMaximized'),

  getSettings: () => ipcRenderer.invoke('settings:get'),
  saveSettings: (settings) => ipcRenderer.invoke('settings:save', settings),
  testConnection: () => ipcRenderer.invoke('settings:test'),

  processRevision: (payload) => ipcRenderer.invoke('ai:process', 'revise', payload),
  processAI: (task, payload) => ipcRenderer.invoke('ai:process', task, payload),
  cancelAI: () => ipcRenderer.invoke('ai:cancel'),
  onStreamChunk: (cb) => {
    const handler = (_e, chunk) => cb(chunk)
    ipcRenderer.on('ai:stream-chunk', handler)
    return () => ipcRenderer.removeListener('ai:stream-chunk', handler)
  },
  onStreamEnd: (cb) => {
    const handler = () => cb()
    ipcRenderer.on('ai:stream-end', handler)
    return () => ipcRenderer.removeListener('ai:stream-end', handler)
  },
  transcribeSpeech: (arrayBuffer) => ipcRenderer.invoke('speech:transcribe', arrayBuffer),
  onSpeechStatus: (cb) => {
    const handler = (_e, status) => cb(status)
    ipcRenderer.on('speech:status', handler)
    return () => ipcRenderer.removeListener('speech:status', handler)
  },
  getKnowledgeBase: () => ipcRenderer.invoke('knowledge:get'),
  saveKnowledgeBase: (content) => ipcRenderer.invoke('knowledge:save', content),
  listKbDocs: () => ipcRenderer.invoke('kb:list-docs'),
  importKbDoc: () => ipcRenderer.invoke('kb:import-doc'),
  importKbText: (payload) => ipcRenderer.invoke('kb:import-text', payload),
  deleteKbDoc: (docId) => ipcRenderer.invoke('kb:delete-doc', docId),
  onKbImportProgress: (cb) => {
    const handler = (_e, progress) => cb(progress)
    ipcRenderer.on('kb:import-progress', handler)
    return () => ipcRenderer.removeListener('kb:import-progress', handler)
  },
  getPreferences: () => ipcRenderer.invoke('prefs:get'),
  updatePreferences: (updates) => ipcRenderer.invoke('prefs:update', updates),
  resetPreferences: () => ipcRenderer.invoke('prefs:reset'),
  logInteraction: (record) => ipcRenderer.invoke('log-interaction', record),

  getFileTree: () => ipcRenderer.invoke('workspace:getTree'),
  readFile: (path) => ipcRenderer.invoke('workspace:readFile', path),
  writeFile: (path, content) => ipcRenderer.invoke('workspace:writeFile', path, content),
  createFile: (folder, name) => ipcRenderer.invoke('workspace:createFile', folder, name),
  deleteFile: (path) => ipcRenderer.invoke('workspace:deleteFile', path),
  renameFile: (path, name) => ipcRenderer.invoke('workspace:renameFile', path, name),
  exportFile: (path, format) => ipcRenderer.invoke('workspace:exportFile', path, format),
  importFile: () => ipcRenderer.invoke('workspace:importFile'),
  openWorkspaceFolder: () => ipcRenderer.invoke('workspace:openFolder'),

  getVersion: () => ipcRenderer.invoke('app:getVersion'),
  isElectron: true,
})
