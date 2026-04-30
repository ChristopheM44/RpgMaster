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
    class="fixed inset-0 z-[60] flex items-center justify-center p-4"
    :style="{ background: 'rgba(7, 6, 12, 0.72)', backdropFilter: 'blur(6px)' }"
    @click.self="emit('cancel')"
  >
    <section
      class="w-[560px] max-w-full overflow-hidden rounded-[14px] border shadow-2xl"
      :style="{
        background: 'linear-gradient(180deg, var(--color-bg-elev), var(--color-bg))',
        borderColor: 'var(--color-border-strong)',
      }"
      role="dialog"
      aria-modal="true"
    >
      <div
        class="h-[3px] w-full"
        :style="{ background: 'linear-gradient(90deg, transparent, var(--color-teal), transparent)' }"
      />

      <div class="p-6">
        <div class="mb-5 flex items-center justify-between gap-4">
          <div>
            <div
              class="text-[10px] font-bold uppercase tracking-[0.24em]"
              :style="{ color: 'var(--color-teal)' }"
            >Repos</div>
            <h2
              class="font-display text-[22px] font-bold"
              :style="{ color: 'var(--color-parchment)' }"
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
          class="mb-5 grid grid-cols-2 gap-2 rounded-lg border p-1"
          :style="{ borderColor: 'var(--color-border)', background: 'rgba(255,255,255,0.02)' }"
        >
          <button
            type="button"
            class="rounded-md px-3 py-2 text-sm font-semibold"
            :style="mode === 'short'
              ? { background: 'rgba(79,216,192,0.16)', color: 'var(--color-teal)' }
              : { color: 'var(--color-text-muted)' }"
            @click="mode = 'short'"
          >Repos court</button>
          <button
            type="button"
            class="rounded-md px-3 py-2 text-sm font-semibold"
            :style="mode === 'long'
              ? { background: 'rgba(192,144,255,0.16)', color: 'var(--color-arcane-light)' }
              : { color: 'var(--color-text-muted)' }"
            @click="mode = 'long'"
          >Repos long</button>
        </div>

        <div v-if="mode === 'short'" class="space-y-2">
          <div
            v-for="character in characters"
            :key="character.id"
            class="grid grid-cols-[1fr_auto] items-center gap-3 rounded-lg border px-4 py-3"
            :style="{ borderColor: 'var(--color-border)', background: 'var(--color-surface)' }"
          >
            <div class="min-w-0">
              <div class="truncate text-sm font-semibold" :style="{ color: 'var(--color-parchment)' }">
                {{ character.name }}
              </div>
              <div class="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs" :style="{ color: 'var(--color-text-muted)' }">
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
                class="flex h-8 w-10 items-center justify-center rounded-md border font-mono text-sm"
                :style="{ borderColor: 'var(--color-border)', color: 'var(--color-parchment)' }"
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
          class="rounded-lg border px-4 py-5 text-sm leading-relaxed"
          :style="{
            borderColor: 'var(--color-border)',
            background: 'var(--color-surface)',
            color: 'var(--color-parchment-dark)',
          }"
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
