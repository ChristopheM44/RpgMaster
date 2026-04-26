<script setup lang="ts">
import { ref, watch } from 'vue'
import NarrativeLog from '../narrative/NarrativeLog.vue'
import CharacterPanel from './CharacterPanel.vue'
import AdventureJournal from '../journal/AdventureJournal.vue'
import QuestPanel from '../journal/QuestPanel.vue'
import ChroniclersBook from '../journal/ChroniclersBook.vue'
import { useGameStore } from '../../stores/game'

defineEmits<{
  startCombat: []
  openSheet: [id: string]
}>()

type TabId = 'perso' | 'aventure' | 'chronique'

const activeTab = ref<TabId>('perso')
const dirtyTabs = ref(new Set<TabId>())

const gameStore = useGameStore()

function markDirty(tab: TabId) {
  if (activeTab.value !== tab) {
    dirtyTabs.value = new Set([...dirtyTabs.value, tab])
  }
}

watch(() => gameStore.adventureJournal, () => markDirty('aventure'))
watch(() => gameStore.quests.length, () => markDirty('aventure'))
watch(() => gameStore.chronicle.length, () => markDirty('chronique'))

function switchTab(tab: TabId) {
  activeTab.value = tab
  const next = new Set(dirtyTabs.value)
  next.delete(tab)
  dirtyTabs.value = next
}

const TABS: { id: TabId; label: string }[] = [
  { id: 'perso', label: 'Personnage' },
  { id: 'aventure', label: 'Aventure' },
  { id: 'chronique', label: 'Chronique' },
]
</script>

<template>
  <div class="hidden min-h-0 flex-1 overflow-hidden md:flex">
    <section
      class="flex min-h-0 flex-1 flex-col overflow-hidden border-r"
      :style="{ borderColor: 'var(--color-border)' }"
    >
      <NarrativeLog />
    </section>

    <aside
      class="flex w-[360px] shrink-0 min-h-0 flex-col overflow-hidden"
      :style="{ background: 'var(--color-bg-elev)' }"
    >
      <!-- Tab bar -->
      <div
        class="flex shrink-0 border-b"
        :style="{ borderColor: 'var(--color-border)' }"
      >
        <button
          v-for="tab in TABS"
          :key="tab.id"
          class="relative flex-1 cursor-pointer py-2.5 text-[10px] font-bold uppercase tracking-[0.12em] transition-colors"
          :style="{
            color: activeTab === tab.id ? 'var(--color-gold)' : 'var(--color-text-muted)',
            borderBottom: activeTab === tab.id ? '2px solid var(--color-gold)' : '2px solid transparent',
            background: 'transparent',
          }"
          @click="switchTab(tab.id)"
        >
          {{ tab.label }}
          <span
            v-if="dirtyTabs.has(tab.id)"
            class="absolute right-2 top-2 h-1.5 w-1.5 rounded-full"
            :style="{ background: 'var(--color-gold)' }"
          />
        </button>
      </div>

      <!-- Tab content -->
      <div class="flex min-h-0 flex-1 flex-col overflow-y-auto">
        <template v-if="activeTab === 'perso'">
          <CharacterPanel
            @start-combat="$emit('startCombat')"
            @open-sheet="(id: string) => $emit('openSheet', id)"
          />
        </template>

        <template v-if="activeTab === 'aventure'">
          <AdventureJournal />
          <div
            class="mx-5 shrink-0 border-t"
            :style="{ borderColor: 'var(--color-border)' }"
          />
          <QuestPanel />
        </template>

        <template v-if="activeTab === 'chronique'">
          <ChroniclersBook />
        </template>
      </div>
    </aside>
  </div>
</template>
