#!/usr/bin/env node
/**
 * 本地测试大模型调用链路（不启动 Electron UI）
 * 用法: node scripts/test-llm.cjs
 * 环境变量: DOCMATE_API_KEY, DOCMATE_API_URL, DOCMATE_MODEL
 */
const { processTask } = require('../electron/ai-services.cjs')
const { testLlmConnection } = require('../electron/llm.cjs')

const settings = {
  apiUrl: process.env.DOCMATE_API_URL || 'https://ark.cn-beijing.volces.com/api/v3/chat/completions',
  apiKey: process.env.DOCMATE_API_KEY || '',
  model: process.env.DOCMATE_MODEL || 'doubao-pro-32k',
  useApi: !!process.env.DOCMATE_API_KEY,
  optionCount: 1,
}

const sampleDoc = `关于推进数字化转型的工作方案
一、总体目标。以数字化为引领，提升管理效率。
二、重点任务。建设统一数据平台，推进智慧工地。`

async function main() {
  console.log('=== DocMate LLM 链路测试 ===')
  console.log('useApi:', settings.useApi)
  console.log('model:', settings.model)

  if (settings.useApi) {
    const conn = await testLlmConnection(settings)
    console.log('连接测试:', conn.ok ? '✓' : '✗', conn.message)
    if (!conn.ok) process.exit(1)
  } else {
    console.log('未设置 DOCMATE_API_KEY，使用本地模拟模式')
  }

  const chunks = []
  const onChunk = (c) => {
    chunks.push(c)
    process.stdout.write(c)
  }

  const routeResult = await processTask(
    settings,
    'route',
    {
      user_input: '把第一段改得更正式',
      document_text: sampleDoc,
      selected_text: '',
      history: [],
    },
    '',
    onChunk,
  )

  console.log('\n\n--- route 结果 ---')
  console.log(JSON.stringify(routeResult, null, 2))

  // 验证可 JSON 序列化（模拟 IPC 返回）
  JSON.parse(JSON.stringify(routeResult))
  console.log('\n✓ 结果可 IPC 序列化')
}

main().catch((err) => {
  console.error('测试失败:', err.message)
  process.exit(1)
})
