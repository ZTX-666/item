<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { getLongTermMemory, saveLongTermMemory, summarizeTodayLongTermMemory } from '../services/chitungApi'

const content = ref('')
const original = ref('')
const path = ref('')
const updatedAt = ref('')
const loading = ref(false)
const saving = ref(false)
const summarizing = ref(false)
const message = ref('')
const error = ref('')
const lastSummary = ref('')

const dirty = computed(() => content.value !== original.value)
const wordCount = computed(() => content.value.trim().length)

async function refresh() {
  loading.value = true
  error.value = ''
  message.value = ''
  try {
    const result = await getLongTermMemory()
    content.value = result.content || ''
    original.value = result.content || ''
    path.value = result.path || ''
    updatedAt.value = result.updated_at || ''
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  error.value = ''
  message.value = ''
  try {
    const result = await saveLongTermMemory(content.value)
    content.value = result.content || content.value
    original.value = content.value
    path.value = result.path || path.value
    updatedAt.value = result.updated_at || updatedAt.value
    message.value = '长期记忆已保存。'
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    saving.value = false
  }
}

async function summarizeToday() {
  summarizing.value = true
  error.value = ''
  message.value = ''
  try {
    const result = await summarizeTodayLongTermMemory()
    lastSummary.value = result.summary || ''
    message.value = result.message || '今日对话已写入长期记忆。'
    await refresh()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    summarizing.value = false
  }
}

function formatTime(value: string): string {
  if (!value) return '-'
  try {
    return new Date(value).toLocaleString('zh-CN')
  } catch {
    return value
  }
}

onMounted(refresh)
</script>

<template>
  <main class="workbench">
    <section class="hero-panel">
      <div>
        <p class="eyebrow">Long Term Memory</p>
        <h1>长期记忆</h1>
        <p>所有长期记忆共用一个 Markdown 文档。闪闪助手会自动参考这里的上下文，你也可以手动编辑。</p>
      </div>
      <div class="memory-actions">
        <button class="primary-soft-button" :disabled="loading" @click="refresh">
          {{ loading ? '读取中...' : '重新读取' }}
        </button>
        <button class="primary-soft-button" :disabled="summarizing" @click="summarizeToday">
          {{ summarizing ? '总结中...' : '总结今日对话' }}
        </button>
      </div>
    </section>

    <section class="memory-grid">
      <article class="panel memory-editor">
        <div class="panel__header">
          <div>
            <h2>长期记忆 Markdown</h2>
            <p>{{ path || 'chitung-center/data/long_term_memory.md' }}</p>
          </div>
          <div class="memory-meta">
            <span>{{ wordCount }} 字符</span>
            <span>更新：{{ formatTime(updatedAt) }}</span>
            <span v-if="dirty" class="dirty">未保存</span>
          </div>
        </div>
        <textarea
          v-model="content"
          class="memory-textarea"
          spellcheck="false"
          placeholder="# 赤瞳长期记忆&#10;&#10;在这里记录长期上下文..."
        />
        <div class="memory-footer">
          <p v-if="message" class="memory-ok">{{ message }}</p>
          <p v-if="error" class="memory-error">{{ error }}</p>
          <button class="primary-soft-button" :disabled="saving || !dirty" @click="save">
            {{ saving ? '保存中...' : '保存 Markdown' }}
          </button>
        </div>
      </article>

      <aside class="panel memory-guide">
        <h2>使用方式</h2>
        <p>在闪闪助手里点击或输入“长期记忆”，即可把今日对话压缩写入这份文档。</p>
        <p>后续聊天会自动带入压缩后的长期记忆作为上下文，帮助助手记住项目偏好、模块决策和未完成事项。</p>
        <h3>建议记录</h3>
        <ul>
          <li>用户长期偏好和命名习惯</li>
          <li>项目模块边界和架构决策</li>
          <li>已完成但容易忘记的修复</li>
          <li>后续需要验证的风险点</li>
        </ul>
        <h3>不要记录</h3>
        <ul>
          <li>API key、token、密码</li>
          <li>一次性日志和临时错误堆栈</li>
          <li>没有长期价值的闲聊</li>
        </ul>
        <div v-if="lastSummary" class="summary-box">
          <strong>最近一次总结</strong>
          <pre>{{ lastSummary }}</pre>
        </div>
      </aside>
    </section>
  </main>
</template>

<style scoped>
.memory-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.memory-grid {
  display: grid;
  gap: 16px;
  grid-template-columns: minmax(0, 1fr) 320px;
}

.memory-editor {
  min-height: calc(100vh - 230px);
}

.memory-meta {
  color: var(--text-secondary);
  display: flex;
  flex-wrap: wrap;
  font-size: 12px;
  gap: 10px;
  justify-content: flex-end;
}

.dirty {
  color: var(--color-warning, #c77700);
  font-weight: 700;
}

.memory-textarea {
  background: var(--bg-white);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  flex: 1;
  font-family: 'Cascadia Code', 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.65;
  min-height: 520px;
  padding: 14px;
  resize: vertical;
  width: 100%;
}

.memory-footer {
  align-items: center;
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

.memory-ok,
.memory-error {
  margin: 0 auto 0 0;
}

.memory-ok {
  color: var(--color-success, #2e7d32);
}

.memory-error {
  color: var(--color-error);
}

.memory-guide {
  color: var(--text-secondary);
}

.memory-guide h2,
.memory-guide h3 {
  color: var(--text-primary);
  margin-bottom: 8px;
}

.memory-guide ul {
  padding-left: 18px;
}

.summary-box {
  background: var(--bg-subtle);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  margin-top: 14px;
  padding: 10px;
}

.summary-box pre {
  white-space: pre-wrap;
}

@media (max-width: 1100px) {
  .memory-grid {
    grid-template-columns: 1fr;
  }
}
</style>
