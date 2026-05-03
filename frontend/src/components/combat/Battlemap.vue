<script setup lang="ts">
import { computed } from 'vue'
import { useCharacterStore } from '../../stores/character'
import { useGameStore } from '../../stores/game'
import type { CombatantState, GridPosition, PointOfInterest, SceneExit, SceneLayout } from '../../types'

const props = withDefaults(defineProps<{
  mode?: 'combat' | 'exploration'
  sceneLayout?: SceneLayout | null
  myCharacterId?: string
  isMyTurn?: boolean
  speedM?: number
}>(), {
  mode: 'combat',
  sceneLayout: null,
})

const emit = defineEmits<{
  move: [col: number, row: number]
  sceneExit: [exitId: string, label: string]
}>()

const gameStore = useGameStore()
const charStore = useCharacterStore()
const cellPx = 42

const isExploration = computed(() => props.mode === 'exploration')
const activeScene = computed(() => props.sceneLayout ?? gameStore.currentScene)

const cols = computed(() => isExploration.value ? activeScene.value?.cols ?? 8 : gameStore.gridConfig?.cols ?? 10)
const rows = computed(() => isExploration.value ? activeScene.value?.rows ?? 8 : gameStore.gridConfig?.rows ?? 8)
const cellSizeM = computed(() => isExploration.value ? activeScene.value?.cell_size_m ?? 1.5 : gameStore.gridConfig?.cell_size_m ?? 1.5)
const mapTitle = computed(() => isExploration.value ? 'Carte de scène' : 'Battlemap')
const terrainLabel = computed(() => activeScene.value?.terrain?.replaceAll('_', ' ') ?? 'lieu actuel')

const cellMap = computed(() => {
  const map: Record<string, CombatantState> = {}
  if (isExploration.value) return map
  for (const combatant of gameStore.combatants) {
    if (combatant.position) map[`${combatant.position.col},${combatant.position.row}`] = combatant
  }
  return map
})

const exitMap = computed(() => {
  const map: Record<string, SceneExit> = {}
  for (const exit of activeScene.value?.exits ?? []) {
    if (exit.position) map[`${exit.position.col},${exit.position.row}`] = exit
  }
  return map
})

const poiMarkers = computed(() => activeScene.value?.pois ?? [])
const exitMarkers = computed(() => activeScene.value?.exits ?? [])

const partyMarkers = computed(() => {
  const positions = activeScene.value?.party_positions ?? {}
  return Object.entries(positions).map(([id, position]) => {
    const character = charStore.sessionCharacters.find((c) => c.id === id)
    const name = character?.name ?? id.replaceAll('_', ' ')
    return { id, name, position, token: tokenForName(name) }
  })
})

const myPos = computed((): GridPosition | null => {
  const me = gameStore.combatants.find((c) => c.id === props.myCharacterId)
  return me?.position ?? null
})

const reachableCells = computed((): Set<string> => {
  if (isExploration.value || !props.isMyTurn || !myPos.value) return new Set()
  const maxCells = Math.floor((props.speedM ?? 9) / cellSizeM.value)
  const result = new Set<string>()
  for (let row = 0; row < rows.value; row++) {
    for (let col = 0; col < cols.value; col++) {
      const key = `${col},${row}`
      if (cellMap.value[key]) continue
      const dist = Math.max(Math.abs(col - myPos.value.col), Math.abs(row - myPos.value.row))
      if (dist > 0 && dist <= maxCells) result.add(key)
    }
  }
  return result
})

const gridCells = computed(() =>
  Array.from({ length: rows.value * cols.value }, (_, index) => ({
    col: index % cols.value,
    row: Math.floor(index / cols.value),
  })),
)

const mapBackground = computed(() => {
  if (isExploration.value) {
    return `
      radial-gradient(circle at 52% 48%, rgba(247,199,107,0.18), transparent 16%),
      radial-gradient(circle at 78% 35%, rgba(90,138,111,0.18), transparent 24%),
      linear-gradient(180deg, rgba(63,55,44,0.68), rgba(20,22,21,0.98))
    `
  }
  return `
    radial-gradient(circle at 78% 42%, rgba(247,199,107,0.16), transparent 13%),
    radial-gradient(circle at 35% 35%, rgba(192,144,255,0.08), transparent 30%),
    linear-gradient(180deg, rgba(78,49,36,0.42), rgba(21,19,25,0.98))
  `
})

function hpPct(cur: number, max: number): number {
  return Math.max(0, max > 0 ? (cur / max) * 100 : 0)
}

function tokenLabel(combatant: CombatantState): string {
  if (combatant.token) return combatant.token
  return tokenForName(combatant.name)
}

function tokenForName(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  const letters = parts.length > 1 ? parts.map((p) => p[0]).join('') : name.slice(0, 2)
  return letters.toUpperCase()
}

function tokenBackground(combatant: CombatantState): string {
  if (combatant.kind === 'monster') {
    return `radial-gradient(circle at 35% 25%, rgba(255,255,255,0.28), ${combatant.color ?? 'var(--color-blood)'} 62%, rgba(0,0,0,0.8))`
  }
  if (combatant.kind === 'pc' && (combatant.is_ai_controlled ?? combatant.is_ai)) {
    return 'radial-gradient(circle at 35% 25%, rgba(255,255,255,0.25), var(--color-arcane) 58%, #7050b0)'
  }
  return 'radial-gradient(circle at 35% 25%, rgba(255,255,255,0.28), var(--color-arcane) 58%, var(--color-ember))'
}

function markerStyle(position: GridPosition) {
  const col = Math.max(0, Math.min(position.col, cols.value - 1))
  const row = Math.max(0, Math.min(position.row, rows.value - 1))
  return {
    left: `${col * cellPx + cellPx / 2}px`,
    top: `${row * cellPx + cellPx / 2}px`,
    transform: 'translate(-50%, -50%)',
  }
}

function poiGlyph(poi: PointOfInterest): string {
  const key = `${poi.icon ?? poi.kind}`.toLowerCase()
  if (key.includes('mist')) return '≋'
  if (key.includes('rubble') || key.includes('ruin')) return '▧'
  if (key.includes('lantern') || key.includes('light')) return '✦'
  if (key.includes('hazard')) return '!'
  if (key.includes('passage')) return '↗'
  if (key.includes('clue')) return '?'
  return '•'
}

function isInteractiveCell(col: number, row: number): boolean {
  const key = `${col},${row}`
  if (isExploration.value) return Boolean(exitMap.value[key])
  return reachableCells.value.has(key) || Boolean(cellMap.value[key])
}

function handleCellClick(col: number, row: number) {
  const key = `${col},${row}`
  if (isExploration.value) {
    const exit = exitMap.value[key]
    if (exit) emit('sceneExit', exit.id, exit.label)
    return
  }

  const combatant = cellMap.value[key]
  if (combatant) {
    gameStore.setSelectedCombatant(combatant.id)
    return
  }
  if (reachableCells.value.has(key)) emit('move', col, row)
}
</script>

<template>
  <section class="flex min-h-0 flex-1 flex-col overflow-hidden">
    <div class="flex items-center justify-between border-b px-4 py-3" :style="{ borderColor: 'var(--color-border)' }">
      <div>
        <div class="rpg-eyebrow" :style="{ color: 'var(--color-gold)' }">{{ mapTitle }}</div>
        <div class="mt-1 text-xs capitalize" :style="{ color: 'var(--color-text-muted)' }">
          {{ cols * cellSizeM }} × {{ rows * cellSizeM }} m
          <template v-if="isExploration"> · {{ terrainLabel }}</template>
        </div>
      </div>
      <div class="rounded border px-2 py-1 font-mono text-[11px]" :style="{ borderColor: 'rgba(247,199,107,0.25)', color: 'var(--color-gold)' }">
        A1
      </div>
    </div>

    <div class="flex min-h-0 flex-1 items-center justify-center overflow-auto p-5">
      <div
        class="relative overflow-hidden rounded border"
        :style="{
          width: `${cols * cellPx}px`,
          height: `${rows * cellPx}px`,
          borderColor: 'rgba(247,199,107,0.22)',
          background: mapBackground,
          boxShadow: 'inset 0 0 45px rgba(0,0,0,0.55), 0 14px 40px rgba(0,0,0,0.28)',
        }"
      >
        <svg class="pointer-events-none absolute inset-0 h-full w-full" aria-hidden="true">
          <defs>
            <pattern id="combat-grid" :width="cellPx" :height="cellPx" patternUnits="userSpaceOnUse">
              <path :d="`M ${cellPx} 0 L 0 0 0 ${cellPx}`" fill="none" stroke="rgba(255,235,180,0.08)" stroke-width="1" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#combat-grid)" />
        </svg>

        <div class="pointer-events-none absolute inset-x-0 top-0 h-7 bg-black/25" />
        <div class="pointer-events-none absolute inset-x-0 bottom-0 h-8 bg-black/30" />
        <div v-if="!isExploration" class="pointer-events-none absolute left-[18%] top-[20%] text-lg text-parchment/20">▲</div>
        <div v-if="!isExploration" class="pointer-events-none absolute right-[28%] bottom-[22%] text-xl text-parchment/20">▲</div>
        <div v-if="!isExploration" class="pointer-events-none absolute right-[14%] top-[38%] h-16 w-16 rounded-full border border-gold/20 shadow-[0_0_28px_rgba(247,199,107,0.22)]" />

        <template v-if="isExploration">
          <div
            v-for="poi in poiMarkers"
            :key="`poi-${poi.id}`"
            class="pointer-events-none absolute z-10 flex h-8 w-8 items-center justify-center rounded-lg border bg-black/45 text-sm font-bold text-gold shadow-[0_8px_18px_rgba(0,0,0,0.35)]"
            :style="{ ...markerStyle(poi.position), borderColor: 'rgba(247,199,107,0.32)' }"
            :title="poi.name"
          >
            {{ poiGlyph(poi) }}
          </div>

          <div
            v-for="exit in exitMarkers"
            :key="`exit-${exit.id}`"
            class="pointer-events-none absolute z-10 flex h-9 w-9 items-center justify-center rounded-full border text-sm font-bold text-teal-100 shadow-[0_0_18px_rgba(72,187,156,0.28)]"
            :style="{ ...markerStyle(exit.position), borderColor: 'rgba(72,187,156,0.55)', background: 'rgba(18,64,57,0.74)' }"
            :title="exit.label"
          >
            ↗
          </div>

          <div
            v-for="marker in partyMarkers"
            :key="`party-${marker.id}`"
            class="pointer-events-none absolute z-20 flex h-9 w-9 items-center justify-center rounded-full border text-[10px] font-bold text-white shadow-[0_8px_18px_rgba(0,0,0,0.42)]"
            :style="{
              ...markerStyle(marker.position),
              borderColor: marker.id === myCharacterId ? 'var(--color-gold)' : 'rgba(247,236,208,0.35)',
              background: 'radial-gradient(circle at 35% 25%, rgba(255,255,255,0.28), var(--color-arcane) 58%, var(--color-ember))',
            }"
            :title="marker.name"
          >
            {{ marker.token }}
          </div>
        </template>

        <div
          v-for="cell in gridCells"
          :key="`${cell.col},${cell.row}`"
          class="absolute flex items-center justify-center"
          :class="{ 'cursor-pointer': isInteractiveCell(cell.col, cell.row) }"
          :style="{ left: `${cell.col * cellPx}px`, top: `${cell.row * cellPx}px`, width: `${cellPx}px`, height: `${cellPx}px` }"
          @click="handleCellClick(cell.col, cell.row)"
        >
          <span
            v-if="reachableCells.has(`${cell.col},${cell.row}`)"
            class="h-5 w-5 rounded-full border border-gold/35 bg-gold/10 transition group-hover:bg-gold/20"
          />

          <div
            v-if="cellMap[`${cell.col},${cell.row}`]"
            class="relative flex h-9 w-9 items-center justify-center rounded-full border text-[11px] font-bold text-white transition-transform hover:scale-105"
            :style="{
              background: tokenBackground(cellMap[`${cell.col},${cell.row}`]!),
              borderColor: cellMap[`${cell.col},${cell.row}`]!.is_active
                ? 'var(--color-gold)'
                : cellMap[`${cell.col},${cell.row}`]!.id === gameStore.selectedCombatantId ? 'var(--color-parchment)' : 'rgba(247,236,208,0.28)',
              boxShadow: cellMap[`${cell.col},${cell.row}`]!.is_active
                ? '0 0 0 2px rgba(247,199,107,0.28), 0 0 18px rgba(247,199,107,0.45)'
                : cellMap[`${cell.col},${cell.row}`]!.id === gameStore.selectedCombatantId ? '0 0 0 2px rgba(247,236,208,0.22)' : '0 5px 14px rgba(0,0,0,0.35)',
            }"
            :title="cellMap[`${cell.col},${cell.row}`]!.name"
          >
            {{ tokenLabel(cellMap[`${cell.col},${cell.row}`]!) }}
            <span class="absolute -bottom-1.5 h-1 w-8 overflow-hidden rounded-full bg-black/70">
              <span
                class="block h-full rounded-full"
                :style="{
                  width: `${hpPct(cellMap[`${cell.col},${cell.row}`]!.hp_current, cellMap[`${cell.col},${cell.row}`]!.hp_max)}%`,
                  background: 'var(--color-green)',
                }"
              />
            </span>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>
