const fs = require('fs')
const path = require('path')
const { execSync } = require('child_process')

const root = path.join(__dirname, '..')
const pkgPath = path.join(root, 'package.json')

function bumpPatchVersion(version) {
  const parts = version.split('.').map((p) => parseInt(p, 10))
  if (parts.length !== 3 || parts.some(Number.isNaN)) {
    throw new Error(`无法解析版本号: ${version}`)
  }
  parts[2] += 1
  return parts.join('.')
}

const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf-8'))
const oldVersion = pkg.version
const newVersion = bumpPatchVersion(oldVersion)

pkg.version = newVersion
fs.writeFileSync(pkgPath, `${JSON.stringify(pkg, null, 2)}\n`, 'utf-8')

console.log('')
console.log('='.repeat(60))
console.log(`版本升级: ${oldVersion} → ${newVersion}`)
console.log('='.repeat(60))
console.log('')

execSync('npm run build && node scripts/publish100.cjs', {
  cwd: root,
  stdio: 'inherit',
  shell: true,
})

console.log('')
console.log(`✓ 发布完成 v${newVersion}`)
console.log(`  精简运行包: publish100/`)
console.log(`  启动: 双击 publish100/DocMate.vbs`)
console.log('')
