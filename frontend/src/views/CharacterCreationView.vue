<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { srdApi, characterApi } from '../services/api'
import type { SrdSpecies, SrdClass, SrdEquipmentEntry, SrdSpell } from '../types'

// ─── Constants ────────────────────────────────────────────────────────────────

const TOTAL_STEPS = 9

const STANDARD_ARRAY = [15, 14, 13, 12, 10, 8]

const POINT_BUY_COST: Record<number, number> = { 8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9 }
const POINT_BUY_BUDGET = 27

const ABILITY_KEYS = ['str', 'dex', 'con', 'int', 'wis', 'cha'] as const

const ABILITY_INFO: Record<(typeof ABILITY_KEYS)[number], { fr: string; abbr: string }> = {
  str: { fr: 'Force', abbr: 'FOR' },
  dex: { fr: 'Dextérité', abbr: 'DEX' },
  con: { fr: 'Constitution', abbr: 'CON' },
  int: { fr: 'Intelligence', abbr: 'INT' },
  wis: { fr: 'Sagesse', abbr: 'SAG' },
  cha: { fr: 'Charisme', abbr: 'CHA' },
}

// Mapping noms complets → clés courtes (pour ability_bonuses du SRD)
const ABILITY_FULL_TO_KEY: Record<string, string> = {
  strength: 'str',
  dexterity: 'dex',
  constitution: 'con',
  intelligence: 'int',
  wisdom: 'wis',
  charisma: 'cha',
}

// Mapping clés courtes → noms complets (pour lookup dans ability_bonuses SRD)
const ABILITY_KEY_TO_FULL: Record<string, string> = {
  str: 'strength',
  dex: 'dexterity',
  con: 'constitution',
  int: 'intelligence',
  wis: 'wisdom',
  cha: 'charisma',
}

// Traduction française de l'équipement SRD
const EQUIPMENT_FR: Record<string, string> = {
  chain_mail: 'Cotte de mailles',
  leather: 'Armure de cuir',
  longbow: 'Arc long',
  shortbow: 'Arc court',
  light_crossbow: 'Arbalète légère',
  hand_crossbow: 'Arbalète de poing',
  martial_weapon: 'Arme de guerre',
  simple_weapon: 'Arme simple',
  shield: 'Bouclier',
  dagger: 'Dague',
  two_daggers: 'Deux dagues',
  rapier: 'Rapière',
  shortsword: 'Épée courte',
  longsword: 'Épée longue',
  handaxe: 'Hachette',
  mace: 'Masse',
  quarterstaff: 'Bâton',
  warhammer: 'Marteau de guerre',
  scale_mail: "Cotte d'écailles",
  arrows: 'Flèches',
  bolts: 'Carreaux',
  quiver: 'Carquois',
  arcane_focus: 'Focalisateur arcanique',
  component_pouch: 'Bourse de composantes',
  spellbook: 'Grimoire',
  thieves_tools: 'Outils de voleur',
  holy_symbol: 'Symbole sacré',
  dungeoneer_pack: "Paquetage d'aventurier",
  explorer_pack: "Paquetage d'explorateur",
  scholar_pack: "Paquetage d'érudit",
  burglar_pack: 'Paquetage de cambrioleur',
  priest_pack: 'Paquetage du prêtre',
  greataxe: 'Grande hache',
  javelin: 'Javelot',
  lute: 'Luth',
  diplomat_pack: 'Paquetage du diplomate',
  entertainer_pack: 'Paquetage du saltimbanque',
  scimitar: 'Cimeterre',
  druidic_focus: 'Focalisateur druidique',
  wooden_shield: 'Bouclier de bois',
  simple_melee_weapon: 'Arme de corps-à-corps simple',
  musical_instrument: 'Instrument de musique',
  dart: 'Fléchette',
  herbalism_kit: "Kit d'herboristerie",
}

const SKILL_FR: Record<string, string> = {
  acrobatics: 'Acrobaties',
  animal_handling: 'Dressage',
  arcana: 'Arcanes',
  athletics: 'Athlétisme',
  deception: 'Duperie',
  history: 'Histoire',
  insight: 'Intuition',
  intimidation: 'Intimidation',
  investigation: 'Investigation',
  medicine: 'Médecine',
  nature: 'Nature',
  perception: 'Perception',
  performance: 'Représentation',
  persuasion: 'Persuasion',
  religion: 'Religion',
  sleight_of_hand: 'Escamotage',
  stealth: 'Discrétion',
  survival: 'Survie',
}

const STEP_LABELS = [
  'Espèce',
  'Classe',
  'Historique',
  'Caractéristiques',
  'Ajustements',
  'Compétences',
  'Équipement',
  'Sorts',
  'Nom',
]

const CASTER_LEVEL1: Record<string, { cantrips: number; spells: number }> = {
  wizard:   { cantrips: 3, spells: 6 },
  cleric:   { cantrips: 3, spells: 0 },
  druid:    { cantrips: 3, spells: 0 },
  bard:     { cantrips: 2, spells: 4 },
  sorcerer: { cantrips: 4, spells: 2 },
  warlock:  { cantrips: 2, spells: 2 },
}

interface Background {
  id: string
  name_fr: string
  description: string
  skills: string[]
}

const BACKGROUNDS: Background[] = [
  {
    id: 'acolyte',
    name_fr: 'Acolyte',
    description: 'Vous avez passé votre vie au service d\'un temple, apprenant ses rites et prières.',
    skills: ['insight', 'religion'],
  },
  {
    id: 'criminal',
    name_fr: 'Criminel',
    description: 'Vous avez un passé dans les milieux criminels et un réseau de contacts louches.',
    skills: ['deception', 'stealth'],
  },
  {
    id: 'folk_hero',
    name_fr: 'Héros du Peuple',
    description: 'Issu de la classe humble, vous avez accompli un acte qui vous a valu la célébrité.',
    skills: ['animal_handling', 'survival'],
  },
  {
    id: 'noble',
    name_fr: 'Noble',
    description: 'Vous comprenez la richesse, le pouvoir et les privilèges de la haute société.',
    skills: ['history', 'persuasion'],
  },
  {
    id: 'sage',
    name_fr: 'Sage',
    description: 'Vous avez consacré des années à l\'étude des mystères du monde dans une bibliothèque.',
    skills: ['arcana', 'history'],
  },
  {
    id: 'soldier',
    name_fr: 'Soldat',
    description: 'Vous avez servi dans une armée et appris la guerre, la discipline et la camaraderie.',
    skills: ['athletics', 'intimidation'],
  },
]

// Caractéristiques proposées par chaque historique pour les ajustements (SRD 5.2)
const BG_ABILITY_SCORES: Record<string, string[]> = {
  acolyte:   ['int', 'wis', 'cha'],
  criminal:  ['dex', 'con', 'int'],
  folk_hero: ['str', 'dex', 'wis'],
  noble:     ['str', 'dex', 'cha'],
  sage:      ['con', 'int', 'wis'],
  soldier:   ['str', 'dex', 'con'],
}

// ─── Route / Router ───────────────────────────────────────────────────────────

const route = useRoute()
const router = useRouter()
const sessionId = route.params.id as string

// ─── State ────────────────────────────────────────────────────────────────────

const step = ref(1)
const loading = ref(false)
const submitError = ref<string | null>(null)

// SRD data
const speciesList = ref<SrdSpecies[]>([])
const classList = ref<SrdClass[]>([])

// Step 1: Espèce
const selectedSpeciesId = ref<string | null>(null)

// Step 2: Classe
const selectedClassId = ref<string | null>(null)

// Step 3: Background
const selectedBackgroundId = ref<string | null>(null)

// Step 4: Méthode de génération des caractéristiques
type StatMethod = 'standard' | 'rolled' | 'pointbuy'
const statMethod = ref<StatMethod | null>(null)

// Step 4 — pool assignment (standard & rolled)
const assignments = ref<Record<string, number | null>>({
  str: null, dex: null, con: null, int: null, wis: null, cha: null,
})

// Step 4 — génération aléatoire
const rolledValues = ref<number[]>([])

// Step 4 — acquisition par points
const pointBuyScores = ref<Record<string, number>>({
  str: 8, dex: 8, con: 8, int: 8, wis: 8, cha: 8,
})

// Step 5: Ajustements de caractéristiques (bonus historique)
type BgBonusMode = 'two_one' | 'all_one'
const bgBonusMode = ref<BgBonusMode | null>(null)
const bgBonus2Stat = ref<string | null>(null)   // stat qui reçoit +2
const bgBonus1Stat = ref<string | null>(null)   // stat qui reçoit +1 (mode two_one)

// Step 6: Compétences
const selectedSkills = ref<string[]>([])

// Step 6: Équipement (choiceGroupIndex -> optionIndex)
const equipmentChoices = ref<Record<number, number>>({})

// Step 7: Sorts
const selectedCantrips = ref<string[]>([])
const selectedSpells = ref<string[]>([])
const availableCantrips = ref<SrdSpell[]>([])
const availableSpells = ref<SrdSpell[]>([])
const spellsLoading = ref(false)

// Step 8: Nom
const characterName = ref('')
const isAi = ref(false)

// ─── Derived State ────────────────────────────────────────────────────────────

const selectedSpecies = computed(() =>
  speciesList.value.find((s) => s.id === selectedSpeciesId.value) ?? null,
)

const selectedClass = computed(() =>
  classList.value.find((c) => c.id === selectedClassId.value) ?? null,
)

const selectedBackground = computed(() =>
  BACKGROUNDS.find((b) => b.id === selectedBackgroundId.value) ?? null,
)

// Values already assigned to other stats
const usedArrayValues = computed(() =>
  (Object.values(assignments.value) as (number | null)[]).filter((v) => v !== null) as number[],
)

// Options disponibles pour une caractéristique donnée (gère les doublons dans les jets)
function optionsForStat(key: string): number[] {
  const pool = statMethod.value === 'rolled' ? rolledValues.value : STANDARD_ARRAY
  const current = assignments.value[key]
  // Count occurrences of each value in the pool
  const poolCounts = pool.reduce((acc, v) => { acc[v] = (acc[v] ?? 0) + 1; return acc }, {} as Record<number, number>)
  // Count occurrences used by other stats
  const usedCounts = Object.entries(assignments.value)
    .filter(([k]) => k !== key)
    .reduce((acc, [, v]) => { if (v !== null) acc[v] = (acc[v] ?? 0) + 1; return acc }, {} as Record<number, number>)

  return Object.keys(poolCounts)
    .map(Number)
    .filter((v) => v === current || (poolCounts[v] ?? 0) - (usedCounts[v] ?? 0) > 0)
    .sort((a, b) => b - a)
}

// Les 3 caractéristiques proposées par l'historique sélectionné
const bgAbilityStats = computed<string[]>(() =>
  selectedBackgroundId.value ? (BG_ABILITY_SCORES[selectedBackgroundId.value] ?? []) : [],
)

// Ajustements de caractéristiques apportés par l'historique
const bgAdjustments = computed<Record<string, number>>(() => {
  if (!bgBonusMode.value) return {}
  if (bgBonusMode.value === 'all_one') {
    return Object.fromEntries(bgAbilityStats.value.map((s) => [s, 1]))
  }
  const result: Record<string, number> = {}
  if (bgBonus2Stat.value) result[bgBonus2Stat.value] = 2
  if (bgBonus1Stat.value) result[bgBonus1Stat.value] = 1
  return result
})

// Point buy: points dépensés / restants
const pointsSpent = computed(() =>
  Object.values(pointBuyScores.value).reduce((sum, v) => sum + (POINT_BUY_COST[v] ?? 0), 0),
)
const pointsRemaining = computed(() => POINT_BUY_BUDGET - pointsSpent.value)

// Scores finaux (base + bonus espèce + ajustement historique, cap 20)
const finalScores = computed(() => {
  const speciesBonuses = selectedSpecies.value?.ability_bonuses ?? {}
  return Object.fromEntries(
    ABILITY_KEYS.map((key) => {
      const base =
        statMethod.value === 'pointbuy'
          ? (pointBuyScores.value[key] ?? 8)
          : (assignments.value[key] ?? 10)
      const fullKey = ABILITY_KEY_TO_FULL[key] ?? key
      const specBonus = speciesBonuses[fullKey] ?? 0
      const bgBonus = bgAdjustments.value[key] ?? 0
      return [key, Math.min(20, base + specBonus + bgBonus)]
    }),
  )
})

const conMod = computed(() => Math.floor(((finalScores.value.con as number) - 10) / 2))
const hpMax = computed(() => (selectedClass.value?.hit_die ?? 8) + conMod.value)

const isCaster = computed(() => !!selectedClass.value?.spellcasting_ability)
const numCantrips = computed(() => CASTER_LEVEL1[selectedClassId.value ?? '']?.cantrips ?? 0)
const numSpells = computed(() => CASTER_LEVEL1[selectedClassId.value ?? '']?.spells ?? 0)

// Groupes de choix d'équipement (entrées "choice" uniquement)
interface EquipmentChoiceGroup extends SrdEquipmentEntry {
  originalIndex: number
  choice: string[][]
}

const equipmentChoiceGroups = computed<EquipmentChoiceGroup[]>(() =>
  (selectedClass.value?.starting_equipment ?? [])
    .map((entry, i) => ({ ...entry, originalIndex: i }))
    .filter((e): e is EquipmentChoiceGroup => Array.isArray(e.choice)),
)

// Équipement fixe (toujours inclus)
const equipmentFixed = computed(() =>
  (selectedClass.value?.starting_equipment ?? [])
    .filter((e) => Array.isArray(e.fixed))
    .flatMap((e) => e.fixed ?? []),
)

// ─── Helpers ──────────────────────────────────────────────────────────────────

function modStr(score: number): string {
  const mod = Math.floor((score - 10) / 2)
  return mod >= 0 ? `+${mod}` : `${mod}`
}

function formatOption(items: string[]): string {
  return items
    .map((i) => {
      // Cas "20 arrows", "20 bolts" : traiter le chiffre séparément
      const match = i.match(/^(\d+)\s+(.+)$/)
      if (match) {
        const qty = match[1]
        const key = match[2]!.replace(/\s+/g, '_')
        return `${qty} ${EQUIPMENT_FR[key] ?? match[2]!}`
      }
      return EQUIPMENT_FR[i] ?? i.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
    })
    .join(' + ')
}

// Tells whether the i-th element of the pool is "consumed" (shown as strikethrough)
// Works correctly even when the pool contains duplicate values.
function isPoolValueUsed(value: number, poolIndex: number): boolean {
  const pool = statMethod.value === 'rolled' ? rolledValues.value : STANDARD_ARRAY
  // How many instances of `value` appear at or before this index in the pool
  const instanceIndex = pool.slice(0, poolIndex + 1).filter((v) => v === value).length - 1
  // How many times `value` has been assigned across all stats
  const usedCount = (Object.values(assignments.value) as (number | null)[])
    .filter((v) => v === value).length
  return instanceIndex < usedCount
}

function assignStat(key: string, event: Event) {
  const val = (event.target as HTMLSelectElement).value
  assignments.value[key] = val === '' ? null : parseInt(val)
}

function selectStatMethod(method: StatMethod) {
  statMethod.value = method
  ABILITY_KEYS.forEach((k) => { assignments.value[k] = null })
  if (method === 'rolled') rolledValues.value = []
  if (method === 'pointbuy') ABILITY_KEYS.forEach((k) => { pointBuyScores.value[k] = 8 })
}

function rollDie(sides: number): number {
  return Math.floor(Math.random() * sides) + 1
}

function roll4d6DropLowest(): number {
  const rolls = [rollDie(6), rollDie(6), rollDie(6), rollDie(6)]
  rolls.sort((a, b) => a - b)
  return rolls.slice(1).reduce((sum, v) => sum + v, 0)
}

function rollAbilityScores() {
  rolledValues.value = Array.from({ length: 6 }, () => roll4d6DropLowest())
  ABILITY_KEYS.forEach((k) => { assignments.value[k] = null })
}

function canIncrease(key: string): boolean {
  const cur = pointBuyScores.value[key] ?? 8
  if (cur >= 15) return false
  const addedCost = (POINT_BUY_COST[cur + 1] ?? 0) - (POINT_BUY_COST[cur] ?? 0)
  return pointsRemaining.value >= addedCost
}

function canDecrease(key: string): boolean {
  return (pointBuyScores.value[key] ?? 8) > 8
}

function increaseStat(key: string) {
  if (canIncrease(key)) pointBuyScores.value[key] = (pointBuyScores.value[key] ?? 8) + 1
}

function decreaseStat(key: string) {
  if (canDecrease(key)) pointBuyScores.value[key] = (pointBuyScores.value[key] ?? 8) - 1
}

// Helper pour afficher le bonus d'espèce depuis la clé courte
function speciesBonusFor(key: string): number {
  const full = ABILITY_KEY_TO_FULL[key] ?? key
  return selectedSpecies.value?.ability_bonuses[full] ?? 0
}

// Helper pour le coût point buy d'une stat
function pointBuyCostFor(key: string): number {
  return POINT_BUY_COST[pointBuyScores.value[key] ?? 8] ?? 0
}

function toggleSkill(skill: string) {
  const max = selectedClass.value?.num_skill_choices ?? 0
  const idx = selectedSkills.value.indexOf(skill)
  if (idx >= 0) {
    selectedSkills.value.splice(idx, 1)
  } else if (selectedSkills.value.length < max) {
    selectedSkills.value.push(skill)
  }
}

function toggleCantrip(id: string) {
  const idx = selectedCantrips.value.indexOf(id)
  if (idx >= 0) selectedCantrips.value.splice(idx, 1)
  else if (selectedCantrips.value.length < numCantrips.value) selectedCantrips.value.push(id)
}

function toggleSpell(id: string) {
  const idx = selectedSpells.value.indexOf(id)
  if (idx >= 0) selectedSpells.value.splice(idx, 1)
  else if (selectedSpells.value.length < numSpells.value) selectedSpells.value.push(id)
}

async function loadSpells() {
  if (!selectedClassId.value || !isCaster.value) return
  spellsLoading.value = true
  try {
    const [cantripData, spellData] = await Promise.all([
      srdApi.listSpells({ level: 0, charClass: selectedClassId.value }),
      srdApi.listSpells({ level: 1, charClass: selectedClassId.value }),
    ])
    availableCantrips.value = cantripData.spells
    availableSpells.value = spellData.spells
  } finally {
    spellsLoading.value = false
  }
}

// ─── Validation ───────────────────────────────────────────────────────────────

const canProceed = computed(() => {
  switch (step.value) {
    case 1:
      return selectedSpeciesId.value !== null
    case 2:
      return selectedClassId.value !== null
    case 3:
      return selectedBackgroundId.value !== null
    case 4:
      if (!statMethod.value) return false
      if (statMethod.value === 'pointbuy') return true
      if (statMethod.value === 'rolled' && rolledValues.value.length === 0) return false
      return (Object.values(assignments.value) as (number | null)[]).every((v) => v !== null)
    case 5:
      if (!bgBonusMode.value) return false
      if (bgBonusMode.value === 'all_one') return true
      return bgBonus2Stat.value !== null && bgBonus1Stat.value !== null
    case 6: {
      const numRequired = selectedClass.value?.num_skill_choices ?? 0
      return selectedSkills.value.length === numRequired
    }
    case 7:
      return equipmentChoiceGroups.value.every((_, i) => equipmentChoices.value[i] !== undefined)
    case 8: {
      if (!isCaster.value) return true
      return (
        selectedCantrips.value.length === numCantrips.value &&
        selectedSpells.value.length === numSpells.value
      )
    }
    case 9:
      return characterName.value.trim().length > 0
    default:
      return false
  }
})

// ─── Navigation ───────────────────────────────────────────────────────────────

function nextStep() {
  if (canProceed.value && step.value < TOTAL_STEPS) step.value++
}

function prevStep() {
  if (step.value > 1) step.value--
}

// Réinitialiser les étapes dépendantes quand la classe change
watch(selectedClassId, () => {
  selectedSkills.value = []
  equipmentChoices.value = {}
  selectedCantrips.value = []
  selectedSpells.value = []
  availableCantrips.value = []
  availableSpells.value = []
})

// Réinitialiser les ajustements si l'historique change
watch(selectedBackgroundId, () => {
  bgBonusMode.value = null
  bgBonus2Stat.value = null
  bgBonus1Stat.value = null
})

watch(step, (newStep) => {
  if (newStep === 8 && isCaster.value) {
    loadSpells()
  }
})

// ─── Chargement SRD ───────────────────────────────────────────────────────────

onMounted(async () => {
  loading.value = true
  try {
    const [speciesData, classData] = await Promise.all([
      srdApi.listSpecies(),
      srdApi.listClasses(),
    ])
    speciesList.value = speciesData.species
    classList.value = classData.classes
  } catch {
    submitError.value = 'Impossible de charger les données SRD. Vérifiez que le backend est démarré.'
  } finally {
    loading.value = false
  }
})

// ─── Création du personnage ───────────────────────────────────────────────────

async function handleCreate() {
  if (!canProceed.value) return
  loading.value = true
  submitError.value = null

  // Construire la liste d'équipement
  const equipment: Record<string, unknown>[] = []
  equipmentChoiceGroups.value.forEach((group, i) => {
    const optIdx = equipmentChoices.value[i] ?? 0
    const items = group.choice[optIdx] ?? []
    items.forEach((item) =>
      equipment.push({ id: item, name_fr: formatOption([item]), quantity: 1 }),
    )
  })
  equipmentFixed.value.forEach((item) =>
    equipment.push({ id: item, name_fr: formatOption([item]), quantity: 1 }),
  )

  // Construire les maîtrises
  const proficiencies: Record<string, unknown> = {
    saving_throws: selectedClass.value?.saving_throw_proficiencies ?? [],
    skills: [
      ...new Set([
        ...selectedSkills.value,
        ...(selectedBackground.value?.skills ?? []),
        ...(selectedSpecies.value?.skill_proficiencies ?? []),
      ]),
    ],
    armor: selectedClass.value?.armor_proficiencies ?? [],
    weapons: selectedClass.value?.weapon_proficiencies ?? [],
    tools: selectedClass.value?.tool_proficiencies ?? [],
  }

  try {
    await characterApi.create({
      name: characterName.value.trim(),
      is_ai: isAi.value,
      species: selectedSpeciesId.value!,
      char_class: selectedClassId.value!,
      level: 1,
      background: selectedBackgroundId.value ?? undefined,
      ability_scores: finalScores.value as Record<string, number>,
      hp_current: hpMax.value,
      hp_max: hpMax.value,
      hp_temp: 0,
      equipment,
      proficiencies,
      known_spells: [...selectedCantrips.value, ...selectedSpells.value],
      session_id: sessionId,
    })
    router.push({ name: 'character-setup', params: { id: sessionId } })
  } catch {
    submitError.value = 'Impossible de créer le personnage. Réessayez.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="mx-auto max-w-4xl px-4 py-8">

    <!-- Titre -->
    <h1 class="mb-6 text-center text-4xl font-bold text-gold">Création de Personnage</h1>

    <!-- Chargement initial -->
    <div v-if="loading && speciesList.length === 0" class="py-20 text-center text-parchment-dark">
      Chargement des données SRD...
    </div>

    <!-- Erreur critique -->
    <div
      v-else-if="submitError && speciesList.length === 0"
      class="rounded border border-blood bg-blood/10 p-6 text-center text-blood-light"
    >
      {{ submitError }}
    </div>

    <template v-else>

      <!-- Indicateur d'étapes -->
      <div class="mb-8 flex items-center justify-between">
        <template v-for="(label, i) in STEP_LABELS" :key="i">
          <div class="flex flex-col items-center">
            <div
              :class="[
                'flex h-8 w-8 items-center justify-center rounded-full border-2 text-sm font-bold transition',
                i + 1 < step
                  ? 'border-gold bg-gold text-ink'
                  : i + 1 === step
                    ? 'border-gold bg-ink text-gold'
                    : 'border-stone bg-ink text-stone-light',
              ]"
            >
              <span v-if="i + 1 < step">✓</span>
              <span v-else>{{ i + 1 }}</span>
            </div>
            <span
              :class="[
                'mt-1 hidden text-xs sm:block',
                i + 1 === step ? 'text-gold' : 'text-stone-light',
              ]"
            >
              {{ label }}
            </span>
          </div>
          <div
            v-if="i < STEP_LABELS.length - 1"
            :class="['h-0.5 flex-1 mx-1', i + 1 < step ? 'bg-gold' : 'bg-stone']"
          />
        </template>
      </div>

      <!-- Contenu de l'étape -->
      <div class="min-h-96 rounded-lg border border-stone bg-ink-light p-6">

        <!-- Étape 1 : Espèce -->
        <template v-if="step === 1">
          <h2 class="mb-1 text-2xl font-bold text-gold">Choisissez votre Espèce</h2>
          <p class="mb-5 text-sm text-parchment-dark">Votre espèce définit vos traits naturels et vos bonus de caractéristiques.</p>
          <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <button
              v-for="species in speciesList"
              :key="species.id"
              class="rounded-lg border p-4 text-left transition"
              :class="
                selectedSpeciesId === species.id
                  ? 'border-gold bg-gold/10'
                  : 'border-stone hover:border-gold/40'
              "
              @click="selectedSpeciesId = species.id"
            >
              <div
                class="font-display text-lg font-bold"
                :class="selectedSpeciesId === species.id ? 'text-gold' : 'text-parchment'"
              >
                {{ species.name_fr }}
              </div>
              <p class="mt-1 line-clamp-2 text-xs text-parchment-dark">{{ species.description }}</p>
              <div class="mt-3 flex flex-wrap gap-1.5">
                <span class="rounded bg-stone/40 px-1.5 py-0.5 text-xs text-parchment-dark">
                  Vit. {{ species.speed }} m
                </span>
                <span v-if="species.darkvision_m > 0" class="rounded bg-arcane/20 px-1.5 py-0.5 text-xs text-arcane-light">
                  Vision nocturne {{ species.darkvision_m }} m
                </span>
              </div>
              <div class="mt-2 flex flex-wrap gap-1">
                <span
                  v-for="(bonus, stat) in species.ability_bonuses"
                  :key="stat"
                  class="rounded bg-gold/15 px-1.5 py-0.5 text-xs font-medium text-gold"
                >
                  {{ ABILITY_INFO[(ABILITY_FULL_TO_KEY[stat as string] ?? stat) as (typeof ABILITY_KEYS)[number]]?.abbr ?? (stat as string).toUpperCase() }} +{{ bonus }}
                </span>
              </div>
            </button>
          </div>

          <!-- Panneau de détail espèce sélectionnée -->
          <div
            v-if="selectedSpecies"
            class="mt-5 rounded border border-gold/30 bg-ink p-4"
          >
            <h3 class="mb-2 font-display font-bold text-gold">{{ selectedSpecies.name_fr }} — Traits</h3>
            <ul class="space-y-1">
              <li v-for="trait in selectedSpecies.traits" :key="trait.name" class="text-sm">
                <span class="font-semibold text-parchment">{{ trait.name_fr }}</span>
                <span class="text-parchment-dark"> — {{ trait.description }}</span>
              </li>
            </ul>
          </div>
        </template>

        <!-- Étape 2 : Classe -->
        <template v-if="step === 2">
          <h2 class="mb-1 text-2xl font-bold text-gold">Choisissez votre Classe</h2>
          <p class="mb-5 text-sm text-parchment-dark">Votre classe définit vos capacités, votre dé de vie et votre style de combat.</p>
          <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <button
              v-for="cls in classList"
              :key="cls.id"
              class="rounded-lg border p-4 text-left transition"
              :class="
                selectedClassId === cls.id
                  ? 'border-gold bg-gold/10'
                  : 'border-stone hover:border-gold/40'
              "
              @click="selectedClassId = cls.id"
            >
              <div
                class="font-display text-lg font-bold"
                :class="selectedClassId === cls.id ? 'text-gold' : 'text-parchment'"
              >
                {{ cls.name_fr }}
              </div>
              <p class="mt-1 line-clamp-2 text-xs text-parchment-dark">{{ cls.description }}</p>
              <div class="mt-3 flex flex-wrap gap-1.5">
                <span class="rounded bg-blood/20 px-1.5 py-0.5 text-xs text-blood-light">
                  d{{ cls.hit_die }} PV
                </span>
                <span
                  v-if="cls.spellcasting_ability"
                  class="rounded bg-arcane/20 px-1.5 py-0.5 text-xs text-arcane-light"
                >
                  Incantateur
                </span>
                <span class="rounded bg-stone/40 px-1.5 py-0.5 text-xs text-parchment-dark">
                  {{ cls.num_skill_choices }} compétences
                </span>
              </div>
            </button>
          </div>

          <!-- Détail classe sélectionnée -->
          <div v-if="selectedClass" class="mt-5 rounded border border-gold/30 bg-ink p-4">
            <h3 class="mb-2 font-display font-bold text-gold">{{ selectedClass.name_fr }} — Capacités niv. 1</h3>
            <ul class="space-y-1">
              <li v-for="feat in selectedClass.level_1_features" :key="feat.name" class="text-sm">
                <span class="font-semibold text-parchment">{{ feat.name_fr }}</span>
                <span class="text-parchment-dark"> — {{ feat.description }}</span>
              </li>
            </ul>
          </div>
        </template>

        <!-- Étape 3 : Historique -->
        <template v-if="step === 3">
          <h2 class="mb-1 text-2xl font-bold text-gold">Choisissez votre Historique</h2>
          <p class="mb-5 text-sm text-parchment-dark">Votre passé vous confère des maîtrises de compétences supplémentaires.</p>
          <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <button
              v-for="bg in BACKGROUNDS"
              :key="bg.id"
              class="rounded-lg border p-4 text-left transition"
              :class="
                selectedBackgroundId === bg.id
                  ? 'border-gold bg-gold/10'
                  : 'border-stone hover:border-gold/40'
              "
              @click="selectedBackgroundId = bg.id"
            >
              <div
                class="font-display text-lg font-bold"
                :class="selectedBackgroundId === bg.id ? 'text-gold' : 'text-parchment'"
              >
                {{ bg.name_fr }}
              </div>
              <p class="mt-1 text-xs text-parchment-dark">{{ bg.description }}</p>
              <div class="mt-3 flex flex-wrap gap-1">
                <span
                  v-for="skill in bg.skills"
                  :key="skill"
                  class="rounded bg-forest/20 px-1.5 py-0.5 text-xs text-forest-light"
                >
                  {{ SKILL_FR[skill] ?? skill }}
                </span>
              </div>
            </button>
          </div>
        </template>

        <!-- Étape 4 : Caractéristiques -->
        <template v-if="step === 4">
          <h2 class="mb-1 text-2xl font-bold text-gold">Répartissez vos Caractéristiques</h2>

          <!-- Sélection de la méthode -->
          <template v-if="!statMethod">
            <p class="mb-5 text-sm text-parchment-dark">Choisissez votre méthode de génération.</p>
            <div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <!-- Valeurs standard -->
              <button
                class="rounded-lg border border-stone p-5 text-left transition hover:border-gold/60"
                @click="selectStatMethod('standard')"
              >
                <div class="mb-1 font-display text-lg font-bold text-parchment">Valeurs standard</div>
                <p class="mb-3 text-xs text-parchment-dark">Assignez les six valeurs fixes : 15, 14, 13, 12, 10, 8.</p>
                <div class="flex flex-wrap gap-1.5">
                  <span v-for="v in STANDARD_ARRAY" :key="v" class="rounded bg-gold/15 px-2 py-0.5 text-xs font-bold text-gold">{{ v }}</span>
                </div>
              </button>

              <!-- Génération aléatoire -->
              <button
                class="rounded-lg border border-stone p-5 text-left transition hover:border-gold/60"
                @click="selectStatMethod('rolled')"
              >
                <div class="mb-1 font-display text-lg font-bold text-parchment">Génération aléatoire</div>
                <p class="mb-3 text-xs text-parchment-dark">Lancez 4d6, ignorez le dé le plus bas. Répétez 6 fois.</p>
                <div class="flex items-center gap-1.5">
                  <span v-for="i in 6" :key="i" class="flex h-7 w-7 items-center justify-center rounded bg-arcane/20 text-sm font-bold text-arcane-light">?</span>
                </div>
              </button>

              <!-- Acquisition par points -->
              <button
                class="rounded-lg border border-stone p-5 text-left transition hover:border-gold/60"
                @click="selectStatMethod('pointbuy')"
              >
                <div class="mb-1 font-display text-lg font-bold text-parchment">Acquisition par points</div>
                <p class="mb-3 text-xs text-parchment-dark">Dépensez 27 points pour personnaliser chaque caractéristique (8–15).</p>
                <div class="flex items-center gap-1 text-xs text-parchment-dark">
                  <span class="rounded bg-stone/40 px-2 py-0.5 font-bold text-parchment">27 pts</span>
                  <span>à répartir librement</span>
                </div>
              </button>
            </div>
          </template>

          <!-- UI partagée : tableau standard & jets aléatoires -->
          <template v-else-if="statMethod === 'standard' || statMethod === 'rolled'">
            <div class="mb-4 flex items-center gap-3">
              <button class="text-xs text-stone-light underline hover:text-parchment-dark" @click="statMethod = null">
                ← Changer de méthode
              </button>
              <span class="text-sm font-semibold text-parchment">
                {{ statMethod === 'standard' ? 'Valeurs standard' : 'Génération aléatoire' }}
              </span>
            </div>

            <!-- Bouton de lancement (méthode aléatoire) -->
            <div v-if="statMethod === 'rolled'" class="mb-4">
              <button
                class="rounded border border-arcane px-4 py-2 text-sm font-bold text-arcane-light transition hover:bg-arcane/10"
                @click="rollAbilityScores"
              >
                {{ rolledValues.length === 0 ? 'Lancer les dés (4d6)' : 'Relancer les dés' }}
              </button>
            </div>

            <!-- Valeurs du pool -->
            <div class="mb-5 flex flex-wrap gap-2">
              <span
                v-for="(v, i) in (statMethod === 'rolled' ? rolledValues : STANDARD_ARRAY)"
                :key="i"
                :class="[
                  'rounded border px-3 py-1 text-sm font-bold transition',
                  isPoolValueUsed(v, i) ? 'border-stone/30 text-stone-light line-through' : 'border-gold text-gold',
                ]"
              >
                {{ v }}
              </span>
            </div>

            <p v-if="statMethod === 'rolled' && rolledValues.length === 0" class="mb-4 text-sm text-parchment-dark italic">
              Cliquez sur "Lancer les dés" pour générer vos valeurs.
            </p>

            <div v-else class="grid grid-cols-2 gap-3 sm:grid-cols-3">
              <div
                v-for="key in ABILITY_KEYS"
                :key="key"
                class="rounded-lg border border-stone bg-ink p-3"
              >
                <div class="mb-2 text-xs font-semibold uppercase tracking-wider text-parchment-dark">
                  {{ ABILITY_INFO[key].fr }}
                </div>
                <select
                  :value="assignments[key] ?? ''"
                  class="w-full rounded border border-stone bg-ink-light px-2 py-1.5 text-parchment outline-none transition focus:border-gold"
                  @change="assignStat(key, $event)"
                >
                  <option value="">— Choisir —</option>
                  <option v-for="v in optionsForStat(key)" :key="v" :value="v">{{ v }}</option>
                </select>
                <div v-if="assignments[key] !== null" class="mt-2 flex items-baseline gap-2">
                  <span class="text-2xl font-bold text-gold">{{ finalScores[key] }}</span>
                  <span class="text-sm text-parchment-dark">{{ modStr(finalScores[key] as number) }}</span>
                  <span v-if="speciesBonusFor(key) > 0" class="text-xs text-arcane-light">
                    (+{{ speciesBonusFor(key) }} espèce)
                  </span>
                </div>
                <div v-else class="mt-2 text-lg text-stone-light">—</div>
              </div>
            </div>
          </template>

          <!-- UI : Acquisition par points -->
          <template v-else-if="statMethod === 'pointbuy'">
            <div class="mb-4 flex items-center justify-between">
              <button class="text-xs text-stone-light underline hover:text-parchment-dark" @click="statMethod = null">
                ← Changer de méthode
              </button>
              <div class="flex items-center gap-2 rounded border px-3 py-1.5 text-sm"
                :class="pointsRemaining === 0 ? 'border-gold/60 bg-gold/10 text-gold' : 'border-stone text-parchment'">
                <span class="font-bold text-lg">{{ pointsRemaining }}</span>
                <span class="text-parchment-dark">/ {{ POINT_BUY_BUDGET }} points restants</span>
              </div>
            </div>

            <!-- Table de coût (rappel) -->
            <div class="mb-5 flex flex-wrap gap-1.5 text-xs text-parchment-dark">
              <span v-for="(cost, score) in POINT_BUY_COST" :key="score"
                class="rounded bg-stone/30 px-2 py-0.5">
                {{ score }} <span class="text-stone-light">({{ cost }} pt{{ cost > 1 ? 's' : '' }})</span>
              </span>
            </div>

            <div class="grid grid-cols-2 gap-3 sm:grid-cols-3">
              <div
                v-for="key in ABILITY_KEYS"
                :key="key"
                class="rounded-lg border border-stone bg-ink p-3"
              >
                <div class="mb-2 text-xs font-semibold uppercase tracking-wider text-parchment-dark">
                  {{ ABILITY_INFO[key].fr }}
                </div>
                <div class="flex items-center gap-2">
                  <button
                    :disabled="!canDecrease(key)"
                    class="flex h-7 w-7 items-center justify-center rounded border text-lg font-bold transition disabled:cursor-not-allowed disabled:opacity-30"
                    :class="canDecrease(key) ? 'border-stone text-parchment hover:border-gold hover:text-gold' : 'border-stone/30 text-stone-light'"
                    @click="decreaseStat(key)"
                  >−</button>
                  <span class="min-w-8 text-center text-2xl font-bold text-gold">{{ pointBuyScores[key] }}</span>
                  <button
                    :disabled="!canIncrease(key)"
                    class="flex h-7 w-7 items-center justify-center rounded border text-lg font-bold transition disabled:cursor-not-allowed disabled:opacity-30"
                    :class="canIncrease(key) ? 'border-stone text-parchment hover:border-gold hover:text-gold' : 'border-stone/30 text-stone-light'"
                    @click="increaseStat(key)"
                  >+</button>
                </div>
                <div class="mt-2 flex items-baseline gap-2">
                  <span class="text-base font-bold text-parchment">{{ finalScores[key] }}</span>
                  <span class="text-sm text-parchment-dark">{{ modStr(finalScores[key] as number) }}</span>
                  <span v-if="speciesBonusFor(key) > 0" class="text-xs text-arcane-light">
                    (+{{ speciesBonusFor(key) }} espèce)
                  </span>
                </div>
                <div class="mt-1 text-xs text-stone-light">
                  Coût : {{ pointBuyCostFor(key) }} pt{{ pointBuyCostFor(key) > 1 ? 's' : '' }}
                </div>
              </div>
            </div>
          </template>

          <!-- Aperçu HP (commun) -->
          <div v-if="canProceed" class="mt-4 rounded border border-blood/40 bg-blood/10 px-4 py-2 text-sm">
            <span class="text-parchment-dark">Points de vie au niveau 1 : </span>
            <span class="font-bold text-blood-light">{{ hpMax }} PV</span>
            <span class="text-stone-light"> (d{{ selectedClass?.hit_die }} max + CON {{ modStr(finalScores.con as number) }})</span>
          </div>
        </template>

        <!-- Étape 5 : Ajustements de caractéristiques (historique) -->
        <template v-if="step === 5">
          <h2 class="mb-1 text-2xl font-bold text-gold">Ajustez vos Caractéristiques</h2>
          <p class="mb-2 text-sm text-parchment-dark">
            Votre historique <span class="font-semibold text-parchment">{{ selectedBackground?.name_fr }}</span>
            vous permet d'améliorer les caractéristiques suivantes :
          </p>

          <!-- Les 3 stats du background -->
          <div class="mb-5 flex flex-wrap gap-2">
            <span
              v-for="stat in bgAbilityStats"
              :key="stat"
              class="rounded border border-gold/50 bg-gold/10 px-3 py-1 text-sm font-bold text-gold"
            >
              {{ ABILITY_INFO[stat as (typeof ABILITY_KEYS)[number]]?.fr ?? stat }}
            </span>
          </div>

          <!-- Choix du mode -->
          <div v-if="!bgBonusMode" class="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <!-- +2 / +1 -->
            <button
              class="rounded-lg border border-stone p-5 text-left transition hover:border-gold/60"
              @click="bgBonusMode = 'two_one'"
            >
              <div class="mb-1 font-display text-lg font-bold text-parchment">+2 et +1</div>
              <p class="text-xs text-parchment-dark">Augmentez une caractéristique de 2 et une autre de 1.</p>
            </button>
            <!-- +1 / +1 / +1 -->
            <button
              class="rounded-lg border border-stone p-5 text-left transition hover:border-gold/60"
              @click="bgBonusMode = 'all_one'"
            >
              <div class="mb-1 font-display text-lg font-bold text-parchment">+1 / +1 / +1</div>
              <p class="text-xs text-parchment-dark">Augmentez chacune des trois caractéristiques de 1.</p>
            </button>
          </div>

          <!-- Mode +2 / +1 : sélection des stats -->
          <template v-else-if="bgBonusMode === 'two_one'">
            <button class="mb-4 text-xs text-stone-light underline hover:text-parchment-dark" @click="bgBonusMode = null; bgBonus2Stat = null; bgBonus1Stat = null">
              ← Changer de mode
            </button>
            <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <!-- Choix +2 -->
              <div>
                <p class="mb-2 text-sm font-semibold text-parchment">Caractéristique +2</p>
                <div class="flex flex-col gap-2">
                  <button
                    v-for="stat in bgAbilityStats"
                    :key="stat"
                    :disabled="bgBonus1Stat === stat"
                    class="rounded border px-4 py-2 text-left text-sm font-medium transition"
                    :class="bgBonus2Stat === stat
                      ? 'border-gold bg-gold/10 text-gold'
                      : bgBonus1Stat === stat
                        ? 'border-stone/30 text-stone-light cursor-not-allowed opacity-40'
                        : 'border-stone text-parchment-dark hover:border-gold/40'"
                    @click="bgBonus2Stat = stat"
                  >
                    <span class="font-bold">{{ ABILITY_INFO[stat as (typeof ABILITY_KEYS)[number]]?.fr ?? stat }}</span>
                    <span class="ml-2 text-xs text-stone-light">{{ finalScores[stat as (typeof ABILITY_KEYS)[number]] }} → {{ Math.min(20, (finalScores[stat as (typeof ABILITY_KEYS)[number]] as number) + 2) }}</span>
                  </button>
                </div>
              </div>
              <!-- Choix +1 -->
              <div>
                <p class="mb-2 text-sm font-semibold text-parchment">Caractéristique +1</p>
                <div class="flex flex-col gap-2">
                  <button
                    v-for="stat in bgAbilityStats"
                    :key="stat"
                    :disabled="bgBonus2Stat === stat"
                    class="rounded border px-4 py-2 text-left text-sm font-medium transition"
                    :class="bgBonus1Stat === stat
                      ? 'border-arcane bg-arcane/10 text-arcane-light'
                      : bgBonus2Stat === stat
                        ? 'border-stone/30 text-stone-light cursor-not-allowed opacity-40'
                        : 'border-stone text-parchment-dark hover:border-arcane/20'"
                    @click="bgBonus1Stat = stat"
                  >
                    <span class="font-bold">{{ ABILITY_INFO[stat as (typeof ABILITY_KEYS)[number]]?.fr ?? stat }}</span>
                    <span class="ml-2 text-xs text-stone-light">{{ finalScores[stat as (typeof ABILITY_KEYS)[number]] }} → {{ Math.min(20, (finalScores[stat as (typeof ABILITY_KEYS)[number]] as number) + 1) }}</span>
                  </button>
                </div>
              </div>
            </div>
          </template>

          <!-- Mode +1/+1/+1 : confirmation -->
          <template v-else-if="bgBonusMode === 'all_one'">
            <button class="mb-4 text-xs text-stone-light underline hover:text-parchment-dark" @click="bgBonusMode = null">
              ← Changer de mode
            </button>
            <div class="rounded border border-gold/30 bg-gold/5 p-4">
              <p class="mb-3 text-sm text-parchment-dark">Chaque caractéristique recevra <span class="font-bold text-gold">+1</span> :</p>
              <div class="flex flex-wrap gap-3">
                <div v-for="stat in bgAbilityStats" :key="stat" class="flex items-center gap-2 text-sm">
                  <span class="font-semibold text-parchment">{{ ABILITY_INFO[stat as (typeof ABILITY_KEYS)[number]]?.abbr ?? stat.toUpperCase() }}</span>
                  <span class="text-stone-light">{{ finalScores[stat as (typeof ABILITY_KEYS)[number]] }} →</span>
                  <span class="font-bold text-gold">{{ Math.min(20, (finalScores[stat as (typeof ABILITY_KEYS)[number]] as number) + 1) }}</span>
                </div>
              </div>
            </div>
          </template>
        </template>

        <!-- Étape 6 : Compétences -->
        <template v-if="step === 6">
          <h2 class="mb-1 text-2xl font-bold text-gold">Choisissez vos Compétences</h2>
          <p class="mb-1 text-sm text-parchment-dark">
            Sélectionnez
            <span class="font-bold text-parchment">{{ selectedClass?.num_skill_choices }}</span>
            compétence(s) parmi celles proposées par votre classe.
          </p>
          <p class="mb-5 text-xs text-stone-light">
            {{ selectedSkills.length }} / {{ selectedClass?.num_skill_choices }} sélectionnée(s)
          </p>

          <div class="grid grid-cols-2 gap-2 sm:grid-cols-3">
            <button
              v-for="skill in selectedClass?.skill_choices"
              :key="skill"
              :disabled="
                !selectedSkills.includes(skill) &&
                selectedSkills.length >= (selectedClass?.num_skill_choices ?? 0)
              "
              class="rounded border px-3 py-2 text-sm font-medium transition"
              :class="
                selectedSkills.includes(skill)
                  ? 'border-gold bg-gold/10 text-gold'
                  : 'border-stone text-parchment-dark hover:border-gold/40 disabled:cursor-not-allowed disabled:opacity-40'
              "
              @click="toggleSkill(skill)"
            >
              {{ SKILL_FR[skill] ?? skill }}
            </button>
          </div>

          <!-- Compétences venant du background et de l'espèce -->
          <div class="mt-5 space-y-2 text-xs text-stone-light">
            <div v-if="(selectedBackground?.skills.length ?? 0) > 0">
              <span class="text-parchment-dark">Historique ({{ selectedBackground?.name_fr }}) : </span>
              <span v-for="s in selectedBackground?.skills" :key="s" class="ml-1 text-forest-light">
                {{ SKILL_FR[s] ?? s }}
              </span>
            </div>
            <div v-if="(selectedSpecies?.skill_proficiencies.length ?? 0) > 0">
              <span class="text-parchment-dark">Espèce ({{ selectedSpecies?.name_fr }}) : </span>
              <span
                v-for="s in selectedSpecies?.skill_proficiencies"
                :key="s"
                class="ml-1 text-forest-light"
              >
                {{ SKILL_FR[s] ?? s }}
              </span>
            </div>
          </div>
        </template>

        <!-- Étape 7 : Équipement -->
        <template v-if="step === 7">
          <h2 class="mb-1 text-2xl font-bold text-gold">Équipement de Départ</h2>
          <p class="mb-5 text-sm text-parchment-dark">
            Choisissez votre équipement initial parmi les options proposées par votre classe.
          </p>

          <!-- Choix d'équipement -->
          <div v-if="equipmentChoiceGroups.length > 0" class="space-y-5">
            <div v-for="(group, i) in equipmentChoiceGroups" :key="i">
              <p class="mb-2 text-sm font-medium text-parchment-dark">Choix {{ i + 1 }}</p>
              <div class="flex flex-col gap-2 sm:flex-row">
                <button
                  v-for="(option, optIdx) in group.choice"
                  :key="optIdx"
                  class="flex-1 rounded border px-4 py-3 text-left text-sm transition"
                  :class="
                    equipmentChoices[i] === optIdx
                      ? 'border-gold bg-gold/10 text-parchment'
                      : 'border-stone text-parchment-dark hover:border-gold/40'
                  "
                  @click="equipmentChoices[i] = optIdx"
                >
                  <span v-if="equipmentChoices[i] === optIdx" class="mr-2 text-gold">✓</span>
                  {{ formatOption(option) }}
                </button>
              </div>
            </div>
          </div>

          <div v-else class="text-parchment-dark">
            Aucun choix d'équipement pour cette classe.
          </div>

          <!-- Équipement fixe -->
          <div v-if="equipmentFixed.length > 0" class="mt-6">
            <p class="mb-2 text-sm font-medium text-parchment-dark">Équipement fixe (inclus automatiquement)</p>
            <div class="flex flex-wrap gap-2">
              <span
                v-for="item in equipmentFixed"
                :key="item"
                class="rounded border border-stone/50 bg-ink px-2.5 py-1 text-xs text-parchment-dark"
              >
                {{ formatOption([item]) }}
              </span>
            </div>
          </div>
        </template>

        <!-- Étape 8 : Sorts -->
        <template v-if="step === 8">
          <h2 class="mb-1 text-2xl font-bold text-gold">Choisissez vos Sorts</h2>

          <template v-if="!isCaster">
            <p class="mt-4 text-parchment-dark">Votre classe n'utilise pas la magie. Passez à l'étape suivante.</p>
          </template>

          <template v-else>
            <div v-if="spellsLoading" class="py-10 text-center text-parchment-dark">
              Chargement des sorts…
            </div>
            <template v-else>

              <!-- Tours de magie -->
              <section v-if="numCantrips > 0" class="mb-6">
                <h3 class="mb-1 font-display font-bold text-parchment">
                  Tours de magie
                  <span class="ml-2 text-sm font-normal text-stone-light">
                    {{ selectedCantrips.length }} / {{ numCantrips }}
                  </span>
                </h3>
                <p class="mb-3 text-xs text-parchment-dark">Lancés à volonté, sans emplacement de sort.</p>
                <div class="grid grid-cols-2 gap-2 sm:grid-cols-3">
                  <button
                    v-for="spell in availableCantrips"
                    :key="spell.id"
                    :disabled="!selectedCantrips.includes(spell.id) && selectedCantrips.length >= numCantrips"
                    class="rounded border px-3 py-2 text-left text-sm transition"
                    :class="selectedCantrips.includes(spell.id)
                      ? 'border-arcane bg-arcane/10 text-arcane-light'
                      : 'border-stone text-parchment-dark hover:border-arcane/40 disabled:cursor-not-allowed disabled:opacity-40'"
                    @click="toggleCantrip(spell.id)"
                  >
                    <div class="font-medium">{{ spell.name_fr }}</div>
                    <div class="text-xs text-stone-light capitalize">{{ spell.school }}</div>
                  </button>
                </div>
              </section>

              <!-- Sorts de niveau 1 -->
              <section v-if="numSpells > 0">
                <h3 class="mb-1 font-display font-bold text-parchment">
                  Sorts de niveau 1
                  <span class="ml-2 text-sm font-normal text-stone-light">
                    {{ selectedSpells.length }} / {{ numSpells }}
                  </span>
                </h3>
                <p class="mb-3 text-xs text-parchment-dark">
                  {{ selectedClassId === 'wizard' ? 'Inscrits dans votre grimoire.' : 'Sorts que vous connaissez.' }}
                </p>
                <div class="grid grid-cols-2 gap-2 sm:grid-cols-3">
                  <button
                    v-for="spell in availableSpells"
                    :key="spell.id"
                    :disabled="!selectedSpells.includes(spell.id) && selectedSpells.length >= numSpells"
                    class="rounded border px-3 py-2 text-left text-sm transition"
                    :class="selectedSpells.includes(spell.id)
                      ? 'border-gold bg-gold/10 text-parchment'
                      : 'border-stone text-parchment-dark hover:border-gold/40 disabled:cursor-not-allowed disabled:opacity-40'"
                    @click="toggleSpell(spell.id)"
                  >
                    <div class="font-medium">{{ spell.name_fr }}</div>
                    <div class="text-xs text-stone-light capitalize">
                      {{ spell.school }}<span v-if="spell.concentration"> · Concentration</span>
                    </div>
                  </button>
                </div>
              </section>

              <div v-if="numCantrips === 0 && numSpells === 0" class="mt-4 text-parchment-dark">
                Votre classe prépare ses sorts depuis la liste complète — aucun choix requis maintenant.
              </div>

            </template>
          </template>
        </template>

        <!-- Étape 9 : Nom + Résumé -->
        <template v-if="step === 9">
          <h2 class="mb-1 text-2xl font-bold text-gold">Nommez votre Personnage</h2>
          <p class="mb-5 text-sm text-parchment-dark">Dernière étape avant de partir à l'aventure !</p>

          <!-- Saisie du nom -->
          <input
            v-model="characterName"
            type="text"
            placeholder="Entrez un nom..."
            maxlength="100"
            class="mb-4 w-full rounded border border-stone bg-ink px-4 py-3 font-display text-xl text-parchment outline-none transition focus:border-gold"
          />

          <!-- Compagnon IA -->
          <label class="mb-8 flex cursor-pointer items-center gap-3 rounded border border-stone bg-ink px-4 py-3">
            <input v-model="isAi" type="checkbox" class="h-4 w-4 accent-arcane" />
            <span class="text-parchment">Personnage géré par l'IA</span>
            <span class="ml-auto text-xs text-parchment-dark">
              {{ isAi ? 'L\'IA jouera ce personnage automatiquement' : 'Joueur humain' }}
            </span>
          </label>

          <!-- Résumé -->
          <h3 class="mb-3 font-display text-lg font-semibold text-parchment">Récapitulatif</h3>
          <div class="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <div class="rounded border border-stone bg-ink p-3">
              <div class="text-xs text-stone-light">Espèce</div>
              <div class="font-display font-bold text-parchment">{{ selectedSpecies?.name_fr }}</div>
            </div>
            <div class="rounded border border-stone bg-ink p-3">
              <div class="text-xs text-stone-light">Classe</div>
              <div class="font-display font-bold text-parchment">{{ selectedClass?.name_fr }}</div>
            </div>
            <div class="rounded border border-stone bg-ink p-3">
              <div class="text-xs text-stone-light">Historique</div>
              <div class="font-display font-bold text-parchment">{{ selectedBackground?.name_fr }}</div>
            </div>
            <div class="rounded border border-blood/40 bg-blood/10 p-3">
              <div class="text-xs text-stone-light">Points de Vie</div>
              <div class="font-display text-xl font-bold text-blood-light">{{ hpMax }}</div>
            </div>
            <div class="col-span-2 rounded border border-stone bg-ink p-3 sm:col-span-2">
              <div class="mb-1 text-xs text-stone-light">Caractéristiques</div>
              <div class="flex flex-wrap gap-2">
                <span v-for="key in ABILITY_KEYS" :key="key" class="text-sm">
                  <span class="text-stone-light">{{ ABILITY_INFO[key].abbr }}</span>
                  <span class="ml-1 font-bold text-parchment">{{ finalScores[key] }}</span>
                  <span class="ml-0.5 text-xs text-parchment-dark">({{ modStr(finalScores[key] as number) }})</span>
                </span>
              </div>
            </div>
          </div>

          <!-- Compétences -->
          <div class="mt-3 rounded border border-stone bg-ink p-3">
            <div class="mb-1 text-xs text-stone-light">Compétences maîtrisées</div>
            <div class="flex flex-wrap gap-1.5">
              <span
                v-for="skill in [
                  ...new Set([
                    ...selectedSkills,
                    ...(selectedBackground?.skills ?? []),
                    ...(selectedSpecies?.skill_proficiencies ?? []),
                  ]),
                ]"
                :key="skill"
                class="rounded bg-forest/20 px-2 py-0.5 text-xs text-forest-light"
              >
                {{ SKILL_FR[skill] ?? skill }}
              </span>
            </div>
          </div>

          <!-- Sorts connus -->
          <div v-if="isCaster && (selectedCantrips.length > 0 || selectedSpells.length > 0)" class="mt-3 rounded border border-arcane/30 bg-arcane/5 p-3">
            <div class="mb-1 text-xs text-stone-light">Sorts</div>
            <div class="flex flex-wrap gap-1.5">
              <span
                v-for="id in selectedCantrips"
                :key="id"
                class="rounded bg-arcane/20 px-2 py-0.5 text-xs text-arcane-light"
              >
                {{ availableCantrips.find(s => s.id === id)?.name_fr ?? id }}
              </span>
              <span
                v-for="id in selectedSpells"
                :key="id"
                class="rounded bg-gold/15 px-2 py-0.5 text-xs text-gold"
              >
                {{ availableSpells.find(s => s.id === id)?.name_fr ?? id }}
              </span>
            </div>
          </div>

          <!-- Erreur de soumission -->
          <div
            v-if="submitError"
            class="mt-4 rounded border border-blood bg-blood/10 px-4 py-3 text-sm text-blood-light"
          >
            {{ submitError }}
          </div>
        </template>

      </div>
      <!-- fin step content -->

      <!-- Navigation -->
      <div class="mt-6 flex items-center justify-between">
        <button
          v-if="step > 1"
          class="rounded border border-stone px-5 py-2 text-parchment-dark transition hover:border-gold hover:text-parchment"
          @click="prevStep"
        >
          ← Retour
        </button>
        <div v-else />

        <button
          v-if="step < TOTAL_STEPS"
          :disabled="!canProceed"
          class="rounded bg-blood px-6 py-2 font-display font-semibold text-parchment transition hover:bg-blood-light disabled:cursor-not-allowed disabled:opacity-40"
          @click="nextStep"
        >
          Suivant →
        </button>

        <button
          v-else
          :disabled="!canProceed || loading"
          class="rounded bg-gold px-8 py-2 font-display font-bold text-ink transition hover:bg-gold-light disabled:cursor-not-allowed disabled:opacity-40"
          @click="handleCreate"
        >
          {{ loading ? 'Création...' : '⚔ Commencer l\'Aventure' }}
        </button>
      </div>

    </template>
  </div>
</template>
