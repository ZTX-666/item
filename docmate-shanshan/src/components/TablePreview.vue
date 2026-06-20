<script setup lang="ts">
import type { TableResult } from '@/types'

defineProps<{
  table: TableResult
}>()

const emit = defineEmits<{
  insert: []
  cancel: []
}>()
</script>

<template>
  <div class="table-preview">
    <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th v-for="h in table.headers" :key="h">{{ h }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, i) in table.rows" :key="i">
            <td v-for="(cell, j) in row" :key="j">{{ cell }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <p v-if="table.reason" class="table-reason">{{ table.reason }}</p>
    <div class="table-actions">
      <button class="table-btn primary" @click="emit('insert')">插入表格</button>
      <button class="table-btn" @click="emit('cancel')">取消</button>
    </div>
  </div>
</template>

<style scoped>
.table-preview {
  margin-top: 8px;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  overflow: hidden;
  background: var(--bg-base);
}

.table-scroll {
  overflow-x: auto;
  padding: 8px;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

th, td {
  border: 1px solid var(--border-light);
  padding: 6px 10px;
  text-align: left;
}

th {
  background: var(--bg-hover);
  color: var(--text-bright);
  font-weight: 600;
}

td {
  color: var(--text-primary);
}

.table-reason {
  padding: 0 12px 8px;
  font-size: 11px;
  color: var(--text-muted);
}

.table-actions {
  display: flex;
  gap: 8px;
  padding: 8px 12px;
  border-top: 1px solid var(--border);
}

.table-btn {
  flex: 1;
  padding: 6px;
  font-size: 12px;
  border-radius: 6px;
  background: var(--bg-hover);
  color: var(--text-secondary);
  border: 1px solid var(--border-light);
}

.table-btn.primary {
  background: var(--accent);
  color: white;
  border-color: transparent;
}
</style>
