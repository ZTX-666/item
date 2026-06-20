const baseUrl = process.env.VITE_CHITUNG_CENTER_URL || 'http://127.0.0.1:8999'

const checks = [
  {
    name: 'llm settings test',
    path: '/api/settings/llm/test',
    body: null,
  },
  {
    name: 'document revision preview',
    path: '/api/documents/revision-preview',
    body: {
      title: 'Smoke Test',
      source: 'smoke',
      instruction: '正式化',
      original_text: '护栏没弄好，需要处理。',
      revised_text: '现场临边防护存在缺失，请责任单位立即安排整改并提交复查资料。',
    },
  },
  {
    name: 'smart form draft',
    path: '/api/forms/smart-draft',
    body: {
      query: 'T006 临边',
      source_text: 'B2 区临边护栏缺失，需要整改。',
      instruction: '生成安全表格草稿。',
    },
  },
  {
    name: 'daily report generation',
    path: '/api/reports/generate',
    body: {
      report_type: 'daily_safety',
      title: 'Smoke Test Daily Report',
    },
  },
]

let failed = false

for (const check of checks) {
  try {
    const response = await fetch(`${baseUrl}${check.path}`, {
      method: 'POST',
      headers: check.body ? { 'Content-Type': 'application/json' } : undefined,
      body: check.body ? JSON.stringify(check.body) : undefined,
    })
    if (!response.ok) {
      failed = true
      console.error(`[FAIL] ${check.name}: HTTP ${response.status}`)
      continue
    }
    const data = await response.json()
    console.log(`[OK] ${check.name}: ${JSON.stringify(summarize(data))}`)
  } catch (error) {
    failed = true
    console.error(`[FAIL] ${check.name}: ${error instanceof Error ? error.message : String(error)}`)
  }
}

if (failed) {
  process.exitCode = 1
}

function summarize(data) {
  if (data?.lines) {
    return { additions: data.additions, deletions: data.deletions, lines: data.lines.length }
  }
  if (data?.model !== undefined && data?.message) {
    return { ok: data.ok, model: data.model, message: data.message }
  }
  if (data?.selected_template) {
    return {
      ok: data.ok,
      template: data.selected_template.id,
      fields: Object.keys(data.prefill?.fields || {}).length,
      hasDocx: Boolean(data.docx_draft?.output_path),
    }
  }
  if (data?.report_type) {
    return { ok: data.ok, reportType: data.report_type, hasOutput: Boolean(data.output_path) }
  }
  return data
}
