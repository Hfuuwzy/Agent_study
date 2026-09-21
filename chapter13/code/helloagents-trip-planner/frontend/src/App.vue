<template>
  <div id="app">
    <a-layout style="min-height: 100vh">
      <a-layout-header class="app-header">
        <div class="app-title">
          🌍 HelloAgents智能旅行助手
        </div>
      </a-layout-header>
      <a-layout-content style="padding: 24px">
        <router-view />
      </a-layout-content>
      <a-layout-footer style="text-align: center">
        HelloAgents智能旅行助手 ©2025 基于HelloAgents框架
      </a-layout-footer>
    </a-layout>
  </div>
</template>

<script setup lang="ts">
</script>

<style>
#app {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial,
    'Noto Sans', sans-serif;
}

/* Shared header brand: must stay fully legible inside the dark header at every width.
   Geometry moved out of inline styles so mobile can reflow it responsively. */
#app .app-header {
  background: #001529;
  padding: 0 50px;
  min-height: 64px;
  height: auto;
  display: flex;
  align-items: center;
}

#app .app-title {
  color: white;
  font-size: 24px;
  font-weight: bold;
  line-height: 1.4;
  white-space: nowrap;
}

@media (max-width: 480px) {
  #app .app-header {
    padding: 0 16px;
  }

  #app .app-title {
    font-size: 18px;
    white-space: normal;
  }
}
</style>

