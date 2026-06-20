const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('chitungDesktop', {
  getRuntime: () => ipcRenderer.invoke('app:get-runtime'),
  openPath: (targetPath) => ipcRenderer.invoke('file:open-path', targetPath),
  showInFolder: (targetPath) => ipcRenderer.invoke('file:show-in-folder', targetPath),
  restartServices: () => ipcRenderer.invoke('services:restart-local'),
})
