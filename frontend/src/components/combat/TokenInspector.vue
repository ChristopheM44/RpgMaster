<script setup lang="ts">
import { computed } from 'vue'
import { useGameStore } from '../../stores/game'
import { useCharacterStore } from '../../stores/character'
import { toneForCombatant, hpColor } from '../../utils/combatUtils'
import type { CombatantState } from '../../types'

const gameStore = useGameStore()
const charStore = useCharacterStore()

const myCharId = computed(() => charStore.myCharacter?.id ?? null)

const unit = computed<CombatantState | null>(() => {
  const id = gameStore.selectedCombatantId
  if (!id) return null
  return gameStore.combatants.find((c) => c.id === id) ?? null
})

const tone = computed(() => {
  if (!unit.value) return 'blood'
  return toneForCombatant(unit.value, myCharId.value)
})

const toneColor = computed(() => `var(--color-${tone.value})`)

const isPC = computed(() => unit.value?.kind === 'pc')
const isMe = computed(() => unit.value?.id === myCharId.value)

const roleLabel = computed(() => {
  if (!unit.value) return ''
  if (isMe.value) return 'Vous'
  if (isPC.value) {
    if (unit.value.is_ai || unit.value.is_ai_controlled) return 'Allié IA'
    return 'Allié'
  }
  return 'Ennemi'
})

const subtitle = computed(() => {
  if (!unit.value) return ''
  if (isPC.value) {
    const parts = []
    if (unit.value.species) parts.push(unit.value.species)
    return parts.join(' · ')
  }
  return unit.value.cr != null ? `FP ${unit.value.cr}` : ''
})

const hpRatio = computed(() => {
  if (!unit.value || unit.value.hp_max === 0) return 0
  return unit.value.hp_current / unit.value.hp_max
})

const hpBarColor = computed(() =>
  unit.value ? hpColor(unit.value.hp_current, unit.value.hp_max) : 'var(--color-blood)',
)

const movementLeft = computed(() => {
  const ae = unit.value?.action_economy
  if (!ae) return null
  return ae.movement
})

const movementMax = computed(() => unit.value?.action_economy?.movement_max ?? unit.value?.speed_m ?? null)

function close() {
  gameStore.setSelectedCombatant(null)
}

const emit = defineEmits<{
  target: [id: string]
  approach: [id: string]
  openSheet: [id: string]
}>()
</script>

<template>
  <Transition name="inspector-slide">
    <div
      v-if="unit"
      class="inspector"
      :style="{ '--tone': toneColor }"
    >
      <!-- Close -->
      <button class="inspector-close" @click="close" title="Fermer">✕</button>

      <!-- Header: avatar + identity -->
      <div class="inspector-header">
        <div
          class="inspector-avatar"
          :style="{
            background: isPC
              ? `linear-gradient(135deg, ${toneColor}, color-mix(in srgb, ${toneColor} 60%, transparent))`
              : `radial-gradient(circle at 30% 30%, ${toneColor}, #20141a)`,
            border: `2px solid ${isPC ? 'var(--color-gold)' : 'rgba(0,0,0,0.6)'}`,
            color: isPC ? 'var(--color-bg)' : 'var(--color-parchment)',
          }"
        >
          {{ unit.token ?? unit.name.charAt(0).toUpperCase() }}
        </div>
        <div class="inspector-identity">
          <div class="inspector-role" :style="{ color: toneColor }">
            {{ roleLabel }}
            <span v-if="unit.position" style="color: var(--color-text-dim)"> · {{ unit.position.col }},{{ unit.position.row }}</span>
          </div>
          <div class="inspector-name">{{ unit.name }}</div>
          <div class="inspector-subtitle">{{ subtitle }}</div>
        </div>
      </div>

      <!-- Stats row -->
      <div class="inspector-stats">
        <div class="stat-box" :style="{ '--sc': hpBarColor }">
          <span class="stat-label">PV</span>
          <span class="stat-value" :style="{ color: hpBarColor }">
            {{ unit.hp_current }}/{{ unit.hp_max }}
          </span>
        </div>
        <div class="stat-box" style="--sc: var(--color-teal)">
          <span class="stat-label">CA</span>
          <span class="stat-value" style="color: var(--color-teal)">{{ unit.ac }}</span>
        </div>
        <div class="stat-box" style="--sc: var(--color-gold)">
          <span class="stat-label">Init.</span>
          <span class="stat-value" style="color: var(--color-gold)">{{ unit.initiative }}</span>
        </div>
      </div>

      <!-- HP bar -->
      <div class="hp-track">
        <div
          class="hp-fill"
          :style="{
            width: `${hpRatio * 100}%`,
            background: hpBarColor,
            boxShadow: `0 0 6px ${hpBarColor}80`,
          }"
        />
      </div>

      <!-- Tactical info grid -->
      <div class="inspector-tactical">
        <div class="tac-row">
          <span class="tac-key">Dépl.</span>
          <span class="tac-val" style="color: var(--color-teal)">
            <template v-if="movementLeft !== null && movementMax !== null">
              {{ movementLeft }}/{{ movementMax }} m
            </template>
            <template v-else-if="unit.speed_m != null">
              {{ unit.speed_m }} m
            </template>
            <template v-else>—</template>
          </span>
        </div>
        <div class="tac-row">
          <span class="tac-key">Portée</span>
          <span class="tac-val" style="color: var(--color-gold)">
            {{ unit.reach_m ?? '1.5' }} m
          </span>
        </div>
        <div class="tac-row">
          <span class="tac-key">État</span>
          <span class="tac-val">
            <template v-if="unit.conditions.length">
              {{ unit.conditions.join(', ') }}
            </template>
            <template v-else>—</template>
          </span>
        </div>
        <div class="tac-row">
          <span class="tac-key">Statut</span>
          <span class="tac-val">{{ unit.status ?? 'actif' }}</span>
        </div>
      </div>

      <!-- Action economy pips (if available) -->
      <div v-if="unit.action_economy" class="economy-row">
        <div class="economy-label">Économie</div>
        <div class="pips">
          <div class="pip" :class="{ 'pip--used': !unit.action_economy.action }" title="Action">A</div>
          <div class="pip" :class="{ 'pip--used': !unit.action_economy.bonus_action }" title="Action bonus">B</div>
          <div class="pip" :class="{ 'pip--used': !unit.action_economy.reaction }" title="Réaction">R</div>
        </div>
      </div>

      <!-- Inspector CTA buttons -->
      <div class="inspector-actions">
        <button
          v-if="!isPC"
          class="inspector-btn inspector-btn--primary"
          :style="{ background: `linear-gradient(135deg, var(--color-blood), rgba(232,69,69,0.7))` }"
          @click="emit('target', unit!.id)"
        >⚔ Cibler</button>

        <button
          v-if="isPC && !isMe"
          class="inspector-btn inspector-btn--primary"
          :style="{ background: `linear-gradient(135deg, var(--color-green), rgba(111,217,111,0.7))` }"
          @click="emit('target', unit!.id)"
        >✦ Soigner</button>

        <button
          class="inspector-btn inspector-btn--tonal"
          :style="{ background: 'rgba(79,216,192,0.08)', border: '1px solid rgba(79,216,192,0.3)', color: 'var(--color-teal)' }"
          @click="emit('approach', unit!.id)"
        >✥ Approcher</button>

        <button
          class="inspector-btn inspector-btn--tonal"
          :style="{ background: 'rgba(240,199,100,0.08)', border: '1px solid rgba(240,199,100,0.3)', color: 'var(--color-gold)' }"
          @click="emit('openSheet', unit!.id)"
        >👁 Fiche</button>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.inspector {
  position: absolute;
  top: 60px;
  right: 20px;
  width: 310px;
  padding: 14px;
  background: linear-gradient(180deg, var(--color-surface), var(--color-bg-elev));
  border: 1px solid color-mix(in srgb, var(--tone) 30%, transparent);
  border-radius: 10px;
  box-shadow:
    0 12px 36px rgba(0, 0, 0, 0.6),
    0 0 24px color-mix(in srgb, var(--tone) 12%, transparent);
  z-index: 20;
}

/* Close */
.inspector-close {
  position: absolute;
  top: 10px;
  right: 10px;
  width: 22px;
  height: 22px;
  border-radius: 4px;
  background: transparent;
  border: none;
  color: var(--color-text-muted);
  font-size: 14px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 120ms ease;
}

.inspector-close:hover { color: var(--color-parchment); }

/* Header */
.inspector-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
  padding-right: 24px; /* room for close button */
}

.inspector-avatar {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 14px;
  flex-shrink: 0;
}

.inspector-identity {
  flex: 1;
  min-width: 0;
}

.inspector-role {
  font-size: 8px;
  font-weight: 700;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  line-height: 1;
  margin-bottom: 2px;
}

.inspector-name {
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 700;
  color: var(--color-parchment);
  line-height: 1.1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.inspector-subtitle {
  font-size: 10px;
  color: var(--color-text-muted);
  margin-top: 2px;
}

/* Stats row */
.inspector-stats {
  display: flex;
  gap: 4px;
  margin-bottom: 8px;
}

.stat-box {
  flex: 1;
  padding: 5px 8px;
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid color-mix(in srgb, var(--sc) 20%, transparent);
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.stat-label {
  font-size: 8px;
  font-weight: 700;
  letter-spacing: 1px;
  color: var(--color-text-dim);
  text-transform: uppercase;
}

.stat-value {
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 700;
  line-height: 1;
}

/* HP bar */
.hp-track {
  height: 5px;
  border-radius: 3px;
  background: rgba(0, 0, 0, 0.5);
  overflow: hidden;
  margin-bottom: 10px;
}

.hp-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 300ms ease;
}

/* Tactical grid */
.inspector-tactical {
  padding: 8px 10px;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px 10px;
  font-size: 10px;
  margin-bottom: 8px;
}

.tac-row {
  display: flex;
  align-items: center;
  gap: 5px;
}

.tac-key {
  color: var(--color-text-dim);
  min-width: 42px;
}

.tac-val {
  font-family: var(--font-mono);
  font-weight: 700;
  color: var(--color-parchment);
  font-size: 10px;
}

/* Action economy */
.economy-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.economy-label {
  font-size: 8px;
  font-weight: 700;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: var(--color-text-muted);
}

.pips {
  display: flex;
  gap: 4px;
}

.pip {
  width: 22px;
  height: 22px;
  border-radius: 4px;
  background: rgba(240, 199, 100, 0.15);
  border: 1px solid rgba(240, 199, 100, 0.4);
  color: var(--color-gold);
  font-size: 8px;
  font-weight: 700;
  font-family: var(--font-mono);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: opacity 120ms;
}

.pip--used {
  background: rgba(0, 0, 0, 0.2);
  border-color: var(--color-border);
  color: var(--color-text-dim);
  opacity: 0.4;
}

/* Action buttons */
.inspector-actions {
  display: flex;
  gap: 5px;
  margin-top: 4px;
}

.inspector-btn {
  flex: 1;
  padding: 7px 0;
  border: none;
  border-radius: 5px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  cursor: pointer;
  white-space: nowrap;
  transition: opacity 120ms ease;
}

.inspector-btn:hover { opacity: 0.85; }

.inspector-btn--primary {
  color: var(--color-bg);
}

.inspector-btn--tonal {
  /* inline styles set bg/border/color */
}

/* Slide-in transition */
.inspector-slide-enter-active,
.inspector-slide-leave-active {
  transition: opacity 150ms ease, transform 150ms ease;
}

.inspector-slide-enter-from {
  opacity: 0;
  transform: translateY(-6px) scale(0.97);
}

.inspector-slide-leave-to {
  opacity: 0;
  transform: translateY(-4px) scale(0.97);
}
</style>
