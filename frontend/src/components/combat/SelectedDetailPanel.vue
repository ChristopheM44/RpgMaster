<script setup lang="ts">
import { computed } from 'vue'
import { useGameStore } from '../../stores/game'
import { useCharacterStore } from '../../stores/character'
import type { Character } from '../../types'

const emit = defineEmits<{
  openSheet: [id: string]
}>()

const gameStore = useGameStore()
const charStore = useCharacterStore()

const combatant = computed(() =>
  gameStore.combatants.find((c) => c.id === gameStore.selectedCombatantId)
    ?? gameStore.activeCombatant
    ?? gameStore.combatants[0]
    ?? null,
)

const character = computed<Character | null>(() => {
  if (!combatant.value || combatant.value.kind !== 'pc') return null
  return charStore.sessionCharacters.find((c) => c.id === combatant.value?.id) ?? null
})

const abilityLabels: Record<string, string> = {
  strength: 'FOR',
  dexterity: 'DEX',
  constitution: 'CON',
  intelligence: 'INT',
  wisdom: 'SAG',
  charisma: 'CHA',
  str: 'FOR',
  dex: 'DEX',
  con: 'CON',
  int: 'INT',
  wis: 'SAG',
  cha: 'CHA',
}

function hpPct(cur: number, max: number): number {
  return Math.max(0, max > 0 ? (cur / max) * 100 : 0)
}

function mod(score: number): string {
  const value = Math.floor((score - 10) / 2)
  return value >= 0 ? `+${value}` : `${value}`
}

function weaponName(item: Record<string, unknown>): string {
  return String(item.name_fr ?? item.name ?? item.id ?? 'Arme')
}

const pcWeapons = computed(() => {
  const equipment = character.value?.equipment ?? []
  return equipment.filter((item) => {
    const category = String(item.category ?? '').toLowerCase()
    return category.includes('melee') || category.includes('ranged')
  }).slice(0, 4)
})
</script>

<template>
  <aside
    class="rpg-detail-panel flex w-[320px] shrink-0 flex-col overflow-y-auto border-l"
  >
    <div v-if="!combatant" class="flex flex-1 items-center justify-center p-6 text-center">
      <p class="rpg-text-muted font-serif italic text-sm">Aucun combattant sélectionné.</p>
    </div>

    <template v-else>
      <div
        class="rpg-detail-header rpg-border border-b p-5"
        :class="combatant.kind === 'monster' ? 'is-monster' : 'is-pc'"
        :style="combatant.kind === 'monster' && combatant.color
          ? { background: `linear-gradient(180deg, ${combatant.color}33, transparent)` }
          : undefined"
      >
        <div class="flex items-start gap-3">
          <div
            class="rpg-detail-token flex h-14 w-14 shrink-0 items-center justify-center rounded-lg border font-display text-lg font-bold text-white"
            :class="[
              combatant.kind === 'monster' ? 'is-monster' : 'is-pc',
              combatant.is_active ? 'is-active' : '',
            ]"
            :style="combatant.kind === 'monster' && combatant.color
              ? { '--rpg-token-color': combatant.color }
              : undefined"
          >
            {{ combatant.token ?? combatant.name.charAt(0).toUpperCase() }}
          </div>
          <div class="min-w-0 flex-1">
            <div class="rpg-eyebrow mb-1" :class="combatant.kind === 'monster' ? 'rpg-text-blood' : 'rpg-text-arcane-light'">
              {{ combatant.kind === 'monster' ? 'Créature' : 'Personnage' }}
            </div>
            <h2 class="truncate font-display text-xl font-bold text-parchment">{{ combatant.name }}</h2>
            <p class="rpg-text-muted truncate text-xs capitalize">
              <template v-if="combatant.kind === 'monster'">
                {{ combatant.species ?? 'monstre' }} · FP {{ combatant.cr ?? '—' }}
              </template>
              <template v-else-if="character">
                Niveau {{ character.level }} · {{ character.species }} {{ character.char_class }}
              </template>
            </p>
          </div>
        </div>

        <div class="mt-4 grid grid-cols-4 gap-2">
          <div class="rpg-detail-stat rounded border p-2 text-center">
            <div class="font-mono text-sm font-bold text-parchment">{{ combatant.hp_current }}/{{ combatant.hp_max }}</div>
            <div class="rpg-text-dim text-[9px] uppercase">PV</div>
          </div>
          <div class="rpg-detail-stat rounded border p-2 text-center">
            <div class="font-mono text-sm font-bold text-parchment">{{ combatant.ac }}</div>
            <div class="rpg-text-dim text-[9px] uppercase">CA</div>
          </div>
          <div class="rpg-detail-stat rounded border p-2 text-center">
            <div class="font-mono text-sm font-bold text-parchment">{{ combatant.initiative }}</div>
            <div class="rpg-text-dim text-[9px] uppercase">Init</div>
          </div>
          <div class="rpg-detail-stat rounded border p-2 text-center">
            <div class="font-mono text-sm font-bold text-parchment">{{ combatant.action_economy?.movement ?? 9 }}</div>
            <div class="rpg-text-dim text-[9px] uppercase">Vit</div>
          </div>
        </div>

        <div class="mt-3 h-2 overflow-hidden rounded-full bg-black/40">
          <div
            class="h-full rounded-full transition-all"
            :style="{ width: `${hpPct(combatant.hp_current, combatant.hp_max)}%`, background: combatant.hp_current > combatant.hp_max / 2 ? 'var(--color-green)' : 'var(--color-blood)' }"
          />
        </div>
      </div>

      <div class="space-y-5 p-5">
        <section v-if="combatant.kind === 'pc' && character">
          <div class="mb-2 flex items-center justify-between">
            <h3 class="rpg-eyebrow">Actions</h3>
            <button class="rpg-btn-secondary !py-1 !text-[10px]" @click="emit('openSheet', character.id)">Fiche</button>
          </div>
          <div class="space-y-2">
            <div
              v-for="item in pcWeapons"
              :key="String(item.id ?? weaponName(item))"
              class="rpg-detail-card rounded border px-3 py-2"
            >
              <div class="text-sm font-semibold text-parchment">{{ weaponName(item) }}</div>
              <div class="rpg-text-muted text-xs">
                {{ item.damage_dice ?? item.damage ?? 'Dégâts selon fiche' }}
              </div>
            </div>
            <p v-if="pcWeapons.length === 0" class="rpg-text-muted text-sm italic">Aucune arme listée.</p>
          </div>
        </section>

        <section v-if="combatant.kind === 'pc'">
          <h3 class="rpg-eyebrow mb-2">Économie</h3>
          <div class="grid grid-cols-3 gap-2">
            <div class="rpg-economy-box rounded border p-2 text-center text-xs" :class="{ 'is-available': combatant.action_economy?.action !== false }">Action</div>
            <div class="rpg-economy-box rounded border p-2 text-center text-xs" :class="{ 'is-available': combatant.action_economy?.bonus_action !== false }">Bonus</div>
            <div class="rpg-economy-box rounded border p-2 text-center text-xs" :class="{ 'is-available': combatant.action_economy?.reaction !== false }">Réaction</div>
          </div>
        </section>

        <section v-if="combatant.kind === 'monster'">
          <h3 class="rpg-eyebrow mb-2">Actions</h3>
          <div class="space-y-2">
            <div
              v-for="action in combatant.actions ?? []"
              :key="action.name"
              class="rpg-detail-card danger rounded border px-3 py-2"
            >
              <div class="flex items-center justify-between gap-2">
                <span class="text-sm font-semibold text-parchment">{{ action.name }}</span>
                <span class="rpg-text-gold font-mono text-xs">
                  {{ action.attack_bonus !== undefined ? `+${action.attack_bonus}` : '' }}
                </span>
              </div>
              <p class="rpg-text-muted mt-1 text-xs">
                {{ action.damage_dice ?? action.description ?? 'Action spéciale' }}
              </p>
            </div>
          </div>
        </section>

        <section v-if="combatant.conditions.length">
          <h3 class="rpg-eyebrow mb-2">Conditions</h3>
          <div class="flex flex-wrap gap-1.5">
            <span v-for="condition in combatant.conditions" :key="condition" class="rpg-chip rpg-tone-blood">{{ condition }}</span>
          </div>
        </section>

        <section v-if="combatant.kind === 'monster' && combatant.ability_scores">
          <h3 class="rpg-eyebrow mb-2">Caractéristiques</h3>
          <div class="grid grid-cols-3 gap-2">
            <div
              v-for="(score, ability) in combatant.ability_scores"
              :key="ability"
              class="rpg-detail-stat rounded border p-2 text-center"
            >
              <div class="rpg-text-dim text-[10px] uppercase">{{ abilityLabels[ability] ?? ability }}</div>
              <div class="font-mono text-sm text-parchment">{{ score }} <span class="rpg-text-muted">{{ mod(score) }}</span></div>
            </div>
          </div>
        </section>

        <section v-if="combatant.description">
          <h3 class="rpg-eyebrow mb-2">Notes MJ</h3>
          <p class="rpg-text-muted text-sm leading-relaxed">{{ combatant.description }}</p>
        </section>
      </div>
    </template>
  </aside>
</template>
