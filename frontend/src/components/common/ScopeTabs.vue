<script setup lang="ts">
defineProps<{
  modelValue: 'scene' | 'ville' | 'region'
}>()

const emit = defineEmits<{
  'update:modelValue': [value: 'scene' | 'ville' | 'region']
}>()

const tabs: { id: 'scene' | 'ville' | 'region'; label: string; icon: string }[] = [
  { id: 'scene', label: 'Scène', icon: '✦' },
  { id: 'ville', label: 'Ville', icon: '⊚' },
  { id: 'region', label: 'Région', icon: '◇' },
]
</script>

<template>
  <div class="scope-tabs">
    <button
      v-for="tab in tabs"
      :key="tab.id"
      :class="['scope-tab', { active: modelValue === tab.id }]"
      @click="emit('update:modelValue', tab.id)"
    >
      <span class="scope-tab-icon">{{ tab.icon }}</span>
      {{ tab.label }}
    </button>
  </div>
</template>

<style scoped>
.scope-tabs {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 3px;
  border-radius: 7px;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid var(--color-border);
  flex-shrink: 0;
}

.scope-tab {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 5px 10px;
  border-radius: 5px;
  background: transparent;
  border: none;
  color: var(--color-text-muted);
  font-family: var(--font-display);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  cursor: pointer;
  transition: background 120ms ease, color 120ms ease;
  box-shadow: none;
  white-space: nowrap;
}

.scope-tab:hover {
  color: var(--color-parchment);
  background: rgba(247, 236, 208, 0.06);
}

.scope-tab.active {
  color: var(--color-gold);
  background: linear-gradient(
    135deg,
    rgba(240, 199, 100, 0.25),
    rgba(240, 199, 100, 0.08)
  );
  box-shadow: inset 0 0 0 1px rgba(240, 199, 100, 0.4);
}

.scope-tab-icon {
  font-size: 10px;
  opacity: 0.5;
  transition: opacity 120ms ease;
}

.scope-tab.active .scope-tab-icon {
  opacity: 1;
}
</style>
