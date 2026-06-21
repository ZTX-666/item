#!/usr/bin/env node
const fs = require('fs')
const path = require('path')
const { execSync } = require('child_process')

const root = path.join(__dirname, '..')
const pkgPath = path.join(root, 'package.json')

function bumpPatch(version) {
  const parts = version.split('.').map((part) => Number(part))
  if (parts.length !== 3 || parts.some(Number.isNaN)) throw new Error(`无法解析版本号: ${version}`)
  parts[2] += 1
  return parts.join('.')
}

const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf-8'))
const oldVersion = pkg.version
pkg.version = bumpPatch(oldVersion)
fs.writeFileSync(pkgPath, `${JSON.stringify(pkg, null, 2)}\n`, 'utf-8')

console.log(`版本升级: ${oldVersion} -> ${pkg.version}`)
execSync('node scripts/publish100.cjs', { cwd: root, stdio: 'inherit', shell: true })
console.log(`发布完成 v${pkg.version}`)
