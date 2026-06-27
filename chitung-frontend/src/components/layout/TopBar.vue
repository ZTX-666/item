<script setup lang="ts">
import brandLogo from '../../assets/logos/brand.jpg'
import companyMark from '../../assets/logos/company-mark.png'
import { useLocale } from '../../composables/useLocale'
import { usePlatformConnection } from '../../composables/usePlatformConnection'
import { useTheme } from '../../composables/useTheme'

const { isTraditional, toggleLocale, display } = useLocale()
const { isDark, toggleTheme } = useTheme()
const { connected, reconnecting, lastError } = usePlatformConnection()

const connectionLabel = () => {
  if (connected.value) return display('中台已连接')
  if (reconnecting.value) return display('重连中…')
  return display('中台断开')
}
</script>

<template>
  <header class="topbar">
    <img class="topbar__logo" :src="brandLogo" alt="赤瞳" />
    <div class="topbar__brand">
      <strong>{{ display('赤瞳') }}</strong>
      <span>CSCEC Safety Intelligence</span>
    </div>
    <div class="topbar__center-mark">
      <img :src="companyMark" alt="公司标识" />
    </div>
    <div class="topbar__right">
      <span
        class="topbar-connection"
        :class="{
          'topbar-connection--ok': connected && !reconnecting,
          'topbar-connection--warn': reconnecting,
          'topbar-connection--bad': !connected && !reconnecting,
        }"
        :title="lastError || connectionLabel()"
      >
        <span class="topbar-connection__dot" />
        {{ connected && reconnecting ? display('中台繁忙') : connectionLabel() }}
      </span>
      <button class="topbar-action" type="button" @click="toggleLocale">
        {{ isTraditional ? '简' : '繁' }}
      </button>
      <button class="topbar-action" type="button" @click="toggleTheme">
        {{ isDark ? '☀' : '🌙' }}
      </button>
      <span class="desktop-pill">{{ display('开发者') }} Sean Xu</span>
    </div>
  </header>
</template>
