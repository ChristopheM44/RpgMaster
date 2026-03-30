<script setup lang="ts">
import { RouterView, useRoute } from 'vue-router'
import AppNav from './components/common/AppNav.vue'

const route = useRoute()
</script>

<template>
  <div class="min-h-screen bg-ink text-parchment">
    <AppNav v-if="route.name !== 'home'" />
    <main :class="{ 'pt-14': route.name !== 'home' }">
      <RouterView />
    </main>
  </div>
</template>
