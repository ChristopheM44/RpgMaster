<script setup lang="ts">
import { computed } from 'vue'
import { useSessionStore } from '../../stores/session'
import RefChip from './RefChip.vue'
import RollCard from './RollCard.vue'
import DecisionCard from './DecisionCard.vue'
import type { ExNarrativeEntry } from '../../fixtures/exploration'

const props = defineProps<{
  entry: ExNarrativeEntry
  /** Mode compact pour le drawer 360 px — tailles légèrement réduites, même langage visuel */
  compact?: boolean
}>()

const emit = defineEmits<{
  decide: [optionId: string]
}>()

const sessionStore = useSessionStore()

const refs = computed<string[]>(() => {
  if ('refs' in props.entry && props.entry.refs) return props.entry.refs
  return []
})

function onRefHover(id: string | null) {
  sessionStore.setHighlighted(id)
}

function onRefClick(id: string) {
  sessionStore.selectEntity(id)
}

function onEntryEnter() {
  if (refs.value.length > 0) {
    sessionStore.setHighlighted(refs.value)
  }
}

function onEntryLeave() {
  sessionStore.setHighlighted(null)
}
</script>

<template>
  <!-- ─ divider ────────────────────────────────────────────── -->
  <div v-if="entry.type === 'divider'" class="ne-divider">
    <span class="ne-divider-rule" />
    <span class="ne-divider-text">✦ {{ entry.text }} ✦</span>
    <span class="ne-divider-rule rev" />
  </div>

  <!-- ─ gm ─────────────────────────────────────────────────── -->
  <div
    v-else-if="entry.type === 'gm'"
    class="ne-gm"
    :class="{ compact }"
    @mouseenter="onEntryEnter"
    @mouseleave="onEntryLeave"
  >
    <div class="ne-gm-eyebrow rpg-eyebrow">
      <span>✦</span>Maître du jeu
    </div>
    <p class="ne-gm-text">{{ entry.text }}</p>
    <div v-if="refs.length" class="ne-refs">
      <RefChip
        v-for="rid in refs"
        :key="rid"
        :ref-id="rid"
        @hover="onRefHover"
        @click="onRefClick"
      />
    </div>
  </div>

  <!-- ─ player ────────────────────────────────────────────── -->
  <div
    v-else-if="entry.type === 'player'"
    class="ne-player"
    :class="{ compact }"
    @mouseenter="onEntryEnter"
    @mouseleave="onEntryLeave"
  >
    <div class="ne-player-head">
      <div class="ne-player-who">
        <span class="ne-player-marker">▸</span>
        <span>{{ entry.who }}</span>
      </div>
      <div v-if="refs.length" class="ne-refs">
        <RefChip
          v-for="rid in refs"
          :key="rid"
          :ref-id="rid"
          @hover="onRefHover"
          @click="onRefClick"
        />
      </div>
    </div>
    <div class="ne-player-text">« {{ entry.text }} »</div>
  </div>

  <!-- ─ dialogue (PNJ / compagnon) ─────────────────────────── -->
  <div
    v-else-if="entry.type === 'dialogue'"
    class="ne-dialogue"
    :class="[entry.speakerKind === 'companion' ? 'tone-arcane' : 'tone-gold', { compact }]"
  >
    <div class="ne-dialogue-who">
      <span class="ne-dialogue-marker">▸</span>
      <span>{{ entry.who }}</span>
    </div>
    <div class="ne-dialogue-text">« {{ entry.text }} »</div>
  </div>

  <!-- ─ combat ────────────────────────────────────────────── -->
  <div v-else-if="entry.type === 'combat'" class="ne-combat" :class="{ compact }">
    <div class="ne-combat-head">
      <span class="ne-combat-icon">⚔</span>
      <span class="ne-combat-name">{{ entry.attacker }}</span>
      <span class="ne-combat-arrow">→</span>
      <span class="ne-combat-name">{{ entry.target }}</span>
      <span v-if="entry.critical" class="ne-combat-chip">Critique !</span>
    </div>
    <div class="ne-combat-detail">
      <span>d20 : <strong>{{ entry.d20 }}</strong></span>
      <span>Total : <strong>{{ entry.attackRoll }}</strong> vs CA {{ entry.targetAc }}</span>
      <span v-if="entry.hit" class="ne-combat-hit">Touché</span>
      <span v-else class="ne-combat-miss">Raté</span>
      <span v-if="entry.hit && entry.damage !== null" class="ne-combat-dmg">{{ entry.damage }} dégâts</span>
    </div>
  </div>

  <!-- ─ roll ──────────────────────────────────────────────── -->
  <RollCard v-else-if="entry.type === 'roll'" :entry="entry" />

  <!-- ─ decision ──────────────────────────────────────────── -->
  <DecisionCard
    v-else-if="entry.type === 'decision'"
    :entry="entry"
    @decide="(id: string) => emit('decide', id)"
  />
</template>

<style scoped>
/* ── divider ────────────────────────────────────────────────────────── */
.ne-divider {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 20px 0;
}

.ne-divider-rule {
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(240, 199, 100, 0.33));
}

.ne-divider-rule.rev {
  background: linear-gradient(90deg, rgba(240, 199, 100, 0.33), transparent);
}

.ne-divider-text {
  font-family: var(--font-display);
  font-size: 10px;
  color: var(--color-gold);
  letter-spacing: 3px;
  text-transform: uppercase;
  white-space: nowrap;
}

/* ── gm ─────────────────────────────────────────────────────────────── */
.ne-gm { margin: 20px 0; }

.ne-gm-eyebrow {
  color: var(--color-ember);
  margin-bottom: 6px;
  display: flex;
  align-items: center;
  gap: 5px;
}

.ne-gm-text {
  font-family: var(--font-serif);
  font-size: 15.5px;
  line-height: 1.65;
  color: var(--color-parchment);
  margin: 0;
  text-wrap: pretty;
}

.ne-refs {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  margin-top: 6px;
}

/* ── player ─────────────────────────────────────────────────────────── */
.ne-player {
  margin: 16px 0;
  padding: 8px 12px;
  background: rgba(192, 144, 255, 0.06);
  border: 1px solid rgba(192, 144, 255, 0.22);
  border-left: 3px solid rgba(192, 144, 255, 0.6);
  border-radius: 6px;
}

.ne-player-head {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
  justify-content: space-between;
}

.ne-player-who {
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-display);
  font-size: 11px;
  font-weight: 700;
  color: var(--color-arcane);
}

.ne-player-marker {
  color: var(--color-arcane);
  font-size: 10px;
}

.ne-player-text {
  font-size: 13.5px;
  color: var(--color-parchment-dark);
  font-family: var(--font-serif);
  font-style: italic;
  line-height: 1.5;
}

/* ── compact overrides (drawer 360 px) ──────────────────────────────── */
.ne-gm.compact { margin: 14px 0; }
.ne-gm.compact .ne-gm-text { font-size: 13px; line-height: 1.6; }

.ne-player.compact { margin: 10px 0; }
.ne-player.compact .ne-player-text { font-size: 12px; }

/* ── dialogue ────────────────────────────────────────────────────────── */
.ne-dialogue {
  margin: 16px 0;
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid;
  border-left-width: 3px;
}

.ne-dialogue.tone-arcane {
  background: rgba(192, 144, 255, 0.06);
  border-color: rgba(192, 144, 255, 0.22);
  border-left-color: rgba(192, 144, 255, 0.6);
}

.ne-dialogue.tone-gold {
  background: rgba(240, 199, 100, 0.05);
  border-color: rgba(240, 199, 100, 0.20);
  border-left-color: rgba(240, 199, 100, 0.5);
}

.ne-dialogue-who {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
  font-family: var(--font-display);
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.ne-dialogue.tone-arcane .ne-dialogue-who { color: var(--color-arcane); }
.ne-dialogue.tone-gold   .ne-dialogue-who { color: var(--color-gold); }

.ne-dialogue-marker { font-size: 10px; }

.ne-dialogue-text {
  font-family: var(--font-serif);
  font-size: 13.5px;
  font-style: italic;
  color: var(--color-parchment-dark);
  line-height: 1.5;
}

.ne-dialogue.compact { margin: 10px 0; }
.ne-dialogue.compact .ne-dialogue-text { font-size: 12px; }

/* ── combat ──────────────────────────────────────────────────────────── */
.ne-combat {
  margin: 14px 0;
  padding: 8px 12px;
  background: rgba(232, 69, 69, 0.05);
  border: 1px solid rgba(232, 69, 69, 0.15);
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.ne-combat-head {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.ne-combat-icon {
  color: var(--color-blood);
  font-size: 11px;
}

.ne-combat-name {
  font-family: var(--font-display);
  font-size: 11px;
  font-weight: 700;
  color: var(--color-parchment);
  letter-spacing: 0.5px;
  text-transform: uppercase;
}

.ne-combat-arrow {
  color: var(--color-blood);
  font-size: 11px;
}

.ne-combat-chip {
  margin-left: auto;
  padding: 1px 6px;
  background: rgba(240, 199, 100, 0.18);
  border: 1px solid rgba(240, 199, 100, 0.5);
  border-radius: 4px;
  font-family: var(--font-display);
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  color: var(--color-gold);
}

.ne-combat-detail {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--color-text-muted);
}

.ne-combat-detail strong {
  color: var(--color-parchment);
  font-weight: 700;
}

.ne-combat-hit { color: var(--color-teal); font-weight: 600; }
.ne-combat-miss { color: var(--color-text-dim); }
.ne-combat-dmg { color: var(--color-blood); font-weight: 600; }

.ne-combat.compact { margin: 10px 0; padding: 6px 10px; }
.ne-combat.compact .ne-combat-name { font-size: 10px; }
.ne-combat.compact .ne-combat-detail { font-size: 9px; }
</style>
