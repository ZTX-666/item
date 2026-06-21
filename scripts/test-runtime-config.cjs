#!/usr/bin/env node
const assert = require('assert')
const path = require('path')
const {
  defaultConfig,
  readRuntimeConfig,
  writeRuntimeConfig,
} = require('../electron/runtime-config.cjs')
const { alignOldText } = require('../electron/text-match.cjs')

const fakeApp = {
  getPath(name) {
    if (name === 'userData') return path.join(__dirname, '..', '.tmp-test-userdata')
    throw new Error(`unexpected path ${name}`)
  },
}

const config = writeRuntimeConfig(fakeApp, {
  baseDir: path.join(__dirname, '..', '.tmp-docmate-data'),
})
const readBack = readRuntimeConfig(fakeApp)

assert.strictEqual(readBack.baseDir, config.baseDir, 'runtime config should persist')
assert.ok(readBack.workspaceDir.endsWith('workspace'), 'workspace defaults under base dir')
assert.ok(defaultConfig().baseDir.includes('DocMateData'), 'default base dir should be DocMateData')

const sample = '一、总体目标。以数字化为引领，提升管理效率。'
assert.ok(sample.includes(alignOldText(sample, '以数字化为引领，提升管理效率')), 'text alignment should still work')

console.log('runtime config smoke test passed')
