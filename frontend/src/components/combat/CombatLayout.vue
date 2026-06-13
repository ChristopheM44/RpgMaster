<script setup lang="ts">
/**
 * CombatLayout V2 — "Carte d'abord"
 *
 * Layout:
 *   ┌─ InitiativeTimeline (bandeau horizontal) ──────────────┐
 *   │                                                         │
 *   ├─ Main (flex, min-h-0) ──────────────────────┬─ Récit ─┤
 *   │   MAP (flex-1, position relative)            │  drawer │
 *   │   ├ overlay top (loc pill + map tools)       │  (360px)│
 *   │   ├ Battlemap lean                           │         │
 *   │   └ TokenInspector (abs overlay)             │         │
 *   │                                              │         │
 *   ├─ HotSeatBar (border-top) ────────────────────┴─────────┤
 *   └─────────────────────────────────────────────────────────┘
 */
import { computed, ref } from 'vue'
import { useGameStore } from '../../stores/game'
import { useCharacterStore } from '../../stores/character'
import { useSessionStore } from '../../stores/session'
import type { PendingSpellAim, SrdSpell } from '../../types'
import InitiativeTimeline from './InitiativeTimeline.vue'
import Battlemap from './Battlemap.vue'
import TokenInspector from './TokenInspector.vue'
import HotSeatBar from './HotSeatBar.vue'
import NarrativeLog from '../narrative/NarrativeLog.vue'

const emit = defineEmits<{
  action: [actionType: string, content?: string, targetId?: string, extra?: Record<string, unknown>]
  endCombat: []
  openSheet: [id: string]
}>()

const gameStore = useGameStore()
const charStore = useCharacterStore()
const sessionStore = useSessionStore()

const isMyTurn = computed(() => gameStore.currentTurnId === charStore.myCharacter?.id)
const speedM = computed(() => {
  const movement = gameStore.combatants.find((c) => c.id === charStore.myCharacter?.id)?.action_economy?.movement
  return movement ?? 9
})

type MapInteractionMode = 'inspect' | 'move' | 'attack' | 'spell'
const mapMode = ref<MapInteractionMode>('inspect')

/** Sort à aire en cours de visée sur la carte (gabarit AoE). */
const pendingSpell = ref<{ spellId: string; slotLevel: number; aim: PendingSpellAim } | null>(null)

const sceneLabel = computed(() => {
  const scene = gameStore.currentScene
  if (!scene) return 'Champ de bataille'
  return `${scene.cols} × ${scene.rows} cases`
})
const sceneSize = computed(() => {
  const scene = gameStore.currentScene
  if (!scene) return null
  const wM = scene.cols * scene.cell_size_m
  const hM = scene.rows * scene.cell_size_m
  return `${wM} × ${hM} m`
})

// ── Event handlers ───────────────────────────────────────────────────────────

function handleMapMove(col: number, row: number) {
  emit('action', 'move', `${col},${row}`)
  mapMode.value = 'inspect'
}

function handleMapTarget(targetId: string, mode: MapInteractionMode) {
  gameStore.setSelectedCombatant(targetId)
  if (mode === 'attack') {
    emit('action', 'attack', undefined, targetId)
    mapMode.value = 'inspect'
  }
}

function handleMapFlee(exitId: string) {
  emit('action', 'flee', exitId)
  mapMode.value = 'inspect'
}


function handleHotSeatAction(
  actionType: string,
  content?: string,
  targetId?: string,
  extra?: Record<string, unknown>,
) {
  emit('action', actionType, content, targetId, extra)
}

function handleMapMode(mode: 'inspect' | 'move' | 'attack' | 'spell') {
  mapMode.value = mode
  if (mode !== 'spell') pendingSpell.value = null
}

function handleAimSpell(spell: SrdSpell, slotLevel: number) {
  pendingSpell.value = {
    spellId: spell.id,
    slotLevel,
    aim: {
      rangeM: spell.range_m,
      shape: spell.area_shape ?? 'sphere',
      sizeM: spell.area_size_m ?? 1.5,
      origin: spell.area_origin === 'self' || spell.area_shape === 'emanation' ? 'self' : 'point',
    },
  }
  mapMode.value = 'spell'
}

function handleCastAt(col: number, row: number, targetId: string | undefined) {
  const pending = pendingSpell.value
  if (!pending) return
  emit('action', 'cast_spell', undefined, targetId, {
    spell_id: pending.spellId,
    slot_level: pending.slotLevel,
    target_cell: { col, row },
  })
  pendingSpell.value = null
  mapMode.value = 'inspect'
}

// Add ally / enemy (forward to parent via action event)
function addAlly() { emit('action', 'add_ally') }
function addEnemy() { emit('action', 'add_enemy') }
function rerollInit() { emit('action', 'reroll_initiative') }
</script>

<template>
  <!-- V2 layout, desktop only (md+) -->
  <div class="combat-v2 hidden md:flex">

    <!-- ── Initiative timeline ──────────────────────────────────────────── -->
    <InitiativeTimeline
      @add-ally="addAlly"
      @add-enemy="addEnemy"
      @reroll-init="rerollInit"
    />

    <!-- ── Middle area: Map + Récit drawer ─────────────────────────────── -->
    <div class="combat-middle">

      <!-- MAP section -->
      <section class="combat-map">

        <!-- Overlay top bar (location pill + map tools) -->
        <div class="map-overlay-top">
          <!-- Location pill -->
          <div class="location-pill">
            <span class="location-pill-icon">✦</span>
            <span class="location-pill-name">{{ sceneLabel }}</span>
            <span class="location-pill-sep">·</span>
            <span class="location-pill-size">{{ sceneSize ?? '—' }}</span>
          </div>

          <div style="flex: 1" />

          <!-- Map tools -->
          <div class="map-tools">
            <button
              class="map-tool"
              :class="{ active: mapMode === 'move' }"
              title="Déplacer"
              @click="mapMode = mapMode === 'move' ? 'inspect' : 'move'"
            >✥ Déplacer</button>
            <button class="map-tool" title="Mesurer">📏 Mesurer</button>
            <button
              class="map-tool"
              title="Annuler le mode"
              v-if="mapMode !== 'inspect'"
              style="color: var(--color-gold)"
              @click="mapMode = 'inspect'"
            >✕ Annuler</button>
          </div>
        </div>

        <!-- Battlemap (lean — no internal header/side panel) -->
        <Battlemap
          variant="lean"
          :my-character-id="charStore.myCharacter?.id"
          :is-my-turn="isMyTurn"
          :speed-m="speedM"
          :interaction-mode="mapMode"
          :pending-spell="pendingSpell?.aim ?? null"
          @move="handleMapMove"
          @target="handleMapTarget"
          @mode-change="handleMapMode"
          @flee="handleMapFlee"
          @cast-at="handleCastAt"
        />

        <!-- Token inspector (absolute overlay, top-right) -->
        <TokenInspector
          @target="(id) => emit('action', 'attack', undefined, id)"
          @approach="(id) => emit('action', 'move_to', undefined, id)"
          @open-sheet="(id) => emit('openSheet', id)"
        />

        <!-- Récit re-open tab (visible only when drawer is closed) -->
        <Transition name="recit-tab">
          <button
            v-if="!sessionStore.recitOpen"
            class="recit-reopen-tab"
            @click="sessionStore.recitOpen = true"
          >◀ Récit</button>
        </Transition>
      </section>

      <!-- Récit drawer -->
      <Transition name="recit-drawer">
        <aside v-if="sessionStore.recitOpen" class="recit-drawer">
          <NarrativeLog variant="drawer" />
        </aside>
      </Transition>
    </div>

    <!-- ── Hot-seat bar ─────────────────────────────────────────────────── -->
    <HotSeatBar
      @action="handleHotSeatAction"
      @map-mode="handleMapMode"
      @aim-spell="handleAimSpell"
    />
  </div>
</template>

<style scoped>
/* ── Outer shell ──────────────────────────────────────────────────────────── */
.combat-v2 {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  flex-direction: column;
}

/* ── Middle row (map + récit) ─────────────────────────────────────────────── */
.combat-middle {
  flex: 1;
  display: flex;
  min-height: 0;
  position: relative;
  z-index: 1;
  overflow: hidden;
}

/* ── Map section ──────────────────────────────────────────────────────────── */
.combat-map {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  position: relative;
  overflow: hidden;
}

/* Overlay top bar */
.map-overlay-top {
  position: absolute;
  top: 16px;
  left: 20px;
  right: 20px;
  display: flex;
  align-items: center;
  gap: 10px;
  z-index: 5;
  pointer-events: none;
}

.location-pill {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: rgba(14, 13, 20, 0.7);
  backdrop-filter: blur(8px);
  border: 1px solid var(--color-border);
  border-radius: 999px;
  pointer-events: auto;
  flex-shrink: 0;
}

.location-pill-icon {
  color: var(--color-ember);
  font-size: 11px;
}

.location-pill-name {
  font-family: var(--font-display);
  font-size: 11px;
  font-weight: 700;
  color: var(--color-parchment);
  letter-spacing: 2px;
  text-transform: uppercase;
}

.location-pill-sep {
  color: var(--color-text-dim);
}

.location-pill-size {
  font-size: 10px;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
}

.map-tools {
  display: flex;
  gap: 4px;
  pointer-events: auto;
}

.map-tool {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 5px 9px;
  background: rgba(14, 13, 20, 0.7);
  backdrop-filter: blur(8px);
  border: 1px solid var(--color-border);
  border-radius: 5px;
  color: var(--color-text-muted);
  font-size: 10px;
  font-weight: 600;
  cursor: pointer;
  transition: color 120ms ease, border-color 120ms ease;
}

.map-tool:hover {
  color: var(--color-parchment);
  border-color: var(--color-border-strong);
}

.map-tool.active {
  color: var(--color-teal);
  border-color: rgba(79, 216, 192, 0.4);
  background: rgba(79, 216, 192, 0.08);
}

/* Récit re-open tab (vertical button on right edge) */
.recit-reopen-tab {
  position: absolute;
  top: 50%;
  right: 0;
  transform: translateY(-50%);
  padding: 14px 6px;
  background: var(--color-bg-elev);
  border: 1px solid var(--color-border);
  border-right: none;
  border-radius: 8px 0 0 8px;
  color: var(--color-gold);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  cursor: pointer;
  writing-mode: vertical-rl;
  display: flex;
  align-items: center;
  gap: 6px;
  z-index: 4;
  transition: background 120ms ease;
}

.recit-reopen-tab:hover {
  background: var(--color-surface);
}

/* ── Récit drawer ─────────────────────────────────────────────────────────── */
.recit-drawer {
  width: 360px;
  display: flex;
  flex-direction: column;
  border-left: 1px solid var(--color-border);
  background: var(--color-bg-elev);
  flex-shrink: 0;
  min-height: 0;
  overflow: hidden;
}

/* Récit drawer slide transition */
.recit-drawer-enter-active,
.recit-drawer-leave-active {
  transition: width 200ms ease, opacity 200ms ease;
  overflow: hidden;
}

.recit-drawer-enter-from,
.recit-drawer-leave-to {
  width: 0;
  opacity: 0;
}

/* Récit tab fade */
.recit-tab-enter-active,
.recit-tab-leave-active {
  transition: opacity 150ms ease;
}

.recit-tab-enter-from,
.recit-tab-leave-to {
  opacity: 0;
}
</style>
