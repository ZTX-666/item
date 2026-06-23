<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  createYaoyaoStructuredDraft,
  exportYaoyaoStructuredExcel,
  getYaoyaoTemplate,
  listYaoyaoTemplates,
  renderYaoyaoStructuredPage,
  saveYaoyaoTemplate,
} from '../services/chitungApi'
import type { YaoyaoPageRow, YaoyaoRegion, YaoyaoTemplateListItem } from '../types/domain'

const CANVAS_WIDTH = 900
const CANVAS_HEIGHT = 1200
const FIELD_SERIAL = '序號'

const fileInput = ref<HTMLInputElement | null>(null)
const sourcePath = ref('')
const statusText = ref('未載入 PDF')
const previewUrl = ref('')
const currentPageIndex = ref(0)
const pageCount = ref(0)
const pageInput = ref('1')
const zoom = ref(1)
const pdfViewportRef = ref<HTMLElement | null>(null)
const fitScale = ref(0.72)
let fitScaleObserver: ResizeObserver | null = null

const regions = ref<YaoyaoRegion[]>([])
const selectedRegionIndex = ref(-1)
const pageRows = ref<YaoyaoPageRow[]>([])
const templates = ref<YaoyaoTemplateListItem[]>([])
const selectedTemplateId = ref('')
const templateName = ref('')

const isRendering = ref(false)
const isRecognizing = ref(false)
const isBatching = ref(false)
const cancelBatch = ref(false)
const message = ref('')
const errorMessage = ref('')
const exportedUrl = ref('')

type DragMode = 'move' | 'resize'
type DragState = {
  mode: DragMode
  index: number
  startX: number
  startY: number
  original: YaoyaoRegion
}

const dragState = ref<DragState | null>(null)

const orderedRows = computed(() =>
  [...pageRows.value].sort((a, b) => a.pageNumber - b.pageNumber),
)

const tableColumns = computed(() => [FIELD_SERIAL, ...regions.value.map((region) => region.name)])

const canRecognize = computed(() => Boolean(sourcePath.value.trim()) && regions.value.length > 0 && !isRecognizing.value && !isBatching.value)

function pickFile() {
  fileInput.value?.click()
}

async function handleFileSelect(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  const maybePath = (file as File & { path?: string }).path || ''
  if (maybePath) {
    sourcePath.value = maybePath
    await importCurrentPath()
  } else {
    errorMessage.value = `已选择 ${file.name}，但浏览器环境不能读取本地绝对路径，请在路径栏粘贴 PDF 路径。`
  }
  input.value = ''
}

async function importCurrentPath() {
  if (!sourcePath.value.trim()) {
    errorMessage.value = '请先输入或选择 PDF / 图片路径。'
    return
  }
  currentPageIndex.value = 0
  pageInput.value = '1'
  pageRows.value = []
  exportedUrl.value = ''
  await renderPage(0)
}

async function renderPage(pageIndex: number) {
  isRendering.value = true
  errorMessage.value = ''
  message.value = ''
  try {
    const result = await renderYaoyaoStructuredPage({
      filePath: sourcePath.value.trim(),
      pageIndex,
      renderWidth: CANVAS_WIDTH,
      renderHeight: CANVAS_HEIGHT,
    })
    if (!result.ok) throw new Error(result.message || result.error || '页面渲染失败')
    previewUrl.value = result.preview_url || ''
    currentPageIndex.value = result.page_index ?? pageIndex
    pageCount.value = result.page_count || pageCount.value || 1
    pageInput.value = String(currentPageIndex.value + 1)
    statusText.value = `已載入：第 ${currentPageIndex.value + 1} / ${pageCount.value} 頁`
    await nextTick()
    updateFitScale()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error)
    statusText.value = '頁面渲染失敗'
  } finally {
    isRendering.value = false
  }
}

function addRegion() {
  const index = regions.value.length + 1
  const region = {
    name: `欄位${index}`,
    x: Math.round((CANVAS_WIDTH - 180) / 2),
    y: Math.round((CANVAS_HEIGHT - 80) / 2),
    width: 180,
    height: 80,
    angle: 0,
  }
  regions.value.push(region)
  selectedRegionIndex.value = regions.value.length - 1
  ensureRowsHaveColumns()
  statusText.value = `已新增識別框：${region.name}`
}

function removeRegion(index: number) {
  const [removed] = regions.value.splice(index, 1)
  if (selectedRegionIndex.value === index) selectedRegionIndex.value = -1
  if (removed) {
    for (const row of pageRows.value) delete row.values[removed.name]
  }
}

function duplicateRegion(index: number) {
  const source = regions.value[index]
  if (!source) return
  regions.value.push({
    ...source,
    name: `${source.name}_副本`,
    x: Math.min(CANVAS_WIDTH - source.width, source.x + 20),
    y: Math.min(CANVAS_HEIGHT - source.height, source.y + 20),
  })
  selectedRegionIndex.value = regions.value.length - 1
}

function updateRegion(index: number, patch: Partial<YaoyaoRegion>) {
  const current = regions.value[index]
  if (!current) return
  const next = { ...current, ...patch }
  next.x = clamp(next.x, 0, CANVAS_WIDTH - 12)
  next.y = clamp(next.y, 0, CANVAS_HEIGHT - 12)
  next.width = clamp(next.width, 12, CANVAS_WIDTH - next.x)
  next.height = clamp(next.height, 12, CANVAS_HEIGHT - next.y)
  next.angle = Number.isFinite(next.angle) ? next.angle : 0
  regions.value[index] = next
  ensureRowsHaveColumns()
}

function startRegionDrag(event: PointerEvent, index: number, mode: DragMode) {
  const region = regions.value[index]
  if (!region) return
  selectedRegionIndex.value = index
  dragState.value = {
    mode,
    index,
    startX: event.clientX,
    startY: event.clientY,
    original: { ...region },
  }
  window.addEventListener('pointermove', handleRegionDrag)
  window.addEventListener('pointerup', stopRegionDrag, { once: true })
}

function handleRegionDrag(event: PointerEvent) {
  const drag = dragState.value
  if (!drag) return
  const scale = fitScale.value * zoom.value
  const dx = (event.clientX - drag.startX) / scale
  const dy = (event.clientY - drag.startY) / scale
  if (drag.mode === 'move') {
    updateRegion(drag.index, {
      x: Math.round(drag.original.x + dx),
      y: Math.round(drag.original.y + dy),
    })
  } else {
    updateRegion(drag.index, {
      width: Math.round(drag.original.width + dx),
      height: Math.round(drag.original.height + dy),
    })
  }
}

function stopRegionDrag() {
  dragState.value = null
  window.removeEventListener('pointermove', handleRegionDrag)
}

function zoomIn() {
  zoom.value = Math.min(2, Number((zoom.value + 0.1).toFixed(2)))
}

function zoomOut() {
  zoom.value = Math.max(0.5, Number((zoom.value - 0.1).toFixed(2)))
}

function resetZoom() {
  zoom.value = 1
}

async function goToPage(pageIndex: number) {
  if (!sourcePath.value.trim()) return
  const safeIndex = clamp(pageIndex, 0, Math.max(0, pageCount.value - 1))
  await renderPage(safeIndex)
}

async function jumpPage() {
  const value = Number(pageInput.value)
  if (!Number.isFinite(value)) return
  await goToPage(value - 1)
}

async function recognizeCurrentPage() {
  if (!canRecognize.value) {
    errorMessage.value = '请先导入文件并新增至少一个识别框。'
    return
  }
  isRecognizing.value = true
  errorMessage.value = ''
  exportedUrl.value = ''
  try {
    const draft = await createYaoyaoStructuredDraft({
      filePath: sourcePath.value.trim(),
      pageIndex: currentPageIndex.value,
      regions: regions.value,
      renderWidth: CANVAS_WIDTH,
      renderHeight: CANVAS_HEIGHT,
    })
    if (!draft.ok) throw new Error(draft.message || '识别失败')
    upsertRows(draft.pages)
    if (draft.page_count) pageCount.value = draft.page_count
    message.value = `第 ${currentPageIndex.value + 1} 頁識別完成，共 ${draft.field_candidates.length} 個欄位。`
    statusText.value = message.value
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error)
  } finally {
    isRecognizing.value = false
  }
}

async function recognizeAllPages() {
  if (!canRecognize.value) {
    errorMessage.value = '请先导入文件并新增至少一个识别框。'
    return
  }
  isBatching.value = true
  cancelBatch.value = false
  errorMessage.value = ''
  exportedUrl.value = ''
  const total = pageCount.value || 1
  try {
    for (let page = 0; page < total; page += 1) {
      if (cancelBatch.value) break
      statusText.value = `批量識別中：${page + 1} / ${total}`
      const draft = await createYaoyaoStructuredDraft({
        filePath: sourcePath.value.trim(),
        pageIndex: page,
        regions: regions.value,
        renderWidth: CANVAS_WIDTH,
        renderHeight: CANVAS_HEIGHT,
      })
      if (!draft.ok) throw new Error(draft.message || `第 ${page + 1} 頁識別失敗`)
      upsertRows(draft.pages)
    }
    message.value = cancelBatch.value ? '批量識別已取消。' : `批量識別完成，共 ${orderedRows.value.length} 頁。`
    statusText.value = message.value
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error)
  } finally {
    isBatching.value = false
    cancelBatch.value = false
  }
}

function requestCancelBatch() {
  cancelBatch.value = true
}

function upsertRows(rows: Array<{ page_number: number; values: Record<string, string> }>) {
  for (const page of rows) {
    const pageNumber = page.page_number
    const existing = pageRows.value.find((row) => row.pageNumber === pageNumber)
    const values = normalizeValues(page.values || {})
    if (existing) {
      existing.values = { ...existing.values, ...values }
    } else {
      pageRows.value.push({ pageNumber, values })
    }
  }
  ensureRowsHaveColumns()
}

function normalizeValues(values: Record<string, string>) {
  const next: Record<string, string> = {}
  for (const region of regions.value) {
    next[region.name] = values[region.name] ?? ''
  }
  return next
}

function ensureRowsHaveColumns() {
  for (const row of pageRows.value) {
    for (const region of regions.value) {
      if (!(region.name in row.values)) row.values[region.name] = ''
    }
  }
}

function updateCell(row: YaoyaoPageRow, field: string, value: string) {
  row.values[field] = value
}

async function refreshTemplates() {
  try {
    templates.value = await listYaoyaoTemplates()
  } catch {
    templates.value = []
  }
}

async function saveTemplate() {
  if (!regions.value.length) {
    errorMessage.value = '没有可保存的识别框。'
    return
  }
  try {
    const result = await saveYaoyaoTemplate({
      regions: regions.value,
      rows: orderedRows.value.map((row) => ({ page: row.pageNumber, values: row.values })),
      name: templateName.value || undefined,
      templateId: selectedTemplateId.value || undefined,
    })
    selectedTemplateId.value = result.template_id
    templateName.value = result.name
    message.value = `模板已保存：${result.name}`
    await refreshTemplates()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error)
  }
}

async function loadTemplate() {
  if (!selectedTemplateId.value) {
    errorMessage.value = '请选择或输入模板 ID。'
    return
  }
  try {
    const result = await getYaoyaoTemplate(selectedTemplateId.value)
    if (!result.ok || !result.template) throw new Error('模板读取失败')
    regions.value = result.template.regions || []
    templateName.value = result.template.name || ''
    pageRows.value = (result.template.rows || []).map((row) => ({
      pageNumber: row.page,
      values: { ...row.values },
    }))
    selectedRegionIndex.value = regions.value.length ? 0 : -1
    message.value = `模板已载入：${result.template.name}`
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error)
  }
}

async function exportExcel() {
  if (!orderedRows.value.length) {
    errorMessage.value = '请先识别至少一页数据。'
    return
  }
  try {
    const result = await exportYaoyaoStructuredExcel({
      rows: orderedRows.value,
      regions: regions.value,
      fileName: 'ocr_result.xlsx',
    })
    exportedUrl.value = result.download_url
    message.value = `Excel 已导出：${result.file_name}`
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error)
  }
}

function showUsageGuide() {
  message.value = '使用流程：导入 PDF -> 新增并拖动识别框 -> 识别当前页或批量识别 -> 校对右侧表格 -> 导出 Excel。'
}

function previewCrop() {
  const region = regions.value[selectedRegionIndex.value]
  if (!region) {
    message.value = '请先选择一个识别框。'
    return
  }
  message.value = `当前识别框：${region.name}，坐标 ${Math.round(region.x)}, ${Math.round(region.y)}, ${Math.round(region.width)} x ${Math.round(region.height)}，角度 ${region.angle}°。`
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value))
}

const canvasTransformScale = computed(() => Number((fitScale.value * zoom.value).toFixed(3)))

function updateFitScale() {
  const viewport = pdfViewportRef.value
  if (!viewport) return
  const availableWidth = Math.max(120, viewport.clientWidth - 24)
  const availableHeight = Math.max(120, viewport.clientHeight - 24)
  const scale = Math.min(1, availableWidth / CANVAS_WIDTH, availableHeight / CANVAS_HEIGHT)
  fitScale.value = Number(scale.toFixed(3))
}

onMounted(async () => {
  void refreshTemplates()
  await nextTick()
  updateFitScale()
  if (pdfViewportRef.value) {
    fitScaleObserver = new ResizeObserver(() => updateFitScale())
    fitScaleObserver.observe(pdfViewportRef.value)
  }
})

watch(previewUrl, async () => {
  await nextTick()
  updateFitScale()
})

onBeforeUnmount(() => {
  window.removeEventListener('pointermove', handleRegionDrag)
  fitScaleObserver?.disconnect()
  fitScaleObserver = null
})
</script>

<template>
  <main class="ocr-app">
    <section class="ocr-header">
      <div>
        <h1>地盤票據識別助手</h1>
        <p>OCR Document Assistant</p>
      </div>
      <div class="ocr-status">
        <span>當前狀態：</span>
        <strong>{{ statusText }}</strong>
      </div>
    </section>

    <section class="ocr-pathbar">
      <button @click="pickFile">導入 PDF</button>
      <input ref="fileInput" type="file" accept=".pdf,.png,.jpg,.jpeg,.bmp,.webp" class="hidden-input" @change="handleFileSelect" />
      <input v-model="sourcePath" class="path-input" placeholder="或粘贴本地 PDF / 图片绝对路径，例如 E:\\data\\ticket.pdf" @keydown.enter="importCurrentPath" />
      <button @click="importCurrentPath">載入</button>
    </section>

    <section class="ocr-toolbar">
      <button @click="showUsageGuide">使用教學</button>
      <button :disabled="!previewUrl" @click="addRegion">新增識別框</button>
      <button :disabled="selectedRegionIndex < 0" @click="previewCrop">裁剪預覽</button>
      <button :disabled="!canRecognize" @click="recognizeCurrentPage">{{ isRecognizing ? '識別中...' : '識別當前頁' }}</button>
      <button :disabled="!canRecognize" @click="recognizeAllPages">{{ isBatching ? '批量中...' : '批量識別' }}</button>
      <button :disabled="!isBatching" @click="requestCancelBatch">取消批量</button>
      <button :disabled="!regions.length" @click="saveTemplate">儲存模板</button>
      <button :disabled="!selectedTemplateId" @click="loadTemplate">載入模板</button>
      <button :disabled="!orderedRows.length" @click="exportExcel">導出 Excel</button>
    </section>

    <section class="template-row">
      <select v-model="selectedTemplateId">
        <option value="">选择模板</option>
        <option v-for="template in templates" :key="template.id" :value="template.id">
          {{ template.name }} · {{ template.region_count }}框
        </option>
      </select>
      <input v-model="selectedTemplateId" placeholder="模板 ID" />
      <input v-model="templateName" placeholder="模板名称" />
      <a v-if="exportedUrl" class="download-link" :href="exportedUrl" target="_blank" rel="noreferrer">下载 Excel</a>
    </section>

    <p v-if="message" class="notice notice--ok">{{ message }}</p>
    <p v-if="errorMessage" class="notice notice--error">{{ errorMessage }}</p>

    <section class="ocr-workspace">
      <article class="pdf-panel">
        <div ref="pdfViewportRef" class="pdf-viewport">
          <div class="canvas-shell" :style="{ transform: `scale(${canvasTransformScale})` }">
            <img v-if="previewUrl" :src="previewUrl" class="page-image" alt="PDF page preview" />
            <div v-else class="empty-preview">請導入 PDF</div>
            <div class="region-layer">
              <div
                v-for="(region, index) in regions"
                :key="`${region.name}-${index}`"
                class="ocr-region"
                :class="{ 'ocr-region--active': selectedRegionIndex === index }"
                :style="{
                  left: `${region.x}px`,
                  top: `${region.y}px`,
                  width: `${region.width}px`,
                  height: `${region.height}px`,
                  transform: `rotate(${region.angle}deg)`,
                }"
                @pointerdown.prevent="startRegionDrag($event, index, 'move')"
              >
                <span>{{ region.name }} ({{ Math.round(region.angle) }}°)</span>
                <button class="region-resize" title="resize" @pointerdown.prevent.stop="startRegionDrag($event, index, 'resize')"></button>
              </div>
            </div>
          </div>

          <div class="zoom-controls">
            <button @click="zoomOut">-</button>
            <button @click="resetZoom">1:1</button>
            <button @click="zoomIn">+</button>
          </div>
        </div>
      </article>

      <article class="result-panel">
        <div class="result-table-wrap">
          <table class="result-table">
            <thead>
              <tr>
                <th v-for="column in tableColumns" :key="column">{{ column }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in orderedRows" :key="row.pageNumber">
                <td>{{ row.pageNumber }}</td>
                <td v-for="region in regions" :key="`${row.pageNumber}-${region.name}`">
                  <input :value="row.values[region.name] || ''" @input="updateCell(row, region.name, ($event.target as HTMLInputElement).value)" />
                </td>
              </tr>
              <tr v-if="!orderedRows.length">
                <td :colspan="Math.max(1, tableColumns.length)">尚未識別，結果會顯示在這裡。</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>
    </section>

    <section class="region-editor">
      <div class="region-list">
        <button
          v-for="(region, index) in regions"
          :key="`${region.name}-tab-${index}`"
          :class="{ active: selectedRegionIndex === index }"
          @click="selectedRegionIndex = index"
        >
          {{ region.name }}
        </button>
      </div>
      <div v-if="regions[selectedRegionIndex]" class="region-fields">
        <label>
          名稱
          <input :value="regions[selectedRegionIndex].name" @input="updateRegion(selectedRegionIndex, { name: ($event.target as HTMLInputElement).value })" />
        </label>
        <label>
          X
          <input type="number" :value="regions[selectedRegionIndex].x" @input="updateRegion(selectedRegionIndex, { x: Number(($event.target as HTMLInputElement).value) })" />
        </label>
        <label>
          Y
          <input type="number" :value="regions[selectedRegionIndex].y" @input="updateRegion(selectedRegionIndex, { y: Number(($event.target as HTMLInputElement).value) })" />
        </label>
        <label>
          W
          <input type="number" :value="regions[selectedRegionIndex].width" @input="updateRegion(selectedRegionIndex, { width: Number(($event.target as HTMLInputElement).value) })" />
        </label>
        <label>
          H
          <input type="number" :value="regions[selectedRegionIndex].height" @input="updateRegion(selectedRegionIndex, { height: Number(($event.target as HTMLInputElement).value) })" />
        </label>
        <label>
          角度
          <input type="number" :value="regions[selectedRegionIndex].angle" @input="updateRegion(selectedRegionIndex, { angle: Number(($event.target as HTMLInputElement).value) })" />
        </label>
        <button @click="duplicateRegion(selectedRegionIndex)">复制</button>
        <button class="danger" @click="removeRegion(selectedRegionIndex)">删除</button>
      </div>
      <p v-else class="region-empty">新增或选择一个识别框后，可在这里精确调整坐标。</p>
    </section>

    <section class="pager">
      <button :disabled="currentPageIndex <= 0 || isRendering" @click="goToPage(currentPageIndex - 1)">上一頁</button>
      <span>頁碼：</span>
      <input v-model="pageInput" @keydown.enter="jumpPage" />
      <span>/ {{ pageCount || 0 }}</span>
      <button :disabled="isRendering" @click="jumpPage">跳轉</button>
      <button :disabled="!pageCount || currentPageIndex >= pageCount - 1 || isRendering" @click="goToPage(currentPageIndex + 1)">下一頁</button>
    </section>
  </main>
</template>

<style scoped>
.ocr-app {
  background: #f4f6fa;
  color: #1d2b45;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: calc(100vh - 56px);
  padding: 10px;
}

.ocr-header,
.ocr-pathbar,
.ocr-toolbar,
.template-row,
.pager,
.region-editor {
  background: #fff;
  border: 1px solid #d8e1ee;
  border-radius: 10px;
  box-shadow: 0 1px 3px rgba(29, 43, 69, 0.06);
}

.ocr-header {
  align-items: center;
  display: grid;
  gap: 34px;
  grid-template-columns: minmax(360px, auto) 1fr;
  min-height: 86px;
  padding: 8px 14px;
}

.ocr-header h1 {
  color: #1d2b45;
  font-size: 34px;
  font-weight: 800;
  letter-spacing: -0.5px;
  line-height: 1;
  margin: 0;
}

.ocr-header p {
  color: #6b7893;
  font-size: 14px;
  margin: 4px 0 0;
}

.ocr-status {
  align-items: center;
  color: #344563;
  display: flex;
  font-size: 14px;
  gap: 8px;
  justify-self: start;
}

.ocr-status strong {
  color: #1d2b45;
}

.ocr-pathbar,
.ocr-toolbar,
.template-row,
.pager {
  align-items: center;
  display: flex;
  gap: 8px;
  padding: 7px 8px;
}

.ocr-toolbar {
  flex-wrap: wrap;
}

.template-row {
  background: #fbfcff;
  border-color: #e0e7f2;
}

.path-input,
.template-row input,
.template-row select,
.pager input,
.region-fields input,
.result-table input {
  background: #fff;
  border: 1px solid #bfcbe0;
  border-radius: 3px;
  color: #1d2b45;
  padding: 5px 8px;
}

.path-input {
  flex: 1;
}

button,
.download-link {
  background: #fff;
  border: 1px solid #bfcbe0;
  border-radius: 3px;
  color: #1d2b45;
  cursor: pointer;
  font-size: 12px;
  font-weight: 700;
  min-height: 30px;
  padding: 5px 11px;
  text-decoration: none;
}

button:hover,
.download-link:hover {
  background: rgba(15, 158, 213, 0.08);
  border-color: var(--brand-cyan, #0f9ed5);
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.hidden-input {
  display: none;
}

.notice {
  border-radius: 8px;
  margin: 0;
  padding: 8px 10px;
}

.notice--ok {
  background: rgba(67, 160, 71, 0.12);
  color: var(--risk-low, #2e7d32);
}

.notice--error {
  background: rgba(229, 57, 53, 0.12);
  color: var(--risk-high, #c62828);
}

.ocr-workspace {
  display: grid;
  flex: 0 0 auto;
  gap: 12px;
  grid-template-columns: minmax(0, 2.1fr) minmax(0, 2.2fr);
}

.pdf-panel,
.result-panel {
  aspect-ratio: 11 / 10;
  background: #fff;
  border: 1px solid #c8d1e0;
  border-radius: 8px;
  max-height: min(42vw, 460px);
  min-height: 0;
  overflow: hidden;
  width: 100%;
}

.result-panel {
  background: #2f3640;
  padding: 8px;
}

.pdf-viewport {
  align-items: center;
  background: #f8faff;
  display: flex;
  height: 100%;
  justify-content: center;
  min-height: 0;
  overflow: auto;
  position: relative;
}

.canvas-shell {
  height: 1200px;
  position: relative;
  transform-origin: center;
  width: 900px;
}

.page-image,
.region-layer,
.empty-preview {
  height: 1200px;
  left: 0;
  position: absolute;
  top: 0;
  width: 900px;
}

.page-image {
  object-fit: contain;
}

.empty-preview {
  align-items: center;
  background: linear-gradient(135deg, #f8fbff, #eef3fb);
  color: #6b7893;
  display: flex;
  font-size: 28px;
  font-weight: 800;
  justify-content: center;
}

.region-layer {
  pointer-events: none;
}

.ocr-region {
  background: rgba(0, 191, 255, 0.16);
  border: 2px solid deepskyblue;
  cursor: move;
  pointer-events: auto;
  position: absolute;
  transform-origin: center;
}

.ocr-region--active {
  border-color: #ff9800;
  box-shadow: 0 0 0 2px rgba(255, 152, 0, 0.22);
}

.ocr-region span {
  background: deepskyblue;
  color: white;
  display: inline-block;
  font-size: 12px;
  font-weight: 700;
  padding: 2px 5px;
}

.region-resize {
  background: deepskyblue;
  border: none;
  border-radius: 0;
  bottom: -1px;
  height: 16px;
  min-width: 0;
  padding: 0;
  position: absolute;
  right: -1px;
  width: 16px;
}

.zoom-controls {
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid var(--border-normal, #bfcbe0);
  border-radius: 8px;
  bottom: 12px;
  display: flex;
  gap: 6px;
  padding: 6px;
  position: absolute;
  right: 12px;
}

.result-table-wrap {
  background: #fff;
  border: 1px solid #1f252d;
  height: 100%;
  overflow: auto;
}

.result-table {
  border-collapse: collapse;
  min-width: 100%;
}

.result-table th,
.result-table td {
  border: 1px solid #9ca8b9;
  min-width: 140px;
  padding: 3px 4px;
  text-align: left;
}

.result-table th {
  background: #eef2f8;
  color: #1d2b45;
  font-size: 12px;
  font-weight: 700;
  position: sticky;
  top: 0;
  z-index: 1;
}

.result-table input {
  border: none;
  border-radius: 0;
  min-width: 120px;
  padding: 3px 4px;
  width: 100%;
}

.region-editor {
  display: grid;
  gap: 8px;
  grid-template-columns: 260px 1fr;
  padding: 8px;
}

.region-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.region-list button.active {
  background: var(--brand-cyan, #0f9ed5);
  border-color: var(--brand-cyan, #0f9ed5);
  color: white;
}

.region-fields {
  align-items: end;
  display: grid;
  gap: 8px;
  grid-template-columns: 1.3fr repeat(5, 90px) auto auto;
}

.region-fields label {
  color: var(--text-secondary, #6b7893);
  display: grid;
  font-size: 12px;
  gap: 3px;
}

.danger {
  color: var(--risk-high, #c62828);
}

.region-empty {
  color: var(--text-secondary, #6b7893);
  margin: 0;
}

.pager {
  justify-content: center;
  min-height: 42px;
}

.pager input {
  width: 70px;
}

@media (max-width: 1200px) {
  .ocr-workspace,
  .region-editor {
    grid-template-columns: 1fr;
  }

  .region-fields {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
