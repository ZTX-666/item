<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { deleteSkill, getSkillDetail, getSkills, importSkill, saveSkillConfig, testSkill, toggleSkill } from '../services/chitungApi'
import type { SkillDetail, SkillInfo } from '../types/domain'

const skills = ref<SkillInfo[]>([])
const selected = ref<SkillDetail | null>(null)
const loading = ref(false)
const query = ref('')
const error = ref('')
const importName = ref('')
const importContent = ref('')
const configText = ref('')
const isSavingConfig = ref(false)
const isTestingSkill = ref(false)
const testResult = ref<Record<string, unknown> | null>(null)

const filteredSkills = computed(() => {
  const value = query.value.trim().toLowerCase()
  if (!value) return skills.value
  return skills.value.filter((skill) => {
    return skill.name.toLowerCase().includes(value) || skill.summary.toLowerCase().includes(value)
  })
})

async function refresh() {
  loading.value = true
  error.value = ''
  try {
    skills.value = await getSkills()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
}

async function openSkill(name: string) {
  try {
    selected.value = await getSkillDetail(name)
    configText.value = selected.value.config ? JSON.stringify(selected.value.config, null, 2) : ''
    testResult.value = null
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function handleToggle(skill: SkillInfo) {
  try {
    await toggleSkill(skill.name, !skill.enabled)
    await refresh()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function handleImport() {
  try {
    await importSkill(importName.value, importContent.value)
    importName.value = ''
    importContent.value = ''
    await refresh()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function handleDelete(skill: SkillInfo) {
  try {
    await deleteSkill(skill.name)
    if (selected.value?.name === skill.name) selected.value = null
    await refresh()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function handleSaveConfig() {
  if (!selected.value || isSavingConfig.value) return
  isSavingConfig.value = true
  error.value = ''
  try {
    const parsed = configText.value.trim() ? JSON.parse(configText.value) : {}
    const result = await saveSkillConfig(selected.value.name, parsed)
    selected.value.config = (result.config as Record<string, unknown> | undefined) ?? parsed
    configText.value = JSON.stringify(selected.value.config, null, 2)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    isSavingConfig.value = false
  }
}

async function handleTestSkill() {
  if (!selected.value || isTestingSkill.value) return
  isTestingSkill.value = true
  error.value = ''
  try {
    testResult.value = await testSkill(selected.value.name)
    selected.value = await getSkillDetail(selected.value.name)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    isTestingSkill.value = false
  }
}

function dependencyLabel(item: Record<string, unknown>): string {
  const name = String(item.name || 'dependency')
  if (item.available === false) return `${name}：不可用`
  if (item.available === true) return `${name}：可用`
  return `${name}：未声明`
}

function formatRunTime(value?: string | null): string {
  if (!value) return '-'
  try {
    return new Date(value).toLocaleString('zh-CN')
  } catch {
    return value
  }
}

function testResultText(): string {
  const result = testResult.value?.result
  if (result && typeof result === 'object') {
    const message = (result as Record<string, unknown>).message
    if (typeof message === 'string') return message
  }
  return testResult.value?.ok ? 'Skill 测试完成。' : 'Skill 测试失败。'
}

onMounted(refresh)
</script>

<template>
  <main class="workbench">
    <section class="hero-panel">
      <div>
        <p class="eyebrow">Skill Market</p>
        <h1>Skill 技能</h1>
        <p>管理中台 Skill.md：列表、详情、启停、导入和外部 Skill 删除。</p>
      </div>
      <button class="primary-soft-button" :disabled="loading" @click="refresh">
        {{ loading ? '刷新中...' : '刷新' }}
      </button>
    </section>

    <section class="panel">
      <div class="panel__header">
        <div>
          <h2>已接入技能</h2>
          <p>{{ filteredSkills.length }} / {{ skills.length }} 个 Skill.md</p>
        </div>
        <input v-model="query" class="compat-search" placeholder="搜索技能名称或摘要" />
      </div>
      <p v-if="error" class="compat-error">{{ error }}</p>
      <div class="compat-card-grid">
        <article v-for="skill in filteredSkills" :key="skill.name" class="compat-card">
          <strong @click="openSkill(skill.name)">{{ skill.display_name || skill.name }}</strong>
          <p>{{ skill.description || skill.summary }}</p>
          <div v-if="skill.triggers?.length" class="compat-tags">
            <span v-for="trigger in skill.triggers.slice(0, 4)" :key="`${skill.name}-${trigger}`">{{ trigger }}</span>
          </div>
          <div class="compat-badges">
            <span>{{ skill.enabled === false ? '已停用' : '已启用' }}</span>
            <span>{{ skill.tools?.length || 0 }} 个依赖</span>
            <span>{{ skill.workflow || '无绑定工作流' }}</span>
          </div>
          <div class="compat-actions">
            <button class="mini-button" @click="openSkill(skill.name)">详情</button>
            <button class="mini-button" @click="handleToggle(skill)">
              {{ skill.enabled === false ? '启用' : '禁用' }}
            </button>
            <button
              class="mini-button"
              :disabled="skill.category !== 'external'"
              @click="handleDelete(skill)"
            >
              删除
            </button>
          </div>
          <small>{{ skill.path }}</small>
        </article>
      </div>
    </section>

    <section class="panel">
      <div class="panel__header">
        <div>
          <h2>导入外部 Skill</h2>
          <p>会写入 `skills/{name}/SKILL.md`，category 标记为 external。</p>
        </div>
      </div>
      <div class="compat-import">
        <input v-model="importName" placeholder="skill-name" />
        <textarea v-model="importContent" rows="8" placeholder="# Skill Name&#10;&#10;Skill content..." />
        <button class="primary-soft-button" :disabled="!importName.trim() || !importContent.trim()" @click="handleImport">
          导入 Skill
        </button>
      </div>
    </section>

    <section v-if="selected" class="panel">
      <div class="panel__header">
        <div>
          <h2>{{ selected.name }}</h2>
          <p>配置、依赖、调用记录和测试入口</p>
        </div>
        <div class="compat-actions">
          <button class="mini-button" :disabled="isTestingSkill" @click="handleTestSkill">
            {{ isTestingSkill ? '测试中...' : '测试 Skill' }}
          </button>
          <button class="mini-button" @click="selected = null">关闭</button>
        </div>
      </div>
      <div class="skill-ops-grid">
        <div class="skill-ops-card">
          <h3>依赖状态</h3>
          <p v-if="!selected.dependencies?.length">该 Skill 暂未声明工具依赖。</p>
          <span
            v-for="dep in selected.dependencies"
            :key="String(dep.name)"
            class="skill-dependency"
            :class="{ 'skill-dependency--bad': dep.available === false }"
          >
            {{ dependencyLabel(dep) }}
          </span>
        </div>
        <div class="skill-ops-card">
          <h3>最近调用</h3>
          <p v-if="!selected.recent_runs?.length">暂无统一任务记录。</p>
          <div v-for="run in selected.recent_runs?.slice(0, 5)" :key="run.job_id" class="skill-run-row">
            <strong>{{ run.title }}</strong>
            <span>{{ run.status }} · {{ run.progress }}% · {{ formatRunTime(run.created_at) }}</span>
          </div>
        </div>
      </div>
      <p v-if="testResult" class="compat-test-result">
        {{ testResultText() }}
      </p>
      <pre class="compat-markdown">{{ selected.content }}</pre>
      <div class="compat-config">
        <div class="panel__header">
          <div>
            <h2>配置 JSON</h2>
            <p>用于来源、关键词、媒体抓取边界等 sidecar 配置。</p>
          </div>
          <button class="mini-button" :disabled="isSavingConfig" @click="handleSaveConfig">
            {{ isSavingConfig ? '保存中...' : '保存配置' }}
          </button>
        </div>
        <textarea v-model="configText" rows="12" placeholder="{ }" />
      </div>
    </section>
  </main>
</template>

<style scoped>
.compat-search {
  border: 1px solid var(--border-light);
  border-radius: 8px;
  min-width: 240px;
  padding: 8px 10px;
}

.compat-error {
  color: var(--color-error);
  margin-bottom: 12px;
}

.compat-card-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
}

.compat-card {
  border: 1px solid var(--border-light);
  border-left: 4px solid var(--brand-green);
  border-radius: 10px;
  cursor: pointer;
  padding: 14px;
}

.compat-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 10px 0;
}

.compat-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 8px 0;
}

.compat-badges span,
.skill-dependency {
  background: var(--bg-subtle);
  border: 1px solid var(--border-light);
  border-radius: 999px;
  color: var(--text-secondary);
  display: inline-flex;
  font-size: 11px;
  padding: 4px 8px;
}

.skill-ops-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  margin-bottom: 12px;
}

.skill-ops-card {
  background: var(--bg-subtle);
  border: 1px solid var(--border-light);
  border-radius: 10px;
  padding: 12px;
}

.skill-ops-card h3 {
  font-size: 13px;
  margin: 0 0 8px;
}

.skill-ops-card p,
.skill-run-row span {
  color: var(--text-secondary);
  font-size: 12px;
}

.skill-dependency {
  margin: 0 6px 6px 0;
}

.skill-dependency--bad {
  background: #fff1f2;
  border-color: #fecdd3;
  color: var(--brand-red-dark);
}

.skill-run-row {
  border-top: 1px solid var(--border-light);
  display: grid;
  gap: 3px;
  padding: 8px 0;
}

.skill-run-row:first-of-type {
  border-top: 0;
}

.compat-test-result {
  background: #eef7fb;
  border: 1px solid #bae6fd;
  border-radius: 10px;
  color: #0b6f96;
  margin: 10px 0;
  padding: 10px 12px;
}

.compat-import {
  display: grid;
  gap: 10px;
}

.compat-import input,
.compat-import textarea {
  border: 1px solid var(--border-light);
  border-radius: 8px;
  padding: 10px;
}

.compat-card:hover {
  box-shadow: var(--shadow-md);
}

.compat-card p {
  color: var(--text-secondary);
  margin: 6px 0;
}

.compat-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.compat-tags span {
  background: #eef2f8;
  border-radius: 999px;
  color: #344563;
  font-size: 11px;
  padding: 2px 8px;
}

.compat-card small {
  color: var(--text-muted);
  word-break: break-all;
}

.compat-markdown {
  background: #0f172a;
  border-radius: 10px;
  color: #dbeafe;
  max-height: 520px;
  overflow: auto;
  padding: 16px;
  white-space: pre-wrap;
}

.compat-config {
  display: grid;
  gap: 10px;
  margin-top: 14px;
}

.compat-config textarea {
  background: #ffffff;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  padding: 12px;
  resize: vertical;
}
</style>
