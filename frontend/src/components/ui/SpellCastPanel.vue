<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useCharacterStore } from '../../stores/character'
import { useGameStore } from '../../stores/game'
import { srdApi } from '../../services/api'
import type { SrdSpell } from '../../types'

const emit = defineEmits<{
  confirm: [spellId: string, slotLevel: number, targetId: string | undefined]
  cancel: []
}>()

const charStore = useCharacterStore()
const gameStore = useGameStore()

type Step = 1 | 2 | 3
const step = ref<Step>(1)
const allSpells = ref<SrdSpell[]>([])
const selectedSpell = ref<SrdSpell | null>(null)
const selectedSlotLevel = ref<number>(0)
const loading = ref(false)
const noSlotsSpellId = ref<string | null>(null)

// Sorts connus du personnage, triés par niveau puis nom
const knownSpells = computed<SrdSpell[]>(() => {
  const char = charStore.myCharacter
  if (!char || !char.known_spells.length) return []
  return allSpells.value
    .filter((s) => char.known_spells.includes(s.id))
    .sort((a, b) => a.level - b.level || a.name_fr.localeCompare(b.name_fr))
})

// Emplacements disponibles pour le sort sélectionné (≥ niveau du sort)
const availableSlots = computed<{ level: number; remaining: number }[]>(() => {
  const char = charStore.myCharacter
  const spell = selectedSpell.value
  if (!char || !spell || spell.level === 0) return []

  const slots = char.spell_slots as Record<string, { total: number; used: number }>
  const result: { level: number; remaining: number }[] = []
  for (let lvl = spell.level; lvl <= 9; lvl++) {
    const info = slots[String(lvl)]
    if (info) {
      const remaining = info.total - info.used
      if (remaining > 0) result.push({ level: lvl, remaining })
    }
  }
  return result
})

// Cibles disponibles en combat (hors soi-même)
const combatTargets = computed(() => {
  const myId = charStore.myCharacter?.id
  return gameStore.combatants.filter((c) => c.id !== myId)
})

// Un sort d'attaque de sort nécessite de choisir une cible explicite
const needsTarget = computed(() => {
  const spell = selectedSpell.value
  if (!spell) return false
  return (
    ['ranged_spell', 'melee_spell'].includes(spell.attack_type ?? '') &&
    gameStore.isInCombat &&
    combatTargets.value.length > 0
  )
})

function hasAvailableSlot(spell: SrdSpell): boolean {
  if (spell.level === 0) return true
  const char = charStore.myCharacter
  if (!char) return false
  const slots = char.spell_slots as Record<string, { total: number; used: number }>
  for (let lvl = spell.level; lvl <= 9; lvl++) {
    const info = slots[String(lvl)]
    if (info && info.total - info.used > 0) return true
  }
  return false
}

function selectSpell(spell: SrdSpell) {
  noSlotsSpellId.value = null
  if (!hasAvailableSlot(spell)) {
    noSlotsSpellId.value = spell.id
    return
  }
  selectedSpell.value = spell

  if (spell.level === 0) {
    // Cantrip : pas d'emplacement à choisir
    selectedSlotLevel.value = 0
    if (needsTarget.value) {
      step.value = 3
    } else {
      emit('confirm', spell.id, 0, undefined)
    }
  } else {
    selectedSlotLevel.value = availableSlots.value[0]?.level ?? spell.level
    step.value = 2
  }
}

function confirmSlot() {
  if (!selectedSpell.value) return
  if (needsTarget.value) {
    step.value = 3
  } else {
    emit('confirm', selectedSpell.value.id, selectedSlotLevel.value, undefined)
  }
}

function confirmTarget(targetId?: string) {
  if (!selectedSpell.value) return
  emit('confirm', selectedSpell.value.id, selectedSlotLevel.value, targetId)
}

function schoolLabel(school: string): { text: string; cls: string } {
  const map: Record<string, { text: string; cls: string }> = {
    evocation:    { text: 'Évocation',     cls: 'text-blood' },
    conjuration:  { text: 'Conjuration',   cls: 'text-arcane' },
    abjuration:   { text: 'Abjuration',    cls: 'text-gold' },
    divination:   { text: 'Divination',    cls: 'text-parchment/70' },
    enchantment:  { text: 'Enchantement',  cls: 'text-purple-400' },
    illusion:     { text: 'Illusion',      cls: 'text-blue-400' },
    necromancy:   { text: 'Nécromancie',   cls: 'text-green-500' },
    transmutation:{ text: 'Transmutation', cls: 'text-orange-400' },
  }
  return map[school] ?? { text: school, cls: 'text-parchment/50' }
}

const totalSteps = computed(() => {
  if (!selectedSpell.value) return 3
  if (selectedSpell.value.level === 0) return needsTarget.value ? 2 : 1
  return needsTarget.value ? 3 : 2
})

onMounted(async () => {
  loading.value = true
  try {
    const data = await srdApi.listSpells()
    allSpells.value = data.spells
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-ink/80 backdrop-blur-sm">
    <div class="w-full max-w-md rounded-lg border border-arcane/40 bg-ink shadow-2xl">

      <!-- En-tête -->
      <div class="flex items-center justify-between border-b border-arcane/20 px-4 py-3">
        <h2 class="font-semibold text-arcane">
          ✦ Lancer un sort
        </h2>
        <div class="flex items-center gap-3">
          <span class="text-xs text-parchment/30">Étape {{ step }}/{{ totalSteps }}</span>
          <button class="text-parchment/40 hover:text-parchment transition-colors" @click="emit('cancel')">✕</button>
        </div>
      </div>

      <!-- Étape 1 : Sélection du sort -->
      <div v-if="step === 1">
        <div v-if="loading" class="p-6 text-center text-parchment/40">Chargement…</div>
        <div v-else-if="knownSpells.length === 0" class="p-6 text-center text-parchment/40">
          Aucun sort connu.
        </div>
        <div v-else class="max-h-96 overflow-y-auto p-3 space-y-1">
          <button
            v-for="spell in knownSpells"
            :key="spell.id"
            class="w-full rounded border px-3 py-2 text-left transition-colors"
            :class="hasAvailableSlot(spell)
              ? 'border-gold/15 hover:bg-arcane/10 hover:border-arcane/30 cursor-pointer'
              : 'border-gold/5 opacity-40 cursor-not-allowed'"
            :title="!hasAvailableSlot(spell) ? 'Aucun emplacement disponible' : undefined"
            @click="selectSpell(spell)"
          >
            <div class="flex items-center justify-between">
              <span class="font-medium text-parchment text-sm">{{ spell.name_fr }}</span>
              <span class="text-xs text-parchment/40 shrink-0">
                {{ spell.level === 0 ? 'Cantrip' : `Niv. ${spell.level}` }}
              </span>
            </div>
            <div class="flex items-center gap-2 mt-0.5">
              <span class="text-xs" :class="schoolLabel(spell.school).cls">
                {{ schoolLabel(spell.school).text }}
              </span>
              <span v-if="spell.damage_dice" class="text-xs text-blood/80">{{ spell.damage_dice }}</span>
              <span v-if="spell.concentration" class="text-xs text-gold/60">conc.</span>
              <span v-if="noSlotsSpellId === spell.id" class="text-xs text-blood ml-auto">
                Aucun emplacement
              </span>
            </div>
          </button>
        </div>
      </div>

      <!-- Étape 2 : Choix de l'emplacement -->
      <div v-if="step === 2" class="p-4">
        <p class="mb-3 text-sm text-parchment/60">
          <span class="font-medium text-arcane">{{ selectedSpell?.name_fr }}</span>
          — choisissez l'emplacement :
        </p>
        <div class="space-y-2">
          <button
            v-for="slot in availableSlots"
            :key="slot.level"
            class="w-full rounded border px-4 py-2.5 text-left transition-colors"
            :class="selectedSlotLevel === slot.level
              ? 'border-arcane bg-arcane/20 text-arcane'
              : 'border-gold/20 text-parchment hover:bg-arcane/10 hover:border-arcane/30'"
            @click="selectedSlotLevel = slot.level"
          >
            <span class="font-medium">Niveau {{ slot.level }}</span>
            <span class="ml-2 text-xs opacity-60">
              ({{ slot.remaining }} restant{{ slot.remaining > 1 ? 's' : '' }})
            </span>
            <span
              v-if="selectedSpell && slot.level > selectedSpell.level"
              class="ml-2 text-xs text-arcane"
            >↑ surpuissant</span>
          </button>
        </div>
        <div class="mt-4 flex gap-2">
          <button
            class="flex-1 rounded border border-parchment/20 py-2 text-sm text-parchment/50 hover:text-parchment transition-colors"
            @click="step = 1"
          >← Retour</button>
          <button
            class="flex-1 rounded border border-arcane/50 bg-arcane/15 py-2 text-sm font-semibold text-arcane hover:bg-arcane/25 transition-colors"
            @click="confirmSlot"
          >Confirmer →</button>
        </div>
      </div>

      <!-- Étape 3 : Choix de la cible -->
      <div v-if="step === 3" class="p-4">
        <p class="mb-3 text-sm text-parchment/60">
          <span class="font-medium text-arcane">{{ selectedSpell?.name_fr }}</span>
          — choisissez la cible :
        </p>
        <div class="space-y-2">
          <button
            v-for="target in combatTargets"
            :key="target.id"
            class="w-full rounded border border-gold/15 px-4 py-2.5 text-left hover:bg-blood/10 hover:border-blood/30 transition-colors"
            @click="confirmTarget(target.id)"
          >
            <span class="font-medium text-parchment text-sm">{{ target.name }}</span>
            <span class="ml-2 text-xs text-parchment/40">
              PV {{ target.hp_current }}/{{ target.hp_max }}
            </span>
          </button>
          <button
            class="w-full rounded border border-parchment/15 px-4 py-2 text-sm text-parchment/50 hover:text-parchment hover:border-parchment/30 transition-colors"
            @click="confirmTarget(undefined)"
          >Sans cible spécifique</button>
        </div>
        <button
          class="mt-3 w-full rounded border border-parchment/15 py-2 text-sm text-parchment/40 hover:text-parchment transition-colors"
          @click="selectedSpell && selectedSpell.level > 0 ? (step = 2) : (step = 1)"
        >← Retour</button>
      </div>

    </div>
  </div>
</template>
