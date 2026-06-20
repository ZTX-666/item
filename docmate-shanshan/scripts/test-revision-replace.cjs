#!/usr/bin/env node
/**
 * 验证修改方案归一化与文本对齐（不启动 Electron UI）
 * 用法: node scripts/test-revision-replace.cjs
 */
const { alignOldText } = require('../electron/text-match.cjs')

const sampleDoc = `关于推进数字化转型的工作方案
一、总体目标。以数字化为引领，提升管理效率。
二、重点任务。建设统一数据平台，推进智慧工地。`

function normalizeRevisionResult(result, documentText, selectedText) {
  const selected = selectedText?.trim()
  if (selected) {
    result.old_text = selected
    result.match_confidence = documentText.includes(selected) ? 'ok' : 'failed'
  } else {
    const alignedOld = alignOldText(documentText, result.old_text || '')
    const matchFailed = alignedOld && documentText && !documentText.includes(alignedOld)
    result.old_text = alignedOld || result.old_text
    result.match_confidence = matchFailed ? 'failed' : 'ok'
  }

  const best = (result.options || []).find((opt) => opt.text || opt.new_text)
  result.options = best
    ? [{
        id: best.id || 'final',
        label: best.label || '最终方案',
        text: best.text || best.new_text || '',
      }]
    : []
  return result
}

function assert(condition, message) {
  if (!condition) {
    console.error('✗', message)
    process.exit(1)
  }
  console.log('✓', message)
}

function main() {
  console.log('=== DocMate 修改替换链路测试 ===\n')

  const selected = '一、总体目标。以数字化为引领，提升管理效率。'
  const llmResult = {
    old_text: '总体目标段落（LLM 偏差描述）',
    options: [
      { id: 'opt1', label: '方案一', text: '一、总体目标。深入贯彻数字化战略，全面提升管理效能。' },
      { id: 'opt2', label: '方案二', text: '一、总体目标。以数字化为引领，显著增强管理效率。' },
      { id: 'opt3', label: '方案三', text: '一、总体目标。推进数字化，优化管理。' },
    ],
    reason: 'test',
  }

  const normalized = normalizeRevisionResult({ ...llmResult }, sampleDoc, selected)

  assert(normalized.old_text === selected, 'old_text 应等于用户选中文本')
  assert(normalized.options.length === 1, '只保留 1 个最终方案')
  assert(normalized.options[0].text.includes('管理效能') || normalized.options[0].text.includes('管理效率'), '保留第一个有效方案文本')
  assert(normalized.match_confidence === 'ok', '选中文本在文档中应匹配成功')

  const noSelection = normalizeRevisionResult(
    {
      old_text: '以数字化为引领，提升管理效率',
      options: [{ id: 'a', text: '新文本' }, { id: 'b', text: '另一文本' }],
    },
    sampleDoc,
    '',
  )
  assert(noSelection.options.length === 1, '无选区时也仅保留 1 个方案')
  assert(sampleDoc.includes(noSelection.old_text), '无选区时 old_text 应对齐到文档')

  const aligned = alignOldText(sampleDoc, '以数字化为引领，提升管理效率')
  assert(sampleDoc.includes(aligned), 'alignOldText 应找回文档中的原文片段')

  console.log('\n全部通过')
}

main()
