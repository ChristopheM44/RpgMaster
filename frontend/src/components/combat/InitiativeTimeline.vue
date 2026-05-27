<script setup lang="ts">
import { computed } from 'vue'
import { useGameStore } from '../../stores/game'
import { useCharacterStore } from '../../stores/character'
import { toneForCombatant, hpColor } from '../../utils/combatUtils'
import type { CombatantState } from '../../types'

const gameStore = useGameStore()
const charStore = useCharacterStore()

const myCharId = computed(() => charStore.myCharacter?.id ?? null)
const combatants = computed(() => gameStore.combatants)
const activeId = computed(() => gameStore.currentTurnId)
const selectedId = computed(() => gameStore.selectedCombatantId)
const roundNumber = computed(() => gameStore.roundNumber)

function selectUnit(unit: CombatantState) {
  gameStore.setSelectedCombatant(unit.id === selectedId.value ? null : unit.id)
}

function toneColorVar(unit: CombatantState): string {
  return `var(--color-${toneForCombatant(unit, myCharId.value)})`
}

const emit = defineEmits<{
  addAlly: []
  addEnemy: []
  rerollInit: []
}>()
</script>

<template>
  <div class="initiative-timeline">
    <!-- Round counter -->
    <div class="round-counter">
      <span class="round-label">Round {{ roundNumber || 1 }}</span>
      <span class="round-sub">{{ combatants.length }} combattants</span>
    </div>

    <!-- Timeline chips -->
    <div class="chips-scroll">
      <template v-for="(unit, index) in combatants" :key="unit.id">
        <button
          class="init-chip"
          :class="{
            active: unit.id === activeId,
            selected: unit.id === selectedId,
            defeated: unit.conditions?.includes('defeated'),
          }"
          @click="selectUnit(unit)"
          :title="unit.name"
        >
          <!-- Initiative badge -->
          <span
            class="init-badge"
            :class="{ 'init-badge--active': unit.id === activeId }"
          >{{ unit.initiative ?? '?' }}</span>

          <!-- Avatar -->
          <div
            class="chip-avatar"
            :style="{
              background: unit.kind === 'pc'
                ? `linear-gradient(135deg, ${toneColorVar(unit)}, color-mix(in srgb, ${toneColorVar(unit)} 60%, transparent))`
                : `radial-gradient(circle at 30% 30%, ${toneColorVar(unit)}, #20141a)`,
              border: `1.5px solid ${unit.kind === 'pc' ? (unit.id === myCharId ? 'var(--color-gold)' : 'rgba(247,236,208,0.4)') : 'rgba(0,0,0,0.6)'}`,
            }"
          >
            {{ unit.token ?? unit.name.charAt(0).toUpperCase() }}
          </div>

          <!-- Name + HP row -->
          <div class="chip-info">
            <div class="chip-name-row">
              <span class="chip-name">{{ unit.name }}</span>
              <span v-if="unit.id === myCharId" class="chip-badge chip-badge--vous">VOUS</span>
              <span v-else-if="unit.is_ai || unit.is_ai_controlled" class="chip-badge chip-badge--ia">IA</span>
            </div>
            <div class="chip-hp-row">
              <div class="chip-hp-track">
                <div
                  class="chip-hp-fill"
                  :style="{
                    width: unit.hp_max > 0 ? `${(unit.hp_current / unit.hp_max) * 100}%` : '0%',
                    background: hpColor(unit.hp_current, unit.hp_max),
                  }"
                />
              </div>
              <span class="chip-hp-text">{{ unit.hp_current }}/{{ unit.hp_max }}</span>
            </div>
          </div>
        </button>

        <!-- Separator arrow (not after last) -->
        <span v-if="index < combatants.length - 1" class="chip-separator">›</span>
      </template>
    </div>

    <!-- Management buttons -->
    <div class="timeline-actions">
      <button class="timeline-btn timeline-btn--ally" @click="emit('addAlly')">+ Allié</button>
      <button class="timeline-btn timeline-btn--enemy" @click="emit('addEnemy')">+ Ennemi</button>
      <button class="timeline-btn timeline-btn--init" @click="emit('rerollInit')">↻ Init.</button>
    </div>
  </div>
</template>

<style scoped>
.initiative-timeline {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 20px;
  min-height: 72px;
  border-bottom: 1px solid var(--color-border);
  background: linear-gradient(180deg, var(--color-bg-elev), rgba(24, 22, 35, 0.6));
  overflow: visible;
}

/* Round counter */
.round-counter {
  display: flex;
  flex-direction: column;
  gap: 1px;
  padding-right: 8px;
  border-right: 1px solid var(--color-border);
  flex-shrink: 0;
}

.round-label {
  font-family: var(--font-display);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--color-gold);
  white-space: nowrap;
}

.round-sub {
  font-size: 8px;
  color: var(--color-text-dim);
  font-family: var(--font-serif);
  font-style: italic;
}

/* Scrollable chip row */
.chips-scroll {
  display: flex;
  align-items: center;
  gap: 4px;
  overflow-x: auto;
  flex: 1;
  scrollbar-width: none;
  min-width: 0;
  /* Padding pour éviter le clipping du badge positionné à top:-5px */
  padding-top: 8px;
  padding-bottom: 8px;
}

.chips-scroll::-webkit-scrollbar {
  display: none;
}

.chip-separator {
  color: var(--color-text-dim);
  font-size: 10px;
  flex-shrink: 0;
  pointer-events: none;
}

/* Individual chip */
.init-chip {
  position: relative;
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 4px 10px 4px 4px;
  background: transparent;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  cursor: pointer;
  flex-shrink: 0;
  transition: background 120ms ease, border-color 120ms ease, box-shadow 120ms ease;
}

.init-chip:hover {
  background: rgba(247, 236, 208, 0.05);
  border-color: var(--color-border-strong);
}

.init-chip.selected {
  background: rgba(247, 236, 208, 0.07);
  border-color: var(--color-border-strong);
}

.init-chip.active {
  padding: 5px 11px 5px 5px;
  background: linear-gradient(90deg, rgba(240, 199, 100, 0.22), rgba(240, 199, 100, 0.04));
  border-color: var(--color-gold);
  box-shadow: 0 0 14px rgba(240, 199, 100, 0.18);
}

.init-chip.defeated {
  opacity: 0.4;
}

/* Initiative number badge */
.init-badge {
  position: absolute;
  top: -5px;
  left: -5px;
  background: var(--color-bg-elev);
  color: var(--color-text-muted);
  font-size: 8px;
  font-weight: 700;
  font-family: var(--font-mono);
  padding: 1px 4px;
  border-radius: 999px;
  border: 1px solid var(--color-border-strong);
  line-height: 1;
  min-width: 14px;
  text-align: center;
  pointer-events: none;
  z-index: 1;
}

.init-badge--active {
  background: var(--color-gold);
  color: var(--color-bg);
  border-color: var(--color-gold);
}

/* Circular avatar */
.chip-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 10px;
  color: var(--color-bg);
  flex-shrink: 0;
}

/* Text block */
.chip-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.chip-name-row {
  display: flex;
  align-items: center;
  gap: 4px;
}

.chip-name {
  font-family: var(--font-display);
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-muted);
  line-height: 1;
  white-space: nowrap;
}

.init-chip.active .chip-name {
  color: var(--color-parchment);
}

.chip-badge {
  font-size: 7px;
  font-weight: 700;
  letter-spacing: 0.5px;
  line-height: 1;
}

.chip-badge--vous { color: var(--color-gold); }
.chip-badge--ia   { color: var(--color-arcane); }

/* HP mini-bar */
.chip-hp-row {
  display: flex;
  align-items: center;
  gap: 4px;
}

.chip-hp-track {
  width: 36px;
  height: 3px;
  border-radius: 2px;
  background: rgba(0, 0, 0, 0.5);
  overflow: hidden;
  flex-shrink: 0;
}

.chip-hp-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 300ms ease;
}

.chip-hp-text {
  font-size: 8px;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  white-space: nowrap;
}

/* Timeline action buttons */
.timeline-actions {
  display: flex;
  gap: 4px;
  padding-left: 8px;
  border-left: 1px solid var(--color-border);
  flex-shrink: 0;
}

.timeline-btn {
  padding: 6px 10px;
  border-radius: 5px;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  cursor: pointer;
  white-space: nowrap;
  transition: opacity 120ms ease;
}

.timeline-btn:hover {
  opacity: 0.8;
}

.timeline-btn--ally {
  background: rgba(79, 216, 192, 0.08);
  border: 1px solid rgba(79, 216, 192, 0.25);
  color: var(--color-teal);
}

.timeline-btn--enemy {
  background: rgba(232, 69, 69, 0.08);
  border: 1px solid rgba(232, 69, 69, 0.25);
  color: var(--color-blood);
}

.timeline-btn--init {
  background: rgba(240, 199, 100, 0.08);
  border: 1px solid rgba(240, 199, 100, 0.25);
  color: var(--color-gold);
}
</style>
