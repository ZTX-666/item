<script setup lang="ts">
import { computed } from 'vue'
import type { CameraConfig } from '../../types/domain'

const props = defineProps<{
  cameras?: CameraConfig[] | null
  isPatrolling?: boolean
}>()

const emit = defineEmits<{
  patrol: [cameraId?: string]
  openEvidence: [cameraId: string]
}>()

const displayCameras = computed(() => {
  if (!props.cameras?.length) return []
  return props.cameras.map((camera) => ({
    id: camera.id,
    status: camera.enabled ? 'READY' : 'OFF',
    tone: camera.rtmp_url ? 'green' : 'orange',
    note: camera.rtmp_url ? `${camera.area} · RTMP 已配置` : `${camera.area} · 待填写 RTMP`,
  }))
})
</script>

<template>
  <section class="panel panel--tall">
    <div class="panel__header">
      <div>
        <h2>摄像头网格</h2>
        <p>RTMP 截图 + YOLO/VLM 检测入口</p>
      </div>
      <button
        class="primary-soft-button"
        :disabled="isPatrolling || !displayCameras.length"
        @click="emit('patrol')"
      >
        {{ isPatrolling ? '巡检中' : '立即巡检' }}
      </button>
    </div>

    <div v-if="!displayCameras.length" class="camera-empty">
      <p>尚未配置摄像头。请先确认 CCTV 网关或 C-SMART 通道缓存已配置。</p>
      <p class="camera-empty__hint">未配置时不会显示伪在线画面。</p>
    </div>
    <div v-else class="camera-grid">
      <article v-for="camera in displayCameras" :key="camera.id" class="camera-card">
        <div class="camera-card__screen">
          <span class="camera-card__scanline" />
          <span class="camera-card__risk-box" v-if="camera.tone === 'red'">NO HELMET</span>
        </div>
        <div class="camera-card__meta">
          <strong>{{ camera.id }}</strong>
          <span class="camera-status" :class="`camera-status--${camera.tone}`">{{ camera.status }}</span>
        </div>
        <p>{{ camera.note }}</p>
        <div class="camera-card__actions">
          <button class="mini-button camera-card__action" @click="emit('patrol', camera.id)">巡检此摄像头</button>
          <button class="mini-button camera-card__action" @click="emit('openEvidence', camera.id)">打开证据</button>
        </div>
      </article>
    </div>
  </section>
</template>

<style scoped>
.camera-empty {
  padding: 20px;
  color: var(--text-muted, #9aa4b2);
  border: 1px dashed rgba(255, 255, 255, 0.12);
  border-radius: 12px;
}

.camera-empty__hint {
  margin-top: 8px;
  font-size: 12px;
}

.camera-card__actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
</style>
