const fs = require('fs')
const os = require('os')
const path = require('path')

const CONFIG_FILE_NAME = 'runtime-paths.json'

function defaultBaseDir() {
  const root = path.parse(os.homedir()).root || 'C:\\'
  return path.join(root, 'DocMateData')
}

function configFile(app) {
  return path.join(app.getPath('userData'), CONFIG_FILE_NAME)
}

function defaultConfig() {
  const baseDir = defaultBaseDir()
  return {
    baseDir,
    workspaceDir: path.join(baseDir, 'workspace'),
    knowledgeDir: path.join(baseDir, 'knowledge'),
    memoryDir: path.join(baseDir, 'memory'),
    whisperModelDir: path.join(baseDir, 'models', 'whisper'),
    downloadsDir: path.join(baseDir, 'downloads'),
  }
}

function normalizePath(value, fallback) {
  const text = String(value || '').trim()
  if (!text) return fallback
  return path.resolve(text)
}

function normalizeConfig(raw = {}) {
  const defaults = defaultConfig()
  const baseDir = normalizePath(raw.baseDir, defaults.baseDir)
  return {
    baseDir,
    workspaceDir: normalizePath(raw.workspaceDir, path.join(baseDir, 'workspace')),
    knowledgeDir: normalizePath(raw.knowledgeDir, path.join(baseDir, 'knowledge')),
    memoryDir: normalizePath(raw.memoryDir, path.join(baseDir, 'memory')),
    whisperModelDir: normalizePath(raw.whisperModelDir, path.join(baseDir, 'models', 'whisper')),
    downloadsDir: normalizePath(raw.downloadsDir, path.join(baseDir, 'downloads')),
  }
}

function readRuntimeConfig(app) {
  try {
    const raw = JSON.parse(fs.readFileSync(configFile(app), 'utf-8'))
    return normalizeConfig(raw)
  } catch {
    return defaultConfig()
  }
}

function ensureRuntimeDirs(config) {
  for (const key of ['baseDir', 'workspaceDir', 'knowledgeDir', 'memoryDir', 'whisperModelDir', 'downloadsDir']) {
    fs.mkdirSync(config[key], { recursive: true })
  }
}

function writeRuntimeConfig(app, patch = {}) {
  const next = normalizeConfig({ ...readRuntimeConfig(app), ...patch })
  ensureRuntimeDirs(next)
  const fp = configFile(app)
  fs.mkdirSync(path.dirname(fp), { recursive: true })
  fs.writeFileSync(fp, `${JSON.stringify(next, null, 2)}\n`, 'utf-8')
  return next
}

function getRuntimeDir(app, key) {
  const config = readRuntimeConfig(app)
  ensureRuntimeDirs(config)
  return config[key]
}

module.exports = {
  defaultBaseDir,
  defaultConfig,
  readRuntimeConfig,
  writeRuntimeConfig,
  ensureRuntimeDirs,
  getRuntimeDir,
}
