<script setup lang="ts">
import { computed } from 'vue';
import type { Spell } from '@/types/library';
import { SCHOOL_COLORS, LEVEL_LABELS } from '@/types/library';

const props = defineProps<{
  /** Sort sélectionné, ou null pour l'état vide */
  spell: Spell | null;
}>();

const schoolColor = computed(() => (
  props.spell ? (SCHOOL_COLORS[props.spell.school] ?? '#f7ecd0') : ''
));
const comps = computed(() => (
  props.spell
    ? [props.spell.components.V && 'V', props.spell.components.S && 'S', props.spell.components.M && 'M']
      .filter(Boolean)
      .join(', ')
    : ''
));
</script>

<template>
  <!-- État vide -->
  <div v-if="!spell" class="spell-detail-empty">
    <span class="spell-detail-empty-icon">✦</span>
    <span class="spell-detail-empty-text">Sélectionnez un sort</span>
  </div>

  <!-- Détail du sort -->
  <div v-else class="spell-detail">
    <!-- Header -->
    <div class="spell-detail-header">
      <div class="spell-detail-title-row">
        <span :style="{ color: schoolColor, fontSize: '18px' }">✦</span>
        <h1 class="spell-detail-title">{{ spell.name.toUpperCase() }}</h1>
      </div>
      <div class="spell-detail-subtitle">
        <span
          class="spell-school-chip"
          :style="{
            background: `color-mix(in srgb, ${schoolColor} 15%, transparent)`,
            color: schoolColor,
            borderColor: schoolColor + '30',
          }"
        >{{ spell.school }}</span>
        <span class="spell-detail-sep">·</span>
        <span class="spell-detail-level">{{ LEVEL_LABELS[spell.level] }}</span>
      </div>
    </div>

    <!-- Grille de stats -->
    <div class="spell-stat-grid">
      <div class="spell-stat-cell" v-for="[label, val] in [
        ['INCANTATION', spell.casting_time],
        ['PORTÉE', spell.range],
        ['COMPOSANTES', comps],
        ['DURÉE', spell.duration],
      ]" :key="label">
        <div class="spell-stat-label">{{ label }}</div>
        <div class="spell-stat-value">{{ val }}</div>
      </div>
    </div>

    <!-- Composante matérielle -->
    <div v-if="spell.components.M" class="spell-material">
      <span class="spell-material-label">Matériel :</span>
      {{ spell.components.M }}
    </div>

    <!-- Tags -->
    <div class="spell-tags">
      <span v-if="spell.concentration" class="spell-tag gold">◉ Concentration</span>
      <span v-if="spell.ritual" class="spell-tag arcane">◈ Rituel</span>
      <span v-if="spell.damage_type" class="spell-tag ember">◆ {{ spell.damage_type }}</span>
    </div>

    <!-- Description -->
    <div class="rpg-detail-section"><span>Description</span></div>
    <p class="spell-description">{{ spell.description }}</p>

    <!-- Niveaux supérieurs -->
    <template v-if="spell.higher_levels">
      <div class="rpg-detail-section"><span>Aux niveaux supérieurs</span></div>
      <p class="spell-higher-levels">{{ spell.higher_levels }}</p>
    </template>

    <!-- Classes -->
    <div class="rpg-detail-section"><span>Classes</span></div>
    <div class="spell-classes">
      <span v-for="c in spell.classes" :key="c" class="spell-class-chip">{{ c }}</span>
    </div>

    <!-- Source -->
    <div class="spell-source">Source : {{ spell.source }}</div>
  </div>
</template>

<style scoped>
.spell-detail-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--color-text-dim);
  gap: 12px;
}
.spell-detail-empty-icon {
  font-size: 48px;
  opacity: 0.15;
}
.spell-detail-empty-text {
  font-family: var(--font-display);
  font-size: 14px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.spell-detail {
  flex: 1;
  overflow-y: auto;
  padding: 32px 40px 40px;
}

/* Header */
.spell-detail-header { margin-bottom: 24px; }
.spell-detail-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}
.spell-detail-title {
  font-family: var(--font-display);
  font-size: 28px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: var(--color-parchment);
  margin: 0;
  line-height: 1.2;
}
.spell-detail-subtitle {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: 28px;
}
.spell-school-chip {
  padding: 3px 10px;
  border-radius: var(--radius-sm);
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  border: 1px solid;
}
.spell-detail-sep {
  color: var(--color-text-muted);
  font-size: 13px;
}
.spell-detail-level {
  font-family: var(--font-display);
  font-size: 13px;
  font-weight: 700;
  color: var(--color-parchment-dark);
  letter-spacing: 0.05em;
}

/* Stats grid */
.spell-stat-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1px;
  background: var(--color-border);
  border-radius: var(--radius-lg);
  overflow: hidden;
  margin-bottom: 20px;
}
.spell-stat-cell {
  background: var(--color-surface);
  padding: 12px 16px;
}
.spell-stat-label {
  font-family: var(--font-display);
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  color: var(--color-text-dim);
  margin-bottom: 4px;
}
.spell-stat-value {
  font-family: var(--font-body);
  font-size: 13px;
  font-weight: 500;
  color: var(--color-parchment);
}

/* Matériel */
.spell-material {
  padding: 10px 14px;
  border-radius: var(--radius-md);
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid var(--color-border);
  font-size: 12px;
  color: var(--color-text-muted);
  font-family: var(--font-serif);
  font-style: italic;
  margin-bottom: 20px;
}
.spell-material-label {
  color: var(--color-parchment-dark);
  font-weight: 600;
  font-style: normal;
  font-family: var(--font-body);
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

/* Tags */
.spell-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 24px;
}
.spell-tag {
  padding: 4px 10px;
  border-radius: var(--radius-sm);
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  border: 1px solid;
}
.spell-tag.gold {
  background: rgba(240, 199, 100, 0.10);
  color: var(--color-gold);
  border-color: rgba(240, 199, 100, 0.25);
}
.spell-tag.arcane {
  background: rgba(192, 144, 255, 0.10);
  color: var(--color-arcane);
  border-color: rgba(192, 144, 255, 0.25);
}
.spell-tag.ember {
  background: rgba(255, 130, 71, 0.10);
  color: var(--color-ember);
  border-color: rgba(255, 130, 71, 0.25);
}

/* Description */
.spell-description {
  font-family: var(--font-serif);
  font-size: 15px;
  line-height: 1.7;
  color: var(--color-parchment-dark);
  text-wrap: pretty;
  margin: 0 0 24px;
}

/* Higher levels */
.spell-higher-levels {
  font-family: var(--font-serif);
  font-size: 14px;
  line-height: 1.65;
  color: var(--color-parchment-dark);
  text-wrap: pretty;
  font-style: italic;
  margin: 0 0 24px;
}

/* Classes */
.spell-classes {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 24px;
}
.spell-class-chip {
  padding: 4px 12px;
  border-radius: var(--radius-sm);
  font-size: 11px;
  font-weight: 600;
  font-family: var(--font-body);
  background: var(--color-surface);
  color: var(--color-parchment-dark);
  border: 1px solid var(--color-border);
}

/* Source */
.spell-source {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--color-border);
  font-size: 10px;
  color: var(--color-text-dim);
  font-family: var(--font-mono);
}
</style>
