<template>
  <footer class="site-footer">
    <div class="site-footer__inner">
      <div>
        <strong>随心游</strong>
        <span>让真实地图、天气和偏好共同决定每一天。</span>
      </div>
      <span>© 2026 AI Travel Planner</span>
    </div>
  </footer>
</template>

<style scoped>
.site-footer { border-top: 1px solid #e5e9ef; background: #fff; }
.site-footer__inner {
  width: min(1180px, calc(100% - 40px));
  min-height: 104px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  margin: 0 auto;
  color: #8a94a3;
  font-size: 12px;
}
.site-footer__inner strong,
.site-footer__inner span { display: block; }
.site-footer__inner strong { margin-bottom: 5px; color: #111827; font-size: 15px; }
@media (max-width: 640px) {
  .site-footer { padding-bottom: 78px; }
  .site-footer__inner { align-items: flex-start; flex-direction: column; justify-content: center; }
}
</style>
