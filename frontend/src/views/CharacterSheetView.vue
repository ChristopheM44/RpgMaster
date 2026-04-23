<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { characterApi, srdApi } from '../services/api'
import type { Character, SrdClass, SrdSpell } from '../types'

const route = useRoute()
const router = useRouter()
const charId = route.params.charId as string
const sessionId = route.query.session as string | undefined

const character = ref<Character | null>(null)
const srdClass = ref<SrdClass | null>(null)
const spellDetails = ref<SrdSpell[]>([])
const loading = ref(true)
const error = ref<string | null>(null)

// ─── Skills mapping ────────────────────────────────────────────────────────────

const SKILLS: { id: string; name_fr: string; ability: string }[] = [
  { id: 'acrobatics', name_fr: 'Acrobaties', ability: 'dex' },
  { id: 'animal_handling', name_fr: 'Dressage', ability: 'wis' },
  { id: 'arcana', name_fr: 'Arcanes', ability: 'int' },
  { id: 'athletics', name_fr: 'Athlétisme', ability: 'str' },
  { id: 'deception', name_fr: 'Tromperie', ability: 'cha' },
  { id: 'history', name_fr: 'Histoire', ability: 'int' },
  { id: 'insight', name_fr: 'Intuition', ability: 'wis' },
  { id: 'intimidation', name_fr: 'Intimidation', ability: 'cha' },
  { id: 'investigation', name_fr: 'Investigation', ability: 'int' },
  { id: 'medicine', name_fr: 'Médecine', ability: 'wis' },
  { id: 'nature', name_fr: 'Nature', ability: 'int' },
  { id: 'perception', name_fr: 'Perception', ability: 'wis' },
  { id: 'performance', name_fr: 'Représentation', ability: 'cha' },
  { id: 'persuasion', name_fr: 'Persuasion', ability: 'cha' },
  { id: 'religion', name_fr: 'Religion', ability: 'int' },
  { id: 'sleight_of_hand', name_fr: 'Escamotage', ability: 'dex' },
  { id: 'stealth', name_fr: 'Discrétion', ability: 'dex' },
  { id: 'survival', name_fr: 'Survie', ability: 'wis' },
]

const ABILITY_LABELS: Record<string, { abbr: string; name_fr: string; save_abbr: string }> = {
  str: { abbr: 'FOR', name_fr: 'Force', save_abbr: 'FOR' },
  dex: { abbr: 'DEX', name_fr: 'Dextérité', save_abbr: 'DEX' },
  con: { abbr: 'CON', name_fr: 'Constitution', save_abbr: 'CON' },
  int: { abbr: 'INT', name_fr: 'Intelligence', save_abbr: 'INT' },
  wis: { abbr: 'SAG', name_fr: 'Sagesse', save_abbr: 'SAG' },
  cha: { abbr: 'CHA', name_fr: 'Charisme', save_abbr: 'CHA' },
}

const SPELL_SCHOOLS: Record<string, string> = {
  evocation: 'Évocation',
  conjuration: 'Invocation',
  abjuration: 'Abjuration',
  divination: 'Divination',
  enchantment: 'Enchantement',
  illusion: 'Illusion',
  necromancy: 'Nécromancie',
  transmutation: 'Transmutation',
}

// ─── Derived values ────────────────────────────────────────────────────────────

function abilityMod(score: number): number {
  return Math.floor((score - 10) / 2)
}

function fmtMod(val: number): string {
  return val >= 0 ? `+${val}` : `${val}`
}

const profBonus = computed((): number => {
  if (!character.value) return 2
  return Math.floor((character.value.level - 1) / 4) + 2
})

const scores = computed((): Record<string, number> => character.value?.ability_scores ?? {})

const mods = computed((): Record<string, number> =>
  Object.fromEntries(Object.entries(scores.value).map(([k, v]) => [k, abilityMod(v)])),
)

const skillProficiencies = computed((): string[] => {
  const p = character.value?.proficiencies as Record<string, unknown> | undefined
  return Array.isArray(p?.skills) ? (p!.skills as string[]) : []
})

const saveProficiencies = computed((): string[] => {
  const p = character.value?.proficiencies as Record<string, unknown> | undefined
  if (Array.isArray(p?.saving_throws)) return p!.saving_throws as string[]
  return srdClass.value?.saving_throw_proficiencies ?? []
})

function skillBonus(skill: { id: string; ability: string }): number {
  const base = mods.value[skill.ability] ?? 0
  return skillProficiencies.value.includes(skill.id) ? base + profBonus.value : base
}

function saveBonus(ability: string): number {
  const base = mods.value[ability] ?? 0
  return saveProficiencies.value.includes(ability) ? base + profBonus.value : base
}

const armorClass = computed((): number => {
  if (!character.value) return 10
  const equip = character.value.equipment as Record<string, unknown>[]
  const ARMOR_CATS = new Set(['light', 'medium', 'heavy'])
  const armor = equip.find((e) => e.equipped && ARMOR_CATS.has(e.category as string))
  const shield = equip.find((e) => e.equipped && e.category === 'shield')
  const shieldBonus = shield ? 2 : 0
  if (armor && typeof armor.base_ac === 'number') {
    const dexCap = armor.dex_cap
    const dexMod = mods.value.dex ?? 0
    const dexApplied = dexCap === null ? dexMod : Math.min(dexMod, dexCap as number)
    return armor.base_ac + dexApplied + shieldBonus
  }
  return 10 + (mods.value.dex ?? 0) + shieldBonus
})

const initiative = computed(() => mods.value.dex ?? 0)

const hpPercent = computed((): number => {
  if (!character.value || character.value.hp_max === 0) return 0
  return Math.max(0, Math.min(100, (character.value.hp_current / character.value.hp_max) * 100))
})

const hpColorVar = computed((): string => {
  const pct = hpPercent.value
  if (pct > 50) return 'var(--color-green)'
  if (pct > 25) return 'var(--color-gold)'
  return 'var(--color-blood)'
})

const isSpellcaster = computed((): boolean => {
  if (!character.value) return false
  return (
    (character.value.known_spells?.length ?? 0) > 0 ||
    Object.keys(character.value.spell_slots ?? {}).length > 0
  )
})

const spellSlotEntries = computed(() => {
  const slots = character.value?.spell_slots as Record<
    string,
    { total: number; used: number }
  > | undefined
  if (!slots) return []
  return Object.entries(slots)
    .map(([level, data]) => ({ level: Number(level), ...data }))
    .filter((s) => s.total > 0)
    .sort((a, b) => a.level - b.level)
})

const backgroundLabel = computed((): string => {
  const bg = character.value?.background
  if (!bg) return '—'
  const labels: Record<string, string> = {
    acolyte: 'Acolyte',
    criminal: 'Criminel',
    folk_hero: 'Héros du Peuple',
    noble: 'Noble',
    sage: 'Sage',
    soldier: 'Soldat',
  }
  return labels[bg] ?? bg
})

const personalityTraits = computed((): string[] => {
  const p = character.value?.personality as Record<string, unknown> | undefined
  if (!p) return []
  const result: string[] = []
  if (Array.isArray(p.traits)) result.push(...(p.traits as string[]))
  if (typeof p.bonds === 'string' && p.bonds) result.push(`Lien : ${p.bonds}`)
  if (typeof p.flaws === 'string' && p.flaws) result.push(`Défaut : ${p.flaws}`)
  return result
})

// ─── Load data ─────────────────────────────────────────────────────────────────

onMounted(async () => {
  try {
    character.value = await characterApi.get(charId)
    const promises: Promise<void>[] = [
      srdApi.getClass(character.value.char_class).then((c) => {
        srdClass.value = c
      }),
    ]
    if (character.value.known_spells?.length) {
      promises.push(
        srdApi.listSpells({ charClass: character.value.char_class }).then((res) => {
          const known = new Set(character.value!.known_spells)
          spellDetails.value = res.spells.filter((s) => known.has(s.id))
        }),
      )
    }
    await Promise.allSettled(promises)
  } catch {
    error.value = 'Impossible de charger la fiche de personnage.'
  } finally {
    loading.value = false
  }
})

function goBack() {
  if (sessionId) router.push({ name: 'game-session', params: { id: sessionId } })
  else router.back()
}

// ─── Inventory actions ─────────────────────────────────────────────────────────

const inventoryLoading = ref<string | null>(null)
const inventoryError = ref<string | null>(null)

const EQUIPPABLE_CATEGORIES = new Set([
  'simple_melee', 'simple_ranged', 'martial_melee', 'martial_ranged',
  'light', 'medium', 'heavy', 'shield',
])

function isEquippable(item: Record<string, unknown>): boolean {
  return EQUIPPABLE_CATEGORIES.has(item.category as string)
}

function isConsumable(item: Record<string, unknown>): boolean {
  const id = (item.id as string ?? '').toLowerCase()
  const name = (item.name_fr as string ?? '').toLowerCase()
  return id.includes('potion') || name.includes('potion')
}

async function onEquip(itemId: string) {
  if (!character.value) return
  inventoryLoading.value = itemId
  inventoryError.value = null
  try {
    character.value = await characterApi.inventoryEquip(character.value.id, itemId)
  } catch {
    inventoryError.value = 'Impossible de modifier l\'équipement.'
  } finally {
    inventoryLoading.value = null
  }
}

async function onUse(itemId: string) {
  if (!character.value) return
  inventoryLoading.value = itemId
  inventoryError.value = null
  try {
    character.value = await characterApi.inventoryUse(character.value.id, itemId)
  } catch {
    inventoryError.value = 'Impossible d\'utiliser cet objet.'
  } finally {
    inventoryLoading.value = null
  }
}

const itemToDrop = ref<string | null>(null)

async function confirmDrop() {
  if (!character.value || !itemToDrop.value) return
  inventoryLoading.value = itemToDrop.value
  inventoryError.value = null
  try {
    character.value = await characterApi.inventoryDrop(character.value.id, itemToDrop.value)
  } catch {
    inventoryError.value = 'Impossible de lâcher cet objet.'
  } finally {
    inventoryLoading.value = null
    itemToDrop.value = null
  }
}
</script>

<template>
  <div class="min-h-screen" :style="{ background: 'var(--color-bg)', color: 'var(--color-parchment)' }">

    <!-- Header bar -->
    <div
      class="sticky top-0 z-10 flex items-center gap-4 border-b px-6 py-3 backdrop-blur"
      :style="{ borderColor: 'var(--color-border)', background: 'rgba(14,13,20,0.9)' }"
    >
      <button class="rpg-btn-secondary !py-1 !px-3 !text-[11px]" @click="goBack">← Retour</button>

      <div class="flex items-baseline gap-3 min-w-0">
        <h1
          class="font-display text-2xl font-bold tracking-wider truncate"
          :style="{ color: 'var(--color-parchment)' }"
        >{{ character?.name ?? 'Chargement…' }}</h1>
        <span
          v-if="character"
          class="font-serif italic text-sm shrink-0"
          :style="{ color: 'var(--color-text-muted)' }"
        >
          Niv. {{ character.level }}
          · {{ character.char_class.charAt(0).toUpperCase() + character.char_class.slice(1) }}
          · {{ character.species }}
        </span>
      </div>

      <span
        v-if="character?.is_ai"
        class="ml-auto rpg-chip"
        :style="{
          color: 'var(--color-arcane)',
          background: 'rgba(192,144,255,0.1)',
          borderColor: 'rgba(192,144,255,0.3)',
        }"
      >IA</span>
    </div>

    <!-- Error -->
    <div
      v-if="error"
      class="p-6 text-center font-serif italic"
      :style="{ color: 'var(--color-blood-light)' }"
    >{{ error }}</div>

    <!-- Loading -->
    <div
      v-else-if="loading"
      class="flex items-center justify-center p-16 font-serif italic"
      :style="{ color: 'var(--color-text-muted)' }"
    >
      <span class="rpg-pulse">Déroulement du parchemin…</span>
    </div>

    <!-- Sheet content -->
    <div v-else-if="character" class="mx-auto max-w-5xl px-6 py-8 space-y-8">

      <!-- ── Row 1 : Identity + Combat vitals ─────────────────────────────────── -->
      <div class="grid grid-cols-1 gap-5 md:grid-cols-3">

        <!-- Identity card -->
        <div class="rpg-card p-5 space-y-3">
          <div class="rpg-eyebrow">✦ Identité</div>

          <div>
            <p
              class="font-display text-xl font-bold"
              :style="{ color: 'var(--color-parchment)' }"
            >{{ character.name }}</p>
            <p class="font-serif text-sm italic" :style="{ color: 'var(--color-text-muted)' }">
              {{ character.player_name ? `Joueur : ${character.player_name}` : (character.is_ai ? 'Contrôlé par l\'IA' : 'Joueur humain') }}
            </p>
          </div>

          <div class="space-y-1 text-sm">
            <div
              v-for="(val, label) in {
                Classe: character.char_class,
                Niveau: character.level,
                Espèce: character.species,
                Historique: backgroundLabel,
              }"
              :key="label"
              class="flex justify-between border-b py-1"
              :style="{ borderColor: 'var(--color-border)' }"
            >
              <span :style="{ color: 'var(--color-text-muted)' }">{{ label }}</span>
              <span class="font-semibold capitalize" :style="{ color: 'var(--color-parchment)' }">{{ val }}</span>
            </div>
            <div class="flex justify-between pt-2">
              <span :style="{ color: 'var(--color-text-muted)' }">Bonus de maîtrise</span>
              <span class="font-mono font-bold" :style="{ color: 'var(--color-gold)' }">{{ fmtMod(profBonus) }}</span>
            </div>
          </div>
        </div>

        <!-- Combat vitals -->
        <div class="rpg-card p-5 space-y-4 md:col-span-2">
          <div class="rpg-eyebrow">⚔ Stats de combat</div>

          <!-- HP bar -->
          <div>
            <div class="flex justify-between mb-1.5">
              <span class="text-sm" :style="{ color: 'var(--color-text-muted)' }">Points de Vie</span>
              <span class="font-mono font-bold text-base" :style="{ color: 'var(--color-parchment)' }">
                {{ character.hp_current }}<span :style="{ color: 'var(--color-text-dim)' }">/{{ character.hp_max }}</span>
                <span v-if="character.hp_temp > 0" class="ml-1.5" :style="{ color: 'var(--color-arcane)' }">+{{ character.hp_temp }} tmp</span>
              </span>
            </div>
            <div
              class="h-3 overflow-hidden rounded-full border"
              :style="{
                borderColor: 'var(--color-border)',
                background: 'rgba(0,0,0,0.3)',
              }"
            >
              <div
                class="h-full rounded-full transition-all duration-500"
                :style="{
                  width: hpPercent + '%',
                  background: 'linear-gradient(90deg, ' + hpColorVar + ', ' + hpColorVar + 'cc)',
                  boxShadow: '0 0 10px ' + hpColorVar,
                }"
              />
            </div>
          </div>

          <!-- Combat stats grid -->
          <div class="grid grid-cols-3 gap-3">
            <div
              v-for="stat in [
                { label: 'Classe d\'Armure', value: String(armorClass), sub: '', color: 'var(--color-parchment)' },
                { label: 'Initiative', value: fmtMod(initiative), sub: '', color: initiative >= 0 ? 'var(--color-green)' : 'var(--color-blood)' },
                { label: 'Dé de Vie', value: 'd' + (srdClass?.hit_die ?? '?'), sub: '× ' + character.level, color: 'var(--color-parchment)' },
              ]"
              :key="stat.label"
              class="flex flex-col items-center rounded-lg border py-3"
              :style="{
                borderColor: 'var(--color-border-strong)',
                background: 'var(--color-surface)',
              }"
            >
              <span class="text-[10px] uppercase tracking-widest" :style="{ color: 'var(--color-text-muted)' }">{{ stat.label }}</span>
              <span
                class="font-display text-[28px] font-bold leading-tight"
                :style="{ color: stat.color }"
              >{{ stat.value }}</span>
              <span v-if="stat.sub" class="font-mono text-[10px]" :style="{ color: 'var(--color-text-dim)' }">{{ stat.sub }}</span>
            </div>
          </div>

          <!-- Conditions -->
          <div v-if="character.conditions?.length" class="flex flex-wrap gap-1.5">
            <span
              v-for="cond in character.conditions"
              :key="cond"
              class="rpg-chip capitalize"
              :style="{
                color: 'var(--color-blood)',
                background: 'rgba(232,69,69,0.15)',
                borderColor: 'rgba(232,69,69,0.4)',
              }"
            >{{ cond }}</span>
          </div>
          <p
            v-else
            class="font-serif italic text-xs"
            :style="{ color: 'var(--color-text-dim)' }"
          >Aucune condition active</p>
        </div>
      </div>

      <!-- ── Row 2 : Ability scores + Saving throws ───────────────────────────── -->
      <div class="grid grid-cols-1 gap-5 md:grid-cols-2">

        <!-- Ability scores -->
        <div class="rpg-card p-5">
          <div class="rpg-eyebrow mb-4">✦ Caractéristiques</div>
          <div class="grid grid-cols-3 gap-2.5">
            <div
              v-for="(labels, key) in ABILITY_LABELS"
              :key="key"
              class="flex flex-col items-center rounded-lg border py-3 px-1"
              :style="{
                borderColor: 'var(--color-border-strong)',
                background: 'var(--color-surface)',
              }"
            >
              <span
                class="font-display text-[11px] font-bold tracking-[0.15em]"
                :style="{ color: 'var(--color-text-muted)' }"
              >{{ labels.abbr }}</span>
              <span
                class="font-display text-[26px] font-bold leading-tight my-0.5"
                :style="{ color: 'var(--color-parchment)' }"
              >{{ scores[key] ?? '—' }}</span>
              <span
                class="font-mono text-sm font-bold rounded px-2 py-0.5"
                :style="{
                  color: (mods[key] ?? 0) >= 0 ? 'var(--color-green)' : 'var(--color-blood)',
                  background: (mods[key] ?? 0) >= 0 ? 'rgba(111,217,111,0.1)' : 'rgba(232,69,69,0.1)',
                }"
              >{{ fmtMod(mods[key] ?? 0) }}</span>
              <span
                class="font-serif italic text-[10px] mt-1"
                :style="{ color: 'var(--color-text-dim)' }"
              >{{ labels.name_fr }}</span>
            </div>
          </div>
        </div>

        <!-- Saving throws -->
        <div class="rpg-card p-5">
          <div class="rpg-eyebrow mb-4">✦ Jets de Sauvegarde</div>
          <div class="space-y-1.5">
            <div
              v-for="(labels, key) in ABILITY_LABELS"
              :key="key"
              class="flex items-center gap-3 rounded px-2 py-1.5"
              :style="{
                background: saveProficiencies.includes(key) ? 'rgba(240,199,100,0.05)' : 'transparent',
              }"
            >
              <div
                class="h-3 w-3 rounded-full border shrink-0"
                :style="{
                  borderColor: saveProficiencies.includes(key) ? 'var(--color-gold)' : 'var(--color-border-strong)',
                  background: saveProficiencies.includes(key) ? 'var(--color-gold)' : 'transparent',
                  boxShadow: saveProficiencies.includes(key) ? '0 0 6px var(--color-gold)' : 'none',
                }"
              />
              <span class="flex-1 text-sm" :style="{ color: 'var(--color-parchment)' }">{{ labels.name_fr }}</span>
              <span
                class="font-mono text-sm font-bold w-8 text-right"
                :style="{ color: saveBonus(key) >= 0 ? 'var(--color-green)' : 'var(--color-blood)' }"
              >{{ fmtMod(saveBonus(key)) }}</span>
            </div>
          </div>
          <p class="mt-3 font-serif italic text-xs" :style="{ color: 'var(--color-text-dim)' }">
            Disque plein = maîtrise incluse
          </p>
        </div>
      </div>

      <!-- ── Row 3 : Skills ────────────────────────────────────────────────────── -->
      <div class="rpg-card p-5">
        <div class="rpg-eyebrow mb-4">✦ Compétences</div>
        <div class="grid grid-cols-1 gap-1 sm:grid-cols-2 md:grid-cols-3">
          <div
            v-for="skill in SKILLS"
            :key="skill.id"
            class="flex items-center gap-2 rounded px-2.5 py-1.5 transition-colors"
            :style="{
              background: skillProficiencies.includes(skill.id) ? 'rgba(240,199,100,0.05)' : 'transparent',
            }"
          >
            <div
              class="h-2.5 w-2.5 rounded-full border shrink-0"
              :style="{
                borderColor: skillProficiencies.includes(skill.id) ? 'var(--color-gold)' : 'var(--color-border-strong)',
                background: skillProficiencies.includes(skill.id) ? 'var(--color-gold)' : 'transparent',
              }"
            />
            <span class="flex-1 text-sm" :style="{ color: 'var(--color-parchment)' }">{{ skill.name_fr }}</span>
            <span class="font-mono text-[10px] uppercase mr-1" :style="{ color: 'var(--color-text-dim)' }">{{ ABILITY_LABELS[skill.ability]?.abbr }}</span>
            <span
              class="font-mono text-sm font-bold w-7 text-right"
              :style="{ color: skillBonus(skill) >= 0 ? 'var(--color-green)' : 'var(--color-blood)' }"
            >{{ fmtMod(skillBonus(skill)) }}</span>
          </div>
        </div>
      </div>

      <!-- ── Row 4 : Spells (if spellcaster) ──────────────────────────────────── -->
      <div
        v-if="isSpellcaster"
        class="rounded-[10px] border p-5"
        :style="{
          borderColor: 'rgba(192,144,255,0.3)',
          background: 'linear-gradient(135deg, rgba(192,144,255,0.05), var(--color-bg-elev))',
        }"
      >
        <div
          class="mb-4 font-display text-[11px] font-bold tracking-[0.2em] uppercase"
          :style="{ color: 'var(--color-arcane)' }"
        >✦ Magie</div>

        <!-- Spell slots -->
        <div v-if="spellSlotEntries.length" class="mb-5">
          <p class="mb-2 text-[10px] uppercase tracking-wider" :style="{ color: 'var(--color-text-muted)' }">
            Emplacements de sorts
          </p>
          <div class="flex flex-wrap gap-3">
            <div
              v-for="slot in spellSlotEntries"
              :key="slot.level"
              class="rounded-lg border px-3 py-2 text-center"
              :style="{
                borderColor: 'rgba(192,144,255,0.3)',
                background: 'rgba(192,144,255,0.08)',
              }"
            >
              <p class="font-display text-xs font-bold mb-1" :style="{ color: 'var(--color-arcane)' }">
                Niv. {{ slot.level }}
              </p>
              <div class="flex gap-1 justify-center">
                <div
                  v-for="i in slot.total"
                  :key="i"
                  class="h-3 w-3 rounded-full border"
                  :style="{
                    borderColor: 'rgba(192,144,255,0.6)',
                    background: i <= slot.total - slot.used ? 'var(--color-arcane)' : 'transparent',
                    boxShadow: i <= slot.total - slot.used ? '0 0 6px var(--color-arcane)' : 'none',
                  }"
                />
              </div>
              <p class="font-mono text-[10px] mt-1.5" :style="{ color: 'var(--color-text-muted)' }">
                {{ slot.total - slot.used }}/{{ slot.total }}
              </p>
            </div>
          </div>
        </div>

        <!-- Known spells -->
        <div>
          <p class="mb-2 text-[10px] uppercase tracking-wider" :style="{ color: 'var(--color-text-muted)' }">
            Sorts connus ({{ character.known_spells?.length ?? 0 }})
          </p>
          <div v-if="spellDetails.length" class="grid gap-2 sm:grid-cols-2 md:grid-cols-3">
            <div
              v-for="spell in spellDetails"
              :key="spell.id"
              class="rounded-lg border px-3 py-2"
              :style="{
                borderColor: 'rgba(192,144,255,0.2)',
                background: 'var(--color-surface)',
              }"
            >
              <div class="flex items-start justify-between gap-1">
                <p
                  class="font-display text-sm font-bold leading-tight"
                  :style="{ color: 'var(--color-parchment)' }"
                >{{ spell.name_fr }}</p>
                <span
                  class="shrink-0 rounded px-1.5 py-0.5 text-[10px] font-bold"
                  :style="{
                    color: 'var(--color-arcane)',
                    background: 'rgba(192,144,255,0.15)',
                  }"
                >{{ spell.level === 0 ? 'Tour' : 'Niv.' + spell.level }}</span>
              </div>
              <p class="mt-0.5 font-serif italic text-xs" :style="{ color: 'var(--color-text-muted)' }">
                {{ SPELL_SCHOOLS[spell.school] ?? spell.school }}
              </p>
              <p
                v-if="spell.damage_dice"
                class="mt-1 font-mono text-xs"
                :style="{ color: 'var(--color-gold)' }"
              >{{ spell.damage_dice }} {{ spell.damage_type }}</p>
            </div>
          </div>
          <div v-else class="flex flex-wrap gap-1.5">
            <span
              v-for="spellId in character.known_spells"
              :key="spellId"
              class="rpg-chip"
              :style="{
                color: 'var(--color-arcane)',
                background: 'rgba(192,144,255,0.08)',
                borderColor: 'rgba(192,144,255,0.25)',
              }"
            >{{ spellId }}</span>
          </div>
        </div>
      </div>

      <!-- ── Row 5 : Equipment ─────────────────────────────────────────────────── -->
      <div class="rpg-card p-5">
        <div class="rpg-eyebrow mb-4">✦ Équipement</div>
        <p
          v-if="inventoryError"
          class="mb-3 rounded-lg border px-3 py-2 text-xs"
          :style="{
            borderColor: 'rgba(232,69,69,0.4)',
            background: 'rgba(232,69,69,0.1)',
            color: 'var(--color-blood-light)',
          }"
        >{{ inventoryError }}</p>
        <div v-if="character.equipment?.length" class="space-y-1.5">
          <div
            v-for="(item, idx) in (character.equipment as Record<string, unknown>[])"
            :key="idx"
            class="flex items-center gap-3 rounded-lg border px-3 py-2 text-sm transition-colors"
            :style="{
              borderColor: item.equipped ? 'rgba(240,199,100,0.3)' : 'var(--color-border)',
              background: item.equipped ? 'rgba(240,199,100,0.05)' : 'transparent',
              color: item.equipped ? 'var(--color-parchment)' : 'var(--color-text-muted)',
            }"
          >
            <span
              class="shrink-0 text-base"
              :style="{ color: item.equipped ? 'var(--color-gold)' : 'var(--color-text-dim)' }"
              :title="item.equipped ? 'Équipé' : 'Dans le sac'"
            >{{ item.equipped ? '⚔' : '○' }}</span>
            <span class="flex-1 capitalize">{{ String(item.name_fr ?? item.id ?? 'Objet inconnu') }}</span>
            <span
              v-if="item.quantity && Number(item.quantity) > 1"
              class="font-mono text-xs"
              :style="{ color: 'var(--color-text-dim)' }"
            >×{{ item.quantity }}</span>
            <div class="flex shrink-0 gap-1">
              <button
                v-if="isEquippable(item)"
                class="rounded border px-2 py-0.5 text-[10px] uppercase tracking-wide font-semibold transition-colors"
                :style="{
                  borderColor: item.equipped ? 'var(--color-gold)' : 'var(--color-border-strong)',
                  color: item.equipped ? 'var(--color-gold)' : 'var(--color-text-muted)',
                }"
                :disabled="inventoryLoading === item.id"
                @click="onEquip(String(item.id))"
              >{{ item.equipped ? 'Retirer' : 'Équiper' }}</button>
              <button
                v-if="isConsumable(item)"
                class="rpg-btn-tonal tone-arcane !py-0.5 !px-2 !text-[10px]"
                :disabled="inventoryLoading === item.id"
                @click="onUse(String(item.id))"
              >Utiliser</button>
              <button
                class="rounded border px-2 py-0.5 text-[10px] uppercase tracking-wide transition-colors"
                :style="{
                  borderColor: 'var(--color-border)',
                  color: 'var(--color-text-dim)',
                }"
                :disabled="inventoryLoading === item.id"
                @click="itemToDrop = String(item.id)"
              >Lâcher</button>
            </div>
          </div>
        </div>
        <p
          v-else
          class="font-serif italic text-sm"
          :style="{ color: 'var(--color-text-dim)' }"
        >Aucun objet</p>
      </div>

      <!-- Confirmation dialog -->
      <div
        v-if="itemToDrop"
        class="fixed inset-0 z-50 flex items-center justify-center"
        :style="{ background: 'rgba(0,0,0,0.75)' }"
        @click.self="itemToDrop = null"
      >
        <div
          class="rounded-[14px] border p-6 shadow-2xl w-80"
          :style="{
            borderColor: 'rgba(232,69,69,0.3)',
            background: 'var(--color-bg-elev)',
          }"
        >
          <p
            class="mb-1 font-display text-base font-bold"
            :style="{ color: 'var(--color-parchment)' }"
          >Lâcher cet objet ?</p>
          <p
            class="mb-5 font-serif italic text-sm"
            :style="{ color: 'var(--color-text-muted)' }"
          >Cette action est irréversible.</p>
          <div class="flex gap-3">
            <button class="rpg-btn-tonal tone-blood flex-1 justify-center !py-2" @click="confirmDrop">Confirmer</button>
            <button class="rpg-btn-secondary flex-1 justify-center !py-2" @click="itemToDrop = null">Annuler</button>
          </div>
        </div>
      </div>

      <!-- ── Row 6 : Traits de classe ─────────────────────────────────────────── -->
      <div v-if="srdClass?.level_1_features?.length" class="rpg-card p-5">
        <div class="rpg-eyebrow mb-4">
          ✦ Aptitudes de classe — {{ srdClass.name_fr }}
        </div>
        <div class="grid gap-3 sm:grid-cols-2">
          <div
            v-for="feature in srdClass.level_1_features"
            :key="feature.name"
            class="rounded-lg border px-4 py-3"
            :style="{
              borderColor: 'var(--color-border)',
              background: 'var(--color-surface)',
            }"
          >
            <p
              class="font-display text-sm font-bold tracking-wide"
              :style="{ color: 'var(--color-gold)' }"
            >{{ feature.name_fr }}</p>
            <p
              class="mt-1.5 font-serif text-[13px] leading-relaxed"
              :style="{ color: 'var(--color-parchment-dark)' }"
            >{{ feature.description }}</p>
          </div>
        </div>
      </div>

      <!-- ── Row 7 : Personnalité ─────────────────────────────────────────────── -->
      <div v-if="personalityTraits.length" class="rpg-card p-5">
        <div class="rpg-eyebrow mb-4">✦ Personnalité</div>
        <ul class="space-y-2">
          <li
            v-for="(trait, i) in personalityTraits"
            :key="i"
            class="flex items-start gap-3 font-serif text-sm leading-relaxed"
            :style="{ color: 'var(--color-parchment-dark)' }"
          >
            <span
              class="mt-0.5 shrink-0"
              :style="{ color: 'var(--color-ember)' }"
            >❞</span>
            <span class="italic">{{ trait }}</span>
          </li>
        </ul>
      </div>

    </div>
  </div>
</template>
