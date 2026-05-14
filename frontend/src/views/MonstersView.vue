<script setup lang="ts">
/**
 * MonstersView — Page /bestiaire
 * Catalogue complet des monstres avec recherche multi-critères et bloc de stats.
 */
import { onMounted } from 'vue';
import { storeToRefs } from 'pinia';
import { useMonsterStore } from '@/stores/useMonsterStore';
import ListDetailLayout from '@/components/common/ListDetailLayout.vue';
import MonsterFilters from '@/components/monsters/MonsterFilters.vue';
import MonsterListItem from '@/components/monsters/MonsterListItem.vue';
import MonsterDetail from '@/components/monsters/MonsterDetail.vue';

const store = useMonsterStore();
const { filtered, grouped, selected } = storeToRefs(store);

onMounted(() => {
  if (store.monsters.length === 0) {
    store.fetchMonsters();
  }
});
</script>

<template>
  <ListDetailLayout>
    <!-- Filtres -->
    <template #header>
      <MonsterFilters />
    </template>

    <!-- Compteur -->
    <template #count>
      {{ filtered.length }} monstre{{ filtered.length > 1 ? 's' : '' }}
      trouvé{{ filtered.length > 1 ? 's' : '' }}
    </template>

    <!-- Liste groupée par FP -->
    <template #list>
      <div v-if="grouped.length === 0" class="list-empty">
        Aucun monstre ne correspond
      </div>

      <div v-for="group in grouped" :key="group.cr">
        <!-- En-tête de groupe -->
        <div class="rpg-group-header">
          FP {{ group.cr }}
          <span class="group-count">({{ group.items.length }})</span>
        </div>

        <!-- Items -->
        <MonsterListItem
          v-for="monster in group.items"
          :key="monster.id"
          :monster="monster"
          :selected="monster.id === store.selectedId"
          @select="store.select(monster.id)"
        />
      </div>
    </template>

    <!-- Panneau détail -->
    <template #detail>
      <MonsterDetail :monster="selected" />
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
