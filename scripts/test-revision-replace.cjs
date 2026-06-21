#!/usr/bin/env node
const { alignOldText } = require('../electron/text-match.cjs')

const sampleDoc = `关于推进数字化转型的工作方案
一、总体目标。以数字化为引领，提升管理效率。
二、重点任务。建设统一数据平台，推进智慧工地。`

function assert(condition, message) {
  if (!condition) {
    console.error('✗', message)
    process.exit(1)
  }
  console.log('✓', message)
}

function main() {
  console.log('=== DocMate 修改替换链路测试 ===\n')
  const aligned = alignOldText(sampleDoc, '以数字化为引领，提升管理效率')
  assert(sampleDoc.includes(aligned), 'alignOldText 应找回文档中的原文片段')
  console.log('\n全部通过')
}

main()
