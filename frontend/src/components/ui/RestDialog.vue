<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import type { Character } from '../../types'

type RestMode = 'short' | 'long'

const props = defineProps<{
  characters: Character[]
}>()

const emit = defineEmits<{
  confirmShort: [spend: Record<string, number>]
  confirmLong: []
  cancel: []
}>()

const mode = ref<RestMode>('short')
const spend = ref<Record<string, number>>(initialSpend())

const spendTotal = computed(() =>
  Object.values(spend.value).reduce((sum, value) => sum + value, 0),
)

const canConfirm = computed(() => mode.value === 'long' || spendTotal.value > 0)

function hitDice(character: Character) {
  return character.hit_dice ?? { die: 8, total: character.level || 1, used: 0 }
}

function availableDice(character: Character) {
  const hd = hitDice(character)
  return Math.max(0, Number(hd.total ?? 0) - Number(hd.used ?? 0))
}

function missingHp(character: Character) {
  return Math.max(0, character.hp_max - character.hp_current)
}

function maxSpend(character: Character) {
  return missingHp(character) > 0 ? availableDice(character) : 0
}

function initialSpend() {
  return Object.fromEntries(
    props.characters.map((character) => [
      character.id,
      missingHp(character) > 0 && availableDice(character) > 0 ? 1 : 0,
    ]),
  )
}

function adjust(character: Character, delta: number) {
  const current = spend.value[character.id] ?? 0
  const next = Math.min(Math.max(0, current + delta), maxSpend(character))
  spend.value = { ...spend.value, [character.id]: next }
}

function confirm() {
  if (!canConfirm.value) return
  if (mode.value === 'long') {
    emit('confirmLong')
    return
  }
  const selected = Object.fromEntries(
    Object.entries(spend.value).filter(([, value]) => value > 0),
  )
  emit('confirmShort', selected)
}

function onEsc(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('cancel')
}

onMounted(() => window.addEventListener('keydown', onEsc))
onBeforeUnmount(() => window.removeEventListener('keydown', onEsc))
</script>

<template>
  <div
    class="rpg-modal-backdrop fixed inset-0 z-[60] flex items-center justify-center p-4"
    @click.self="emit('cancel')"
  >
    <section
      class="rpg-dialog-panel rpg-tone-teal w-[560px] max-w-full overflow-hidden rounded-[14px] border shadow-2xl"
      role="dialog"
      aria-modal="true"
    >
      <div class="rpg-dialog-bar h-[3px] w-full" />

      <div class="p-6">
        <div class="mb-5 flex items-center justify-between gap-4">
          <div>
            <div
              class="rpg-text-teal text-[10px] font-bold uppercase tracking-[0.24em]"
            >Repos</div>
            <h2
              class="rpg-text-main font-display text-[22px] font-bold"
            >Récupération du groupe</h2>
          </div>
          <button
            class="rpg-btn-secondary !h-9 !w-9 !p-0"
            type="button"
            aria-label="Fermer"
            @click="emit('cancel')"
          >×</button>
        </div>

        <div
          class="rpg-segmented mb-5 grid grid-cols-2 gap-2 rounded-lg border p-1"
        >
          <button
            type="button"
            class="rpg-text-muted rounded-md px-3 py-2 text-sm font-semibold"
            :class="mode === 'short' ? 'rpg-tone-teal rpg-tone-panel' : ''"
            @click="mode = 'short'"
          >Repos court</button>
          <button
            type="button"
            class="rpg-text-muted rounded-md px-3 py-2 text-sm font-semibold"
            :class="mode === 'long' ? 'rpg-tone-arcane rpg-tone-panel' : ''"
            @click="mode = 'long'"
          >Repos long</button>
        </div>

        <div v-if="mode === 'short'" class="space-y-2">
          <div
            v-for="character in characters"
            :key="character.id"
            class="rpg-mini-panel grid grid-cols-[1fr_auto] items-center gap-3 rounded-lg border px-4 py-3"
          >
            <div class="min-w-0">
              <div class="rpg-text-main truncate text-sm font-semibold">
                {{ character.name }}
              </div>
              <div class="rpg-text-muted mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs">
                <span>PV {{ character.hp_current }}/{{ character.hp_max }}</span>
                <span>d{{ hitDice(character).die }}</span>
                <span>{{ availableDice(character) }}/{{ hitDice(character).total }} dispo</span>
              </div>
            </div>

            <div class="flex items-center gap-2">
              <button
                type="button"
                class="rpg-btn-secondary !h-8 !w-8 !p-0"
                :disabled="(spend[character.id] ?? 0) <= 0"
                @click="adjust(character, -1)"
              >−</button>
              <div
                class="rpg-counter-box flex h-8 w-10 items-center justify-center rounded-md border font-mono text-sm"
              >{{ spend[character.id] ?? 0 }}</div>
              <button
                type="button"
                class="rpg-btn-secondary !h-8 !w-8 !p-0"
                :disabled="(spend[character.id] ?? 0) >= maxSpend(character)"
                @click="adjust(character, 1)"
              >+</button>
            </div>
          </div>
        </div>

        <div
          v-else
          class="rpg-mini-panel rpg-text-secondary rounded-lg border px-4 py-5 text-sm leading-relaxed"
        >
          Le groupe récupère tous ses points de vie, ses emplacements de sorts et ses dés de vie.
        </div>

        <div class="mt-6 flex gap-3">
          <button type="button" class="rpg-btn-secondary flex-1 justify-center" @click="emit('cancel')">
            Annuler
          </button>
          <button
            type="button"
            class="rpg-btn-primary flex-1 justify-center"
            :disabled="!canConfirm"
            @click="confirm"
          >
            Valider
          </button>
        </div>
      </div>
    </section>
  </div>
</template>
