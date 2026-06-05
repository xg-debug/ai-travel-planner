<script setup lang="ts">
import { onLaunch, onShow } from '@dcloudio/uni-app'
import { useAuthStore } from '@/stores/authStore'
import { useThemeStore } from '@/stores/themeStore'

onLaunch(() => {
  useAuthStore().restore()
  useThemeStore().restore()
})

onShow(() => {
  useAuthStore().refreshProfileSilently()
  useThemeStore().restore()
})
</script>

<style lang="scss">
@use '@/styles/theme.scss';

page {
  min-height: 100%;
  background: var(--app-bg);
  color: var(--text-strong);
  font-family:
    -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC',
    'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
}

button {
  padding: 0;
  margin: 0;
  border: 0;
  background: transparent;
  line-height: 1.2;
}

button::after {
  border: 0;
}

input,
textarea {
  box-sizing: border-box;
}
</style>
