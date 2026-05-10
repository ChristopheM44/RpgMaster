<script setup lang="ts">
import { ref, computed } from 'vue'
import { useGameStore } from '../../stores/game'
import { useCharacterStore } from '../../stores/character'
import SpellCastPanel from '../ui/SpellCastPanel.vue'
import RpgMapIcon from './RpgMapIcon.vue'
import type { RpgMapIconId } from '../../icons/rpgMapIcons'

const props = withDefaults(defineProps<{
  variant?: 'default' | 'combat-immersive'
}>(), {
  variant: 'default',
})

const emit = defineEmits<{
  action: [actionType: string, content?: string, targetId?: string, extra?: Record<string, unknown>]
  mapMode: [mode: 'inspect' | 'move' | 'attack' | 'spell']
}>()

const gameStore = useGameStore()
const charStore = useCharacterStore()

const input = ref('')
const showSpellPanel = ref(false)
const showTargetSelector = ref(false)
const showItemPicker = ref(false)
const addressedTo = ref<string | null>(null)

const isMyTurn = computed(
  () => gameStore.currentTurnId === charStore.myCharacter?.id,
)
const canActNow = computed(() => !gameStore.isInCombat || isMyTurn.value)

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

// Alliés à 0 PV (personnages joueurs, pas monstres) que je peux stabiliser
const downedAllies = computed(() =>
  gameStore.combatants.filter(
    (c) => c.kind === 'pc' && c.id !== charStore.myCharacter?.id && c.hp_current <= 0,
  ),
)

const attackTargets = computed(() => {
  const myId = charStore.myCharacter?.id
  return gameStore.combatants.filter((c) => c.id !== myId && c.kind === 'monster' && c.hp_current > 0)
})

const aiCompanions = computed(() =>
  charStore.sessionCharacters.filter((c) => c.is_ai),
)

const combatActions: Array<{ label: string; type: string; iconId: RpgMapIconId; tone: string }> = [
  { label: 'Attaquer', type: 'attack', iconId: 'c-atk-target', tone: 'tone-blood' },
  { label: 'Sort', type: 'cast_spell', iconId: 'c-spell-target', tone: 'tone-arcane' },
  { label: 'Objet', type: 'use_item', iconId: 'chest', tone: 'tone-gold' },
  { label: 'Déplacer', type: 'move', iconId: 'c-move-dest', tone: 'tone-teal' },
  { label: 'Dash', type: 'dash', iconId: 'c-move-tile', tone: 'tone-gold' },
  { label: 'Désengager', type: 'disengage', iconId: 'c-selection', tone: 'tone-arcane' },
  { label: 'Fin du tour', type: 'end_turn', iconId: 'c-active-turn', tone: 'tone-gold' },
]

const canSend = computed(
  () => gameStore.connected && !gameStore.isProcessing && canActNow.value,
)

const isCombatImmersive = computed(() => props.variant === 'combat-immersive')

function submitText() {
  const text = input.value.trim()
  if (!text || !canSend.value) return
  const extra = buildAddressingPayload(text)
  emit('action', 'free_text', text, undefined, extra)
  input.value = ''
  addressedTo.value = null
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
  if (!canActNow.value) return
  if (actionType === 'cast_spell') {
    emit('mapMode', 'spell')
    showSpellPanel.value = true
  } else if (actionType === 'attack') {
    emit('mapMode', 'attack')
  } else if (actionType === 'use_item') {
    showItemPicker.value = true
  } else if (actionType === 'move') {
    emit('mapMode', 'move')
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

function addressCompanion(characterId: string, name: string) {
  addressedTo.value = characterId
  const mention = `@${name} `
  if (!input.value.trim().startsWith(mention)) {
    input.value = mention + input.value.replace(/^@\S+\s*/, '')
  }
}

function buildAddressingPayload(text: string): Record<string, unknown> | undefined {
  const explicit = addressedTo.value
  if (explicit) {
    return { addressed_to: explicit, audience: 'companion' }
  }

  const normalized = text.toLocaleLowerCase()
  const mentioned = aiCompanions.value.find((c) => {
    const name = c.name.toLocaleLowerCase()
    return normalized.includes(`@${name}`) || normalized.startsWith(`${name},`) || normalized.startsWith(`${name} `)
  })
  if (mentioned) {
    return { addressed_to: mentioned.id, audience: 'companion' }
  }

  if (
    normalized.includes('compagnon') ||
    normalized.includes('votre avis') ||
    normalized.includes('que pensez') ||
    normalized.includes('on fait quoi')
  ) {
    return { audience: 'party' }
  }

  return undefined
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
    class="rpg-actionbar shrink-0 border-t"
    :class="[isCombatImmersive ? 'combat-immersive px-4 py-3' : 'px-5 py-4']"
  >
    <!-- Character context line -->
    <div
      v-if="charStore.myCharacter"
      class="mb-3 flex items-center gap-2.5"
    >
      <div
        class="rpg-avatar-player flex h-7 w-7 shrink-0 items-center justify-center rounded-md font-display text-xs font-bold"
      >{{ charStore.myCharacter.name.charAt(0).toUpperCase() }}</div>
      <span class="rpg-text-muted text-sm">
        Vous incarnez
        <strong class="rpg-text-main font-display">{{ charStore.myCharacter.name }}</strong>
        <span v-if="isMyTurn && gameStore.isInCombat" class="rpg-text-ember"> — c'est à vous de jouer</span>
        <span v-else-if="gameStore.isInCombat && activeCombatantName" class="italic"> — tour de {{ activeCombatantName }}</span>
      </span>
    </div>

    <!-- Unconscious state -->
    <div
      v-if="isDowned && isMyTurn"
      class="rpg-danger-message mb-3 rounded-lg border px-3 py-2 text-sm italic"
    >
      Vous êtes inconscient(e). Effectuez votre jet de sauvegarde contre la mort.
    </div>
    <div
      v-else-if="isDowned && !isMyTurn"
      class="rpg-danger-message is-waiting mb-3 rounded-lg border px-3 py-2 text-sm italic"
    >
      Inconscient(e) — en attente de votre tour.
    </div>

    <!-- Textarea + Envoyer -->
    <div
      v-if="!gameStore.isInCombat && aiCompanions.length > 0"
      class="mb-2 flex flex-wrap items-center gap-2"
    >
      <span class="rpg-text-muted text-[11px] font-semibold uppercase tracking-[0.14em]">Parler à</span>
      <button
        v-for="companion in aiCompanions"
        :key="companion.id"
        class="rpg-companion-chip rounded border px-2.5 py-1 text-xs font-semibold"
        :class="{ 'is-selected': addressedTo === companion.id }"
        type="button"
        @click="addressCompanion(companion.id, companion.name)"
      >@{{ companion.name }}</button>
      <button
        v-if="addressedTo"
        class="rpg-text-muted text-xs"
        type="button"
        @click="addressedTo = null"
      >Tous</button>
    </div>

    <div class="flex items-end gap-3">
      <textarea
        v-model="input"
        :rows="isCombatImmersive ? 2 : 2"
        :placeholder="gameStore.isProcessing ? 'Le Maître du Jeu répond…' : gameStore.isInCombat && !isMyTurn ? 'En attente de votre tour…' : 'Décrivez votre action, parlez, ou posez une question au MJ…'"
        :disabled="!canSend"
        class="rpg-input flex-1 resize-none font-[inherit]"
        :class="isCombatImmersive ? 'text-[13px]' : 'text-sm'"
        @keydown="onKeydown"
      />
      <button
        class="rpg-btn-primary shrink-0 self-end"
        :class="isCombatImmersive ? '!px-5 !py-2.5 !text-[12px]' : '!px-5 !py-3'"
        :disabled="!input.trim() || !canSend"
        @click="submitText"
      >{{ isCombatImmersive ? 'Lancer ↵' : 'Envoyer ↵' }}</button>
    </div>

    <!-- Action chips row (combat only) -->
    <div
      v-if="gameStore.isInCombat"
      class="mt-2.5 flex items-center gap-2 flex-wrap"
      :class="{ 'justify-between': isCombatImmersive }"
    >
      <!-- Death save -->
      <template v-if="isDowned && isMyTurn">
        <button class="rpg-btn-tonal tone-blood !py-1 !text-[11px]" :disabled="!canSend" @click="onDeathSave">
          <RpgMapIcon icon-id="c-body-down" :size="16" label="Corps à terre" />
          Jet de sauvegarde
        </button>
        <button class="rpg-btn-secondary !py-1 !text-[11px]" :disabled="!canSend" @click="emit('action', 'end_turn')">
          <RpgMapIcon icon-id="c-active-turn" :size="16" label="Fin du tour" />
          Fin du tour
        </button>
      </template>

      <!-- Combat actions -->
      <template v-else-if="!isDowned">
        <button
          v-for="action in combatActions"
          :key="action.type"
          class="rpg-btn-tonal !py-1 !text-[11px]"
          :class="[action.tone, !canActNow ? 'opacity-40 !cursor-not-allowed' : '']"
          :disabled="!canActNow || !gameStore.connected || gameStore.isProcessing"
          @click="onCombatAction(action.type)"
        >
          <RpgMapIcon
            :icon-id="action.iconId"
            :size="16"
            :state="!canActNow || !gameStore.connected || gameStore.isProcessing ? 'disabled' : 'normal'"
            :label="action.label"
          />
          {{ action.label }}
        </button>

        <template v-if="isMyTurn && downedAllies.length > 0">
          <button
            v-for="ally in downedAllies"
            :key="ally.id"
            class="rpg-btn-tonal tone-arcane !py-1 !text-[11px]"
            :disabled="!canSend"
            @click="onStabilize(ally.id)"
          >
            <RpgMapIcon icon-id="c-ally" :size="16" :label="`Stabiliser ${ally.name}`" />
            Stabiliser {{ ally.name }}
          </button>
        </template>
      </template>
    </div>
  </div>
</template>
