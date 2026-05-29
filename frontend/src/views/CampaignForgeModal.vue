<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useCampaignStore } from '../stores/campaign'
import type {
  CampaignForgeJobResponse,
  CampaignGmDossier,
  CampaignImportSourceBody,
  CampaignPlayerContract,
} from '../types'

const emit = defineEmits<{
  close: []
  'forge-completed': [payload: { campaignId: string; newSessionId: string }]
}>()

const campaignStore = useCampaignStore()

type ForgeMode = 'scratch' | 'import'
type ImportKind = 'url' | 'text' | 'file_text'

const TONES = ['Dark fantasy', 'Mystère', 'Politique', 'Exploration', 'Combat tactique', 'Romance', 'Cosmique']
const OPTIONS_AMBIANCE = [
  'High fantasy (Magie & Héroïsme)',
  'Dark fantasy (Survie & Corruption)',
  'Low fantasy (Magie rare & Réalisme)',
  'Sword & Sorcery (Magie occulte & Cités antiques)',
  'Dungeon crawler (Ruines & Souterrains)',
  'Intrigue politique (Conflits de cours & Châteaux)',
  'Mythologie antique (Dieux actifs & Héros légendaires)',
]
const OPTIONS_BIOME = ['Marais / Marécages', 'Ruines oubliées', 'Souterrains / Grottes', 'Forêt dense / Jungle', 'Désert aride', 'Plaines verdoyantes', 'Canyons / Montagnes', 'Archipel / Îles tropicales', 'Ville côtière']
const OPTIONS_CLIMAT = ['Brumeux / Humide', 'Glacial / Neigeux', 'Caniculaire / Aride', 'Tempétueux / Orageux', 'Pluvieux / Crachin', 'Ensoleillé / Printanier', 'Nocturne éternel']
const OPTIONS_TON = ['Tragique', 'Épique / Héroïque', 'Mystérieux / Enquête', 'Survie / Cruel', 'Comique / Léger', 'Sombre / Mélancolique', 'Horrifique / Angoissant']

const IMPORT_KINDS: Array<{ id: ImportKind; label: string }> = [
  { id: 'text', label: 'Texte' },
  { id: 'url', label: 'URL' },
  { id: 'file_text', label: 'Fichier' },
]

const mode = ref<ForgeMode>('scratch')
const forgeStep = ref(1)

const commonBrief = reactive({
  name: '',
  tones: [] as string[],
  duration: '3-5',
  startingLevel: 1,
  scope: 'mini-campagne',
  combat: 'hybride léger',
})
const scratchInputs = reactive({
  pitch: '',
  options5Acts: { ambiance: '', biome: '', climat: '', ton: '', info: '' },
})
const importInputs = reactive({
  kind: 'text' as ImportKind,
  title: '',
  url: '',
  text: '',
  filename: '',
})

const forgeCampaignId = ref<string | null>(null)
const draftContract = ref<CampaignPlayerContract | null>(null)
const forgeJob = ref<CampaignForgeJobResponse | null>(null)
const sourceCount = ref(0)
const contractValidated = ref(false)
const isForging = ref(false)
const isImporting = ref(false)
const isValidating = ref(false)
const isFetchingDossier = ref(false)
const isClosing = ref(false)
const modalError = ref<string | null>(null)
const validationTab = ref<'contract' | 'secrets'>('contract')

const narrativeStructure = computed(() => (mode.value === 'scratch' ? 'epic_5_acts' : 'adaptive'))
const totalSteps = computed(() => (mode.value === 'scratch' ? 6 : 5))

const durationDisplay = computed(() => {
  const trimmed = commonBrief.duration.trim()
  if (!trimmed) return ''
  if (/session/i.test(trimmed)) return trimmed
  return `${trimmed} sessions`
})

const isForgeStep = computed(
  () =>
    (mode.value === 'scratch' && forgeStep.value === 5) ||
    (mode.value === 'import' && forgeStep.value === 4),
)
const isValidationStep = computed(
  () =>
    (mode.value === 'scratch' && forgeStep.value === 6) ||
    (mode.value === 'import' && forgeStep.value === 5),
)

const gmDossier = computed<CampaignGmDossier | null>(() => {
  if (!forgeCampaignId.value) return null
  return campaignStore.gmDossiers[forgeCampaignId.value]?.gm_dossier ?? null
})

const forgeProgressPercent = computed(() => {
  if (!forgeJob.value) return 0
  const total = Math.max(forgeJob.value.total_steps || 1, 1)
  const current = Math.min(total, Math.max(forgeJob.value.current_step || 0, 0))
  return Math.round((current / total) * 100)
})

const forgeProgressLabel = computed(() => {
  if (!forgeJob.value) return ''
  const total = Math.max(forgeJob.value.total_steps || 1, 1)
  const current = Math.min(total, Math.max(forgeJob.value.current_step || 0, 0))
  return `Global ${current} / ${total}`
})

const forgeRetryEvents = computed(() =>
  (forgeJob.value?.events ?? []).filter((event) => event.type.includes('retry')).slice(-4),
)

function selectMode(next: ForgeMode) {
  mode.value = next
}

function toggleTone(tone: string) {
  const idx = commonBrief.tones.indexOf(tone)
  if (idx >= 0) {
    commonBrief.tones.splice(idx, 1)
  } else if (commonBrief.tones.length < 3) {
    commonBrief.tones.push(tone)
  }
}

function rollRandomOption(field: 'ambiance' | 'biome' | 'climat' | 'ton') {
  const lists: Record<typeof field, string[]> = {
    ambiance: OPTIONS_AMBIANCE,
    biome: OPTIONS_BIOME,
    climat: OPTIONS_CLIMAT,
    ton: OPTIONS_TON,
  }
  const list = lists[field]
  if (!list.length) return
  const pick = list[Math.floor(Math.random() * list.length)]
  if (pick) scratchInputs.options5Acts[field] = pick
}

function rollAllRandomOptions() {
  rollRandomOption('ambiance')
  rollRandomOption('biome')
  rollRandomOption('climat')
  rollRandomOption('ton')
}

function validateStep(): string | null {
  if (forgeStep.value === 1) return null
  if (mode.value === 'scratch') {
    if (forgeStep.value === 2) {
      if (!commonBrief.name.trim()) return 'Le nom de la campagne est requis.'
    }
    if (forgeStep.value === 4 && commonBrief.startingLevel < 1) {
      return 'Le niveau initial doit être supérieur ou égal à 1.'
    }
  } else {
    if (forgeStep.value === 2 && sourceCount.value === 0) {
      return 'Importez au moins une source pour continuer.'
    }
    if (forgeStep.value === 3 && commonBrief.startingLevel < 1) {
      return 'Le niveau initial doit être supérieur ou égal à 1.'
    }
  }
  return null
}

function nextStep() {
  const err = validateStep()
  if (err) {
    modalError.value = err
    return
  }
  modalError.value = null
  forgeStep.value = Math.min(totalSteps.value, forgeStep.value + 1)
}

function previousStep() {
  if (isForging.value || isValidating.value) return
  modalError.value = null
  forgeStep.value = Math.max(1, forgeStep.value - 1)
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

async function ensureForgeCampaign(): Promise<string | null> {
  if (forgeCampaignId.value) return forgeCampaignId.value
  const fallbackName = mode.value === 'import' ? 'Chronique Importée' : 'Chronique sans nom'
  const fallbackDesc = mode.value === 'import' ? '' : 'Aventure de campagne.'
  const pitchForDesc = mode.value === 'scratch' ? scratchInputs.pitch.trim() : ''
  const created = await campaignStore.createCampaign({
    name: commonBrief.name.trim() || fallbackName,
    description: pitchForDesc || fallbackDesc,
  })
  if (!created) {
    modalError.value = 'Impossible de créer la campagne.'
    return null
  }
  forgeCampaignId.value = created.id
  return created.id
}

async function importSource() {
  modalError.value = null
  const campaignId = await ensureForgeCampaign()
  if (!campaignId) return
  const body: CampaignImportSourceBody = {
    kind: importInputs.kind,
    title: importInputs.title.trim() || undefined,
  }
  if (importInputs.kind === 'url') {
    body.url = importInputs.url.trim()
  } else {
    body.content = importInputs.text.trim()
    body.filename = importInputs.filename || undefined
  }
  if ((body.kind === 'url' && !body.url) || (body.kind !== 'url' && !body.content)) {
    modalError.value = 'La source est vide.'
    return
  }
  isImporting.value = true
  try {
    const result = await campaignStore.importSource(campaignId, body)
    if (!result) {
      modalError.value = campaignStore.error ?? "L'import a échoué."
      return
    }
    sourceCount.value = result.source_count
    importInputs.title = ''
    importInputs.url = ''
    importInputs.text = ''
    importInputs.filename = ''
  } finally {
    isImporting.value = false
  }
}

async function handleFileImport(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  importInputs.kind = 'file_text'
  importInputs.filename = file.name
  importInputs.title = importInputs.title || file.name
  importInputs.text = await file.text()
}

async function runForge() {
  if (isForging.value) return
  modalError.value = null
  const campaignId = await ensureForgeCampaign()
  if (!campaignId) return
  isForging.value = true
  forgeJob.value = null
  try {
    const briefPayload: Record<string, unknown> = {
      title: commonBrief.name,
      tones: commonBrief.tones,
      duration: durationDisplay.value,
    }
    if (mode.value === 'scratch' && scratchInputs.pitch.trim()) {
      briefPayload.pitch = scratchInputs.pitch
    }
    const optionsPayload: Record<string, unknown> = {
      scope: commonBrief.scope,
      starting_level: commonBrief.startingLevel,
      combat: commonBrief.combat,
      narrative_structure: narrativeStructure.value,
    }
    if (mode.value === 'scratch') {
      optionsPayload.options_5_acts = { ...scratchInputs.options5Acts }
    }
    const initial = await campaignStore.startForgeDraftJob(campaignId, briefPayload, optionsPayload)
    if (!initial) {
      modalError.value = campaignStore.error ?? 'La forge a échoué.'
      return
    }
    forgeJob.value = initial
    let current = initial
    while (current.status === 'queued' || current.status === 'running') {
      await delay(1000)
      const next = await campaignStore.getForgeDraftJob(campaignId, current.job_id)
      if (!next) {
        modalError.value = campaignStore.error ?? 'Suivi de forge impossible.'
        return
      }
      current = next
      forgeJob.value = next
    }
    if (current.status !== 'completed' || !current.player_contract) {
      modalError.value = current.error || 'La forge a échoué.'
      return
    }
    draftContract.value = cloneContract(current.player_contract)
    isFetchingDossier.value = true
    try {
      await campaignStore.fetchGmDossier(campaignId)
    } finally {
      isFetchingDossier.value = false
    }
    validationTab.value = 'contract'
    forgeStep.value = mode.value === 'scratch' ? 6 : 5
  } finally {
    isForging.value = false
  }
}

async function validateAndStart() {
  if (!forgeCampaignId.value || !draftContract.value) return
  isValidating.value = true
  modalError.value = null
  try {
    const validated = await campaignStore.validateContract(forgeCampaignId.value, draftContract.value)
    if (!validated) {
      modalError.value = campaignStore.error ?? 'Validation impossible.'
      return
    }
    contractValidated.value = true
    const sessionName =
      draftContract.value.title?.trim()
      || draftContract.value.visible_chapters?.[0]?.title?.trim()
      || 'Première session'
    const result = await campaignStore.advance(forgeCampaignId.value, sessionName)
    if (!result) {
      modalError.value = campaignStore.error ?? 'Impossible de créer la première session.'
      return
    }
    emit('forge-completed', {
      campaignId: forgeCampaignId.value,
      newSessionId: result.new_session_id,
    })
  } finally {
    isValidating.value = false
  }
}

async function cancelForge() {
  if (isForging.value || isClosing.value) return
  isClosing.value = true
  try {
    if (forgeCampaignId.value && !contractValidated.value) {
      await campaignStore.deleteCampaign(forgeCampaignId.value)
    }
    emit('close')
  } finally {
    isClosing.value = false
  }
}

function updateObjectivesEvent(event: Event) {
  if (!draftContract.value) return
  draftContract.value.known_objectives = (event.target as HTMLTextAreaElement).value
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean)
}

function updateToneEvent(event: Event) {
  if (!draftContract.value) return
  draftContract.value.tones = (event.target as HTMLInputElement).value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

function cloneContract(contract: CampaignPlayerContract): CampaignPlayerContract {
  return JSON.parse(JSON.stringify(contract)) as CampaignPlayerContract
}

function asList(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

function handleBackdrop() {
  if (isForging.value || isValidating.value) return
  void cancelForge()
}

function handleFooterBack() {
  if (forgeStep.value === 1) {
    void cancelForge()
  } else {
    previousStep()
  }
}
</script>

<template>
  <Teleport to="body">
    <div
      class="rpg-modal-backdrop fixed inset-0 z-50 flex items-center justify-center p-4"
      @click.self="handleBackdrop"
    >
      <div class="rpg-dialog-panel rpg-tone-gold relative max-h-[90vh] w-full max-w-[640px] overflow-y-auto overflow-x-hidden rounded-[14px] border p-7">
        <div class="rpg-campaign-modal-glow pointer-events-none absolute -right-12 -top-20 h-60 w-60 rounded-full" />
        <div class="relative">
          <div class="rpg-eyebrow"><span class="rpg-sparkle">✦</span>Forger une nouvelle chronique</div>
          <h2 class="mt-1 font-display text-[28px] font-bold leading-tight">Nouvelle campagne</h2>

          <div class="mt-5 flex gap-2">
            <span
              v-for="step in totalSteps"
              :key="step"
              class="h-1.5 flex-1 rounded-full"
              :class="step <= forgeStep ? 'bg-[linear-gradient(90deg,var(--color-ember),var(--color-gold))]' : 'bg-surface-raised'"
            />
          </div>

          <p v-if="modalError" class="mt-4 rounded border border-blood/30 bg-blood/10 px-3 py-2 text-sm text-blood-light">
            {{ modalError }}
          </p>

          <!-- Step 1 — Choix du mode -->
          <div v-if="forgeStep === 1" class="mt-6 space-y-4">
            <div class="rpg-eyebrow"><span class="rpg-sparkle">✦</span>Choisissez votre approche</div>
            <p class="font-serif text-sm italic text-parchment-dark">
              Deux voies pour faire naître votre chronique : laisser le MJ IA bâtir une intrigue en 5 actes, ou lui fournir vos propres sources de lore à adapter.
            </p>
            <div class="grid gap-3 md:grid-cols-2">
              <button
                class="flex flex-col gap-2 rounded-lg border p-4 text-left transition"
                :class="mode === 'scratch' ? 'border-gold/50 bg-gold/10 text-gold' : 'border-border text-text-muted hover:border-border-strong'"
                type="button"
                @click="selectMode('scratch')"
              >
                <div class="font-display text-sm font-bold uppercase tracking-wider">⚔ Création Assistée</div>
                <div class="font-serif text-[11px] italic leading-snug">
                  Feuille blanche guidée par l'IA. Le MJ structure une épopée stricte en 5 actes à partir de votre brief.
                </div>
              </button>
              <button
                class="flex flex-col gap-2 rounded-lg border p-4 text-left transition"
                :class="mode === 'import' ? 'border-gold/50 bg-gold/10 text-gold' : 'border-border text-text-muted hover:border-border-strong'"
                type="button"
                @click="selectMode('import')"
              >
                <div class="font-display text-sm font-bold uppercase tracking-wider">❦ Conversion de Lore</div>
                <div class="font-serif text-[11px] italic leading-snug">
                  Importez scénarios, bibles ou synopsis. Le MJ adapte la structure narrative au matériel fourni.
                </div>
              </button>
            </div>
          </div>

          <!-- Step 2 scratch — Brief -->
          <div v-else-if="mode === 'scratch' && forgeStep === 2" class="mt-6 space-y-5">
            <div class="rpg-eyebrow"><span class="rpg-sparkle">✦</span>Brief de chronique</div>
            <label class="block">
              <span class="mb-1.5 block font-display text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">Nom de la campagne *</span>
              <input v-model="commonBrief.name" class="rpg-input w-full text-base" placeholder="La Chute des Rois Anciens" />
            </label>
            <label class="block">
              <span class="mb-1.5 block font-display text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">Brief court — Pitch <span class="text-text-dim normal-case tracking-normal">(optionnel)</span></span>
              <textarea v-model="scratchInputs.pitch" class="rpg-input min-h-28 w-full resize-y" placeholder="Laissez vide pour une chronique tirée au sort par le MJ, ou esquissez votre vision…" />
            </label>
            <div>
              <div class="mb-2 font-display text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">Tonalités — max 3</div>
              <div class="flex flex-wrap gap-2">
                <button
                  v-for="tone in TONES"
                  :key="tone"
                  class="rounded-full border px-3 py-1.5 font-serif text-[11px] transition"
                  :class="commonBrief.tones.includes(tone)
                    ? 'border-arcane/50 bg-arcane/15 text-arcane'
                    : 'border-border bg-transparent text-text-muted hover:border-border-strong'"
                  type="button"
                  @click="toggleTone(tone)"
                >
                  {{ tone }}
                </button>
              </div>
            </div>
            <label class="block">
              <span class="mb-1.5 block font-display text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">Durée estimée <span class="text-text-dim normal-case tracking-normal">(en sessions)</span></span>
              <input v-model="commonBrief.duration" class="rpg-input w-full" placeholder="3-5" />
            </label>
          </div>

          <!-- Step 3 scratch — Cadre esthétique 5 Actes -->
          <div v-else-if="mode === 'scratch' && forgeStep === 3" class="mt-6 space-y-4">
            <div class="rpg-eyebrow"><span class="rpg-sparkle">✦</span>Cadre esthétique — 5 Actes</div>
            <div class="flex items-center justify-between">
              <div class="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">Options de départ</div>
              <button
                type="button"
                class="rounded-md border border-gold/30 bg-gold/5 px-2.5 py-1 font-display text-[9px] font-bold uppercase tracking-wider text-gold transition hover:bg-gold/10"
                @click="rollAllRandomOptions"
              >
                ⚂ Tirer tout au sort
              </button>
            </div>

            <div class="grid gap-3 md:grid-cols-2">
              <label class="block">
                <span class="mb-1 block font-display text-[9px] font-bold uppercase tracking-[0.14em] text-text-muted">Ambiance / Univers</span>
                <div class="flex gap-1.5">
                  <select v-model="scratchInputs.options5Acts.ambiance" class="rpg-input flex-1 text-xs min-w-0">
                    <option value="">— Choisir —</option>
                    <option v-for="opt in OPTIONS_AMBIANCE" :key="opt" :value="opt">{{ opt }}</option>
                  </select>
                  <button
                    type="button"
                    class="flex h-9 w-9 items-center justify-center rounded-md border border-border bg-black/25 text-base text-gold transition hover:border-gold"
                    title="Tirer au sort l'Ambiance"
                    @click="rollRandomOption('ambiance')"
                  >⚂</button>
                </div>
              </label>

              <label class="block">
                <span class="mb-1 block font-display text-[9px] font-bold uppercase tracking-[0.14em] text-text-muted">Biome</span>
                <div class="flex gap-1.5">
                  <select v-model="scratchInputs.options5Acts.biome" class="rpg-input flex-1 text-xs min-w-0">
                    <option value="">— Choisir —</option>
                    <option v-for="opt in OPTIONS_BIOME" :key="opt" :value="opt">{{ opt }}</option>
                  </select>
                  <button
                    type="button"
                    class="flex h-9 w-9 items-center justify-center rounded-md border border-border bg-black/25 text-base text-gold transition hover:border-gold"
                    title="Tirer au sort le Biome"
                    @click="rollRandomOption('biome')"
                  >⚂</button>
                </div>
              </label>

              <label class="block">
                <span class="mb-1 block font-display text-[9px] font-bold uppercase tracking-[0.14em] text-text-muted">Climat</span>
                <div class="flex gap-1.5">
                  <select v-model="scratchInputs.options5Acts.climat" class="rpg-input flex-1 text-xs min-w-0">
                    <option value="">— Choisir —</option>
                    <option v-for="opt in OPTIONS_CLIMAT" :key="opt" :value="opt">{{ opt }}</option>
                  </select>
                  <button
                    type="button"
                    class="flex h-9 w-9 items-center justify-center rounded-md border border-border bg-black/25 text-base text-gold transition hover:border-gold"
                    title="Tirer au sort le Climat"
                    @click="rollRandomOption('climat')"
                  >⚂</button>
                </div>
              </label>

              <label class="block">
                <span class="mb-1 block font-display text-[9px] font-bold uppercase tracking-[0.14em] text-text-muted">Ton</span>
                <div class="flex gap-1.5">
                  <select v-model="scratchInputs.options5Acts.ton" class="rpg-input flex-1 text-xs min-w-0">
                    <option value="">— Choisir —</option>
                    <option v-for="opt in OPTIONS_TON" :key="opt" :value="opt">{{ opt }}</option>
                  </select>
                  <button
                    type="button"
                    class="flex h-9 w-9 items-center justify-center rounded-md border border-border bg-black/25 text-base text-gold transition hover:border-gold"
                    title="Tirer au sort le Ton"
                    @click="rollRandomOption('ton')"
                  >⚂</button>
                </div>
              </label>
            </div>

            <label class="block">
              <span class="mb-1 block font-display text-[9px] font-bold uppercase tracking-[0.14em] text-text-muted">Inspirations / Notes libres</span>
              <textarea
                v-model="scratchInputs.options5Acts.info"
                class="rpg-input min-h-28 w-full resize-y text-xs"
                placeholder="Précisez des inspirations littéraires, musicales ou thématiques pour orienter l'écriture des 5 actes…"
              />
            </label>
          </div>

          <!-- Step 2 import — Sources de lore -->
          <div v-else-if="mode === 'import' && forgeStep === 2" class="mt-6 space-y-4">
            <div class="rpg-eyebrow"><span class="rpg-sparkle">✦</span>Sources de lore</div>
            <label class="block">
              <span class="mb-1.5 block font-display text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">Nom de la campagne (optionnel)</span>
              <input v-model="commonBrief.name" class="rpg-input w-full text-base" placeholder="Nom déduit de la source si laissé vide…" />
            </label>

            <div class="flex gap-2">
              <button
                v-for="kind in IMPORT_KINDS"
                :key="kind.id"
                class="rounded-md border px-3 py-1.5 text-xs font-semibold uppercase tracking-widest transition"
                :class="importInputs.kind === kind.id ? 'border-gold/40 bg-gold/10 text-gold' : 'border-border text-text-muted hover:border-border-strong'"
                type="button"
                @click="importInputs.kind = kind.id"
              >
                {{ kind.label }}
              </button>
            </div>

            <div class="space-y-3">
              <input v-model="importInputs.title" class="rpg-input w-full" placeholder="Titre de la source (ex. Chapitre 1, Lore général…)" />
              <input v-if="importInputs.kind === 'url'" v-model="importInputs.url" class="rpg-input w-full" placeholder="https://…" />
              <input
                v-if="importInputs.kind === 'file_text'"
                type="file"
                class="w-full rounded border border-border-strong bg-black/30 px-3 py-2 text-sm text-text-muted"
                accept=".txt,.md,.html,.htm"
                @change="handleFileImport"
              />
              <textarea
                v-if="importInputs.kind !== 'url'"
                v-model="importInputs.text"
                class="rpg-input min-h-40 w-full resize-y"
                placeholder="Collez votre scénario, notes, bestiaire ou synopsis ici…"
              />
              <div class="flex items-center justify-between">
                <span class="font-mono text-xs text-text-muted">
                  {{ sourceCount }} source{{ sourceCount > 1 ? 's' : '' }} privée{{ sourceCount > 1 ? 's' : '' }} chargée{{ sourceCount > 1 ? 's' : '' }}
                </span>
                <button class="rpg-btn-secondary" :disabled="isImporting" type="button" @click="importSource">
                  {{ isImporting ? 'Import…' : 'Importer cette source' }}
                </button>
              </div>
            </div>

            <div>
              <div class="mb-2 font-display text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">Tonalités (optionnel — max 3)</div>
              <div class="flex flex-wrap gap-2">
                <button
                  v-for="tone in TONES"
                  :key="tone"
                  class="rounded-full border px-3 py-1.5 font-serif text-[11px] transition"
                  :class="commonBrief.tones.includes(tone)
                    ? 'border-arcane/50 bg-arcane/15 text-arcane'
                    : 'border-border bg-transparent text-text-muted hover:border-border-strong'"
                  type="button"
                  @click="toggleTone(tone)"
                >
                  {{ tone }}
                </button>
              </div>
            </div>
          </div>

          <!-- Cadrage technique : step 4 (scratch) ou step 3 (import) -->
          <div
            v-else-if="(mode === 'scratch' && forgeStep === 4) || (mode === 'import' && forgeStep === 3)"
            class="mt-6 space-y-4"
          >
            <div class="rpg-eyebrow"><span class="rpg-sparkle">✦</span>Paramètres de jeu & Mécaniques</div>

            <div class="grid gap-4 md:grid-cols-2">
              <label v-if="mode === 'import'" class="block">
                <span class="mb-1.5 block font-display text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">Durée estimée <span class="text-text-dim normal-case tracking-normal">(en sessions)</span></span>
                <input v-model="commonBrief.duration" class="rpg-input w-full" placeholder="3-5" />
              </label>
              <label class="block">
                <span class="mb-1.5 block font-display text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">Niveau initial des PJ</span>
                <input v-model.number="commonBrief.startingLevel" min="1" max="20" type="number" class="rpg-input w-full" />
              </label>
              <label class="block">
                <span class="mb-1.5 block font-display text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">Format</span>
                <select v-model="commonBrief.scope" class="rpg-input w-full">
                  <option>one-shot</option>
                  <option>mini-campagne</option>
                  <option>campagne longue</option>
                </select>
              </label>
              <label class="block">
                <span class="mb-1.5 block font-display text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">Dominance de jeu</span>
                <select v-model="commonBrief.combat" class="rpg-input w-full">
                  <option>hybride léger</option>
                  <option>exploration sociale</option>
                  <option>combat tactique</option>
                </select>
              </label>
            </div>

            <div v-if="mode === 'import'" class="rounded-lg border border-gold/20 bg-gold/5 p-3 text-xs leading-relaxed text-text-muted">
              <span class="font-bold text-gold">◆ Conseil MJ :</span>
              Si vous importez un scénario ou module pré-écrit contenant des statistiques de combat,
              alignez le niveau initial sur les prérequis narratifs de votre document.
            </div>
          </div>

          <!-- Forge step (5 scratch / 4 import) -->
          <div v-else-if="isForgeStep" class="mt-6 space-y-4">
            <div class="rpg-eyebrow"><span class="rpg-sparkle">✦</span>Forge IA</div>
            <div class="rounded-lg border border-border bg-surface p-4">
              <div class="text-[9px] font-bold uppercase tracking-[0.22em] text-text-muted">Récapitulatif</div>
              <dl class="mt-3 grid gap-2 font-mono text-[11px] text-parchment-dark md:grid-cols-2">
                <div><dt class="inline text-text-muted">Mode :</dt> <dd class="inline">{{ mode === 'scratch' ? 'Création Assistée (5 Actes)' : 'Conversion de Lore (Adaptive)' }}</dd></div>
                <div><dt class="inline text-text-muted">Nom :</dt> <dd class="inline">{{ commonBrief.name.trim() || (mode === 'import' ? '— déduit des sources —' : '—') }}</dd></div>
                <div><dt class="inline text-text-muted">Niveau :</dt> <dd class="inline">{{ commonBrief.startingLevel }}</dd></div>
                <div><dt class="inline text-text-muted">Format :</dt> <dd class="inline">{{ commonBrief.scope }}</dd></div>
                <div><dt class="inline text-text-muted">Dominance :</dt> <dd class="inline">{{ commonBrief.combat }}</dd></div>
                <div v-if="mode === 'scratch'"><dt class="inline text-text-muted">Durée :</dt> <dd class="inline">{{ durationDisplay || '—' }}</dd></div>
                <div v-if="mode === 'import'"><dt class="inline text-text-muted">Sources :</dt> <dd class="inline">{{ sourceCount }}</dd></div>
                <div v-if="commonBrief.tones.length" class="md:col-span-2"><dt class="inline text-text-muted">Tonalités :</dt> <dd class="inline">{{ commonBrief.tones.join(', ') }}</dd></div>
              </dl>
            </div>

            <p class="font-serif text-sm italic text-parchment-dark">
              Le dossier privé sera structuré côté MJ, puis seul le contrat joueur vous sera présenté pour validation.
            </p>

            <div v-if="forgeJob" class="rounded-lg border border-border bg-black/25 p-3">
              <div class="flex items-center justify-between gap-3 font-mono text-[10px] uppercase tracking-wider text-text-muted">
                <span class="min-w-0 truncate">{{ forgeJob.message || 'Forge en cours…' }}</span>
                <span class="shrink-0 text-right text-gold">{{ forgeProgressLabel }}</span>
              </div>
              <div class="mt-2 h-1.5 overflow-hidden rounded-full bg-surface-raised">
                <div
                  class="h-full rounded-full bg-[linear-gradient(90deg,var(--color-ember),var(--color-gold))] transition-all"
                  :style="{ width: `${forgeProgressPercent}%` }"
                />
              </div>
              <div v-if="forgeRetryEvents.length" class="mt-3 space-y-1">
                <div
                  v-for="event in forgeRetryEvents"
                  :key="event.at + event.message"
                  class="font-mono text-[10px] text-gold"
                >
                  {{ event.message }}<span v-if="event.error" class="text-text-dim"> — {{ event.error }}</span>
                </div>
              </div>
              <div v-if="isFetchingDossier" class="mt-3 font-mono text-[10px] uppercase tracking-wider text-text-muted">
                Chargement du dossier MJ…
              </div>
            </div>
          </div>

          <!-- Validation step (6 scratch / 5 import) -->
          <div v-else-if="isValidationStep && draftContract" class="mt-6 space-y-4">
            <nav class="mb-4 flex border-b border-border">
              <button
                class="border-b-2 px-4 py-2 font-display text-[11px] font-bold uppercase tracking-[0.12em] transition"
                :class="validationTab === 'contract' ? 'border-ember text-parchment' : 'border-transparent text-text-muted hover:text-parchment'"
                type="button"
                @click="validationTab = 'contract'"
              >
                ✦ Contrat Joueur (Visible)
              </button>
              <button
                class="border-b-2 px-4 py-2 font-display text-[11px] font-bold uppercase tracking-[0.12em] transition"
                :class="validationTab === 'secrets' ? 'border-ember text-parchment' : 'border-transparent text-text-muted hover:text-parchment'"
                type="button"
                @click="validationTab = 'secrets'"
              >
                ❦ Secrets du MJ (Privé)
              </button>
            </nav>

            <div v-if="validationTab === 'contract'" class="space-y-4">
              <label class="block">
                <span class="mb-1.5 block font-display text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">Titre public</span>
                <input v-model="draftContract.title" class="rpg-input w-full text-base" />
              </label>
              <label class="block">
                <span class="mb-1.5 block font-display text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">Pitch public</span>
                <textarea v-model="draftContract.pitch_public" class="rpg-input min-h-24 w-full resize-y" />
              </label>
              <div class="grid gap-4 md:grid-cols-2">
                <label class="block">
                  <span class="mb-1.5 block font-display text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">Durée</span>
                  <input v-model="draftContract.duration" class="rpg-input w-full" />
                </label>
                <label class="block">
                  <span class="mb-1.5 block font-display text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">Tonalités</span>
                  <input :value="draftContract.tones.join(', ')" class="rpg-input w-full" @input="updateToneEvent" />
                </label>
              </div>
              <label class="block">
                <span class="mb-1.5 block font-display text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">Accroche</span>
                <textarea v-model="draftContract.hook" class="rpg-input min-h-20 w-full resize-y" />
              </label>
              <label class="block">
                <span class="mb-1.5 block font-display text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">Objectifs connus</span>
                <textarea
                  :value="draftContract.known_objectives.join('\n')"
                  class="rpg-input min-h-20 w-full resize-y"
                  @input="updateObjectivesEvent"
                />
              </label>
              <div class="space-y-2">
                <div class="font-display text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">Chapitres visibles</div>
                <div
                  v-for="chapter in draftContract.visible_chapters"
                  :key="chapter.id"
                  class="rounded-lg border border-border bg-surface p-3"
                >
                  <input v-model="chapter.title" class="rpg-input mb-2 w-full" />
                  <textarea v-model="chapter.summary" class="rpg-input min-h-16 w-full resize-y" />
                </div>
              </div>
            </div>

            <div v-else class="space-y-4">
              <div v-if="isFetchingDossier" class="rounded-lg border border-border bg-surface p-4 font-serif text-sm italic text-text-muted">
                Chargement du dossier MJ…
              </div>
              <template v-else>
                <div class="rounded-lg border border-border bg-surface p-4">
                  <div class="text-[9px] font-bold uppercase tracking-[0.22em] text-ember">Arc narratif privé</div>
                  <p class="mt-2 font-serif text-sm leading-relaxed text-parchment-dark">
                    {{ gmDossier?.narrative_arc || 'Aucun arc narratif privé.' }}
                  </p>
                </div>

                <div v-if="asList(gmDossier?.important_npcs).length" class="space-y-2">
                  <div class="text-[9px] font-bold uppercase tracking-[0.22em] text-text-muted">PNJ importants générés</div>
                  <div class="grid gap-2 md:grid-cols-2">
                    <div
                      v-for="(npc, idx) in (asList(gmDossier?.important_npcs) as Array<Record<string, unknown>>)"
                      :key="(npc.id as string) || idx"
                      class="rounded border border-border bg-black/20 p-2.5"
                    >
                      <div class="font-display text-xs font-bold text-parchment">{{ (npc.name as string) || 'PNJ' }}</div>
                      <div v-if="npc.archetype" class="mb-1 font-mono text-[9px] uppercase tracking-wider text-text-dim">{{ npc.archetype as string }}</div>
                      <p v-if="npc.short_description" class="font-serif text-[11px] leading-snug text-parchment-dark">{{ npc.short_description as string }}</p>
                    </div>
                  </div>
                </div>

                <div v-if="asList((gmDossier as Record<string, unknown> | null)?.items).length" class="space-y-2">
                  <div class="text-[9px] font-bold uppercase tracking-[0.22em] text-text-muted">Objets magiques / custom</div>
                  <div class="grid gap-2 md:grid-cols-2">
                    <div
                      v-for="(item, idx) in (asList((gmDossier as Record<string, unknown> | null)?.items) as Array<Record<string, unknown>>)"
                      :key="(item.id as string) || idx"
                      class="rounded border border-border bg-black/20 p-2.5"
                    >
                      <div class="font-display text-xs font-bold text-gold">{{ (item.name_fr as string) || (item.name as string) || 'Objet' }}</div>
                      <div v-if="item.rarity || item.item_type" class="mb-1 font-mono text-[9px] uppercase tracking-wider text-text-dim">
                        {{ item.rarity as string }}{{ item.rarity && item.item_type ? ' · ' : '' }}{{ item.item_type as string }}
                      </div>
                    </div>
                  </div>
                </div>

                <div v-if="asList(gmDossier?.chapters).length" class="space-y-2">
                  <div class="text-[9px] font-bold uppercase tracking-[0.22em] text-text-muted">Détails privés des chapitres</div>
                  <div
                    v-for="(ch, idx) in (asList(gmDossier?.chapters) as Array<Record<string, unknown>>)"
                    :key="(ch.id as string) || idx"
                    class="rounded-lg border border-border bg-surface p-3"
                  >
                    <div class="mb-1 font-display text-xs font-bold text-parchment">{{ (ch.title as string) || `Chapitre ${idx + 1}` }}</div>
                    <div class="space-y-1 font-serif text-[11px] text-parchment-dark">
                      <p v-if="ch.objective"><span class="font-bold text-text-muted">Objectif secret :</span> {{ ch.objective as string }}</p>
                      <p v-if="ch.stakes"><span class="font-bold text-text-muted">Enjeux :</span> {{ ch.stakes as string }}</p>
                    </div>
                  </div>
                </div>
              </template>
            </div>
          </div>

          <!-- Footer -->
          <div class="mt-7 flex justify-end gap-2">
            <button class="rpg-btn-secondary" :disabled="isForging || isValidating || isClosing" type="button" @click="handleFooterBack">
              {{ forgeStep === 1 ? 'Annuler' : 'Retour' }}
            </button>
            <button
              v-if="isForgeStep"
              class="rpg-btn-primary"
              :disabled="isForging"
              type="button"
              @click="runForge"
            >
              <span>⚔</span> {{ isForging ? 'Forge en cours…' : 'Forger le dossier' }}
            </button>
            <button
              v-else-if="isValidationStep"
              class="rpg-btn-primary"
              :disabled="isValidating || !draftContract"
              type="button"
              @click="validateAndStart"
            >
              {{ isValidating ? 'Validation…' : 'Valider et démarrer la 1re session' }}
            </button>
            <button
              v-else
              class="rpg-btn-primary"
              :disabled="isForging"
              type="button"
              @click="nextStep"
            >
              Suivant
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
