<script setup lang="ts">
import type { Spell } from '@/types/library';
import { SCHOOL_COLORS } from '@/types/library';

const props = defineProps<{
  spell: Spell;
  selected: boolean;
}>();

defineEmits<{
  select: [];
}>();

const schoolColor = SCHOOL_COLORS[props.spell.school] ?? '#f7ecd0';
</script>

<template>
  <button
    class="spell-list-item"
    :class="{ 'is-selected': selected }"
    :style="{
      borderLeftColor: selected ? schoolColor : 'transparent',
    }"
    @click="$emit('select')"
  >
    <!-- Dot école -->
    <span
      class="spell-dot"
      :style="{
        background: schoolColor,
        boxShadow: `0 0 6px ${schoolColor}50`,
      }"
    ></span>

    <!-- Infos -->
    <div class="spell-info">
      <div class="spell-name">{{ spell.name }}</div>
      <div class="spell-meta">
        <span>{{ spell.school }}</span>
        <span v-if="spell.concentration" class="spell-tag-conc">◉ C</span>
        <span v-if="spell.ritual" class="spell-tag-ritual">◈ R</span>
      </div>
    </div>

    <!-- Badge niveau -->
    <span
      class="spell-level-badge"
      :style="{
        background: spell.level === 0
          ? 'rgba(247,236,208,0.06)'
          : `color-mix(in srgb, ${schoolColor} 12%, transparent)`,
        color: spell.level === 0 ? 'var(--color-text-muted)' : schoolColor,
        borderColor: spell.level === 0
          ? 'var(--color-border)'
          : `${schoolColor}40`,
      }"
    >
      {{ spell.level === 0 ? 'C' : `Niv.${spell.level}` }}
    </span>
  </button>
</template>

<style scoped>
.spell-list-item {
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
.spell-list-item:hover {
  filter: brightness(1.08);
}
.spell-list-item.is-selected {
  background: var(--color-surface-raised);
  box-shadow: var(--shadow-card-active);
}

.spell-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.spell-info {
  flex: 1;
  min-width: 0;
}
.spell-name {
  font-family: var(--font-display);
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.03em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.spell-meta {
  font-size: 10px;
  color: var(--color-text-muted);
  display: flex;
  gap: 6px;
  align-items: center;
  margin-top: 1px;
}
.spell-tag-conc {
  color: var(--color-gold);
  font-weight: 600;
}
.spell-tag-ritual {
  color: var(--color-arcane);
  font-weight: 600;
}

.spell-level-badge {
  flex-shrink: 0;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-size: 10px;
  font-weight: 700;
  font-family: var(--font-mono);
  border: 1px solid;
}
</style>
