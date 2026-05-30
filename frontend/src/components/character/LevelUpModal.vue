<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Character } from '../../types'

export interface LevelUpResult {
  hp_gained: number
  asi_levels_granted: number[]
  new_level: number
  old_level: number
}

const props = defineProps<{
  characters: Character[]
  visible: boolean
  levelUpResult?: LevelUpResult | null
}>()

const emit = defineEmits<{
  asiChoice: [
    payload:
      | { characterId: string; mode: 'plus_two'; ability: string }
      | { characterId: string; mode: 'plus_one_two'; abilities: [string, string] },
  ]
  close: []
}>()

const ABILITIES: { key: string; label: string }[] = [
  { key: 'str', label: 'FOR' },
  { key: 'dex', label: 'DEX' },
  { key: 'con', label: 'CON' },
  { key: 'int', label: 'INT' },
  { key: 'wis', label: 'SAG' },
  { key: 'cha', label: 'CHA' },
]

// ASI_THRESHOLDS where proficiency bonus increases
const PROF_BONUS_THRESHOLDS: Record<number, number> = { 5: 3, 9: 4, 13: 5, 17: 6 }

const pending = computed(() => props.characters.find((c) => c.pending_asi) ?? null)
const asiMode = ref<'plus_two' | 'plus_one_two'>('plus_two')
const selectedA = ref<string | null>(null)
const selectedB = ref<string | null>(null)

const newProfBonus = computed(() => {
  const lv = props.levelUpResult?.new_level
  return lv ? PROF_BONUS_THRESHOLDS[lv] ?? null : null
})

function selectPlusTwo(ability: string) {
  if (!pending.value) return
  emit('asiChoice', { characterId: pending.value.id, mode: 'plus_two', ability })
}

function selectA(key: string) {
  selectedA.value = key
  if (selectedB.value === key) selectedB.value = null
}

function selectB(key: string) {
  if (key === selectedA.value) return
  selectedB.value = key
}

function confirmPlusOne() {
  if (!pending.value || !selectedA.value || !selectedB.value) return
  emit('asiChoice', {
    characterId: pending.value.id,
    mode: 'plus_one_two',
    abilities: [selectedA.value, selectedB.value],
  })
  selectedA.value = null
  selectedB.value = null
}

function resetAsiSelection() {
  asiMode.value = 'plus_two'
  selectedA.value = null
  selectedB.value = null
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="visible || pending"
      class="fixed inset-0 z-[70] flex items-center justify-center bg-black/70 p-4"
      style="backdrop-filter: blur(4px)"
    >
      <div class="level-up-card w-full max-w-md rounded-xl border p-6 shadow-2xl">

        <!-- Celebration glow decoration -->
        <div class="level-up-glow" aria-hidden="true" />

        <!-- Header -->
        <div class="rpg-eyebrow mb-1" style="color: var(--color-gold)">✦ MONTÉE DE NIVEAU</div>

        <template v-if="levelUpResult">
          <h2 class="font-display text-2xl font-bold tracking-wide" style="color: var(--color-parchment)">
            Niveau {{ levelUpResult.old_level }}
            <span style="color: var(--color-text-dim)">→</span>
            <span style="color: var(--color-gold)"> {{ levelUpResult.new_level }}</span>
          </h2>

          <!-- Gains summary -->
          <div class="mt-3 rounded-lg border px-4 py-3 space-y-1" style="border-color: var(--color-border); background: rgba(255,255,255,0.03)">
            <div class="flex items-center gap-2 text-sm">
              <span style="color: var(--color-green)">▲</span>
              <span style="color: var(--color-parchment-dark)">+{{ levelUpResult.hp_gained }} PV maximum</span>
            </div>
            <div v-if="newProfBonus" class="flex items-center gap-2 text-sm">
              <span style="color: var(--color-ember)">✦</span>
              <span style="color: var(--color-parchment-dark)">Bonus de maîtrise → +{{ newProfBonus }}</span>
            </div>
          </div>
        </template>

        <template v-else>
          <h2 class="font-display text-xl font-bold" style="color: var(--color-parchment)">
            Progression appliquée
          </h2>
          <p class="mt-2 text-sm" style="color: var(--color-text-muted)">
            PV, dés de vie et emplacements de sorts ont été mis à jour.
          </p>
        </template>

        <!-- ASI section -->
        <div v-if="pending" class="mt-5">
          <div class="mb-3">
            <div class="rpg-eyebrow mb-1" style="color: var(--color-arcane)">✦ AMÉLIORATION DE CARACTÉRISTIQUE</div>
            <p class="text-xs" style="color: var(--color-text-muted)">{{ pending.name }} — choisissez une amélioration</p>
          </div>

          <!-- Mode toggle -->
          <div class="mb-4 flex rounded-lg border overflow-hidden" style="border-color: var(--color-border)">
            <button
              class="flex-1 py-1.5 text-xs font-bold uppercase tracking-widest transition-colors"
              :style="{
                background: asiMode === 'plus_two' ? 'rgba(240,199,100,0.12)' : 'transparent',
                color: asiMode === 'plus_two' ? 'var(--color-gold)' : 'var(--color-text-muted)',
              }"
              @click="() => { asiMode = 'plus_two'; resetAsiSelection() }"
            >+2 une stat</button>
            <button
              class="flex-1 py-1.5 text-xs font-bold uppercase tracking-widest transition-colors border-l"
              :style="{
                borderColor: 'var(--color-border)',
                background: asiMode === 'plus_one_two' ? 'rgba(240,199,100,0.12)' : 'transparent',
                color: asiMode === 'plus_one_two' ? 'var(--color-gold)' : 'var(--color-text-muted)',
              }"
              @click="() => { asiMode = 'plus_one_two'; resetAsiSelection() }"
            >+1 deux stats</button>
          </div>

          <!-- Mode: +2 to one stat -->
          <template v-if="asiMode === 'plus_two'">
            <div class="grid grid-cols-3 gap-2">
              <button
                v-for="ab in ABILITIES"
                :key="ab.key"
                class="rpg-btn-secondary justify-center !py-1.5 !text-[11px]"
                @click="selectPlusTwo(ab.key)"
              >
                +2 {{ ab.label }}
                <span class="ml-1 font-mono opacity-60">{{ (pending.ability_scores?.[ab.key] ?? 10) }}</span>
              </button>
            </div>
          </template>

          <!-- Mode: +1 to two different stats -->
          <template v-else>
            <div class="space-y-3">
              <div>
                <p class="mb-1.5 text-[10px] font-bold uppercase tracking-wider" style="color: var(--color-text-muted)">Première stat</p>
                <div class="grid grid-cols-3 gap-1.5">
                  <button
                    v-for="ab in ABILITIES"
                    :key="ab.key"
                    class="rounded-lg border py-1.5 text-[11px] font-bold uppercase tracking-wide transition-all"
                    :style="{
                      borderColor: selectedA === ab.key ? 'var(--color-gold)' : 'var(--color-border)',
                      background: selectedA === ab.key ? 'rgba(240,199,100,0.15)' : 'rgba(255,255,255,0.03)',
                      color: selectedA === ab.key ? 'var(--color-gold)' : 'var(--color-parchment-dark)',
                    }"
                    @click="selectA(ab.key)"
                  >{{ ab.label }}</button>
                </div>
              </div>
              <div>
                <p class="mb-1.5 text-[10px] font-bold uppercase tracking-wider" style="color: var(--color-text-muted)">Deuxième stat</p>
                <div class="grid grid-cols-3 gap-1.5">
                  <button
                    v-for="ab in ABILITIES"
                    :key="ab.key"
                    class="rounded-lg border py-1.5 text-[11px] font-bold uppercase tracking-wide transition-all"
                    :disabled="ab.key === selectedA"
                    :style="{
                      borderColor: selectedB === ab.key ? 'var(--color-gold)' : 'var(--color-border)',
                      background: selectedB === ab.key ? 'rgba(240,199,100,0.15)' : (ab.key === selectedA ? 'transparent' : 'rgba(255,255,255,0.03)'),
                      color: ab.key === selectedA ? 'var(--color-text-dim)' : (selectedB === ab.key ? 'var(--color-gold)' : 'var(--color-parchment-dark)'),
                      opacity: ab.key === selectedA ? '0.3' : '1',
                      cursor: ab.key === selectedA ? 'not-allowed' : 'pointer',
                    }"
                    @click="selectB(ab.key)"
                  >{{ ab.label }}</button>
                </div>
              </div>
              <button
                class="rpg-btn-primary w-full justify-center"
                :disabled="!selectedA || !selectedB"
                :style="{ opacity: (!selectedA || !selectedB) ? '0.4' : '1' }"
                @click="confirmPlusOne"
              >
                Confirmer +1 {{ ABILITIES.find(a => a.key === selectedA)?.label ?? '?' }} · +1 {{ ABILITIES.find(a => a.key === selectedB)?.label ?? '?' }}
              </button>
            </div>
          </template>
        </div>

        <!-- Close button (only when no ASI pending) -->
        <button
          v-else
          class="rpg-btn-primary mt-5 w-full justify-center"
          @click="emit('close')"
        >
          Poursuivre l'aventure →
        </button>

      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.level-up-card {
  background: linear-gradient(180deg, #181623, #0e0d14);
  border-color: var(--color-border-strong);
  animation: rpg-dialog-in 200ms ease both;
  position: relative;
  overflow: hidden;
}

.level-up-glow {
  position: absolute;
  top: -40px;
  right: -40px;
  width: 200px;
  height: 200px;
  background: radial-gradient(circle, rgba(240,199,100,0.10) 0%, transparent 70%);
  pointer-events: none;
}
</style>
