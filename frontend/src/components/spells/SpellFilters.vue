<script setup lang="ts">
import { SPELL_SCHOOLS, SPELL_CLASSES } from '@/types/library';
import { useSpellStore } from '@/stores/useSpellStore';
import { storeToRefs } from 'pinia';

const store = useSpellStore();
const {
  search,
  levelFilter,
  schoolFilter,
  classFilter,
  concentrationOnly,
  ritualOnly,
  activeFilterCount,
  availableLevels,
} = storeToRefs(store);

const levelLabels: Record<number, string> = {
  0: 'Cantrip', 1: 'Niv. 1', 2: 'Niv. 2', 3: 'Niv. 3',
  4: 'Niv. 4', 5: 'Niv. 5', 6: 'Niv. 6', 7: 'Niv. 7',
  8: 'Niv. 8', 9: 'Niv. 9',
};
</script>

<template>
  <div class="spell-filters">
    <!-- Recherche -->
    <div class="spell-search-wrap">
      <span class="spell-search-icon">◉</span>
      <input
        v-model="search"
        type="text"
        placeholder="Rechercher un sort…"
        class="rpg-mini-select spell-search-input"
      />
    </div>

    <!-- Selects -->
    <div class="spell-filter-row">
      <select v-model.number="levelFilter" class="rpg-mini-select">
        <option :value="null">Niveau</option>
        <option
          v-for="l in availableLevels"
          :key="l"
          :value="l"
        >{{ levelLabels[l] ?? `Niv. ${l}` }}</option>
      </select>

      <select v-model="schoolFilter" class="rpg-mini-select">
        <option value="">École</option>
        <option v-for="s in SPELL_SCHOOLS" :key="s" :value="s">{{ s }}</option>
      </select>

      <select v-model="classFilter" class="rpg-mini-select">
        <option value="">Classe</option>
        <option v-for="c in SPELL_CLASSES" :key="c" :value="c">{{ c }}</option>
      </select>
    </div>

    <!-- Toggles + effacer -->
    <div class="spell-filter-toggles">
      <button
        class="rpg-toggle-chip"
        :class="{ active: concentrationOnly }"
        @click="concentrationOnly = !concentrationOnly"
      >◉ Concentration</button>

      <button
        class="rpg-toggle-chip"
        :class="{ active: ritualOnly, arcane: ritualOnly }"
        @click="ritualOnly = !ritualOnly"
      >◈ Rituel</button>

      <span class="spell-filter-spacer"></span>

      <button
        v-if="activeFilterCount > 0"
        class="spell-clear-btn"
        @click="store.clearFilters()"
      >Effacer</button>
    </div>
  </div>
</template>

<style scoped>
.spell-filters {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-bottom: 10px;
}

.spell-search-wrap {
  position: relative;
  margin-bottom: 2px;
}
.spell-search-icon {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--color-text-dim);
  font-size: 13px;
  pointer-events: none;
}
.spell-search-input {
  width: 100%;
  padding: 8px 12px 8px 30px !important;
  font-size: 13px !important;
}

.spell-filter-row {
  display: flex;
  gap: 6px;
  padding: 0 14px;
}
.spell-filter-row .rpg-mini-select {
  flex: 1;
  min-width: 0;
}

.spell-filter-toggles {
  display: flex;
  gap: 6px;
  align-items: center;
  padding: 0 14px;
}
.spell-filter-spacer {
  flex: 1;
}
.spell-clear-btn {
  font-size: 10px;
  color: var(--color-text-dim);
  background: none;
  border: none;
  cursor: pointer;
  text-decoration: underline;
}
</style>
