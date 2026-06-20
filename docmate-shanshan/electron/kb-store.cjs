const fs = require('fs')
const path = require('path')

function docsPath(userDataPath) {
  return path.join(userDataPath, 'kb-documents.json')
}

function chunksDir(userDataPath) {
  return path.join(userDataPath, 'kb-chunks')
}

function readJson(fp, fallback) {
  try {
    return JSON.parse(fs.readFileSync(fp, 'utf-8'))
  } catch {
    return fallback
  }
}

function writeJson(fp, data) {
  fs.mkdirSync(path.dirname(fp), { recursive: true })
  fs.writeFileSync(fp, `${JSON.stringify(data, null, 2)}\n`, 'utf-8')
}

function listDocuments(userDataPath) {
  return readJson(docsPath(userDataPath), [])
}

function saveDocumentMeta(userDataPath, meta) {
  const list = listDocuments(userDataPath)
  const idx = list.findIndex((d) => d.doc_id === meta.doc_id)
  if (idx >= 0) list[idx] = meta
  else list.push(meta)
  writeJson(docsPath(userDataPath), list)
}

function removeDocumentMeta(userDataPath, docId) {
  const list = listDocuments(userDataPath).filter((d) => d.doc_id !== docId)
  writeJson(docsPath(userDataPath), list)
}

function saveChunksForDoc(userDataPath, docId, chunks) {
  const dir = chunksDir(userDataPath)
  fs.mkdirSync(dir, { recursive: true })
  writeJson(path.join(dir, `${docId}.json`), chunks)
}

function removeChunksByDocId(userDataPath, docId) {
  const fp = path.join(chunksDir(userDataPath), `${docId}.json`)
  try {
    fs.unlinkSync(fp)
  } catch {
    /* ignore */
  }
}

function readAllChunks(userDataPath) {
  const dir = chunksDir(userDataPath)
  if (!fs.existsSync(dir)) return []

  const all = []
  for (const file of fs.readdirSync(dir)) {
    if (!file.endsWith('.json')) continue
    const chunks = readJson(path.join(dir, file), [])
    if (Array.isArray(chunks)) all.push(...chunks)
  }
  return all
}

function newDocId() {
  const stamp = new Date().toISOString().replace(/[-:TZ.]/g, '').slice(0, 14)
  return `doc-${stamp}-${Math.random().toString(36).slice(2, 6)}`
}

function newChunkId() {
  return `chunk-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`
}

function persistImportedDoc(userDataPath, docName, rawChunks) {
  const docId = newDocId()
  const now = new Date().toISOString()
  const chunks = rawChunks.map((c, i) => ({
    chunk_id: newChunkId(),
    doc_id: docId,
    doc_name: docName,
    title: c.title || `片段${i + 1}`,
    keywords: Array.isArray(c.keywords) ? c.keywords : [],
    summary: c.summary || '',
    content: c.content || '',
    chunk_index: i + 1,
    char_count: (c.content || '').length,
    created_at: now,
  }))

  const totalChars = chunks.reduce((n, c) => n + c.char_count, 0)
  saveDocumentMeta(userDataPath, {
    doc_id: docId,
    doc_name: docName,
    file_type: 'text',
    chunk_count: chunks.length,
    total_chars: totalChars,
    created_at: now,
    status: 'ready',
  })
  saveChunksForDoc(userDataPath, docId, chunks)
  return { doc_id: docId, chunk_count: chunks.length }
}

module.exports = {
  listDocuments,
  saveDocumentMeta,
  removeDocumentMeta,
  removeChunksByDocId,
  readAllChunks,
  persistImportedDoc,
  docsPath,
  chunksDir,
}
