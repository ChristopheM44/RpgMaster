<script setup lang="ts">
// V2 « Diptyque équilibré » — Map gauche 50% + Récit droite 50%
// Carnet ouvert via bouton dans la top bar de la map.
import { onMounted, onUnmounted } from 'vue'
import { useSessionStore } from '../../stores/session'
import { useExplorationPois } from '../../composables/useExplorationPois'
import MapColumn from './MapColumn.vue'
import NarrativeColumn from './NarrativeColumn.vue'
import BottomBar from './BottomBar.vue'

const emit = defineEmits<{
  action: [actionType: string, content?: string, targetId?: string, extra?: Record<string, unknown>]
  openSheet: [id: string]
}>()

const sessionStore = useSessionStore()
const { findPoi } = useExplorationPois()

function scenePoiExtra(
  poiId: string,
  interactionId?: string,
  intent?: string,
): Record<string, unknown> {
  return {
    scene_poi_id: poiId,
    ...(interactionId ? { scene_interaction_id: interactionId } : {}),
    ...(intent ? { scene_interaction_intent: intent } : {}),
  }
}

function onAct(id: string) {
  const poi = findPoi(id)
  if (!poi) return
  if (poi.kind === 'sortie') {
    sessionStore.moveParty(poi.dest ?? poi.id)
    emit('action', 'free_text', `Je me dirige vers ${poi.title}.`)
  } else {
    const content = poi.prompt
      ?? (poi.kind === 'npc'
        ? `Je parle à ${poi.title}.`
        : `J'examine : ${poi.title}${poi.dc ? ` (${poi.actionLabel ?? poi.skill ?? 'Examiner'} DD ${poi.dc})` : ''}.`)
    emit(
      'action',
      'free_text',
      content,
      poi.kind === 'npc' ? poi.id : undefined,
      scenePoiExtra(poi.id, poi.interactionId, poi.intent),
    )
  }
}

function onApproach(id: string) {
  const poi = findPoi(id)
  if (!poi || poi.kind === 'sortie') return
  emit(
    'action',
    'free_text',
    `Je m'approche de ${poi.title} pour mieux voir ce qu'il y a là-bas.`,
    undefined,
    scenePoiExtra(poi.id, undefined, 'approach'),
  )
}

function onDecide(optionId: string) {
  const poi = findPoi(optionId)
  if (!poi) return
  sessionStore.moveParty(poi.dest ?? poi.id)
  emit('action', 'free_text', `Le groupe décide : ${poi.title}.`)
}

function onKey(e: KeyboardEvent) {
  // 1 / 2 / 3 → scope
  if (e.key === '1') { sessionStore.setMapScope('scene'); return }
  if (e.key === '2') { sessionStore.setMapScope('ville'); return }
  if (e.key === '3') { sessionStore.setMapScope('region'); return }
  // Esc → ferme inspector ou popover
  if (e.key === 'Escape') {
    if (sessionStore.carnetOpen) sessionStore.toggleCarnet(false)
    else if (sessionStore.selectedId) sessionStore.selectEntity(null)
  }
}

onMounted(() => { document.addEventListener('keydown', onKey) })
onUnmounted(() => { document.removeEventListener('keydown', onKey) })
</script>

<template>
  <div class="exploration-v2">
    <div class="exploration-body">
      <MapColumn
        @act="onAct"
        @approach="onApproach"
        @open-sheet="(id) => emit('openSheet', id)"
      />
      <NarrativeColumn @decide="onDecide" />
    </div>

    <BottomBar
      @action="(actionType, content, targetId, extra) => emit('action', actionType, content, targetId, extra)"
    />
  </div>
</template>

<style scoped>
.exploration-v2 {
  display: flex;
  flex: 1;
  min-height: 0;
  flex-direction: column;
  overflow: hidden;
}

.exploration-body {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 1fr;
  min-height: 0;
  position: relative;
}

@media (max-width: 1280px) {
  :deep(.map-canvas),
  :deep(.narrative-scroll) { padding: 12px 16px; }
}
</style>
