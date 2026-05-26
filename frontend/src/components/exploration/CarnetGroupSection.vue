<script setup lang="ts">
import CollapsibleSection from './CollapsibleSection.vue'
import { useExplorationParty } from '../../composables/useExplorationParty'

const emit = defineEmits<{ openSheet: [id: string] }>()

const { party } = useExplorationParty()
</script>

<template>
  <CollapsibleSection id="group" eyebrow="✦ Le groupe" :count="party.length">
    <div class="carnet-group">
      <div
        v-for="h in party"
        :key="h.id"
        class="carnet-group-row"
        :class="{ 'is-mine': h.isMe }"
      >
        <div
          class="carnet-group-avatar"
          :class="{ 'is-mine': h.isMe }"
          :style="{ background: `radial-gradient(circle at 30% 30%, ${h.color}, ${h.color}aa)` }"
        >{{ h.token }}</div>
        <div class="carnet-group-meta">
          <div class="carnet-group-line">
            <span class="carnet-group-name" :class="{ 'is-mine': h.isMe }">{{ h.name }}</span>
            <span v-if="h.isMe" class="carnet-group-tag tag-me">VOUS</span>
            <span v-else-if="h.ai" class="carnet-group-tag tag-ai">IA</span>
            <span v-else class="carnet-group-tag tag-ally">ALLIÉ</span>
          </div>
          <div class="carnet-group-stats">{{ h.cls }} · PV {{ h.hp }}/{{ h.hpMax }}</div>
        </div>
        <button
          class="carnet-group-action"
          title="Voir la fiche"
          @click="emit('openSheet', h.id)"
        >📜</button>
      </div>
    </div>
  </CollapsibleSection>
</template>

<style scoped>
.carnet-group {
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 6px 14px 10px;
}

.carnet-group-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 6px;
  border-radius: 5px;
  background: transparent;
  border: 1px solid transparent;
}

.carnet-group-row.is-mine {
  background: rgba(255, 130, 71, 0.08);
  border-color: rgba(255, 130, 71, 0.25);
}

.carnet-group-avatar {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  border: 1.5px solid rgba(247, 236, 208, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-display);
  font-size: 10px;
  font-weight: 700;
  color: var(--color-bg);
  flex-shrink: 0;
}

.carnet-group-avatar.is-mine { border-color: var(--color-gold); }

.carnet-group-meta {
  flex: 1;
  min-width: 0;
}

.carnet-group-line {
  display: flex;
  align-items: center;
  gap: 4px;
}

.carnet-group-name {
  font-family: var(--font-display);
  font-size: 11px;
  font-weight: 600;
  color: var(--color-parchment);
}

.carnet-group-name.is-mine { color: var(--color-gold); }

.carnet-group-tag {
  font-size: 8px;
  font-weight: 700;
  letter-spacing: 0.5px;
}

.carnet-group-tag.tag-me { color: var(--color-ember); }
.carnet-group-tag.tag-ai { color: var(--color-arcane); }
.carnet-group-tag.tag-ally { color: var(--color-teal); }

.carnet-group-stats {
  font-size: 9px;
  color: var(--color-text-dim);
  font-family: var(--font-mono);
}

.carnet-group-action {
  padding: 3px 6px;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  background: transparent;
  color: var(--color-text-muted);
  font-size: 11px;
  cursor: pointer;
  transition: color 120ms, border-color 120ms;
}

.carnet-group-action:hover {
  color: var(--color-parchment);
  border-color: var(--color-border-strong);
}
</style>
