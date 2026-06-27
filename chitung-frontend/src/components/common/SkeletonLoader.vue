<script setup lang="ts">
/**
 * SkeletonLoader — 骨架屏加载组件
 * 用灰色条替代纯文本"Loading..."
 * 支持多种模式：段落、卡片、行
 */

const props = withDefaults(defineProps<{
  /** 骨架类型 */
  type?: 'paragraphs' | 'cards' | 'rows' | 'report'
  /** 行数/卡片数 */
  count?: number
}>(), {
  type: 'paragraphs',
  count: 4,
})

function rowWidths(index: number): string {
  const patterns = ['100%', '85%', '92%', '70%', '88%', '60%']
  return patterns[index % patterns.length]
}
</script>

<template>
  <div class="skeleton-loader" :class="`skeleton-loader--${props.type}`">
    <!-- 段落骨架 -->
    <template v-if="props.type === 'paragraphs'">
      <div v-for="i in props.count" :key="i" class="skeleton-paragraph">
        <div class="skeleton-bar skeleton-bar--index"></div>
        <div class="skeleton-paragraph__lines">
          <div class="skeleton-bar" :style="{ width: rowWidths(i * 2) }"></div>
          <div class="skeleton-bar" :style="{ width: rowWidths(i * 2 + 1) }"></div>
        </div>
      </div>
    </template>

    <!-- 卡片骨架 -->
    <template v-else-if="props.type === 'cards'">
      <div v-for="i in props.count" :key="i" class="skeleton-card">
        <div class="skeleton-bar skeleton-bar--title" :style="{ width: rowWidths(i) }"></div>
        <div class="skeleton-bar skeleton-bar--text"></div>
        <div class="skeleton-bar skeleton-bar--text" :style="{ width: '70%' }"></div>
        <div class="skeleton-card__footer">
          <div class="skeleton-bar skeleton-bar--badge"></div>
          <div class="skeleton-bar skeleton-bar--btn"></div>
        </div>
      </div>
    </template>

    <!-- 行骨架 -->
    <template v-else-if="props.type === 'rows'">
      <div v-for="i in props.count" :key="i" class="skeleton-row">
        <div class="skeleton-bar skeleton-bar--label"></div>
        <div class="skeleton-bar skeleton-bar--field"></div>
        <div class="skeleton-bar skeleton-bar--tag"></div>
      </div>
    </template>

    <!-- 报告卡片骨架 -->
    <template v-else-if="props.type === 'report'">
      <div v-for="i in props.count" :key="i" class="skeleton-report">
        <div class="skeleton-report__head">
          <div class="skeleton-bar skeleton-bar--title" :style="{ width: '50%' }"></div>
          <div class="skeleton-bar skeleton-bar--badge"></div>
        </div>
        <div class="skeleton-bar skeleton-bar--text"></div>
        <div class="skeleton-bar skeleton-bar--text" :style="{ width: '80%' }"></div>
        <div class="skeleton-report__foot">
          <div class="skeleton-bar skeleton-bar--btn"></div>
          <div class="skeleton-bar skeleton-bar--btn"></div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.skeleton-loader {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.skeleton-bar {
  animation: skeleton-pulse 1.4s ease-in-out infinite;
  background: linear-gradient(90deg, var(--bg-subtle, #f0f2f5) 25%, var(--bg-active, #e4e8ee) 50%, var(--bg-subtle, #f0f2f5) 75%);
  background-size: 200% 100%;
  border-radius: var(--radius-sm, 4px);
  height: 12px;
}

@keyframes skeleton-pulse {
  0% {
    background-position: 200% 0;
  }

  100% {
    background-position: -200% 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .skeleton-bar {
    animation: none;
    background: var(--bg-subtle);
  }
}

/* 段落骨架 */
.skeleton-paragraph {
  display: flex;
  gap: 10px;
  padding: 6px 4px;
}

.skeleton-bar--index {
  flex-shrink: 0;
  height: 12px;
  width: 22px;
}

.skeleton-paragraph__lines {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 6px;
}

/* 卡片骨架 */
.skeleton-card {
  background: var(--bg-white, #fff);
  border: 1px solid var(--border-light, #e8eaef);
  border-radius: var(--radius-md, 8px);
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px;
}

.skeleton-bar--title {
  height: 14px;
  width: 60%;
}

.skeleton-bar--text {
  height: 11px;
  width: 100%;
}

.skeleton-card__footer {
  align-items: center;
  display: flex;
  gap: 8px;
  justify-content: space-between;
  margin-top: 4px;
}

.skeleton-bar--badge {
  height: 16px;
  width: 50px;
}

.skeleton-bar--btn {
  height: 28px;
  width: 70px;
}

/* 行骨架 */
.skeleton-row {
  align-items: center;
  display: grid;
  gap: 10px;
  grid-template-columns: 120px 1fr 50px;
}

.skeleton-bar--label {
  height: 12px;
  width: 100%;
}

.skeleton-bar--field {
  height: 32px;
  width: 100%;
}

.skeleton-bar--tag {
  height: 12px;
  width: 100%;
}

/* 报告骨架 */
.skeleton-report {
  background: var(--bg-white, #fff);
  border: 1px solid var(--border-light, #e8eaef);
  border-radius: var(--radius-lg, 12px);
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px;
}

.skeleton-report__head {
  align-items: center;
  display: flex;
  justify-content: space-between;
}

.skeleton-report__foot {
  display: flex;
  gap: 8px;
  margin-top: 6px;
}
</style>
