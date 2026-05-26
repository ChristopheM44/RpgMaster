<script setup lang="ts">
import { useSessionStore } from '../../stores/session'
import CarnetGroupSection from './CarnetGroupSection.vue'
import CarnetQuestsSection from './CarnetQuestsSection.vue'
import CarnetMemorySection from './CarnetMemorySection.vue'

const sessionStore = useSessionStore()

const emit = defineEmits<{ openSheet: [id: string] }>()

function close() {
  sessionStore.toggleCarnet(false)
}
</script>

<template>
  <div v-if="sessionStore.carnetOpen" class="carnet-popover" role="dialog">
    <header class="carnet-header">
      <span class="carnet-header-icon">✦</span>
      <h3 class="carnet-header-title">Carnet d'aventure</h3>
      <div style="flex: 1" />
      <button class="carnet-close" @click="close">✕</button>
    </header>

    <div class="carnet-body">
      <div class="carnet-campaign rpg-card">
        <div class="carnet-campaign-title">Côte des Épées · Triboar Trail</div>
        <div class="carnet-campaign-sub">✦ Matin · Jour 1 · humide</div>
      </div>

      <CarnetGroupSection @open-sheet="(id) => emit('openSheet', id)" />
      <CarnetQuestsSection />
      <CarnetMemorySection />
    </div>
  </div>
</template>

<style scoped>
.carnet-popover {
  position: absolute;
  top: 12px;
  right: 12px;
  width: 380px;
  max-height: calc(100% - 24px);
  background: linear-gradient(180deg, var(--color-bg-elev), var(--color-surface));
  border: 1px solid var(--color-border-strong);
  border-radius: 10px;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.7);
  z-index: 30;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.carnet-header {
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.carnet-header-icon {
  color: var(--color-ember);
  font-size: 12px;
}

.carnet-header-title {
  margin: 0;
  font-family: var(--font-display);
  font-size: 12px;
  font-weight: 700;
  color: var(--color-parchment);
  letter-spacing: 2px;
  text-transform: uppercase;
}

.carnet-close {
  width: 22px;
  height: 22px;
  border-radius: 4px;
  background: transparent;
  border: none;
  color: var(--color-text-muted);
  font-size: 14px;
  cursor: pointer;
}

.carnet-close:hover { color: var(--color-parchment); }

.carnet-body {
  flex: 1;
  overflow-y: auto;
  padding: 10px 0 16px;
}

.carnet-campaign {
  margin: 0 14px 12px;
  padding: 10px 12px;
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid var(--color-border);
  border-radius: 6px;
}

.carnet-campaign-title {
  font-family: var(--font-display);
  font-size: 12px;
  font-weight: 700;
  color: var(--color-gold);
  letter-spacing: 0.6px;
}

.carnet-campaign-sub {
  font-size: 10px;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  margin-top: 2px;
}
</style>
