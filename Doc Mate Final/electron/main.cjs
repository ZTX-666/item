const { app, BrowserWindow, ipcMain, shell, dialog } = require('electron')
const path = require('path')
const fs = require('fs')
const { testLlmConnection } = require('./llm.cjs')
const { processTask, readKnowledgeBase, writeKnowledgeBase, classifyError, callChat } = require('./ai-services.cjs')
const { transcribeAudioBuffer, setupSpeechEnvironment, getSpeechEnvironmentStatus } = require('./speech.cjs')
const { chunkDocument } = require('./kb-chunk.cjs')
const {
  listDocuments,
  removeDocumentMeta,
  removeChunksByDocId,
  readAllChunks,
  persistImportedDoc,
  docsPath,
} = require('./kb-store.cjs')
const {
  DEFAULT_PROFILE,
  readUserProfile,
  writeUserProfile,
  logInteraction,
  deepMerge,
} = require('./preference-engine.cjs')
const { logger } = require('./logger.cjs')
const {
  readRuntimeConfig,
  writeRuntimeConfig,
  ensureRuntimeDirs,
  getRuntimeDir,
} = require('./runtime-config.cjs')

const portableDir = process.env.PORTABLE_EXECUTABLE_DIR
if (portableDir) {
  app.setPath('userData', path.join(portableDir, 'DocMateData'))
}

const isDev = !app.isPackaged
const APP_ICON = [
  path.join(__dirname, '../public/闪闪文档.png'),
  path.join(__dirname, '../dist/闪闪文档.png'),
].find((fp) => fs.existsSync(fp))
let mainWindow = null

const SETTINGS_FILE = () => path.join(app.getPath('userData'), 'llm-settings.json')
const WORKSPACE_DIR = () => getRuntimeDir(app, 'workspaceDir')
const KNOWLEDGE_DIR = () => getRuntimeDir(app, 'knowledgeDir')
const MEMORY_DIR = () => getRuntimeDir(app, 'memoryDir')

const DEFAULT_SETTINGS = {
  apiUrl: 'https://open.bigmodel.cn/api/paas/v4/chat/completions',
  apiKey: '',
  model: 'glm-5.1',
  useApi: true,
  optionCount: 1,
  speechMode: 'online-first',
  speechApiUrl: '',
  speechModel: 'whisper-1',
}

const mammothPromise = Promise.resolve().then(() => require('mammoth')).catch((err) => {
  logger.warn('startup', 'mammoth 预加载失败，将在读取 Word 时重试', err)
  return null
})

const aiContextCache = { value: null, expiresAt: 0 }
const AI_CONTEXT_TTL_MS = 45 * 1000
const fileContentCache = new Map()
const FILE_CACHE_LIMIT = 20

async function renderMarkdown(md) {
  const { marked } = await import('marked')
  return marked.parse(md, { async: false, breaks: true, gfm: true })
}

function safeWorkspacePath(relPath = '') {
  const root = WORKSPACE_DIR()
  const fp = path.resolve(root, relPath || '')
  const relative = path.relative(root, fp)
  if (relative.startsWith('..') || path.isAbsolute(relative)) throw new Error('Invalid path')
  return fp
}

// 支持的文件扩展名
const SUPPORTED_EXTENSIONS = ['.md', '.txt', '.doc', '.docx', '.rtf', '.html', '.htm']

function ensureWorkspace() {
  const dir = WORKSPACE_DIR()
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true })
    seedWorkspace(dir)
  }
  return dir
}

function ensureConfiguredRuntime() {
  const config = readRuntimeConfig(app)
  ensureRuntimeDirs(config)
  return config
}

function seedWorkspace(dir) {
  const docsDir = path.join(dir, '文稿')
  const tplDir = path.join(dir, '模板')
  fs.mkdirSync(docsDir, { recursive: true })
  fs.mkdirSync(tplDir, { recursive: true })

  const samples = [
    {
      folder: docsDir,
      name: '数字化转型工作方案.md',
      content: `<p>关于推进中国建筑国际集团数字化转型的工作方案</p>
<p>为深入贯彻落实集团高质量发展战略部署，加快推进中国建筑国际集团数字化转型工作，提升企业核心竞争力和可持续发展能力，特制定本工作方案。</p>
<p>一、总体目标。以"数字中建"建设为引领，到2028年基本建成覆盖全业务链条的数字化管理体系，实现项目全生命周期数字化管理覆盖率达到90%以上，数据驱动决策能力显著提升。</p>
<p>二、重点任务。一是建设统一数据平台，打通各业务系统数据孤岛；二是推进智慧工地建设，实现施工过程全面感知与智能管控；三是构建数字化供应链，提升采购与物流协同效率；四是打造数字孪生平台，实现重点项目全要素数字化映射。</p>
<p>三、保障措施。加强组织领导，成立数字化转型工作领导小组；加大资金投入，确保年度数字化转型专项预算不低于营收的1.5%；强化人才保障，每年引进和培养数字化专业人才不少于200人；完善考核机制，将数字化转型成效纳入各二级单位绩效考核体系。</p>`,
    },
    {
      folder: docsDir,
      name: '项目汇报提纲.md',
      content: `<p>项目汇报提纲</p>
<p>一、项目背景。本项目旨在推进集团数字化建设，提升管理效率与决策水平。</p>
<p>二、当前进展。已完成需求调研与方案设计，进入系统开发阶段。</p>
<p>三、下一步计划。加快核心模块上线，开展试点应用与培训推广。</p>`,
    },
  ]
  const templates = [
    {
      folder: tplDir,
      name: '人事通知模板.md',
      content: '<p>关于________事项的通知</p><p>各部门：</p><p>为进一步规范________工作，现将有关事项通知如下：</p><p>一、适用范围。</p><p>二、工作要求。</p><p>三、时间安排。</p><p>请各部门结合实际认真落实。</p>',
    },
    {
      folder: tplDir,
      name: '会议纪要模板.md',
      content: '<p>会议纪要</p><p>会议时间：____年__月__日</p><p>会议地点：________</p><p>参会人员：________</p><p>一、会议主要内容。</p><p>二、议定事项。</p><p>三、下一步工作安排。</p>',
    },
    {
      folder: tplDir,
      name: '党建学习通知模板.md',
      content: '<p>关于开展________学习活动的通知</p><p>各党支部：</p><p>为深入学习贯彻________，现就开展学习活动有关事项通知如下：</p><p>一、学习主题。</p><p>二、时间安排。</p><p>三、有关要求。</p>',
    },
  ]

  for (const s of [...samples, ...templates]) {
    const fp = path.join(s.folder, s.name)
    if (!fs.existsSync(fp)) {
      fs.writeFileSync(fp, s.content, 'utf-8')
    }
  }
}

function readSettings() {
  try {
    const raw = fs.readFileSync(SETTINGS_FILE(), 'utf-8')
    const settings = { ...DEFAULT_SETTINGS, ...JSON.parse(raw) }
    settings.optionCount = Math.min(3, Math.max(1, parseInt(settings.optionCount, 10) || 1))
    return settings
  } catch {
    return { ...DEFAULT_SETTINGS }
  }
}

function writeSettings(settings) {
  const file = SETTINGS_FILE()
  fs.mkdirSync(path.dirname(file), { recursive: true })
  fs.writeFileSync(file, `${JSON.stringify(settings, null, 2)}\n`, 'utf-8')
  invalidateAiContext()
}

function invalidateAiContext() {
  aiContextCache.value = null
  aiContextCache.expiresAt = 0
}

function buildAiContext(userDataPath) {
  const now = Date.now()
  if (aiContextCache.value && aiContextCache.expiresAt > now) {
    return aiContextCache.value
  }
  const allChunks = readAllChunks(KNOWLEDGE_DIR())
  const preferences = readUserProfile(MEMORY_DIR())
  const legacyKnowledgeBase = allChunks.length ? '' : readKnowledgeBase(KNOWLEDGE_DIR())
  aiContextCache.value = { allChunks, preferences, legacyKnowledgeBase }
  aiContextCache.expiresAt = now + AI_CONTEXT_TTL_MS
  return aiContextCache.value
}

async function readPlainTextForKb(filePath) {
  const ext = path.extname(filePath).toLowerCase()
  const buffer = fs.readFileSync(filePath)
  if (ext === '.docx') {
    const mammoth = (await mammothPromise) || require('mammoth')
    const result = await mammoth.extractRawText({ buffer })
    return result.value || ''
  }
  if (ext === '.md' || ext === '.txt' || ext === '.html' || ext === '.htm') {
    return buffer.toString('utf-8').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim() || buffer.toString('utf-8')
  }
  return buffer.toString('utf-8')
}

async function migrateLegacyKnowledgeBase(userDataPath) {
  const legacyPath = path.join(userDataPath, 'knowledge-base.txt')
  if (!fs.existsSync(legacyPath)) return
  if (fs.existsSync(docsPath(userDataPath))) {
    const docs = listDocuments(userDataPath)
    if (docs.length > 0) return
  }
  const content = readKnowledgeBase(userDataPath)
  if (!content.trim()) return
  try {
    const settings = readSettings()
    const chunks = await chunkDocument(callChat, settings, '历史知识库', content)
    persistImportedDoc(userDataPath, '历史知识库', chunks)
    fs.renameSync(legacyPath, `${legacyPath}.bak`)
  } catch (err) {
    console.error('旧知识库迁移失败:', err)
  }
}

// 读取文件内容，支持多种格式
async function readFileContent(filePath) {
  const ext = path.extname(filePath).toLowerCase()
  
  try {
    if (!fs.existsSync(filePath)) {
      throw new Error('文件不存在')
    }

    const stat = fs.statSync(filePath)
    const cacheKey = filePath
    const cached = fileContentCache.get(cacheKey)
    if (cached && cached.mtimeMs === stat.mtimeMs && cached.size === stat.size) {
      fileContentCache.delete(cacheKey)
      fileContentCache.set(cacheKey, cached)
      return cached.content
    }

    const buffer = fs.readFileSync(filePath)
    
    // 检测编码
    let content = ''
    if (buffer.length >= 3 && buffer[0] === 0xEF && buffer[1] === 0xBB && buffer[2] === 0xBF) {
      content = buffer.slice(3).toString('utf-8')
    } else if (buffer.length >= 2 && buffer[0] === 0xFF && buffer[1] === 0xFE) {
      content = buffer.slice(2).toString('utf-16le')
    } else {
      content = buffer.toString('utf-8')
    }
    
    let output = ''

    // 根据扩展名处理
    if (ext === '.md') {
      // .md 文件：内容可能是 HTML（编辑器保存的）或纯 Markdown，统一用转换器处理
      output = await convertMarkdownToHtml(content)
    } else if (ext === '.html' || ext === '.htm') {
      output = content
    } else if (ext === '.txt') {
      // 纯文本，包装成 HTML 段落
      output = content.split('\n').map(line => `<p>${escapeHtml(line)}</p>`).join('')
    } else if (ext === '.docx') {
      try {
        const mammoth = (await mammothPromise) || require('mammoth')
        const result = mammoth.extractRawText({ buffer })
        const text = (await result).value || ''
        output = text.split('\n').filter(Boolean).map((line) => `<p>${escapeHtml(line)}</p>`).join('') || '<p></p>'
      } catch {
        return '<p>Word 文档读取失败，请确认文件未损坏或转换为 .txt 格式。</p>'
      }
    } else if (ext === '.doc') {
      output = '<p>检测到旧版 Word 文档 (.doc)。</p><p>建议转换为 .docx 或 .txt 格式后重新打开。</p>'
    } else if (ext === '.rtf') {
      output = '<p>检测到 RTF 文档。</p><p>建议转换为 .txt 或 .md 格式获得更好体验。</p>'
    } else {
      // 默认作为纯文本读取
      output = content.split('\n').map(line => `<p>${escapeHtml(line)}</p>`).join('')
    }

    setFileCache(cacheKey, stat, output)
    return output
  } catch (error) {
    throw new Error(`读取文件失败: ${error.message}`)
  }
}

function setFileCache(key, stat, content) {
  if (fileContentCache.has(key)) fileContentCache.delete(key)
  fileContentCache.set(key, {
    mtimeMs: stat.mtimeMs,
    size: stat.size,
    content,
  })
  if (fileContentCache.size > FILE_CACHE_LIMIT) {
    fileContentCache.delete(fileContentCache.keys().next().value)
  }
}

// Markdown 转 HTML（优先使用 marked，失败时回退到轻量转换）
async function convertMarkdownToHtml(md) {
  const trimmed = md.trim()
  // 如果内容已经是 HTML，直接返回
  if (trimmed.startsWith('<') && (trimmed.includes('</') || trimmed.startsWith('<p'))) {
    return md
  }

  try {
    return await renderMarkdown(md)
  } catch (err) {
    logger.warn('file', 'marked 解析失败，回退轻量 Markdown 转换', err)
  }

  let html = md
  
  // 标题
  html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>')
  html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>')
  html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>')
  
  // 加粗和斜体
  html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/(?<!\*)\*(?!\*)(.*?)(?<!\*)\*(?!\*)/g, '<em>$1</em>')
  
  // 无序列表
  html = html.replace(/^[\-\*] (.*$)/gim, '<li>$1</li>')
  // 有序列表
  html = html.replace(/^\d+\. (.*$)/gim, '<li>$1</li>')
  
  // 代码块
  html = html.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
  // 行内代码
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>')
  
  // 分割线
  html = html.replace(/^---$/gim, '<hr>')
  
  // 段落（避免对已转换的标签再包一层）
  html = html.split('\n\n').map(para => {
    const p = para.trim()
    if (!p) return ''
    if (p.match(/^<[huplo]|^<li|^<pre|^<hr|^<table|^<blockquote/i)) return para
    return `<p>${para.replace(/\n/g, '<br>')}</p>`
  }).join('\n')
  
  return html
}

// HTML 转义
function escapeHtml(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

function htmlToPlainText(html) {
  return String(html || '')
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/p>/gi, '\n')
    .replace(/<\/h[1-6]>/gi, '\n')
    .replace(/<[^>]+>/g, '')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .trim()
}

async function exportDocxFromHtml(html, outPath) {
  const { Document, Packer, Paragraph, TextRun } = require('docx')
  const lines = htmlToPlainText(html).split(/\n+/).map((line) => line.trim()).filter(Boolean)
  const doc = new Document({
    sections: [
      {
        children: lines.length
          ? lines.map((line) => new Paragraph({ children: [new TextRun(line)] }))
          : [new Paragraph('')],
      },
    ],
  })
  const buffer = await Packer.toBuffer(doc)
  fs.writeFileSync(outPath, buffer)
}

function buildFileTree(dir, basePath = '') {
  const entries = fs.readdirSync(dir, { withFileTypes: true })
  const nodes = []

  for (const entry of entries) {
    // 跳过隐藏文件和系统文件
    if (entry.name.startsWith('.') || entry.name === 'node_modules') continue
    
    const rel = basePath ? `${basePath}/${entry.name}` : entry.name
    const full = path.join(dir, entry.name)

    if (entry.isDirectory()) {
      nodes.push({
        id: rel,
        name: entry.name,
        type: 'folder',
        path: rel,
        children: buildFileTree(full, rel),
      })
    } else if (SUPPORTED_EXTENSIONS.some(ext => entry.name.toLowerCase().endsWith(ext))) {
      nodes.push({
        id: rel,
        name: entry.name,
        type: 'file',
        path: rel,
        extension: path.extname(entry.name).toLowerCase(),
      })
    }
  }

  nodes.sort((a, b) => {
    if (a.type !== b.type) return a.type === 'folder' ? -1 : 1
    return a.name.localeCompare(b.name, 'zh-CN')
  })

  return nodes
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 960,
    minHeight: 600,
    title: 'DocMate 闪闪文档',
    icon: fs.existsSync(APP_ICON) ? APP_ICON : undefined,
    backgroundColor: '#141414',
    frame: false,
    titleBarStyle: 'hidden',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
      spellcheck: false,
    },
  })

  const devServerUrl = process.env.VITE_DEV_SERVER_URL || 'http://localhost:5173'
  const indexHtml = path.join(__dirname, '../dist/index.html')
  const useDevServer = isDev && process.env.ELECTRON_DEV === '1'

  if (useDevServer) {
    mainWindow.loadURL(devServerUrl)
  } else if (fs.existsSync(indexHtml)) {
    mainWindow.loadFile(indexHtml)
  } else {
    dialog.showErrorBox(
      'DocMate 无法启动',
      '未找到 dist/index.html。\n\n请先执行 npm run build，\n或使用 npm run electron:dev 进行开发调试。',
    )
    app.quit()
    return
  }

  mainWindow.once('ready-to-show', () => {
    mainWindow?.show()
  })

  mainWindow.webContents.on('did-fail-load', (_e, code, desc, url) => {
    console.error('Failed to load:', url, code, desc)
    if (useDevServer || !fs.existsSync(indexHtml)) return
    mainWindow?.loadFile(indexHtml)
  })

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

function registerIpc() {
  // 窗口控制
  ipcMain.handle('window:minimize', () => mainWindow?.minimize())
  ipcMain.handle('window:maximize', () => {
    if (mainWindow?.isMaximized()) mainWindow.unmaximize()
    else mainWindow?.maximize()
  })
  ipcMain.handle('window:close', () => mainWindow?.close())
  ipcMain.handle('window:isMaximized', () => mainWindow?.isMaximized() ?? false)

  // 设置管理
  ipcMain.handle('settings:get', () => {
    const s = readSettings()
    return { ...s, apiKey: s.apiKey ? '••••••••' + s.apiKey.slice(-4) : '' }
  })

  ipcMain.handle('settings:save', (_e, partial) => {
    const current = readSettings()
    const next = { ...current, ...partial }
    if (partial.apiKey && partial.apiKey.includes('••••')) {
      next.apiKey = current.apiKey
    }
    writeSettings(next)
    return { ok: true }
  })

  ipcMain.handle('settings:test', async () => {
    const settings = readSettings()
    return testLlmConnection(settings)
  })

  ipcMain.handle('config:getRuntime', () => {
    const config = ensureConfiguredRuntime()
    return {
      ok: true,
      config,
      defaults: {
        note: '默认数据目录位于 C 盘，用户可自行修改工作区、知识库、长期记忆和模型缓存地址。',
      },
    }
  })

  ipcMain.handle('config:saveRuntime', (_e, patch) => {
    const config = writeRuntimeConfig(app, patch || {})
    invalidateAiContext()
    return { ok: true, config }
  })

  ipcMain.handle('config:chooseDirectory', async (_e, key) => {
    const result = await dialog.showOpenDialog(mainWindow, {
      properties: ['openDirectory', 'createDirectory'],
    })
    if (result.canceled || !result.filePaths.length) return { ok: false, reason: 'cancelled' }
    const config = writeRuntimeConfig(app, { [key]: result.filePaths[0] })
    invalidateAiContext()
    return { ok: true, config }
  })

  ipcMain.handle('config:openDirectory', (_e, key) => {
    const config = ensureConfiguredRuntime()
    const dir = config[key]
    if (!dir) throw new Error('未知路径配置项')
    fs.mkdirSync(dir, { recursive: true })
    shell.openPath(dir)
    return { ok: true }
  })

  ipcMain.handle('env:check', () => ({ ok: true, speech: getSpeechEnvironmentStatus() }))

  ipcMain.handle('env:setupSpeech', async (event) => {
    const status = await setupSpeechEnvironment((step) => {
      event.sender.send('env:setup-progress', { area: 'speech', step })
    })
    return { ok: true, speech: status }
  })

let currentAiAbortController = null

  ipcMain.handle('ai:cancel', () => {
    if (currentAiAbortController) {
      currentAiAbortController.abort()
      currentAiAbortController = null
    }
    return { ok: true }
  })

  ipcMain.handle('ai:process', async (event, task, payload) => {
    const settings = readSettings()
    const aiContext = buildAiContext()
    if (currentAiAbortController) {
      throw new Error('当前已有任务进行中，请先终止或等待完成')
    }
    const abortController = new AbortController()
    currentAiAbortController = abortController
    const streamTasks = new Set(['qa', 'route', 'revise', 'polish', 'risk', 'oral', 'table', 'summarize'])
    const onChunk = streamTasks.has(task)
      ? (chunk) => {
          if (typeof chunk === 'string') event.sender.send('ai:stream-chunk', chunk)
        }
      : null
    try {
      logger.info('ai', '开始处理任务', { task })
      const result = await processTask(settings, task, payload, aiContext, onChunk, abortController.signal)
      if (onChunk) event.sender.send('ai:stream-end')
      logger.info('ai', '任务处理完成', { task: result?.task || task })
      return result
    } catch (err) {
      if (onChunk) event.sender.send('ai:stream-end')
      if (err.name === 'AbortError') {
        throw new Error('任务已终止')
      }
      const info = classifyError(err)
      logger.error('ai', '任务处理失败', err)
      throw new Error(info.message)
    } finally {
      if (currentAiAbortController === abortController) {
        currentAiAbortController = null
      }
    }
  })

  ipcMain.handle('speech:transcribe', async (_e, arrayBuffer) => {
    try {
      const settings = readSettings()
      const text = await transcribeAudioBuffer(Buffer.from(arrayBuffer), settings, (status) => {
        mainWindow?.webContents.send('speech:status', status)
      })
      return { ok: true, text }
    } catch (err) {
      return { ok: false, error: err.message || String(err) }
    }
  })

  // 知识库管理（旧接口保留兼容）
  ipcMain.handle('knowledge:get', () => readKnowledgeBase(KNOWLEDGE_DIR()))
  ipcMain.handle('knowledge:save', (_e, content) => {
    writeKnowledgeBase(KNOWLEDGE_DIR(), content)
    invalidateAiContext()
    return { ok: true }
  })

  ipcMain.handle('kb:list-docs', () => listDocuments(KNOWLEDGE_DIR()))
  ipcMain.handle('kb:get-chunks', () => readAllChunks(KNOWLEDGE_DIR()))

  ipcMain.handle('kb:import-doc', async (event) => {
    const result = await dialog.showOpenDialog(mainWindow, {
      properties: ['openFile'],
      filters: [
        { name: '知识库文档', extensions: ['txt', 'md', 'docx'] },
        { name: '所有文件', extensions: ['*'] },
      ],
    })
    if (result.canceled || !result.filePaths.length) {
      return { ok: false, reason: 'cancelled' }
    }
    const filePath = result.filePaths[0]
    const name = path.basename(filePath, path.extname(filePath))
    const content = await readPlainTextForKb(filePath)
    const settings = readSettings()
    const chunks = await chunkDocument(callChat, settings, name, content, undefined, (progress) => {
      event.sender.send('kb:import-progress', progress)
    })
    const saved = persistImportedDoc(KNOWLEDGE_DIR(), name, chunks)
    invalidateAiContext()
    return { ok: true, ...saved, doc_name: name }
  })

  ipcMain.handle('kb:import-text', async (event, { name, content }) => {
    const docName = (name || '粘贴文档').trim()
    const text = String(content || '').trim()
    if (!text) throw new Error('内容不能为空')
    const settings = readSettings()
    const chunks = await chunkDocument(callChat, settings, docName, text, undefined, (progress) => {
      event.sender.send('kb:import-progress', progress)
    })
    const saved = persistImportedDoc(KNOWLEDGE_DIR(), docName, chunks)
    invalidateAiContext()
    return { ok: true, ...saved, doc_name: docName }
  })

  ipcMain.handle('kb:delete-doc', (_e, docId) => {
    const knowledgeDir = KNOWLEDGE_DIR()
    removeDocumentMeta(knowledgeDir, docId)
    removeChunksByDocId(knowledgeDir, docId)
    invalidateAiContext()
    return { ok: true }
  })

  ipcMain.handle('prefs:get', () => readUserProfile(MEMORY_DIR()))
  ipcMain.handle('prefs:update', (_e, updates) => {
    const memoryDir = MEMORY_DIR()
    const profile = readUserProfile(memoryDir)
    const merged = deepMerge(profile, updates)
    merged.updated_at = new Date().toISOString()
    writeUserProfile(memoryDir, merged)
    invalidateAiContext()
    return merged
  })
  ipcMain.handle('prefs:reset', () => {
    const memoryDir = MEMORY_DIR()
    const profile = { ...DEFAULT_PROFILE, updated_at: new Date().toISOString() }
    writeUserProfile(memoryDir, profile)
    invalidateAiContext()
    try {
      fs.writeFileSync(path.join(memoryDir, 'interaction-log.jsonl'), '', 'utf-8')
    } catch {
      /* ignore */
    }
    return profile
  })
  ipcMain.handle('log-interaction', (_e, record) => {
    const settings = readSettings()
    const result = logInteraction(MEMORY_DIR(), record, settings, callChat)
    invalidateAiContext()
    return result
  })

  // 工作区管理
  ipcMain.handle('workspace:getTree', () => {
    const dir = ensureWorkspace()
    return buildFileTree(dir)
  })

  ipcMain.handle('workspace:readFile', async (_e, relPath) => {
    const fp = safeWorkspacePath(relPath)
    return readFileContent(fp)
  })

  ipcMain.handle('workspace:writeFile', (_e, relPath, content) => {
    const fp = safeWorkspacePath(relPath)
    fs.writeFileSync(fp, content, 'utf-8')
    fileContentCache.delete(fp)
    return { ok: true }
  })

  ipcMain.handle('workspace:createFile', (_e, folderPath, name) => {
    const dir = safeWorkspacePath(folderPath || '')
    fs.mkdirSync(dir, { recursive: true })
    
    // 不再强制添加 .md 扩展名
    const fileName = name.includes('.') ? name : `${name}.md`
    const rel = folderPath ? `${folderPath}/${fileName}` : fileName
    const fp = path.join(WORKSPACE_DIR(), rel)
    
    if (fs.existsSync(fp)) throw new Error('文件已存在')
    fs.writeFileSync(fp, '<p></p>', 'utf-8')
    fileContentCache.delete(fp)
    return { path: rel, name: fileName }
  })

  ipcMain.handle('workspace:deleteFile', (_e, relPath) => {
    const fp = safeWorkspacePath(relPath)
    if (!fs.existsSync(fp)) throw new Error('文件不存在')
    if (fs.statSync(fp).isDirectory()) throw new Error('暂不支持删除文件夹')
    fs.rmSync(fp, { force: true })
    fileContentCache.delete(fp)
    return { ok: true }
  })

  ipcMain.handle('workspace:renameFile', (_e, relPath, newName) => {
    const fp = safeWorkspacePath(relPath)
    if (!fs.existsSync(fp)) throw new Error('文件不存在')
    if (fs.statSync(fp).isDirectory()) throw new Error('暂不支持重命名文件夹')
    const cleanName = String(newName || '').trim()
    if (!cleanName || cleanName.includes('/') || cleanName.includes('\\')) throw new Error('文件名不合法')
    const next = path.join(path.dirname(fp), cleanName.includes('.') ? cleanName : `${cleanName}${path.extname(fp) || '.md'}`)
    const rel = path.relative(WORKSPACE_DIR(), next).replace(/\\/g, '/')
    if (fs.existsSync(next)) throw new Error('目标文件已存在')
    fs.renameSync(fp, next)
    fileContentCache.delete(fp)
    fileContentCache.delete(next)
    return { ok: true, path: rel, name: path.basename(next) }
  })

  ipcMain.handle('workspace:exportFile', async (_e, relPath, format) => {
    const fp = safeWorkspacePath(relPath)
    if (!fs.existsSync(fp)) throw new Error('文件不存在')
    const html = await readFileContent(fp)
    const ext = format === 'pdf' ? 'pdf' : 'docx'
    const result = await dialog.showSaveDialog(mainWindow, {
      defaultPath: path.join(app.getPath('desktop'), `${path.basename(relPath, path.extname(relPath))}.${ext}`),
      filters: [{ name: ext.toUpperCase(), extensions: [ext] }],
    })
    if (result.canceled || !result.filePath) return { ok: false, reason: 'cancelled' }
    if (ext === 'docx') {
      await exportDocxFromHtml(html, result.filePath)
    } else {
      const win = new BrowserWindow({ show: false, webPreferences: { sandbox: true } })
      const tmp = path.join(app.getPath('temp'), `docmate-export-${Date.now()}.html`)
      fs.writeFileSync(tmp, `<!doctype html><html><head><meta charset="utf-8"><style>body{font-family:"Microsoft YaHei",sans-serif;line-height:1.8;padding:40px;color:#111}</style></head><body>${html}</body></html>`, 'utf-8')
      await win.loadFile(tmp)
      const data = await win.webContents.printToPDF({ printBackground: true, pageSize: 'A4' })
      fs.writeFileSync(result.filePath, data)
      win.close()
      fs.rmSync(tmp, { force: true })
    }
    return { ok: true, path: result.filePath }
  })

  ipcMain.handle('workspace:openFolder', () => {
    shell.openPath(WORKSPACE_DIR())
  })

  ipcMain.handle('workspace:importFile', async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
      properties: ['openFile'],
      filters: [
        { name: '文档', extensions: ['md', 'txt', 'html', 'htm', 'rtf', 'docx'] },
        { name: '所有文件', extensions: ['*'] }
      ]
    })
    
    if (result.canceled || !result.filePaths.length) {
      return { ok: false, reason: 'cancelled' }
    }
    
    const srcPath = result.filePaths[0]
    const fileName = path.basename(srcPath)
    const destPath = path.join(WORKSPACE_DIR(), '文稿', fileName)
    
    // 复制到工作区
    fs.copyFileSync(srcPath, destPath)
    fileContentCache.delete(destPath)
    
    return { ok: true, path: `文稿/${fileName}` }
  })

  ipcMain.handle('app:getVersion', () => app.getVersion())
}

app.whenReady().then(async () => {
  ensureConfiguredRuntime()
  ensureWorkspace()
  registerIpc()
  migrateLegacyKnowledgeBase(KNOWLEDGE_DIR()).catch((err) => {
    console.error('知识库迁移失败:', err)
  })
  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
