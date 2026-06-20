const fs = require('fs')
const path = require('path')

const root = path.join(__dirname, '..')
const src = path.join(root, 'release', 'win-unpacked')
const dest = path.join(root, 'publish2')

function copyDir(from, to) {
  fs.mkdirSync(to, { recursive: true })
  for (const entry of fs.readdirSync(from, { withFileTypes: true })) {
    const srcPath = path.join(from, entry.name)
    const destPath = path.join(to, entry.name)
    if (entry.isDirectory()) {
      copyDir(srcPath, destPath)
    } else {
      fs.copyFileSync(srcPath, destPath)
    }
  }
}

if (!fs.existsSync(src)) {
  console.error('未找到 release/win-unpacked，请先运行 npm run pack')
  process.exit(1)
}

if (fs.existsSync(dest)) {
  fs.rmSync(dest, { recursive: true, force: true })
}

copyDir(src, dest)

const readme = `# 文稿修改助手 v${require('../package.json').version}

## 启动方式
双击「文稿修改助手.exe」即可运行。

## 功能
- 左侧：文件管理器
- 中间：Tiptap 文档编辑器
- 右侧：Agent（修改 / 润色 / 问答 / 风险 / 口语 / 表格）

## 大模型配置
Agent 面板 → ⚙️ → 填写 API 并保存

## 方案数量
配置中可选 1–4 个方案，默认 1 个（直接应用）
`

fs.writeFileSync(path.join(dest, '使用说明.txt'), readme, 'utf-8')
console.log(`已发布到: ${dest}`)
