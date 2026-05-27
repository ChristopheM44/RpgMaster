<script setup lang="ts">
/**
 * HotSeatBar — V2 combat bottom bar.
 * Shows player identity, stats, action economy and action chips.
 * Emits the same `action` / `mapMode` events as ActionBar so the
 * parent CombatLayout can wire them identically.
 */
import { ref, computed } from 'vue'
import { useGameStore } from '../../stores/game'
import { useCharacterStore } from '../../stores/character'
import SpellCastPanel from '../ui/SpellCastPanel.vue'
import RpgMapIcon from '../common/RpgMapIcon.vue'
import { hpColor } from '../../utils/combatUtils'
import type { RpgMapIconId } from '../../icons/rpgMapIcons'

const emit = defineEmits<{
  action: [actionType: string, content?: string, targetId?: string, extra?: Record<string, unknown>]
  mapMode: [mode: 'inspect' | 'move' | 'attack' | 'spell']
}>()

const gameStore = useGameStore()
const charStore = useCharacterStore()

const input = ref('')
const showSpellPanel = ref(false)
const showItemPicker = ref(false)
const showTargetSelector = ref(false)

// ── Computed ────────────────────────────────────────────────────────────────

const me = computed(() => charStore.myCharacter)

/** Combatant entry for the human player (action_economy lives here). */
const myCombatant = computed(
  () => gameStore.combatants.find((c) => c.id === me.value?.id) ?? null,
)

const isMyTurn = computed(
  () => gameStore.currentTurnId === me.value?.id,
)

const canActNow = computed(() => !gameStore.isInCombat || isMyTurn.value)

const canSend = computed(
  () => gameStore.connected && !gameStore.isProcessing && canActNow.value,
)

const isDowned = computed(
  () =>
    myCombatant.value !== null &&
    myCombatant.value.hp_current <= 0 &&
    !myCombatant.value.death_saves?.stable,
)

const downedAllies = computed(() =>
  gameStore.combatants.filter(
    (c) => c.kind === 'pc' && c.id !== me.value?.id && c.hp_current <= 0,
  ),
)

const attackTargets = computed(() =>
  gameStore.combatants.filter(
    (c) => c.id !== me.value?.id && c.kind === 'monster' && c.hp_current > 0,
  ),
)

const combatItems = computed(() => {
  const equipment = me.value?.equipment as Record<string, unknown>[] | undefined
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

const hpCur = computed(() => myCombatant.value?.hp_current ?? me.value?.hp_current ?? 0)
const hpMax = computed(() => myCombatant.value?.hp_max ?? me.value?.hp_max ?? 1)
const hpRatio = computed(() => hpMax.value > 0 ? hpCur.value / hpMax.value : 0)
const hpBarColor = computed(() => hpColor(hpCur.value, hpMax.value))

const movLeft = computed(() => myCombatant.value?.action_economy?.movement ?? null)
const movMax  = computed(() => myCombatant.value?.action_economy?.movement_max ?? myCombatant.value?.speed_m ?? null)

const actionEconomy = computed(() => myCombatant.value?.action_economy ?? null)

const activeCombatantName = computed(() => {
  const c = gameStore.combatants.find((c) => c.id === gameStore.currentTurnId)
  return c?.name ?? null
})

// ── Chip definitions ─────────────────────────────────────────────────────────

const combatActions: Array<{ label: string; type: string; iconId: RpgMapIconId; tone: string }> = [
  { label: 'Attaquer',    type: 'attack',     iconId: 'c-atk-target',  tone: 'tone-blood'  },
  { label: 'Sort',        type: 'cast_spell', iconId: 'c-spell-target', tone: 'tone-arcane' },
  { label: 'Objet',       type: 'use_item',   iconId: 'chest',          tone: 'tone-gold'   },
  { label: 'Déplacer',    type: 'move',       iconId: 'c-move-dest',    tone: 'tone-teal'   },
  { label: 'Dash',        type: 'dash',       iconId: 'c-move-tile',    tone: 'tone-gold'   },
  { label: 'Désengager',  type: 'disengage',  iconId: 'c-selection',    tone: 'tone-arcane' },
]

// ── Handlers ─────────────────────────────────────────────────────────────────

function onCombatAction(type: string) {
  if (!canActNow.value) return
  if (type === 'cast_spell') {
    emit('mapMode', 'spell')
    showSpellPanel.value = true
  } else if (type === 'attack') {
    emit('mapMode', 'attack')
    showTargetSelector.value = true
  } else if (type === 'use_item') {
    showItemPicker.value = true
  } else if (type === 'move') {
    emit('mapMode', 'move')
  } else {
    emit('action', type)
  }
}

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

function onSpellConfirm(spellId: string, slotLevel: number, targetId: string | undefined) {
  showSpellPanel.value = false
  emit('action', 'cast_spell', undefined, targetId, { spell_id: spellId, slot_level: slotLevel })
}

function confirmAttackTarget(targetId: string) {
  showTargetSelector.value = false
  emit('action', 'attack', undefined, targetId)
}

function onItemAction(item: Record<string, unknown>, actionType: 'use_item' | 'equip') {
  showItemPicker.value = false
  emit('action', actionType, undefined, undefined, { item_id: item.id as string })
}
</script>

<template>
  <!-- Overlays -->
  <SpellCastPanel v-if="showSpellPanel" @confirm="onSpellConfirm" @cancel="showSpellPanel = false" />

  <div v-if="showItemPicker" class="fixed inset-0 z-40 flex items-end justify-center bg-black/60" @click.self="showItemPicker = false">
    <div class="rpg-card w-full max-w-md rounded-t-xl p-4 shadow-xl">
      <p class="mb-3 text-sm font-semibold text-parchment/70">Utiliser ou équiper un objet :</p>
      <div class="space-y-1.5 max-h-60 overflow-y-auto">
        <div v-for="(item, idx) in combatItems" :key="idx" class="flex items-center gap-2 rounded border border-parchment/10 px-3 py-2">
          <span class="flex-1 text-sm capitalize text-parchment">
            {{ String(item.name_fr ?? item.id ?? 'Objet') }}
            <span v-if="item.equipped" class="ml-1 text-xs text-gold/60">(équipé)</span>
          </span>
          <button v-if="String(item.id ?? '').toLowerCase().includes('potion') || String(item.name_fr ?? '').toLowerCase().includes('potion')" class="rpg-btn-tonal tone-arcane" @click="onItemAction(item, 'use_item')">Utiliser</button>
          <button v-else class="rpg-btn-tonal tone-gold" @click="onItemAction(item, 'equip')">{{ item.equipped ? 'Retirer' : 'Équiper' }}</button>
        </div>
        <p v-if="combatItems.length === 0" class="py-2 text-center text-sm text-parchment/40">Aucun objet disponible</p>
      </div>
      <button class="rpg-btn-secondary mt-3 w-full justify-center" @click="showItemPicker = false">Annuler</button>
    </div>
  </div>

  <div v-if="showTargetSelector" class="fixed inset-0 z-40 flex items-end justify-center bg-black/60" @click.self="showTargetSelector = false">
    <div class="rpg-card w-full max-w-md rounded-t-xl p-4 shadow-xl">
      <p class="mb-3 text-sm font-semibold text-parchment/70">Choisissez une cible :</p>
      <div class="space-y-2">
        <button v-for="target in attackTargets" :key="target.id" class="rpg-btn-tonal tone-blood w-full text-left" @click="confirmAttackTarget(target.id)">
          <span class="font-medium text-parchment text-sm">{{ target.name }}</span>
          <span class="ml-2 text-xs text-parchment/40">PV {{ target.hp_current }}/{{ target.hp_max }}</span>
        </button>
        <p v-if="attackTargets.length === 0" class="py-2 text-center text-sm text-parchment/40">Aucune cible disponible</p>
      </div>
      <button class="rpg-btn-secondary mt-3 w-full justify-center" @click="showTargetSelector = false">Annuler</button>
    </div>
  </div>

  <!-- Main bar -->
  <div v-if="me" class="hotseat">

    <!-- Identity block -->
    <div class="hs-identity">
      <div class="hs-avatar">{{ me.name.charAt(0).toUpperCase() }}</div>
      <div class="hs-id-text">
        <div class="hs-turn-label">
          <span v-if="isMyTurn" class="hs-turn-label--active">◆ Votre tour</span>
          <span v-else>⏳ Tour de {{ activeCombatantName ?? '...' }}</span>
        </div>
        <div class="hs-name">{{ me.name }}</div>
        <div class="hs-sub">Niv.{{ me.level }} · {{ me.species }} · {{ me.char_class }}</div>
      </div>
    </div>

    <!-- Stats -->
    <div class="hs-stats">
      <!-- HP with mini bar -->
      <div class="hs-stat-hp">
        <div class="hs-stat-row">
          <span class="hs-stat-label">PV</span>
          <span class="hs-stat-val" :style="{ color: hpBarColor }">{{ hpCur }}/{{ hpMax }}</span>
        </div>
        <div class="hs-hp-track">
          <div class="hs-hp-fill" :style="{ width: `${hpRatio * 100}%`, background: hpBarColor }" />
        </div>
      </div>

      <div class="hs-stat-box">
        <span class="hs-stat-label">CA</span>
        <span class="hs-stat-val" style="color: var(--color-teal)">{{ myCombatant?.ac ?? '—' }}</span>
      </div>

      <div class="hs-stat-box">
        <span class="hs-stat-label">Init.</span>
        <span class="hs-stat-val" style="color: var(--color-gold)">{{ myCombatant?.initiative ?? '—' }}</span>
      </div>
    </div>

    <!-- Action economy -->
    <div class="hs-economy">
      <div class="hs-economy-title">
        Économie ·
        <span v-if="movLeft !== null && movMax !== null" style="color: var(--color-teal); font-family: var(--font-mono)">
          {{ movLeft }}/{{ movMax }} m
        </span>
        <span v-else-if="myCombatant?.speed_m" style="color: var(--color-teal); font-family: var(--font-mono)">
          {{ myCombatant.speed_m }} m
        </span>
      </div>
      <div class="hs-pips">
        <div class="hs-pip" :class="{ 'hs-pip--used': actionEconomy && !actionEconomy.action }" title="Action">A</div>
        <div class="hs-pip" :class="{ 'hs-pip--used': actionEconomy && !actionEconomy.bonus_action }" title="Action bonus">B</div>
        <div class="hs-pip" :class="{ 'hs-pip--used': actionEconomy && !actionEconomy.reaction }" title="Réaction">R</div>
      </div>
    </div>

    <!-- Action chips -->
    <div class="hs-actions">
      <div class="hs-actions-title">Actions</div>
      <div class="hs-chips">
        <!-- Death save state -->
        <template v-if="isDowned && isMyTurn">
          <button class="rpg-btn-tonal tone-blood !py-1 !text-[11px]" :disabled="!canSend" @click="emit('action', 'death_save')">
            <RpgMapIcon icon-id="c-body-down" :size="16" label="Corps à terre" />
            Jet de sauvegarde
          </button>
          <button class="rpg-btn-secondary !py-1 !text-[11px]" :disabled="!canSend" @click="emit('action', 'end_turn')">
            Fin du tour
          </button>
        </template>

        <!-- Normal combat actions -->
        <template v-else-if="!isDowned">
          <button
            v-for="action in combatActions"
            :key="action.type"
            class="rpg-btn-tonal !py-1 !text-[11px]"
            :class="[action.tone, !canActNow ? 'opacity-40 !cursor-not-allowed' : '']"
            :disabled="!canActNow || !gameStore.connected || gameStore.isProcessing"
            @click="onCombatAction(action.type)"
          >
            <RpgMapIcon :icon-id="action.iconId" :size="16" :state="!canActNow ? 'disabled' : 'normal'" :label="action.label" />
            {{ action.label }}
          </button>

          <button
            v-for="ally in downedAllies"
            :key="ally.id"
            class="rpg-btn-tonal tone-arcane !py-1 !text-[11px]"
            :disabled="!canSend"
            @click="emit('action', 'stabilize', undefined, ally.id)"
          >
            <RpgMapIcon icon-id="c-ally" :size="16" :label="`Stabiliser ${ally.name}`" />
            Stabiliser {{ ally.name }}
          </button>
        </template>
      </div>
    </div>

    <!-- Composer + end turn -->
    <div class="hs-composer">
      <textarea
        v-model="input"
        rows="2"
        placeholder="Décrivez votre action ou parlez au MJ…"
        :disabled="!canSend"
        class="rpg-input w-full resize-none text-[13px]"
        @keydown="onKeydown"
      />
      <div class="hs-composer-btns">
        <button
          class="rpg-btn-primary flex-1 !py-2 !text-[11px]"
          :disabled="!input.trim() || !canSend"
          @click="submitText"
        >Lancer ↵</button>
        <button
          class="rpg-btn-tonal tone-gold !py-2 !text-[11px] whitespace-nowrap"
          :disabled="!canActNow || !gameStore.connected || gameStore.isProcessing"
          @click="emit('action', 'end_turn')"
        >⏭ Fin tour</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.hotseat {
  flex-shrink: 0;
  display: flex;
  align-items: stretch;
  gap: 14px;
  padding: 12px 20px;
  border-top: 1px solid var(--color-border-strong);
  background: linear-gradient(180deg, var(--color-bg-elev), var(--color-bg));
  box-shadow: 0 -8px 24px rgba(0, 0, 0, 0.4);
}

/* Identity */
.hs-identity {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-right: 14px;
  border-right: 1px solid var(--color-border);
  flex-shrink: 0;
}

.hs-avatar {
  width: 44px;
  height: 44px;
  border-radius: 8px;
  background: var(--grad-primary);
  color: var(--color-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 700;
  box-shadow: 0 0 18px rgba(255, 130, 71, 0.4);
  flex-shrink: 0;
}

.hs-id-text {
  display: flex;
  flex-direction: column;
  gap: 1px;
  line-height: 1.15;
}

.hs-turn-label {
  font-size: 8px;
  font-weight: 700;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: var(--color-text-muted);
}

.hs-turn-label--active {
  color: var(--color-gold);
}

.hs-name {
  font-family: var(--font-display);
  font-size: 15px;
  font-weight: 700;
  color: var(--color-parchment);
}

.hs-sub {
  font-size: 10px;
  color: var(--color-text-muted);
}

/* Stats */
.hs-stats {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.hs-stat-hp {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 5px 10px;
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid rgba(111, 217, 111, 0.2);
  border-radius: 6px;
  min-width: 72px;
}

.hs-stat-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 6px;
}

.hs-hp-track {
  height: 3px;
  border-radius: 2px;
  background: rgba(0, 0, 0, 0.5);
  overflow: hidden;
}

.hs-hp-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 300ms ease;
}

.hs-stat-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 5px 10px;
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid var(--color-border-strong);
  border-radius: 6px;
  min-width: 48px;
}

.hs-stat-label {
  font-size: 8px;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  color: var(--color-text-dim);
}

.hs-stat-val {
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 700;
}

/* Action economy */
.hs-economy {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 5px;
  padding: 0 14px;
  border-left: 1px solid var(--color-border);
  border-right: 1px solid var(--color-border);
  flex-shrink: 0;
}

.hs-economy-title {
  font-size: 8px;
  font-weight: 700;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: var(--color-text-muted);
  white-space: nowrap;
}

.hs-pips {
  display: flex;
  gap: 4px;
}

.hs-pip {
  width: 26px;
  height: 26px;
  border-radius: 5px;
  background: rgba(240, 199, 100, 0.15);
  border: 1px solid rgba(240, 199, 100, 0.4);
  color: var(--color-gold);
  font-size: 9px;
  font-weight: 700;
  font-family: var(--font-mono);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: opacity 120ms, background 120ms;
}

.hs-pip--used {
  background: rgba(0, 0, 0, 0.2);
  border-color: var(--color-border);
  color: var(--color-text-dim);
  opacity: 0.35;
}

/* Actions area */
.hs-actions {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 5px;
  min-width: 0;
}

.hs-actions-title {
  font-size: 8px;
  font-weight: 700;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: var(--color-text-muted);
}

.hs-chips {
  display: flex;
  gap: 5px;
  flex-wrap: wrap;
}

/* Composer */
.hs-composer {
  width: 270px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  justify-content: center;
  padding-left: 14px;
  border-left: 1px solid var(--color-border);
  flex-shrink: 0;
}

.hs-composer-btns {
  display: flex;
  gap: 5px;
}
</style>
