const baseUrl = process.env.VITE_CHITUNG_CENTER_URL || 'http://127.0.0.1:8999'

const checks = [
  ['health', '/health'],
  ['runtime', '/api/runtime/status'],
  ['app config', '/api/config/app'],
  ['hazards', '/api/hazards?limit=5'],
  ['form templates', '/api/forms/templates?query=T006&limit=5'],
  ['workbench', '/api/workbench/summary'],
  ['llm settings', '/api/settings/llm'],
  ['connector settings', '/api/settings/connectors'],
]

let failed = false

for (const [name, path] of checks) {
  try {
    const response = await fetch(`${baseUrl}${path}`)
    if (!response.ok) {
      failed = true
      console.error(`[FAIL] ${name}: HTTP ${response.status}`)
      continue
    }
    const data = await response.json()
    console.log(`[OK] ${name}: ${JSON.stringify(summarize(data))}`)
  } catch (error) {
    failed = true
    console.error(`[FAIL] ${name}: ${error instanceof Error ? error.message : String(error)}`)
  }
}

if (failed) {
  process.exitCode = 1
}

function summarize(data) {
  if (data?.service) {
    return { service: data.service, llm_configured: data.llm_configured }
  }
  if (data?.ready !== undefined) {
    return { ready: data.ready, toolbox_ok: data.toolbox?.ok, llm: data.llm?.configured }
  }
  if (data?.project) {
    return { project: data.project.name, cameras: data.cameras?.length, contractors: data.contractors?.length }
  }
  if (Array.isArray(data?.items)) {
    return { items: data.items.length, ok: data.ok }
  }
  if (data?.status) {
    return data.status
  }
  if (data?.configured !== undefined) {
    return { configured: data.configured, model: data.model }
  }
  if (data?.whatsapp && data?.feishu) {
    return {
      whatsapp: data.whatsapp.configured,
      feishu: data.feishu.configured,
      restart: data.requires_toolbox_restart,
    }
  }
  return data
}
