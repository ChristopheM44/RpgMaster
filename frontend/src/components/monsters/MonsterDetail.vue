<script setup lang="ts">
import { computed } from 'vue';
import type { Monster } from '@/types/library';
import { TYPE_COLORS } from '@/types/library';
import AbilityBlock from './AbilityBlock.vue';

const props = defineProps<{
  /** Monstre sélectionné, ou null pour l'état vide */
  monster: Monster | null;
}>();

const typeColor = computed(() => (
  props.monster ? (TYPE_COLORS[props.monster.type] ?? '#f7ecd0') : ''
));

function formatSpeed(speed: Monster['speed']): string {
  return Object.entries(speed)
    .map(([k, v]) => (k === 'marche' ? v : `${k} ${v}`))
    .join(', ');
}
</script>

<template>
  <!-- État vide -->
  <div v-if="!monster" class="monster-detail-empty">
    <span class="monster-detail-empty-icon">◆</span>
    <span class="monster-detail-empty-text">Sélectionnez un monstre</span>
  </div>

  <!-- Détail du monstre -->
  <div v-else class="monster-detail">
    <!-- Header -->
    <div class="monster-detail-header">
      <div class="monster-detail-title-row">
        <span :style="{ color: typeColor, fontSize: '18px' }">◆</span>
        <h1 class="monster-detail-title">{{ monster.name.toUpperCase() }}</h1>
      </div>
      <div class="monster-detail-subtitle">
        {{ monster.type }}<span v-if="monster.subtype"> ({{ monster.subtype }})</span>
        de taille {{ monster.size.toLowerCase() }}, {{ monster.alignment.toLowerCase() }}
      </div>
    </div>

    <!-- Stats principaux : CA, PV, Vitesse -->
    <div class="monster-main-stats">
      <div class="monster-stat-cell">
        <div class="monster-stat-label">Classe d'armure</div>
        <div class="monster-stat-row">
          <span class="monster-stat-big">{{ monster.ac }}</span>
          <span v-if="monster.ac_type" class="monster-stat-note">{{ monster.ac_type }}</span>
        </div>
      </div>
      <div class="monster-stat-cell">
        <div class="monster-stat-label">Points de vie</div>
        <div class="monster-stat-row">
          <span class="monster-stat-big">{{ monster.hp }}</span>
          <span class="monster-stat-dice">({{ monster.hp_dice }})</span>
        </div>
      </div>
      <div class="monster-stat-cell">
        <div class="monster-stat-label">Vitesse</div>
        <div class="monster-stat-speed">{{ formatSpeed(monster.speed) }}</div>
      </div>
    </div>

    <!-- Caractéristiques -->
    <AbilityBlock :abilities="monster.abilities" />

    <!-- Info lines -->
    <div
      v-if="monster.saving_throws"
      class="rpg-info-line"
    >
      <span class="rpg-info-line-label">Jets de sauvegarde</span>
      <span class="rpg-info-line-value">
        {{ Object.entries(monster.saving_throws).map(([k, v]) => `${k} ${v}`).join(', ') }}
      </span>
    </div>

    <div
      v-if="monster.skills && Object.keys(monster.skills).length > 0"
      class="rpg-info-line"
    >
      <span class="rpg-info-line-label">Compétences</span>
      <span class="rpg-info-line-value">
        {{ Object.entries(monster.skills).map(([k, v]) => `${k} ${v}`).join(', ') }}
      </span>
    </div>

    <div v-if="monster.damage_resistances.length > 0" class="rpg-info-line">
      <span class="rpg-info-line-label">Résistances</span>
      <span class="rpg-info-line-value">{{ monster.damage_resistances.join(', ') }}</span>
    </div>

    <div v-if="monster.damage_immunities.length > 0" class="rpg-info-line">
      <span class="rpg-info-line-label">Immunités (dégâts)</span>
      <span class="rpg-info-line-value">{{ monster.damage_immunities.join(', ') }}</span>
    </div>

    <div v-if="monster.condition_immunities.length > 0" class="rpg-info-line">
      <span class="rpg-info-line-label">Immunités (conditions)</span>
      <span class="rpg-info-line-value">{{ monster.condition_immunities.join(', ') }}</span>
    </div>

    <div class="rpg-info-line">
      <span class="rpg-info-line-label">Sens</span>
      <span class="rpg-info-line-value">{{ monster.senses }}</span>
    </div>

    <div class="rpg-info-line">
      <span class="rpg-info-line-label">Langues</span>
      <span class="rpg-info-line-value">{{ monster.languages }}</span>
    </div>

    <!-- FP -->
    <div class="monster-cr-line">
      <span class="rpg-info-line-label">Facteur de puissance</span>
      <span class="monster-cr-value">{{ monster.challenge }}</span>
      <span class="monster-cr-xp">({{ monster.xp.toLocaleString('fr-FR') }} XP)</span>
    </div>

    <!-- Capacités -->
    <template v-if="monster.traits.length > 0">
      <div class="rpg-detail-section"><span>Capacités</span></div>
      <div class="monster-features">
        <div v-for="(t, i) in monster.traits" :key="i" class="monster-feature">
          <div class="monster-feature-name">{{ t.name }}.</div>
          <p class="monster-feature-desc">{{ t.desc }}</p>
        </div>
      </div>
    </template>

    <!-- Actions -->
    <template v-if="monster.actions.length > 0">
      <div class="rpg-detail-section"><span>Actions</span></div>
      <div class="monster-features">
        <div v-for="(a, i) in monster.actions" :key="i" class="monster-feature">
          <div class="monster-feature-name">{{ a.name }}.</div>
          <p class="monster-feature-desc">{{ a.desc }}</p>
        </div>
      </div>
    </template>

    <!-- Réactions -->
    <template v-if="monster.reactions && monster.reactions.length > 0">
      <div class="rpg-detail-section"><span>Réactions</span></div>
      <div class="monster-features">
        <div v-for="(r, i) in monster.reactions" :key="i" class="monster-feature">
          <div class="monster-feature-name">{{ r.name }}.</div>
          <p class="monster-feature-desc">{{ r.desc }}</p>
        </div>
      </div>
    </template>

    <!-- Actions légendaires -->
    <template v-if="monster.legendary_actions && monster.legendary_actions.length > 0">
      <div class="rpg-detail-section"><span>Actions légendaires</span></div>
      <div class="monster-features">
        <div v-for="(la, i) in monster.legendary_actions" :key="i" class="monster-feature">
          <div class="monster-feature-name">{{ la.name }}.</div>
          <p class="monster-feature-desc">{{ la.desc }}</p>
        </div>
      </div>
    </template>

    <!-- Environnement -->
    <template v-if="monster.environment && monster.environment.length > 0">
      <div class="rpg-detail-section"><span>Environnement</span></div>
      <div class="monster-env-chips">
        <span v-for="e in monster.environment" :key="e" class="monster-env-chip">{{ e }}</span>
      </div>
    </template>

    <!-- Source -->
    <div class="monster-source">Source : {{ monster.source }}</div>
  </div>
</template>

<style scoped>
.monster-detail-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--color-text-dim);
  gap: 12px;
}
.monster-detail-empty-icon {
  font-size: 48px;
  opacity: 0.15;
}
.monster-detail-empty-text {
  font-family: var(--font-display);
  font-size: 14px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.monster-detail {
  flex: 1;
  overflow-y: auto;
  padding: 32px 40px 40px;
}

/* Header */
.monster-detail-header { margin-bottom: 24px; }
.monster-detail-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}
.monster-detail-title {
  font-family: var(--font-display);
  font-size: 28px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: var(--color-parchment);
  margin: 0;
  line-height: 1.2;
}
.monster-detail-subtitle {
  margin-left: 28px;
  font-size: 13px;
  color: var(--color-parchment-dark);
  font-family: var(--font-serif);
  font-style: italic;
}

/* Main stats grid */
.monster-main-stats {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 1px;
  background: var(--color-border);
  border-radius: var(--radius-lg);
  overflow: hidden;
  margin-bottom: 20px;
}
.monster-stat-cell {
  background: var(--color-surface);
  padding: 14px 16px;
}
.monster-stat-label {
  font-family: var(--font-display);
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  color: var(--color-text-dim);
  margin-bottom: 4px;
}
.monster-stat-row {
  display: flex;
  align-items: baseline;
  gap: 6px;
}
.monster-stat-big {
  font-family: var(--font-mono);
  font-size: 22px;
  font-weight: 700;
  color: var(--color-parchment);
}
.monster-stat-note {
  font-size: 10px;
  color: var(--color-text-muted);
  font-family: var(--font-body);
}
.monster-stat-dice {
  font-size: 10px;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
}
.monster-stat-speed {
  font-size: 13px;
  color: var(--color-parchment);
  font-family: var(--font-body);
}

/* CR line */
.monster-cr-line {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 0;
  border-bottom: 1px solid var(--color-border);
  margin-bottom: 20px;
}
.monster-cr-value {
  font-family: var(--font-mono);
  font-size: 14px;
  font-weight: 700;
  color: var(--color-parchment);
}
.monster-cr-xp {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--color-text-muted);
}

/* Features / actions */
.monster-features {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-bottom: 24px;
}
.monster-feature-name {
  font-family: var(--font-display);
  font-size: 13px;
  font-weight: 700;
  color: var(--color-parchment);
  margin-bottom: 4px;
  letter-spacing: 0.02em;
}
.monster-feature-desc {
  font-family: var(--font-serif);
  font-size: 13px;
  line-height: 1.65;
  color: var(--color-parchment-dark);
  margin: 0;
  text-wrap: pretty;
}

/* Environment chips */
.monster-env-chips {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 24px;
}
.monster-env-chip {
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
.monster-source {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--color-border);
  font-size: 10px;
  color: var(--color-text-dim);
  font-family: var(--font-mono);
}
</style>
