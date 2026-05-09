<script setup lang="ts">
import { computed } from 'vue'
import { useCharacterStore } from '../../stores/character'
import { useGameStore } from '../../stores/game'

const emit = defineEmits<{
  startCombat: []
  openSheet: [id: string]
}>()

const charStore = useCharacterStore()
const gameStore = useGameStore()

const ch = computed(() => charStore.myCharacter)

const ABILITY_ABBR: Record<string, string> = {
  str: 'FOR', dex: 'DEX', con: 'CON', int: 'INT', wis: 'SAG', cha: 'CHA',
}

function fmtMod(score: number): string {
  const m = Math.floor((score - 10) / 2)
  return m >= 0 ? `+${m}` : `${m}`
}

function hpPct(): number {
  if (!ch.value) return 0
  return Math.max(0, ch.value.hp_max > 0 ? (ch.value.hp_current / ch.value.hp_max) * 100 : 0)
}

function hpColor(): string {
  const pct = hpPct()
  return pct > 50 ? 'var(--color-green)' : pct > 25 ? 'var(--color-gold)' : 'var(--color-blood)'
}

// Arme équipée (première arme équipée dans l'équipement)
const equippedWeapon = computed(() => {
  const equipment = ch.value?.equipment ?? []
  return equipment.find((item) => {
    const cat = (item.category as string ?? '').toLowerCase()
    return item.equipped && (
      cat.includes('melee') || cat.includes('ranged') ||
      cat === 'simple_melee' || cat === 'simple_ranged' ||
      cat === 'martial_melee' || cat === 'martial_ranged'
    )
  }) ?? null
})

// Classe d'armure approximative: 10 + mod DEX (si pas d'armure connue)
const armorClass = computed(() => {
  if (!ch.value) return '—'
  const dex = ch.value.ability_scores.dex ?? 10
  const dexMod = Math.floor((dex - 10) / 2)
  return 10 + dexMod
})

// Initiative = mod DEX
const initiative = computed(() => {
  if (!ch.value) return '—'
  const dex = ch.value.ability_scores.dex ?? 10
  const mod = Math.floor((dex - 10) / 2)
  return mod >= 0 ? `+${mod}` : `${mod}`
})

const isMyTurn = computed(() =>
  gameStore.currentTurnId !== null &&
  gameStore.currentTurnId === ch.value?.id
)
</script>

<template>
  <div class="flex flex-1 min-h-0 flex-col overflow-y-auto">

    <!-- Empty state -->
    <div
      v-if="!ch"
      class="flex flex-1 items-center justify-center p-8 text-center"
    >
      <p class="rpg-text-muted font-serif italic text-sm">
        Chargement du personnage…
      </p>
    </div>

    <template v-else>
      <!-- Character card header -->
      <div
        class="rpg-character-panel-header relative shrink-0 overflow-hidden px-5 pt-5 pb-4"
        :class="{ 'is-turn': isMyTurn }"
      >
        <div class="rpg-eyebrow mb-3 relative" :class="isMyTurn ? 'rpg-text-ember' : 'rpg-text-arcane'">
          ✦ {{ isMyTurn ? 'Votre tour' : 'Votre personnage' }}
        </div>
        <div
          v-if="gameStore.isCharacterThinking(ch.id)"
          class="rpg-tone-gold rpg-tone-panel relative mb-3 inline-flex items-center gap-2 rounded-full border px-3 py-1 text-[10px] font-bold tracking-[0.08em]"
        >
          <span class="rpg-pulse">◉</span>
          <span>IA en réflexion</span>
        </div>

        <div class="relative flex items-center gap-3">
          <!-- Avatar -->
          <div
            class="rpg-character-avatar flex h-14 w-14 shrink-0 items-center justify-center rounded-[10px] font-display text-[26px] font-bold"
            :class="{ 'is-turn': isMyTurn }"
          >{{ ch.name.charAt(0).toUpperCase() }}</div>

          <div>
            <div
              class="rpg-text-main font-display text-xl font-bold tracking-[0.05em]"
            >{{ ch.name }}</div>
            <div class="rpg-text-muted text-[12px]">
              Niv. {{ ch.level }} · {{ ch.char_class }} · {{ ch.species }}
            </div>
          </div>
        </div>

        <!-- Stats row: PV / CA / Init -->
        <div class="relative mt-4 grid grid-cols-3 gap-2">
          <div
            v-for="stat in [
              { label: 'PV', value: `${ch.hp_current}/${ch.hp_max}` },
              { label: 'CA', value: String(armorClass) },
              { label: 'Init.', value: String(initiative) },
            ]"
            :key="stat.label"
            class="rpg-panel-stat flex flex-col items-center rounded-lg border py-2"
          >
            <div class="rpg-text-dim mb-0.5 text-[9px] font-bold uppercase tracking-[0.2em]">{{ stat.label }}</div>
            <div class="rpg-text-main font-mono text-base font-bold">{{ stat.value }}</div>
          </div>
        </div>

        <!-- HP bar -->
        <div
          class="rpg-hp-track thin relative mt-3 overflow-hidden rounded-full"
        >
          <div
            class="absolute inset-y-0 left-0 rounded-full transition-all duration-300"
            :style="{
              width: `${hpPct()}%`,
              background: hpColor(),
              boxShadow: `0 0 8px ${hpColor()}80`,
            }"
          />
        </div>
      </div>

      <!-- Ability scores -->
      <div class="shrink-0 px-5 py-3">
        <div class="grid grid-cols-6 gap-1">
          <div
            v-for="(abbr, key) in ABILITY_ABBR"
            :key="key"
            class="rpg-mini-panel flex flex-col items-center rounded-md border py-2"
          >
            <span class="rpg-text-dim text-[8px] font-bold uppercase tracking-[0.1em]">{{ abbr }}</span>
            <span class="rpg-text-main font-display text-sm font-bold">{{ ch.ability_scores[key] ?? '—' }}</span>
            <span class="rpg-text-gold font-mono text-[10px] font-bold">{{ fmtMod(ch.ability_scores[key] ?? 10) }}</span>
          </div>
        </div>
      </div>

      <!-- Open sheet button -->
      <div class="shrink-0 px-5 pb-3">
        <button
          class="rpg-btn-secondary w-full justify-center !text-[11px]"
          @click="emit('openSheet', ch.id)"
        >Ouvrir la fiche complète →</button>
      </div>

      <!-- Divider -->
      <div class="rpg-border shrink-0 mx-5 border-t" />

      <!-- Combat section -->
      <div class="shrink-0 px-5 py-4">
        <div class="flex items-center gap-2 mb-3">
          <span class="rpg-eyebrow rpg-text-blood">⚔ Combat</span>
          <span v-if="!gameStore.isInCombat" class="rpg-text-dim text-[11px]">— Hors combat</span>
          <span v-else class="rpg-text-blood-soft font-mono text-[11px]">— Round {{ gameStore.roundNumber }}</span>
        </div>

        <!-- Hors combat -->
        <div
          v-if="!gameStore.isInCombat"
          class="rpg-soft-panel rounded-lg border px-4 py-4 text-center"
        >
          <div class="rpg-text-dim mb-3 text-[11px]">Aucun ennemi à l'horizon</div>
          <button
            class="rpg-btn-tonal tone-blood !text-[10px] !py-1.5 !px-3"
            @click="emit('startCombat')"
          >Déclencher une rencontre</button>
        </div>

        <!-- En combat: initiative order -->
        <div v-else class="space-y-1.5">
          <div
            v-for="combatant in gameStore.combatants"
            :key="combatant.id"
            class="rpg-combat-row flex items-center gap-2 rounded-md border px-2.5 py-1.5"
            :class="{ 'is-active': combatant.is_active }"
          >
            <span
              class="w-6 shrink-0 text-center font-mono text-xs font-bold"
              :class="combatant.is_active ? 'rpg-text-gold' : 'rpg-text-muted'"
            >{{ combatant.initiative }}</span>
            <span
              class="flex-1 truncate font-display text-xs font-semibold"
              :class="combatant.is_active ? 'rpg-text-gold' : 'rpg-text-main'"
            >{{ combatant.name }}</span>
            <span
              class="rpg-text-muted shrink-0 font-mono text-[10px]"
            >{{ combatant.hp_current }}<span class="rpg-text-dim">/{{ combatant.hp_max }}</span></span>
            <span v-if="combatant.is_active" class="rpg-text-gold">◆</span>
          </div>
        </div>
      </div>

      <!-- Divider -->
      <div class="rpg-border shrink-0 mx-5 border-t" />

      <!-- Equipped weapon -->
      <div v-if="equippedWeapon" class="shrink-0 px-5 py-4">
        <div class="rpg-eyebrow mb-2">✦ Arme équipée</div>
        <div class="rpg-mini-panel rounded-lg border px-3 py-2.5">
          <div class="rpg-text-main font-display text-sm font-bold">
            {{ (equippedWeapon.name_fr as string) || (equippedWeapon.name as string) || 'Arme' }}
          </div>
          <div class="rpg-text-muted mt-0.5 text-[11px]">
            {{ (equippedWeapon.detail as string) || (equippedWeapon.category as string) || '—' }}
          </div>
        </div>
      </div>

      <!-- Conditions -->
      <div v-if="ch.conditions?.length" class="shrink-0 px-5 pb-4 flex flex-wrap gap-1">
        <span
          v-for="cond in ch.conditions"
          :key="cond"
          class="rpg-chip rpg-tone-blood"
        >{{ cond }}</span>
      </div>
    </template>
  </div>
</template>
