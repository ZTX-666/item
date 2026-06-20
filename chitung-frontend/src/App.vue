<script setup lang="ts">
import { provide, ref } from 'vue'
import HazardLedgerPage from './pages/HazardLedgerPage.vue'
import ShanshanDocPage from './pages/ShanshanDocPage.vue'
import YaoyaoStructuredInputPage from './pages/YaoyaoStructuredInputPage.vue'
import Sidebar from './components/layout/Sidebar.vue'
import TopBar from './components/layout/TopBar.vue'
import SmartFormPage from './pages/SmartFormPage.vue'
import VisualPatrolPage from './pages/VisualPatrolPage.vue'
import PendingConfirmationsPage from './pages/PendingConfirmationsPage.vue'
import WorkbenchPage from './pages/WorkbenchPage.vue'
import { confirmationsRefreshKey, navigateKey, type AppPage } from './composables/useAppNavigation'

const currentPage = ref<AppPage>('workbench')
const confirmationsRefreshTick = ref(0)

function handleNavigate(page: string) {
  if (
    page === 'workbench'
    || page === 'pending-confirmations'
    || page === 'hazard-ledger'
    || page === 'visual-patrol'
    || page === 'smart-form'
    || page === 'shanshan-doc'
    || page === 'yaoyao-structured-input'
  ) {
    currentPage.value = page
  }
}

provide(navigateKey, handleNavigate)
provide(confirmationsRefreshKey, confirmationsRefreshTick)
</script>

<template>
  <div class="app-shell">
    <TopBar />
    <div class="app-shell__body">
      <Sidebar :current-page="currentPage" @navigate="handleNavigate" />
      <WorkbenchPage v-if="currentPage === 'workbench'" />
      <PendingConfirmationsPage
        v-else-if="currentPage === 'pending-confirmations'"
        :refresh-tick="confirmationsRefreshTick"
      />
      <HazardLedgerPage v-else-if="currentPage === 'hazard-ledger'" />
      <VisualPatrolPage v-else-if="currentPage === 'visual-patrol'" />
      <SmartFormPage v-else-if="currentPage === 'smart-form'" />
      <ShanshanDocPage v-else-if="currentPage === 'shanshan-doc'" />
      <YaoyaoStructuredInputPage v-else-if="currentPage === 'yaoyao-structured-input'" />
    </div>
  </div>
</template>
