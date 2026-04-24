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

function hpPct(c: Character): number {
  return Math.max(0, c.hp_max > 0 ? (c.hp_current / c.hp_max) * 100 : 0)
}

function hpColor(c: Character): string {
  const pct = hpPct(c)
  return pct > 50 ? 'var(--color-green)' : pct > 25 ? '#e5b93a' : 'var(--color-blood)'
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
      class="flex shrink-0 items-center border-b px-4 py-2.5"
      :style="{ borderColor: 'var(--color-border)' }"
    >
      <span class="rpg-eyebrow">✦ Personnages</span>
    </div>

    <!-- Empty state -->
    <div
      v-if="charStore.sessionCharacters.length === 0"
      class="flex flex-1 items-center justify-center"
    >
      <p class="font-serif italic text-sm" :style="{ color: 'var(--color-text-muted)' }">Aucun personnage</p>
    </div>

    <div v-else class="flex flex-1 min-h-0 overflow-hidden">

      <!-- Left: character list (MiniCharRow style) -->
      <div
        class="w-[45%] shrink-0 overflow-y-auto border-r py-2 space-y-1.5 px-2"
        :style="{ borderColor: 'var(--color-border)' }"
      >
        <button
          v-for="c in charStore.sessionCharacters"
          :key="c.id"
          class="w-full rounded-lg border px-2.5 py-2 text-left transition-all"
          :style="{
            borderColor: selected?.id === c.id ? 'rgba(255,130,71,0.5)' : 'var(--color-border)',
            background: selected?.id === c.id ? 'rgba(255,130,71,0.05)' : 'var(--color-surface)',
          }"
          @click="charStore.setSelectedCharacter(c)"
        >
          <div class="flex items-center gap-2">
            <!-- Avatar -->
            <div
              class="flex h-7 w-7 shrink-0 items-center justify-center rounded-md font-display text-[13px] font-bold"
              :style="{
                background: c.is_ai
                  ? 'linear-gradient(135deg, var(--color-arcane), #7050b0)'
                  : 'linear-gradient(135deg, var(--color-ember), var(--color-gold))',
                color: 'var(--color-bg)',
              }"
            >{{ c.name.charAt(0).toUpperCase() }}</div>

            <!-- Name + AI badge -->
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-1.5">
                <span
                  class="truncate font-display text-xs font-semibold"
                  :style="{ color: isMyChar(c) ? 'var(--color-gold)' : 'var(--color-parchment)' }"
                >{{ c.name }}</span>
                <span
                  v-if="c.is_ai"
                  class="shrink-0 text-[8px] font-bold tracking-[0.1em]"
                  :style="{ color: 'var(--color-arcane)' }"
                >IA</span>
              </div>
              <div class="text-[10px]" :style="{ color: 'var(--color-text-muted)' }">
                Niv. {{ c.level }} · {{ c.char_class }}
              </div>
            </div>
          </div>

          <!-- HP mini-bar -->
          <div class="mt-1.5">
            <div
              class="relative w-full overflow-hidden rounded-full"
              style="height: 4px; background: rgba(0,0,0,0.4);"
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
          <p class="font-display text-sm font-bold" :style="{ color: 'var(--color-parchment)' }">{{ selected.name }}</p>
          <p class="text-[11px]" :style="{ color: 'var(--color-text-muted)' }">
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
          @click="charStore.toggleAiControl(selected.id)"
        >
          <span class="font-semibold">{{ selected.is_ai ? '🤖 Géré par l\'IA' : '👤 Joueur humain' }}</span>
          <span class="ml-2 opacity-60 text-xs">— {{ selected.is_ai ? 'reprendre le contrôle' : 'confier à l\'IA' }}</span>
        </button>

        <!-- HP bar (D3 style) -->
        <div>
          <div class="mb-1.5 flex justify-between text-xs">
            <span :style="{ color: 'var(--color-text-muted)' }">Points de vie</span>
            <span class="font-mono font-semibold" :style="{ color: 'var(--color-parchment)' }">
              {{ selected.hp_current }}<span :style="{ color: 'var(--color-text-dim)' }">/{{ selected.hp_max }}</span>
              <span v-if="selected.hp_temp > 0" class="ml-1" :style="{ color: 'var(--color-arcane)' }">+{{ selected.hp_temp }}</span>
            </span>
          </div>
          <div
            class="relative w-full overflow-hidden rounded-full"
            style="height: 8px; background: rgba(0,0,0,0.4); border: 1px solid rgba(255,255,255,0.04);"
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
            class="flex flex-col items-center rounded-lg border py-1.5"
            :style="{
              background: 'var(--color-surface)',
              borderColor: 'var(--color-border)',
            }"
          >
            <span class="text-[9px] font-bold uppercase tracking-[0.15em]" :style="{ color: 'var(--color-text-dim)' }">{{ abbr }}</span>
            <span class="font-display text-sm font-bold" :style="{ color: 'var(--color-parchment)' }">{{ selected.ability_scores[key] ?? '—' }}</span>
            <span class="font-mono text-xs font-bold" :style="{ color: 'var(--color-gold)' }">{{ fmtMod(selected.ability_scores[key] ?? 10) }}</span>
          </div>
        </div>

        <!-- Conditions -->
        <div v-if="selected.conditions?.length" class="flex flex-wrap gap-1">
          <span
            v-for="cond in selected.conditions"
            :key="cond"
            class="rpg-chip"
            :style="{ color: 'var(--color-blood)', borderColor: 'rgba(232,69,69,0.4)' }"
          >{{ cond }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
