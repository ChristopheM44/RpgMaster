<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useCampaignStore } from '../stores/campaign'
import { useGameStore } from '../stores/game'
import type {
  Campaign,
  CampaignGmDossier,
  CampaignGmDossierResponse,
  CampaignScenario,
  CampaignSessionSummary,
  CampaignVisibleChapter,
  SessionStatus,
} from '../types'
import ConfirmDialog from '../components/common/ConfirmDialog.vue'
import CampaignForgeModal from './CampaignForgeModal.vue'
import CampaignCharacterPanel from '../components/campaign/CampaignCharacterPanel.vue'

const router = useRouter()
const campaignStore = useCampaignStore()
const gameStore = useGameStore()

type DetailTab = 'sessions' | 'scenario' | 'notes' | 'groupe'

const DETAIL_TABS: Array<{ id: DetailTab; label: string; icon: string }> = [
  { id: 'sessions', label: 'Sessions', icon: '◆' },
  { id: 'scenario', label: 'Scénario', icon: '✦' },
  { id: 'notes', label: 'Notes du MJ', icon: '❦' },
  { id: 'groupe', label: 'Groupe', icon: '⚔' },
]
const STATUS_META: Record<SessionStatus, { label: string; tone: string; live: boolean }> = {
  lobby: { label: 'Préparation', tone: 'rpg-tone-muted', live: false },
  character_creation: { label: 'Création', tone: 'rpg-tone-arcane', live: false },
  exploration: { label: 'Exploration', tone: 'rpg-tone-green', live: true },
  encounter_start: { label: 'Rencontre', tone: 'rpg-tone-blood', live: true },
  combat: { label: 'Combat', tone: 'rpg-tone-blood', live: true },
  encounter_end: { label: 'Fin rencontre', tone: 'rpg-tone-gold', live: true },
  rest: { label: 'Repos', tone: 'rpg-tone-teal', live: true },
  level_up: { label: 'Montée', tone: 'rpg-tone-gold', live: true },
  session_end: { label: 'Terminée', tone: 'rpg-tone-dim', live: false },
}
const GM_SECTIONS: Array<{ key: keyof CampaignGmDossier; label: string }> = [
  { key: 'important_npcs', label: 'PNJ importants' },
  { key: 'locations', label: 'Lieux' },
  { key: 'factions', label: 'Factions' },
  { key: 'quests', label: 'Quêtes' },
  { key: 'fronts', label: 'Fronts' },
  { key: 'secrets', label: 'Secrets globaux' },
  { key: 'revelations', label: 'Révélations' },
  { key: 'complications', label: 'Complications' },
  { key: 'clues', label: 'Indices' },
  { key: 'light_mechanics', label: 'Mécaniques légères' },
]

const selectedCampaign = ref<Campaign | null>(null)
const activeTab = ref<DetailTab>('sessions')
const showForge = ref(false)
const showAdvance = ref(false)
const confirmDeleteId = ref<string | null>(null)
const confirmResetId = ref<string | null>(null)
const newSessionName = ref('')
const isResetting = ref(false)
const authorMode = ref(false)
const isLoadingGmDossier = ref(false)
const actionError = ref<string | null>(null)
const notesError = ref<string | null>(null)

onMounted(async () => {
  await campaignStore.fetchCampaigns()
  if (router.currentRoute.value.query.forge === '1') {
    showForge.value = true
  } else if (campaignStore.campaigns[0]) {
    await selectCampaign(campaignStore.campaigns[0])
  }
})

watch(activeTab, async (tab) => {
  if (tab === 'scenario' && selectedCampaign.value) {
    await campaignStore.fetchScenario(selectedCampaign.value.id)
  }
  if (tab === 'notes' && selectedCampaign.value && authorMode.value) {
    await loadGmDossier()
  }
})

const scenario = computed<CampaignScenario | null>(() => {
  if (!selectedCampaign.value) return null
  return campaignStore.scenarios[selectedCampaign.value.id] ?? null
})

const sessionSummaries = computed<CampaignSessionSummary[]>(() => {
  if (!selectedCampaign.value) return []
  return selectedCampaign.value.session_summaries ?? selectedCampaign.value.session_ids.map((id) => ({
    id,
    name: `Session ${selectedCampaign.value!.session_ids.indexOf(id) + 1}`,
    status: 'lobby',
    created_at: selectedCampaign.value!.created_at,
    updated_at: selectedCampaign.value!.updated_at,
    character_count: 0,
  }))
})

const currentSession = computed<CampaignSessionSummary | null>(() => {
  if (!selectedCampaign.value) return null
  const index = selectedCampaign.value.current_session_index
  return sessionSummaries.value[index] ?? sessionSummaries.value[sessionSummaries.value.length - 1] ?? null
})

const gmDossierResponse = computed<CampaignGmDossierResponse | null>(() => {
  if (!selectedCampaign.value) return null
  return campaignStore.gmDossiers[selectedCampaign.value.id] ?? null
})

const gmDossier = computed<CampaignGmDossier | null>(() => gmDossierResponse.value?.gm_dossier ?? null)

const gmDossierRaw = computed(() => {
  if (!gmDossier.value) return ''
  return JSON.stringify(gmDossier.value, null, 2)
})

const campaignToDelete = computed(
  () => campaignStore.campaigns.find((c) => c.id === confirmDeleteId.value) ?? null,
)

const campaignToReset = computed(
  () => campaignStore.campaigns.find((c) => c.id === confirmResetId.value) ?? null,
)

async function selectCampaign(campaign: Campaign) {
  actionError.value = null
  const fresh = await campaignStore.fetchCampaign(campaign.id)
  selectedCampaign.value = fresh ?? campaign
  if (activeTab.value === 'scenario') await campaignStore.fetchScenario(campaign.id)
  if (activeTab.value === 'notes' && authorMode.value) await loadGmDossier()
}

function openForge() {
  showForge.value = true
}

async function handleForgeCompleted(payload: { campaignId: string; newSessionId: string }) {
  showForge.value = false
  await campaignStore.fetchCampaigns()
  const campaign = campaignStore.campaigns.find((c) => c.id === payload.campaignId)
  if (campaign) selectedCampaign.value = campaign
  await router.push({
    name: 'character-setup',
    params: { id: payload.newSessionId },
    query: { back: 'campaigns' },
  })
}

function setActiveTab(tab: DetailTab) {
  activeTab.value = tab
}

async function loadGmDossier(force = false) {
  if (!selectedCampaign.value) return
  const campaignId = selectedCampaign.value.id
  if (!force && campaignStore.gmDossiers[campaignId]) return
  notesError.value = null
  isLoadingGmDossier.value = true
  try {
    const result = await campaignStore.fetchGmDossier(campaignId)
    if (!result) {
      notesError.value = campaignStore.error ?? 'Notes MJ introuvables.'
    }
  } finally {
    isLoadingGmDossier.value = false
  }
}

async function setAuthorMode(value: boolean) {
  authorMode.value = value
  notesError.value = null
  if (value) {
    await loadGmDossier()
  }
}

function handleAuthorModeChange(event: Event) {
  void setAuthorMode((event.target as HTMLInputElement).checked)
}

function currentSessionId(campaign: Campaign): string | null {
  const ids = campaign.session_ids
  if (!ids.length) return null
  return ids[campaign.current_session_index] ?? ids[ids.length - 1] ?? null
}

async function playCurrent() {
  if (!selectedCampaign.value) return
  const sid = currentSession.value?.id ?? currentSessionId(selectedCampaign.value)
  if (!sid) return
  actionError.value = null
  if (currentSession.value && ['lobby', 'character_creation'].includes(currentSession.value.status)) {
    await router.push({
      name: 'character-setup',
      params: { id: sid },
      query: { back: 'campaigns' },
    })
    return
  }
  await openPlaySession(sid)
}

async function startAndOpenSession(sessionId: string): Promise<boolean> {
  gameStore.setProcessing(true)
  try {
    await router.push({
      name: 'game-session',
      params: { id: sessionId },
      query: { start: '1' },
    })
    return true
  } catch {
    gameStore.setProcessing(false)
    actionError.value = 'Impossible de lancer la session. Vérifiez que la chronique possède au moins un personnage.'
    activeTab.value = 'sessions'
    return false
  }
}

async function openPlaySession(sessionId: string): Promise<boolean> {
  gameStore.setProcessing(true)
  try {
    await router.push({
      name: 'game-session',
      params: { id: sessionId },
    })
    return true
  } catch {
    gameStore.setProcessing(false)
    actionError.value = 'Impossible d’ouvrir la session.'
    activeTab.value = 'sessions'
    return false
  }
}

async function openSession(summary: CampaignSessionSummary) {
  if (['lobby', 'character_creation'].includes(summary.status)) {
    await router.push({
      name: 'character-setup',
      params: { id: summary.id },
      query: { back: 'campaigns' },
    })
    return
  }
  await openPlaySession(summary.id)
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

async function handleReset(id: string) {
  actionError.value = null
  isResetting.value = true
  try {
    const result = await campaignStore.resetCampaign(id)
    if (!result) return
    selectedCampaign.value = result.campaign
    if (activeTab.value === 'scenario') await campaignStore.fetchScenario(id)
    if (activeTab.value === 'notes' && authorMode.value) await loadGmDossier(true)
    confirmResetId.value = null
    await startAndOpenSession(result.session_id)
  } finally {
    isResetting.value = false
  }
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

function statusMeta(status: SessionStatus) {
  return STATUS_META[status] ?? STATUS_META.lobby
}

function sessionActionLabel(status: SessionStatus): string {
  if (status === 'session_end') return 'Voir →'
  if (status === 'lobby' || status === 'character_creation') return 'Préparer →'
  return 'Jouer →'
}

function chipStateLabel(state: string): string {
  if (state === 'done') return 'Terminé'
  if (state === 'active') return 'En cours'
  return 'À venir'
}

function asList(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

function dossierList(key: keyof CampaignGmDossier): unknown[] {
  if (!gmDossier.value) return []
  return asList(gmDossier.value[key])
}

function formatGmValue(value: unknown): string {
  if (value === null || value === undefined) return ''
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  return JSON.stringify(value, null, 2)
}

function itemTitle(item: unknown, fallback: string): string {
  if (typeof item === 'string' || typeof item === 'number' || typeof item === 'boolean') {
    return String(item)
  }
  if (item && typeof item === 'object' && !Array.isArray(item)) {
    const record = item as Record<string, unknown>
    return (
      formatGmValue(record.title)
      || formatGmValue(record.name)
      || formatGmValue(record.label)
      || formatGmValue(record.id)
      || fallback
    )
  }
  return fallback
}

function itemDetail(item: unknown): string {
  if (!item || typeof item !== 'object' || Array.isArray(item)) return ''
  const record = item as Record<string, unknown>
  const preferred = record.summary ?? record.description ?? record.note ?? record.secret ?? record.objective
  if (preferred !== undefined && preferred !== null && preferred !== '') return formatGmValue(preferred)
  const rest = Object.fromEntries(
    Object.entries(record).filter(([key]) => !['id', 'title', 'name', 'label', 'public'].includes(key)),
  )
  return Object.keys(rest).length ? JSON.stringify(rest, null, 2) : ''
}
</script>

<template>
  <div class="flex min-h-[calc(100vh-56px)] bg-bg text-parchment">
    <section class="flex min-w-0 flex-1 flex-col">
      <div class="relative flex items-end gap-6 px-6 py-8 md:px-14">
        <div class="rpg-campaign-hero-glow pointer-events-none absolute -left-10 -top-14 h-48 w-72 rounded-full" />
        <div class="relative min-w-0 flex-1">
          <div class="rpg-eyebrow"><span class="rpg-sparkle">✦</span>Vos chroniques</div>
          <h1 class="font-display text-[44px] font-bold leading-none tracking-[0.03em]">Chroniques</h1>
          <p class="mt-3 max-w-2xl font-serif text-[15px] italic leading-snug text-parchment-dark">
            Reprenez vos aventures depuis leur chronique. Même un one-shot garde son fil — groupe, session active, quêtes, PNJ et mémoire jouée.
          </p>
        </div>
        <button class="rpg-btn-primary shrink-0" @click="openForge">
          <span>✦</span> Forger une chronique
        </button>
      </div>

      <div class="min-h-0 flex-1 overflow-y-auto px-6 pb-8 md:px-14">
        <p v-if="!campaignStore.campaigns.length" class="py-16 text-center font-serif italic text-text-muted">
          Aucune chronique.
        </p>
        <div class="flex flex-col gap-2.5">
          <article
            v-for="campaign in campaignStore.campaigns"
            :key="campaign.id"
            class="rpg-campaign-card relative cursor-pointer overflow-hidden rounded-[10px] border p-4 transition"
            :class="{ 'is-selected': selectedCampaign?.id === campaign.id }"
            @click="selectCampaign(campaign)"
          >
            <div
              v-if="selectedCampaign?.id === campaign.id"
              class="rpg-campaign-accent-bar absolute inset-y-0 left-0 w-[3px]"
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
              <div class="flex shrink-0 items-center gap-1">
                <button
                  class="h-6 w-6 rounded text-text-dim transition hover:text-gold"
                  type="button"
                  title="Réinitialiser la chronique"
                  aria-label="Réinitialiser la chronique"
                  @click.stop="confirmResetId = campaign.id"
                >
                  ↺
                </button>
                <button
                  class="h-6 w-6 rounded text-text-dim transition hover:text-blood"
                  type="button"
                  title="Supprimer la chronique"
                  aria-label="Supprimer la chronique"
                  @click.stop="confirmDeleteId = campaign.id"
                >
                  ×
                </button>
              </div>
            </div>

            <div class="mt-3">
              <div class="h-1 overflow-hidden rounded border border-border bg-black/40">
                <div
                  class="rpg-campaign-progress-fill h-full"
                  :style="{ width: `${progressPercent(campaign)}%` }"
                />
              </div>
              <div class="mt-1 flex justify-between font-mono text-[10px] text-text-dim">
                <span>{{ campaign.progress?.done ?? 0 }} / {{ campaign.progress?.total ?? 1 }} chapitres</span>
                <span>{{ formatDate(campaign.updated_at) }}</span>
              </div>
            </div>

            <div class="mt-3 flex flex-wrap gap-1.5">
              <span class="rpg-chip rpg-tone-muted font-mono text-[10px]">◆ {{ campaign.counts?.sessions ?? campaign.session_ids.length }} sessions</span>
              <span class="rpg-chip rpg-tone-muted font-mono text-[10px]">✦ {{ campaign.counts?.characters ?? campaign.character_ids.length }} persos</span>
              <span class="rpg-chip rpg-tone-gold font-mono text-[10px]">◷ {{ campaign.counts?.quests_active ?? 0 }} quêtes</span>
              <span class="rpg-chip rpg-tone-muted font-mono text-[10px]">◉ {{ campaign.counts?.npcs ?? 0 }} PNJ</span>
            </div>
          </article>
        </div>
      </div>
    </section>

    <aside
      v-if="selectedCampaign"
      class="rpg-campaign-aside flex w-[580px] shrink-0 flex-col border-l border-border"
    >
      <header class="relative overflow-hidden border-b border-border px-7 py-6">
        <div class="rpg-campaign-side-glow pointer-events-none absolute -right-10 -top-16 h-56 w-56 rounded-full" />
        <div class="relative">
          <div class="rpg-eyebrow"><span class="rpg-sparkle">✦</span>Campagne sélectionnée</div>
          <h2 class="mt-1 font-display text-[28px] font-bold leading-tight">{{ selectedCampaign.name }}</h2>
          <p class="mt-1 line-clamp-2 font-serif text-[13px] italic text-parchment-dark">
            {{ selectedCampaign.tagline || selectedCampaign.description || 'Chronique à forger.' }}
          </p>
          <div class="mt-4 grid grid-cols-4 gap-2">
            <div class="rpg-campaign-stat rounded-md border p-2">
              <div class="text-[9px] font-bold uppercase tracking-[0.16em] text-text-dim">Sessions</div>
              <div class="font-display text-[22px] font-bold">{{ selectedCampaign.counts?.sessions ?? selectedCampaign.session_ids.length }}</div>
            </div>
            <div class="rpg-campaign-stat rounded-md border p-2">
              <div class="text-[9px] font-bold uppercase tracking-[0.16em] text-text-dim">Persos</div>
              <div class="font-display text-[22px] font-bold text-gold">{{ selectedCampaign.counts?.characters ?? selectedCampaign.character_ids.length }}</div>
            </div>
            <div class="rpg-campaign-stat rounded-md border p-2">
              <div class="text-[9px] font-bold uppercase tracking-[0.16em] text-text-dim">Quêtes</div>
              <div class="font-display text-[22px] font-bold text-ember">{{ selectedCampaign.counts?.quests_active ?? 0 }}</div>
              <div class="font-mono text-[9px] text-text-dim">{{ selectedCampaign.counts?.quests_done ?? 0 }} fini</div>
            </div>
            <div class="rpg-campaign-stat rounded-md border p-2">
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
          <p v-if="actionError" class="rounded border border-blood/30 bg-blood/10 px-3 py-2 text-sm text-blood-light">
            {{ actionError }}
          </p>
          <p v-if="!sessionSummaries.length" class="py-8 font-serif italic text-text-muted">
            Aucune session rattachée à cette chronique.
          </p>
          <div
            v-for="(session, idx) in sessionSummaries"
            :key="session.id"
            class="rpg-campaign-session-row flex items-center gap-3 rounded-lg border p-3"
            :class="{ 'is-active': idx === selectedCampaign.current_session_index }"
          >
            <div
              class="rpg-campaign-index-badge flex h-8 w-8 items-center justify-center rounded-md border font-display text-sm font-bold"
              :class="{ 'is-active': idx === selectedCampaign.current_session_index }"
            >
              {{ idx + 1 }}
            </div>
            <div class="min-w-0 flex-1">
              <div class="flex min-w-0 items-center gap-2">
                <div class="truncate font-display text-[13px] font-bold tracking-wide">
                  {{ session.name || `Session ${idx + 1}` }}
                </div>
                <span v-if="idx === selectedCampaign.current_session_index" class="rpg-chip rpg-tone-ember ml-2 px-1.5 py-0.5 text-[9px] uppercase tracking-widest">active</span>
              </div>
              <div class="truncate font-serif text-[11px] italic text-text-muted">{{ sessionLabel(selectedCampaign, idx) }}</div>
              <div class="mt-1 flex flex-wrap items-center gap-2 font-mono text-[9px] text-text-dim">
                <span class="rpg-chip px-1.5 py-0.5 text-[9px]" :class="statusMeta(session.status).tone">
                  <span v-if="statusMeta(session.status).live" class="rpg-pulse">●</span>
                  {{ statusMeta(session.status).label }}
                </span>
                <span>✦ {{ session.character_count }} perso.</span>
                <span>◷ {{ formatDate(session.updated_at) }}</span>
              </div>
            </div>
            <button
              class="rpg-btn-secondary shrink-0 !px-3 !py-1.5 !text-[10px]"
              type="button"
              @click="openSession(session)"
            >
              {{ sessionActionLabel(session.status) }}
            </button>
          </div>

          <div class="pt-3">
            <button
              v-if="currentSession"
              class="rpg-btn-primary w-full justify-center font-display"
              @click="playCurrent"
            >
              ▶ {{ ['lobby', 'character_creation'].includes(currentSession.status) ? 'Préparer le groupe' : 'Jouer la session courante' }}
            </button>
            <button
              class="rpg-quick-action rpg-tone-arcane mt-2 w-full rounded-lg border px-4 py-2.5 font-display"
              @click="showAdvance = true"
            >
              → Session suivante (transférer personnages)
            </button>
            <button
              class="mt-2 w-full rounded-lg border border-gold/30 bg-gold/10 px-4 py-2.5 font-display text-[11px] font-bold uppercase tracking-[0.12em] text-gold transition hover:border-gold/50"
              type="button"
              @click="confirmResetId = selectedCampaign.id"
            >
              ↺ Réinitialiser la chronique
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
              <div class="rpg-campaign-timeline-line absolute bottom-5 left-[13px] top-5 w-px" />
              <div
                v-for="chapter in scenario.timeline"
                :key="chapter.id"
                class="relative flex gap-3.5 pb-4 last:pb-0"
              >
                <div
                  class="rpg-campaign-timeline-dot z-[1] flex h-7 w-7 shrink-0 items-center justify-center rounded-full border font-display text-[11px] font-bold"
                  :class="chapter.state === 'active'
                    ? 'is-active'
                    : chapter.state === 'done'
                      ? 'is-done'
                      : 'is-planned'"
                >
                  {{ chapter.num }}
                </div>
                <div
                  class="rpg-campaign-chapter-card flex-1 rounded-lg border p-3"
                  :class="{ 'is-active': chapter.state === 'active' }"
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

        <div v-else-if="activeTab === 'notes'" class="space-y-4">
          <div class="rounded-lg border border-border bg-surface p-4">
            <div class="flex items-center justify-between gap-3">
              <div>
                <div class="text-[9px] font-bold uppercase tracking-[0.22em] text-text-muted">✦ Notes du MJ</div>
                <div
                  v-if="gmDossierResponse"
                  class="mt-1 font-mono text-[10px] uppercase tracking-wider text-text-dim"
                >
                  {{ gmDossierResponse.generation_status }} · chapitre {{ gmDossierResponse.active_chapter_id || 'n/a' }}
                </div>
              </div>
              <label class="inline-flex cursor-pointer items-center gap-2">
                <span class="font-display text-[10px] font-bold uppercase tracking-[0.14em] text-parchment-dark">Mode auteur</span>
                <input
                  class="sr-only"
                  type="checkbox"
                  :checked="authorMode"
                  @change="handleAuthorModeChange"
                />
                <span
                  class="relative h-6 w-11 rounded-full border transition"
                  :class="authorMode ? 'border-ember/50 bg-ember/25' : 'border-border-strong bg-black/30'"
                >
                  <span
                    class="absolute top-1 h-4 w-4 rounded-full transition"
                    :class="authorMode ? 'left-6 bg-ember' : 'left-1 bg-text-dim'"
                  />
                </span>
              </label>
            </div>

            <p
              v-if="!authorMode"
              class="mt-3 font-serif text-sm italic leading-relaxed text-parchment-dark"
            >
              Mode auteur verrouillé. Les secrets, fronts, twists et sources importées restent côté MJ IA.
            </p>
            <p v-else-if="notesError" class="mt-3 rounded border border-blood/30 bg-blood/10 px-3 py-2 text-sm text-blood-light">
              {{ notesError }}
            </p>
            <p v-else-if="isLoadingGmDossier" class="mt-3 font-serif text-sm italic text-text-muted">
              Chargement des notes MJ...
            </p>
            <p v-else-if="!gmDossier" class="mt-3 font-serif text-sm italic text-text-muted">
              Aucun dossier MJ disponible.
            </p>
          </div>

          <template v-if="authorMode && gmDossier">
            <div class="rpg-campaign-author-panel rounded-lg border p-4">
              <div class="text-[9px] font-bold uppercase tracking-[0.22em] text-ember">Arc narratif privé</div>
              <p class="mt-2 font-serif text-sm leading-relaxed text-parchment-dark">
                {{ gmDossier.narrative_arc || 'Aucun arc privé.' }}
              </p>
            </div>

            <div v-if="gmDossier.chapters?.length" class="space-y-3">
              <div class="text-[9px] font-bold uppercase tracking-[0.22em] text-text-muted">
                Chapitres privés — {{ gmDossier.chapters.length }}
              </div>
              <div
                v-for="(chapter, chapterIdx) in gmDossier.chapters"
                :key="chapter.id || chapter.title || chapterIdx"
                class="rpg-campaign-private-card rounded-lg border p-4"
                :class="{ 'is-active': gmDossierResponse?.active_chapter_id === chapter.id }"
              >
                <div class="flex items-start gap-2">
                  <div class="min-w-0 flex-1">
                    <h3 class="font-display text-[14px] font-bold">{{ chapter.title || `Chapitre ${chapterIdx + 1}` }}</h3>
                    <div class="mt-0.5 font-mono text-[9px] uppercase tracking-wider text-text-dim">
                      {{ chipStateLabel(chapter.state || 'planned') }} · {{ chapter.id || 'sans-id' }}
                    </div>
                  </div>
                </div>
                <div class="mt-3 space-y-2 font-serif text-xs leading-relaxed text-parchment-dark">
                  <p v-if="chapter.objective"><span class="font-bold text-parchment">Objectif.</span> {{ chapter.objective }}</p>
                  <p v-if="chapter.stakes"><span class="font-bold text-parchment">Enjeux.</span> {{ chapter.stakes }}</p>
                  <p v-if="chapter.initial_state"><span class="font-bold text-parchment">État initial.</span> {{ chapter.initial_state }}</p>
                </div>
                <div class="mt-3 grid gap-2 md:grid-cols-2">
                  <div
                    v-if="asList(chapter.secrets).length"
                    class="rounded border border-blood/20 bg-blood/10 p-2"
                  >
                    <div class="font-display text-[9px] font-bold uppercase tracking-[0.16em] text-blood-light">Secrets</div>
                    <ul class="mt-1 space-y-1 font-serif text-xs text-parchment-dark">
                      <li v-for="(secret, secretIdx) in asList(chapter.secrets)" :key="'secret-' + secretIdx">
                        {{ formatGmValue(secret) }}
                      </li>
                    </ul>
                  </div>
                  <div
                    v-if="asList(chapter.clues).length"
                    class="rounded border border-gold/20 bg-gold/10 p-2"
                  >
                    <div class="font-display text-[9px] font-bold uppercase tracking-[0.16em] text-gold">Indices</div>
                    <ul class="mt-1 space-y-1 font-serif text-xs text-parchment-dark">
                      <li v-for="(clue, clueIdx) in asList(chapter.clues)" :key="'clue-' + clueIdx">
                        {{ formatGmValue(clue) }}
                      </li>
                    </ul>
                  </div>
                  <div
                    v-if="asList(chapter.involved_npcs).length"
                    class="rounded border border-border bg-black/20 p-2"
                  >
                    <div class="font-display text-[9px] font-bold uppercase tracking-[0.16em] text-text-muted">PNJ</div>
                    <p class="mt-1 font-serif text-xs text-parchment-dark">
                      {{ asList(chapter.involved_npcs).map((npc) => formatGmValue(npc)).join(', ') }}
                    </p>
                  </div>
                  <div
                    v-if="asList(chapter.key_locations).length"
                    class="rounded border border-border bg-black/20 p-2"
                  >
                    <div class="font-display text-[9px] font-bold uppercase tracking-[0.16em] text-text-muted">Lieux</div>
                    <p class="mt-1 font-serif text-xs text-parchment-dark">
                      {{ asList(chapter.key_locations).map((place) => formatGmValue(place)).join(', ') }}
                    </p>
                  </div>
                </div>
              </div>
            </div>

            <template v-for="section in GM_SECTIONS" :key="section.key">
              <div v-if="dossierList(section.key).length" class="rounded-lg border border-border bg-surface p-4">
                <div class="text-[9px] font-bold uppercase tracking-[0.22em] text-text-muted">
                  {{ section.label }} — {{ dossierList(section.key).length }}
                </div>
                <div class="mt-3 space-y-2">
                  <div
                    v-for="(item, itemIdx) in dossierList(section.key)"
                    :key="String(section.key) + '-' + itemIdx"
                    class="rounded border border-border bg-black/20 p-2"
                  >
                    <div class="font-display text-[12px] font-bold text-parchment">
                      {{ itemTitle(item, section.label + ' ' + (itemIdx + 1)) }}
                    </div>
                    <pre
                      v-if="itemDetail(item)"
                      class="mt-1 whitespace-pre-wrap break-words font-serif text-xs leading-relaxed text-parchment-dark"
                    >{{ itemDetail(item) }}</pre>
                  </div>
                </div>
              </div>
            </template>

            <div class="rounded-lg border border-border bg-surface p-4">
              <div class="text-[9px] font-bold uppercase tracking-[0.22em] text-text-muted">JSON brut</div>
              <pre class="mt-3 max-h-80 overflow-auto whitespace-pre-wrap break-words rounded border border-border bg-black/35 p-3 font-mono text-[10px] leading-relaxed text-parchment-dark">{{ gmDossierRaw }}</pre>
            </div>
          </template>
          <button class="w-full rounded-lg border border-blood/25 bg-transparent px-4 py-2.5 font-display text-[11px] font-bold uppercase tracking-[0.12em] text-blood/70" @click="confirmDeleteId = selectedCampaign.id">
            Supprimer la chronique
          </button>
        </div>

        <div v-else-if="activeTab === 'groupe'">
          <CampaignCharacterPanel
            :session-id="currentSession?.id ?? null"
            :campaign-id="selectedCampaign.id"
          />
        </div>
      </div>

      <footer class="border-t border-border bg-black/25 px-7 py-4">
        <div class="mb-2 text-[9px] font-bold uppercase tracking-[0.22em] text-text-muted">✦ Codex de la chronique</div>
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

    <CampaignForgeModal
      v-if="showForge"
      @close="showForge = false"
      @forge-completed="handleForgeCompleted"
    />

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
      title="Supprimer cette chronique ?"
      :message="`« ${campaignToDelete.name} » sera définitivement supprimée avec ses sessions rattachées.`"
      confirm-label="Supprimer"
      tone="danger"
      @confirm="handleDelete(campaignToDelete.id)"
      @cancel="confirmDeleteId = null"
    />

    <ConfirmDialog
      v-if="campaignToReset"
      title="Réinitialiser cette chronique ?"
      :message="`« ${campaignToReset.name} » sera conservée, mais l'historique, les sauvegardes, la progression jouée et les sessions secondaires seront effacés. La session courante et les personnages repartiront du niveau de départ.`"
      confirm-label="Réinitialiser"
      tone="warning"
      icon="↺"
      :loading="isResetting"
      :persistent="isResetting"
      @confirm="handleReset(campaignToReset.id)"
      @cancel="confirmResetId = null"
    />
  </div>
</template>
