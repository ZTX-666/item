import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import assert from 'node:assert/strict'

const root = new URL('..', import.meta.url).pathname
const read = (path) => readFileSync(join(root, path), 'utf8')

const whatsappPage = read('src/pages/WhatsAppOpsPage.vue')
const packageJson = read('package.json')

for (const label of [
  'doctor json',
  'auth status json',
  'search media',
  'search documents',
  'contacts search',
  'unread chats',
  'group search',
  'history fill dry-run',
  'store stats',
  'calls list',
  'channels list',
]) {
  assert(whatsappPage.includes(`label: '${label}'`), `WhatsApp command panel must include ${label}`)
}

for (const token of ['--read-only', '--json', '--has-media', '--type', 'document', 'store', 'stats']) {
  assert(whatsappPage.includes(`'${token}'`), `WhatsApp command panel should use safe structured option ${token}`)
}

assert(
  packageJson.includes('"test:whatsapp-ops"'),
  'frontend package must expose a WhatsApp ops contract test',
)
