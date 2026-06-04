<script setup lang="ts">
import { computed, ref, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useNarrativeStore } from '../../stores/narrative'
import NarrativeEntry from './NarrativeEntry.vue'
import type { ExNarrativeEntry } from '../../fixtures/exploration'

const emit = defineEmits<{ decide: [optionId: string] }>()

const narrativeStore = useNarrativeStore()
const scrollEl = ref<HTMLElement | null>(null)
const filterEl = ref<HTMLElement | null>(null)
const filterOpen = ref(false)

type NarrativeFilter = 'all' | 'story' | 'player' | 'dialogue' | 'roll' | 'combat' | 'system'

const activeFilter = ref<NarrativeFilter>('all')
const filterOptions: { id: NarrativeFilter; label: string }[] = [
  { id: 'all', label: 'Tout' },
  { id: 'story', label: 'Récit' },
  { id: 'player', label: 'Joueurs' },
  { id: 'dialogue', label: 'Dialogues' },
  { id: 'roll', label: 'Jets' },
  { id: 'combat', label: 'Combat' },
  { id: 'system', label: 'Système' },
]

const count = computed(() => narrativeStore.entries.length)
const visibleEntries = computed(() =>
  narrativeStore.entries.filter((entry) => matchesFilter(entry, activeFilter.value)),
)
const visibleCount = computed(() => visibleEntries.value.length)
const activeFilterLabel = computed(
  () => filterOptions.find((option) => option.id === activeFilter.value)?.label ?? 'Tout',
)
const headerCount = computed(() => (
  activeFilter.value === 'all'
    ? `${count.value} entrées`
    : `${visibleCount.value}/${count.value} entrées`
))
const filterCounts = computed<Record<NarrativeFilter, number>>(() => {
  const counts = Object.fromEntries(
    filterOptions.map((option) => [option.id, 0]),
  ) as Record<NarrativeFilter, number>

  for (const entry of narrativeStore.entries) {
    for (const option of filterOptions) {
      if (matchesFilter(entry, option.id)) counts[option.id] += 1
    }
  }
  return counts
})

function matchesFilter(entry: ExNarrativeEntry, filter: NarrativeFilter): boolean {
  if (filter === 'all') return true
  if (filter === 'story') return entry.type === 'gm' || entry.type === 'divider'
  if (filter === 'system') return entry.type === 'system'
  return entry.type === filter
}

function selectFilter(filter: NarrativeFilter) {
  activeFilter.value = filter
  filterOpen.value = false
}

function onClickOutside(e: MouseEvent) {
  if (!filterOpen.value) return
  if (filterEl.value && !filterEl.value.contains(e.target as Node)) {
    filterOpen.value = false
  }
}

// Auto-scroll vers la dernière entrée à chaque ajout
watch(count, async () => {
  await nextTick()
  if (scrollEl.value) {
    scrollEl.value.scrollTop = scrollEl.value.scrollHeight
  }
})

onMounted(() => {
  document.addEventListener('click', onClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', onClickOutside)
})
</script>

<template>
  <section class="narrative-column">
    <header class="narrative-header">
      <span class="narrative-header-icon">✦</span>
      <h2 class="narrative-header-title">Récit</h2>
      <span class="narrative-header-spacer" />
      <span class="narrative-header-count">{{ headerCount }}</span>
      <div ref="filterEl" class="narrative-filter-wrap">
        <button
          class="narrative-header-filter"
          :class="{ 'is-active': filterOpen || activeFilter !== 'all' }"
          type="button"
          title="Filtrer"
          aria-haspopup="menu"
          :aria-expanded="filterOpen"
          data-testid="narrative-filter-toggle"
          @click.stop="filterOpen = !filterOpen"
        >
          <span class="narrative-filter-glyph">⌕</span>
          <span>{{ activeFilter === 'all' ? 'Filtrer' : activeFilterLabel }}</span>
        </button>
        <div
          v-if="filterOpen"
          class="narrative-filter-menu"
          role="menu"
          data-testid="narrative-filter-menu"
        >
          <button
            v-for="option in filterOptions"
            :key="option.id"
            class="narrative-filter-option"
            :class="{ 'is-selected': activeFilter === option.id }"
            type="button"
            role="menuitemradio"
            :aria-checked="activeFilter === option.id"
            @click="selectFilter(option.id)"
          >
            <span>{{ option.label }}</span>
            <span class="narrative-filter-option-count">{{ filterCounts[option.id] }}</span>
          </button>
        </div>
      </div>
    </header>

    <div ref="scrollEl" class="narrative-scroll">
      <NarrativeEntry
        v-for="entry in visibleEntries"
        :key="entry.id"
        :entry="entry"
        @decide="(id: string) => emit('decide', id)"
      />
      <div v-if="visibleEntries.length === 0" class="narrative-empty">
        Aucune entrée
      </div>
    </div>
  </section>
</template>

<style scoped>
.narrative-column {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  background: linear-gradient(180deg, var(--color-bg-elev), rgba(24, 22, 35, 0.6));
}

.narrative-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 24px;
  border-bottom: 1px solid var(--color-border);
  flex-shrink: 0;
  height: 44px;
}

.narrative-header-icon {
  color: var(--color-ember);
  font-size: 13px;
}

.narrative-header-title {
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 700;
  color: var(--color-parchment);
  margin: 0;
  letter-spacing: 2px;
  text-transform: uppercase;
}

.narrative-header-spacer {
  flex: 1;
}

.narrative-header-count {
  font-size: 9px;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  white-space: nowrap;
}

.narrative-filter-wrap {
  position: relative;
  flex-shrink: 0;
}

.narrative-header-filter {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 8px;
  border-radius: 4px;
  background: transparent;
  border: 1px solid var(--color-border);
  color: var(--color-text-muted);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 1px;
  text-transform: uppercase;
  cursor: pointer;
  transition: color 120ms, border-color 120ms;
}

.narrative-header-filter:hover,
.narrative-header-filter.is-active {
  color: var(--color-parchment);
  border-color: var(--color-border-strong);
}

.narrative-header-filter.is-active {
  background: rgba(240, 199, 100, 0.10);
  color: var(--color-gold);
}

.narrative-filter-glyph {
  font-size: 11px;
  line-height: 1;
}

.narrative-filter-menu {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  z-index: 30;
  min-width: 178px;
  padding: 6px;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-md);
  background: var(--color-bg-elev);
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.6);
}

.narrative-filter-option {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 7px 8px;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-parchment-dark);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1px;
  text-align: left;
  text-transform: uppercase;
  cursor: pointer;
  transition: background 120ms, color 120ms;
}

.narrative-filter-option:hover,
.narrative-filter-option.is-selected {
  background: rgba(247, 236, 208, 0.08);
  color: var(--color-parchment);
}

.narrative-filter-option.is-selected {
  color: var(--color-gold);
}

.narrative-filter-option-count {
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 9px;
}

.narrative-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 8px 28px 16px;
  min-height: 0;
}

.narrative-empty {
  margin-top: 24px;
  color: var(--color-text-muted);
  font-family: var(--font-serif);
  font-size: 14px;
  font-style: italic;
  text-align: center;
}
</style>
