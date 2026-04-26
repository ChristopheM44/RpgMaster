<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useCampaignStore } from '../stores/campaign'
import type {
  Campaign,
  CampaignImportSourceBody,
  CampaignPlayerContract,
  CampaignScenario,
  CampaignVisibleChapter,
} from '../types'
import ConfirmDialog from '../components/common/ConfirmDialog.vue'

const router = useRouter()
const campaignStore = useCampaignStore()

type DetailTab = 'sessions' | 'scenario' | 'notes'
type ForgeStep = 1 | 2 | 3 | 4 | 5

const TONES = ['Dark fantasy', 'Mystère', 'Politique', 'Exploration', 'Combat tactique', 'Romance', 'Cosmique']
const DETAIL_TABS: Array<{ id: DetailTab; label: string; icon: string }> = [
  { id: 'sessions', label: 'Sessions', icon: '◆' },
  { id: 'scenario', label: 'Scénario', icon: '✦' },
  { id: 'notes', label: 'Notes du MJ', icon: '❦' },
]
const IMPORT_KINDS: Array<{ id: 'url' | 'text' | 'file_text'; label: string }> = [
  { id: 'text', label: 'Texte' },
  { id: 'url', label: 'URL' },
  { id: 'file_text', label: 'Fichier' },
]

const selectedCampaign = ref<Campaign | null>(null)
const activeTab = ref<DetailTab>('sessions')
const showForge = ref(false)
const showAdvance = ref(false)
const confirmDeleteId = ref<string | null>(null)
const newSessionName = ref('')
const forgeStep = ref<ForgeStep>(1)
const forgeCampaignId = ref<string | null>(null)
const draftContract = ref<CampaignPlayerContract | null>(null)
const sourceCount = ref(0)
const isForging = ref(false)
const isImporting = ref(false)
const isValidating = ref(false)
const modalError = ref<string | null>(null)

const forgeForm = reactive({
  name: '',
  pitch: '',
  duration: '3-5 sessions',
  tones: [] as string[],
  scope: 'mini-campagne',
  startingLevel: 1,
  combat: 'hybride léger',
  importKind: 'text' as 'url' | 'text' | 'file_text',
  importTitle: '',
  importUrl: '',
  importText: '',
  importFilename: '',
})

onMounted(async () => {
  await campaignStore.fetchCampaigns()
  if (campaignStore.campaigns[0]) {
    await selectCampaign(campaignStore.campaigns[0])
  }
})

watch(activeTab, async (tab) => {
  if (tab === 'scenario' && selectedCampaign.value) {
    await campaignStore.fetchScenario(selectedCampaign.value.id)
  }
})

const scenario = computed<CampaignScenario | null>(() => {
  if (!selectedCampaign.value) return null
  return campaignStore.scenarios[selectedCampaign.value.id] ?? null
})

const campaignToDelete = computed(
  () => campaignStore.campaigns.find((c) => c.id === confirmDeleteId.value) ?? null,
)

async function selectCampaign(campaign: Campaign) {
  const fresh = await campaignStore.fetchCampaign(campaign.id)
  selectedCampaign.value = fresh ?? campaign
  if (activeTab.value === 'scenario') await campaignStore.fetchScenario(campaign.id)
}

function openForge() {
  showForge.value = true
  forgeStep.value = 1
  forgeCampaignId.value = null
  draftContract.value = null
  sourceCount.value = 0
  modalError.value = null
  Object.assign(forgeForm, {
    name: '',
    pitch: '',
    duration: '3-5 sessions',
    tones: [],
    scope: 'mini-campagne',
    startingLevel: 1,
    combat: 'hybride léger',
    importKind: 'text',
    importTitle: '',
    importUrl: '',
    importText: '',
    importFilename: '',
  })
}

function closeForge() {
  showForge.value = false
}

function toggleTone(tone: string) {
  const idx = forgeForm.tones.indexOf(tone)
  if (idx >= 0) {
    forgeForm.tones.splice(idx, 1)
  } else if (forgeForm.tones.length < 3) {
    forgeForm.tones.push(tone)
  }
}

function nextStep() {
  modalError.value = null
  if (forgeStep.value === 1 && !forgeForm.name.trim()) {
    modalError.value = 'Le nom de la campagne est requis.'
    return
  }
  forgeStep.value = Math.min(5, forgeStep.value + 1) as ForgeStep
}

function previousStep() {
  modalError.value = null
  forgeStep.value = Math.max(1, forgeStep.value - 1) as ForgeStep
}

async function ensureForgeCampaign(): Promise<string | null> {
  if (forgeCampaignId.value) return forgeCampaignId.value
  const created = await campaignStore.createCampaign({
    name: forgeForm.name.trim(),
    description: forgeForm.pitch.trim(),
  })
  if (!created) {
    modalError.value = 'Impossible de créer la campagne.'
    return null
  }
  forgeCampaignId.value = created.id
  await selectCampaign(created)
  return created.id
}

async function importSource() {
  modalError.value = null
  const campaignId = await ensureForgeCampaign()
  if (!campaignId) return
  const body: CampaignImportSourceBody = {
    kind: forgeForm.importKind,
    title: forgeForm.importTitle.trim() || undefined,
  }
  if (forgeForm.importKind === 'url') {
    body.url = forgeForm.importUrl.trim()
  } else {
    body.content = forgeForm.importText.trim()
    body.filename = forgeForm.importFilename || undefined
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
    forgeForm.importTitle = ''
    forgeForm.importUrl = ''
    forgeForm.importText = ''
    forgeForm.importFilename = ''
  } finally {
    isImporting.value = false
  }
}

async function handleFileImport(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  forgeForm.importKind = 'file_text'
  forgeForm.importFilename = file.name
  forgeForm.importTitle = forgeForm.importTitle || file.name
  forgeForm.importText = await file.text()
}

async function forgeDraft() {
  modalError.value = null
  const campaignId = await ensureForgeCampaign()
  if (!campaignId) return
  isForging.value = true
  try {
    const result = await campaignStore.forgeDraft(
      campaignId,
      {
        title: forgeForm.name,
        pitch: forgeForm.pitch,
        tones: forgeForm.tones,
        duration: forgeForm.duration,
      },
      {
        scope: forgeForm.scope,
        starting_level: forgeForm.startingLevel,
        combat: forgeForm.combat,
      },
    )
    if (!result) {
      modalError.value = campaignStore.error ?? 'La forge a échoué.'
      return
    }
    draftContract.value = cloneContract(result.player_contract)
    forgeStep.value = 5
  } finally {
    isForging.value = false
  }
}

async function validateContract() {
  if (!forgeCampaignId.value || !draftContract.value) return
  isValidating.value = true
  modalError.value = null
  try {
    const result = await campaignStore.validateContract(forgeCampaignId.value, draftContract.value)
    if (!result) {
      modalError.value = campaignStore.error ?? 'Validation impossible.'
      return
    }
    await campaignStore.fetchCampaigns()
    const campaign = campaignStore.campaigns.find((c) => c.id === forgeCampaignId.value)
    if (campaign) {
      await selectCampaign(campaign)
      activeTab.value = 'scenario'
      await campaignStore.fetchScenario(campaign.id)
    }
    closeForge()
  } finally {
    isValidating.value = false
  }
}

function updateObjectives(value: string) {
  if (!draftContract.value) return
  draftContract.value.known_objectives = value
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean)
}

function updateToneInput(value: string) {
  if (!draftContract.value) return
  draftContract.value.tones = value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

function updateToneEvent(event: Event) {
  updateToneInput((event.target as HTMLInputElement).value)
}

function updateObjectivesEvent(event: Event) {
  updateObjectives((event.target as HTMLTextAreaElement).value)
}

function setActiveTab(tab: DetailTab) {
  activeTab.value = tab
}

function currentSessionId(campaign: Campaign): string | null {
  const ids = campaign.session_ids
  if (!ids.length) return null
  return ids[campaign.current_session_index] ?? ids[ids.length - 1] ?? null
}

async function playCurrent() {
  if (!selectedCampaign.value) return
  const sid = currentSessionId(selectedCampaign.value)
  if (!sid) return
  router.push({ name: 'game-session', params: { id: sid } })
}

async function handleAdvance() {
  if (!selectedCampaign.value || !newSessionName.value.trim()) return
  const result = await campaignStore.advance(selectedCampaign.value.id, newSessionName.value.trim())
  if (result) {
    showAdvance.value = false
    newSessionName.value = ''
    selectedCampaign.value = result.campaign
    router.push({
      name: 'character-setup',
      params: { id: result.new_session_id },
      query: { back: 'campaigns' },
    })
  }
}

async function handleDelete(id: string) {
  await campaignStore.deleteCampaign(id)
  if (selectedCampaign.value?.id === id) {
    selectedCampaign.value = campaignStore.campaigns[0] ?? null
  }
  confirmDeleteId.value = null
}

function displayChapter(campaign: Campaign): CampaignVisibleChapter {
  const chapter = campaign.active_chapter as CampaignVisibleChapter
  if (chapter?.title) return chapter
  return {
    id: 'chapter_1',
    num: 'I',
    title: 'À écrire',
    state: 'planned',
    sessions: 0,
    summary: campaign.description || 'Campagne à forger.',
  }
}

function progressPercent(campaign: Campaign): number {
  const total = Math.max(campaign.progress?.total ?? 1, 1)
  return Math.round(((campaign.progress?.done ?? 0) / total) * 100)
}

function formatDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    year: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

function sessionLabel(campaign: Campaign, idx: number): string {
  const chapter = displayChapter(campaign)
  return `Chap. ${chapter.num} — ${chapter.title}${idx === campaign.current_session_index ? ' · active' : ''}`
}

function chipStateLabel(state: string): string {
  if (state === 'done') return 'Terminé'
  if (state === 'active') return 'En cours'
  return 'À venir'
}

function cloneContract(contract: CampaignPlayerContract): CampaignPlayerContract {
  return JSON.parse(JSON.stringify(contract)) as CampaignPlayerContract
}
</script>

<template>
  <div class="flex min-h-[calc(100vh-56px)] bg-bg text-parchment">
    <section class="flex min-w-0 flex-1 flex-col">
      <div class="relative flex items-end gap-6 px-6 py-8 md:px-14">
        <div class="pointer-events-none absolute -left-10 -top-14 h-48 w-72 rounded-full bg-[radial-gradient(ellipse,rgba(255,130,71,0.12),transparent_70%)]" />
        <div class="relative min-w-0 flex-1">
          <div class="rpg-eyebrow"><span class="rpg-sparkle">✦</span>Vos chroniques</div>
          <h1 class="font-display text-[44px] font-bold leading-none tracking-[0.03em]">Campagnes</h1>
          <p class="mt-3 max-w-2xl font-serif text-[15px] italic leading-snug text-parchment-dark">
            Enchaînez des sessions avec progression persistante. Chaque campagne tisse son propre fil — quêtes, PNJ, lieux et chroniques.
          </p>
        </div>
        <button class="rpg-btn-primary shrink-0" @click="openForge">
          <span>✦</span> Forger une campagne
        </button>
      </div>

      <div class="min-h-0 flex-1 overflow-y-auto px-6 pb-8 md:px-14">
        <p v-if="!campaignStore.campaigns.length" class="py-16 text-center font-serif italic text-text-muted">
          Aucune campagne.
        </p>
        <div class="flex flex-col gap-2.5">
          <article
            v-for="campaign in campaignStore.campaigns"
            :key="campaign.id"
            class="relative cursor-pointer overflow-hidden rounded-[10px] border p-4 transition"
            :class="selectedCampaign?.id === campaign.id
              ? 'border-ember bg-[linear-gradient(135deg,rgba(255,130,71,0.12),var(--color-surface))] shadow-[0_0_24px_rgba(255,130,71,0.15)]'
              : 'border-border bg-surface hover:border-border-strong'"
            @click="selectCampaign(campaign)"
          >
            <div
              v-if="selectedCampaign?.id === campaign.id"
              class="absolute inset-y-0 left-0 w-[3px] bg-[linear-gradient(180deg,var(--color-ember),var(--color-gold))]"
            />
            <div class="flex items-start gap-3">
              <div class="min-w-0 flex-1">
                <h2 class="truncate font-display text-[17px] font-bold tracking-wide">
                  {{ campaign.name }}
                </h2>
                <p class="mt-0.5 truncate font-serif text-xs italic text-text-muted">
                  ✦ Chapitre {{ displayChapter(campaign).num }} — {{ displayChapter(campaign).title }}
                </p>
              </div>
              <button
                class="h-6 w-6 shrink-0 rounded text-text-dim transition hover:text-blood"
                @click.stop="confirmDeleteId = campaign.id"
              >
                ×
              </button>
            </div>

            <div class="mt-3">
              <div class="h-1 overflow-hidden rounded border border-border bg-black/40">
                <div
                  class="h-full bg-[linear-gradient(90deg,var(--color-gold-deep),var(--color-ember))]"
                  :style="{ width: `${progressPercent(campaign)}%` }"
                />
              </div>
              <div class="mt-1 flex justify-between font-mono text-[10px] text-text-dim">
                <span>{{ campaign.progress?.done ?? 0 }} / {{ campaign.progress?.total ?? 1 }} chapitres</span>
                <span>{{ formatDate(campaign.updated_at) }}</span>
              </div>
            </div>

            <div class="mt-3 flex flex-wrap gap-1.5">
              <span class="rounded border border-border bg-black/30 px-2 py-1 font-mono text-[10px] text-text-muted">◆ {{ campaign.counts?.sessions ?? campaign.session_ids.length }} sessions</span>
              <span class="rounded border border-border bg-black/30 px-2 py-1 font-mono text-[10px] text-text-muted">✦ {{ campaign.counts?.characters ?? campaign.character_ids.length }} persos</span>
              <span class="rounded border border-border bg-black/30 px-2 py-1 font-mono text-[10px] text-gold">◷ {{ campaign.counts?.quests_active ?? 0 }} quêtes</span>
              <span class="rounded border border-border bg-black/30 px-2 py-1 font-mono text-[10px] text-text-muted">◉ {{ campaign.counts?.npcs ?? 0 }} PNJ</span>
            </div>
          </article>
        </div>
      </div>
    </section>

    <aside
      v-if="selectedCampaign"
      class="flex w-[580px] shrink-0 flex-col border-l border-border bg-[linear-gradient(180deg,var(--color-bg-elev),var(--color-bg))]"
    >
      <header class="relative overflow-hidden border-b border-border px-7 py-6">
        <div class="pointer-events-none absolute -right-10 -top-16 h-56 w-56 rounded-full bg-[radial-gradient(circle,rgba(255,130,71,0.18),transparent_70%)]" />
        <div class="relative">
          <div class="rpg-eyebrow"><span class="rpg-sparkle">✦</span>Campagne sélectionnée</div>
          <h2 class="mt-1 font-display text-[28px] font-bold leading-tight">{{ selectedCampaign.name }}</h2>
          <p class="mt-1 line-clamp-2 font-serif text-[13px] italic text-parchment-dark">
            {{ selectedCampaign.tagline || selectedCampaign.description || 'Chronique à forger.' }}
          </p>
          <div class="mt-4 grid grid-cols-4 gap-2">
            <div class="rounded-md border border-border bg-black/30 p-2">
              <div class="text-[9px] font-bold uppercase tracking-[0.16em] text-text-dim">Sessions</div>
              <div class="font-display text-[22px] font-bold">{{ selectedCampaign.counts?.sessions ?? selectedCampaign.session_ids.length }}</div>
            </div>
            <div class="rounded-md border border-border bg-black/30 p-2">
              <div class="text-[9px] font-bold uppercase tracking-[0.16em] text-text-dim">Persos</div>
              <div class="font-display text-[22px] font-bold text-gold">{{ selectedCampaign.counts?.characters ?? selectedCampaign.character_ids.length }}</div>
            </div>
            <div class="rounded-md border border-border bg-black/30 p-2">
              <div class="text-[9px] font-bold uppercase tracking-[0.16em] text-text-dim">Quêtes</div>
              <div class="font-display text-[22px] font-bold text-ember">{{ selectedCampaign.counts?.quests_active ?? 0 }}</div>
              <div class="font-mono text-[9px] text-text-dim">{{ selectedCampaign.counts?.quests_done ?? 0 }} fini</div>
            </div>
            <div class="rounded-md border border-border bg-black/30 p-2">
              <div class="text-[9px] font-bold uppercase tracking-[0.16em] text-text-dim">Chronique</div>
              <div class="font-display text-[22px] font-bold text-arcane">{{ selectedCampaign.counts?.chronicle_entries ?? 0 }}</div>
              <div class="font-mono text-[9px] text-text-dim">entrées</div>
            </div>
          </div>
        </div>
      </header>

      <nav class="flex border-b border-border px-7">
        <button
          v-for="tab in DETAIL_TABS"
          :key="tab.id"
          class="border-b-2 px-3.5 py-3 font-display text-[11px] font-bold uppercase tracking-[0.12em] transition"
          :class="activeTab === tab.id ? 'border-ember text-parchment' : 'border-transparent text-text-muted hover:text-parchment'"
          @click="setActiveTab(tab.id)"
        >
          <span :class="activeTab === tab.id ? 'text-ember' : 'text-text-dim'">{{ tab.icon }}</span>
          {{ tab.label }}
        </button>
      </nav>

      <div class="min-h-0 flex-1 overflow-y-auto px-7 py-5">
        <div v-if="activeTab === 'sessions'" class="space-y-2">
          <p v-if="!selectedCampaign.session_ids.length" class="py-8 font-serif italic text-text-muted">
            Aucune session.
          </p>
          <div
            v-for="(sid, idx) in selectedCampaign.session_ids"
            :key="sid"
            class="flex items-center gap-3 rounded-lg border p-3"
            :class="idx === selectedCampaign.current_session_index
              ? 'border-[rgba(255,130,71,0.35)] bg-[linear-gradient(90deg,rgba(255,130,71,0.10),var(--color-surface))]'
              : 'border-border bg-surface'"
          >
            <div
              class="flex h-8 w-8 items-center justify-center rounded-md font-display text-sm font-bold"
              :class="idx === selectedCampaign.current_session_index
                ? 'bg-[linear-gradient(135deg,var(--color-ember),var(--color-gold))] text-bg'
                : 'border border-border bg-black/30 text-text-muted'"
            >
              {{ idx + 1 }}
            </div>
            <div class="min-w-0 flex-1">
              <div class="font-display text-[13px] font-bold tracking-wide">
                Session {{ idx + 1 }}
                <span v-if="idx === selectedCampaign.current_session_index" class="ml-2 rounded border border-ember/40 bg-ember/15 px-1.5 py-0.5 text-[9px] uppercase tracking-widest text-ember">active</span>
              </div>
              <div class="truncate font-serif text-[11px] italic text-text-muted">{{ sessionLabel(selectedCampaign, idx) }}</div>
            </div>
            <div class="font-mono text-[9px] text-text-dim">{{ sid.slice(0, 8) }}</div>
          </div>

          <div class="pt-3">
            <button
              v-if="currentSessionId(selectedCampaign)"
              class="rpg-btn-primary w-full justify-center font-display"
              @click="playCurrent"
            >
              ▶ Jouer la session courante
            </button>
            <button
              class="mt-2 w-full rounded-lg border border-arcane/30 bg-arcane/10 px-4 py-2.5 font-display text-[11px] font-bold uppercase tracking-[0.12em] text-arcane"
              @click="showAdvance = true"
            >
              → {{ selectedCampaign.session_ids.length === 0 ? 'Démarrer une session' : 'Session suivante (transférer personnages)' }}
            </button>
          </div>
        </div>

        <div v-else-if="activeTab === 'scenario'" class="space-y-5">
          <div v-if="!scenario" class="py-8 text-center">
            <button class="rpg-btn-secondary" @click="campaignStore.fetchScenario(selectedCampaign.id)">
              Charger le scénario
            </button>
          </div>
          <template v-else>
            <div class="text-[9px] font-bold uppercase tracking-[0.22em] text-text-muted">
              ✦ Arc narratif — {{ scenario.timeline.length }} chapitres
            </div>
            <div class="relative">
              <div class="absolute bottom-5 left-[13px] top-5 w-px bg-[linear-gradient(180deg,var(--color-border-strong),var(--color-border)_55%,transparent)]" />
              <div
                v-for="chapter in scenario.timeline"
                :key="chapter.id"
                class="relative flex gap-3.5 pb-4 last:pb-0"
              >
                <div
                  class="z-[1] flex h-7 w-7 shrink-0 items-center justify-center rounded-full font-display text-[11px] font-bold"
                  :class="chapter.state === 'active'
                    ? 'bg-[linear-gradient(135deg,var(--color-ember),var(--color-gold))] text-bg shadow-[0_0_14px_rgba(255,130,71,0.5)]'
                    : chapter.state === 'done'
                      ? 'border border-border-strong bg-surface-raised text-gold'
                      : 'border border-border bg-surface text-text-muted'"
                >
                  {{ chapter.num }}
                </div>
                <div
                  class="flex-1 rounded-lg border p-3"
                  :class="chapter.state === 'active'
                    ? 'border-ember/35 bg-[linear-gradient(135deg,rgba(255,130,71,0.08),var(--color-surface))]'
                    : 'border-border bg-surface'"
                >
                  <div class="flex items-baseline gap-2">
                    <h3 class="font-display text-[13px] font-bold">{{ chapter.title }}</h3>
                    <span class="rounded border border-border-strong bg-black/20 px-1.5 py-0.5 text-[8px] font-bold uppercase tracking-widest text-text-muted">
                      {{ chipStateLabel(chapter.state) }}
                    </span>
                    <span v-if="chapter.sessions" class="ml-auto font-mono text-[9px] text-text-dim">{{ chapter.sessions }} session</span>
                  </div>
                  <p class="mt-1 font-serif text-xs leading-relaxed text-parchment-dark">{{ chapter.summary }}</p>
                </div>
              </div>
            </div>

            <div class="rounded-lg border border-border bg-surface p-4">
              <div class="text-[9px] font-bold uppercase tracking-[0.22em] text-text-muted">✦ Objectifs connus</div>
              <ul class="mt-2 space-y-1 font-serif text-sm text-parchment-dark">
                <li v-for="objective in scenario.known_objectives" :key="objective">◆ {{ objective }}</li>
              </ul>
            </div>

            <div class="rounded-lg border border-border bg-surface p-4">
              <div class="text-[9px] font-bold uppercase tracking-[0.22em] text-text-muted">✦ Récap joué</div>
              <p class="mt-2 font-serif text-sm italic leading-relaxed text-parchment-dark">
                {{ scenario.played_summary || 'Aucun événement joué pour le moment.' }}
              </p>
            </div>
          </template>
        </div>

        <div v-else class="space-y-4">
          <div class="rounded-lg border border-border bg-surface p-4">
            <div class="text-[9px] font-bold uppercase tracking-[0.22em] text-text-muted">✦ Notes du MJ</div>
            <p class="mt-3 font-serif text-sm italic leading-relaxed text-parchment-dark">
              Mode auteur verrouillé. Les secrets, fronts, twists et sources importées restent côté MJ IA.
            </p>
          </div>
          <button class="w-full rounded-lg border border-blood/25 bg-transparent px-4 py-2.5 font-display text-[11px] font-bold uppercase tracking-[0.12em] text-blood/70" @click="confirmDeleteId = selectedCampaign.id">
            Supprimer la campagne
          </button>
        </div>
      </div>

      <footer class="border-t border-border bg-black/25 px-7 py-4">
        <div class="mb-2 text-[9px] font-bold uppercase tracking-[0.22em] text-text-muted">✦ Codex de la campagne</div>
        <div class="grid grid-cols-3 gap-2">
          <button class="rounded-lg border border-border bg-surface p-3 text-left">
            <div class="flex items-center gap-2 font-mono text-base font-bold text-gold">◷ {{ (selectedCampaign.counts?.quests_active ?? 0) + (selectedCampaign.counts?.quests_done ?? 0) }}</div>
            <div class="font-display text-[11px] font-bold leading-tight">Journal de quêtes</div>
            <div class="text-[9px] text-text-dim">{{ selectedCampaign.counts?.quests_active ?? 0 }} actives</div>
          </button>
          <button class="rounded-lg border border-border bg-surface p-3 text-left">
            <div class="flex items-center gap-2 font-mono text-base font-bold text-arcane">❦ {{ selectedCampaign.counts?.chronicle_entries ?? 0 }}</div>
            <div class="font-display text-[11px] font-bold leading-tight">Journal du chroniqueur</div>
            <div class="text-[9px] text-text-dim">entrées</div>
          </button>
          <button class="rounded-lg border border-border bg-surface p-3 text-left">
            <div class="flex items-center gap-2 font-mono text-base font-bold text-teal">◉ {{ (selectedCampaign.counts?.npcs ?? 0) + (selectedCampaign.counts?.places ?? 0) }}</div>
            <div class="font-display text-[11px] font-bold leading-tight">Carnet d’aventure</div>
            <div class="text-[9px] text-text-dim">{{ selectedCampaign.counts?.npcs ?? 0 }} PNJ · {{ selectedCampaign.counts?.places ?? 0 }} lieux</div>
          </button>
        </div>
      </footer>
    </aside>

    <Teleport to="body">
      <div
        v-if="showForge"
        class="fixed inset-0 z-50 flex items-center justify-center bg-[rgba(8,6,12,0.72)] p-4 backdrop-blur-md"
        @click.self="closeForge"
      >
        <div class="relative max-h-[90vh] w-full max-w-[640px] overflow-y-auto rounded-[14px] border border-border-strong bg-[linear-gradient(180deg,var(--color-bg-elev),var(--color-bg))] p-7 shadow-[0_24px_80px_rgba(0,0,0,0.6),0_0_0_1px_rgba(240,199,100,0.08)]">
          <div class="pointer-events-none absolute -right-12 -top-20 h-60 w-60 rounded-full bg-[radial-gradient(circle,rgba(255,130,71,0.18),transparent_70%)]" />
          <div class="relative">
            <div class="rpg-eyebrow"><span class="rpg-sparkle">✦</span>Forger une nouvelle chronique</div>
            <h2 class="mt-1 font-display text-[28px] font-bold leading-tight">Nouvelle campagne</h2>

            <div class="mt-5 flex gap-2">
              <span
                v-for="step in 5"
                :key="step"
                class="h-1.5 flex-1 rounded-full"
                :class="step <= forgeStep ? 'bg-[linear-gradient(90deg,var(--color-ember),var(--color-gold))]' : 'bg-surface-raised'"
              />
            </div>

            <p v-if="modalError" class="mt-4 rounded border border-blood/30 bg-blood/10 px-3 py-2 text-sm text-blood-light">
              {{ modalError }}
            </p>

            <div v-if="forgeStep === 1" class="mt-6 space-y-4">
              <label class="block">
                <span class="mb-1.5 block font-display text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">Nom de la campagne</span>
                <input v-model="forgeForm.name" class="rpg-input w-full text-base" placeholder="La Chute des Rois Anciens" />
              </label>
              <label class="block">
                <span class="mb-1.5 block font-display text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">Brief court</span>
                <textarea v-model="forgeForm.pitch" class="rpg-input min-h-28 w-full resize-y" placeholder="Une épopée qui traverse trois royaumes..." />
              </label>
              <div>
                <div class="mb-2 font-display text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">Tonalités — max 3</div>
                <div class="flex flex-wrap gap-2">
                  <button
                    v-for="tone in TONES"
                    :key="tone"
                    class="rounded-full border px-3 py-1.5 font-serif text-[11px] transition"
                    :class="forgeForm.tones.includes(tone)
                      ? 'border-arcane/50 bg-arcane/15 text-arcane'
                      : 'border-border bg-transparent text-text-muted hover:border-border-strong'"
                    @click="toggleTone(tone)"
                  >
                    {{ tone }}
                  </button>
                </div>
              </div>
            </div>

            <div v-else-if="forgeStep === 2" class="mt-6 grid gap-4 md:grid-cols-2">
              <label class="block">
                <span class="mb-1.5 block font-display text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">Durée</span>
                <input v-model="forgeForm.duration" class="rpg-input w-full" />
              </label>
              <label class="block">
                <span class="mb-1.5 block font-display text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">Niveau initial</span>
                <input v-model.number="forgeForm.startingLevel" min="1" max="20" type="number" class="rpg-input w-full" />
              </label>
              <label class="block">
                <span class="mb-1.5 block font-display text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">Format</span>
                <select v-model="forgeForm.scope" class="rpg-input w-full">
                  <option>one-shot</option>
                  <option>mini-campagne</option>
                  <option>campagne longue</option>
                </select>
              </label>
              <label class="block">
                <span class="mb-1.5 block font-display text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">Mécaniques</span>
                <select v-model="forgeForm.combat" class="rpg-input w-full">
                  <option>hybride léger</option>
                  <option>exploration sociale</option>
                  <option>combat tactique</option>
                </select>
              </label>
            </div>

            <div v-else-if="forgeStep === 3" class="mt-6 space-y-4">
              <div class="flex gap-2">
                <button
                  v-for="kind in IMPORT_KINDS"
                  :key="kind.id"
                  class="rounded-md border px-3 py-1.5 text-xs font-semibold uppercase tracking-widest"
                  :class="forgeForm.importKind === kind.id ? 'border-gold/40 bg-gold/10 text-gold' : 'border-border text-text-muted'"
                  @click="forgeForm.importKind = kind.id"
                >
                  {{ kind.label }}
                </button>
              </div>
              <input v-model="forgeForm.importTitle" class="rpg-input w-full" placeholder="Titre de source" />
              <input v-if="forgeForm.importKind === 'url'" v-model="forgeForm.importUrl" class="rpg-input w-full" placeholder="https://..." />
              <input v-if="forgeForm.importKind === 'file_text'" type="file" class="w-full rounded border border-border-strong bg-black/30 px-3 py-2 text-sm text-text-muted" accept=".txt,.md,.html,.htm" @change="handleFileImport" />
              <textarea v-if="forgeForm.importKind !== 'url'" v-model="forgeForm.importText" class="rpg-input min-h-40 w-full resize-y" placeholder="Collez une aventure, un synopsis ou des notes..." />
              <div class="flex items-center justify-between">
                <span class="font-mono text-xs text-text-muted">{{ sourceCount }} source{{ sourceCount > 1 ? 's' : '' }} privée{{ sourceCount > 1 ? 's' : '' }}</span>
                <button class="rpg-btn-secondary" :disabled="isImporting" @click="importSource">
                  {{ isImporting ? 'Import...' : 'Importer' }}
                </button>
              </div>
            </div>

            <div v-else-if="forgeStep === 4" class="mt-6 rounded-lg border border-border bg-surface p-5 text-center">
              <div class="font-display text-lg font-bold">Forge IA</div>
              <p class="mx-auto mt-2 max-w-md font-serif text-sm italic text-parchment-dark">
                Le dossier privé sera structuré côté MJ, puis seul le contrat joueur sera affiché.
              </p>
              <button class="rpg-btn-primary mt-5" :disabled="isForging" @click="forgeDraft">
                <span>⚔</span> {{ isForging ? 'Forge en cours...' : 'Forger le dossier' }}
              </button>
            </div>

            <div v-else-if="draftContract" class="mt-6 space-y-4">
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
                <textarea :value="draftContract.known_objectives.join('\n')" class="rpg-input min-h-20 w-full resize-y" @input="updateObjectivesEvent" />
              </label>
              <div class="space-y-2">
                <div class="font-display text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">Chapitres visibles</div>
                <div v-for="chapter in draftContract.visible_chapters" :key="chapter.id" class="rounded-lg border border-border bg-surface p-3">
                  <input v-model="chapter.title" class="rpg-input mb-2 w-full" />
                  <textarea v-model="chapter.summary" class="rpg-input min-h-16 w-full resize-y" />
                </div>
              </div>
            </div>

            <div class="mt-7 flex justify-end gap-2">
              <button class="rpg-btn-secondary" @click="forgeStep === 1 ? closeForge() : previousStep()">
                {{ forgeStep === 1 ? 'Annuler' : 'Retour' }}
              </button>
              <button v-if="forgeStep < 4" class="rpg-btn-primary" @click="nextStep">Suivant</button>
              <button v-else-if="forgeStep === 4" class="rpg-btn-secondary" @click="forgeDraft">Forger</button>
              <button v-else class="rpg-btn-primary" :disabled="isValidating" @click="validateContract">
                {{ isValidating ? 'Validation...' : 'Valider le contrat' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div v-if="showAdvance" class="fixed inset-0 z-50 flex items-center justify-center bg-ink/80 p-4" @click.self="showAdvance = false">
        <div class="w-full max-w-md rounded-xl border border-border-strong bg-bg-elev p-6 shadow-xl">
          <h2 class="font-display text-lg font-bold text-gold">Nouvelle session</h2>
          <p class="mt-2 text-sm text-text-muted">Les personnages seront transférés avec leurs stats actuelles.</p>
          <input v-model="newSessionName" class="rpg-input mt-4 w-full" placeholder="Nom de la nouvelle session..." @keydown.enter="handleAdvance" />
          <div class="mt-4 flex justify-end gap-2">
            <button class="rpg-btn-secondary" @click="showAdvance = false">Annuler</button>
            <button class="rpg-btn-primary" @click="handleAdvance">Créer</button>
          </div>
        </div>
      </div>
    </Teleport>

    <ConfirmDialog
      v-if="campaignToDelete"
      title="Supprimer cette campagne ?"
      :message="`« ${campaignToDelete.name} » sera définitivement supprimée. Les sessions rattachées ne seront pas effacées.`"
      confirm-label="Supprimer"
      tone="danger"
      @confirm="handleDelete(campaignToDelete.id)"
      @cancel="confirmDeleteId = null"
    />
  </div>
</template>
