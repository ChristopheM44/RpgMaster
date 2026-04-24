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
  { label: 'Attaquer', type: 'attack', icon: '⚔', tone: 'tone-blood' },
  { label: 'Sort', type: 'cast_spell', icon: '✦', tone: 'tone-arcane' },
  { label: 'Objet', type: 'use_item', icon: '🎒', tone: 'tone-gold' },
  { label: 'Foncer', type: 'move', icon: '💨', tone: 'tone-teal' },
  { label: 'Fin du tour', type: 'end_turn', icon: '⏭', tone: 'tone-gold' },
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
    <div class="rpg-card w-full max-w-md rounded-t-xl p-4 shadow-xl">
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
            class="rpg-btn-tonal tone-arcane"
            @click="onItemAction(item, 'use_item')"
          >Utiliser</button>
          <button
            v-else
            class="rpg-btn-tonal tone-gold"
            @click="onItemAction(item, 'equip')"
          >{{ item.equipped ? 'Retirer' : 'Équiper' }}</button>
        </div>
        <p v-if="combatItems.length === 0" class="py-2 text-center text-sm text-parchment/40">
          Aucun objet disponible
        </p>
      </div>
      <button
        class="rpg-btn-secondary mt-3 w-full justify-center"
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
    <div class="rpg-card w-full max-w-md rounded-t-xl p-4 shadow-xl">
      <p class="mb-3 text-sm font-semibold text-parchment/70">Choisissez une cible :</p>
      <div class="space-y-2">
        <button
          v-for="target in attackTargets"
          :key="target.id"
          class="rpg-btn-tonal tone-blood w-full text-left"
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
        class="rpg-btn-secondary mt-3 w-full justify-center"
        @click="showTargetSelector = false"
      >
        Annuler
      </button>
    </div>
  </div>

  <div
    class="shrink-0 border-t px-5 py-4"
    :style="{
      borderColor: 'var(--color-border)',
      background: 'var(--color-bg-elev)',
    }"
  >
    <!-- Character context line -->
    <div
      v-if="charStore.myCharacter"
      class="mb-3 flex items-center gap-2.5"
    >
      <div
        class="flex h-7 w-7 shrink-0 items-center justify-center rounded-md font-display text-xs font-bold"
        :style="{
          background: 'linear-gradient(135deg, var(--color-ember), var(--color-gold))',
          color: 'var(--color-bg)',
        }"
      >{{ charStore.myCharacter.name.charAt(0).toUpperCase() }}</div>
      <span class="text-sm" :style="{ color: 'var(--color-text-muted)' }">
        Vous incarnez
        <strong class="font-display" :style="{ color: 'var(--color-parchment)' }">{{ charStore.myCharacter.name }}</strong>
        <span v-if="isMyTurn && gameStore.isInCombat" :style="{ color: 'var(--color-ember)' }"> — c'est à vous de jouer</span>
        <span v-else-if="gameStore.isInCombat && activeCombatantName" class="italic"> — tour de {{ activeCombatantName }}</span>
      </span>
    </div>

    <!-- Unconscious state -->
    <div
      v-if="isDowned && isMyTurn"
      class="mb-3 rounded-lg border px-3 py-2 text-sm italic"
      :style="{ background: 'rgba(232,69,69,0.08)', borderColor: 'rgba(232,69,69,0.3)', color: 'rgba(232,69,69,0.8)' }"
    >
      Vous êtes inconscient(e). Effectuez votre jet de sauvegarde contre la mort.
    </div>
    <div
      v-else-if="isDowned && !isMyTurn"
      class="mb-3 rounded-lg border px-3 py-2 text-sm italic"
      :style="{ background: 'rgba(232,69,69,0.06)', borderColor: 'rgba(232,69,69,0.2)', color: 'rgba(232,69,69,0.6)' }"
    >
      Inconscient(e) — en attente de votre tour.
    </div>

    <!-- Textarea + Envoyer -->
    <div class="flex items-end gap-3">
      <textarea
        v-model="input"
        rows="2"
        :placeholder="gameStore.isProcessing ? 'Le Maître du Jeu répond…' : 'Décrivez votre action, parlez, ou posez une question au MJ…'"
        :disabled="!canSend"
        class="rpg-input flex-1 resize-none"
        style="font-family: inherit; font-size: 14px;"
        @keydown="onKeydown"
      />
      <button
        class="rpg-btn-primary shrink-0 self-end !px-5 !py-3"
        :disabled="!input.trim() || !canSend"
        @click="submitText"
      >Envoyer ↵</button>
    </div>

    <!-- Action chips row -->
    <div class="mt-2.5 flex items-center gap-2 flex-wrap">
      <!-- Death save -->
      <template v-if="isDowned && isMyTurn">
        <button class="rpg-btn-tonal tone-blood !py-1 !text-[11px]" :disabled="!canSend" @click="onDeathSave">
          💀 Jet de sauvegarde
        </button>
        <button class="rpg-btn-secondary !py-1 !text-[11px]" @click="emit('action', 'end_turn')">
          ⏭ Fin du tour
        </button>
      </template>

      <!-- Normal actions (combat or exploration) -->
      <template v-else-if="!isDowned">
        <button
          v-for="action in combatActions"
          :key="action.type"
          class="rpg-btn-tonal !py-1 !text-[11px]"
          :class="[action.tone, (gameStore.isInCombat && !isMyTurn) ? 'opacity-40 !cursor-not-allowed' : '']"
          :disabled="gameStore.isInCombat && !isMyTurn"
          @click="onCombatAction(action.type)"
        >
          {{ action.icon }} {{ action.label }}
        </button>

        <template v-if="isMyTurn && downedAllies.length > 0">
          <button
            v-for="ally in downedAllies"
            :key="ally.id"
            class="rpg-btn-tonal tone-arcane !py-1 !text-[11px]"
            :disabled="!canSend"
            @click="onStabilize(ally.id)"
          >🩹 Stabiliser {{ ally.name }}</button>
        </template>
      </template>
    </div>
  </div>
</template>
