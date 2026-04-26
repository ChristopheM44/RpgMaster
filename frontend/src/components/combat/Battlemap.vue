<script setup lang="ts">
import { computed } from 'vue'
import { useGameStore } from '../../stores/game'
import type { GridPosition } from '../../types'

const props = defineProps<{
  myCharacterId?: string
  isMyTurn?: boolean
  speedM?: number
}>()

const emit = defineEmits<{
  move: [col: number, row: number]
}>()

const gameStore = useGameStore()
const cellPx = 42

const cols = computed(() => gameStore.gridConfig?.cols ?? 10)
const rows = computed(() => gameStore.gridConfig?.rows ?? 8)
const cellSizeM = computed(() => gameStore.gridConfig?.cell_size_m ?? 1.5)

const cellMap = computed(() => {
  const map: Record<string, (typeof gameStore.combatants)[0]> = {}
  for (const combatant of gameStore.combatants) {
    if (combatant.position) map[`${combatant.position.col},${combatant.position.row}`] = combatant
  }
  return map
})

const myPos = computed((): GridPosition | null => {
  const me = gameStore.combatants.find((c) => c.id === props.myCharacterId)
  return me?.position ?? null
})

const reachableCells = computed((): Set<string> => {
  if (!props.isMyTurn || !myPos.value) return new Set()
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

function hpPct(cur: number, max: number): number {
  return Math.max(0, max > 0 ? (cur / max) * 100 : 0)
}

function tokenLabel(combatant: (typeof gameStore.combatants)[0]): string {
  if (combatant.token) return combatant.token
  return combatant.name.charAt(0).toUpperCase()
}

function tokenBackground(combatant: (typeof gameStore.combatants)[0]): string {
  if (combatant.kind === 'monster') {
    return `radial-gradient(circle at 35% 25%, rgba(255,255,255,0.28), ${combatant.color ?? 'var(--color-blood)'} 62%, rgba(0,0,0,0.8))`
  }
  if (combatant.kind === 'pc' && (combatant.is_ai_controlled ?? combatant.is_ai)) {
    return 'radial-gradient(circle at 35% 25%, rgba(255,255,255,0.25), var(--color-arcane) 58%, #7050b0)'
  }
  return 'radial-gradient(circle at 35% 25%, rgba(255,255,255,0.28), var(--color-arcane) 58%, var(--color-ember))'
}

function handleCellClick(col: number, row: number) {
  const combatant = cellMap.value[`${col},${row}`]
  if (combatant) {
    gameStore.setSelectedCombatant(combatant.id)
    return
  }
  if (reachableCells.value.has(`${col},${row}`)) emit('move', col, row)
}
</script>

<template>
  <section class="flex min-h-0 flex-1 flex-col overflow-hidden">
    <div class="flex items-center justify-between border-b px-4 py-3" :style="{ borderColor: 'var(--color-border)' }">
      <div>
        <div class="rpg-eyebrow" :style="{ color: 'var(--color-gold)' }">Battlemap</div>
        <div class="mt-1 text-xs" :style="{ color: 'var(--color-text-muted)' }">
          {{ cols * cellSizeM }} × {{ rows * cellSizeM }} m
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
          background: `
            radial-gradient(circle at 78% 42%, rgba(247,199,107,0.16), transparent 13%),
            radial-gradient(circle at 35% 35%, rgba(192,144,255,0.08), transparent 30%),
            linear-gradient(180deg, rgba(78,49,36,0.42), rgba(21,19,25,0.98))
          `,
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
        <div class="pointer-events-none absolute left-[18%] top-[20%] text-lg text-parchment/20">▲</div>
        <div class="pointer-events-none absolute right-[28%] bottom-[22%] text-xl text-parchment/20">▲</div>
        <div class="pointer-events-none absolute right-[14%] top-[38%] h-16 w-16 rounded-full border border-gold/20 shadow-[0_0_28px_rgba(247,199,107,0.22)]" />

        <div
          v-for="cell in gridCells"
          :key="`${cell.col},${cell.row}`"
          class="absolute flex items-center justify-center"
          :class="{ 'cursor-pointer': reachableCells.has(`${cell.col},${cell.row}`) || cellMap[`${cell.col},${cell.row}`] }"
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
