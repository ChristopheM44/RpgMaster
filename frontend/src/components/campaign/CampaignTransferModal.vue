<script setup lang="ts">
import { computed, ref } from 'vue'
import { useCampaignStore } from '../../stores/campaign'
import type {
  Campaign,
  ChronicleArchivePayload,
  ChronicleImportPreview,
  ChronicleImportResponse,
} from '../../types'

const props = defineProps<{
  mode: 'import' | 'export'
  campaign: Campaign | null
}>()

const emit = defineEmits<{
  close: []
  imported: [payload: ChronicleImportResponse]
  exported: []
}>()

const campaignStore = useCampaignStore()
const fileInput = ref<HTMLInputElement | null>(null)
const selectedFileName = ref('')
const archivePayload = ref<ChronicleArchivePayload | null>(null)
const preview = ref<ChronicleImportPreview | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const success = ref<string | null>(null)

const isImportMode = computed(() => props.mode === 'import')
const title = computed(() => (isImportMode.value ? 'Importer une chronique' : 'Exporter la chronique'))
const eyebrow = computed(() => (isImportMode.value ? 'Archive entrante' : 'Archive sortante'))
const hasConflicts = computed(() => Boolean(preview.value?.conflicts.length))
const canImport = computed(() => archivePayload.value && preview.value && !hasConflicts.value)

function triggerFilePicker() {
  fileInput.value?.click()
}

async function handleFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  error.value = null
  success.value = null
  preview.value = null
  archivePayload.value = null
  selectedFileName.value = file?.name ?? ''
  if (!file) return

  loading.value = true
  try {
    const parsed = JSON.parse(await file.text()) as ChronicleArchivePayload
    if (parsed.format !== 'rpgmaster.chronicle') {
      error.value = "Ce fichier n'est pas une archive de chronique RPGMaster."
      return
    }
    archivePayload.value = parsed
    const result = await campaignStore.previewChronicleImport(parsed)
    if (!result) {
      error.value = campaignStore.error ?? 'Archive impossible à lire.'
      return
    }
    preview.value = result
  } catch (e: unknown) {
    error.value = e instanceof SyntaxError ? 'Le fichier JSON est invalide.' : 'Lecture impossible.'
  } finally {
    loading.value = false
    input.value = ''
  }
}

async function importArchive() {
  if (!archivePayload.value || !canImport.value) return
  error.value = null
  success.value = null
  loading.value = true
  try {
    const result = await campaignStore.importChronicle(archivePayload.value)
    if (!result) {
      error.value = campaignStore.error ?? "L'import a échoué."
      return
    }
    success.value = 'Chronique importée.'
    emit('imported', result)
  } finally {
    loading.value = false
  }
}

async function exportArchive() {
  if (!props.campaign) return
  error.value = null
  success.value = null
  loading.value = true
  try {
    const blob = await campaignStore.exportChronicle(props.campaign.id)
    if (!blob) {
      error.value = campaignStore.error ?? "L'export a échoué."
      return
    }
    downloadBlob(blob, archiveFilename(props.campaign.name))
    success.value = 'Archive téléchargée.'
    emit('exported')
  } finally {
    loading.value = false
  }
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

function archiveFilename(name: string): string {
  const safe = name
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-zA-Z0-9._-]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .toLowerCase()
  return `rpgmaster-chronique-${safe || 'chronique'}.json`
}
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-50 flex items-center justify-center bg-ink/80 p-4" @click.self="emit('close')">
      <section class="relative w-full max-w-xl overflow-hidden rounded-xl border border-border-strong bg-bg-elev p-6 shadow-xl">
        <div class="pointer-events-none absolute -right-16 -top-16 h-52 w-52 rounded-full bg-ember/10 blur-3xl" />

        <header class="relative flex items-start justify-between gap-4">
          <div>
            <div class="rpg-eyebrow"><span class="rpg-sparkle">✦</span>{{ eyebrow }}</div>
            <h2 class="mt-1 font-display text-2xl font-bold text-gold">{{ title }}</h2>
          </div>
          <button
            class="h-8 w-8 rounded text-text-muted transition hover:bg-surface hover:text-parchment"
            type="button"
            aria-label="Fermer"
            @click="emit('close')"
          >
            ×
          </button>
        </header>

        <div class="relative mt-5 space-y-4">
          <div class="rounded-lg border border-gold/20 bg-gold/10 p-3 font-serif text-sm italic leading-relaxed text-parchment-dark">
            L'archive contient les notes MJ, les secrets, le canon joué, les personnages, les sessions, l'historique et les sauvegardes.
          </div>

          <template v-if="isImportMode">
            <input
              ref="fileInput"
              class="hidden"
              type="file"
              accept=".json,application/json"
              @change="handleFileChange"
            />
            <button class="rpg-btn-secondary w-full justify-center" type="button" :disabled="loading" @click="triggerFilePicker">
              Choisir une archive JSON
            </button>

            <div v-if="selectedFileName" class="rpg-card p-3">
              <div class="font-display text-[11px] font-bold uppercase tracking-[0.14em] text-text-muted">Fichier</div>
              <div class="mt-1 truncate font-mono text-xs text-parchment-dark">{{ selectedFileName }}</div>
            </div>

            <div v-if="preview" class="rpg-card space-y-3 p-4">
              <div>
                <div class="font-display text-[11px] font-bold uppercase tracking-[0.14em] text-text-muted">Chronique détectée</div>
                <div class="mt-1 font-display text-lg font-bold text-parchment">
                  {{ preview.manifest.campaign.name }}
                </div>
                <div class="font-mono text-[10px] text-text-dim">
                  {{ preview.manifest.sessions.length }} sessions · {{ preview.manifest.includes.characters }} personnages · {{ preview.manifest.includes.messages }} messages
                </div>
              </div>

              <div v-if="preview.warnings.length" class="rounded border border-gold/25 bg-gold/10 p-2 text-xs leading-relaxed text-gold">
                <p v-for="warning in preview.warnings" :key="warning">{{ warning }}</p>
              </div>

              <div v-if="hasConflicts" class="rounded border border-blood/30 bg-blood/10 p-2 text-xs leading-relaxed text-blood-light">
                <div class="font-display text-[10px] font-bold uppercase tracking-[0.14em]">Collision détectée</div>
                <p class="mt-1">
                  Cette archive existe déjà dans cette base. L'import en copie avec nouveaux IDs sera ajouté dans une version ultérieure.
                </p>
                <ul class="mt-2 max-h-24 overflow-auto font-mono text-[10px]">
                  <li v-for="conflict in preview.conflicts.slice(0, 6)" :key="conflict.kind + conflict.id">
                    {{ conflict.kind }} · {{ conflict.id }}
                  </li>
                </ul>
              </div>
            </div>

            <button
              class="rpg-btn-primary w-full justify-center"
              type="button"
              :disabled="loading || !canImport"
              @click="importArchive"
            >
              {{ loading ? 'Import...' : 'Importer la chronique' }}
            </button>
          </template>

          <template v-else>
            <div v-if="campaign" class="rpg-card p-4">
              <div class="font-display text-[11px] font-bold uppercase tracking-[0.14em] text-text-muted">Chronique</div>
              <div class="mt-1 font-display text-lg font-bold text-parchment">{{ campaign.name }}</div>
              <div class="mt-1 font-mono text-[10px] text-text-dim">
                {{ campaign.counts?.sessions ?? campaign.session_ids.length }} sessions · {{ campaign.counts?.characters ?? campaign.character_ids.length }} personnages
              </div>
            </div>

            <button
              class="rpg-btn-primary w-full justify-center"
              type="button"
              :disabled="loading || !campaign"
              @click="exportArchive"
            >
              {{ loading ? 'Export...' : "Télécharger l'archive" }}
            </button>
          </template>

          <p v-if="error" class="rounded border border-blood/30 bg-blood/10 px-3 py-2 text-sm text-blood-light">
            {{ error }}
          </p>
          <p v-if="success" class="rounded border border-teal/30 bg-teal/10 px-3 py-2 text-sm text-teal">
            {{ success }}
          </p>
        </div>
      </section>
    </div>
  </Teleport>
</template>
