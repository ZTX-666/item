<script setup lang="ts">
import { ref } from 'vue'
import { generateReport } from '../services/chitungApi'
import type { GeneratedOutputItem } from '../types/domain'

const isGenerating = ref(false)
const outputs = ref<GeneratedOutputItem[]>([])
const note = ref('选择一种报告类型开始生成。')

function rememberOutput(item: Omit<GeneratedOutputItem, 'id' | 'createdAt'>) {
  outputs.value = [
    {
      ...item,
      id: `${item.kind}-${Date.now()}-${Math.random().toString(16).slice(2)}`,
      createdAt: new Date().toLocaleString(),
    },
    ...outputs.value,
  ].slice(0, 12)
}

async function handleGenerateReport(reportType: 'community' | 'daily_safety' | 'rectification') {
  isGenerating.value = true
  note.value = '正在生成报告...'
  try {
    const title = reportType === 'community' ? '社区建设报告' : reportType === 'rectification' ? '整改报告' : '每日安全日报'
    const report = await generateReport({ reportType, title })
    note.value = report.message
    if (report.output_path) {
      rememberOutput({
        title: report.message,
        kind: report.output_path.endsWith('.docx') ? 'docx' : 'report',
        path: report.output_path,
      })
    }
  } catch (error) {
    note.value = `报告生成失败：${error instanceof Error ? error.message : String(error)}`
  } finally {
    isGenerating.value = false
  }
}

async function openPath(path?: string) {
  if (!path || !window.chitungDesktop) return
  await window.chitungDesktop.openPath(path)
}

async function showInFolder(path?: string) {
  if (!path || !window.chitungDesktop) return
  await window.chitungDesktop.showInFolder(path)
}
</script>

<template>
  <main class="workbench">
    <section class="hero-panel">
      <div>
        <p class="eyebrow">Reports</p>
        <h1>报告生成</h1>
        <p>安全日报、整改报告和社区报告在这里生成、打开和定位。</p>
      </div>
      <div class="hero-panel__status">
        <span class="status-dot" :class="isGenerating ? 'status-dot--orange' : 'status-dot--green'" />
        {{ isGenerating ? '生成中' : '就绪' }}
      </div>
    </section>

    <section class="panel report-generator-panel">
      <div class="panel__header">
        <div>
          <h2>报告类型</h2>
          <p>{{ note }}</p>
        </div>
      </div>
      <div class="workflow-shortcuts">
        <button :disabled="isGenerating" @click="handleGenerateReport('daily_safety')">安全日报</button>
        <button :disabled="isGenerating" @click="handleGenerateReport('rectification')">整改报告</button>
        <button :disabled="isGenerating" @click="handleGenerateReport('community')">社区报告 DOCX</button>
      </div>
    </section>

    <section class="panel output-history-panel">
      <div class="panel__header">
        <div>
          <h2>最近生成文件</h2>
          <p>本页只管理报告产物，表格草稿和巡检证据留在各自流程页。</p>
        </div>
      </div>
      <div class="output-history-list">
        <article v-for="item in outputs" :key="item.id" class="output-history-row">
          <div>
            <strong>{{ item.title }}</strong>
            <p>{{ item.path || item.content || '暂无路径' }}</p>
            <small>{{ item.kind }} · {{ item.createdAt }}</small>
          </div>
          <div class="output-history-actions">
            <button v-if="item.path" class="mini-button" @click="openPath(item.path)">打开</button>
            <button v-if="item.path" class="mini-button" @click="showInFolder(item.path)">定位</button>
          </div>
        </article>
        <p v-if="!outputs.length" class="smart-form-empty">暂无生成文件。</p>
      </div>
    </section>
  </main>
</template>
