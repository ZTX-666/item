<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import QRCode from 'qrcode'
import {
  getWhatsAppAgentListenerStatus,
  getWhatsAppAuthStatus,
  getWhatsAppGroups,
  ingestWhatsAppSearch,
  listWhatsAppSqlTables,
  logoutWhatsAppAuth,
  refreshWhatsAppGroups,
  runWhatsAppCommand,
  runWhatsAppSqlSelect,
  searchWhatsAppMessages,
  startWhatsAppAgentListener,
  startWhatsAppAuth,
  stopWhatsAppAgentListener,
  stopWhatsAppAuth,
  type WhatsAppCommandResultData,
  type WhatsAppSqlSelectData,
} from '../services/chitungApi'

type BrowseTab = 'messages' | 'attachments' | 'chats'
type NoticeTone = 'info' | 'warning' | 'error' | 'success'

interface Notice {
  tone: NoticeTone
  text: string
}

interface QuickCommand {
  label: string
  args: string[]
  group: string
}

const query = ref('整改')
const hkPhone = ref('')
const authLoading = ref(false)
const syncLoading = ref(false)
const browseLoading = ref(false)
const ingesting = ref(false)
const sqlLoading = ref(false)
const commandLoading = ref(false)

const qrDataUrl = ref('')
const authStatus = ref<Record<string, unknown> | null>(null)
const syncStatus = ref<Record<string, unknown> | null>(null)
const authNotice = ref<Notice | null>(null)
const syncNotice = ref<Notice | null>(null)
const browseNotice = ref<Notice | null>(null)
const sqlNotice = ref<Notice | null>(null)
const commandNotice = ref<Notice | null>(null)
const ingestNotice = ref<Notice | null>(null)

const messageRows = ref<Array<Record<string, unknown>>>([])
const groupRows = ref<Array<Record<string, unknown>>>([])
const activeBrowseTab = ref<BrowseTab>('messages')

const sqlTables = ref<string[]>([])
const selectedSqlTable = ref('messages')
const sqlInput = ref('SELECT * FROM messages ORDER BY ts DESC')
const sqlLimit = ref(100)
const sqlResult = ref<WhatsAppSqlSelectData>({ columns: [], rows: [] })

const commandOutput = ref('等待执行快捷命令。')
const authTimer = ref<number | null>(null)

const browseTabs: Array<{ id: BrowseTab; label: string }> = [
  { id: 'messages', label: '消息' },
  { id: 'attachments', label: '附件' },
  { id: 'chats', label: '聊天列表' },
]

const quickCommands: QuickCommand[] = [
  { group: 'Start', label: 'doctor json', args: ['--read-only', '--json', 'doctor'] },
  { group: 'Start', label: 'doctor', args: ['doctor'] },
  { group: 'Start', label: 'version', args: ['version'] },
  { group: 'Start', label: 'docs', args: ['docs'] },
  { group: 'Start', label: 'help messages', args: ['help', 'messages'] },
  { group: 'Auth & Sync', label: 'auth status json', args: ['--read-only', '--json', 'auth', 'status'] },
  { group: 'Auth & Sync', label: 'auth status', args: ['auth', 'status'] },
  { group: 'Auth & Sync', label: 'sync help', args: ['sync', '--help'] },
  { group: 'Messages', label: 'message search', args: ['--read-only', '--json', 'messages', 'search', '{query}', '--limit', '20'] },
  { group: 'Messages', label: 'search media', args: ['--read-only', '--json', 'messages', 'search', '{query}', '--has-media', '--limit', '20'] },
  { group: 'Messages', label: 'search documents', args: ['--read-only', '--json', 'messages', 'search', '{query}', '--type', 'document', '--limit', '20'] },
  { group: 'Messages', label: 'starred', args: ['--read-only', '--json', 'messages', 'starred', '--limit', '20'] },
  { group: 'Chats', label: 'chat list', args: ['--read-only', '--json', 'chats', 'list'] },
  { group: 'Chats', label: 'chat search', args: ['--read-only', '--json', 'chats', 'list', '--query', '{query}', '--limit', '50'] },
  { group: 'Chats', label: 'unread chats', args: ['--read-only', '--json', 'chats', 'list', '--unread', '--limit', '50'] },
  { group: 'Contacts', label: 'contacts search', args: ['--read-only', '--json', 'contacts', 'search', '{query}', '--limit', '50'] },
  { group: 'Groups', label: 'group list', args: ['--read-only', '--json', 'groups', 'list'] },
  { group: 'Groups', label: 'group search', args: ['--read-only', '--json', 'groups', 'list', '--query', '{query}', '--limit', '50'] },
  { group: 'History', label: 'coverage', args: ['--read-only', '--json', 'history', 'coverage', '--query', '{query}', '--limit', '50'] },
  { group: 'History', label: 'history fill dry-run', args: ['--read-only', '--json', 'history', 'fill', '--dry-run', '--limit', '20'] },
  { group: 'Store', label: 'store stats', args: ['--read-only', '--json', 'store', 'stats'] },
  { group: 'Calls', label: 'calls list', args: ['--read-only', '--json', 'calls', 'list', '--limit', '20'] },
  { group: 'Channels', label: 'channels list', args: ['--read-only', '--json', 'channels', 'list'] },
]

const selectedCommand = ref<QuickCommand>(quickCommands[0])

const selectedCommandLine = computed(() => `wacli ${resolvedCommandArgs(selectedCommand.value).join(' ')}`)

const authStatusText = computed(() => stringValue(authStatus.value, ['status', 'state'], '未连接'))
const syncStatusText = computed(() => stringValue(syncStatus.value, ['status', 'state'], '未启动'))
const pairingCode = computed(() => stringValue(authStatus.value, ['pairing_code', 'pairingCode', 'code'], '等待配对码'))
const currentPhone = computed(() => stringValue(authStatus.value, ['phone', 'current_phone', 'account'], '未选择'))
const authLogs = computed(() => arrayValue(authStatus.value, ['logs', 'log']).slice(-8))
const syncLogs = computed(() => arrayValue(syncStatus.value, ['logs', 'log']).slice(-8))

const overviewCards = computed(() => [
  {
    label: '认证状态',
    value: authStatusText.value,
    helper: currentPhone.value,
    tone: authStatusText.value.includes('已') || authStatusText.value.includes('sync') ? 'green' : 'red',
  },
  {
    label: '同步监听',
    value: syncStatusText.value,
    helper: `消息 ${stringValue(syncStatus.value, ['messages_synced', 'synced', 'count'], '0')}`,
    tone: syncStatusText.value.includes('running') || syncStatusText.value.includes('启动') ? 'green' : 'orange',
  },
  {
    label: '聊天列表',
    value: String(groupRows.value.length),
    helper: '可搜索、刷新、选择',
    tone: 'blue',
  },
  {
    label: '消息结果',
    value: String(messageRows.value.length),
    helper: query.value || '等待关键词',
    tone: 'red',
  },
])

const browseColumns = computed(() => {
  if (activeBrowseTab.value === 'chats') return ['名称', 'ID', '成员', '状态']
  if (activeBrowseTab.value === 'attachments') return ['日期', '聊天', '文件', '类型', '状态']
  return ['日期', '聊天', '发送人', '内容', 'ID']
})

const browseTableRows = computed<Array<Record<string, string>>>(() => {
  if (activeBrowseTab.value === 'chats') {
    return groupRows.value.map((row) => ({
      名称: stringValue(row, ['name', 'Name', 'subject'], '未命名聊天'),
      ID: stringValue(row, ['id', 'jid', 'JID'], '—'),
      成员: stringValue(row, ['participants', 'member_count', 'members'], '—'),
      状态: boolishValue(row, ['archived', 'is_archived']) ? '已归档' : '活跃',
    }))
  }

  if (activeBrowseTab.value === 'attachments') {
    return messageRows.value
      .filter(hasAttachment)
      .map((row) => ({
        日期: stringValue(row, ['message_date', 'messageDate', 'date', 'timestamp'], '—'),
        聊天: stringValue(row, ['chat_name', 'chatName', 'chat_id', 'chatJid'], '—'),
        文件: stringValue(row, ['attachment_filename', 'attachmentFilename', 'filename', 'file_name'], '未命名附件'),
        类型: stringValue(row, ['attachment_type', 'attachmentType', 'mime', 'attachment_mime'], '—'),
        状态: stringValue(row, ['attachment_status', 'attachmentStatus', 'status'], '等待补全'),
      }))
  }

  return messageRows.value.map((row) => ({
    日期: stringValue(row, ['message_date', 'messageDate', 'date', 'timestamp'], '—'),
    聊天: stringValue(row, ['chat_name', 'chatName', 'chat_id', 'chatJid'], '—'),
    发送人: stringValue(row, ['sender_name', 'senderName', 'sender', 'from'], '—'),
    内容: stringValue(row, ['text', 'message_text', 'messageText', 'content'], '(无文本)'),
    ID: stringValue(row, ['message_id', 'msg_id', 'id'], '—'),
  }))
})

const sqlResultColumns = computed(() => {
  if (sqlResult.value.columns.length) return sqlResult.value.columns
  const first = sqlResult.value.rows[0]
  return first ? Object.keys(first) : []
})

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' ? (value as Record<string, unknown>) : {}
}

function toolData(resp: Record<string, unknown>): Record<string, unknown> {
  return asRecord(resp.data ?? resp)
}

function toolOk(resp: Record<string, unknown>): boolean {
  return resp.ok !== false
}

function responseText(resp: Record<string, unknown>, fallback: string): string {
  return stringValue(resp, ['summary', 'error', 'message'], fallback)
}

function authStatusValue(record: Record<string, unknown> | null): string {
  return stringValue(record, ['status', 'state'], '').toLowerCase()
}

function authFailureText(record: Record<string, unknown> | null): string {
  return stringValue(record, ['last_error', 'error', 'message'], '')
}

function isQrExpired(record: Record<string, unknown> | null): boolean {
  const status = authStatusValue(record)
  const failure = authFailureText(record).toLowerCase()
  return status === 'qr_timed_out' || failure.includes('qr code timed out')
}

function shouldShowQr(record: Record<string, unknown> | null): boolean {
  const status = authStatusValue(record)
  return !['failed', 'qr_timed_out', 'ended', 'stopped', 'logged_out'].includes(status)
}

async function renderAuthQr(record: Record<string, unknown> | null) {
  await renderQr(shouldShowQr(record) ? record?.qr_payload : '')
}

function stringValue(record: Record<string, unknown> | null, keys: string[], fallback: string): string {
  if (!record) return fallback
  for (const key of keys) {
    const value = record[key]
    if (value !== undefined && value !== null && value !== '') return String(value)
  }
  return fallback
}

function boolishValue(record: Record<string, unknown>, keys: string[]): boolean {
  return keys.some((key) => record[key] === true || record[key] === 'true' || record[key] === 1)
}

function arrayValue(record: Record<string, unknown> | null, keys: string[]): unknown[] {
  if (!record) return []
  for (const key of keys) {
    const value = record[key]
    if (Array.isArray(value)) return value
  }
  return []
}

function arrayFromData(data: Record<string, unknown>, keys: string[]): Array<Record<string, unknown>> {
  for (const key of keys) {
    const value = data[key]
    if (Array.isArray(value)) return value.map(asRecord)
  }
  return []
}

function hasAttachment(row: Record<string, unknown>): boolean {
  return [
    'attachment_filename',
    'attachmentFilename',
    'filename',
    'file_name',
    'attachment_type',
    'attachmentType',
    'attachment_local_path',
  ].some((key) => Boolean(row[key]))
}

function setTab(tab: BrowseTab) {
  activeBrowseTab.value = tab
  if ((tab === 'chats' && !groupRows.value.length) || (tab !== 'chats' && !messageRows.value.length)) {
    void loadBrowseData(false)
  }
}

function selectOverview(target: string) {
  document.getElementById(target)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

async function renderQr(payload: unknown) {
  const text = typeof payload === 'string' ? payload : ''
  qrDataUrl.value = text ? await QRCode.toDataURL(text, { width: 220, margin: 1 }) : ''
}

async function pollAuth() {
  try {
    const resp = await getWhatsAppAuthStatus(true)
    authStatus.value = toolData(resp)
    await renderAuthQr(authStatus.value)
    if (isQrExpired(authStatus.value)) {
      authNotice.value = { tone: 'warning', text: '二维码已过期，请重新生成。' }
      return
    }
    if (authStatusValue(authStatus.value) === 'failed') {
      authNotice.value = { tone: 'error', text: authFailureText(authStatus.value) || '认证流程失败，请重新生成二维码。' }
      return
    }
    authNotice.value = null
  } catch (error) {
    authNotice.value = {
      tone: 'warning',
      text: `认证状态不可用：${error instanceof Error ? error.message : String(error)}`,
    }
  }
}

async function pollSync() {
  try {
    const resp = await getWhatsAppAgentListenerStatus(true)
    syncStatus.value = toolData(resp)
    syncNotice.value = null
  } catch (error) {
    syncNotice.value = {
      tone: 'warning',
      text: `同步监听不可用：${error instanceof Error ? error.message : String(error)}`,
    }
  }
}

function startAuthPoller() {
  if (authTimer.value) window.clearInterval(authTimer.value)
  authTimer.value = window.setInterval(() => void pollAuth(), 3000)
}

async function startQrLogin(mode: 'qr' | 'phone') {
  authLoading.value = true
  authNotice.value = null
  try {
    const resp = await startWhatsAppAuth(
      mode === 'phone'
        ? { phone: hkPhone.value || undefined, mode }
        : { mode },
    )
    authStatus.value = toolData(resp)
    await renderAuthQr(authStatus.value)
    if (!toolOk(resp)) {
      authNotice.value = { tone: 'error', text: responseText(resp, '登录配对启动失败。') }
      return
    }
    authNotice.value = { tone: 'success', text: mode === 'phone' ? '已请求配对码。' : '已请求二维码。' }
    startAuthPoller()
  } catch (error) {
    authNotice.value = {
      tone: 'error',
      text: `登录配对启动失败：${error instanceof Error ? error.message : String(error)}`,
    }
  } finally {
    authLoading.value = false
  }
}

async function stopLogin() {
  authLoading.value = true
  try {
    if (authTimer.value) window.clearInterval(authTimer.value)
    authTimer.value = null
    authStatus.value = toolData(await stopWhatsAppAuth('user_stop'))
    authNotice.value = { tone: 'info', text: '认证进程已请求停止。' }
  } catch (error) {
    authNotice.value = {
      tone: 'error',
      text: `停止认证失败：${error instanceof Error ? error.message : String(error)}`,
    }
  } finally {
    authLoading.value = false
  }
}

async function logoutLogin() {
  const ok = window.confirm('确认退出当前 WhatsApp 登录？退出后需要重新扫码或配对。')
  if (!ok) return
  authLoading.value = true
  try {
    authStatus.value = toolData(await logoutWhatsAppAuth(true))
    qrDataUrl.value = ''
    authNotice.value = { tone: 'info', text: '已请求退出当前登录。' }
  } catch (error) {
    authNotice.value = {
      tone: 'error',
      text: `退出登录失败：${error instanceof Error ? error.message : String(error)}`,
    }
  } finally {
    authLoading.value = false
  }
}

async function startSync() {
  syncLoading.value = true
  syncNotice.value = null
  try {
    const resp = await startWhatsAppAgentListener()
    syncStatus.value = toolData(resp)
    if (!toolOk(resp)) {
      syncNotice.value = { tone: 'warning', text: responseText(resp, '同步监听启动失败。') }
      return
    }
    syncNotice.value = { tone: 'success', text: '已请求启动同步监听。' }
  } catch (error) {
    syncNotice.value = {
      tone: 'error',
      text: `启动同步失败：${error instanceof Error ? error.message : String(error)}`,
    }
  } finally {
    syncLoading.value = false
  }
}

async function stopSync() {
  syncLoading.value = true
  try {
    syncStatus.value = toolData(await stopWhatsAppAgentListener('user_stop'))
    syncNotice.value = { tone: 'info', text: '已请求停止同步监听。' }
  } catch (error) {
    syncNotice.value = {
      tone: 'error',
      text: `停止同步失败：${error instanceof Error ? error.message : String(error)}`,
    }
  } finally {
    syncLoading.value = false
  }
}

async function loadBrowseData(refresh = false) {
  browseLoading.value = true
  browseNotice.value = null
  try {
    if (activeBrowseTab.value === 'chats') {
      const resp = refresh ? await refreshWhatsAppGroups() : await getWhatsAppGroups()
      const data = toolData(resp)
      if (!toolOk(resp)) {
        groupRows.value = []
        browseNotice.value = { tone: 'warning', text: responseText(resp, '聊天列表暂不可用。') }
        return
      }
      groupRows.value = arrayFromData(data, ['groups', 'items', 'rows', 'chats'])
      if (!groupRows.value.length) {
        browseNotice.value = { tone: 'info', text: '聊天列表为空，或本地归档服务尚未返回数据。' }
      }
      return
    }

    const resp = await searchWhatsAppMessages({ q: query.value, limit: 50 })
    const data = toolData(resp)
    if (!toolOk(resp)) {
      messageRows.value = []
      browseNotice.value = { tone: 'warning', text: responseText(resp, '消息检索暂不可用。') }
      return
    }
    messageRows.value = arrayFromData(data, ['rows', 'items', 'messages', 'results'])
    if (!messageRows.value.length) {
      browseNotice.value = { tone: 'info', text: '未检索到消息。可以换一个关键词或稍后刷新。' }
    }
  } catch (error) {
    browseNotice.value = {
      tone: 'warning',
      text: `数据浏览不可用：${error instanceof Error ? error.message : String(error)}`,
    }
    if (activeBrowseTab.value === 'chats') groupRows.value = []
    else messageRows.value = []
  } finally {
    browseLoading.value = false
  }
}

async function ingestSearch() {
  ingesting.value = true
  ingestNotice.value = null
  try {
    const resp = await ingestWhatsAppSearch({ q: query.value, limit: 20, autoRoute: true })
    ingestNotice.value = {
      tone: 'success',
      text: String(resp.summary || resp.message || '已提交到赤瞳工作流。'),
    }
  } catch (error) {
    ingestNotice.value = {
      tone: 'warning',
      text: `转入工作流不可用：${error instanceof Error ? error.message : String(error)}`,
    }
  } finally {
    ingesting.value = false
  }
}

async function loadSqlTables() {
  const result = await listWhatsAppSqlTables()
  const tables = result.data?.tables ?? []
  if (result.ok && tables.length) {
    sqlTables.value = tables
    sqlNotice.value = null
    return
  }

  sqlTables.value = ['messages', 'chats', 'attachments', 'contacts']
  sqlNotice.value = {
    tone: result.unavailable ? 'warning' : 'info',
    text: result.error || 'SQLite 表列表暂不可用，已显示常见表名占位。',
  }
}

function selectSqlTable(table: string) {
  selectedSqlTable.value = table
  sqlInput.value = `SELECT * FROM ${table} ORDER BY rowid DESC`
}

function isSafeSelect(sql: string): boolean {
  const trimmed = sql.trim().toLowerCase()
  if (!trimmed.startsWith('select')) return false
  if (trimmed.includes(';')) return false
  return !/\b(insert|update|delete|drop|alter|create|replace|attach|detach|vacuum|reindex)\b/.test(trimmed)
}

async function runSql() {
  if (!isSafeSelect(sqlInput.value)) {
    sqlNotice.value = { tone: 'error', text: '这里只允许单条 SELECT 查询。' }
    return
  }

  sqlLoading.value = true
  sqlNotice.value = null
  try {
    const result = await runWhatsAppSqlSelect({ sql: sqlInput.value, limit: sqlLimit.value })
    if (!result.ok) {
      sqlResult.value = { columns: [], rows: [] }
      sqlNotice.value = {
        tone: result.unavailable ? 'warning' : 'error',
        text: result.error || 'SQLite 查询暂不可用。',
      }
      return
    }
    sqlResult.value = result.data ?? { columns: [], rows: [] }
    if (!sqlResult.value.rows.length) {
      sqlNotice.value = { tone: 'info', text: '查询成功，但没有返回行。' }
    }
  } finally {
    sqlLoading.value = false
  }
}

function resolvedCommandArgs(command: QuickCommand): string[] {
  return command.args.map((arg) => (arg === '{query}' ? query.value.trim() || '整改' : arg))
}

function selectCommand(command: QuickCommand) {
  selectedCommand.value = command
}

function renderCommandResult(result: WhatsAppCommandResultData): string {
  const lines = [
    result.command?.length ? `$ wacli ${result.command.join(' ')}` : selectedCommandLine.value,
    result.code !== undefined || result.exit_code !== undefined ? `exit code: ${result.code ?? result.exit_code}` : '',
    result.stdout ? `\nstdout:\n${result.stdout}` : '',
    result.stderr ? `\nstderr:\n${result.stderr}` : '',
    result.output ? `\noutput:\n${result.output}` : '',
  ].filter(Boolean)
  return lines.join('\n')
}

async function executeCommand(command = selectedCommand.value) {
  selectCommand(command)
  commandLoading.value = true
  commandNotice.value = null
  try {
    const result = await runWhatsAppCommand({ args: resolvedCommandArgs(selectedCommand.value) })
    if (!result.ok) {
      commandOutput.value = result.error || '命令接口暂不可用。'
      commandNotice.value = {
        tone: result.unavailable ? 'warning' : 'error',
        text: result.error || '命令接口暂不可用。',
      }
      return
    }
    commandOutput.value = renderCommandResult(result.data ?? {})
    commandNotice.value = { tone: 'success', text: '命令已执行。' }
  } finally {
    commandLoading.value = false
  }
}

function rowKey(row: Record<string, unknown>, index: number): string {
  return String(row.ID || row.id || row.msg_id || row.message_id || row.名称 || index)
}

function cellValue(row: Record<string, unknown>, column: string): string {
  const value = row[column]
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

onMounted(async () => {
  startAuthPoller()
  await Promise.allSettled([pollAuth(), pollSync(), loadSqlTables(), loadBrowseData(false)])
})

onUnmounted(() => {
  if (authTimer.value) window.clearInterval(authTimer.value)
})
</script>

<template>
  <main class="whatsapp-workbench">
    <section class="lingxun-hero">
      <div>
        <p class="eyebrow">赤瞳灵讯</p>
        <h1>WhatsApp 控制台</h1>
        <p class="hero-copy">面向 wacli 本地归档、配对登录、SQLite 检索和命令诊断的统一操作台。</p>
      </div>
      <div class="hero-status">
        <span class="status-dot" :class="authStatusText.includes('已') ? 'status-dot--green' : 'status-dot--orange'" />
        <strong>{{ authStatusText }}</strong>
        <small>{{ syncStatusText }}</small>
      </div>
    </section>

    <section class="overview-grid" aria-label="总览入口">
      <button
        v-for="card in overviewCards"
        :key="card.label"
        class="overview-card"
        :class="`overview-card--${card.tone}`"
        @click="selectOverview(card.label === '认证状态' ? 'login' : card.label === '同步监听' ? 'commands' : 'browse')"
      >
        <span>{{ card.label }}</span>
        <strong>{{ card.value }}</strong>
        <small>{{ card.helper }}</small>
      </button>
    </section>

    <section id="login" class="module-panel login-panel">
      <div class="module-header">
        <div>
          <h2>登录配对</h2>
          <p>二维码 / 配对码占位与认证状态</p>
        </div>
        <div class="module-actions">
          <button class="secondary-button" :disabled="authLoading" @click="pollAuth">刷新状态</button>
          <button class="danger-button" :disabled="authLoading" @click="logoutLogin">退出登录</button>
        </div>
      </div>

      <div class="login-grid">
        <div class="qr-stage">
          <img v-if="qrDataUrl" :src="qrDataUrl" alt="WhatsApp login QR" />
          <div v-else class="qr-placeholder">
            <strong>QR</strong>
            <span>等待二维码 payload</span>
          </div>
        </div>
        <div class="pairing-card">
          <label>
            <span>香港手机号</span>
            <input v-model="hkPhone" placeholder="+85291234567" />
          </label>
          <div class="pairing-code">
            <span>配对码</span>
            <strong>{{ pairingCode }}</strong>
          </div>
          <div class="button-row">
            <button class="primary-button" :disabled="authLoading" @click="startQrLogin('qr')">生成二维码</button>
            <button class="primary-soft-button" :disabled="authLoading || !hkPhone" @click="startQrLogin('phone')">
              获取配对码
            </button>
            <button class="secondary-button" :disabled="authLoading" @click="stopLogin">停止认证</button>
          </div>
        </div>
        <div class="status-console">
          <div>
            <span>当前账号</span>
            <strong>{{ currentPhone }}</strong>
          </div>
          <div>
            <span>认证状态</span>
            <strong>{{ authStatusText }}</strong>
          </div>
          <pre>{{ authLogs.length ? JSON.stringify(authLogs, null, 2) : '暂无认证日志。' }}</pre>
        </div>
      </div>
      <p v-if="authNotice" class="notice" :class="`notice--${authNotice.tone}`">{{ authNotice.text }}</p>
    </section>

    <section id="browse" class="module-panel">
      <div class="module-header">
        <div>
          <h2>数据浏览</h2>
          <p>消息 / 附件 / 聊天列表 tabs 和搜索刷新</p>
        </div>
        <div class="module-actions">
          <button class="secondary-button" :disabled="browseLoading" @click="loadBrowseData(true)">刷新</button>
          <button class="primary-soft-button" :disabled="ingesting" @click="ingestSearch">
            {{ ingesting ? '转入中' : '转入工作流' }}
          </button>
        </div>
      </div>

      <div class="browse-toolbar">
        <div class="tab-list" role="tablist">
          <button
            v-for="tab in browseTabs"
            :key="tab.id"
            :class="{ active: activeBrowseTab === tab.id }"
            role="tab"
            @click="setTab(tab.id)"
          >
            {{ tab.label }}
          </button>
        </div>
        <input v-model="query" placeholder="搜索关键词，如：整改 / 发票 / 吊运" @keydown.enter="loadBrowseData(false)" />
        <button class="primary-button" :disabled="browseLoading" @click="loadBrowseData(false)">
          {{ browseLoading ? '搜索中' : '搜索' }}
        </button>
      </div>

      <p v-if="browseNotice" class="notice" :class="`notice--${browseNotice.tone}`">{{ browseNotice.text }}</p>
      <p v-if="ingestNotice" class="notice" :class="`notice--${ingestNotice.tone}`">{{ ingestNotice.text }}</p>

      <div class="data-table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th v-for="column in browseColumns" :key="column">{{ column }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, index) in browseTableRows" :key="rowKey(row, index)">
              <td v-for="column in browseColumns" :key="column">{{ cellValue(row, column) }}</td>
            </tr>
            <tr v-if="!browseTableRows.length">
              <td :colspan="browseColumns.length" class="empty-cell">暂无数据，页面仍可继续操作。</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section id="sql" class="module-panel sql-panel">
      <div class="module-header">
        <div>
          <h2>SQLite 查询</h2>
          <p>表列表、SELECT 输入和结果表</p>
        </div>
        <button class="secondary-button" :disabled="sqlLoading" @click="loadSqlTables">刷新表</button>
      </div>

      <div class="sql-layout">
        <aside class="table-list" aria-label="SQLite table list">
          <button
            v-for="table in sqlTables"
            :key="table"
            :class="{ active: selectedSqlTable === table }"
            @click="selectSqlTable(table)"
          >
            {{ table }}
          </button>
        </aside>
        <div class="sql-editor">
          <label>
            <span>SELECT</span>
            <textarea v-model="sqlInput" rows="5" spellcheck="false" />
          </label>
          <div class="button-row">
            <label class="limit-input">
              <span>Limit</span>
              <input v-model.number="sqlLimit" type="number" min="1" max="500" />
            </label>
            <button class="primary-button" :disabled="sqlLoading" @click="runSql">
              {{ sqlLoading ? '查询中' : '运行 SELECT' }}
            </button>
          </div>
        </div>
      </div>

      <p v-if="sqlNotice" class="notice" :class="`notice--${sqlNotice.tone}`">{{ sqlNotice.text }}</p>
      <div class="data-table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th v-for="column in sqlResultColumns" :key="column">{{ column }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, index) in sqlResult.rows" :key="rowKey(row, index)">
              <td v-for="column in sqlResultColumns" :key="column">{{ cellValue(row, column) }}</td>
            </tr>
            <tr v-if="!sqlResult.rows.length">
              <td :colspan="Math.max(sqlResultColumns.length, 1)" class="empty-cell">暂无查询结果。</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section id="commands" class="module-panel command-panel">
      <div class="module-header">
        <div>
          <h2>命令工具</h2>
          <p>快捷命令按钮、只读命令输入和输出</p>
        </div>
        <div class="module-actions">
          <button class="primary-button" :disabled="syncLoading" @click="startSync">启动同步</button>
          <button class="secondary-button" :disabled="syncLoading" @click="stopSync">停止同步</button>
          <button class="secondary-button" :disabled="syncLoading" @click="pollSync">刷新状态</button>
        </div>
      </div>

      <div class="command-grid">
        <div class="quick-command-list">
          <button
            v-for="command in quickCommands"
            :key="`${command.group}-${command.label}`"
            :class="{ active: selectedCommand.label === command.label }"
            @click="executeCommand(command)"
          >
            <span>{{ command.group }}</span>
            <strong>{{ command.label }}</strong>
          </button>
        </div>
        <div class="command-console">
          <label>
            <span>只读命令输入</span>
            <input :value="selectedCommandLine" readonly />
          </label>
          <button class="primary-soft-button" :disabled="commandLoading" @click="executeCommand()">
            {{ commandLoading ? '执行中' : '再次运行' }}
          </button>
          <pre>{{ commandOutput }}</pre>
        </div>
      </div>
      <p v-if="commandNotice" class="notice" :class="`notice--${commandNotice.tone}`">{{ commandNotice.text }}</p>
      <p v-if="syncNotice" class="notice" :class="`notice--${syncNotice.tone}`">{{ syncNotice.text }}</p>
      <pre class="sync-log">{{ syncLogs.length ? JSON.stringify(syncLogs, null, 2) : '暂无同步日志。' }}</pre>
    </section>

    <section class="module-panel footer-entries">
      <div>
        <p class="eyebrow">环境入口</p>
        <h2>配置环境 / 耀耀工厂</h2>
      </div>
      <div class="entry-actions">
        <a class="entry-button" href="#/center/settings">配置环境</a>
        <a class="entry-button entry-button--red" href="#/yaoyao/structured">耀耀工厂</a>
      </div>
    </section>
  </main>
</template>

<style scoped>
.whatsapp-workbench {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: calc(100vh - 56px);
  padding: 24px;
}

.lingxun-hero,
.module-panel,
.overview-card {
  background: var(--bg-white);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}

.lingxun-hero {
  align-items: center;
  background:
    linear-gradient(135deg, rgb(231 0 18 / 10%), transparent 36%),
    linear-gradient(90deg, #fff, #fff7f7);
  display: flex;
  justify-content: space-between;
  overflow: hidden;
  padding: 22px 24px;
  position: relative;
}

.lingxun-hero::after {
  background: var(--brand-red);
  border-radius: 50%;
  content: '';
  height: 160px;
  opacity: 0.08;
  position: absolute;
  right: -44px;
  top: -70px;
  width: 160px;
}

.lingxun-hero h1 {
  color: var(--text-primary);
  font-size: 26px;
  line-height: 1.2;
  margin: 2px 0 8px;
}

.hero-copy {
  color: var(--text-secondary);
  max-width: 640px;
}

.hero-status {
  align-items: center;
  background: var(--bg-white);
  border: 1px solid rgb(231 0 18 / 14%);
  border-radius: var(--radius-md);
  display: grid;
  gap: 2px 8px;
  grid-template-columns: auto 1fr;
  min-width: 180px;
  padding: 10px 12px;
  position: relative;
  z-index: 1;
}

.hero-status small {
  color: var(--text-secondary);
  grid-column: 2;
}

.overview-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.overview-card {
  border-left: 4px solid var(--border-normal);
  color: var(--text-primary);
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-height: 104px;
  padding: 14px;
  text-align: left;
}

.overview-card span,
.overview-card small,
.module-header p,
label span {
  color: var(--text-secondary);
  font-size: 12px;
}

.overview-card strong {
  font-size: 24px;
  line-height: 1.15;
}

.overview-card--red {
  border-left-color: var(--brand-red);
}

.overview-card--green {
  border-left-color: var(--brand-green);
}

.overview-card--orange {
  border-left-color: var(--brand-orange);
}

.overview-card--blue {
  border-left-color: var(--brand-cyan);
}

.module-panel {
  padding: 16px;
}

.module-header {
  align-items: flex-start;
  display: flex;
  gap: 16px;
  justify-content: space-between;
  margin-bottom: 14px;
}

.module-header h2 {
  font-size: 17px;
  line-height: 1.2;
}

.module-actions,
.button-row,
.browse-toolbar,
.entry-actions {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

button,
.entry-button {
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-weight: 700;
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.primary-button,
.danger-button,
.entry-button--red {
  border: 0;
  color: var(--text-white);
  padding: 8px 12px;
}

.primary-button {
  background: var(--brand-red);
}

.danger-button {
  background: var(--brand-red-dark);
}

.secondary-button {
  background: var(--bg-white);
  border: 1px solid var(--border-normal);
  color: var(--text-secondary);
  padding: 7px 11px;
}

.primary-soft-button {
  padding: 7px 11px;
}

.login-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: 240px minmax(260px, 1fr) minmax(260px, 1fr);
}

.qr-stage,
.pairing-card,
.status-console,
.command-console,
.table-list,
.quick-command-list {
  background: var(--bg-subtle);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
}

.qr-stage {
  display: grid;
  min-height: 240px;
  place-items: center;
}

.qr-stage img {
  height: 220px;
  width: 220px;
}

.qr-placeholder {
  align-items: center;
  border: 1px dashed var(--border-strong);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  display: flex;
  flex-direction: column;
  height: 190px;
  justify-content: center;
  width: 190px;
}

.qr-placeholder strong {
  color: var(--brand-red);
  font-size: 44px;
  line-height: 1;
}

.pairing-card,
.status-console,
.command-console {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px;
}

label {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

input,
textarea {
  background: var(--bg-white);
  border: 1px solid var(--border-normal);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font: inherit;
  outline: none;
  padding: 9px 10px;
  width: 100%;
}

textarea,
pre,
.command-console input {
  font-family: var(--font-mono);
}

input:focus,
textarea:focus {
  border-color: var(--brand-red);
  box-shadow: 0 0 0 3px rgb(231 0 18 / 10%);
}

.pairing-code {
  background: var(--bg-white);
  border: 1px solid rgb(231 0 18 / 16%);
  border-radius: var(--radius-md);
  padding: 12px;
}

.pairing-code span {
  color: var(--text-secondary);
  display: block;
  font-size: 12px;
}

.pairing-code strong {
  color: var(--brand-red);
  display: block;
  font-family: var(--font-mono);
  font-size: 28px;
  letter-spacing: 0;
  margin-top: 4px;
}

.status-console > div {
  display: flex;
  justify-content: space-between;
}

.status-console span {
  color: var(--text-secondary);
  font-size: 12px;
}

pre {
  background: #1f2329;
  border-radius: var(--radius-md);
  color: #fff;
  font-size: 12px;
  margin: 0;
  max-height: 220px;
  overflow: auto;
  padding: 10px;
  white-space: pre-wrap;
}

.browse-toolbar {
  margin-bottom: 12px;
}

.browse-toolbar input {
  flex: 1;
  min-width: 220px;
}

.tab-list {
  background: var(--bg-subtle);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  display: flex;
  padding: 3px;
}

.tab-list button {
  background: transparent;
  border: 0;
  color: var(--text-secondary);
  min-width: 72px;
  padding: 7px 10px;
}

.tab-list button.active {
  background: var(--bg-white);
  color: var(--brand-red);
  box-shadow: var(--shadow-sm);
}

.data-table-wrap {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  overflow: auto;
}

.data-table {
  border-collapse: collapse;
  min-width: 780px;
  width: 100%;
}

.data-table th,
.data-table td {
  border-bottom: 1px solid var(--border-light);
  font-size: 12px;
  padding: 9px 10px;
  text-align: left;
  vertical-align: top;
}

.data-table th {
  background: var(--bg-subtle);
  color: var(--text-secondary);
  font-weight: 800;
}

.data-table td {
  color: var(--text-primary);
  max-width: 360px;
  overflow-wrap: anywhere;
}

.empty-cell {
  color: var(--text-secondary) !important;
  text-align: center !important;
}

.sql-layout {
  display: grid;
  gap: 12px;
  grid-template-columns: 220px minmax(0, 1fr);
  margin-bottom: 12px;
}

.table-list {
  align-content: start;
  display: grid;
  gap: 6px;
  max-height: 236px;
  overflow: auto;
  padding: 8px;
}

.table-list button,
.quick-command-list button {
  background: var(--bg-white);
  border: 1px solid var(--border-light);
  color: var(--text-primary);
  padding: 8px 10px;
  text-align: left;
}

.table-list button.active,
.quick-command-list button.active {
  border-color: var(--brand-red);
  color: var(--brand-red);
}

.sql-editor {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
}

.limit-input {
  max-width: 140px;
}

.command-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: minmax(260px, 0.8fr) minmax(360px, 1.2fr);
}

.quick-command-list {
  display: grid;
  gap: 8px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  padding: 10px;
}

.quick-command-list button {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-height: 58px;
}

.quick-command-list span {
  color: var(--text-secondary);
  font-size: 11px;
}

.sync-log {
  margin-top: 10px;
}

.footer-entries {
  align-items: center;
  display: flex;
  justify-content: space-between;
}

.entry-button {
  background: var(--bg-white);
  border: 1px solid var(--border-normal);
  color: var(--text-primary);
  padding: 8px 12px;
  text-decoration: none;
}

.entry-button--red {
  background: var(--brand-red);
  border-color: var(--brand-red);
}

.notice {
  border-radius: var(--radius-md);
  font-size: 12px;
  margin: 10px 0 0;
  padding: 8px 10px;
}

.notice--info {
  background: #eef7fb;
  color: #0b6f96;
}

.notice--warning {
  background: #fff7ed;
  color: #b45309;
}

.notice--error {
  background: var(--brand-red-light);
  color: var(--brand-red-dark);
}

.notice--success {
  background: #edf7e8;
  color: var(--brand-green);
}

@media (max-width: 1180px) {
  .overview-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .login-grid,
  .command-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 820px) {
  .whatsapp-workbench {
    padding: 16px;
  }

  .lingxun-hero,
  .module-header,
  .footer-entries {
    align-items: stretch;
    flex-direction: column;
  }

  .overview-grid,
  .sql-layout,
  .quick-command-list {
    grid-template-columns: 1fr;
  }
}
</style>
