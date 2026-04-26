<script setup lang="ts">
import { computed } from 'vue'
import { useGameStore } from '../../stores/game'
import type { TimeOfDay } from '../../types'

const gameStore = useGameStore()
const journal = computed(() => gameStore.adventureJournal)

const TIME_GLYPH: Record<TimeOfDay, string> = {
  dawn: '☀',
  morning: '☀',
  noon: '☀',
  afternoon: '☼',
  dusk: '☾',
  night: '☽',
}

const TIME_LABEL: Record<TimeOfDay, string> = {
  dawn: 'Aube',
  morning: 'Matin',
  noon: 'Midi',
  afternoon: 'Après-midi',
  dusk: 'Crépuscule',
  night: 'Nuit',
}

const locationText = computed(() => {
  if (!journal.value) return null
  const parts = [journal.value.location_region, journal.value.location_place].filter(Boolean)
  return parts.length ? parts.join(' · ') : null
})
</script>

<template>
  <div class="px-5 py-4">
    <div class="mb-3 text-[10px] font-bold uppercase tracking-[0.18em]" style="color: var(--color-gold)">
      ✦ Carnet d'aventure
    </div>

    <div v-if="!journal || (!locationText && !journal.calendar_date)" class="text-[12px] italic" style="color: var(--color-text-muted)">
      Lieu inconnu…
    </div>

    <template v-else>
      <div class="font-display text-[14px] font-semibold leading-snug" style="color: var(--color-parchment)">
        {{ locationText ?? 'Lieu inconnu' }}
      </div>
      <div class="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px]" style="color: var(--color-text-muted)">
        <span>{{ TIME_GLYPH[journal.time_of_day] }} {{ TIME_LABEL[journal.time_of_day] }}</span>
        <span class="opacity-40">·</span>
        <span>Jour {{ journal.day_number }}</span>
        <template v-if="journal.calendar_date">
          <span class="opacity-40">—</span>
          <span>{{ journal.calendar_date }}</span>
        </template>
        <template v-if="journal.weather">
          <span class="opacity-40">·</span>
          <span>{{ journal.weather }}</span>
        </template>
      </div>
    </template>
  </div>
</template>
