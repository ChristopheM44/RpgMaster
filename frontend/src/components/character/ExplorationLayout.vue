<script setup lang="ts">
import NarrativeLog from '../narrative/NarrativeLog.vue'
import AdventureLogPanel from '../exploration/AdventureLogPanel.vue'

defineEmits<{
  startCombat: []
  openSheet: [id: string]
}>()
</script>

<template>
  <div class="hidden min-h-0 flex-1 overflow-hidden md:flex">
    <section
      class="flex min-h-0 flex-1 flex-col overflow-hidden border-r"
      :style="{ borderColor: 'var(--color-border)' }"
    >
      <NarrativeLog />
    </section>

    <AdventureLogPanel @open-sheet="(id: string) => $emit('openSheet', id)" />
  </div>
</template>
