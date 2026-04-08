<script setup lang="ts">
import { computed } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import AppNav from './components/common/AppNav.vue'

const route = useRoute()
const showNav = computed(() => route.name !== 'home')
const isGameSession = computed(() => route.name === 'game-session')
</script>

<template>
  <div class="flex h-full flex-col bg-ink text-parchment">
    <AppNav v-if="showNav" />
    <main
      class="flex-1 min-h-0"
      :class="isGameSession ? 'overflow-hidden' : 'overflow-y-auto'"
    >
      <RouterView />
    </main>
  </div>
</template>
