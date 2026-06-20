import './style.css'

const API_BASE = (import.meta as any).env?.VITE_API_BASE || 'http://localhost:8787'

type ChatRow = {
  jid: string
  name: string | null
  unreadCount: number | null
  lastMessageAt: number | null
  isGroup: number | null
}

type MessageRow = {
  id: string
  chatJid: string
  senderJid: string | null
  fromMe: number | null
  timestamp: number
  type: string | null
  content: string | null
  quotedId: string | null
  mediaPath: string | null
}

function el<K extends keyof HTMLElementTagNameMap>(tag: K, attrs: Record<string, any> = {}, children: any[] = []) {
  const node = document.createElement(tag)
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'class') node.className = v
    else if (k === 'text') node.textContent = v
    else if (k.startsWith('on') && typeof v === 'function') (node as any)[k.toLowerCase()] = v
    else if (v != null) node.setAttribute(k, String(v))
  }
  for (const child of children) node.append(child)
  return node
}

function fmtTime(tsSec: number) {
  const d = new Date(tsSec * 1000)
  return d.toLocaleString()
}

async function apiGet<T>(path: string): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`)
  if (!r.ok) throw new Error(await r.text())
  return (await r.json()) as T
}

async function apiPost<T>(path: string, body: any): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok) throw new Error(await r.text())
  return (await r.json()) as T
}

const root = document.querySelector<HTMLDivElement>('#app')!
root.innerHTML = ''

const state = {
  chats: [] as ChatRow[],
  selectedChat: null as ChatRow | null,
  messages: [] as MessageRow[],
}

const header = el('div', { class: 'topbar' }, [
  el('div', { class: 'title', text: 'WhatsApp 本地归档' }),
  el('div', { class: 'meta', text: `API: ${API_BASE}` }),
])

const chatsList = el('div', { class: 'list' })
const messagesPane = el('div', { class: 'messages' })

const chatSearch = el('input', { class: 'input', placeholder: '搜索聊天（名称 / jid）' }) as HTMLInputElement
const msgSearch = el('input', { class: 'input', placeholder: '搜索消息内容（例如：你好）' }) as HTMLInputElement
const msgSearchBtn = el('button', { class: 'btn', text: '搜索' })

const refreshBtn = el('button', { class: 'btn secondary', text: '刷新' })

const left = el('div', { class: 'left' }, [
  el('div', { class: 'panel' }, [
    el('div', { class: 'row' }, [chatSearch, refreshBtn]),
    chatsList,
  ]),
])

const rightHeader = el('div', { class: 'panel' }, [
  el('div', { class: 'row' }, [msgSearch, msgSearchBtn]),
  el('div', { class: 'hint', text: '提示：附件下载会调用 whatscli，若正在 sync --follow 可能会锁库。' }),
])

const right = el('div', { class: 'right' }, [rightHeader, messagesPane])

root.append(header, el('div', { class: 'layout' }, [left, right]))

function renderChats() {
  const q = chatSearch.value.trim().toLowerCase()
  const filtered = q
    ? state.chats.filter((c) => (c.name || '').toLowerCase().includes(q) || c.jid.toLowerCase().includes(q))
    : state.chats

  chatsList.innerHTML = ''
  for (const c of filtered) {
    const isSelected = state.selectedChat?.jid === c.jid
    const label = c.name || c.jid
    const subtitle = `${c.jid}${c.isGroup ? ' · group' : ''}${c.unreadCount ? ` · unread ${c.unreadCount}` : ''}`
    const item = el('button', {
      class: `item ${isSelected ? 'active' : ''}`,
      onclick: async () => {
        state.selectedChat = c
        await loadMessages()
        renderChats()
      },
    }, [
      el('div', { class: 'itemTitle', text: label }),
      el('div', { class: 'itemSub', text: subtitle }),
    ])
    chatsList.append(item)
  }
}

function renderMessages(rows: MessageRow[]) {
  messagesPane.innerHTML = ''
  if (!state.selectedChat) {
    messagesPane.append(el('div', { class: 'empty', text: '先在左侧选择一个聊天/群组。' }))
    return
  }

  const header = el('div', { class: 'chatHeader' }, [
    el('div', { class: 'chatTitle', text: state.selectedChat.name || state.selectedChat.jid }),
    el('div', { class: 'chatSub', text: state.selectedChat.jid }),
  ])
  messagesPane.append(header)

  const list = el('div', { class: 'msgList' })
  const ordered = [...rows].sort((a, b) => a.timestamp - b.timestamp)

  for (const m of ordered) {
    const who = m.fromMe ? 'ME' : (m.senderJid || 'UNKNOWN')
    const content = m.content || ''

    const mediaLink =
      m.mediaPath
        ? el('a', { class: 'link', href: `${API_BASE}/api/media?path=${encodeURIComponent(m.mediaPath)}`, target: '_blank', text: '打开已下载附件' })
        : null

    const downloadBtn = el('button', {
      class: 'btn tiny',
      text: '下载附件',
      onclick: async () => {
        try {
          downloadBtn.textContent = '下载中...'
          downloadBtn.setAttribute('disabled', 'true')
          await apiPost('/api/media/download', { messageId: m.id })
          // reload message list so mediaPath appears
          await loadMessages()
        } catch (e: any) {
          alert(String(e?.message || e))
        } finally {
          downloadBtn.textContent = '下载附件'
          downloadBtn.removeAttribute('disabled')
        }
      },
    })

    const bubble = el('div', { class: `bubble ${m.fromMe ? 'me' : 'them'}` }, [
      el('div', { class: 'metaRow' }, [
        el('span', { class: 'who', text: who }),
        el('span', { class: 'time', text: fmtTime(m.timestamp) }),
        el('span', { class: 'type', text: m.type || '' }),
      ]),
      content ? el('div', { class: 'content', text: content }) : el('div', { class: 'content muted', text: '(no text)' }),
      el('div', { class: 'actions' }, [
        mediaLink || el('span', { class: 'muted', text: m.mediaPath ? '' : '' }),
        downloadBtn,
      ].filter(Boolean) as any),
    ])
    list.append(bubble)
  }
  messagesPane.append(list)
}

async function loadChats() {
  const data = await apiGet<{ rows: ChatRow[] }>('/api/chats?limit=200')
  state.chats = data.rows || []
  if (!state.selectedChat && state.chats.length) state.selectedChat = state.chats[0]
  renderChats()
}

async function loadMessages() {
  if (!state.selectedChat) return
  const data = await apiGet<{ rows: MessageRow[] }>(`/api/messages?chat=${encodeURIComponent(state.selectedChat.jid)}&limit=100`)
  state.messages = data.rows || []
  renderMessages(state.messages)
}

async function searchMessages() {
  const q = msgSearch.value.trim()
  if (!q) return
  const chat = state.selectedChat?.jid
  const data = await apiGet<{ rows: MessageRow[] }>(
    `/api/messages/search?q=${encodeURIComponent(q)}${chat ? `&chat=${encodeURIComponent(chat)}` : ''}&limit=100`
  )
  renderMessages(data.rows || [])
}

refreshBtn.onclick = async () => {
  await loadChats()
  await loadMessages()
}
chatSearch.oninput = () => renderChats()
msgSearchBtn.onclick = () => searchMessages()
msgSearch.onkeydown = (e) => {
  if (e.key === 'Enter') searchMessages()
}

;(async () => {
  try {
    await loadChats()
    await loadMessages()
  } catch (e: any) {
    messagesPane.innerHTML = ''
    messagesPane.append(el('div', { class: 'empty', text: `加载失败：${String(e?.message || e)}` }))
  }
})()
