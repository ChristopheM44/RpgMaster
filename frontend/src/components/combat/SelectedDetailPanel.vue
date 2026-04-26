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
    class="flex w-[320px] shrink-0 flex-col overflow-y-auto border-l"
    :style="{ borderColor: 'var(--color-border)', background: 'var(--color-bg-elev)' }"
  >
    <div v-if="!combatant" class="flex flex-1 items-center justify-center p-6 text-center">
      <p class="font-serif italic text-sm" :style="{ color: 'var(--color-text-muted)' }">Aucun combattant sélectionné.</p>
    </div>

    <template v-else>
      <div
        class="border-b p-5"
        :style="{
          borderColor: 'var(--color-border)',
          background: combatant.kind === 'monster'
            ? `linear-gradient(180deg, ${combatant.color ?? 'rgba(232,69,69,0.25)'}33, transparent)`
            : 'linear-gradient(180deg, rgba(192,144,255,0.12), transparent)',
        }"
      >
        <div class="flex items-start gap-3">
          <div
            class="flex h-14 w-14 shrink-0 items-center justify-center rounded-lg border font-display text-lg font-bold text-white"
            :style="{
              background: combatant.kind === 'monster'
                ? `radial-gradient(circle at 35% 25%, rgba(255,255,255,0.24), ${combatant.color ?? 'var(--color-blood)'})`
                : 'linear-gradient(135deg, var(--color-arcane), var(--color-ember))',
              borderColor: combatant.is_active ? 'var(--color-gold)' : 'rgba(247,236,208,0.18)',
            }"
          >
            {{ combatant.token ?? combatant.name.charAt(0).toUpperCase() }}
          </div>
          <div class="min-w-0 flex-1">
            <div class="rpg-eyebrow mb-1" :style="{ color: combatant.kind === 'monster' ? 'var(--color-blood)' : 'var(--color-arcane-light)' }">
              {{ combatant.kind === 'monster' ? 'Créature' : 'Personnage' }}
            </div>
            <h2 class="truncate font-display text-xl font-bold text-parchment">{{ combatant.name }}</h2>
            <p class="truncate text-xs capitalize" :style="{ color: 'var(--color-text-muted)' }">
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
          <div class="rounded border p-2 text-center" :style="{ borderColor: 'rgba(247,236,208,0.1)' }">
            <div class="font-mono text-sm font-bold text-parchment">{{ combatant.hp_current }}/{{ combatant.hp_max }}</div>
            <div class="text-[9px] uppercase" :style="{ color: 'var(--color-text-dim)' }">PV</div>
          </div>
          <div class="rounded border p-2 text-center" :style="{ borderColor: 'rgba(247,236,208,0.1)' }">
            <div class="font-mono text-sm font-bold text-parchment">{{ combatant.ac }}</div>
            <div class="text-[9px] uppercase" :style="{ color: 'var(--color-text-dim)' }">CA</div>
          </div>
          <div class="rounded border p-2 text-center" :style="{ borderColor: 'rgba(247,236,208,0.1)' }">
            <div class="font-mono text-sm font-bold text-parchment">{{ combatant.initiative }}</div>
            <div class="text-[9px] uppercase" :style="{ color: 'var(--color-text-dim)' }">Init</div>
          </div>
          <div class="rounded border p-2 text-center" :style="{ borderColor: 'rgba(247,236,208,0.1)' }">
            <div class="font-mono text-sm font-bold text-parchment">{{ combatant.action_economy?.movement ?? 9 }}</div>
            <div class="text-[9px] uppercase" :style="{ color: 'var(--color-text-dim)' }">Vit</div>
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
              class="rounded border px-3 py-2"
              :style="{ borderColor: 'rgba(247,236,208,0.1)', background: 'rgba(255,255,255,0.025)' }"
            >
              <div class="text-sm font-semibold text-parchment">{{ weaponName(item) }}</div>
              <div class="text-xs" :style="{ color: 'var(--color-text-muted)' }">
                {{ item.damage_dice ?? item.damage ?? 'Dégâts selon fiche' }}
              </div>
            </div>
            <p v-if="pcWeapons.length === 0" class="text-sm italic" :style="{ color: 'var(--color-text-muted)' }">Aucune arme listée.</p>
          </div>
        </section>

        <section v-if="combatant.kind === 'pc'">
          <h3 class="rpg-eyebrow mb-2">Économie</h3>
          <div class="grid grid-cols-3 gap-2">
            <div class="rounded border p-2 text-center text-xs" :style="{ borderColor: combatant.action_economy?.action !== false ? 'rgba(111,217,111,0.35)' : 'rgba(247,236,208,0.1)' }">Action</div>
            <div class="rounded border p-2 text-center text-xs" :style="{ borderColor: combatant.action_economy?.bonus_action !== false ? 'rgba(111,217,111,0.35)' : 'rgba(247,236,208,0.1)' }">Bonus</div>
            <div class="rounded border p-2 text-center text-xs" :style="{ borderColor: combatant.action_economy?.reaction !== false ? 'rgba(111,217,111,0.35)' : 'rgba(247,236,208,0.1)' }">Réaction</div>
          </div>
        </section>

        <section v-if="combatant.kind === 'monster'">
          <h3 class="rpg-eyebrow mb-2">Actions</h3>
          <div class="space-y-2">
            <div
              v-for="action in combatant.actions ?? []"
              :key="action.name"
              class="rounded border px-3 py-2"
              :style="{ borderColor: 'rgba(232,69,69,0.22)', background: 'rgba(232,69,69,0.045)' }"
            >
              <div class="flex items-center justify-between gap-2">
                <span class="text-sm font-semibold text-parchment">{{ action.name }}</span>
                <span class="font-mono text-xs" :style="{ color: 'var(--color-gold)' }">
                  {{ action.attack_bonus !== undefined ? `+${action.attack_bonus}` : '' }}
                </span>
              </div>
              <p class="mt-1 text-xs" :style="{ color: 'var(--color-text-muted)' }">
                {{ action.damage_dice ?? action.description ?? 'Action spéciale' }}
              </p>
            </div>
          </div>
        </section>

        <section v-if="combatant.conditions.length">
          <h3 class="rpg-eyebrow mb-2">Conditions</h3>
          <div class="flex flex-wrap gap-1.5">
            <span v-for="condition in combatant.conditions" :key="condition" class="rpg-chip">{{ condition }}</span>
          </div>
        </section>

        <section v-if="combatant.kind === 'monster' && combatant.ability_scores">
          <h3 class="rpg-eyebrow mb-2">Caractéristiques</h3>
          <div class="grid grid-cols-3 gap-2">
            <div
              v-for="(score, ability) in combatant.ability_scores"
              :key="ability"
              class="rounded border p-2 text-center"
              :style="{ borderColor: 'rgba(247,236,208,0.1)' }"
            >
              <div class="text-[10px] uppercase" :style="{ color: 'var(--color-text-dim)' }">{{ abilityLabels[ability] ?? ability }}</div>
              <div class="font-mono text-sm text-parchment">{{ score }} <span :style="{ color: 'var(--color-text-muted)' }">{{ mod(score) }}</span></div>
            </div>
          </div>
        </section>

        <section v-if="combatant.description">
          <h3 class="rpg-eyebrow mb-2">Notes MJ</h3>
          <p class="text-sm leading-relaxed" :style="{ color: 'var(--color-text-muted)' }">{{ combatant.description }}</p>
        </section>
      </div>
    </template>
  </aside>
</template>
