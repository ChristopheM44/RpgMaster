<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { characterApi, srdApi } from '../services/api'
import type { Character, SrdClass, SrdSpell } from '../types'
import ConfirmDialog from '../components/common/ConfirmDialog.vue'

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

// suppress unused-var warning — kept for potential future template use
void personalityTraits
</script>

<template>
  <div
    class="h-full flex flex-col overflow-hidden"
    style="background: var(--color-bg); color: var(--color-parchment)"
  >
    <!-- ── TOP BAR ──────────────────────────────────────────────────────────── -->
    <header
      class="flex-shrink-0 flex items-center gap-[18px] px-6 border-b z-10"
      style="
        height: 56px;
        border-color: var(--color-border);
        background: linear-gradient(180deg, var(--color-bg-elev), transparent);
        backdrop-filter: blur(8px);
      "
    >
      <!-- Logo mark -->
      <div class="flex items-center gap-2.5">
        <div
          class="flex items-center justify-center font-display font-bold rounded-lg flex-shrink-0"
          style="
            width: 32px; height: 32px;
            background: linear-gradient(135deg, var(--color-ember), var(--color-gold));
            color: var(--color-bg);
            font-size: 16px;
            box-shadow: 0 0 20px rgba(255,130,71,0.3);
          "
        >⚔</div>
        <span class="font-display font-bold" style="font-size: 15px; letter-spacing: 0.07em">RPGMASTER</span>
      </div>

      <span style="color: var(--color-text-dim); font-size: 13px">/</span>

      <!-- Breadcrumbs -->
      <div class="flex items-center gap-2" style="font-size: 12px; color: var(--color-text-muted)">
        <span>Lobby</span>
        <span style="color: var(--color-text-dim)">›</span>
        <span>Session</span>
        <span style="color: var(--color-text-dim)">›</span>
        <span
          class="font-semibold"
          style="color: var(--color-gold); letter-spacing: 0.5px"
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
      class="flex-1 flex items-center justify-center font-serif italic"
      style="color: var(--color-blood-light)"
    >{{ error }}</div>

    <!-- ── LOADING ──────────────────────────────────────────────────────────── -->
    <div
      v-else-if="loading"
      class="flex-1 flex items-center justify-center font-serif italic"
      style="color: var(--color-text-muted)"
    >
      <span class="rpg-pulse">Déroulement du parchemin…</span>
    </div>

    <!-- ── SHEET ─────────────────────────────────────────────────────────────── -->
    <template v-else-if="character">

      <!-- HERO HEADER -->
      <div
        class="flex-shrink-0 relative overflow-hidden"
        style="
          padding: 28px 56px 24px;
          border-bottom: 1px solid var(--color-border);
          background: linear-gradient(180deg, rgba(255,130,71,0.04), transparent);
        "
      >
        <!-- Ambient glow -->
        <div
          class="absolute pointer-events-none rounded-full"
          style="
            top: -100px; right: -50px;
            width: 280px; height: 280px;
            background: radial-gradient(circle, rgba(255,130,71,0.25), transparent 70%);
          "
        />

        <div class="relative flex items-center gap-6">
          <!-- Avatar -->
          <div
            class="flex-shrink-0 flex items-center justify-center font-display font-bold"
            style="
              width: 88px; height: 88px;
              border-radius: 14px;
              background: linear-gradient(135deg, var(--color-ember), var(--color-gold));
              color: var(--color-bg);
              font-size: 44px;
              box-shadow:
                0 0 0 3px var(--color-bg-elev),
                0 0 0 4px var(--color-ember),
                0 0 40px rgba(255,130,71,0.4);
            "
          >{{ character.name[0] }}</div>

          <!-- Identity -->
          <div class="flex-1 min-w-0">
            <div class="rpg-eyebrow mb-1">✦ Fiche de personnage</div>
            <h1
              class="font-display font-bold"
              style="font-size: 40px; line-height: 1; margin: 0 0 4px; letter-spacing: 0.04em; color: var(--color-parchment)"
            >{{ character.name }}</h1>
            <div class="font-serif" style="font-size: 15px; color: var(--color-parchment-dark)">
              Niv. {{ character.level }} · {{ classLabel }} · {{ character.species }}
              <span style="margin: 0 10px; color: var(--color-text-dim)">·</span>
              <span style="color: var(--color-text-muted)">Historique : {{ backgroundLabel }}</span>
            </div>
          </div>

          <!-- Hero stat boxes -->
          <div class="flex gap-2.5 flex-shrink-0">
            <!-- Classe d'armure -->
            <div
              class="text-center rounded-lg border px-4 py-2.5"
              style="min-width: 90px; background: rgba(0,0,0,0.3); border-color: var(--color-border)"
            >
              <div style="font-size: 9px; font-weight: 700; letter-spacing: 0.15em; text-transform: uppercase; color: var(--color-text-dim)">Classe d'armure</div>
              <div class="font-display font-bold" style="font-size: 24px; color: var(--color-teal); margin-top: 2px">{{ armorClass }}</div>
            </div>
            <!-- Initiative -->
            <div
              class="text-center rounded-lg border px-4 py-2.5"
              style="min-width: 90px; background: rgba(0,0,0,0.3); border-color: var(--color-border)"
            >
              <div style="font-size: 9px; font-weight: 700; letter-spacing: 0.15em; text-transform: uppercase; color: var(--color-text-dim)">Initiative</div>
              <div
                class="font-display font-bold"
                style="font-size: 24px; margin-top: 2px"
                :style="{ color: initiative >= 0 ? 'var(--color-gold)' : 'var(--color-blood)' }"
              >{{ fmtMod(initiative) }}</div>
            </div>
            <!-- Vitesse -->
            <div
              class="text-center rounded-lg border px-4 py-2.5"
              style="min-width: 90px; background: rgba(0,0,0,0.3); border-color: var(--color-border)"
            >
              <div style="font-size: 9px; font-weight: 700; letter-spacing: 0.15em; text-transform: uppercase; color: var(--color-text-dim)">Vitesse</div>
              <div class="font-display font-bold" style="font-size: 24px; color: var(--color-parchment); margin-top: 2px">9m</div>
            </div>
            <!-- Maîtrise -->
            <div
              class="text-center rounded-lg border px-4 py-2.5"
              style="min-width: 90px; background: rgba(0,0,0,0.3); border-color: var(--color-border)"
            >
              <div style="font-size: 9px; font-weight: 700; letter-spacing: 0.15em; text-transform: uppercase; color: var(--color-text-dim)">Maîtrise</div>
              <div class="font-display font-bold" style="font-size: 24px; color: var(--color-ember); margin-top: 2px">{{ fmtMod(profBonus) }}</div>
            </div>
          </div>
        </div>

        <!-- HP bar -->
        <div class="relative mt-5" style="max-width: 700px">
          <div class="flex justify-between mb-1">
            <span style="font-size: 10px; font-weight: 700; letter-spacing: 0.2em; text-transform: uppercase; color: var(--color-text-muted)">
              Points de vie
            </span>
            <span class="font-mono font-bold" style="font-size: 13px" :style="{ color: hpColorVar }">
              {{ character.hp_current }}
              <span style="color: var(--color-text-dim)">/ {{ character.hp_max }}</span>
              <span v-if="character.hp_temp > 0" class="ml-1" style="color: var(--color-arcane)">+{{ character.hp_temp }} tmp</span>
            </span>
          </div>
          <div style="height: 12px; border-radius: 6px; background: rgba(0,0,0,0.5); border: 1px solid rgba(255,255,255,0.04); overflow: hidden">
            <div
              class="h-full transition-all duration-500"
              style="border-radius: 6px"
              :style="{
                width: hpPercent + '%',
                background: `linear-gradient(90deg, ${hpColorVar}cc, ${hpColorVar})`,
                boxShadow: `0 0 8px ${hpGlowColor}`,
              }"
            />
          </div>
        </div>
      </div>

      <!-- BODY: 3-column grid -->
      <div class="flex-1 overflow-y-auto" style="padding: 24px 56px 32px">
        <div style="display: grid; grid-template-columns: 260px 1fr 320px; gap: 20px; align-items: start">

          <!-- ══ LEFT: Ability scores + Saving throws ════════════════════════ -->
          <div style="display: flex; flex-direction: column; gap: 16px">

            <!-- Caractéristiques -->
            <div class="rounded-xl" style="background: var(--color-bg-elev); border: 1px solid var(--color-border); padding: 14px">
              <div class="flex items-baseline gap-2" style="margin-bottom: 10px">
                <span style="color: var(--color-ember); font-size: 10px">✦</span>
                <h3 class="font-display font-bold uppercase" style="font-size: 11px; letter-spacing: 0.2em; color: var(--color-parchment); margin: 0">Caractéristiques</h3>
              </div>
              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px">
                <div
                  v-for="(labels, key) in ABILITY_LABELS"
                  :key="key"
                  class="text-center rounded-lg border"
                  style="padding: 10px; background: var(--color-surface); border-color: var(--color-border)"
                >
                  <div style="font-size: 9px; font-weight: 700; letter-spacing: 0.2em; color: var(--color-text-dim)">{{ labels.abbr }}</div>
                  <div class="font-display font-bold" style="font-size: 24px; line-height: 1.1; margin: 2px 0; color: var(--color-parchment)">
                    {{ scores[key] ?? '—' }}
                  </div>
                  <div
                    class="font-mono font-bold rounded inline-block"
                    style="font-size: 11px; padding: 2px 8px"
                    :style="{
                      color: (mods[key] ?? 0) >= 0 ? 'var(--color-green)' : 'var(--color-blood)',
                      background: (mods[key] ?? 0) >= 0 ? 'rgba(111,217,111,0.12)' : 'rgba(232,69,69,0.12)',
                    }"
                  >{{ fmtMod(mods[key] ?? 0) }}</div>
                  <div style="font-size: 9px; color: var(--color-text-dim); margin-top: 3px">{{ labels.name_fr }}</div>
                </div>
              </div>
            </div>

            <!-- Jets de sauvegarde -->
            <div class="rounded-xl" style="background: var(--color-bg-elev); border: 1px solid var(--color-border); padding: 14px">
              <div class="flex items-baseline gap-2" style="margin-bottom: 10px">
                <span style="color: var(--color-ember); font-size: 10px">✦</span>
                <h3 class="font-display font-bold uppercase" style="font-size: 11px; letter-spacing: 0.2em; color: var(--color-parchment); margin: 0">Jets de sauvegarde</h3>
              </div>
              <div style="display: flex; flex-direction: column; gap: 4px">
                <div
                  v-for="(labels, key) in ABILITY_LABELS"
                  :key="key"
                  class="flex items-center gap-2.5 rounded"
                  style="padding: 5px 10px"
                  :style="{ background: saveProficiencies.includes(key) ? 'rgba(240,199,100,0.04)' : 'transparent' }"
                >
                  <div
                    class="rounded-full border flex-shrink-0"
                    style="width: 10px; height: 10px"
                    :style="{
                      background: saveProficiencies.includes(key) ? 'var(--color-gold)' : 'transparent',
                      borderColor: saveProficiencies.includes(key) ? 'var(--color-gold)' : 'var(--color-border-strong)',
                      boxShadow: saveProficiencies.includes(key) ? '0 0 6px var(--color-gold)' : 'none',
                    }"
                  />
                  <span class="flex-1 text-sm" style="color: var(--color-parchment-dark)">{{ labels.name_fr }}</span>
                  <span
                    class="font-mono font-bold"
                    style="font-size: 12px; width: 28px; text-align: right"
                    :style="{ color: saveBonus(key) >= 0 ? 'var(--color-green)' : 'var(--color-blood)' }"
                  >{{ fmtMod(saveBonus(key)) }}</span>
                </div>
              </div>
            </div>

          </div>

          <!-- ══ CENTER: Skills + Features + Personality + Spells ══════════ -->
          <div style="display: flex; flex-direction: column; gap: 16px">

            <!-- Compétences -->
            <div class="rounded-xl" style="background: var(--color-bg-elev); border: 1px solid var(--color-border); padding: 14px">
              <div class="flex items-baseline gap-2" style="margin-bottom: 10px">
                <span style="color: var(--color-ember); font-size: 10px">✦</span>
                <h3 class="font-display font-bold uppercase" style="font-size: 11px; letter-spacing: 0.2em; color: var(--color-parchment); margin: 0">Compétences</h3>
                <span style="font-size: 10px; color: var(--color-text-dim); font-style: italic">— Disque plein = maîtrise</span>
              </div>
              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 4px">
                <div
                  v-for="skill in SKILLS"
                  :key="skill.id"
                  class="flex items-center gap-2 rounded"
                  style="padding: 5px 8px"
                  :style="{ background: skillProficiencies.includes(skill.id) ? 'rgba(240,199,100,0.05)' : 'transparent' }"
                >
                  <div
                    class="rounded-full border flex-shrink-0"
                    style="width: 9px; height: 9px"
                    :style="{
                      background: skillProficiencies.includes(skill.id) ? 'var(--color-gold)' : 'transparent',
                      borderColor: skillProficiencies.includes(skill.id) ? 'var(--color-gold)' : 'var(--color-border-strong)',
                    }"
                  />
                  <span class="flex-1" style="font-size: 12px; color: var(--color-parchment-dark)">{{ skill.name_fr }}</span>
                  <span class="font-mono uppercase" style="font-size: 9px; font-weight: 700; color: var(--color-text-dim); letter-spacing: 0.1em">
                    {{ ABILITY_LABELS[skill.ability]?.abbr }}
                  </span>
                  <span
                    class="font-mono font-bold"
                    style="font-size: 11px; width: 22px; text-align: right"
                    :style="{ color: skillBonus(skill) >= 0 ? 'var(--color-green)' : 'var(--color-blood)' }"
                  >{{ fmtMod(skillBonus(skill)) }}</span>
                </div>
              </div>
            </div>

            <!-- Aptitudes de classe -->
            <div
              v-if="srdClass?.level_1_features?.length"
              class="rounded-xl"
              style="background: var(--color-bg-elev); border: 1px solid rgba(255,130,71,0.4); padding: 14px"
            >
              <div class="flex items-baseline gap-2" style="margin-bottom: 10px">
                <span style="color: var(--color-ember); font-size: 10px">✦</span>
                <h3 class="font-display font-bold uppercase" style="font-size: 11px; letter-spacing: 0.2em; color: var(--color-ember); margin: 0">Aptitudes de classe</h3>
              </div>
              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px">
                <div
                  v-for="feature in srdClass.level_1_features"
                  :key="feature.name"
                  class="rounded-lg border"
                  style="padding: 10px; background: var(--color-surface); border-color: var(--color-border)"
                >
                  <div class="font-display font-bold" style="font-size: 12px; color: var(--color-ember); margin-bottom: 3px">
                    {{ feature.name_fr }}
                  </div>
                  <div class="font-serif" style="font-size: 12px; color: var(--color-parchment-dark); line-height: 1.45">
                    {{ feature.description }}
                  </div>
                </div>
              </div>
            </div>

            <!-- Personnalité -->
            <div
              v-if="personalityBlock"
              class="rounded-xl"
              style="background: var(--color-bg-elev); border: 1px solid rgba(192,144,255,0.4); padding: 14px"
            >
              <div class="flex items-baseline gap-2" style="margin-bottom: 10px">
                <span style="color: var(--color-arcane); font-size: 10px">✦</span>
                <h3 class="font-display font-bold uppercase" style="font-size: 11px; letter-spacing: 0.2em; color: var(--color-arcane); margin: 0">Personnalité</h3>
              </div>
              <div class="font-serif" style="font-size: 13px; color: var(--color-parchment-dark); line-height: 1.6">
                <p v-for="(t, i) in personalityBlock.traits" :key="i" style="margin: 0 0 8px">
                  <span style="color: var(--color-arcane); font-weight: 700">Trait · </span>{{ t }}
                </p>
                <p v-if="personalityBlock.bonds" style="margin: 0 0 8px">
                  <span style="color: var(--color-arcane); font-weight: 700">Lien · </span>{{ personalityBlock.bonds }}
                </p>
                <p v-if="personalityBlock.flaws" style="margin: 0">
                  <span style="color: var(--color-arcane); font-weight: 700">Défaut · </span>{{ personalityBlock.flaws }}
                </p>
              </div>
            </div>

            <!-- Magie (spellcasters only) -->
            <div
              v-if="isSpellcaster"
              class="rounded-xl"
              style="background: var(--color-bg-elev); border: 1px solid rgba(192,144,255,0.3); padding: 14px"
            >
              <div class="flex items-baseline gap-2" style="margin-bottom: 12px">
                <span style="color: var(--color-arcane); font-size: 10px">✦</span>
                <h3 class="font-display font-bold uppercase" style="font-size: 11px; letter-spacing: 0.2em; color: var(--color-arcane); margin: 0">Magie</h3>
              </div>

              <div v-if="spellSlotEntries.length" style="margin-bottom: 16px">
                <p style="font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em; color: var(--color-text-muted); margin: 0 0 8px">
                  Emplacements de sorts
                </p>
                <div class="flex flex-wrap gap-3">
                  <div
                    v-for="slot in spellSlotEntries"
                    :key="slot.level"
                    class="rounded-lg border px-3 py-2 text-center"
                    style="border-color: rgba(192,144,255,0.3); background: rgba(192,144,255,0.08)"
                  >
                    <p class="font-display font-bold" style="font-size: 11px; color: var(--color-arcane); margin: 0 0 4px">Niv. {{ slot.level }}</p>
                    <div class="flex gap-1 justify-center">
                      <div
                        v-for="i in slot.total"
                        :key="i"
                        class="rounded-full border"
                        style="width: 10px; height: 10px"
                        :style="{
                          borderColor: 'rgba(192,144,255,0.6)',
                          background: i <= slot.total - slot.used ? 'var(--color-arcane)' : 'transparent',
                          boxShadow: i <= slot.total - slot.used ? '0 0 6px var(--color-arcane)' : 'none',
                        }"
                      />
                    </div>
                    <p class="font-mono" style="font-size: 10px; color: var(--color-text-muted); margin: 6px 0 0">
                      {{ slot.total - slot.used }}/{{ slot.total }}
                    </p>
                  </div>
                </div>
              </div>

              <div>
                <p style="font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em; color: var(--color-text-muted); margin: 0 0 8px">
                  Sorts connus ({{ character.known_spells?.length ?? 0 }})
                </p>
                <div v-if="spellDetails.length" style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px">
                  <div
                    v-for="spell in spellDetails"
                    :key="spell.id"
                    class="rounded-lg border px-3 py-2"
                    style="border-color: rgba(192,144,255,0.2); background: var(--color-surface)"
                  >
                    <div class="flex items-start justify-between gap-1">
                      <p class="font-display font-bold" style="font-size: 12px; color: var(--color-parchment); margin: 0">{{ spell.name_fr }}</p>
                      <span
                        class="rounded flex-shrink-0"
                        style="font-size: 10px; font-weight: 700; color: var(--color-arcane); background: rgba(192,144,255,0.15); padding: 2px 6px"
                      >{{ spell.level === 0 ? 'Tour' : 'Niv.' + spell.level }}</span>
                    </div>
                    <p class="font-serif italic" style="font-size: 11px; color: var(--color-text-muted); margin: 2px 0 0">
                      {{ SPELL_SCHOOLS[spell.school] ?? spell.school }}
                    </p>
                    <p v-if="spell.damage_dice" class="font-mono" style="font-size: 11px; color: var(--color-gold); margin: 4px 0 0">
                      {{ spell.damage_dice }} {{ spell.damage_type }}
                    </p>
                  </div>
                </div>
                <div v-else class="flex flex-wrap gap-1.5">
                  <span
                    v-for="spellId in character.known_spells"
                    :key="spellId"
                    class="rpg-chip"
                    style="color: var(--color-arcane); background: rgba(192,144,255,0.08); border-color: rgba(192,144,255,0.25)"
                  >{{ spellId }}</span>
                </div>
              </div>
            </div>

          </div>

          <!-- ══ RIGHT: Equipment + Conditions + Quick actions ══════════════ -->
          <div style="display: flex; flex-direction: column; gap: 16px">

            <!-- Équipement -->
            <div class="rounded-xl" style="background: var(--color-bg-elev); border: 1px solid var(--color-border); padding: 14px">
              <div class="flex items-baseline gap-2" style="margin-bottom: 10px">
                <span style="color: var(--color-ember); font-size: 10px">✦</span>
                <h3 class="font-display font-bold uppercase" style="font-size: 11px; letter-spacing: 0.2em; color: var(--color-parchment); margin: 0">Équipement</h3>
              </div>

              <p
                v-if="inventoryError"
                class="rounded-lg border text-xs"
                style="padding: 8px 12px; margin-bottom: 10px; border-color: rgba(232,69,69,0.4); background: rgba(232,69,69,0.1); color: var(--color-blood-light)"
              >{{ inventoryError }}</p>

              <div v-if="character.equipment?.length" style="display: flex; flex-direction: column; gap: 6px">
                <div
                  v-for="(item, idx) in (character.equipment as Record<string, unknown>[])"
                  :key="idx"
                  class="rounded-lg border"
                  style="padding: 8px 10px"
                  :style="{
                    background: item.equipped ? 'rgba(240,199,100,0.06)' : 'var(--color-surface)',
                    borderColor: item.equipped ? 'rgba(240,199,100,0.25)' : 'var(--color-border)',
                  }"
                >
                  <div class="flex items-center gap-1.5">
                    <span style="font-size: 11px" :style="{ color: item.equipped ? 'var(--color-gold)' : 'var(--color-text-dim)' }">
                      {{ item.equipped ? '⚔' : '○' }}
                    </span>
                    <span
                      class="flex-1 font-display font-bold capitalize"
                      style="font-size: 13px"
                      :style="{ color: item.equipped ? 'var(--color-parchment)' : 'var(--color-parchment-dark)' }"
                    >{{ String(item.name_fr ?? item.id ?? 'Objet') }}</span>
                    <span
                      v-if="item.quantity && Number(item.quantity) > 1"
                      class="font-mono"
                      style="font-size: 10px; color: var(--color-text-muted)"
                    >×{{ item.quantity }}</span>
                  </div>

                  <div
                    v-if="item.detail || item.damage_dice"
                    style="font-size: 10px; color: var(--color-text-muted); margin-top: 2px; padding-left: 17px"
                  >{{ item.detail ?? (item.damage_dice ? `${item.damage_dice} ${item.damage_type ?? ''}` : '') }}</div>

                  <div class="flex gap-1.5 mt-1.5" style="padding-left: 17px">
                    <button
                      v-if="isEquippable(item)"
                      class="rounded border"
                      style="padding: 2px 8px; font-size: 10px; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase; cursor: pointer; background: transparent; transition: border-color 120ms, color 120ms"
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
                      class="rounded border"
                      style="padding: 2px 8px; font-size: 10px; text-transform: uppercase; letter-spacing: 0.05em; cursor: pointer; background: transparent; border-color: var(--color-border); color: var(--color-text-dim)"
                      :disabled="inventoryLoading === item.id"
                      @click="itemToDrop = String(item.id)"
                    >Lâcher</button>
                  </div>
                </div>
              </div>
              <p v-else class="font-serif italic text-sm" style="color: var(--color-text-dim)">Aucun objet</p>
            </div>

            <!-- État (conditions) -->
            <div class="rounded-xl" style="background: var(--color-bg-elev); border: 1px solid rgba(232,69,69,0.4); padding: 14px">
              <div class="flex items-baseline gap-2" style="margin-bottom: 10px">
                <span style="color: var(--color-blood); font-size: 10px">✦</span>
                <h3 class="font-display font-bold uppercase" style="font-size: 11px; letter-spacing: 0.2em; color: var(--color-blood); margin: 0">État</h3>
              </div>
              <div v-if="character.conditions?.length" class="flex flex-wrap gap-1.5">
                <span
                  v-for="cond in character.conditions"
                  :key="cond"
                  class="rpg-chip capitalize"
                  style="color: var(--color-blood); background: rgba(232,69,69,0.15); border-color: rgba(232,69,69,0.4)"
                >{{ cond }}</span>
              </div>
              <p
                v-else
                class="font-serif italic text-sm text-center"
                style="color: var(--color-text-muted); padding: 4px 0"
              >Aucune condition active</p>
            </div>

            <!-- Actions rapides -->
            <div class="rounded-xl" style="background: var(--color-bg-elev); border: 1px solid var(--color-border); padding: 14px">
              <div class="flex items-baseline gap-2" style="margin-bottom: 10px">
                <span style="color: var(--color-ember); font-size: 10px">✦</span>
                <h3 class="font-display font-bold uppercase" style="font-size: 11px; letter-spacing: 0.2em; color: var(--color-parchment); margin: 0">Actions rapides</h3>
              </div>
              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px">
                <button class="rounded-md border py-2.5" style="font-size: 11px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; cursor: pointer; color: var(--color-blood); background: rgba(232,69,69,0.08); border-color: rgba(232,69,69,0.4)">⚔ Attaquer</button>
                <button class="rounded-md border py-2.5" style="font-size: 11px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; cursor: pointer; color: var(--color-teal); background: rgba(79,216,192,0.08); border-color: rgba(79,216,192,0.4)">◈ Objet</button>
                <button class="rounded-md border py-2.5" style="font-size: 11px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; cursor: pointer; color: var(--color-arcane); background: rgba(192,144,255,0.08); border-color: rgba(192,144,255,0.4)">✦ Sort</button>
                <button class="rounded-md border py-2.5" style="font-size: 11px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; cursor: pointer; color: var(--color-green); background: rgba(111,217,111,0.08); border-color: rgba(111,217,111,0.4)">☽ Repos</button>
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
