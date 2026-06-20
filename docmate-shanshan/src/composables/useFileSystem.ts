import { ref, onMounted } from 'vue'
import type { FileNode } from '@/types'
import { debounce } from '@/utils/debounce'

export function useFileSystem() {
  const tree = ref<FileNode[]>([])
  const activeFileId = ref('')
  const activeFilePath = ref('')
  const fileContents = ref<Map<string, string>>(new Map())
  const expandedFolders = ref<Set<string>>(new Set())
  const sidebarCollapsed = ref(true)
  const loading = ref(true)

  async function loadTree() {
    if (!window.electronAPI) return
    loading.value = true
    try {
      tree.value = await window.electronAPI.getFileTree()
      if (!activeFileId.value) {
        const first = findFirstFile(tree.value)
        if (first) await selectFile(first.id, first.path!)
      }
    } finally {
      loading.value = false
    }
  }

  function findFirstFile(nodes: FileNode[]): FileNode | null {
    for (const node of nodes) {
      if (node.type === 'file') return node
      if (node.children) {
        const found = findFirstFile(node.children)
        if (found) return found
      }
    }
    return null
  }

  function findNode(nodes: FileNode[], id: string): FileNode | null {
    for (const node of nodes) {
      if (node.id === id) return node
      if (node.children) {
        const found = findNode(node.children, id)
        if (found) return found
      }
    }
    return null
  }

  const activeFile = ref<FileNode | null>(null)

  async function selectFile(id: string, path?: string) {
    const node = findNode(tree.value, id)
    if (!node || node.type !== 'file') return

    activeFileId.value = id
    activeFilePath.value = path || node.path || id

    if (!fileContents.value.has(activeFilePath.value)) {
      const content = await window.electronAPI!.readFile(activeFilePath.value)
      fileContents.value.set(activeFilePath.value, content)
    }

    activeFile.value = {
      ...node,
      content: fileContents.value.get(activeFilePath.value) ?? '',
    }
  }

  function toggleFolder(id: string) {
    const next = new Set(expandedFolders.value)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    expandedFolders.value = next
  }

  async function writeFileContent(content: string) {
    if (!activeFilePath.value) return
    await window.electronAPI!.writeFile(activeFilePath.value, content)
  }

  const debouncedWrite = debounce((content: string) => {
    void writeFileContent(content)
  }, 600)

  async function updateFileContent(content: string) {
    if (!activeFilePath.value) return
    fileContents.value.set(activeFilePath.value, content)
    if (activeFile.value) activeFile.value.content = content
    debouncedWrite(content)
  }

  async function createFile(parentPath: string, customName?: string) {
    const name = customName || '未命名文稿.md'
    const result = await window.electronAPI!.createFile(parentPath, name)
    await loadTree()
    // result 可能是 { path, name } 或 { path }
    const relPath = result.path || result.name
    const node = findNode(tree.value, relPath)
    if (node) await selectFile(node.id, relPath)
  }

  async function createFromTemplate(templatePath: string) {
    const template = await window.electronAPI!.readFile(templatePath)
    const base = templatePath.split('/').pop()?.replace(/\.[^.]+$/, '') || '模板文稿'
    const result = await window.electronAPI!.createFile('文稿', `${base}-副本.md`)
    await window.electronAPI!.writeFile(result.path, template)
    fileContents.value.set(result.path, template)
    await loadTree()
    const node = findNode(tree.value, result.path)
    if (node) await selectFile(node.id, result.path)
    return result
  }

  async function deleteFile(path: string) {
    await window.electronAPI!.deleteFile(path)
    fileContents.value.delete(path)
    if (activeFilePath.value === path) {
      activeFileId.value = ''
      activeFilePath.value = ''
      activeFile.value = null
    }
    await loadTree()
  }

  async function renameFile(path: string, name: string) {
    const result = await window.electronAPI!.renameFile(path, name)
    const cached = fileContents.value.get(path)
    fileContents.value.delete(path)
    if (cached !== undefined) fileContents.value.set(result.path, cached)
    if (activeFilePath.value === path) {
      activeFilePath.value = result.path
      activeFileId.value = result.path
    }
    await loadTree()
    const node = findNode(tree.value, result.path)
    if (node) await selectFile(node.id, result.path)
    return result
  }

  async function exportFile(format: 'docx' | 'pdf') {
    if (!activeFilePath.value) return { ok: false, reason: 'no-active-file' }
    if (activeFile.value?.content !== undefined) {
      await window.electronAPI!.writeFile(activeFilePath.value, activeFile.value.content)
    }
    return window.electronAPI!.exportFile(activeFilePath.value, format)
  }

  async function importExternalFile() {
    if (!window.electronAPI) return { ok: false, reason: 'not-electron' }
    const result = await window.electronAPI.importFile()
    if (result.ok && result.path) {
      await loadTree()
      const node = findNode(tree.value, result.path)
      if (node) await selectFile(node.id, result.path)
    }
    return result
  }

  async function openWorkspaceFolder() {
    await window.electronAPI!.openWorkspaceFolder()
  }

  onMounted(() => {
    loadTree()
    expandedFolders.value = new Set(['文稿', '模板'])
  })

  return {
    tree,
    activeFileId,
    activeFile,
    activeFilePath,
    expandedFolders,
    sidebarCollapsed,
    loading,
    toggleFolder,
    selectFile,
    updateFileContent,
    createFile,
    createFromTemplate,
    deleteFile,
    renameFile,
    exportFile,
    importExternalFile,
    loadTree,
    openWorkspaceFolder,
  }
}
