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
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  padding: 14px;
  margin-top: 10px;
  background: rgba(255, 255, 255, 0.02);
}

.review-card h3 {
  margin: 0 0 6px;
}

.review-card p {
  margin: 0;
  color: var(--text-muted, #9aa4b2);
}

.review-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}
</style>
