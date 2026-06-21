<script setup lang="ts">
export type ReviewCardAction = {
  id: string
  label: string
}

export type ReviewCard = {
  card_type?: string
  title: string
  summary: string
  actions?: ReviewCardAction[]
  data?: Record<string, unknown>
}

defineProps<{
  cards: ReviewCard[]
  busy?: boolean
}>()

const emit = defineEmits<{
  action: [actionId: string, card: ReviewCard]
}>()
</script>

<template>
  <section v-if="cards.length" class="panel review-cards">
    <div class="panel__header">
      <div>
        <h2>待处理卡片</h2>
        <p>点击动作后会创建待确认项或跳转相关页面</p>
      </div>
    </div>
    <article v-for="(card, index) in cards" :key="`${card.card_type || 'card'}-${index}`" class="review-card">
      <header>
        <h3>{{ card.title }}</h3>
        <p>{{ card.summary }}</p>
      </header>
      <div class="review-card__actions">
        <button
          v-for="action in card.actions || []"
          :key="action.id"
          class="primary-soft-button"
          :disabled="busy"
          @click="emit('action', action.id, card)"
        >
          {{ action.label }}
        </button>
      </div>
    </article>
  </section>
</template>

<style scoped>
.review-cards {
  margin-bottom: 12px;
}

.review-card {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  padding: 14px;
  margin-top: 10px;
  background: var(--bg-subtle);
}

.review-card h3 {
  color: var(--text-primary);
  font-size: 14px;
  margin: 0 0 6px;
}

.review-card p {
  margin: 0;
  color: var(--text-secondary);
}

.review-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}
</style>
