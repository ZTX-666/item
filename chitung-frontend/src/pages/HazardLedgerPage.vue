<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import HazardLedgerPanel from '../components/hazards/HazardLedgerPanel.vue'
import { getHazards, runCaseWorkflow } from '../services/chitungApi'
import type { SafetyCaseRecord } from '../types/domain'

const records = ref<SafetyCaseRecord[]>([])
const isLoading = ref(false)
const keyword = ref('')
const statusFilter = ref('all')

const filteredRecords = computed(() => {
  const byStatus = statusFilter.value === 'all'
    ? records.value
    : records.value.filter((item) => String(item.status || '').toLowerCase() === statusFilter.value.toLowerCase())
  if (!keyword.value.trim()) return byStatus
  const q = keyword.value.trim().toLowerCase()
  return byStatus.filter((item) => {
    const text = `${item.id} ${item.description || ''} ${item.area || ''} ${item.contractor || ''} ${item.scene || ''}`.toLowerCase()
    return text.includes(q)
  })
})

async function refresh() {
  isLoading.value = true
  try {
    records.value = await getHazards(statusFilter.value === 'all' ? undefined : statusFilter.value)
  } finally {
    isLoading.value = false
  }
}

async function handleWorkflow(action: 'rectification-notice' | 'contractor-confirm' | 'close-review', caseId: string) {
  await runCaseWorkflow(action, {
    caseId,
    notes: 'Triggered from Hazard Ledger page',
    contractor: '待确认分包商',
  })
  await refresh()
}

onMounted(refresh)
</script>

<template>
  <main class="workbench">
    <section class="hero-panel">
      <div>
        <p class="eyebrow">Hazard Ledger</p>
        <h1>隐患台账</h1>
        <p>对齐原型 02 页面：筛选、检索、案例动作闭环。</p>
      </div>
      <div class="hero-panel__status">
        <span class="status-dot status-dot--green" />
        当前记录 {{ filteredRecords.length }} 条
      </div>
    </section>

    <section class="panel" style="margin-bottom: 12px;">
      <div class="template-search-bar">
        <input v-model="keyword" placeholder="搜索案例/区域/分包商" />
        <select v-model="statusFilter">
          <option value="all">全部状态</option>
          <option value="open">open</option>
          <option value="in_progress">in_progress</option>
          <option value="rectification_notice_drafted">rectification_notice_drafted</option>
          <option value="closed">closed</option>
        </select>
        <button class="primary-soft-button" :disabled="isLoading" @click="refresh">{{ isLoading ? '刷新中' : '刷新' }}</button>
      </div>
    </section>

    <HazardLedgerPanel
      :records="filteredRecords"
      :is-loading="isLoading"
      @refresh="refresh"
      @workflow="handleWorkflow"
    />
  </main>
</template>
