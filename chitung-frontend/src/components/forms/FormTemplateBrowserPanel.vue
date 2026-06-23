<script setup lang="ts">
import { ref } from 'vue'
import type { SmartFormTemplate } from '../../types/domain'
import SkeletonLoader from '../common/SkeletonLoader.vue'

/**
 * FormTemplateBrowserPanel — 模板浏览面板
 * P2-5: 模板搜索结果改为卡片（含id + title + policy_context预览 + 字段数）
 * P1-6: 骨架屏加载
 */

defineProps<{
  templates: SmartFormTemplate[]
  isLoading?: boolean
}>()

const emit = defineEmits<{
  search: [query: string]
  useTemplate: [templateId: string]
}>()

const query = ref('')

const hotTags = ['临边', '高处作业', '整改', '吊运', 'T006', '动火', '受限空间']

function searchTag(tag: string) {
  query.value = tag
  emit('search', tag)
}

function truncate(text: string, max: number): string {
  if (!text) return ''
  return text.length > max ? text.slice(0, max) + '...' : text
}
</script>

<template>
  <section class="panel form-template-panel">
    <div class="panel__header">
      <div>
        <h2>安全表格模板库</h2>
        <p>搜索安全制度/表格模板，并用于智能填表</p>
      </div>
    </div>

    <form class="template-search-bar" @submit.prevent="emit('search', query)">
      <input v-model="query" placeholder="输入关键词，例如：临边 / 吊运 / 动火 / T006" />
      <button class="primary-soft-button" type="submit">{{ isLoading ? '搜索中' : '搜索模板' }}</button>
    </form>

    <!-- 热门标签快捷搜索 -->
    <div class="hot-tags">
      <span class="hot-tags__label">热门搜索：</span>
      <button
        v-for="tag in hotTags"
        :key="tag"
        class="hot-tag"
        @click="searchTag(tag)"
      >
        {{ tag }}
      </button>
    </div>

    <!-- 骨架屏 -->
    <SkeletonLoader v-if="isLoading" type="cards" :count="3" />

    <!-- 模板卡片列表 -->
    <div v-else class="template-list">
      <article v-for="template in templates" :key="template.id" class="template-card">
        <div class="template-card__head">
          <span class="template-card__id">{{ template.id }}</span>
          <strong class="template-card__title">{{ template.title || '未命名模板' }}</strong>
        </div>
        <p class="template-card__context">
          {{ truncate(template.policy_context || template.docx_path || '暂无上下文说明', 80) }}
        </p>
        <div class="template-card__footer">
          <span v-if="template.docx_path" class="template-card__meta">
            &#128196; {{ template.docx_path.split(/[\\/]/).pop() }}
          </span>
          <button class="mini-button" @click="emit('useTemplate', template.id)">用于填表</button>
        </div>
      </article>

      <!-- 空状态 -->
      <div v-if="!templates.length" class="template-empty">
        <div class="template-empty__icon">&#128269;</div>
        <p class="template-empty__title">暂无模板结果</p>
        <p class="template-empty__hint">试试搜索 T006、临边、吊运、动火等关键词</p>
      </div>
    </div>
  </section>
</template>

<style scoped>
.form-template-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.panel__header h2 {
  font-size: 16px;
  margin: 0;
}

.panel__header p {
  color: var(--text-secondary, #5b626c);
  font-size: 12px;
  margin: 4px 0 0;
}

.template-search-bar {
  display: flex;
  gap: 8px;
}

.template-search-bar input {
  background: var(--bg-white, #fff);
  border: 1px solid var(--border-normal, #d0d5dd);
  border-radius: var(--radius-md, 8px);
  color: var(--text-primary, #1a1d23);
  flex: 1;
  font-size: 13px;
  padding: 9px 12px;
}

.template-search-bar input:focus {
  border-color: var(--brand-cyan, #0f9ed5);
  outline: none;
}

.primary-soft-button {
  background: var(--brand-cyan, #0f9ed5);
  border: none;
  border-radius: var(--radius-md, 8px);
  color: var(--text-white, #fff);
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  padding: 9px 16px;
  white-space: nowrap;
}

.primary-soft-button:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

/* 热门标签 */
.hot-tags {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.hot-tags__label {
  color: var(--text-secondary, #5b626c);
  font-size: 11px;
}

.hot-tag {
  background: var(--bg-subtle, #f5f7fa);
  border: 1px solid var(--border-light, #e8eaef);
  border-radius: 999px;
  color: var(--text-secondary, #5b626c);
  cursor: pointer;
  font-size: 11px;
  padding: 3px 10px;
  transition: all 120ms ease;
}

.hot-tag:hover {
  background: rgba(15, 158, 213, 0.08);
  border-color: var(--brand-cyan, #0f9ed5);
  color: var(--brand-cyan, #0f9ed5);
}

/* 模板卡片列表 */
.template-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.template-card {
  background: var(--bg-white, #fff);
  border: 1px solid var(--border-light, #e8eaef);
  border-radius: var(--radius-md, 8px);
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px;
  transition: border-color 120ms ease;
}

.template-card:hover {
  border-color: var(--brand-cyan, #0f9ed5);
}

.template-card__head {
  align-items: center;
  display: flex;
  gap: 8px;
}

.template-card__id {
  background: rgba(15, 158, 213, 0.1);
  border-radius: var(--radius-sm, 4px);
  color: var(--brand-cyan, #0f9ed5);
  font-size: 11px;
  font-weight: 700;
  padding: 2px 6px;
}

.template-card__title {
  color: var(--text-primary, #1a1d23);
  flex: 1;
  font-size: 13px;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.template-card__context {
  color: var(--text-secondary, #5b626c);
  font-size: 12px;
  line-height: 1.5;
  margin: 0;
}

.template-card__footer {
  align-items: center;
  display: flex;
  gap: 8px;
  justify-content: space-between;
}

.template-card__meta {
  color: var(--text-muted, #9ca3af);
  font-size: 11px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mini-button {
  background: var(--brand-cyan, #0f9ed5);
  border: none;
  border-radius: var(--radius-sm, 4px);
  color: var(--text-white, #fff);
  cursor: pointer;
  font-size: 11px;
  font-weight: 600;
  padding: 5px 12px;
  white-space: nowrap;
}

/* 空状态 */
.template-empty {
  align-items: center;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 32px 16px;
  text-align: center;
}

.template-empty__icon {
  font-size: 32px;
  opacity: 0.5;
}

.template-empty__title {
  color: var(--text-primary, #1a1d23);
  font-size: 13px;
  font-weight: 600;
  margin: 0;
}

.template-empty__hint {
  color: var(--text-secondary, #5b626c);
  font-size: 12px;
  margin: 0;
}
</style>
