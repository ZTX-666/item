#!/usr/bin/env node
const fs = require('fs')
const path = require('path')
const { execSync } = require('child_process')

const root = path.join(__dirname, '..')
const out = path.join(root, 'publish100')

const keep = new Set(['dist', 'electron', 'package.json', 'package-lock.json', 'DocMate.vbs', 'Start-DocMate.ps1', 'install-deps.bat'])

function rm(target) {
  fs.rmSync(target, { recursive: true, force: true })
}

function copy(src, dest) {
  const stat = fs.statSync(src)
  if (stat.isDirectory()) {
    fs.mkdirSync(dest, { recursive: true })
    for (const name of fs.readdirSync(src)) copy(path.join(src, name), path.join(dest, name))
  } else {
    fs.mkdirSync(path.dirname(dest), { recursive: true })
    fs.copyFileSync(src, dest)
  }
}

rm(out)
fs.mkdirSync(out, { recursive: true })

for (const name of keep) {
  const src = path.join(root, name)
  if (fs.existsSync(src)) copy(src, path.join(out, name))
}

const pkgPath = path.join(out, 'package.json')
const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf-8'))
pkg.scripts = { start: 'electron .' }
delete pkg.devDependencies
pkg.dependencies = {
  '@tiptap/core': pkg.dependencies['@tiptap/core'],
  '@tiptap/extension-placeholder': pkg.dependencies['@tiptap/extension-placeholder'],
  '@tiptap/pm': pkg.dependencies['@tiptap/pm'],
  '@tiptap/starter-kit': pkg.dependencies['@tiptap/starter-kit'],
  '@tiptap/vue-3': pkg.dependencies['@tiptap/vue-3'],
  '@xenova/transformers': pkg.dependencies['@xenova/transformers'],
  docx: pkg.dependencies.docx,
  mammoth: pkg.dependencies.mammoth,
  marked: pkg.dependencies.marked,
  vue: pkg.dependencies.vue,
  electron: '^34.0.0',
}
fs.writeFileSync(pkgPath, `${JSON.stringify(pkg, null, 2)}\n`, 'utf-8')

fs.writeFileSync(path.join(out, '使用说明.txt'), `DocMate v${pkg.version} — publish100

【推荐启动】双击 DocMate.vbs 或运行 npm start

【环境配置】
启动后点击右下角“环境配置”，可自定义：
· 文稿路径
· 知识库路径
· 长期记忆路径
· Whisper 模型缓存路径

默认数据目录：C:\\DocMateData
Whisper 模型不内置在 exe 中，用户点击“自动配置/下载 Whisper”后按需下载。
`, 'utf-8')

console.log('Installing production dependencies for publish100...')
execSync('npm install --omit=dev --no-audit --no-fund', { cwd: out, stdio: 'inherit', shell: true })
console.log(`publish100 ready: ${out}`)
