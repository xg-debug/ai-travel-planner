<script setup lang="ts">
import { onLaunch, onShow } from '@dcloudio/uni-app'
import { useAuthStore } from '@/stores/authStore'

onLaunch(() => {
  useAuthStore().restore()
})

onShow(() => {
  useAuthStore().refreshProfileSilently()
})
</script>

<style lang="scss">
@use '@/styles/theme.scss';

page {
  min-height: 100%;
  background: #f6f8fb;
  color: #142033;
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
