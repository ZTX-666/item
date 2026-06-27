<script setup lang="ts">
import { onBeforeUnmount, onMounted, provide, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ActivityBar from './components/layout/ActivityBar.vue'
import ChatbotPanel from './components/layout/ChatbotPanel.vue'
import NavigationProgress from './components/common/NavigationProgress.vue'
import PageLoadingShell from './components/common/PageLoadingShell.vue'
import ToastHost from './components/common/ToastHost.vue'
import PanelSidebar from './components/layout/PanelSidebar.vue'
import TopBar from './components/layout/TopBar.vue'
import { useNavigationProgress } from './composables/useNavigationProgress'
import { usePlatformConnection } from './composables/usePlatformConnection'
import { confirmationsRefreshKey, navigateKey, openChatbotKey, type AppPage } from './composables/useAppNavigation'

const route = useRoute()
const router = useRouter()
const { navigating, progress } = useNavigationProgress(router)
const { startPlatformConnectionMonitor, stopPlatformConnectionMonitor } = usePlatformConnection()

function deducePanel(path: string): string {
  if (path.startsWith('/guardian')) return 'guardian'
  if (path.startsWith('/docmate')) return 'docmate'
  if (path.startsWith('/lingxun')) return 'lingxun'
  if (path.startsWith('/center')) return 'center'
  if (path.startsWith('/automation')) return 'center'
  if (path.startsWith('/yaoyao')) return 'yaoyao'
  return 'guardian'
}

const activePanel = ref(deducePanel(route.path))
const chatbotVisible = ref(false)
const confirmationsRefreshTick = ref(0)

const firstPaths: Record<string, string> = {
  guardian: '/guardian/dashboard',
  docmate: '/docmate/documents',
  lingxun: '/lingxun/whatsapp',
  center: '/center/settings',
  yaoyao: '/yaoyao/structured',
}

watch(
  () => route.path,
  (path) => {
    activePanel.value = deducePanel(path)
  },
)

function handlePanelSelect(panel: string) {
  if (panel === 'chatbot') {
    chatbotVisible.value = !chatbotVisible.value
    return
  }
  activePanel.value = panel
  router.push(firstPaths[panel] || firstPaths.guardian)
}

function handleLegacyNavigate(page: AppPage) {
  const routes: Record<AppPage, string> = {
    workbench: '/guardian/dashboard',
    'pending-confirmations': '/guardian/confirmations',
    'hazard-ledger': '/guardian/hazards',
    'visual-patrol': '/guardian/patrol',
    'smart-form': '/docmate/forms',
    'shanshan-doc': '/docmate/documents',
    'yaoyao-structured-input': '/yaoyao/structured',
    'external-risk': '/yaoyao/feed',
  }
  router.push(routes[page] || firstPaths.guardian)
}

provide(navigateKey, handleLegacyNavigate)
provide(confirmationsRefreshKey, confirmationsRefreshTick)
provide(openChatbotKey, () => {
  chatbotVisible.value = true
})

onMounted(() => {
  startPlatformConnectionMonitor(5000)
})

onBeforeUnmount(() => {
  stopPlatformConnectionMonitor()
})
</script>

<template>
  <div class="app-shell">
    <TopBar />
    <NavigationProgress :active="navigating" :progress="progress" />
    <div class="app-shell__body">
      <ActivityBar :active-panel="activePanel" @select="handlePanelSelect" />
      <PanelSidebar :active-panel="activePanel" />
      <main class="app-content">
        <router-view v-slot="{ Component, route: viewRoute }">
          <Transition name="page-fade" mode="out-in">
            <div :key="viewRoute.fullPath" class="page-route-shell">
              <Suspense>
                <component :is="Component" />
                <template #fallback>
                  <PageLoadingShell />
                </template>
              </Suspense>
            </div>
          </Transition>
        </router-view>
      </main>
      <ChatbotPanel :visible="chatbotVisible" @toggle="chatbotVisible = !chatbotVisible" />
    </div>
    <ToastHost />
  </div>
</template>
