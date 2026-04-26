<script setup lang="ts">
import { computed } from 'vue'
import { useGameStore } from '../../stores/game'
import type { GridPosition, GridConfig } from '../../types'

const props = defineProps<{
  myCharacterId?: string
  isMyTurn?: boolean
  speedM?: number
}>()

const emit = defineEmits<{
  move: [col: number, row: number]
}>()

const gameStore = useGameStore()

const cols = computed(() => gameStore.gridConfig?.cols ?? 10)
const rows = computed(() => gameStore.gridConfig?.rows ?? 8)
const cellSizeM = computed(() => gameStore.gridConfig?.cell_size_m ?? 1.5)

const positionMap = computed(() => {
  const map: Record<string, GridPosition> = {}
  for (const c of gameStore.combatants) {
    if (c.position) map[c.id] = c.position
  }
  return map
})

const cellMap = computed(() => {
  const map: Record<string, (typeof gameStore.combatants)[0]> = {}
  for (const c of gameStore.combatants) {
    if (c.position) map[`${c.position.col},${c.position.row}`] = c
  }
  return map
})

const myPos = computed((): GridPosition | null => {
  if (!props.myCharacterId) return null
  return positionMap.value[props.myCharacterId] ?? null
})

const reachableCells = computed((): Set<string> => {
  if (!props.isMyTurn || !myPos.value) return new Set()
  const maxCells = Math.floor((props.speedM ?? 9) / cellSizeM.value)
  const result = new Set<string>()
  const p = myPos.value
  for (let r = 0; r < rows.value; r++) {
    for (let c = 0; c < cols.value; c++) {
      const key = `${c},${r}`
      if (cellMap.value[key]) continue
      const dist = Math.max(Math.abs(c - p.col), Math.abs(r - p.row))
      if (dist > 0 && dist <= maxCells) result.add(key)
    }
  }
  return result
})

// Build rows x cols grid as array of arrays for template iteration
const gridRows = computed(() =>
  Array.from({ length: rows.value }, (_, r) =>
    Array.from({ length: cols.value }, (_, c) => ({ col: c, row: r }))
  )
)

function cellClasses(col: number, row: number) {
  const key = `${col},${row}`
  const reachable = reachableCells.value.has(key)
  const checker = (col + row) % 2 === 0
  return [
    reachable ? 'bg-gold/10 cursor-pointer hover:bg-gold/25' : (checker ? 'bg-bg-elev' : 'bg-bg'),
    checker ? 'border-gold/30' : 'border-gold/15',
    'border transition-colors',
  ]
}

function tokenClasses(combatant: (typeof gameStore.combatants)[0]) {
  if (combatant.id === props.myCharacterId) return 'bg-arcane border-arcane/80 text-white'
  if (combatant.kind === 'pc' && (combatant.is_ai_controlled ?? combatant.is_ai)) return 'bg-arcane/90 border-arcane text-white'
  if (combatant.kind === 'pc') return 'bg-emerald-700 border-emerald-500 text-white'
  return 'bg-blood/90 border-blood text-white'
}

function handleCellClick(col: number, row: number) {
  if (reachableCells.value.has(`${col},${row}`)) {
    emit('move', col, row)
  }
}

function initials(name: string) {
  return name.split(' ').map((w) => w[0]).join('').slice(0, 2).toUpperCase()
}
</script>

<template>
  <div class="select-none">
    <div class="mb-1 flex items-center justify-between px-1">
      <span class="rpg-eyebrow">Carte tactique</span>
      <span class="text-xs text-parchment/30">
        {{ cols * cellSizeM }}×{{ rows * cellSizeM }} m
      </span>
    </div>

    <div class="overflow-auto rounded border border-gold/20">
      <div
        :style="{
          display: 'grid',
          gridTemplateColumns: `repeat(${cols}, 28px)`,
          width: `${cols * 28}px`,
        }"
      >
        <template v-for="rowCells in gridRows" :key="rowCells[0]!.row">
          <div
            v-for="cell in rowCells"
            :key="`${cell.col},${cell.row}`"
            class="relative flex items-center justify-center"
            :class="cellClasses(cell.col, cell.row)"
            style="width: 28px; height: 28px"
            @click="handleCellClick(cell.col, cell.row)"
          >
            <div
              v-if="cellMap[`${cell.col},${cell.row}`]"
              class="flex h-5 w-5 items-center justify-center rounded-full border font-bold"
              :class="tokenClasses(cellMap[`${cell.col},${cell.row}`]!)"
              :title="cellMap[`${cell.col},${cell.row}`]!.name"
              style="font-size: 7px; line-height: 1"
            >
              {{ initials(cellMap[`${cell.col},${cell.row}`]!.name) }}
            </div>
            <div
              v-if="cellMap[`${cell.col},${cell.row}`]?.is_active"
              class="pointer-events-none absolute inset-0 ring-1 ring-gold"
            />
          </div>
        </template>
      </div>
    </div>

    <div class="mt-1 flex flex-wrap gap-3 px-1">
      <div class="flex items-center gap-1">
        <div class="h-2.5 w-2.5 rounded-full bg-arcane border border-arcane/80" />
        <span class="text-xs text-parchment/40">Vous</span>
      </div>
      <div class="flex items-center gap-1">
        <div class="h-2.5 w-2.5 rounded-full bg-emerald-700 border border-emerald-500" />
        <span class="text-xs text-parchment/40">Allié</span>
      </div>
      <div class="flex items-center gap-1">
        <div class="h-2.5 w-2.5 rounded-full bg-blood/90 border border-blood" />
        <span class="text-xs text-parchment/40">Ennemi</span>
      </div>
      <div v-if="isMyTurn" class="flex items-center gap-1">
        <div class="h-2.5 w-2.5 rounded bg-gold/10 border border-gold/30" />
        <span class="text-xs text-parchment/40">Accessible</span>
      </div>
    </div>
  </div>
</template>
