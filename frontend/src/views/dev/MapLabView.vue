<script setup lang="ts">
// Banc d'essai carte (dev uniquement, route /dev/map-lab) : scènes figées —
// réelles et synthétiques — rendues par le vrai moteur 3D, sans backend ni LLM.
// Sert aux captures avant/après de la refonte visuelle (docs/plans/
// refonte-visuelle-cartes-2026-10.md). Changer de scène rejoue la transition :
// « Le Jardin pétrifié » → « Le Caveau du Codex » montre la continuité d'arrivée.
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Scene3DCanvas from '../../components/scene3d/Scene3DCanvas.vue'
import { buildSceneSpec } from '../../engine3d/adapters/sceneAdapter'
import type { PickResult } from '../../engine3d/types'
import { adaptScenePois } from '../../composables/useExplorationPois'
import { characterToHero } from '../../composables/useExplorationParty'
import { MAP_LAB_FIXTURES } from '../../dev/mapLab/fixtures.generated'
import type { ExHero } from '../../fixtures/exploration'

const route = useRoute()
const router = useRouter()

const currentId = ref(String(route.query.scene ?? MAP_LAB_FIXTURES[0]?.id ?? ''))
const selectedId = ref<string | null>(null)
const fixture = computed(() => MAP_LAB_FIXTURES.find((item) => item.id === currentId.value) ?? MAP_LAB_FIXTURES[0]!)

const heroes = computed<ExHero[]>(() => {
  const { scene, characters } = fixture.value
  const myId = characters.find((character) => !character.is_ai)?.id
  const row = Math.floor(scene.rows / 2)
  const startCol = Math.max(0, Math.floor((scene.cols - characters.length) / 2))
  return characters.map((character, index) =>
    characterToHero(character, scene.party_positions?.[character.id] ?? { col: startCol + index, row }, myId),
  )
})

const spec = computed(() => buildSceneSpec({
  scene: fixture.value.scene,
  heroes: heroes.value,
  pois: adaptScenePois(fixture.value.scene),
  selectedId: selectedId.value,
  highlightedIds: [],
}))

const stairs = computed(() => (fixture.value.scene.elements ?? []).filter((element) => element.kind === 'stairs'))

function show(id: string): void {
  selectedId.value = null
  currentId.value = id
  void router.replace({ query: { scene: id } })
}

function onPick(pick: PickResult): void {
  selectedId.value = pick.type === 'cell' ? null : pick.id
}
</script>

<template>
  <div class="map-lab">
    <aside class="map-lab-side">
      <span class="rpg-eyebrow">Banc d'essai carte</span>
      <nav class="map-lab-list" aria-label="Scènes de test">
        <button
          v-for="item in MAP_LAB_FIXTURES"
          :key="item.id"
          type="button"
          class="map-lab-item"
          :aria-pressed="item.id === fixture.id"
          @click="show(item.id)"
        >
          <span class="map-lab-item-title">{{ item.title }}</span>
          <span class="map-lab-item-source">{{ item.source }}</span>
        </button>
      </nav>

      <section v-if="stairs.length" class="map-lab-stairs">
        <span class="rpg-eyebrow">Escaliers</span>
        <ul>
          <li v-for="element in stairs" :key="element.id">
            <span class="map-lab-dir">{{ element.vertical_direction === 'down' ? '↓' : '↑' }}</span>
            {{ element.name }}
            <span class="map-lab-meta">{{ element.facing ?? '—' }} · {{ element.vertical_direction ?? '—' }}</span>
          </li>
        </ul>
      </section>

      <p v-if="fixture.scene.arrival" class="map-lab-meta">
        Arrivée : {{ fixture.scene.arrival.exit_id }} ({{ fixture.scene.arrival.facing }},
        {{ fixture.scene.arrival.vertical_direction }}) depuis {{ fixture.scene.arrival.from_scene_id }}
      </p>
    </aside>

    <main class="map-lab-stage">
      <Scene3DCanvas :spec="spec" @pick="onPick" />
    </main>
  </div>
</template>

<style scoped>
.map-lab {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: 12px;
  /* AppNav (56 px) au-dessus : la scène tient dans l'écran, bandeau d'arrivée compris. */
  height: calc(100vh - 56px);
  padding: 12px;
  background: var(--color-bg);
  color: var(--color-parchment);
}

.map-lab-side {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: 0;
  overflow-y: auto;
  padding: 12px;
  background: var(--color-bg-elev);
  border: 1px solid var(--color-border);
  border-radius: 10px;
}

.map-lab-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.map-lab-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px 10px;
  text-align: left;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  color: var(--color-parchment);
  cursor: pointer;
  transition: border-color 120ms ease, background 120ms ease;
}

.map-lab-item:hover {
  background: var(--color-surface-raised);
}

.map-lab-item[aria-pressed='true'] {
  border-color: var(--color-gold);
  box-shadow: inset 3px 0 0 var(--color-gold);
}

.map-lab-item-title {
  font: 600 13px/1.3 var(--font-body);
}

.map-lab-item-source,
.map-lab-meta {
  font: 400 10.5px/1.4 var(--font-mono);
  color: var(--color-text-muted);
  overflow-wrap: anywhere;
}

.map-lab-stairs ul {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin: 8px 0 0;
  padding: 0;
  list-style: none;
  font: 400 12px/1.35 var(--font-body);
}

.map-lab-dir {
  color: var(--color-gold);
  font-weight: 700;
}

.map-lab-stage {
  min-width: 0;
  min-height: 0;
}
</style>
