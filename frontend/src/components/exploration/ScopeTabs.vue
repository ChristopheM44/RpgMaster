<script setup lang="ts">
// Wrapper exploration : ré-utilise common/ScopeTabs avec le sizing « sm »
// du diptyque (44px de top bar).
import CommonScopeTabs from '../common/ScopeTabs.vue'
import { useSessionStore } from '../../stores/session'

const sessionStore = useSessionStore()
</script>

<template>
  <CommonScopeTabs
    v-model="sessionStore.mapScope"
    class="exploration-scope-tabs"
  />
</template>

<style scoped>
.exploration-scope-tabs :deep(.scope-tab) {
  padding: 4px 8px;
  font-size: 9px;
}
</style>
