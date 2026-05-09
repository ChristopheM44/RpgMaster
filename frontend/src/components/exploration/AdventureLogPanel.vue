<script setup lang="ts">
import AdventureJournal from '../journal/AdventureJournal.vue'
import CollapsibleSection from './CollapsibleSection.vue'
import PartySection from './PartySection.vue'
import QuestsSection from './QuestsSection.vue'
import MemorySection from './MemorySection.vue'

defineEmits<{
  openSheet: [id: string]
}>()
</script>

<template>
  <aside
    class="rpg-bg-elev flex w-[380px] shrink-0 min-h-0 flex-col overflow-y-auto"
  >
    <!-- Journal header (fixed identity of the panel) -->
    <AdventureJournal />

    <!-- Le groupe -->
    <CollapsibleSection id="group" eyebrow="✦ Le groupe">
      <PartySection @open-sheet="(id) => $emit('openSheet', id)" />
    </CollapsibleSection>

    <!-- Quêtes -->
    <QuestsSection />

    <!-- Carnet du chroniqueur -->
    <MemorySection />
  </aside>
</template>
