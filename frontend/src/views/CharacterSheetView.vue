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
  // From character proficiencies
  if (Array.isArray(p?.saving_throws)) return p!.saving_throws as string[]
  // Fallback to SRD class data
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

// Armor class: check equipped armor, else 10 + DEX mod
// SRD item fields: category ('light'|'medium'|'heavy'|'shield'), base_ac, dex_cap (0=heavy, null=uncapped)
const armorClass = computed((): number => {
  if (!character.value) return 10
  const equip = character.value.equipment as Record<string, unknown>[]
  const ARMOR_CATS = new Set(['light', 'medium', 'heavy'])
  const armor = equip.find((e) => e.equipped && ARMOR_CATS.has(e.category as string))
  const shield = equip.find((e) => e.equipped && e.category === 'shield')
  const shieldBonus = shield ? 2 : 0
  if (armor && typeof armor.base_ac === 'number') {
    const dexCap = armor.dex_cap  // null = uncapped, 0 = heavy (no DEX), number = medium cap
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

const hpColorClass = computed((): string => {
  const pct = hpPercent.value
  return pct > 50 ? 'bg-green-600' : pct > 25 ? 'bg-yellow-500' : 'bg-blood'
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
    // Load SRD class in parallel with spells
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

const inventoryLoading = ref<string | null>(null)  // item_id en cours d'action
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
  <div class="min-h-screen bg-ink text-parchment">

    <!-- Header bar -->
    <div class="sticky top-0 z-10 flex items-center gap-3 border-b border-gold/20 bg-ink/95 px-4 py-3 backdrop-blur">
      <button
        class="rounded border border-gold/30 px-3 py-1 text-xs text-gold/70 transition hover:border-gold/60 hover:text-gold"
        @click="goBack"
      >
        ← Retour
      </button>
      <h1 class="text-lg font-bold tracking-wide text-gold">
        {{ character?.name ?? 'Chargement…' }}
      </h1>
      <span v-if="character" class="text-sm text-parchment/50">
        Niv. {{ character.level }}
        {{ character.char_class.charAt(0).toUpperCase() + character.char_class.slice(1) }}
        · {{ character.species }}
      </span>
      <span
        v-if="character?.is_ai"
        class="ml-auto rounded bg-arcane/20 px-2 py-0.5 text-xs text-arcane"
      >IA</span>
    </div>

    <!-- Error -->
    <div v-if="error" class="p-6 text-center text-blood">{{ error }}</div>

    <!-- Loading -->
    <div v-else-if="loading" class="flex items-center justify-center p-16">
      <span class="animate-pulse text-parchment/40">Chargement de la fiche…</span>
    </div>

    <!-- Sheet content -->
    <div v-else-if="character" class="mx-auto max-w-5xl px-4 py-6 space-y-6">

      <!-- ── Row 1 : Identity + Combat vitals ─────────────────────────────────── -->
      <div class="grid grid-cols-1 gap-4 md:grid-cols-3">

        <!-- Identity card -->
        <div class="rounded border border-gold/20 bg-ink/60 p-4 space-y-2">
          <h2 class="text-xs uppercase tracking-widest text-gold/60 font-semibold">Identité</h2>
          <div>
            <p class="text-xl font-bold text-parchment">{{ character.name }}</p>
            <p class="text-sm text-parchment/60">
              {{ character.player_name ? `Joueur : ${character.player_name}` : (character.is_ai ? 'Contrôlé par l\'IA' : 'Joueur humain') }}
            </p>
          </div>
          <div class="space-y-0.5 text-sm">
            <div class="flex justify-between">
              <span class="text-parchment/50">Classe</span>
              <span class="font-semibold capitalize">{{ character.char_class }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-parchment/50">Niveau</span>
              <span class="font-semibold">{{ character.level }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-parchment/50">Espèce</span>
              <span class="font-semibold capitalize">{{ character.species }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-parchment/50">Historique</span>
              <span class="font-semibold">{{ backgroundLabel }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-parchment/50">Bonus de maîtrise</span>
              <span class="font-semibold text-gold">{{ fmtMod(profBonus) }}</span>
            </div>
          </div>
        </div>

        <!-- Combat vitals -->
        <div class="rounded border border-gold/20 bg-ink/60 p-4 space-y-3 md:col-span-2">
          <h2 class="text-xs uppercase tracking-widest text-gold/60 font-semibold">Stats de combat</h2>

          <!-- HP bar -->
          <div>
            <div class="flex justify-between text-sm mb-1">
              <span class="text-parchment/60">Points de Vie</span>
              <span class="font-mono font-bold">
                {{ character.hp_current }}<span class="text-parchment/40">/{{ character.hp_max }}</span>
                <span v-if="character.hp_temp > 0" class="ml-1.5 text-arcane">+{{ character.hp_temp }} tmp</span>
              </span>
            </div>
            <div class="h-3 rounded-full bg-ink border border-gold/10 overflow-hidden">
              <div
                class="h-full rounded-full transition-all duration-500"
                :class="hpColorClass"
                :style="{ width: `${hpPercent}%` }"
              />
            </div>
          </div>

          <!-- Combat stats grid -->
          <div class="grid grid-cols-3 gap-3">
            <div class="flex flex-col items-center rounded border border-gold/20 bg-ink/40 py-2">
              <span class="text-xs text-parchment/50">Classe d'Armure</span>
              <span class="text-2xl font-bold text-parchment">{{ armorClass }}</span>
            </div>
            <div class="flex flex-col items-center rounded border border-gold/20 bg-ink/40 py-2">
              <span class="text-xs text-parchment/50">Initiative</span>
              <span class="text-2xl font-bold" :class="initiative >= 0 ? 'text-green-400' : 'text-blood'">
                {{ fmtMod(initiative) }}
              </span>
            </div>
            <div class="flex flex-col items-center rounded border border-gold/20 bg-ink/40 py-2">
              <span class="text-xs text-parchment/50">Dé de Vie</span>
              <span class="text-2xl font-bold text-parchment">
                d{{ srdClass?.hit_die ?? '?' }}
              </span>
              <span class="text-xs text-parchment/40">× {{ character.level }}</span>
            </div>
          </div>

          <!-- Conditions -->
          <div v-if="character.conditions?.length" class="flex flex-wrap gap-1.5">
            <span
              v-for="cond in character.conditions"
              :key="cond"
              class="rounded-full bg-blood/25 border border-blood/40 px-2.5 py-0.5 text-xs font-semibold text-blood capitalize"
            >{{ cond }}</span>
          </div>
          <p v-else class="text-xs italic text-parchment/30">Aucune condition active</p>
        </div>
      </div>

      <!-- ── Row 2 : Ability scores + Saving throws ───────────────────────────── -->
      <div class="grid grid-cols-1 gap-4 md:grid-cols-2">

        <!-- Ability scores -->
        <div class="rounded border border-gold/20 bg-ink/60 p-4">
          <h2 class="mb-3 text-xs uppercase tracking-widest text-gold/60 font-semibold">Caractéristiques</h2>
          <div class="grid grid-cols-3 gap-2">
            <div
              v-for="(labels, key) in ABILITY_LABELS"
              :key="key"
              class="flex flex-col items-center rounded border border-gold/20 bg-ink/40 py-2.5 px-1"
            >
              <span class="text-xs font-bold text-parchment/50 tracking-wide">{{ labels.abbr }}</span>
              <span class="text-2xl font-bold text-parchment my-0.5">{{ scores[key] ?? '—' }}</span>
              <span
                class="text-sm font-semibold px-2 py-0.5 rounded"
                :class="(mods[key] ?? 0) >= 0 ? 'text-green-400' : 'text-blood'"
              >{{ fmtMod(mods[key] ?? 0) }}</span>
              <span class="mt-0.5 text-xs text-parchment/30">{{ labels.name_fr }}</span>
            </div>
          </div>
        </div>

        <!-- Saving throws -->
        <div class="rounded border border-gold/20 bg-ink/60 p-4">
          <h2 class="mb-3 text-xs uppercase tracking-widest text-gold/60 font-semibold">Jets de Sauvegarde</h2>
          <div class="space-y-1.5">
            <div
              v-for="(labels, key) in ABILITY_LABELS"
              :key="key"
              class="flex items-center gap-2"
            >
              <!-- Proficiency indicator -->
              <div
                class="h-3 w-3 rounded-full border shrink-0 transition-colors"
                :class="saveProficiencies.includes(key)
                  ? 'border-gold bg-gold'
                  : 'border-parchment/30 bg-transparent'"
              />
              <span class="flex-1 text-sm text-parchment/80">{{ labels.name_fr }}</span>
              <span
                class="font-mono text-sm font-semibold w-8 text-right"
                :class="saveBonus(key) >= 0 ? 'text-green-400' : 'text-blood'"
              >{{ fmtMod(saveBonus(key)) }}</span>
            </div>
          </div>
          <p class="mt-3 text-xs text-parchment/30">
            Disque plein = maîtrise incluse
          </p>
        </div>
      </div>

      <!-- ── Row 3 : Skills ────────────────────────────────────────────────────── -->
      <div class="rounded border border-gold/20 bg-ink/60 p-4">
        <h2 class="mb-3 text-xs uppercase tracking-widest text-gold/60 font-semibold">Compétences</h2>
        <div class="grid grid-cols-1 gap-1 sm:grid-cols-2 md:grid-cols-3">
          <div
            v-for="skill in SKILLS"
            :key="skill.id"
            class="flex items-center gap-2 rounded px-2 py-1"
            :class="skillProficiencies.includes(skill.id) ? 'bg-gold/5' : ''"
          >
            <div
              class="h-2.5 w-2.5 rounded-full border shrink-0"
              :class="skillProficiencies.includes(skill.id)
                ? 'border-gold bg-gold'
                : 'border-parchment/30 bg-transparent'"
            />
            <span class="flex-1 text-sm text-parchment/80">{{ skill.name_fr }}</span>
            <span class="text-xs text-parchment/40 uppercase font-mono mr-1">{{ ABILITY_LABELS[skill.ability]?.abbr }}</span>
            <span
              class="font-mono text-sm font-semibold w-7 text-right"
              :class="skillBonus(skill) >= 0 ? 'text-green-400' : 'text-blood'"
            >{{ fmtMod(skillBonus(skill)) }}</span>
          </div>
        </div>
      </div>

      <!-- ── Row 4 : Spells (if spellcaster) ──────────────────────────────────── -->
      <div v-if="isSpellcaster" class="rounded border border-arcane/30 bg-ink/60 p-4">
        <h2 class="mb-3 text-xs uppercase tracking-widest text-arcane/70 font-semibold">Magie</h2>

        <!-- Spell slots -->
        <div v-if="spellSlotEntries.length" class="mb-4">
          <p class="mb-2 text-xs text-parchment/50">Emplacements de sorts</p>
          <div class="flex flex-wrap gap-3">
            <div
              v-for="slot in spellSlotEntries"
              :key="slot.level"
              class="rounded border border-arcane/30 bg-arcane/10 px-3 py-2 text-center"
            >
              <p class="text-xs text-parchment/50 mb-1">Niv. {{ slot.level }}</p>
              <div class="flex gap-1 justify-center">
                <div
                  v-for="i in slot.total"
                  :key="i"
                  class="h-3 w-3 rounded-full border border-arcane/50"
                  :class="i <= slot.total - slot.used ? 'bg-arcane' : 'bg-transparent'"
                />
              </div>
              <p class="text-xs text-parchment/40 mt-1">{{ slot.total - slot.used }}/{{ slot.total }}</p>
            </div>
          </div>
        </div>

        <!-- Known spells -->
        <div>
          <p class="mb-2 text-xs text-parchment/50">Sorts connus ({{ character.known_spells?.length ?? 0 }})</p>
          <div v-if="spellDetails.length" class="grid gap-2 sm:grid-cols-2 md:grid-cols-3">
            <div
              v-for="spell in spellDetails"
              :key="spell.id"
              class="rounded border border-arcane/20 bg-ink/40 px-3 py-2"
            >
              <div class="flex items-start justify-between gap-1">
                <p class="text-sm font-semibold text-parchment leading-tight">{{ spell.name_fr }}</p>
                <span class="shrink-0 rounded bg-arcane/20 px-1.5 py-0.5 text-xs text-arcane">
                  {{ spell.level === 0 ? 'Tour' : `Niv.${spell.level}` }}
                </span>
              </div>
              <p class="mt-0.5 text-xs text-parchment/40">{{ SPELL_SCHOOLS[spell.school] ?? spell.school }}</p>
              <p v-if="spell.damage_dice" class="mt-0.5 text-xs text-gold/70">
                {{ spell.damage_dice }} {{ spell.damage_type }}
              </p>
            </div>
          </div>
          <!-- Fallback: IDs only -->
          <div v-else class="flex flex-wrap gap-1.5">
            <span
              v-for="spellId in character.known_spells"
              :key="spellId"
              class="rounded bg-arcane/10 border border-arcane/20 px-2 py-0.5 text-xs text-arcane/80"
            >{{ spellId }}</span>
          </div>
        </div>
      </div>

      <!-- ── Row 5 : Equipment ─────────────────────────────────────────────────── -->
      <div class="rounded border border-gold/20 bg-ink/60 p-4">
        <h2 class="mb-3 text-xs uppercase tracking-widest text-gold/60 font-semibold">Équipement</h2>
        <p v-if="inventoryError" class="mb-2 rounded border border-blood/30 bg-blood/10 px-3 py-1.5 text-xs text-blood">
          {{ inventoryError }}
        </p>
        <div v-if="character.equipment?.length" class="space-y-1.5">
          <div
            v-for="(item, idx) in (character.equipment as Record<string, unknown>[])"
            :key="idx"
            class="flex items-center gap-2 rounded border px-3 py-1.5 text-sm"
            :class="item.equipped
              ? 'border-gold/30 bg-gold/5 text-parchment'
              : 'border-parchment/10 bg-transparent text-parchment/60'"
          >
            <!-- Équipé indicator -->
            <span class="shrink-0 text-xs" :title="item.equipped ? 'Équipé' : 'Dans le sac'">
              {{ item.equipped ? '⚔' : '○' }}
            </span>
            <span class="flex-1 capitalize">{{ String(item.name_fr ?? item.id ?? 'Objet inconnu') }}</span>
            <span v-if="item.quantity && Number(item.quantity) > 1" class="text-xs text-parchment/40">
              ×{{ item.quantity }}
            </span>
            <!-- Action buttons -->
            <div class="flex shrink-0 gap-1">
              <button
                v-if="isEquippable(item)"
                class="rounded border px-2 py-0.5 text-xs transition-colors"
                :class="item.equipped
                  ? 'border-gold/40 text-gold/70 hover:bg-gold/10'
                  : 'border-parchment/20 text-parchment/50 hover:border-gold/30 hover:text-parchment'"
                :disabled="inventoryLoading === item.id"
                @click="onEquip(String(item.id))"
              >{{ item.equipped ? 'Retirer' : 'Équiper' }}</button>
              <button
                v-if="isConsumable(item)"
                class="rounded border border-arcane/30 px-2 py-0.5 text-xs text-arcane/70 transition-colors hover:bg-arcane/10"
                :disabled="inventoryLoading === item.id"
                @click="onUse(String(item.id))"
              >Utiliser</button>
              <button
                class="rounded border border-parchment/10 px-2 py-0.5 text-xs text-parchment/30 transition-colors hover:border-blood/30 hover:text-blood/70"
                :disabled="inventoryLoading === item.id"
                @click="itemToDrop = String(item.id)"
              >Lâcher</button>
            </div>
          </div>
        </div>
        <p v-else class="text-sm italic text-parchment/30">Aucun objet</p>
      </div>

      <!-- Confirmation dialog : lâcher un objet -->
      <div
        v-if="itemToDrop"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/70"
        @click.self="itemToDrop = null"
      >
        <div class="rounded border border-blood/30 bg-ink p-6 shadow-xl w-80">
          <p class="mb-1 text-sm font-semibold text-parchment">Lâcher cet objet ?</p>
          <p class="mb-4 text-xs text-parchment/50">Cette action est irréversible.</p>
          <div class="flex gap-3">
            <button
              class="flex-1 rounded border border-blood/50 bg-blood/10 py-2 text-sm font-semibold text-blood transition-colors hover:bg-blood/20"
              @click="confirmDrop"
            >Confirmer</button>
            <button
              class="flex-1 rounded border border-parchment/20 py-2 text-sm text-parchment/50 transition-colors hover:text-parchment"
              @click="itemToDrop = null"
            >Annuler</button>
          </div>
        </div>
      </div>

      <!-- ── Row 6 : Traits de classe (niveau 1) ──────────────────────────────── -->
      <div v-if="srdClass?.level_1_features?.length" class="rounded border border-gold/20 bg-ink/60 p-4">
        <h2 class="mb-3 text-xs uppercase tracking-widest text-gold/60 font-semibold">
          Aptitudes de classe — {{ srdClass.name_fr }}
        </h2>
        <div class="grid gap-3 sm:grid-cols-2">
          <div
            v-for="feature in srdClass.level_1_features"
            :key="feature.name"
            class="rounded border border-gold/10 bg-ink/40 px-3 py-2"
          >
            <p class="text-sm font-semibold text-gold/80">{{ feature.name_fr }}</p>
            <p class="mt-1 text-xs text-parchment/60 leading-relaxed">{{ feature.description }}</p>
          </div>
        </div>
      </div>

      <!-- ── Row 7 : Personnalité ─────────────────────────────────────────────── -->
      <div v-if="personalityTraits.length" class="rounded border border-gold/20 bg-ink/60 p-4">
        <h2 class="mb-3 text-xs uppercase tracking-widest text-gold/60 font-semibold">Personnalité</h2>
        <ul class="space-y-1">
          <li
            v-for="(trait, i) in personalityTraits"
            :key="i"
            class="flex items-start gap-2 text-sm text-parchment/70"
          >
            <span class="mt-0.5 text-gold/40 shrink-0">·</span>
            <span>{{ trait }}</span>
          </li>
        </ul>
      </div>

    </div>
  </div>
</template>
