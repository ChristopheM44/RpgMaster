<script setup lang="ts">
import type { Monster } from '@/types/library';
import { TYPE_COLORS } from '@/types/library';

const props = defineProps<{
  monster: Monster;
  selected: boolean;
}>();

defineEmits<{
  select: [];
}>();

const typeColor = TYPE_COLORS[props.monster.type] ?? '#f7ecd0';
</script>

<template>
  <button
    class="monster-list-item"
    :class="{ 'is-selected': selected }"
    :style="{
      borderLeftColor: selected ? typeColor : 'transparent',
    }"
    @click="$emit('select')"
  >
    <!-- Dot type -->
    <span
      class="monster-dot"
      :style="{
        background: typeColor,
        boxShadow: `0 0 6px ${typeColor}50`,
      }"
    ></span>

    <!-- Infos -->
    <div class="monster-info">
      <div class="monster-name">{{ monster.name }}</div>
      <div class="monster-meta">
        <span>{{ monster.type }}</span>
        <span class="monster-meta-sep">·</span>
        <span>{{ monster.size }}</span>
      </div>
    </div>

    <!-- Badge FP -->
    <span
      class="monster-cr-badge"
      :style="{
        background: `color-mix(in srgb, ${typeColor} 12%, transparent)`,
        color: typeColor,
        borderColor: `${typeColor}40`,
      }"
    >FP {{ monster.challenge }}</span>
  </button>
</template>

<style scoped>
.monster-list-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 8px 12px;
  text-align: left;
  cursor: pointer;
  background: transparent;
  border: none;
  border-left: 3px solid transparent;
  border-bottom: 1px solid var(--color-border);
  color: var(--color-parchment);
  transition: all 120ms ease;
}
.monster-list-item:hover {
  filter: brightness(1.08);
}
.monster-list-item.is-selected {
  background: var(--color-surface-raised);
  box-shadow: var(--shadow-card-active);
}

.monster-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.monster-info {
  flex: 1;
  min-width: 0;
}
.monster-name {
  font-family: var(--font-display);
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.03em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.monster-meta {
  font-size: 10px;
  color: var(--color-text-muted);
  display: flex;
  gap: 4px;
  align-items: center;
  margin-top: 1px;
}
.monster-meta-sep {
  color: var(--color-text-dim);
}

.monster-cr-badge {
  flex-shrink: 0;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-size: 10px;
  font-weight: 700;
  font-family: var(--font-mono);
  border: 1px solid;
}
</style>
