<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import {
  createYaoyaoStructuredDraft,
  confirmYaoyaoStructuredDraft,
  listYaoyaoTemplates,
  saveYaoyaoTemplate,
  getYaoyaoTemplate,
} from '../services/chitungApi'
import type {
  YaoyaoRegion,
  YaoyaoFieldCandidate,
  YaoyaoStructuredDraft,
  YaoyaoTemplateListItem,
} from '../types/domain'

// ── State ──────────────────────────────────────────────────────

const filePath = ref('')
const isExtracting = ref(false)
const isConfirming = ref(false)
const draft = ref<YaoyaoStructuredDraft | null>(null)
const errorMessage = ref('')
const successMessage = ref('')
const logs = ref<string[]>([])

// Region management
const regions = ref<YaoyaoRegion[]>([])
const newRegionName = ref('')
const selectedRegionIndex = ref(-1)

// Template management
const templateIdInput = ref('')
const templateNameInput = ref('')
const availableTemplates = ref<YaoyaoTemplateListItem[]>([])

// Editable field values (field_name -> edited value)
const editedFields = ref<Record<string, string>>({})

// ── Computed ───────────────────────────────────────────────────

const fieldCandidates = computed<YaoyaoFieldCandidate[]>(() => {
  return draft.value?.field_candidates ?? []
})

// ── Actions ────────────────────────────────────────────────────

function log(msg: string) {
  const ts = new Date().toLocaleTimeString()
  logs.value.unshift(`[${ts}] ${msg}`)
  if (logs.value.length > 50) logs.value.pop()
}

function handleFileSelect(event: Event) {
  const input = event.target as HTMLInputElement
  if (input.files && input.files.length > 0) {
    // In a desktop context, the file path may be available.
    // For web context, we use the file name as a placeholder.
    const file = input.files[0]
    // @ts-expect-error - path is available in Electron/desktop contexts
    filePath.value = file.path || ''
    if (!filePath.value) {
      errorMessage.value = '当前浏览器环境拿不到本地绝对路径，请手动输入文件路径（桌面版可自动识别）。'
      log(`File selected without absolute path: ${file.name}`)
      return
    }
    log(`File selected: ${filePath.value}`)
  }
}

async function refreshTemplates() {
  try {
    availableTemplates.value = await listYaoyaoTemplates()
  } catch {
    availableTemplates.value = []
  }
}

function addRegion() {
  if (!newRegionName.value.trim()) {
    errorMessage.value = 'Please enter a region name.'
    return
  }
  regions.value.push({
    name: newRegionName.value.trim(),
    x: 50,
    y: 50,
    width: 200,
    height: 60,
    angle: 0,
  })
  newRegionName.value = ''
  log(`Region added: ${regions.value[regions.value.length - 1].name}`)
}

function removeRegion(index: number) {
  const name = regions.value[index]?.name
  regions.value.splice(index, 1)
  if (selectedRegionIndex.value === index) {
    selectedRegionIndex.value = -1
  }
  log(`Region removed: ${name}`)
}

function updateRegion(index: number, field: keyof YaoyaoRegion, value: number) {
  if (index >= 0 && index < regions.value.length) {
    regions.value[index] = { ...regions.value[index], [field]: value }
  }
}

async function handleExtract() {
  if (!filePath.value) {
    errorMessage.value = 'Please select a file first.'
    return
  }

  isExtracting.value = true
  errorMessage.value = ''
  successMessage.value = ''
  log(`Starting structured extraction: ${filePath.value}`)

  try {
    const result = await createYaoyaoStructuredDraft({
      filePath: filePath.value,
      regions: regions.value.length > 0 ? regions.value : undefined,
      templateId: templateIdInput.value || undefined,
    })
    draft.value = result
    // Initialize editable fields with OCR results.
    editedFields.value = {}
    for (const fc of result.field_candidates) {
      editedFields.value[fc.field_name] = fc.value
    }
    log(`Extraction complete: ${result.field_candidates.length} fields, ${result.page_count} pages, ${result.elapsed_seconds}s`)
    if (!result.ok) {
      errorMessage.value = result.message
    }
  } catch (err) {
    errorMessage.value = String(err)
    log(`Extraction error: ${err}`)
  } finally {
    isExtracting.value = false
  }
}

async function handleConfirm() {
  if (!draft.value) return

  isConfirming.value = true
  errorMessage.value = ''
  log('Confirming structured input...')

  try {
    const result = await confirmYaoyaoStructuredDraft({
      draftId: draft.value.draft_id,
      fields: editedFields.value,
      templateId: draft.value.confirm_payload?.template_id ?? undefined,
      caseId: draft.value.confirm_payload?.case_id ?? undefined,
      notes: 'Confirmed from Yaoyao structured input page.',
    })
    if (result.ok) {
      successMessage.value = `Record written: ${result.record_id} (audit: ${result.audit_id})`
      log(`Confirmation successful: record_id=${result.record_id}, audit_id=${result.audit_id}`)
    } else {
      errorMessage.value = result.message
      log(`Confirmation failed: ${result.message}`)
    }
  } catch (err) {
    errorMessage.value = String(err)
    log(`Confirmation error: ${err}`)
  } finally {
    isConfirming.value = false
  }
}

async function handleSaveTemplate() {
  if (regions.value.length === 0) {
    errorMessage.value = 'No regions to save.'
    return
  }

  try {
    const result = await saveYaoyaoTemplate({
      regions: regions.value,
      name: templateNameInput.value || undefined,
      templateId: templateIdInput.value || undefined,
    })
    if (result.ok) {
      templateIdInput.value = result.template_id
      successMessage.value = `Template saved: ${result.template_id}`
      log(`Template saved: ${result.template_id} (${result.name})`)
      await refreshTemplates()
    }
  } catch (err) {
    errorMessage.value = String(err)
    log(`Template save error: ${err}`)
  }
}

async function handleLoadTemplate() {
  if (!templateIdInput.value.trim()) {
    errorMessage.value = 'Please enter a template ID.'
    return
  }

  try {
    const result = await getYaoyaoTemplate(templateIdInput.value.trim())
    if (result.ok && result.template) {
      regions.value = result.template.regions || []
      templateNameInput.value = result.template.name || ''
      log(`Template loaded: ${result.template.id} (${regions.value.length} regions)`)
    }
  } catch (err) {
    errorMessage.value = String(err)
    log(`Template load error: ${err}`)
  }
}

function applyTemplateFromList(templateId: string) {
  templateIdInput.value = templateId
  void handleLoadTemplate()
}

function confidenceLabel(score: number): string {
  if (score >= 0.9) return 'High'
  if (score >= 0.7) return 'Medium'
  return 'Low'
}

function confidenceTone(score: number): string {
  if (score >= 0.9) return 'yaoyao-conf--high'
  if (score >= 0.7) return 'yaoyao-conf--medium'
  return 'yaoyao-conf--low'
}

onMounted(() => {
  void refreshTemplates()
})
</script>

<template>
  <div class="yaoyao-page">
    <!-- Top bar: file + template -->
    <div class="yaoyao-toolbar">
      <div class="yaoyao-toolbar__left">
        <label class="yaoyao-file-btn">
          <input type="file" accept=".pdf,.png,.jpg,.jpeg,.bmp,.tiff" @change="handleFileSelect" />
          <span>Choose File</span>
        </label>
        <input
          v-model="filePath"
          class="yaoyao-input yaoyao-input--path"
          placeholder="Or paste absolute file path here..."
        />
        <span class="yaoyao-filepath" v-if="filePath">{{ filePath }}</span>
      </div>
      <div class="yaoyao-toolbar__right">
        <input
          v-model="templateIdInput"
          class="yaoyao-input"
          placeholder="Template ID"
        />
        <input
          v-model="templateNameInput"
          class="yaoyao-input"
          placeholder="Template name"
        />
        <button class="yaoyao-btn yaoyao-btn--ghost" @click="handleLoadTemplate">Load</button>
        <button class="yaoyao-btn yaoyao-btn--ghost" @click="handleSaveTemplate">Save Template</button>
        <button class="yaoyao-btn yaoyao-btn--ghost" @click="refreshTemplates">Refresh List</button>
      </div>
    </div>

    <!-- Main content: left regions / right results -->
    <div class="yaoyao-body">
      <!-- Left: regions management -->
      <div class="yaoyao-left">
        <div class="yaoyao-panel">
          <div class="yaoyao-panel__header">
            <h3 class="yaoyao-panel__title">Recognition Regions</h3>
            <span class="yaoyao-panel__count">{{ regions.length }}</span>
          </div>

          <div class="yaoyao-add-region">
            <input
              v-model="newRegionName"
              class="yaoyao-input"
              placeholder="Region name (e.g. company_name)"
              @keyup.enter="addRegion"
            />
            <button class="yaoyao-btn yaoyao-btn--sm" @click="addRegion">+ Add</button>
          </div>

          <div v-if="availableTemplates.length" class="yaoyao-template-list">
            <h4>Saved Templates</h4>
            <button
              v-for="tpl in availableTemplates"
              :key="tpl.id"
              class="yaoyao-template-item"
              @click="applyTemplateFromList(tpl.id)"
            >
              <span>{{ tpl.name }}</span>
              <small>{{ tpl.id }} · {{ tpl.region_count }} regions</small>
            </button>
          </div>

          <div class="yaoyao-region-list" v-if="regions.length > 0">
            <div
              v-for="(region, idx) in regions"
              :key="idx"
              class="yaoyao-region-item"
              :class="{ 'yaoyao-region-item--active': selectedRegionIndex === idx }"
              @click="selectedRegionIndex = idx"
            >
              <div class="yaoyao-region-item__header">
                <span class="yaoyao-region-item__name">{{ region.name }}</span>
                <button class="yaoyao-region-item__del" @click.stop="removeRegion(idx)">x</button>
              </div>
              <div class="yaoyao-region-item__coords" v-if="selectedRegionIndex === idx">
                <label>X <input type="number" class="yaoyao-mini-input" :value="region.x" @input="updateRegion(idx, 'x', +($event.target as HTMLInputElement).value)" /></label>
                <label>Y <input type="number" class="yaoyao-mini-input" :value="region.y" @input="updateRegion(idx, 'y', +($event.target as HTMLInputElement).value)" /></label>
                <label>W <input type="number" class="yaoyao-mini-input" :value="region.width" @input="updateRegion(idx, 'width', +($event.target as HTMLInputElement).value)" /></label>
                <label>H <input type="number" class="yaoyao-mini-input" :value="region.height" @input="updateRegion(idx, 'height', +($event.target as HTMLInputElement).value)" /></label>
                <label>Rot <input type="number" class="yaoyao-mini-input" :value="region.angle" @input="updateRegion(idx, 'angle', +($event.target as HTMLInputElement).value)" /></label>
              </div>
            </div>
          </div>

          <div class="yaoyao-empty" v-else>
            <p>No regions defined. Add regions above or run extraction without regions for full-page OCR.</p>
          </div>

          <div class="yaoyao-actions">
            <button
              class="yaoyao-btn yaoyao-btn--primary"
              :disabled="isExtracting || !filePath"
              @click="handleExtract"
            >
              {{ isExtracting ? 'Extracting...' : 'Run OCR Extraction' }}
            </button>
          </div>
        </div>
      </div>

      <!-- Right: results + confirm -->
      <div class="yaoyao-right">
        <div class="yaoyao-panel">
          <div class="yaoyao-panel__header">
            <h3 class="yaoyao-panel__title">Field Results</h3>
            <span class="yaoyao-panel__count" v-if="fieldCandidates.length">{{ fieldCandidates.length }}</span>
          </div>

          <div v-if="fieldCandidates.length > 0" class="yaoyao-results">
            <table class="yaoyao-table">
              <thead>
                <tr>
                  <th>Field</th>
                  <th>OCR Value</th>
                  <th>Confidence</th>
                  <th>Page</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="fc in fieldCandidates" :key="fc.field_name">
                  <td class="yaoyao-table__field">{{ fc.field_name }}</td>
                  <td>
                    <input
                      v-model="editedFields[fc.field_name]"
                      class="yaoyao-table__input"
                    />
                  </td>
                  <td>
                    <span class="yaoyao-conf" :class="confidenceTone(fc.confidence)">
                      {{ confidenceLabel(fc.confidence) }} ({{ (fc.confidence * 100).toFixed(0) }}%)
                    </span>
                  </td>
                  <td class="yaoyao-table__page">{{ fc.page_number }}</td>
                </tr>
              </tbody>
            </table>

            <div class="yaoyao-confirm-bar">
              <button
                class="yaoyao-btn yaoyao-btn--success"
                :disabled="isConfirming"
                @click="handleConfirm"
              >
                {{ isConfirming ? 'Writing...' : 'Confirm & Write to Records' }}
              </button>
              <span class="yaoyao-hint">Fields are editable. Review before confirming.</span>
            </div>
          </div>

          <div class="yaoyao-empty" v-else-if="!isExtracting">
            <p>Run OCR extraction to see field results here.</p>
          </div>
          <div class="yaoyao-loading" v-else>
            <p>Extracting... please wait.</p>
          </div>
        </div>

        <!-- Draft metadata -->
        <div class="yaoyao-panel" v-if="draft">
          <div class="yaoyao-panel__header">
            <h3 class="yaoyao-panel__title">Draft Info</h3>
          </div>
          <dl class="yaoyao-meta">
            <dt>Draft ID</dt><dd>{{ draft.draft_id }}</dd>
            <dt>Pages</dt><dd>{{ draft.page_count }}</dd>
            <dt>Elapsed</dt><dd>{{ draft.elapsed_seconds }}s</dd>
            <dt>Requires Acceptance</dt><dd>{{ draft.requires_acceptance ? 'Yes' : 'No' }}</dd>
          </dl>
        </div>
      </div>
    </div>

    <!-- Bottom: logs & messages -->
    <div class="yaoyao-footer">
      <div v-if="errorMessage" class="yaoyao-alert yaoyao-alert--error">{{ errorMessage }}</div>
      <div v-if="successMessage" class="yaoyao-alert yaoyao-alert--success">{{ successMessage }}</div>
      <div class="yaoyao-logs" v-if="logs.length > 0">
        <div v-for="(line, i) in logs" :key="i" class="yaoyao-logs__line">{{ line }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.yaoyao-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  gap: var(--space-4);
  padding: var(--space-4);
  overflow: hidden;
}

.yaoyao-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-3) var(--space-4);
  background: var(--bg-white);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
}

.yaoyao-toolbar__left,
.yaoyao-toolbar__right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.yaoyao-file-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  background: var(--brand-cyan);
  color: var(--text-white);
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 13px;
}

.yaoyao-file-btn input {
  display: none;
}

.yaoyao-filepath {
  color: var(--text-secondary);
  font-size: 13px;
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.yaoyao-input {
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border-normal);
  border-radius: var(--radius-sm);
  font-size: 13px;
  width: 120px;
}

.yaoyao-input--path {
  width: 280px;
}

.yaoyao-body {
  display: flex;
  gap: var(--space-4);
  flex: 1;
  overflow: hidden;
}

.yaoyao-left {
  width: 40%;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  overflow: hidden;
}

.yaoyao-right {
  width: 60%;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  overflow: auto;
}

.yaoyao-panel {
  background: var(--bg-white);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.yaoyao-panel__header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.yaoyao-panel__title {
  font-size: 15px;
  font-weight: 600;
  margin: 0;
}

.yaoyao-panel__count {
  background: var(--bg-active);
  color: var(--brand-cyan);
  font-size: 12px;
  padding: 2px 8px;
  border-radius: var(--radius-round);
}

.yaoyao-add-region {
  display: flex;
  gap: var(--space-2);
}

.yaoyao-add-region .yaoyao-input {
  flex: 1;
  width: auto;
}

.yaoyao-region-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  overflow-y: auto;
  max-height: 300px;
}

.yaoyao-template-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.yaoyao-template-list h4 {
  margin: 0;
  font-size: 12px;
  color: var(--text-secondary);
}

.yaoyao-template-item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  padding: 6px 8px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  background: var(--bg-subtle);
  cursor: pointer;
  text-align: left;
}

.yaoyao-template-item small {
  color: var(--text-muted);
  font-size: 11px;
}

.yaoyao-region-item {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  padding: var(--space-2) var(--space-3);
  cursor: pointer;
  transition: border-color 0.15s;
}

.yaoyao-region-item--active {
  border-color: var(--brand-cyan);
  background: var(--bg-active);
}

.yaoyao-region-item__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.yaoyao-region-item__name {
  font-weight: 500;
  font-size: 13px;
}

.yaoyao-region-item__del {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 14px;
}

.yaoyao-region-item__del:hover {
  color: var(--color-error);
}

.yaoyao-region-item__coords {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

.yaoyao-region-item__coords label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--text-secondary);
}

.yaoyao-mini-input {
  width: 50px;
  padding: 2px 4px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-xs);
  font-size: 11px;
}

.yaoyao-empty {
  padding: var(--space-6);
  text-align: center;
  color: var(--text-muted);
  font-size: 13px;
}

.yaoyao-loading {
  padding: var(--space-6);
  text-align: center;
  color: var(--brand-cyan);
  font-size: 13px;
}

.yaoyao-actions {
  margin-top: var(--space-2);
}

.yaoyao-btn {
  padding: var(--space-2) var(--space-4);
  border: none;
  border-radius: var(--radius-sm);
  font-size: 13px;
  cursor: pointer;
  transition: opacity 0.15s;
}

.yaoyao-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.yaoyao-btn--primary {
  background: var(--brand-cyan);
  color: var(--text-white);
  width: 100%;
}

.yaoyao-btn--success {
  background: var(--color-success);
  color: var(--text-white);
}

.yaoyao-btn--ghost {
  background: var(--bg-subtle);
  color: var(--text-primary);
  border: 1px solid var(--border-normal);
}

.yaoyao-btn--sm {
  padding: var(--space-1) var(--space-3);
  font-size: 12px;
}

.yaoyao-results {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.yaoyao-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.yaoyao-table th {
  text-align: left;
  padding: var(--space-2) var(--space-3);
  background: var(--bg-subtle);
  color: var(--text-secondary);
  font-weight: 500;
  border-bottom: 1px solid var(--border-light);
}

.yaoyao-table td {
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border-light);
}

.yaoyao-table__field {
  font-weight: 500;
  white-space: nowrap;
}

.yaoyao-table__input {
  width: 100%;
  padding: 4px 8px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-xs);
  font-size: 13px;
}

.yaoyao-table__input:focus {
  border-color: var(--brand-cyan);
  outline: none;
}

.yaoyao-table__page {
  color: var(--text-muted);
  text-align: center;
}

.yaoyao-conf {
  font-size: 12px;
  padding: 2px 6px;
  border-radius: var(--radius-xs);
}

.yaoyao-conf--high {
  background: #e8f5e9;
  color: var(--color-success);
}

.yaoyao-conf--medium {
  background: #fff3e0;
  color: var(--color-warning);
}

.yaoyao-conf--low {
  background: #ffebee;
  color: var(--color-error);
}

.yaoyao-confirm-bar {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-light);
}

.yaoyao-hint {
  font-size: 12px;
  color: var(--text-muted);
}

.yaoyao-meta {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: var(--space-1) var(--space-4);
  font-size: 13px;
}

.yaoyao-meta dt {
  color: var(--text-secondary);
}

.yaoyao-meta dd {
  margin: 0;
}

.yaoyao-footer {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.yaoyao-alert {
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-sm);
  font-size: 13px;
}

.yaoyao-alert--error {
  background: #ffebee;
  color: var(--color-error);
}

.yaoyao-alert--success {
  background: #e8f5e9;
  color: var(--color-success);
}

.yaoyao-logs {
  background: var(--bg-white);
  border-radius: var(--radius-sm);
  padding: var(--space-2) var(--space-3);
  max-height: 120px;
  overflow-y: auto;
  box-shadow: var(--shadow-sm);
}

.yaoyao-logs__line {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-secondary);
  line-height: 1.8;
}
</style>
