<script setup lang="ts">
// Banc d'essai carte (dev uniquement, route /dev/map-lab) : scènes figées —
// réelles et synthétiques — rendues par le vrai moteur 3D, sans backend ni LLM.
// Sert aux captures avant/après de la refonte visuelle (docs/plans/
// refonte-visuelle-cartes-2026-10.md). Changer de scène rejoue la transition :
// « Le Jardin pétrifié » → « Le Caveau du Codex » montre la continuité d'arrivée.
// Section « Cartes 2D » : Région et Ville (lot 5) sur leurs vraies données publiques.
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Scene3DCanvas from '../../components/scene3d/Scene3DCanvas.vue'
import { buildSceneSpec } from '../../engine3d/adapters/sceneAdapter'
import type { PickResult } from '../../engine3d/types'
import { adaptScenePois } from '../../composables/useExplorationPois'
import { characterToHero } from '../../composables/useExplorationParty'
import { MAP_LAB_FIXTURES } from '../../dev/mapLab/fixtures.generated'
import { MAP_LAB_WORLD_FIXTURES } from '../../dev/mapLab/worldFixtures.generated'
import type { ExHero } from '../../fixtures/exploration'
import RegionMap from '../../components/exploration/RegionMap.vue'
import TownMap from '../../components/exploration/TownMap.vue'
import { useGameStore } from '../../stores/game'

const route = useRoute()
const router = useRouter()

const gameStore = useGameStore()
const currentId = ref(String(route.query.scene ?? MAP_LAB_FIXTURES[0]?.id ?? ''))
/** Carte 2D affichée (null = scène 3D). */
const worldId = ref<string | null>(route.query.world ? String(route.query.world) : null)
const worldScope = ref<'region' | 'ville'>(route.query.scope === 'ville' ? 'ville' : 'region')
const world = computed(() => MAP_LAB_WORLD_FIXTURES.find((item) => item.id === worldId.value) ?? null)

watch(
  world,
  (value) => {
    if (!value) return
    gameStore.applyRegionMap(value.region_map)
    for (const city of Object.values(value.city_maps)) gameStore.applyCityMap(city)
    gameStore.applyCityMap({ city_map: value.active_city_id ? value.city_maps[value.active_city_id] ?? null : null, active_city_id: value.active_city_id })
  },
  { immediate: true },
)

function showWorld(id: string, scope: 'region' | 'ville'): void {
  worldId.value = id
  worldScope.value = scope
  void router.replace({ query: { world: id, scope } })
}
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
  worldId.value = null
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
          :aria-pressed="!world && item.id === fixture.id"
          @click="show(item.id)"
        >
          <span class="map-lab-item-title">{{ item.title }}</span>
          <span class="map-lab-item-source">{{ item.source }}</span>
        </button>
      </nav>

      <span class="rpg-eyebrow">Cartes 2D</span>
      <nav class="map-lab-list" aria-label="Cartes Région et Ville">
        <div v-for="item in MAP_LAB_WORLD_FIXTURES" :key="item.id" class="map-lab-item map-lab-world" :aria-pressed="world?.id === item.id">
          <span class="map-lab-item-title">{{ item.title }}</span>
          <span class="map-lab-item-source">{{ item.source }}</span>
          <span class="map-lab-world-actions">
            <button
              type="button"
              :aria-pressed="world?.id === item.id && worldScope === 'region'"
              @click="showWorld(item.id, 'region')"
            >Région</button>
            <button
              v-if="item.active_city_id"
              type="button"
              :aria-pressed="world?.id === item.id && worldScope === 'ville'"
              @click="showWorld(item.id, 'ville')"
            >Ville</button>
          </span>
        </div>
      </nav>

      <section v-if="!world && stairs.length" class="map-lab-stairs">
        <span class="rpg-eyebrow">Escaliers</span>
        <ul>
          <li v-for="element in stairs" :key="element.id">
            <span class="map-lab-dir">{{ element.vertical_direction === 'down' ? '↓' : '↑' }}</span>
            {{ element.name }}
            <span class="map-lab-meta">{{ element.facing ?? '—' }} · {{ element.vertical_direction ?? '—' }}</span>
          </li>
        </ul>
      </section>

      <p v-if="!world && fixture.scene.arrival" class="map-lab-meta">
        Arrivée : {{ fixture.scene.arrival.exit_id }} ({{ fixture.scene.arrival.facing }},
        {{ fixture.scene.arrival.vertical_direction }}) depuis {{ fixture.scene.arrival.from_scene_id }}
      </p>
    </aside>

    <main class="map-lab-stage">
      <TownMap v-if="world && worldScope === 'ville'" :key="`ville-${world.id}`" />
      <RegionMap v-else-if="world" :key="`region-${world.id}`" />
      <Scene3DCanvas v-else :spec="spec" @pick="onPick" />
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

.map-lab-world {
  cursor: default;
}

.map-lab-world-actions {
  display: flex;
  gap: 6px;
  margin-top: 4px;
}

.map-lab-world-actions button {
  padding: 2px 10px;
  border-radius: 6px;
  border: 1px solid var(--color-border-strong);
  background: transparent;
  color: var(--color-parchment-dark);
  font: 500 11px/1.4 var(--font-body);
  cursor: pointer;
  transition: color 120ms ease, border-color 120ms ease;
}

.map-lab-world-actions button[aria-pressed='true'],
.map-lab-world-actions button:hover {
  color: var(--color-gold);
  border-color: var(--color-gold);
}
</style>
