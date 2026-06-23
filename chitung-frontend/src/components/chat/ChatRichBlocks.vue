<script setup lang="ts">
import { computed } from 'vue'
import {
  extractChatRichBlocks,
  fileIconLabel,
  formatCellValue,
  formatFileSize,
  type ChatRichBlock,
} from '../../composables/useChatRichContent'

const props = defineProps<{
  cards?: Array<Record<string, unknown>>
  toolResults?: Array<Record<string, unknown>>
  richBlocks?: Array<Record<string, unknown>>
  content?: string
}>()

const blocks = computed(() =>
  extractChatRichBlocks(props.cards ?? [], props.toolResults ?? [], props.richBlocks ?? []),
)

const imageBlocks = computed(() => blocks.value.filter((block): block is Extract<ChatRichBlock, { kind: 'image' }> => block.kind === 'image'))
const nonImageBlocks = computed(() => blocks.value.filter((block) => block.kind !== 'image'))

function tableMeta(block: Extract<ChatRichBlock, { kind: 'table' }>) {
  const total = block.total ?? block.rows.length
  if (total > block.rows.length) {
    return `展示 ${block.rows.length} / ${total} 行`
  }
  return `${block.rows.length} 行`
}

function fileHref(block: Extract<ChatRichBlock, { kind: 'file' }>) {
  return block.url || block.path || '#'
}
</script>

<template>
  <div v-if="content" class="chat-rich__text">{{ content }}</div>

  <div v-if="imageBlocks.length" class="chat-rich__gallery">
    <div class="chat-rich__block-title">
      <strong>图片附件</strong>
      <span>{{ imageBlocks.length }} 张</span>
    </div>
    <div class="chat-rich__gallery-grid">
      <figure v-for="(block, index) in imageBlocks" :key="`img-${block.url}-${index}`" class="chat-rich__gallery-item">
        <a :href="block.url" target="_blank" rel="noreferrer">
          <img :src="block.url" :alt="block.title" class="chat-rich__image" loading="lazy" />
        </a>
        <figcaption>
          <strong>{{ block.title }}</strong>
          <span v-if="block.caption">{{ block.caption }}</span>
        </figcaption>
      </figure>
    </div>
  </div>

  <div
    v-for="(block, index) in nonImageBlocks"
    :key="`${block.kind}-${block.title}-${index}`"
    class="chat-rich__block"
  >
    <div v-if="block.kind === 'table'" class="chat-rich__table-wrap">
      <div class="chat-rich__block-title">
        <strong>{{ block.title }}</strong>
        <span>{{ tableMeta(block) }}</span>
      </div>
      <div class="chat-rich__table-scroll">
        <table class="chat-rich__table">
          <thead>
            <tr>
              <th v-for="column in block.columns" :key="column">{{ column }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, rowIndex) in block.rows" :key="`${rowIndex}-${block.columns[0]}`">
              <td v-for="column in block.columns" :key="`${rowIndex}-${column}`">
                {{ formatCellValue(row[column]) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-else-if="block.kind === 'file'" class="chat-rich__file">
      <span class="chat-rich__file-icon">{{ fileIconLabel(block.mime, block.fileName || block.path) }}</span>
      <div class="chat-rich__file-meta">
        <strong>{{ block.fileName || block.title }}</strong>
        <span>
          {{ block.title }}
          <template v-if="formatFileSize(block.size)"> · {{ formatFileSize(block.size) }}</template>
        </span>
      </div>
      <div class="chat-rich__file-actions">
        <a v-if="block.url" :href="fileHref(block)" target="_blank" rel="noreferrer">打开</a>
        <a
          v-if="block.url"
          :href="fileHref(block)"
          :download="block.fileName || block.title"
          rel="noreferrer"
        >
          下载
        </a>
      </div>
    </div>

    <div v-else-if="block.kind === 'markdown'" class="chat-rich__markdown">
      <div class="chat-rich__block-title"><strong>{{ block.title }}</strong></div>
      <pre>{{ block.text }}</pre>
    </div>

    <div v-else-if="block.kind === 'code'" class="chat-rich__code">
      <div class="chat-rich__block-title">
        <strong>{{ block.title }}</strong>
        <span>{{ block.language || 'text' }}</span>
      </div>
      <pre><code>{{ block.text }}</code></pre>
    </div>

    <div v-else-if="block.kind === 'list'" class="chat-rich__list">
      <div class="chat-rich__block-title"><strong>{{ block.title }}</strong></div>
      <ul>
        <li v-for="item in block.items" :key="item">{{ item }}</li>
      </ul>
    </div>

    <div v-else-if="block.kind === 'links'" class="chat-rich__links">
      <div class="chat-rich__block-title"><strong>{{ block.title }}</strong></div>
      <ul>
        <li v-for="link in block.links" :key="link.url">
          <a :href="link.url" target="_blank" rel="noreferrer">{{ link.title }}</a>
          <span v-if="link.source"> · {{ link.source }}</span>
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.chat-rich__text {
  margin-bottom: 8px;
  white-space: pre-wrap;
}

.chat-rich__block + .chat-rich__block,
.chat-rich__gallery + .chat-rich__block,
.chat-rich__text + .chat-rich__gallery {
  margin-top: 10px;
}

.chat-rich__block-title {
  align-items: center;
  display: flex;
  gap: 8px;
  justify-content: space-between;
  margin-bottom: 6px;
}

.chat-rich__block-title strong {
  color: #1d2b45;
  font-size: 12px;
}

.chat-rich__block-title span {
  color: #6b7893;
  font-size: 11px;
}

.chat-rich__gallery {
  background: #f8fafc;
  border: 1px solid #dbe3ef;
  border-radius: 10px;
  padding: 8px;
}

.chat-rich__gallery-grid {
  display: grid;
  gap: 8px;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
}

.chat-rich__gallery-item {
  margin: 0;
}

.chat-rich__gallery-item figcaption {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: 4px;
}

.chat-rich__gallery-item figcaption strong,
.chat-rich__gallery-item figcaption span {
  color: #6b7893;
  font-size: 11px;
  line-height: 1.3;
}

.chat-rich__table-wrap {
  background: #f8fafc;
  border: 1px solid #dbe3ef;
  border-radius: 10px;
  padding: 8px;
}

.chat-rich__table-scroll {
  max-height: 280px;
  overflow: auto;
}

.chat-rich__table {
  border-collapse: collapse;
  font-size: 12px;
  min-width: 100%;
}

.chat-rich__table th,
.chat-rich__table td {
  border: 1px solid #dbe3ef;
  max-width: 240px;
  overflow: hidden;
  padding: 6px 8px;
  text-align: left;
  text-overflow: ellipsis;
  vertical-align: top;
  white-space: pre-wrap;
  word-break: break-word;
}

.chat-rich__table th {
  background: #eef2f8;
  position: sticky;
  top: 0;
  z-index: 1;
}

.chat-rich__image {
  border-radius: 8px;
  display: block;
  max-height: 180px;
  object-fit: contain;
  width: 100%;
}

.chat-rich__markdown pre,
.chat-rich__code pre {
  background: #0f172a;
  border-radius: 8px;
  color: #e2e8f0;
  font-size: 12px;
  line-height: 1.5;
  margin: 0;
  max-height: 260px;
  overflow: auto;
  padding: 10px 12px;
  white-space: pre-wrap;
  word-break: break-word;
}

.chat-rich__list ul,
.chat-rich__links ul {
  margin: 0;
  padding-left: 18px;
}

.chat-rich__list li,
.chat-rich__links li {
  font-size: 12px;
  line-height: 1.5;
  margin: 2px 0;
}

.chat-rich__links a {
  color: #2563eb;
  text-decoration: none;
}

.chat-rich__links a:hover {
  text-decoration: underline;
}

.chat-rich__file {
  align-items: center;
  background: #f8fafc;
  border: 1px solid #dbe3ef;
  border-radius: 10px;
  display: flex;
  gap: 10px;
  padding: 10px 12px;
}

.chat-rich__file-icon {
  font-size: 22px;
  line-height: 1;
}

.chat-rich__file-meta {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.chat-rich__file-meta strong {
  color: #1d2b45;
  font-size: 12px;
}

.chat-rich__file-meta span {
  color: #6b7893;
  font-size: 11px;
}

.chat-rich__file-actions {
  display: flex;
  flex-shrink: 0;
  gap: 8px;
}

.chat-rich__file-actions a {
  color: #2563eb;
  font-size: 12px;
  text-decoration: none;
}

.chat-rich__file-actions a:hover {
  text-decoration: underline;
}
</style>
