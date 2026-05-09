<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useCharacterStore } from '../../stores/character'
import type { Character } from '../../types'

const emit = defineEmits<{
  (e: 'toggle-ai', characterId: string, nextIsAi: boolean): void
}>()

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

function hpPct(c: Character): number {
  return Math.max(0, c.hp_max > 0 ? (c.hp_current / c.hp_max) * 100 : 0)
}

function hpColor(c: Character): string {
  const pct = hpPct(c)
  return pct > 50 ? 'var(--color-green)' : pct > 25 ? 'var(--color-gold)' : 'var(--color-blood)'
}

const isMyChar = (c: Character) => c.id === charStore.myCharacter?.id

const selected = computed(
  () => charStore.selectedCharacter ?? charStore.myCharacter,
)
</script>

<template>
  <div class="flex flex-1 min-h-0 flex-col">

    <!-- Section header -->
    <div
      class="rpg-border flex shrink-0 items-center border-b px-4 py-2.5"
    >
      <span class="rpg-eyebrow">✦ Personnages</span>
    </div>

    <!-- Empty state -->
    <div
      v-if="charStore.sessionCharacters.length === 0"
      class="flex flex-1 items-center justify-center"
    >
      <p class="rpg-text-muted font-serif italic text-sm">Aucun personnage</p>
    </div>

    <div v-else class="flex flex-1 min-h-0 overflow-hidden">

      <!-- Left: character list (MiniCharRow style) -->
      <div
        class="rpg-border w-[45%] shrink-0 overflow-y-auto border-r py-2 space-y-1.5 px-2"
      >
        <button
          v-for="c in charStore.sessionCharacters"
          :key="c.id"
          class="rpg-character-list-button w-full rounded-lg border px-2.5 py-2 text-left transition-all"
          :class="{ 'is-selected': selected?.id === c.id }"
          @click="charStore.setSelectedCharacter(c)"
        >
          <div class="flex items-center gap-2">
            <!-- Avatar -->
            <div
              class="flex h-7 w-7 shrink-0 items-center justify-center rounded-md font-display text-[13px] font-bold"
              :class="c.is_ai ? 'rpg-avatar-ai' : 'rpg-avatar-player'"
            >{{ c.name.charAt(0).toUpperCase() }}</div>

            <!-- Name + AI badge -->
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-1.5">
                <span
                  class="truncate font-display text-xs font-semibold"
                  :class="isMyChar(c) ? 'rpg-text-gold' : 'rpg-text-main'"
                >{{ c.name }}</span>
                <span
                  v-if="c.is_ai"
                  class="rpg-text-arcane shrink-0 text-[8px] font-bold tracking-[0.1em]"
                >IA</span>
              </div>
              <div class="rpg-text-muted text-[10px]">
                Niv. {{ c.level }} · {{ c.char_class }}
              </div>
            </div>
          </div>

          <!-- HP mini-bar -->
          <div class="mt-1.5">
            <div
              class="rpg-hp-track mini relative w-full overflow-hidden rounded-full"
            >
              <div
                class="absolute inset-y-0 left-0 rounded-full transition-all duration-300"
                :style="{ width: `${hpPct(c)}%`, background: hpColor(c) }"
              />
            </div>
          </div>
        </button>
      </div>

      <!-- Right: detail panel -->
      <div v-if="selected" class="flex-1 overflow-y-auto px-3 py-3 space-y-3">

        <!-- Name + subtitle -->
        <div>
          <p class="rpg-text-main font-display text-sm font-bold">{{ selected.name }}</p>
          <p class="rpg-text-muted text-[11px]">
            Niv. {{ selected.level }} {{ selected.char_class }} · {{ selected.species }}
          </p>
        </div>

        <!-- Fiche complète -->
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
          @click="emit('toggle-ai', selected.id, !selected.is_ai)"
        >
          <span class="font-semibold">{{ selected.is_ai ? '🤖 Géré par l\'IA' : '👤 Joueur humain' }}</span>
          <span class="ml-2 opacity-60 text-xs">— {{ selected.is_ai ? 'reprendre le contrôle' : 'confier à l\'IA' }}</span>
        </button>

        <!-- HP bar (D3 style) -->
        <div>
          <div class="mb-1.5 flex justify-between text-xs">
            <span class="rpg-text-muted">Points de vie</span>
            <span class="rpg-text-main font-mono font-semibold">
              {{ selected.hp_current }}<span class="rpg-text-dim">/{{ selected.hp_max }}</span>
              <span v-if="selected.hp_temp > 0" class="rpg-text-arcane ml-1">+{{ selected.hp_temp }}</span>
            </span>
          </div>
          <div
            class="rpg-hp-track relative w-full overflow-hidden rounded-full"
          >
            <div
              class="absolute inset-y-0 left-0 rounded-full transition-all duration-300"
              :style="{
                width: `${hpPct(selected)}%`,
                background: hpColor(selected),
                boxShadow: `0 0 8px ${hpColor(selected)}80`,
              }"
            />
          </div>
        </div>

        <!-- Ability scores grid -->
        <div class="grid grid-cols-3 gap-1.5">
          <div
            v-for="(abbr, key) in ABILITY_ABBR"
            :key="key"
            class="rpg-mini-panel flex flex-col items-center rounded-lg border py-1.5"
          >
            <span class="rpg-text-dim text-[9px] font-bold uppercase tracking-[0.15em]">{{ abbr }}</span>
            <span class="rpg-text-main font-display text-sm font-bold">{{ selected.ability_scores[key] ?? '—' }}</span>
            <span class="rpg-text-gold font-mono text-xs font-bold">{{ fmtMod(selected.ability_scores[key] ?? 10) }}</span>
          </div>
        </div>

        <!-- Conditions -->
        <div v-if="selected.conditions?.length" class="flex flex-wrap gap-1">
          <span
            v-for="cond in selected.conditions"
            :key="cond"
            class="rpg-chip rpg-tone-blood"
          >{{ cond }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
