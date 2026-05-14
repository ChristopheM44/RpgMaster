<script setup lang="ts">
/**
 * SpellsView — Page /grimoire
 * Catalogue complet des sorts avec recherche multi-critères et fiche détaillée.
 */
import { onMounted } from 'vue';
import { storeToRefs } from 'pinia';
import { useSpellStore } from '@/stores/useSpellStore';
import { LEVEL_LABELS } from '@/types/library';
import ListDetailLayout from '@/components/common/ListDetailLayout.vue';
import SpellFilters from '@/components/spells/SpellFilters.vue';
import SpellListItem from '@/components/spells/SpellListItem.vue';
import SpellDetail from '@/components/spells/SpellDetail.vue';

const store = useSpellStore();
const { filtered, grouped, selected } = storeToRefs(store);

onMounted(() => {
  if (store.spells.length === 0) {
    store.fetchSpells();
  }
});
</script>

<template>
  <ListDetailLayout>
    <!-- Filtres -->
    <template #header>
      <SpellFilters />
    </template>

    <!-- Compteur -->
    <template #count>
      {{ filtered.length }} sort{{ filtered.length > 1 ? 's' : '' }}
      trouvé{{ filtered.length > 1 ? 's' : '' }}
    </template>

    <!-- Liste groupée par niveau -->
    <template #list>
      <div v-if="grouped.length === 0" class="list-empty">
        Aucun sort ne correspond
      </div>

      <div v-for="group in grouped" :key="group.level">
        <!-- En-tête de groupe -->
        <div class="rpg-group-header">
          {{ LEVEL_LABELS[group.level] }}
          <span class="group-count">({{ group.items.length }})</span>
        </div>

        <!-- Items -->
        <SpellListItem
          v-for="spell in group.items"
          :key="spell.id"
          :spell="spell"
          :selected="spell.id === store.selectedId"
          @select="store.select(spell.id)"
        />
      </div>
    </template>

    <!-- Panneau détail -->
    <template #detail>
      <SpellDetail :spell="selected" />
    </template>
  </ListDetailLayout>
</template>

<style scoped>
.list-empty {
  padding: 32px;
  text-align: center;
  color: var(--color-text-dim);
  font-size: 13px;
  font-family: var(--font-serif);
  font-style: italic;
}

.group-count {
  margin-left: 8px;
  font-family: var(--font-mono);
  font-size: 9px;
  color: var(--color-text-dim);
}
</style>
