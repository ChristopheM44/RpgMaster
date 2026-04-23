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
  }
  return out
})

function isActive(name: string): boolean {
  return route.name === name
}
</script>

<template>
  <header
    class="flex h-14 shrink-0 items-center gap-4 border-b px-6 backdrop-blur"
    :style="{
      background: 'linear-gradient(180deg, var(--color-bg-elev), transparent)',
      borderColor: 'var(--color-border)',
    }"
  >
    <!-- Logo -->
    <router-link to="/" class="flex items-center gap-2.5 shrink-0">
      <span
        class="flex h-8 w-8 items-center justify-center rounded-lg text-base font-bold"
        :style="{
          background: 'linear-gradient(135deg, var(--color-ember), var(--color-gold))',
          color: 'var(--color-bg)',
          boxShadow: '0 0 18px rgba(255,130,71,0.3)',
        }"
      >⚔</span>
      <span class="font-display text-[15px] font-bold tracking-[0.1em]">RPGMASTER</span>
    </router-link>

    <!-- Crumbs -->
    <span class="text-sm" :style="{ color: 'var(--color-text-dim)' }">/</span>
    <nav class="flex items-center gap-2 text-xs">
      <template v-for="(c, i) in crumbs" :key="i">
        <span
          v-if="i > 0"
          :style="{ color: 'var(--color-text-dim)' }"
        >›</span>
        <span
          :class="['tracking-wide', i === crumbs.length - 1 ? 'font-semibold' : '']"
          :style="{
            color: i === crumbs.length - 1 ? 'var(--color-gold)' : 'var(--color-text-muted)',
          }"
        >{{ c }}</span>
      </template>
    </nav>

    <div class="flex-1" />

    <!-- Nav pills -->
    <nav class="flex items-center gap-1.5">
      <router-link
        to="/lobby"
        class="rounded-full border px-3.5 py-1.5 text-xs font-semibold tracking-wide transition"
        :class="isActive('lobby')
          ? 'text-[color:var(--color-gold)] border-[rgba(240,199,100,0.30)] bg-[rgba(240,199,100,0.10)]'
          : 'text-[color:var(--color-text-muted)] border-transparent hover:text-[color:var(--color-parchment)]'"
      >Lobby</router-link>

      <router-link
        to="/campaigns"
        class="rounded-full border px-3.5 py-1.5 text-xs font-semibold tracking-wide transition"
        :class="isActive('campaigns')
          ? 'text-[color:var(--color-gold)] border-[rgba(240,199,100,0.30)] bg-[rgba(240,199,100,0.10)]'
          : 'text-[color:var(--color-text-muted)] border-transparent hover:text-[color:var(--color-parchment)]'"
      >Campagnes</router-link>

      <router-link
        to="/admin"
        class="rounded-full border px-3.5 py-1.5 text-xs font-semibold tracking-wide transition"
        :class="isActive('admin')
          ? 'text-[color:var(--color-gold)] border-[rgba(240,199,100,0.30)] bg-[rgba(240,199,100,0.10)]'
          : 'text-[color:var(--color-text-muted)] border-transparent hover:text-[color:var(--color-parchment)]'"
      >Admin</router-link>
    </nav>

    <div
      class="h-5 w-px"
      :style="{ background: 'var(--color-border)' }"
    />

    <!-- Current session chip (visible sauf en session) -->
    <div
      v-if="sessionStore.currentSession && route.name !== 'game-session'"
      class="flex items-center gap-2 rounded-full border px-3 py-1 text-xs"
      :style="{
        background: 'var(--color-surface)',
        borderColor: 'var(--color-border)',
        color: 'var(--color-text-muted)',
      }"
    >
      <span class="tracking-[0.1em] text-[10px]">SESSION</span>
      <span
        class="font-semibold font-display"
        :style="{ color: 'var(--color-gold)' }"
      >{{ sessionStore.currentSession.name }}</span>
    </div>

    <!-- Connection indicator (signal vert simple, stylé) -->
    <div class="flex items-center gap-1.5 text-[10px] tracking-[0.15em]" :style="{ color: 'var(--color-text-muted)' }">
      <span
        class="h-2 w-2 rounded-full"
        :style="{
          background: 'var(--color-green)',
          boxShadow: '0 0 8px var(--color-green)',
        }"
      />
      EN LIGNE
    </div>

    <!-- Back-to-lobby button (hors lobby) -->
    <button
      v-if="route.name !== 'lobby'"
      class="rounded-md border px-3 py-1 text-xs font-semibold tracking-wide transition"
      :style="{
        borderColor: 'var(--color-border-strong)',
        color: 'var(--color-text-muted)',
      }"
      @click="router.push('/lobby')"
    >
      ← Lobby
    </button>
  </header>
</template>
