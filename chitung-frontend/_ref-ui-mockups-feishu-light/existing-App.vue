<script setup lang="ts">
import { ref } from 'vue'
import AIAssistantPage from './pages/AIAssistantPage.vue'
import Sidebar from './components/layout/Sidebar.vue'
import TopBar from './components/layout/TopBar.vue'
import WhatsAppOpsPage from './pages/WhatsAppOpsPage.vue'
import WorkbenchPage from './pages/WorkbenchPage.vue'

const currentPage = ref<'workbench' | 'assistant' | 'whatsapp'>('workbench')

function handleNavigate(page: string) {
  if (page === 'workbench' || page === 'assistant' || page === 'whatsapp') {
    currentPage.value = page
  }
}
</script>

<template>
  <div class="app-shell">
    <TopBar />
    <div class="app-shell__body">
      <Sidebar :current-page="currentPage" @navigate="handleNavigate" />
      <WorkbenchPage v-if="currentPage === 'workbench'" />
      <AIAssistantPage v-else-if="currentPage === 'assistant'" />
      <WhatsAppOpsPage v-else />
    </div>
  </div>
</template>
