<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { srdApi, characterApi } from '../services/api'
import type { SrdSpecies, SrdClass, SrdEquipmentEntry } from '../types'

// ─── Constants ────────────────────────────────────────────────────────────────

const TOTAL_STEPS = 7

const STANDARD_ARRAY = [15, 14, 13, 12, 10, 8]

const ABILITY_KEYS = ['str', 'dex', 'con', 'int', 'wis', 'cha'] as const

const ABILITY_INFO: Record<(typeof ABILITY_KEYS)[number], { fr: string; abbr: string }> = {
  str: { fr: 'Force', abbr: 'FOR' },
  dex: { fr: 'Dextérité', abbr: 'DEX' },
  con: { fr: 'Constitution', abbr: 'CON' },
  int: { fr: 'Intelligence', abbr: 'INT' },
  wis: { fr: 'Sagesse', abbr: 'SAG' },
  cha: { fr: 'Charisme', abbr: 'CHA' },
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
  'Background',
  'Caractéristiques',
  'Compétences',
  'Équipement',
  'Nom',
]

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

// Step 4: Répartition des caractéristiques (tableau standard)
const assignments = ref<Record<string, number | null>>({
  str: null,
  dex: null,
  con: null,
  int: null,
  wis: null,
  cha: null,
})

// Step 5: Compétences
const selectedSkills = ref<string[]>([])

// Step 6: Équipement (choiceGroupIndex -> optionIndex)
const equipmentChoices = ref<Record<number, number>>({})

// Step 7: Nom
const characterName = ref('')

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

// Options disponibles pour une caractéristique donnée
function optionsForStat(key: string): number[] {
  const current = assignments.value[key]
  return STANDARD_ARRAY.filter((v) => v === current || !usedArrayValues.value.includes(v))
}

// Scores finaux (base + bonus d'espèce)
const finalScores = computed(() => {
  const bonuses = selectedSpecies.value?.ability_bonuses ?? {}
  return Object.fromEntries(
    ABILITY_KEYS.map((key) => [
      key,
      (assignments.value[key] ?? 10) + (bonuses[key] ?? 0),
    ]),
  )
})

const conMod = computed(() => Math.floor(((finalScores.value.con as number) - 10) / 2))
const hpMax = computed(() => (selectedClass.value?.hit_die ?? 8) + conMod.value)

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
    .map((i) => i.replace(/_/g, ' '))
    .join(' + ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

function assignStat(key: string, event: Event) {
  const val = (event.target as HTMLSelectElement).value
  assignments.value[key] = val === '' ? null : parseInt(val)
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
      return (Object.values(assignments.value) as (number | null)[]).every((v) => v !== null)
    case 5: {
      const numRequired = selectedClass.value?.num_skill_choices ?? 0
      return selectedSkills.value.length === numRequired
    }
    case 6:
      return equipmentChoiceGroups.value.every((_, i) => equipmentChoices.value[i] !== undefined)
    case 7:
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
      equipment.push({ id: item, name: formatOption([item]), quantity: 1 }),
    )
  })
  equipmentFixed.value.forEach((item) =>
    equipment.push({ id: item, name: formatOption([item]), quantity: 1 }),
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
      is_ai: false,
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
      session_id: sessionId,
    })
    router.push({ name: 'game-session', params: { id: sessionId } })
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
                  Vit. {{ species.speed }} ft
                </span>
                <span v-if="species.darkvision_ft > 0" class="rounded bg-arcane/20 px-1.5 py-0.5 text-xs text-arcane-light">
                  Vision {{ species.darkvision_ft }} ft
                </span>
              </div>
              <div class="mt-2 flex flex-wrap gap-1">
                <span
                  v-for="(bonus, stat) in species.ability_bonuses"
                  :key="stat"
                  class="rounded bg-gold/15 px-1.5 py-0.5 text-xs font-medium text-gold"
                >
                  {{ (ABILITY_INFO as Record<string, { fr: string; abbr: string } | undefined>)[stat]?.abbr ?? stat.toUpperCase() }} +{{ bonus }}
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

        <!-- Étape 3 : Background -->
        <template v-if="step === 3">
          <h2 class="mb-1 text-2xl font-bold text-gold">Choisissez votre Background</h2>
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
          <p class="mb-2 text-sm text-parchment-dark">
            Tableau standard — assignez chaque valeur à une caractéristique.
          </p>
          <!-- Valeurs disponibles -->
          <div class="mb-5 flex flex-wrap gap-2">
            <span
              v-for="v in STANDARD_ARRAY"
              :key="v"
              :class="[
                'rounded border px-3 py-1 text-sm font-bold transition',
                usedArrayValues.includes(v)
                  ? 'border-stone/30 text-stone-light line-through'
                  : 'border-gold text-gold',
              ]"
            >
              {{ v }}
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
              <select
                :value="assignments[key] ?? ''"
                class="w-full rounded border border-stone bg-ink-light px-2 py-1.5 text-parchment outline-none transition focus:border-gold"
                @change="assignStat(key, $event)"
              >
                <option value="">— Choisir —</option>
                <option
                  v-for="v in optionsForStat(key)"
                  :key="v"
                  :value="v"
                >
                  {{ v }}
                </option>
              </select>

              <div v-if="assignments[key] !== null" class="mt-2 flex items-baseline gap-2">
                <span class="text-2xl font-bold text-gold">{{ finalScores[key] }}</span>
                <span class="text-sm text-parchment-dark">{{ modStr(finalScores[key] as number) }}</span>
                <span
                  v-if="(selectedSpecies?.ability_bonuses[key] ?? 0) > 0"
                  class="text-xs text-arcane-light"
                >
                  (+{{ selectedSpecies?.ability_bonuses[key] }} espèce)
                </span>
              </div>
              <div v-else class="mt-2 text-lg text-stone-light">—</div>
            </div>
          </div>

          <!-- Aperçu HP -->
          <div v-if="canProceed" class="mt-4 rounded border border-blood/40 bg-blood/10 px-4 py-2 text-sm">
            <span class="text-parchment-dark">Points de vie au niveau 1 : </span>
            <span class="font-bold text-blood-light">{{ hpMax }} PV</span>
            <span class="text-stone-light"> (d{{ selectedClass?.hit_die }} max + CON {{ modStr(finalScores.con as number) }})</span>
          </div>
        </template>

        <!-- Étape 5 : Compétences -->
        <template v-if="step === 5">
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
              <span class="text-parchment-dark">Background ({{ selectedBackground?.name_fr }}) : </span>
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

        <!-- Étape 6 : Équipement -->
        <template v-if="step === 6">
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

        <!-- Étape 7 : Nom + Résumé -->
        <template v-if="step === 7">
          <h2 class="mb-1 text-2xl font-bold text-gold">Nommez votre Personnage</h2>
          <p class="mb-5 text-sm text-parchment-dark">Dernière étape avant de partir à l'aventure !</p>

          <!-- Saisie du nom -->
          <input
            v-model="characterName"
            type="text"
            placeholder="Entrez un nom..."
            maxlength="100"
            class="mb-8 w-full rounded border border-stone bg-ink px-4 py-3 font-display text-xl text-parchment outline-none transition focus:border-gold"
          />

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
              <div class="text-xs text-stone-light">Background</div>
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
