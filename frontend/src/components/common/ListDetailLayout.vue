<script setup lang="ts">
/**
 * ListDetailLayout — Layout partagé deux colonnes
 * Sidebar (filtres + liste scrollable) | Panneau détail
 */
defineProps<{
  /** Largeur du sidebar en px */
  sidebarWidth?: number;
}>();
</script>

<template>
  <div class="list-detail-layout">
    <!-- Sidebar -->
    <aside
      class="list-detail-sidebar"
      :style="{ width: (sidebarWidth ?? 360) + 'px' }"
    >
      <!-- Header : search + filtres -->
      <div class="list-detail-sidebar-header">
        <slot name="header"></slot>
      </div>

      <!-- Compteur de résultats -->
      <div class="list-detail-count">
        <slot name="count"></slot>
      </div>

      <!-- Liste scrollable -->
      <div class="list-detail-sidebar-list">
        <slot name="list"></slot>
      </div>
    </aside>

    <!-- Panneau détail -->
    <main class="list-detail-main">
      <slot name="detail"></slot>
    </main>
  </div>
</template>

<style scoped>
.list-detail-layout {
  display: flex;
  flex: 1;
  min-height: 0;
}

.list-detail-sidebar {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--color-border);
  background: var(--color-bg-elev);
}

.list-detail-sidebar-header {
  padding: 16px 14px 0;
  flex-shrink: 0;
}

.list-detail-count {
  padding: 6px 14px 8px;
  font-size: 10px;
  color: var(--color-text-dim);
  font-family: var(--font-mono);
  border-bottom: 1px solid var(--color-border);
  flex-shrink: 0;
}

.list-detail-sidebar-list {
  flex: 1;
  overflow-y: auto;
}

.list-detail-main {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}
</style>
