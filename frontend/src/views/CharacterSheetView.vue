<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { characterApi, srdApi } from '../services/api'
import type { Character, EquipmentItem, SrdClass, SrdSpell } from '../types'
import ConfirmDialog from '../components/common/ConfirmDialog.vue'
import CurrencyDisplay from '../components/character/CurrencyDisplay.vue'
import XpBar from '../components/character/XpBar.vue'

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

const hpGlowColor = computed((): string => {
  const pct = hpPercent.value
  if (pct > 50) return 'rgba(111,217,111,0.5)'
  if (pct > 25) return 'rgba(240,199,100,0.5)'
  return 'rgba(232,69,69,0.5)'
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

const personalityBlock = computed(() => {
  const p = character.value?.personality as Record<string, unknown> | undefined
  if (!p) return null
  const traits = Array.isArray(p.traits) ? (p.traits as string[]) : []
  const bonds = typeof p.bonds === 'string' ? p.bonds : ''
  const flaws = typeof p.flaws === 'string' ? p.flaws : ''
  if (!traits.length && !bonds && !flaws) return null
  return { traits, bonds, flaws }
})

const classLabel = computed(() =>
  srdClass.value?.name_fr ??
  (character.value?.char_class
    ? character.value.char_class.charAt(0).toUpperCase() + character.value.char_class.slice(1)
    : ''),
)

const equipmentWeightLb = computed((): number => {
  const items = character.value?.equipment ?? []
  return items.reduce((sum, item) => {
    const qty = Number(item.quantity ?? 1)
    const weight = Number(item.weight_lb ?? item.weight ?? 0)
    return sum + (Number.isFinite(weight) ? weight * qty : 0)
  }, 0)
})

const equipmentWeightKg = computed((): number => Math.round(equipmentWeightLb.value * 0.453592 * 10) / 10)

function itemName(item: EquipmentItem | Record<string, unknown>): string {
  return String(item.name_fr ?? item.name ?? item.id ?? 'Objet')
}

function itemKind(item: EquipmentItem | Record<string, unknown>): string {
  const type = String(item.item_type ?? '')
  const category = String(item.category ?? '')
  const labels: Record<string, string> = {
    weapon: 'Arme',
    armor: 'Armure',
    shield: 'Bouclier',
    gear: 'Matériel',
    consumable: 'Consommable',
    magic: 'Magique',
    simple: 'Arme courante',
    martial: 'Arme de guerre',
    light: 'Armure légère',
    medium: 'Armure intermédiaire',
    heavy: 'Armure lourde',
  }
  return labels[type] ?? labels[category] ?? category ?? type ?? 'Objet'
}

function itemDetails(item: EquipmentItem | Record<string, unknown>): string {
  const parts: string[] = []
  if (item.damage_dice) parts.push(`${item.damage_dice} ${item.damage_type ?? ''}`.trim())
  if (item.base_ac) parts.push(`CA ${item.base_ac}`)
  if (item.slot) parts.push(`slot ${item.slot}`)
  if (Array.isArray(item.occupied_slots) && item.occupied_slots.length) {
    parts.push(`slots ${item.occupied_slots.join(', ')}`)
  }
  if (item.weight_lb) parts.push(`${item.weight_lb} lb / ${Math.round(Number(item.weight_lb) * 0.453592 * 10) / 10} kg`)
  if (item.cost_gp) parts.push(`${item.cost_gp} po`)
  if (item.identified === false) parts.push('non identifié')
  if (item.attunement_required) parts.push(item.attuned ? 'harmonisé' : 'harmonisation requise')
  return parts.join(' · ')
}

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
  'simple', 'martial', 'light', 'medium', 'heavy', 'shield',
])

function isEquippable(item: Record<string, unknown>): boolean {
  return (
    EQUIPPABLE_CATEGORIES.has(item.category as string)
    || ['weapon', 'armor', 'shield'].includes(String(item.item_type ?? ''))
  )
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

// suppress unused-var warning — kept for potential future template use
void personalityTraits
</script>

<template>
  <div
    class="rpg-sheet-root h-full flex flex-col overflow-hidden"
  >
    <!-- ── TOP BAR ──────────────────────────────────────────────────────────── -->
    <header
      class="rpg-sheet-header flex-shrink-0 flex items-center gap-[18px] px-6 border-b z-10"
    >
      <!-- Logo mark -->
      <div class="flex items-center gap-2.5">
        <div
          class="rpg-brand-mark flex h-8 w-8 items-center justify-center font-display text-base font-bold rounded-lg flex-shrink-0"
        >⚔</div>
        <span class="rpg-sheet-brand-text font-display font-bold">RPGMASTER</span>
      </div>

      <span class="rpg-text-dim text-[13px]">/</span>

      <!-- Breadcrumbs -->
      <div class="rpg-sheet-crumbs flex items-center gap-2">
        <span>Lobby</span>
        <span class="rpg-text-dim">›</span>
        <span>Session</span>
        <span class="rpg-text-dim">›</span>
        <span
          class="rpg-sheet-crumb-current font-semibold"
        >{{ character?.name ?? '…' }}</span>
      </div>

      <div class="flex-1" />

      <button class="rpg-btn-secondary !py-1.5 !px-3 !text-[11px]" @click="goBack">
        ← Retour session
      </button>
    </header>

    <!-- ── ERROR ────────────────────────────────────────────────────────────── -->
    <div
      v-if="error"
      class="rpg-text-blood-light flex-1 flex items-center justify-center font-serif italic"
    >{{ error }}</div>

    <!-- ── LOADING ──────────────────────────────────────────────────────────── -->
    <div
      v-else-if="loading"
      class="rpg-text-muted flex-1 flex items-center justify-center font-serif italic"
    >
      <span class="rpg-pulse">Déroulement du parchemin…</span>
    </div>

    <!-- ── SHEET ─────────────────────────────────────────────────────────────── -->
    <template v-else-if="character">

      <!-- HERO HEADER -->
      <div
        class="rpg-sheet-hero flex-shrink-0 relative overflow-hidden"
      >
        <div class="relative flex items-center gap-6">
          <!-- Avatar -->
          <div
            class="rpg-sheet-avatar flex-shrink-0 flex items-center justify-center font-display font-bold"
          >{{ character.name[0] }}</div>

          <!-- Identity -->
          <div class="flex-1 min-w-0">
            <div class="rpg-eyebrow mb-1">✦ Fiche de personnage</div>
            <h1
              class="rpg-sheet-title font-display font-bold"
            >{{ character.name }}</h1>
            <div class="rpg-sheet-meta font-serif">
              Niv. {{ character.level }} · {{ classLabel }} · {{ character.species }}
              <span class="rpg-text-dim mx-2.5">·</span>
              <span class="rpg-text-muted">Historique : {{ backgroundLabel }}</span>
            </div>
          </div>

          <!-- Hero stat boxes -->
          <div class="flex gap-2.5 flex-shrink-0">
            <!-- Classe d'armure -->
            <div
              class="rpg-stat-slab text-center rounded-lg border px-4 py-2.5"
            >
              <div class="rpg-stat-label">Classe d'armure</div>
              <div class="rpg-stat-value rpg-text-teal font-display font-bold">{{ armorClass }}</div>
            </div>
            <!-- Initiative -->
            <div
              class="rpg-stat-slab text-center rounded-lg border px-4 py-2.5"
            >
              <div class="rpg-stat-label">Initiative</div>
              <div
                class="rpg-stat-value font-display font-bold"
                :class="initiative >= 0 ? 'rpg-text-gold' : 'rpg-text-blood'"
              >{{ fmtMod(initiative) }}</div>
            </div>
            <!-- Vitesse -->
            <div
              class="rpg-stat-slab text-center rounded-lg border px-4 py-2.5"
            >
              <div class="rpg-stat-label">Vitesse</div>
              <div class="rpg-stat-value rpg-text-main font-display font-bold">9m</div>
            </div>
            <!-- Maîtrise -->
            <div
              class="rpg-stat-slab text-center rounded-lg border px-4 py-2.5"
            >
              <div class="rpg-stat-label">Maîtrise</div>
              <div class="rpg-stat-value rpg-text-ember font-display font-bold">{{ fmtMod(profBonus) }}</div>
            </div>
          </div>
        </div>

        <!-- HP bar -->
        <div class="relative mt-5 max-w-[700px]">
          <div class="flex justify-between mb-1">
            <span class="rpg-text-muted text-[10px] font-bold uppercase tracking-[0.2em]">
              Points de vie
            </span>
            <span class="font-mono text-[13px] font-bold" :style="{ color: hpColorVar }">
              {{ character.hp_current }}
              <span class="rpg-text-dim">/ {{ character.hp_max }}</span>
              <span v-if="character.hp_temp > 0" class="rpg-text-arcane ml-1">+{{ character.hp_temp }} tmp</span>
            </span>
          </div>
          <div class="rpg-hp-track tall">
            <div
              class="rpg-hp-fill transition-all duration-500"
              :style="{
                width: hpPercent + '%',
                background: `linear-gradient(90deg, ${hpColorVar}cc, ${hpColorVar})`,
                boxShadow: `0 0 8px ${hpGlowColor}`,
              }"
            />
          </div>
        </div>

        <div class="relative mt-4 grid max-w-[700px] grid-cols-1 gap-3 md:grid-cols-[1fr_220px]">
          <div class="rpg-stat-slab rounded-lg border px-4 py-3">
            <XpBar :character="character" />
          </div>
          <div class="rpg-stat-slab rounded-lg border px-4 py-3">
            <CurrencyDisplay :character="character" />
          </div>
        </div>
      </div>

      <!-- BODY: 3-column grid -->
      <div class="rpg-sheet-body flex-1 overflow-y-auto">
        <div class="rpg-sheet-grid">

          <!-- ══ LEFT: Ability scores + Saving throws ════════════════════════ -->
          <div class="rpg-sheet-column">

            <!-- Caractéristiques -->
            <div class="rpg-sheet-section">
              <div class="rpg-sheet-section-header">
                <span class="rpg-sheet-section-star">✦</span>
                <h3 class="rpg-sheet-section-title font-display font-bold uppercase">Caractéristiques</h3>
              </div>
              <div class="rpg-sheet-two-grid">
                <div
                  v-for="(labels, key) in ABILITY_LABELS"
                  :key="key"
                  class="rpg-ability-card text-center rounded-lg border"
                >
                  <div class="rpg-ability-abbr">{{ labels.abbr }}</div>
                  <div class="rpg-ability-score font-display font-bold">
                    {{ scores[key] ?? '—' }}
                  </div>
                  <div
                    class="rpg-mod-badge font-mono font-bold rounded inline-block"
                    :class="(mods[key] ?? 0) >= 0 ? 'is-positive' : 'is-negative'"
                  >{{ fmtMod(mods[key] ?? 0) }}</div>
                  <div class="rpg-text-dim mt-[3px] text-[9px]">{{ labels.name_fr }}</div>
                </div>
              </div>
            </div>

            <!-- Jets de sauvegarde -->
            <div class="rpg-sheet-section">
              <div class="rpg-sheet-section-header">
                <span class="rpg-sheet-section-star">✦</span>
                <h3 class="rpg-sheet-section-title font-display font-bold uppercase">Jets de sauvegarde</h3>
              </div>
              <div class="rpg-proficiency-list">
                <div
                  v-for="(labels, key) in ABILITY_LABELS"
                  :key="key"
                  class="rpg-proficiency-row flex items-center gap-2.5 rounded"
                  :class="{ 'is-proficient': saveProficiencies.includes(key) }"
                >
                  <div
                    class="rpg-proficiency-dot rounded-full border flex-shrink-0"
                    :class="{ 'is-proficient': saveProficiencies.includes(key) }"
                  />
                  <span class="rpg-text-secondary flex-1 text-sm">{{ labels.name_fr }}</span>
                  <span
                    class="w-7 text-right font-mono text-xs font-bold"
                    :class="saveBonus(key) >= 0 ? 'rpg-text-green' : 'rpg-text-blood'"
                  >{{ fmtMod(saveBonus(key)) }}</span>
                </div>
              </div>
            </div>

          </div>

          <!-- ══ CENTER: Skills + Features + Personality + Spells ══════════ -->
          <div class="rpg-sheet-column">

            <!-- Compétences -->
            <div class="rpg-sheet-section">
              <div class="rpg-sheet-section-header">
                <span class="rpg-sheet-section-star">✦</span>
                <h3 class="rpg-sheet-section-title font-display font-bold uppercase">Compétences</h3>
                <span class="rpg-text-dim text-[10px] italic">— Disque plein = maîtrise</span>
              </div>
              <div class="rpg-sheet-two-grid compact">
                <div
                  v-for="skill in SKILLS"
                  :key="skill.id"
                  class="rpg-skill-row flex items-center gap-2 rounded"
                  :class="{ 'is-proficient': skillProficiencies.includes(skill.id) }"
                >
                  <div
                    class="rpg-proficiency-dot small rounded-full border flex-shrink-0"
                    :class="{ 'is-proficient': skillProficiencies.includes(skill.id) }"
                  />
                  <span class="rpg-text-secondary flex-1 text-xs">{{ skill.name_fr }}</span>
                  <span class="rpg-text-dim font-mono text-[9px] font-bold uppercase tracking-[0.1em]">
                    {{ ABILITY_LABELS[skill.ability]?.abbr }}
                  </span>
                  <span
                    class="w-[22px] text-right font-mono text-[11px] font-bold"
                    :class="skillBonus(skill) >= 0 ? 'rpg-text-green' : 'rpg-text-blood'"
                  >{{ fmtMod(skillBonus(skill)) }}</span>
                </div>
              </div>
            </div>

            <!-- Aptitudes de classe -->
            <div
              v-if="srdClass?.level_1_features?.length"
              class="rpg-sheet-section tone-ember"
            >
              <div class="rpg-sheet-section-header">
                <span class="rpg-sheet-section-star tone-ember">✦</span>
                <h3 class="rpg-sheet-section-title tone-ember font-display font-bold uppercase">Aptitudes de classe</h3>
              </div>
              <div class="rpg-sheet-two-grid spacious">
                <div
                  v-for="feature in srdClass.level_1_features"
                  :key="feature.name"
                  class="rpg-feature-card rounded-lg border"
                >
                  <div class="rpg-feature-title font-display font-bold">
                    {{ feature.name_fr }}
                  </div>
                  <div class="rpg-feature-copy font-serif">
                    {{ feature.description }}
                  </div>
                </div>
              </div>
            </div>

            <!-- Personnalité -->
            <div
              v-if="personalityBlock"
              class="rpg-sheet-section tone-arcane"
            >
              <div class="rpg-sheet-section-header">
                <span class="rpg-sheet-section-star tone-arcane">✦</span>
                <h3 class="rpg-sheet-section-title tone-arcane font-display font-bold uppercase">Personnalité</h3>
              </div>
              <div class="rpg-prose-card font-serif">
                <p v-for="(t, i) in personalityBlock.traits" :key="i">
                  <span class="rpg-prose-label">Trait · </span>{{ t }}
                </p>
                <p v-if="personalityBlock.bonds">
                  <span class="rpg-prose-label">Lien · </span>{{ personalityBlock.bonds }}
                </p>
                <p v-if="personalityBlock.flaws">
                  <span class="rpg-prose-label">Défaut · </span>{{ personalityBlock.flaws }}
                </p>
              </div>
            </div>

            <!-- Magie (spellcasters only) -->
            <div
              v-if="isSpellcaster"
              class="rpg-sheet-section tone-arcane"
            >
              <div class="rpg-sheet-section-header is-wide">
                <span class="rpg-sheet-section-star tone-arcane">✦</span>
                <h3 class="rpg-sheet-section-title tone-arcane font-display font-bold uppercase">Magie</h3>
              </div>

              <div v-if="spellSlotEntries.length" class="mb-4">
                <p class="rpg-sheet-subtitle">
                  Emplacements de sorts
                </p>
                <div class="flex flex-wrap gap-3">
                  <div
                    v-for="slot in spellSlotEntries"
                    :key="slot.level"
                    class="rpg-spell-slot-card rounded-lg border px-3 py-2 text-center"
                  >
                    <p class="rpg-text-arcane mb-1 font-display text-[11px] font-bold">Niv. {{ slot.level }}</p>
                    <div class="flex gap-1 justify-center">
                      <div
                        v-for="i in slot.total"
                        :key="i"
                        class="rpg-spell-dot rounded-full border"
                        :class="{ 'is-filled': i <= slot.total - slot.used }"
                      />
                    </div>
                    <p class="rpg-text-muted mt-1.5 font-mono text-[10px]">
                      {{ slot.total - slot.used }}/{{ slot.total }}
                    </p>
                  </div>
                </div>
              </div>

              <div>
                <p class="rpg-sheet-subtitle">
                  Sorts connus ({{ character.known_spells?.length ?? 0 }})
                </p>
                <div v-if="spellDetails.length" class="rpg-sheet-two-grid">
                  <div
                    v-for="spell in spellDetails"
                    :key="spell.id"
                    class="rpg-spell-card rounded-lg border px-3 py-2"
                  >
                    <div class="flex items-start justify-between gap-1">
                      <p class="rpg-text-main font-display text-xs font-bold">{{ spell.name_fr }}</p>
                      <span
                        class="rpg-spell-level rounded flex-shrink-0"
                      >{{ spell.level === 0 ? 'Tour' : 'Niv.' + spell.level }}</span>
                    </div>
                    <p class="rpg-text-muted mt-0.5 font-serif text-[11px] italic">
                      {{ SPELL_SCHOOLS[spell.school] ?? spell.school }}
                    </p>
                    <p v-if="spell.damage_dice" class="rpg-text-gold mt-1 font-mono text-[11px]">
                      {{ spell.damage_dice }} {{ spell.damage_type }}
                    </p>
                  </div>
                </div>
                <div v-else class="flex flex-wrap gap-1.5">
                  <span
                    v-for="spellId in character.known_spells"
                    :key="spellId"
                    class="rpg-chip rpg-tone-arcane"
                  >{{ spellId }}</span>
                </div>
              </div>
            </div>

          </div>

          <!-- ══ RIGHT: Equipment + Conditions + Quick actions ══════════════ -->
          <div class="rpg-sheet-column">

            <!-- Équipement -->
            <div class="rpg-sheet-section">
              <div class="rpg-sheet-section-header">
                <span class="rpg-sheet-section-star">✦</span>
                <h3 class="rpg-sheet-section-title font-display font-bold uppercase">Équipement</h3>
                <span class="rpg-text-dim ml-auto text-[10px]">
                  {{ equipmentWeightLb.toFixed(1) }} lb · {{ equipmentWeightKg }} kg
                </span>
              </div>

              <p
                v-if="inventoryError"
                class="rpg-inventory-alert rounded-lg border text-xs"
              >{{ inventoryError }}</p>

              <div v-if="character.equipment?.length" class="rpg-equipment-list">
                <div
                  v-for="item in (character.equipment as EquipmentItem[])"
                  :key="item.id"
                  class="rpg-equipment-item rounded-lg border"
                  :class="{ 'is-equipped': item.equipped }"
                >
                  <div class="flex items-center gap-1.5">
                    <span class="text-[11px]" :class="item.equipped ? 'rpg-text-gold' : 'rpg-text-dim'">
                      {{ item.equipped ? '⚔' : '○' }}
                    </span>
                    <span
                      class="flex-1 font-display text-[13px] font-bold capitalize"
                      :class="item.equipped ? 'rpg-text-main' : 'rpg-text-secondary'"
                    >{{ itemName(item) }}</span>
                    <span
                      v-if="item.quantity && Number(item.quantity) > 1"
                      class="rpg-text-muted font-mono text-[10px]"
                    >×{{ item.quantity }}</span>
                  </div>

                  <div
                    v-if="itemKind(item) || itemDetails(item)"
                    class="rpg-text-muted mt-0.5 pl-[17px] text-[10px]"
                  >
                    <span class="rpg-text-gold">{{ itemKind(item) }}</span>
                    <span v-if="itemDetails(item)"> · {{ itemDetails(item) }}</span>
                  </div>

                  <div class="rpg-equipment-actions flex gap-1.5 mt-1.5">
                    <button
                      v-if="isEquippable(item)"
                      class="rpg-equipment-button rounded border"
                      :class="{ 'is-equipped': item.equipped }"
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
                      class="rpg-equipment-button rpg-border rpg-text-dim rounded border"
                      :disabled="inventoryLoading === item.id"
                      @click="itemToDrop = String(item.id)"
                    >Lâcher</button>
                  </div>
                </div>
              </div>
              <p v-else class="rpg-text-dim font-serif italic text-sm">Aucun objet</p>
            </div>

            <!-- État (conditions) -->
            <div class="rpg-sheet-section tone-blood">
              <div class="rpg-sheet-section-header">
                <span class="rpg-sheet-section-star tone-blood">✦</span>
                <h3 class="rpg-sheet-section-title tone-blood font-display font-bold uppercase">État</h3>
              </div>
              <div v-if="character.conditions?.length" class="flex flex-wrap gap-1.5">
                <span
                  v-for="cond in character.conditions"
                  :key="cond"
                  class="rpg-chip rpg-tone-blood capitalize"
                >{{ cond }}</span>
              </div>
              <p
                v-else
                class="rpg-text-muted py-1 text-center font-serif italic text-sm"
              >Aucune condition active</p>
            </div>

            <!-- Actions rapides -->
            <div class="rpg-sheet-section">
              <div class="rpg-sheet-section-header">
                <span class="rpg-sheet-section-star">✦</span>
                <h3 class="rpg-sheet-section-title font-display font-bold uppercase">Actions rapides</h3>
              </div>
              <div class="grid grid-cols-2 gap-1.5">
                <button class="rpg-quick-action rpg-tone-blood rounded-md border py-2.5">⚔ Attaquer</button>
                <button class="rpg-quick-action rpg-tone-teal rounded-md border py-2.5">◈ Objet</button>
                <button class="rpg-quick-action rpg-tone-arcane rounded-md border py-2.5">✦ Sort</button>
                <button class="rpg-quick-action rpg-tone-green rounded-md border py-2.5">☽ Repos</button>
              </div>
            </div>

          </div>
        </div>
      </div>

      <!-- Drop confirmation modal -->
      <ConfirmDialog
        v-if="itemToDrop"
        title="Lâcher cet objet ?"
        message="Cette action est irréversible. L'objet sera retiré de votre inventaire."
        confirm-label="Lâcher"
        tone="danger"
        :loading="inventoryLoading === itemToDrop"
        @confirm="confirmDrop"
        @cancel="itemToDrop = null"
      />

    </template>
  </div>
</template>
