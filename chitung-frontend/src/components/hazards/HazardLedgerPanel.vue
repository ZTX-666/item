<script setup lang="ts">
import type { SafetyCaseRecord } from '../../types/domain'

defineProps<{
  records: SafetyCaseRecord[]
  isLoading?: boolean
}>()

const emit = defineEmits<{
  refresh: []
  workflow: [action: 'rectification-notice' | 'contractor-confirm' | 'close-review', caseId: string]
}>()
</script>

<template>
  <section class="panel hazard-ledger-panel">
    <div class="panel__header">
      <div>
        <h2>隐患台账</h2>
        <p>来自本地 safety_platform.db 的真实记录</p>
      </div>
      <button class="mini-button" type="button" @click="emit('refresh')">
        {{ isLoading ? '刷新中' : '刷新' }}
      </button>
    </div>

    <div class="hazard-table-wrap">
      <table class="hazard-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>状态</th>
            <th>区域</th>
            <th>风险</th>
            <th>隐患描述</th>
            <th>分包商</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="record in records" :key="record.id">
            <td>#{{ record.id }}</td>
            <td>{{ record.status || 'candidate' }}</td>
            <td>{{ record.area || record.scene || '未分区' }}</td>
            <td>{{ record.risk_level || 'medium' }}</td>
            <td>{{ record.description || '未填写描述' }}</td>
            <td>{{ record.contractor || '待确认' }}</td>
            <td>
              <button class="mini-button" @click="emit('workflow', 'rectification-notice', String(record.id))">通知</button>
              <button class="mini-button" @click="emit('workflow', 'contractor-confirm', String(record.id))">分包</button>
              <button class="mini-button" @click="emit('workflow', 'close-review', String(record.id))">关闭</button>
            </td>
          </tr>
          <tr v-if="!records.length">
            <td colspan="7" class="hazard-table__empty">暂无真实隐患记录。可先用 CommandBar 输入隐患，或确认视觉巡检候选入库。</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
