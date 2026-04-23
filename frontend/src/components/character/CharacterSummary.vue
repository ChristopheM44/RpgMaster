<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useCharacterStore } from '../../stores/character'
import type { Character } from '../../types'

const charStore = useCharacterStore()
const router = useRouter()
const route = useRoute()

const sessionId = computed(() => route.params.id as string | undefined)

function openSheet(c: Character) {
  router.push({
    name: 'character-sheet',
    params: { charId: c.id },
    query: sessionId.value ? { session: sessionId.value } : {},
  })
}

const ABILITY_ABBR: Record<string, string> = {
  str: 'FOR', dex: 'DEX', con: 'CON', int: 'INT', wis: 'SAG', cha: 'CHA',
}

function fmtMod(score: number) {
  const m = Math.floor((score - 10) / 2)
  return m >= 0 ? `+${m}` : `${m}`
}

function hpPercent(c: Character) {
  return Math.max(0, (c.hp_current / c.hp_max) * 100)
}

function hpColor(c: Character) {
  const pct = hpPercent(c)
  return pct > 50 ? 'bg-green-600' : pct > 25 ? 'bg-yellow-500' : 'bg-blood'
}

const isMyChar = (c: Character) => c.id === charStore.myCharacter?.id

const selected = computed(
  () => charStore.selectedCharacter ?? charStore.myCharacter,
)
const selectedMods = computed(() => {
  if (!selected.value) return {} as Record<string, number>
  return Object.fromEntries(
    Object.entries(selected.value.ability_scores).map(([k, v]) => [k, Math.floor((v - 10) / 2)]),
  )
})
</script>

<template>
  <div class="flex flex-1 min-h-0 flex-col">
    <div class="border-b border-gold/20 px-4 py-2">
      <h2 class="rpg-eyebrow">Personnages</h2>
    </div>

    <div v-if="charStore.sessionCharacters.length === 0" class="flex-1 flex items-center justify-center">
      <p class="text-parchment/30 italic text-sm">Aucun personnage</p>
    </div>

    <div v-else class="flex flex-1 overflow-hidden">
      <!-- Left: character list -->
      <div class="w-[45%] border-r border-gold/20 overflow-y-auto py-2 space-y-1 px-2 shrink-0">
        <button
          v-for="c in charStore.sessionCharacters"
          :key="c.id"
          class="rpg-card w-full px-2 py-1.5 text-left cursor-pointer transition-colors"
          :class="selected?.id === c.id
            ? 'border-ember/50 bg-surface-raised'
            : 'hover:bg-surface-raised'"
          @click="charStore.setSelectedCharacter(c)"
        >
          <div class="flex items-center gap-1.5">
            <span class="flex-1 truncate text-sm font-semibold"
              :class="isMyChar(c) ? 'text-gold' : 'text-parchment'">
              {{ c.name }}
            </span>
            <span v-if="c.is_ai" class="text-xs text-parchment/40">IA</span>
          </div>
          <div class="mt-1 flex items-center gap-1.5">
            <div class="relative flex-1 h-1.5 rounded-full bg-ink overflow-hidden">
              <div
                class="absolute inset-y-0 left-0 rounded-full"
                :class="hpColor(c)"
                :style="{ width: `${hpPercent(c)}%` }"
              />
            </div>
            <span class="text-xs font-mono text-parchment/50">{{ c.hp_current }}/{{ c.hp_max }}</span>
          </div>
        </button>
      </div>

      <!-- Right: detail panel -->
      <div v-if="selected" class="flex-1 overflow-y-auto px-3 py-2 space-y-3">
        <div>
          <p class="font-bold text-parchment">{{ selected.name }}</p>
          <p class="text-xs text-parchment/50">
            Niv. {{ selected.level }} {{ selected.char_class }} · {{ selected.species }}
          </p>
        </div>

        <!-- Lien fiche complète -->
        <button
          class="rpg-btn-secondary w-full justify-center"
          @click="openSheet(selected)"
        >
          Fiche complète →
        </button>

        <!-- Contrôle IA -->
        <button
          class="rpg-btn-tonal w-full text-left px-3 py-2"
          :class="selected.is_ai ? 'tone-arcane' : 'tone-gold'"
          @click="charStore.toggleAiControl(selected.id)"
        >
          <span class="font-semibold">{{ selected.is_ai ? '🤖 Géré par l\'IA' : '👤 Joueur humain' }}</span>
          <span class="ml-2 opacity-60">— {{ selected.is_ai ? 'cliquer pour reprendre le contrôle' : 'cliquer pour confier à l\'IA' }}</span>
        </button>

        <!-- HP -->
        <div>
          <div class="flex justify-between text-xs mb-1">
            <span class="text-parchment/60">PV</span>
            <span class="font-mono text-parchment">
              {{ selected.hp_current }}<span class="text-parchment/40">/{{ selected.hp_max }}</span>
              <span v-if="selected.hp_temp > 0" class="text-arcane ml-1">+{{ selected.hp_temp }}</span>
            </span>
          </div>
          <div class="h-2 rounded-full bg-ink overflow-hidden">
            <div
              class="h-full rounded-full transition-all duration-300"
              :class="hpColor(selected)"
              :style="{ width: `${hpPercent(selected)}%` }"
            />
          </div>
        </div>

        <!-- Ability scores -->
        <div class="grid grid-cols-3 gap-1">
          <div
            v-for="(abbr, key) in ABILITY_ABBR"
            :key="key"
            class="rpg-card flex flex-col items-center py-1"
          >
            <span class="text-xs text-parchment/50 font-semibold">{{ abbr }}</span>
            <span class="text-sm font-bold text-parchment">{{ selected.ability_scores[key] ?? '—' }}</span>
            <span class="text-xs text-gold/70">{{ fmtMod(selected.ability_scores[key] ?? 10) }}</span>
          </div>
        </div>

        <!-- Conditions -->
        <div v-if="selected.conditions?.length" class="flex flex-wrap gap-1">
          <span
            v-for="cond in selected.conditions"
            :key="cond"
            class="rpg-chip text-blood border-blood/40"
          >{{ cond }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
