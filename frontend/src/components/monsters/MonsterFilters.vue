<script setup lang="ts">
import { useMonsterStore } from '@/stores/useMonsterStore';
import { storeToRefs } from 'pinia';

const store = useMonsterStore();
const {
  search,
  crFilter,
  typeFilter,
  sizeFilter,
  activeFilterCount,
  availableCRs,
  availableTypes,
  availableSizes,
} = storeToRefs(store);
</script>

<template>
  <div class="monster-filters">
    <!-- Recherche -->
    <div class="monster-search-wrap">
      <span class="monster-search-icon">◉</span>
      <input
        v-model="search"
        type="text"
        placeholder="Rechercher un monstre…"
        class="rpg-mini-select monster-search-input"
      />
    </div>

    <!-- Selects -->
    <div class="monster-filter-row">
      <select v-model="crFilter" class="rpg-mini-select">
        <option value="">FP</option>
        <option v-for="cr in availableCRs" :key="cr" :value="cr">FP {{ cr }}</option>
      </select>

      <select v-model="typeFilter" class="rpg-mini-select">
        <option value="">Type</option>
        <option v-for="t in availableTypes" :key="t" :value="t">{{ t }}</option>
      </select>

      <select v-model="sizeFilter" class="rpg-mini-select">
        <option value="">Taille</option>
        <option v-for="s in availableSizes" :key="s" :value="s">{{ s }}</option>
      </select>
    </div>

    <!-- Effacer -->
    <div class="monster-filter-actions">
      <span class="monster-filter-spacer"></span>
      <button
        v-if="activeFilterCount > 0"
        class="monster-clear-btn"
        @click="store.clearFilters()"
      >Effacer les filtres</button>
    </div>
  </div>
</template>

<style scoped>
.monster-filters {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-bottom: 10px;
}

.monster-search-wrap {
  position: relative;
  margin-bottom: 2px;
}
.monster-search-icon {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--color-text-dim);
  font-size: 13px;
  pointer-events: none;
}
.monster-search-input {
  width: 100%;
  padding: 8px 12px 8px 30px !important;
  font-size: 13px !important;
}

.monster-filter-row {
  display: flex;
  gap: 6px;
  padding: 0 14px;
}
.monster-filter-row .rpg-mini-select {
  flex: 1;
  min-width: 0;
}

.monster-filter-actions {
  display: flex;
  gap: 6px;
  align-items: center;
  padding: 0 14px;
}
.monster-filter-spacer {
  flex: 1;
}
.monster-clear-btn {
  font-size: 10px;
  color: var(--color-text-dim);
  background: none;
  border: none;
  cursor: pointer;
  text-decoration: underline;
}
</style>
