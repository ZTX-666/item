<script setup lang="ts">
import brandLogo from '../../assets/logos/brand.jpg'
import companyMark from '../../assets/logos/company-mark.png'
import { useLocale } from '../../composables/useLocale'
import { useTheme } from '../../composables/useTheme'

const { isTraditional, toggleLocale, display } = useLocale()
const { isDark, toggleTheme } = useTheme()
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
