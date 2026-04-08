<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useSessionStore } from '../../stores/session'

const router = useRouter()
const sessionStore = useSessionStore()
</script>

<template>
  <header class="w-full border-b border-stone bg-ink-light px-6 py-3 shrink-0">
    <nav class="mx-auto flex max-w-7xl items-center justify-between">
      <router-link
        to="/"
        class="font-display text-xl font-bold text-gold transition hover:text-gold-light"
      >
        ⚔ RpgMaster
      </router-link>

      <div class="flex items-center gap-6 text-sm text-parchment-dark">
        <span v-if="sessionStore.currentSession" class="text-parchment">
          Session :
          <span class="font-semibold text-gold">{{ sessionStore.currentSession.name }}</span>
        </span>

        <router-link
          to="/lobby"
          class="transition hover:text-parchment"
          active-class="text-parchment"
        >
          Lobby
        </router-link>

        <router-link
          to="/admin"
          class="transition hover:text-parchment"
          active-class="text-parchment"
        >
          Admin
        </router-link>

        <button
          v-if="router.currentRoute.value.name !== 'lobby'"
          class="rounded border border-stone px-3 py-1 transition hover:border-gold hover:text-gold"
          @click="router.push('/lobby')"
        >
          Retour au lobby
        </button>
      </div>
    </nav>
  </header>
</template>
