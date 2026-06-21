#!/usr/bin/env node
const fs = require('fs')
const path = require('path')

const root = path.join(__dirname, '..')
const indexHtml = path.join(root, 'dist', 'index.html')
const electronMain = path.join(root, 'electron', 'main.cjs')

if (!fs.existsSync(indexHtml)) {
  console.error('dist/index.html 不存在。当前包缺少前端源码，无法重新构建 dist。')
  process.exit(1)
}

if (!fs.existsSync(electronMain)) {
  console.error('electron/main.cjs 不存在。')
  process.exit(1)
}

console.log('dist and electron files are present')
