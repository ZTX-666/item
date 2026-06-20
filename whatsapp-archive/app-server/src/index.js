import cors from 'cors'
import express from 'express'
import { execFile } from 'child_process'
import fs from 'fs'
import os from 'os'
import path from 'path'
import Database from 'better-sqlite3'

const app = express()
app.use(express.json({ limit: '2mb' }))
app.use(cors())

function getDefaultStoreDir() {
  // whatscli default is ~/.whatscli
  return path.join(os.homedir(), '.whatscli')
}

function resolveStoreDir() {
  const storeDir = process.env.WHATSCLI_STORE_DIR?.trim() || getDefaultStoreDir()
  return storeDir
}

function discoverSqlitePath(storeDir) {
  const explicit = process.env.WHATSCLI_DB_PATH?.trim()
  if (explicit) return explicit

  if (!fs.existsSync(storeDir)) return null
  const entries = fs.readdirSync(storeDir, { withFileTypes: true })
  const sqliteFiles = entries
    .filter((e) => {
      if (!e.isFile()) return false
      const name = e.name.toLowerCase()
      return name.endsWith('.sqlite') || name.endsWith('.db')
    })
    .map((e) => path.join(storeDir, e.name))

  if (sqliteFiles.length === 1) return sqliteFiles[0]
  if (sqliteFiles.length > 1) {
    // Prefer common names if present
    const preferred = ['whatscli.db', 'store.sqlite', 'whatscli.sqlite', 'db.sqlite', 'db.db']
    for (const name of preferred) {
      const hit = sqliteFiles.find((p) => path.basename(p).toLowerCase() === name)
      if (hit) return hit
    }
    return sqliteFiles[0]
  }
  return null
}

function openDbOrThrow() {
  const storeDir = resolveStoreDir()
  const dbPath = discoverSqlitePath(storeDir)
  if (!dbPath) {
    const hint = [
      `No SQLite DB found in store dir: ${storeDir}`,
      `Run: npm i -g @thiagobarbosa-dev/whatscli`,
      `Then: whatscli auth --store "${storeDir}"`,
      `Then: whatscli sync --once --store "${storeDir}"`,
      `Or set WHATSCLI_DB_PATH to your .sqlite file.`,
    ].join('\n')
    const err = new Error(hint)
    err.code = 'WHATSCLI_DB_NOT_FOUND'
    throw err
  }

  const db = new Database(dbPath, { readonly: true, fileMustExist: true })
  return { db, storeDir, dbPath }
}

function safeInt(value, fallback) {
  const n = Number.parseInt(String(value), 10)
  return Number.isFinite(n) ? n : fallback
}

function withinDir(filePath, baseDir) {
  const rel = path.relative(baseDir, filePath)
  return rel && !rel.startsWith('..') && !path.isAbsolute(rel)
}

app.get('/api/health', (_req, res) => {
  try {
    const { dbPath, storeDir, db } = openDbOrThrow()
    const row = db.prepare('select 1 as ok').get()
    db.close()
    res.json({ ok: row?.ok === 1, storeDir, dbPath })
  } catch (e) {
    res.status(500).json({ ok: false, error: String(e?.message || e) })
  }
})

app.get('/api/chats', (req, res) => {
  try {
    const limit = Math.min(200, Math.max(1, safeInt(req.query.limit, 100)))
    const { db } = openDbOrThrow()
    const rows = db
      .prepare(
        `
        select
          jid,
          name,
          unread_count as unreadCount,
          last_message_at as lastMessageAt,
          is_group as isGroup
        from chats
        order by last_message_at desc
        limit ?
        `
      )
      .all(limit)
    db.close()
    res.json({ rows })
  } catch (e) {
    res.status(500).json({ error: String(e?.message || e) })
  }
})

app.get('/api/messages', (req, res) => {
  try {
    const chatJid = String(req.query.chat || '').trim()
    if (!chatJid) return res.status(400).json({ error: 'Missing query param: chat' })

    const limit = Math.min(200, Math.max(1, safeInt(req.query.limit, 50)))
    const before = safeInt(req.query.before, null) // unix epoch seconds

    const { db } = openDbOrThrow()
    const rows = db
      .prepare(
        `
        select
          id,
          chat_jid as chatJid,
          sender_jid as senderJid,
          from_me as fromMe,
          timestamp,
          type,
          content,
          quoted_id as quotedId,
          media_path as mediaPath
        from messages
        where chat_jid = ?
          and (? is null or timestamp < ?)
        order by timestamp desc
        limit ?
        `
      )
      .all(chatJid, before, before, limit)
    db.close()
    res.json({ rows })
  } catch (e) {
    res.status(500).json({ error: String(e?.message || e) })
  }
})

app.get('/api/messages/search', (req, res) => {
  try {
    const q = String(req.query.q || '').trim()
    if (!q) return res.status(400).json({ error: 'Missing query param: q' })
    const limit = Math.min(200, Math.max(1, safeInt(req.query.limit, 50)))
    const chatJid = String(req.query.chat || '').trim() || null

    const { db } = openDbOrThrow()
    const rows = db
      .prepare(
        `
        select
          id,
          chat_jid as chatJid,
          sender_jid as senderJid,
          from_me as fromMe,
          timestamp,
          type,
          content,
          quoted_id as quotedId,
          media_path as mediaPath
        from messages
        where content like ?
          and (? is null or chat_jid = ?)
        order by timestamp desc
        limit ?
        `
      )
      .all(`%${q}%`, chatJid, chatJid, limit)
    db.close()
    res.json({ rows })
  } catch (e) {
    res.status(500).json({ error: String(e?.message || e) })
  }
})

// Serve media files previously downloaded by whatscli (media_path column)
app.get('/api/media', (req, res) => {
  try {
    const rel = String(req.query.path || '').trim()
    if (!rel) return res.status(400).json({ error: 'Missing query param: path' })

    const storeDir = resolveStoreDir()
    const abs = path.isAbsolute(rel) ? rel : path.join(storeDir, rel)
    const normalized = path.normalize(abs)

    // Only serve files within storeDir to avoid arbitrary file read.
    if (!withinDir(normalized, storeDir)) {
      return res.status(403).json({ error: 'Forbidden path' })
    }

    if (!fs.existsSync(normalized)) {
      return res.status(404).json({ error: 'File not found' })
    }

    res.sendFile(normalized)
  } catch (e) {
    res.status(500).json({ error: String(e?.message || e) })
  }
})

app.post('/api/media/download', (req, res) => {
  try {
    const messageId = String(req.body?.messageId || '').trim()
    if (!messageId) return res.status(400).json({ error: 'Missing body: messageId' })
    if (!/^[A-Z0-9]{10,}$/i.test(messageId)) return res.status(400).json({ error: 'Invalid messageId' })

    // Default to Desktop so the user can find it.
    const desktopDir = path.join(os.homedir(), 'Desktop')
    const destDir = String(req.body?.dir || desktopDir).trim() || desktopDir

    execFile(
      'whatscli',
      ['media', 'download', '--message-id', messageId, '--dir', destDir],
      { windowsHide: true },
      (err, stdout, stderr) => {
        if (err) {
          return res.status(500).json({
            error: 'whatscli media download failed',
            details: String(stderr || stdout || err.message || err),
          })
        }
        return res.json({ ok: true, messageId, dir: destDir, output: String(stdout || '').trim() })
      }
    )
  } catch (e) {
    res.status(500).json({ error: String(e?.message || e) })
  }
})

const port = safeInt(process.env.PORT, 8787)
app.listen(port, () => {
  const storeDir = resolveStoreDir()
  console.log(`[server] http://localhost:${port}`)
  console.log(`[server] store dir: ${storeDir}`)
})

