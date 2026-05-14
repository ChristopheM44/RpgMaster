<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSessionStore } from '../../stores/session'

const router = useRouter()
const route = useRoute()
const sessionStore = useSessionStore()

/** Fil d'Ariane : Lobby › Session › (Personnage) */
const crumbs = computed<string[]>(() => {
  const out: string[] = ['Lobby']
  if (sessionStore.currentSession && route.name !== 'lobby') {
    out.push(sessionStore.currentSession.name)
  }
  if (route.name === 'character-sheet') {
    out.push('Fiche')
  } else if (route.name === 'character-setup') {
    out.push('Création')
  } else if (route.name === 'campaigns') {
    out[out.length - 1] = 'Campagnes'
  } else if (route.name === 'admin') {
    out[out.length - 1] = 'Admin'
  } else if (route.name === 'grimoire') {
    out[out.length - 1] = 'Grimoire'
  } else if (route.name === 'bestiaire') {
    out[out.length - 1] = 'Bestiaire'
  }
  return out
})

function isActive(name: string): boolean {
  return route.name === name
}
</script>

<template>
  <header
    class="rpg-shell-header flex h-14 shrink-0 items-center gap-4 border-b px-6 backdrop-blur"
  >
    <!-- Logo -->
    <router-link to="/" class="flex items-center gap-2.5 shrink-0">
      <span
        class="rpg-brand-mark flex h-8 w-8 items-center justify-center rounded-lg text-base font-bold"
      >⚔</span>
      <span class="font-display text-[15px] font-bold tracking-[0.1em]">RPGMASTER</span>
    </router-link>

    <!-- Crumbs -->
    <span class="rpg-text-dim text-sm">/</span>
    <nav class="flex items-center gap-2 text-xs">
      <template v-for="(c, i) in crumbs" :key="i">
        <span
          v-if="i > 0"
          class="rpg-text-dim"
        >›</span>
        <span
          :class="[
            'tracking-wide',
            i === crumbs.length - 1 ? 'rpg-text-gold font-semibold' : 'rpg-text-muted',
          ]"
        >{{ c }}</span>
      </template>
    </nav>

    <div class="flex-1" />

    <!-- Nav pills -->
    <nav class="flex items-center gap-1.5">
      <router-link
        to="/lobby"
        class="rpg-nav-pill rounded-full border px-3.5 py-1.5 text-xs font-semibold tracking-wide transition"
        :class="{ 'is-active': isActive('lobby') }"
      >Lobby</router-link>

      <router-link
        to="/campaigns"
        class="rpg-nav-pill rounded-full border px-3.5 py-1.5 text-xs font-semibold tracking-wide transition"
        :class="{ 'is-active': isActive('campaigns') }"
      >Campagnes</router-link>

      <router-link
        to="/grimoire"
        class="rpg-nav-pill rounded-full border px-3.5 py-1.5 text-xs font-semibold tracking-wide transition"
        :class="{ 'is-active': isActive('grimoire') }"
      >✦ Grimoire</router-link>

      <router-link
        to="/bestiaire"
        class="rpg-nav-pill rounded-full border px-3.5 py-1.5 text-xs font-semibold tracking-wide transition"
        :class="{ 'is-active': isActive('bestiaire') }"
      >◆ Bestiaire</router-link>

      <router-link
        to="/admin"
        class="rpg-nav-pill rounded-full border px-3.5 py-1.5 text-xs font-semibold tracking-wide transition"
        :class="{ 'is-active': isActive('admin') }"
      >Admin</router-link>
    </nav>

    <div class="rpg-divider-vertical h-5 w-px" />

    <!-- Current session chip (visible sauf en session) -->
    <div
      v-if="sessionStore.currentSession && route.name !== 'game-session'"
      class="rpg-session-chip flex items-center gap-2 rounded-full border px-3 py-1 text-xs"
    >
      <span class="tracking-[0.1em] text-[10px]">SESSION</span>
      <span class="rpg-text-gold font-semibold font-display">{{ sessionStore.currentSession.name }}</span>
    </div>

    <!-- Connection indicator (signal vert simple, stylé) -->
    <div class="rpg-text-muted flex items-center gap-1.5 text-[10px] tracking-[0.15em]">
      <span class="rpg-online-dot h-2 w-2 rounded-full" />
      EN LIGNE
    </div>

    <!-- Back-to-lobby button (hors lobby) -->
    <button
      v-if="route.name !== 'lobby'"
      class="rpg-border-strong rpg-text-muted rounded-md border px-3 py-1 text-xs font-semibold tracking-wide transition"
      @click="router.push('/lobby')"
    >
      ← Lobby
    </button>
  </header>
</template>
