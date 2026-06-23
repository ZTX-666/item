import { resolveChatAssetUrl } from '../services/chitungApi'

export type ChatRichBlock =
  | {
      kind: 'table'
      title: string
      columns: string[]
      rows: Array<Record<string, unknown>>
      total?: number
      limit?: number
      offset?: number
    }
  | {
      kind: 'image'
      title: string
      url: string
      caption?: string
    }
  | {
      kind: 'file'
      title: string
      url?: string
      path?: string
      mime?: string
      fileName?: string
      size?: number
    }
  | {
      kind: 'markdown'
      title: string
      text: string
    }
  | {
      kind: 'code'
      title: string
      language?: string
      text: string
    }
  | {
      kind: 'list'
      title: string
      items: string[]
    }
  | {
      kind: 'links'
      title: string
      links: Array<{ title: string; url: string; source?: string }>
    }

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' ? (value as Record<string, unknown>) : null
}

function pushUnique(blocks: ChatRichBlock[], block: ChatRichBlock | null) {
  if (!block) return
  const key = `${block.kind}:${block.title}:${'text' in block ? block.text.slice(0, 40) : ''}`
  if (blocks.some((item) => `${item.kind}:${item.title}:${'text' in item ? item.text.slice(0, 40) : ''}` === key)) {
    return
  }
  blocks.push(block)
}

function resolveUrl(raw?: string | null): string | undefined {
  return resolveChatAssetUrl(raw)
}

function tableFromData(data: Record<string, unknown>, title: string): ChatRichBlock | null {
  const columns = Array.isArray(data.columns) ? data.columns.map((item) => String(item)) : []
  const rows = Array.isArray(data.rows)
    ? data.rows.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object')
    : []
  if (!columns.length || !rows.length) return null
  return {
    kind: 'table',
    title,
    columns,
    rows,
    total: typeof data.total === 'number' ? data.total : rows.length,
    limit: typeof data.limit === 'number' ? data.limit : undefined,
    offset: typeof data.offset === 'number' ? data.offset : undefined,
  }
}

function fileBlockFromRecord(record: Record<string, unknown>, title: string): ChatRichBlock | null {
  const rawUrl = typeof record.url === 'string' ? record.url : undefined
  const rawPath = typeof record.path === 'string' ? record.path : undefined
  const url = resolveUrl(rawUrl || rawPath)
  if (!url && !rawPath) return null
  return {
    kind: 'file',
    title,
    url,
    path: rawPath,
    mime: typeof record.mime === 'string' ? record.mime : undefined,
    fileName:
      typeof record.file_name === 'string'
        ? record.file_name
        : typeof record.fileName === 'string'
          ? record.fileName
          : undefined,
    size: typeof record.size === 'number' ? record.size : undefined,
  }
}

function blocksFromRichBlocks(value: unknown): ChatRichBlock[] {
  if (!Array.isArray(value)) return []
  const blocks: ChatRichBlock[] = []
  for (const item of value) {
    const record = asRecord(item)
    if (!record || typeof record.kind !== 'string') continue
    if (record.kind === 'table' && Array.isArray(record.columns) && Array.isArray(record.rows)) {
      pushUnique(
        blocks,
        tableFromData(
          {
            columns: record.columns,
            rows: record.rows,
            total: record.total,
            limit: record.limit,
            offset: record.offset,
          },
          String(record.title || '表格结果'),
        ),
      )
      continue
    }
    if (record.kind === 'markdown' && typeof record.text === 'string') {
      pushUnique(blocks, { kind: 'markdown', title: String(record.title || '说明'), text: record.text })
      continue
    }
    if (record.kind === 'code' && typeof record.text === 'string') {
      pushUnique(blocks, {
        kind: 'code',
        title: String(record.title || '代码'),
        language: typeof record.language === 'string' ? record.language : 'text',
        text: record.text,
      })
      continue
    }
    if (record.kind === 'list' && Array.isArray(record.items)) {
      pushUnique(blocks, {
        kind: 'list',
        title: String(record.title || '列表'),
        items: record.items.map((entry) => String(entry)),
      })
      continue
    }
    if (record.kind === 'image' && typeof record.url === 'string') {
      const url = resolveUrl(record.url)
      if (!url) continue
      pushUnique(blocks, {
        kind: 'image',
        title: String(record.title || '图片'),
        url,
        caption: typeof record.caption === 'string' ? record.caption : undefined,
      })
      continue
    }
    if (record.kind === 'file') {
      pushUnique(blocks, fileBlockFromRecord(record, String(record.title || '附件')))
      continue
    }
    if (record.kind === 'links' && Array.isArray(record.links)) {
      const links: Array<{ title: string; url: string; source?: string }> = []
      for (const entry of record.links) {
        const link = asRecord(entry)
        if (!link || typeof link.url !== 'string' || !link.url) continue
        links.push({
          title: String(link.title || '链接'),
          url: link.url,
          ...(typeof link.source === 'string' ? { source: link.source } : {}),
        })
      }
      if (links.length) {
        pushUnique(blocks, { kind: 'links', title: String(record.title || '链接'), links })
      }
    }
  }
  return blocks
}

function collectImages(value: unknown, images: ChatRichBlock[]) {
  const record = asRecord(value)
  if (!record) return
  for (const key of ['annotated_url', 'snapshot_url', 'image_url', 'thumbnail_url', 'preview_url', 'url']) {
    const raw = record[key]
    if (typeof raw !== 'string' || !raw) continue
    const url = resolveUrl(raw)
    if (!url) continue
    pushUnique(images, {
      kind: 'image',
      title: String(record.title || key),
      url,
      caption: String(record.camera_name || record.source_name || record.caption || ''),
    })
  }
  for (const key of ['report', 'data', 'briefing', 'result', 'payload', 'draft']) {
    collectImages(record[key], images)
  }
  for (const key of ['report_images', 'images', 'items', 'cameras']) {
    const list = record[key]
    if (!Array.isArray(list)) continue
    for (const item of list) collectImages(item, images)
  }
}

function collectFiles(value: unknown, files: ChatRichBlock[]) {
  const record = asRecord(value)
  if (!record) return
  for (const key of ['file_path', 'export_path', 'download_path', 'local_path']) {
    const raw = record[key]
    if (typeof raw !== 'string' || !raw) continue
    pushUnique(files, fileBlockFromRecord({ path: raw, file_name: record.file_name || record.filename }, String(record.title || '文件')))
  }
  if (typeof record.file_id === 'string' && record.file_id) {
    pushUnique(
      files,
      fileBlockFromRecord(
        { url: `/api/docmate/download/${record.file_id}`, file_name: record.file_name },
        String(record.title || '文档'),
      ),
    )
  }
  for (const key of ['report', 'data', 'draft', 'result']) {
    collectFiles(record[key], files)
  }
}

function collectFromCardOrTool(value: unknown, blocks: ChatRichBlock[]) {
  const record = asRecord(value)
  if (!record) return

  blocks.push(...blocksFromRichBlocks(record.rich_blocks))

  const data = asRecord(record.data)
  if (data) {
    blocks.push(...blocksFromRichBlocks(data.rich_blocks))
    const nestedResult = asRecord(data.result)
    if (nestedResult) {
      const nestedData = asRecord(nestedResult.data)
      if (nestedData) {
        pushUnique(blocks, tableFromData(nestedData, String(record.title || data.title || '查询结果')))
      }
      blocks.push(...blocksFromRichBlocks(build_wacli_blocks_from_result(nestedResult)))
    }
    pushUnique(blocks, tableFromData(data, String(record.title || '查询结果')))
  }

  const result = asRecord(record.result)
  if (result) {
    const resultData = asRecord(result.data)
    if (resultData) pushUnique(blocks, tableFromData(resultData, '查询结果'))
    blocks.push(...blocksFromRichBlocks(build_wacli_blocks_from_result(result)))
  }

  if (typeof record.answer === 'string' && record.answer.trim()) {
    pushUnique(blocks, { kind: 'markdown', title: '知识库回答', text: record.answer })
  }

  const citations = Array.isArray(record.citations) ? record.citations : []
  if (citations.length) {
    const items = citations.map((item, index) => {
      const citation = asRecord(item)
      if (!citation) return `引用 ${index + 1}`
      const source = String(citation.source_file_name || citation.source || '知识库')
      const chunk = citation.chunk_index
      return chunk !== undefined ? `${source}#${chunk}` : source
    })
    pushUnique(blocks, { kind: 'list', title: '引用来源', items })
  }

  const reportLinks = Array.isArray(record.report_links) ? record.report_links : []
  if (reportLinks.length) {
    const links: Array<{ title: string; url: string; source?: string }> = []
    for (const item of reportLinks) {
      const link = asRecord(item)
      if (!link || typeof link.url !== 'string' || !link.url) continue
      links.push({
        title: String(link.title || '外部更新'),
        url: link.url,
        ...(typeof link.source === 'string' ? { source: link.source } : {}),
      })
    }
    if (links.length) pushUnique(blocks, { kind: 'links', title: '参考链接', links })
  }

  const images: ChatRichBlock[] = []
  collectImages(record, images)
  blocks.push(...images)

  const files: ChatRichBlock[] = []
  collectFiles(record, files)
  blocks.push(...files)
}

function build_wacli_blocks_from_result(result: Record<string, unknown>): ChatRichBlock[] {
  const blocks: ChatRichBlock[] = []
  const data = asRecord(result.data)
  if (!data) return blocks
  const stdout = typeof data.stdout === 'string' ? data.stdout.trim() : ''
  if (stdout) {
    pushUnique(blocks, { kind: 'code', title: '命令输出', language: 'text', text: stdout })
  }
  const fallbackRows = Array.isArray(data.fallback_rows) ? data.fallback_rows : []
  if (fallbackRows.length && typeof fallbackRows[0] === 'object' && fallbackRows[0]) {
    const columns = Object.keys(fallbackRows[0] as Record<string, unknown>)
    pushUnique(
      blocks,
      tableFromData({ columns, rows: fallbackRows, total: fallbackRows.length }, '本地库回退结果'),
    )
  }
  return blocks
}

export function extractChatRichBlocks(
  cards: Array<Record<string, unknown>> = [],
  toolResults: Array<Record<string, unknown>> = [],
  richBlocks: Array<Record<string, unknown>> = [],
): ChatRichBlock[] {
  const blocks: ChatRichBlock[] = []
  blocks.push(...blocksFromRichBlocks(richBlocks))
  for (const card of cards) collectFromCardOrTool(card, blocks)
  for (const result of toolResults) collectFromCardOrTool(result, blocks)
  return blocks
}

export function formatCellValue(value: unknown): string {
  if (value === null || value === undefined) return ''
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

export function formatFileSize(size?: number): string {
  if (!size || size <= 0) return ''
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

export function fileIconLabel(mime?: string, fileName?: string): string {
  const name = (fileName || '').toLowerCase()
  const type = (mime || '').toLowerCase()
  if (type.startsWith('image/') || /\.(png|jpe?g|gif|webp)$/.test(name)) return '🖼️'
  if (type.includes('pdf') || name.endsWith('.pdf')) return '📄'
  if (type.includes('sheet') || type.includes('excel') || /\.xlsx?$/.test(name)) return '📊'
  if (type.includes('word') || name.endsWith('.docx')) return '📝'
  if (type.includes('zip') || name.endsWith('.zip')) return '🗜️'
  return '📎'
}
