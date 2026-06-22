import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

export type AppTheme = 'light' | 'dark'

const THEME_KEY = 'cybertravel_app_theme'
const TAB_BAR_PAGES = new Set([
  'pages/plan/index',
  'pages/trips/index',
  'pages/profile/index'
])

const isCurrentTabBarPage = () => {
  const pages = getCurrentPages()
  const current = pages[pages.length - 1] as any
  const route = String(current?.route || '').replace(/^\//, '')
  return TAB_BAR_PAGES.has(route)
}

export const useThemeStore = defineStore('theme', () => {
  const theme = ref<AppTheme>('light')

  const themeClass = computed(() => theme.value === 'dark' ? 'theme-dark' : 'theme-light')

  const applySystemChrome = () => {
    const dark = theme.value === 'dark'
    uni.setNavigationBarColor({
      frontColor: dark ? '#ffffff' : '#000000',
      backgroundColor: dark ? '#0f172a' : '#f6f7f9'
    })
    if (isCurrentTabBarPage()) {
      uni.setTabBarStyle({
        color: dark ? '#94a3b8' : '#7a8494',
        selectedColor: dark ? '#93c5fd' : '#2563eb',
        backgroundColor: dark ? '#111827' : '#ffffff',
        borderStyle: dark ? 'black' : 'white'
      })
    }
  }

  const restore = () => {
    const saved = uni.getStorageSync(THEME_KEY) as AppTheme | ''
    if (saved === 'dark' || saved === 'light') {
      theme.value = saved
    }
    applySystemChrome()
  }

  const setTheme = (nextTheme: AppTheme) => {
    theme.value = nextTheme
    uni.setStorageSync(THEME_KEY, nextTheme)
    applySystemChrome()
  }

  return {
    theme,
    themeClass,
    restore,
    setTheme
  }
})
