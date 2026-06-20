<script setup lang="ts">
import { ref } from 'vue'
import type { SmartFormTemplate } from '../../types/domain'

defineProps<{
  templates: SmartFormTemplate[]
  isLoading?: boolean
}>()

const emit = defineEmits<{
  search: [query: string]
  useTemplate: [templateId: string]
}>()

const query = ref('临边 整改')
</script>

<template>
  <section class="panel form-template-panel">
    <div class="panel__header">
      <div>
        <h2>安全表格模板库</h2>
        <p>搜索 159 个安全制度/表格模板，并用于智能填表</p>
      </div>
    </div>

    <form class="template-search-bar" @submit.prevent="emit('search', query)">
      <input v-model="query" placeholder="输入关键词，例如：临边 / 吊运 / 酷热 / T006" />
      <button class="primary-soft-button" type="submit">{{ isLoading ? '搜索中' : '搜索模板' }}</button>
    </form>

    <div class="template-list">
      <article v-for="template in templates" :key="template.id" class="template-row">
        <div>
          <strong>{{ template.id }} · {{ template.title || '未命名模板' }}</strong>
          <p>{{ template.policy_context || template.docx_path || '暂无上下文' }}</p>
        </div>
        <button class="mini-button" @click="emit('useTemplate', template.id)">用于填表</button>
      </article>
      <p v-if="!templates.length" class="template-empty">暂无模板结果。可搜索 T006、临边、吊运、酷热等关键词。</p>
    </div>
  </section>
</template>
