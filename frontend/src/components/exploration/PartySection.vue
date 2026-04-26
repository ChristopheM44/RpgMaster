<script setup lang="ts">
import { computed } from 'vue'
import { useCharacterStore } from '../../stores/character'
import { useWebSocket } from '../../composables/useWebSocket'
import { useRoute } from 'vue-router'

const emit = defineEmits<{
  openSheet: [id: string]
}>()

const charStore = useCharacterStore()
const route = useRoute()
const { toggleAiControl } = useWebSocket(route.params.id as string)

const CLASS_FR: Record<string, string> = {
  fighter: 'Guerrier',
  wizard: 'Mage',
  cleric: 'Clerc',
  rogue: 'Roublard',
  ranger: 'Rôdeur',
  paladin: 'Paladin',
  barbarian: 'Barbare',
  bard: 'Barde',
  druid: 'Druide',
  monk: 'Moine',
  sorcerer: 'Ensorceleur',
  warlock: 'Occultiste',
}

const WEAPON_CATEGORIES = new Set([
  'simple_melee', 'simple_ranged', 'martial_melee', 'martial_ranged',
])

function hpColor(current: number, max: number): string {
  if (max <= 0) return 'var(--color-text-dim)'
  const pct = (current / max) * 100
  return pct > 50 ? 'var(--color-green)' : pct > 25 ? 'var(--color-gold)' : 'var(--color-blood)'
}

function calcAc(abilityScores: Record<string, number>): number {
  const dex = abilityScores.dex ?? 10
  return 10 + Math.floor((dex - 10) / 2)
}

function equippedWeaponName(equipment: Record<string, unknown>[]): string | null {
  const weapon = equipment.find(
    (item) => item.equipped && WEAPON_CATEGORIES.has(item.category as string),
  )
  return weapon ? (weapon.name_fr as string ?? weapon.name as string ?? null) : null
}

function spellSlotsSummary(spellSlots: Record<string, unknown>): { left: number; total: number } | null {
  if (!spellSlots || Object.keys(spellSlots).length === 0) return null
  let left = 0
  let total = 0
  for (const slot of Object.values(spellSlots) as { total: number; used: number }[]) {
    total += slot.total
    left += slot.total - slot.used
  }
  return total > 0 ? { left, total } : null
}

const characters = computed(() => charStore.sessionCharacters)
const myId = computed(() => charStore.myCharacter?.id)

async function handleToggleAi(charId: string, currentIsAi: boolean) {
  await charStore.toggleAiControl(charId)
  toggleAiControl(charId, !currentIsAi)
}
</script>

<template>
  <div class="space-y-2 px-4 py-3">
    <div
      v-for="c in characters"
      :key="c.id"
      class="flex items-center gap-3 rounded-lg px-3 py-2.5"
      :style="{
        background: c.id === myId ? 'rgba(212,175,55,0.07)' : 'rgba(255,255,255,0.02)',
        border: c.id === myId ? '1px solid rgba(212,175,55,0.25)' : '1px solid rgba(255,255,255,0.04)',
      }"
    >
      <!-- Avatar -->
      <div
        class="flex h-9 w-9 shrink-0 items-center justify-center rounded-md font-display text-sm font-bold"
        :style="{
          background: c.is_ai
            ? 'linear-gradient(135deg, var(--color-arcane), #7c3aed)'
            : 'linear-gradient(135deg, var(--color-ember), var(--color-gold))',
          color: 'var(--color-bg)',
        }"
      >{{ c.name.charAt(0).toUpperCase() }}</div>

      <!-- Info -->
      <div class="min-w-0 flex-1">
        <div class="flex items-center gap-1.5">
          <span
            class="font-display text-[11px] font-bold truncate"
            :style="{ color: c.id === myId ? 'var(--color-gold)' : 'var(--color-parchment)' }"
          >{{ c.name }}</span>
          <span
            v-if="c.is_ai"
            class="shrink-0 rounded px-1 text-[8px] font-bold uppercase tracking-[0.1em]"
            :style="{
              color: 'var(--color-arcane)',
              background: 'rgba(139,92,246,0.12)',
              border: '1px solid rgba(139,92,246,0.3)',
            }"
          >IA</span>
        </div>

        <div class="text-[10px]" :style="{ color: 'var(--color-text-dim)' }">
          {{ CLASS_FR[c.char_class] ?? c.char_class }} Niv.{{ c.level }}
        </div>

        <!-- HP bar -->
        <div
          class="mt-1.5 h-0.5 w-full overflow-hidden rounded-full"
          :style="{ background: 'rgba(255,255,255,0.08)' }"
        >
          <div
            class="h-full rounded-full transition-all"
            :style="{
              width: `${c.hp_max > 0 ? Math.max(0, (c.hp_current / c.hp_max) * 100) : 0}%`,
              background: hpColor(c.hp_current, c.hp_max),
            }"
          />
        </div>

        <!-- Stats line -->
        <div class="mt-1 flex items-center gap-2 font-mono text-[10px]" :style="{ color: 'var(--color-text-muted)' }">
          <span>{{ c.hp_current }}/{{ c.hp_max }} PV · CA {{ calcAc(c.ability_scores) }}</span>
          <template v-if="equippedWeaponName(c.equipment)">
            <span :style="{ color: 'var(--color-text-dim)' }">·</span>
            <span>⚔ {{ equippedWeaponName(c.equipment) }}</span>
          </template>
          <template v-if="spellSlotsSummary(c.spell_slots as Record<string, unknown>)">
            <span :style="{ color: 'var(--color-text-dim)' }">·</span>
            <span>✦ {{ spellSlotsSummary(c.spell_slots as Record<string, unknown>)?.left }}/{{ spellSlotsSummary(c.spell_slots as Record<string, unknown>)?.total }}</span>
          </template>
        </div>
      </div>

      <!-- Buttons -->
      <div class="flex shrink-0 flex-col gap-1">
        <button
          class="flex h-7 w-7 items-center justify-center rounded text-[13px] transition-colors hover:bg-white/[0.06]"
          :title="c.is_ai ? 'Passer en contrôle humain' : 'Passer en contrôle IA'"
          @click="handleToggleAi(c.id, c.is_ai)"
        >{{ c.is_ai ? '🤖' : '👤' }}</button>
        <button
          class="flex h-7 w-7 items-center justify-center rounded text-[13px] transition-colors hover:bg-white/[0.06]"
          title="Voir la fiche"
          @click="emit('openSheet', c.id)"
        >📜</button>
      </div>
    </div>

    <div
      v-if="!characters.length"
      class="py-4 text-center text-[12px] italic"
      :style="{ color: 'var(--color-text-muted)' }"
    >
      Aucun personnage dans la session
    </div>
  </div>
</template>
