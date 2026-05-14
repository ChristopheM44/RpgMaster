<script setup lang="ts">
import type { AbilityKey } from '@/types/library';

const props = defineProps<{
  abilities: Record<AbilityKey, { v: number; m: string }>;
}>();

const keys: AbilityKey[] = ['FOR', 'DEX', 'CON', 'INT', 'SAG', 'CHA'];

function ability(k: AbilityKey) {
  return props.abilities[k] ?? { v: 10, m: '+0' };
}
</script>

<template>
  <div class="ability-block">
    <div v-for="k in keys" :key="k" class="ability-cell">
      <div class="ability-label">{{ k }}</div>
      <div class="ability-value">{{ ability(k).v }}</div>
      <div class="ability-mod">{{ ability(k).m }}</div>
    </div>
  </div>
</template>

<style scoped>
.ability-block {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 1px;
  background: var(--color-border);
  border-radius: var(--radius-md);
  overflow: hidden;
  margin-bottom: 20px;
}

.ability-cell {
  background: var(--color-surface);
  padding: 10px 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.ability-label {
  font-family: var(--font-display);
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.15em;
  color: var(--color-text-dim);
}

.ability-value {
  font-family: var(--font-mono);
  font-size: 18px;
  font-weight: 700;
  color: var(--color-parchment);
}

.ability-mod {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 500;
  color: var(--color-text-muted);
}
</style>
