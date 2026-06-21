const fs = require('fs')
const path = require('path')
const { app } = require('electron')

function logDir() {
  const dir = path.join(app.getPath('userData'), 'logs')
  fs.mkdirSync(dir, { recursive: true })
  return dir
}

function logPath() {
  const d = new Date()
  const day = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  return path.join(logDir(), `app-${day}.log`)
}

function pruneLogs(keepDays = 7) {
  try {
    const dir = logDir()
    const files = fs.readdirSync(dir).filter((f) => /^app-\d{4}-\d{2}-\d{2}\.log$/.test(f)).sort()
    for (const f of files.slice(0, Math.max(0, files.length - keepDays))) {
      fs.rmSync(path.join(dir, f), { force: true })
    }
  } catch {
    /* ignore logging cleanup errors */
  }
}

function write(level, moduleName, message, data) {
  const entry = {
    ts: new Date().toISOString(),
    level,
    module: moduleName,
    message,
    data: data instanceof Error ? { message: data.message, stack: data.stack } : data,
  }
  const line = `${JSON.stringify(entry)}\n`
  try {
    fs.appendFileSync(logPath(), line, 'utf-8')
    pruneLogs()
  } catch {
    /* ignore */
  }
  const payload = data === undefined ? [message] : [message, data]
  if (level === 'error') console.error(`[${moduleName}]`, ...payload)
  else if (level === 'warn') console.warn(`[${moduleName}]`, ...payload)
  else console.log(`[${moduleName}]`, ...payload)
}

const logger = {
  info: (moduleName, message, data) => write('info', moduleName, message, data),
  warn: (moduleName, message, data) => write('warn', moduleName, message, data),
  error: (moduleName, message, data) => write('error', moduleName, message, data),
}

module.exports = { logger, pruneLogs }
