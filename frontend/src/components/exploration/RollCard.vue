<script setup lang="ts">
import { computed } from 'vue'
import type { ExNarrativeEntry } from '../../fixtures/exploration'

const props = defineProps<{
  entry: Extract<ExNarrativeEntry, { type: 'roll' }>
}>()

const critical = computed(() => props.entry.rolls[0]?.critical ?? false)
const success = computed(() => props.entry.rolls[0]?.hit ?? true)
const total = computed(() => props.entry.rolls[0]?.value ?? 0)
const label = computed(() => props.entry.rolls[0]?.label ?? '1d20')
const stateClass = computed(() => critical.value ? 'is-critical' : success.value ? 'is-success' : 'is-fail')
const marker = computed(() => critical.value ? '★' : success.value ? '✓' : '✕')
</script>

<template>
  <div class="roll-card" :class="stateClass">
    <!-- Séparateurs {{ ' ' }} explicites : les espaces de flex (gap) ne sont pas
         des caractères, donc la copie/lecture d'écran concaténait « OakenDEX Save »
         et « 1d2018 ». Une suite uniquement blanche entre flex items n'est pas
         rendue (aucun impact visuel) mais reste dans le textContent. -->
    <span class="roll-card-marker">{{ marker }}</span>
    {{ ' ' }}
    <span class="roll-card-who">{{ entry.who }}</span>
    {{ ' ' }}
    <span class="roll-card-what">{{ entry.what }}</span>
    {{ ' ' }}

    <div class="roll-card-result">
      <span class="roll-card-result-label">{{ label }}</span>
      {{ ' ' }}
      <span class="roll-card-result-value">{{ total }}</span>
    </div>
    {{ ' ' }}

    <div v-if="entry.detail" class="roll-card-detail">{{ entry.detail }}</div>
  </div>
</template>

<style scoped>
.roll-card {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin: 14px 0;
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid;
}

.roll-card.is-success {
  background: rgba(111, 217, 111, 0.06);
  border-color: rgba(111, 217, 111, 0.25);
}

.roll-card.is-fail {
  background: rgba(232, 69, 69, 0.06);
  border-color: rgba(232, 69, 69, 0.25);
}

.roll-card.is-critical {
  background: rgba(255, 215, 0, 0.07);
  border-color: rgba(255, 215, 0, 0.35);
}

.roll-card-marker {
  font-size: 12px;
}

.roll-card.is-success .roll-card-marker,
.roll-card.is-success .roll-card-who,
.roll-card.is-success .roll-card-result-value {
  color: var(--color-green);
}

.roll-card.is-fail .roll-card-marker,
.roll-card.is-fail .roll-card-who,
.roll-card.is-fail .roll-card-result-value {
  color: var(--color-blood);
}

.roll-card.is-critical .roll-card-marker,
.roll-card.is-critical .roll-card-who,
.roll-card.is-critical .roll-card-result-value {
  color: var(--color-crit);
}

.roll-card.is-critical .roll-card-result {
  border-color: rgba(255, 215, 0, 0.5);
}

.roll-card-who {
  font-family: var(--font-display);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
}

.roll-card-what {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 11px;
  color: var(--color-parchment-dark);
  min-width: 80px;
}

.roll-card-result {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 3px 10px;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid var(--color-border);
  border-radius: 5px;
  min-width: 60px;
}

.roll-card.is-success .roll-card-result {
  border-color: var(--color-green);
}

.roll-card-result-label {
  font-size: 7px;
  color: var(--color-text-dim);
  letter-spacing: 1px;
  text-transform: uppercase;
}

.roll-card-result-value {
  font-family: var(--font-mono);
  font-size: 14px;
  font-weight: 700;
}

.roll-card-detail {
  flex: 1;
  min-width: 150px;
  font-size: 11px;
  font-family: var(--font-serif);
  color: var(--color-parchment-dark);
}
</style>
