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
  return pct > 50 ? 'var(--color-green)' : pct > 25 ? '#e5b93a' : 'var(--color-blood)'
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
      <p class="font-serif italic text-sm" :style="{ color: 'var(--color-text-muted)' }">
        Chargement du personnage…
      </p>
    </div>

    <template v-else>
      <!-- Character card header -->
      <div
        class="relative shrink-0 overflow-hidden px-5 pt-5 pb-4"
        :style="{
          background: isMyTurn
            ? 'linear-gradient(180deg, rgba(255,130,71,0.12), rgba(255,130,71,0.04))'
            : 'linear-gradient(180deg, rgba(192,144,255,0.08), transparent)',
        }"
      >
        <!-- Glow blob -->
        <div
          aria-hidden="true"
          class="pointer-events-none absolute"
          :style="{
            top: '-40px', right: '-20px',
            width: '160px', height: '160px', borderRadius: '80px',
            background: isMyTurn
              ? 'radial-gradient(circle, rgba(255,130,71,0.2), transparent 70%)'
              : 'radial-gradient(circle, rgba(192,144,255,0.15), transparent 70%)',
          }"
        />

        <div class="rpg-eyebrow mb-3 relative" :style="{ color: isMyTurn ? 'var(--color-ember)' : 'var(--color-arcane)' }">
          ✦ {{ isMyTurn ? 'Votre tour' : 'Votre personnage' }}
        </div>

        <div class="relative flex items-center gap-3">
          <!-- Avatar -->
          <div
            class="flex h-14 w-14 shrink-0 items-center justify-center rounded-[10px] font-display text-[26px] font-bold"
            :style="{
              background: 'linear-gradient(135deg, var(--color-ember), var(--color-gold))',
              color: 'var(--color-bg)',
              boxShadow: isMyTurn
                ? '0 0 0 2px var(--color-bg-elev), 0 0 0 3px var(--color-ember), 0 0 20px rgba(255,130,71,0.4)'
                : '0 0 0 2px var(--color-bg-elev), 0 0 0 3px rgba(192,144,255,0.4)',
            }"
          >{{ ch.name.charAt(0).toUpperCase() }}</div>

          <div>
            <div
              class="font-display text-xl font-bold tracking-[0.05em]"
              :style="{ color: 'var(--color-parchment)' }"
            >{{ ch.name }}</div>
            <div class="text-[12px]" :style="{ color: 'var(--color-text-muted)' }">
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
            class="flex flex-col items-center rounded-lg border py-2"
            :style="{ background: 'rgba(0,0,0,0.25)', borderColor: 'var(--color-border)' }"
          >
            <div class="text-[9px] font-bold uppercase tracking-[0.2em] mb-0.5" :style="{ color: 'var(--color-text-dim)' }">{{ stat.label }}</div>
            <div class="font-mono text-base font-bold" :style="{ color: 'var(--color-parchment)' }">{{ stat.value }}</div>
          </div>
        </div>

        <!-- HP bar -->
        <div
          class="relative mt-3 overflow-hidden rounded-full"
          style="height: 6px; background: rgba(0,0,0,0.4); border: 1px solid rgba(255,255,255,0.04);"
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
            class="flex flex-col items-center rounded-md border py-2"
            :style="{ background: 'var(--color-surface)', borderColor: 'var(--color-border)' }"
          >
            <span class="text-[8px] font-bold uppercase tracking-[0.1em]" :style="{ color: 'var(--color-text-dim)' }">{{ abbr }}</span>
            <span class="font-display text-sm font-bold" :style="{ color: 'var(--color-parchment)' }">{{ ch.ability_scores[key] ?? '—' }}</span>
            <span class="font-mono text-[10px] font-bold" :style="{ color: 'var(--color-gold)' }">{{ fmtMod(ch.ability_scores[key] ?? 10) }}</span>
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
      <div class="shrink-0 mx-5 border-t" :style="{ borderColor: 'var(--color-border)' }" />

      <!-- Combat section -->
      <div class="shrink-0 px-5 py-4">
        <div class="flex items-center gap-2 mb-3">
          <span class="rpg-eyebrow" :style="{ color: 'var(--color-blood)' }">⚔ Combat</span>
          <span v-if="!gameStore.isInCombat" class="text-[11px]" :style="{ color: 'var(--color-text-dim)' }">— Hors combat</span>
          <span v-else class="font-mono text-[11px]" :style="{ color: 'rgba(232,69,69,0.7)' }">— Round {{ gameStore.roundNumber }}</span>
        </div>

        <!-- Hors combat -->
        <div
          v-if="!gameStore.isInCombat"
          class="rounded-lg border px-4 py-4 text-center"
          :style="{ background: 'rgba(0,0,0,0.2)', borderColor: 'var(--color-border)' }"
        >
          <div class="mb-3 text-[11px]" :style="{ color: 'var(--color-text-dim)' }">Aucun ennemi à l'horizon</div>
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
            class="flex items-center gap-2 rounded-md border px-2.5 py-1.5"
            :style="{
              background: combatant.is_active ? 'rgba(255,130,71,0.06)' : 'var(--color-surface)',
              borderColor: combatant.is_active ? 'rgba(255,130,71,0.4)' : 'var(--color-border)',
            }"
          >
            <span
              class="w-6 shrink-0 text-center font-mono text-xs font-bold"
              :style="{ color: combatant.is_active ? 'var(--color-gold)' : 'var(--color-text-muted)' }"
            >{{ combatant.initiative }}</span>
            <span
              class="flex-1 truncate font-display text-xs font-semibold"
              :style="{ color: combatant.is_active ? 'var(--color-gold)' : 'var(--color-parchment)' }"
            >{{ combatant.name }}</span>
            <span
              class="shrink-0 font-mono text-[10px]"
              :style="{ color: 'var(--color-text-muted)' }"
            >{{ combatant.hp_current }}<span :style="{ color: 'var(--color-text-dim)' }">/{{ combatant.hp_max }}</span></span>
            <span v-if="combatant.is_active" :style="{ color: 'var(--color-gold)' }">◆</span>
          </div>
        </div>
      </div>

      <!-- Divider -->
      <div class="shrink-0 mx-5 border-t" :style="{ borderColor: 'var(--color-border)' }" />

      <!-- Equipped weapon -->
      <div v-if="equippedWeapon" class="shrink-0 px-5 py-4">
        <div class="rpg-eyebrow mb-2">✦ Arme équipée</div>
        <div class="rounded-lg border px-3 py-2.5" :style="{ background: 'var(--color-surface)', borderColor: 'var(--color-border)' }">
          <div class="font-display text-sm font-bold" :style="{ color: 'var(--color-parchment)' }">
            {{ (equippedWeapon.name_fr as string) || (equippedWeapon.name as string) || 'Arme' }}
          </div>
          <div class="mt-0.5 text-[11px]" :style="{ color: 'var(--color-text-muted)' }">
            {{ (equippedWeapon.detail as string) || (equippedWeapon.category as string) || '—' }}
          </div>
        </div>
      </div>

      <!-- Conditions -->
      <div v-if="ch.conditions?.length" class="shrink-0 px-5 pb-4 flex flex-wrap gap-1">
        <span
          v-for="cond in ch.conditions"
          :key="cond"
          class="rpg-chip"
          :style="{ color: 'var(--color-blood)', borderColor: 'rgba(232,69,69,0.4)' }"
        >{{ cond }}</span>
      </div>
    </template>
  </div>
</template>
