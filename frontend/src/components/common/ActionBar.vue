<script setup lang="ts">
import { ref, computed } from 'vue'
import { useGameStore } from '../../stores/game'
import { useCharacterStore } from '../../stores/character'
import SpellCastPanel from '../ui/SpellCastPanel.vue'

const emit = defineEmits<{
  action: [actionType: string, content?: string, targetId?: string, extra?: Record<string, unknown>]
}>()

const gameStore = useGameStore()
const charStore = useCharacterStore()

const input = ref('')
const showSpellPanel = ref(false)
const showTargetSelector = ref(false)
const showItemPicker = ref(false)

const isMyTurn = computed(
  () => gameStore.currentTurnId === charStore.myCharacter?.id,
)

const activeCombatantName = computed(() => {
  const c = gameStore.combatants.find((c) => c.id === gameStore.currentTurnId)
  return c?.name ?? null
})

// Combattant correspondant à mon personnage dans le suivi de combat
const myCombatant = computed(
  () => gameStore.combatants.find((c) => c.id === charStore.myCharacter?.id) ?? null,
)

// Mon personnage est-il à 0 PV et inconscient (pas encore stable) ?
const isDowned = computed(
  () =>
    myCombatant.value !== null &&
    myCombatant.value.hp_current <= 0 &&
    !myCombatant.value.death_saves?.stable,
)

// Alliés à 0 PV (is_ai=false = personnage joueur, pas monstre) que je peux stabiliser
const downedAllies = computed(() =>
  gameStore.combatants.filter(
    (c) => !c.is_ai && c.id !== charStore.myCharacter?.id && c.hp_current <= 0,
  ),
)

const attackTargets = computed(() => {
  const myId = charStore.myCharacter?.id
  return gameStore.combatants.filter((c) => c.id !== myId && c.is_ai && c.hp_current > 0)
})

const combatActions = [
  { label: 'Attaquer', type: 'attack', icon: '⚔' },
  { label: 'Sort', type: 'cast_spell', icon: '✦' },
  { label: 'Objet', type: 'use_item', icon: '🎒' },
  { label: 'Foncer', type: 'move', icon: '💨' },
  { label: 'Fin du tour', type: 'end_turn', icon: '⏭' },
]

const canSend = computed(
  () => gameStore.connected && !gameStore.isProcessing,
)

function submitText() {
  const text = input.value.trim()
  if (!text || !canSend.value) return
  emit('action', 'free_text', text)
  input.value = ''
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    submitText()
  }
}

// Objets utilisables en combat : consommables + objets équipables
const combatItems = computed(() => {
  const equipment = charStore.myCharacter?.equipment as Record<string, unknown>[] | undefined
  if (!equipment) return []
  return equipment.filter((item) => {
    const id = (item.id as string ?? '').toLowerCase()
    const name = (item.name_fr as string ?? '').toLowerCase()
    const isConsumable = id.includes('potion') || name.includes('potion')
    const isEquippable = [
      'simple_melee', 'simple_ranged', 'martial_melee', 'martial_ranged',
      'light', 'medium', 'heavy', 'shield',
    ].includes(item.category as string)
    return isConsumable || isEquippable
  })
})

function onCombatAction(actionType: string) {
  if (actionType === 'cast_spell') {
    showSpellPanel.value = true
  } else if (actionType === 'attack') {
    showTargetSelector.value = true
  } else if (actionType === 'use_item') {
    showItemPicker.value = true
  } else {
    emit('action', actionType)
  }
}

function onItemAction(item: Record<string, unknown>, actionType: 'use_item' | 'equip') {
  showItemPicker.value = false
  const itemId = item.id as string
  emit('action', actionType, undefined, undefined, { item_id: itemId })
}

function confirmAttackTarget(targetId: string) {
  showTargetSelector.value = false
  emit('action', 'attack', undefined, targetId)
}

function onSpellConfirm(spellId: string, slotLevel: number, targetId: string | undefined) {
  showSpellPanel.value = false
  emit('action', 'cast_spell', undefined, targetId, {
    spell_id: spellId,
    slot_level: slotLevel,
  })
}

function onDeathSave() {
  emit('action', 'death_save')
}

function onStabilize(targetId: string) {
  emit('action', 'stabilize', undefined, targetId)
}
</script>

<template>
  <!-- Spell Cast Panel (overlay) -->
  <SpellCastPanel
    v-if="showSpellPanel"
    @confirm="onSpellConfirm"
    @cancel="showSpellPanel = false"
  />

  <!-- Item Picker (overlay) -->
  <div
    v-if="showItemPicker"
    class="fixed inset-0 z-40 flex items-end justify-center bg-black/60"
    @click.self="showItemPicker = false"
  >
    <div class="w-full max-w-md rounded-t-xl border border-gold/30 bg-ink p-4 shadow-xl">
      <p class="mb-3 text-sm font-semibold text-parchment/70">Utiliser ou équiper un objet :</p>
      <div class="space-y-1.5 max-h-60 overflow-y-auto">
        <div
          v-for="(item, idx) in combatItems"
          :key="idx"
          class="flex items-center gap-2 rounded border border-parchment/10 px-3 py-2"
        >
          <span class="flex-1 text-sm capitalize text-parchment">
            {{ String(item.name_fr ?? item.id ?? 'Objet') }}
            <span v-if="item.equipped" class="ml-1 text-xs text-gold/60">(équipé)</span>
            <span v-if="item.quantity && Number(item.quantity) > 1" class="ml-1 text-xs text-parchment/40">×{{ item.quantity }}</span>
          </span>
          <button
            v-if="(item.id as string ?? '').toLowerCase().includes('potion') || (item.name_fr as string ?? '').toLowerCase().includes('potion')"
            class="rounded border border-arcane/40 px-2 py-0.5 text-xs text-arcane/80 transition-colors hover:bg-arcane/10"
            @click="onItemAction(item, 'use_item')"
          >Utiliser</button>
          <button
            v-else
            class="rounded border px-2 py-0.5 text-xs transition-colors"
            :class="item.equipped ? 'border-gold/40 text-gold/70 hover:bg-gold/10' : 'border-parchment/20 text-parchment/50 hover:border-gold/30'"
            @click="onItemAction(item, 'equip')"
          >{{ item.equipped ? 'Retirer' : 'Équiper' }}</button>
        </div>
        <p v-if="combatItems.length === 0" class="py-2 text-center text-sm text-parchment/40">
          Aucun objet disponible
        </p>
      </div>
      <button
        class="mt-3 w-full rounded border border-parchment/15 py-2 text-sm text-parchment/40 transition-colors hover:text-parchment"
        @click="showItemPicker = false"
      >Annuler</button>
    </div>
  </div>

  <!-- Attack Target Selector (overlay) -->
  <div
    v-if="showTargetSelector"
    class="fixed inset-0 z-40 flex items-end justify-center bg-black/60"
    @click.self="showTargetSelector = false"
  >
    <div class="w-full max-w-md rounded-t-xl border border-blood/30 bg-ink p-4 shadow-xl">
      <p class="mb-3 text-sm font-semibold text-parchment/70">Choisissez une cible :</p>
      <div class="space-y-2">
        <button
          v-for="target in attackTargets"
          :key="target.id"
          class="w-full rounded border border-blood/20 px-4 py-2.5 text-left transition-colors hover:border-blood/50 hover:bg-blood/10"
          @click="confirmAttackTarget(target.id)"
        >
          <span class="font-medium text-parchment text-sm">{{ target.name }}</span>
          <span class="ml-2 text-xs text-parchment/40">PV {{ target.hp_current }}/{{ target.hp_max }}</span>
        </button>
        <p v-if="attackTargets.length === 0" class="py-2 text-center text-sm text-parchment/40">
          Aucune cible disponible
        </p>
      </div>
      <button
        class="mt-3 w-full rounded border border-parchment/15 py-2 text-sm text-parchment/40 transition-colors hover:text-parchment"
        @click="showTargetSelector = false"
      >
        Annuler
      </button>
    </div>
  </div>

  <div class="shrink-0 border-t border-gold/20 bg-ink/80 px-4 py-3 space-y-2">
    <!-- Actions de combat -->
    <div v-if="gameStore.isInCombat" class="flex flex-wrap gap-2">

      <!-- CAS 1 : Mon personnage est à 0 PV → jet de sauvegarde contre la mort uniquement -->
      <template v-if="isDowned && isMyTurn">
        <div class="w-full rounded border border-blood/40 bg-blood/10 px-3 py-2 text-sm text-blood/80 italic">
          Vous êtes inconscient(e). Effectuez votre jet de sauvegarde contre la mort.
        </div>
        <button
          class="flex items-center gap-1.5 rounded border border-blood/60 bg-blood/20 px-4 py-1.5 text-sm font-semibold text-blood transition-colors hover:bg-blood/30 cursor-pointer"
          :disabled="!canSend"
          @click="onDeathSave"
        >
          <span>💀</span>
          <span>Jet de sauvegarde</span>
        </button>
        <button
          class="flex items-center gap-1.5 rounded border border-gold/20 px-3 py-1.5 text-sm text-parchment/40 transition-colors hover:border-gold/40 hover:text-parchment cursor-pointer"
          @click="emit('action', 'end_turn')"
        >
          <span>⏭</span>
          <span>Fin du tour</span>
        </button>
      </template>

      <!-- CAS 2 : Mon tour normal -->
      <template v-else-if="!isDowned">
        <button
          v-for="action in combatActions"
          :key="action.type"
          class="flex items-center gap-1.5 rounded border px-3 py-1.5 text-sm font-semibold transition-colors"
          :class="isMyTurn
            ? 'border-gold/40 text-parchment hover:bg-gold/10 hover:border-gold cursor-pointer'
            : 'border-gold/10 text-parchment/30 cursor-not-allowed'"
          :disabled="!isMyTurn"
          @click="onCombatAction(action.type)"
        >
          <span>{{ action.icon }}</span>
          <span>{{ action.label }}</span>
        </button>

        <!-- Boutons Stabiliser (alliés à terre) -->
        <template v-if="isMyTurn && downedAllies.length > 0">
          <button
            v-for="ally in downedAllies"
            :key="ally.id"
            class="flex items-center gap-1.5 rounded border border-arcane/50 bg-arcane/10 px-3 py-1.5 text-sm font-semibold text-arcane transition-colors hover:bg-arcane/20 cursor-pointer"
            :disabled="!canSend"
            @click="onStabilize(ally.id)"
          >
            <span>🩹</span>
            <span>Stabiliser {{ ally.name }}</span>
          </button>
        </template>

        <span v-if="!isMyTurn" class="ml-auto text-xs text-parchment/30 self-center italic">
          <template v-if="activeCombatantName">Tour de {{ activeCombatantName }}...</template>
          <template v-else>En attente...</template>
        </span>
      </template>

      <!-- CAS 3 : Je suis à terre mais ce n'est pas mon tour -->
      <template v-else>
        <div class="w-full rounded border border-blood/20 bg-blood/5 px-3 py-2 text-sm text-blood/60 italic">
          Inconscient(e) — en attente de votre tour pour effectuer un jet de sauvegarde.
        </div>
      </template>
    </div>

    <!-- Free text input -->
    <div class="flex gap-2">
      <textarea
        v-model="input"
        rows="2"
        :placeholder="gameStore.isProcessing ? 'Le Maître du Jeu répond...' : 'Décrivez votre action ou parlez à vos compagnons...'"
        :disabled="!canSend"
        class="flex-1 resize-none rounded border border-gold/20 bg-ink px-3 py-2 text-sm text-parchment placeholder-parchment/30 focus:border-gold/50 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
        @keydown="onKeydown"
      />
      <button
        class="self-end rounded border border-gold/40 bg-gold/10 px-4 py-2 text-sm font-semibold text-gold hover:bg-gold/20 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        :disabled="!input.trim() || !canSend"
        @click="submitText"
      >
        Envoyer
      </button>
    </div>

    <!-- Connection status -->
    <div class="flex items-center gap-1.5 text-xs">
      <span
        class="inline-block h-2 w-2 rounded-full"
        :class="gameStore.connected ? 'bg-green-500' : 'bg-blood animate-pulse'"
      />
      <span class="text-parchment/40">
        <template v-if="gameStore.connected">
          Connecté · Phase : {{ gameStore.phase }}
          <span v-if="gameStore.isProcessing" class="ml-1 text-gold/50">· MJ en cours...</span>
        </template>
        <template v-else>
          Déconnecté
        </template>
      </span>
    </div>
  </div>
</template>
