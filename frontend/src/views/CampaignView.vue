<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useCampaignStore } from '../stores/campaign'
import { useSessionStore } from '../stores/session'
import type { Campaign } from '../types'

const router = useRouter()
const campaignStore = useCampaignStore()
const sessionStore = useSessionStore()

const showCreate = ref(false)
const newName = ref('')
const newDesc = ref('')
const selectedCampaign = ref<Campaign | null>(null)
const newSessionName = ref('')
const showAdvance = ref(false)
const confirmDeleteId = ref<string | null>(null)

onMounted(() => {
  campaignStore.fetchCampaigns()
})

async function handleCreate() {
  const name = newName.value.trim()
  if (!name) return
  const c = await campaignStore.createCampaign({ name, description: newDesc.value.trim() })
  if (c) {
    showCreate.value = false
    newName.value = ''
    newDesc.value = ''
  }
}

async function selectCampaign(campaign: Campaign) {
  selectedCampaign.value = await campaignStore.fetchCampaign(campaign.id)
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
    router.push({ name: 'character-setup', params: { id: result.new_session_id }, query: { back: 'campaigns' } })
  }
}

async function handleDelete(id: string) {
  await campaignStore.deleteCampaign(id)
  if (selectedCampaign.value?.id === id) selectedCampaign.value = null
  confirmDeleteId.value = null
}

function sessionLabel(campaign: Campaign, idx: number): string {
  const isCurrent = idx === campaign.current_session_index
  return `Session ${idx + 1}${isCurrent ? ' (active)' : ''}`
}
</script>

<template>
  <div class="min-h-screen bg-ink p-4 font-serif text-parchment">
    <!-- Header -->
    <div class="mx-auto max-w-4xl">
      <div class="mb-6 flex items-center justify-between">
        <div>
          <h1 class="text-2xl font-bold text-gold">Campagnes</h1>
          <p class="text-sm text-parchment/50">Enchaînez des sessions avec progression persistante</p>
        </div>
        <div class="flex gap-2">
          <button
            class="rounded border border-gold/30 px-3 py-1.5 text-sm text-parchment/70 hover:border-gold/60 hover:text-parchment transition-colors"
            @click="router.push({ name: 'lobby' })"
          >
            ← Lobby
          </button>
          <button
            class="rounded bg-gold/20 border border-gold/40 px-3 py-1.5 text-sm text-gold hover:bg-gold/30 transition-colors"
            @click="showCreate = true"
          >
            + Nouvelle campagne
          </button>
        </div>
      </div>

      <!-- Create modal -->
      <div
        v-if="showCreate"
        class="fixed inset-0 z-50 flex items-center justify-center bg-ink/80 p-4"
      >
        <div class="w-full max-w-md rounded border border-gold/30 bg-ink p-6 shadow-xl">
          <h2 class="mb-4 text-lg font-semibold text-gold">Nouvelle campagne</h2>
          <div class="space-y-3">
            <div>
              <label class="mb-1 block text-sm text-parchment/70">Nom</label>
              <input
                v-model="newName"
                class="w-full rounded border border-gold/30 bg-ink/60 px-3 py-2 text-parchment focus:border-gold/60 focus:outline-none"
                placeholder="La Chute des Rois Anciens"
                @keydown.enter="handleCreate"
              />
            </div>
            <div>
              <label class="mb-1 block text-sm text-parchment/70">Description (optionnel)</label>
              <textarea
                v-model="newDesc"
                class="w-full rounded border border-gold/30 bg-ink/60 px-3 py-2 text-parchment focus:border-gold/60 focus:outline-none"
                rows="3"
                placeholder="Une épopée qui traverse trois royaumes..."
              />
            </div>
          </div>
          <div class="mt-4 flex justify-end gap-2">
            <button
              class="rounded border border-gold/20 px-4 py-2 text-sm text-parchment/60 hover:text-parchment transition-colors"
              @click="showCreate = false"
            >
              Annuler
            </button>
            <button
              class="rounded bg-gold/20 border border-gold/40 px-4 py-2 text-sm text-gold hover:bg-gold/30 transition-colors"
              @click="handleCreate"
            >
              Créer
            </button>
          </div>
        </div>
      </div>

      <div class="grid gap-4 md:grid-cols-2">
        <!-- Campaign list -->
        <div class="space-y-2">
          <p
            v-if="!campaignStore.campaigns.length"
            class="text-center text-parchment/30 italic py-8"
          >
            Aucune campagne. Créez-en une pour commencer.
          </p>
          <div
            v-for="c in campaignStore.campaigns"
            :key="c.id"
            class="cursor-pointer rounded border p-4 transition-colors"
            :class="selectedCampaign?.id === c.id
              ? 'border-gold bg-gold/10'
              : 'border-gold/20 bg-ink/40 hover:border-gold/40'"
            @click="selectCampaign(c)"
          >
            <div class="flex items-start justify-between">
              <div class="flex-1 min-w-0">
                <h3 class="font-semibold text-parchment truncate">{{ c.name }}</h3>
                <p v-if="c.description" class="mt-0.5 text-xs text-parchment/50 line-clamp-1">
                  {{ c.description }}
                </p>
              </div>
              <button
                v-if="confirmDeleteId === c.id"
                class="ml-2 shrink-0 text-xs text-blood hover:text-blood/80"
                @click.stop="handleDelete(c.id)"
              >
                Confirmer
              </button>
              <button
                v-else
                class="ml-2 shrink-0 text-xs text-parchment/30 hover:text-blood/70"
                @click.stop="confirmDeleteId = c.id"
              >
                ✕
              </button>
            </div>
            <div class="mt-2 flex items-center gap-3 text-xs text-parchment/50">
              <span>{{ c.session_ids.length }} session{{ c.session_ids.length !== 1 ? 's' : '' }}</span>
              <span>{{ c.character_ids.length }} personnage{{ c.character_ids.length !== 1 ? 's' : '' }}</span>
            </div>
          </div>
        </div>

        <!-- Campaign detail -->
        <div v-if="selectedCampaign" class="rounded border border-gold/20 bg-ink/40 p-4">
          <h2 class="mb-1 text-lg font-semibold text-gold">{{ selectedCampaign.name }}</h2>
          <p v-if="selectedCampaign.description" class="mb-4 text-sm text-parchment/60">
            {{ selectedCampaign.description }}
          </p>

          <!-- Sessions list -->
          <div class="mb-4">
            <h3 class="mb-2 text-xs font-semibold uppercase tracking-widest text-gold/60">Sessions</h3>
            <div v-if="!selectedCampaign.session_ids.length" class="text-sm text-parchment/40 italic">
              Aucune session. Cliquez sur « Démarrer une session » ci-dessous.
            </div>
            <div v-else class="space-y-1.5">
              <div
                v-for="(sid, idx) in selectedCampaign.session_ids"
                :key="sid"
                class="flex items-center justify-between rounded border border-gold/15 bg-ink/60 px-3 py-2 text-sm"
                :class="idx === selectedCampaign.current_session_index ? 'border-gold/40 bg-gold/5' : ''"
              >
                <span :class="idx === selectedCampaign.current_session_index ? 'text-gold' : 'text-parchment/70'">
                  {{ sessionLabel(selectedCampaign, idx) }}
                </span>
                <span class="text-xs text-parchment/30 font-mono">{{ sid.slice(0, 8) }}…</span>
              </div>
            </div>
          </div>

          <!-- XP pool -->
          <div v-if="Object.keys(selectedCampaign.xp_pool).length" class="mb-4">
            <h3 class="mb-2 text-xs font-semibold uppercase tracking-widest text-gold/60">XP</h3>
            <div class="space-y-1">
              <div
                v-for="(xp, charId) in selectedCampaign.xp_pool"
                :key="charId"
                class="flex items-center justify-between text-sm"
              >
                <span class="text-parchment/60 font-mono text-xs">{{ String(charId).slice(0, 8) }}…</span>
                <span class="text-gold font-semibold">{{ xp }} XP</span>
              </div>
            </div>
          </div>

          <!-- Actions -->
          <div class="flex flex-col gap-2">
            <button
              v-if="currentSessionId(selectedCampaign)"
              class="w-full rounded bg-arcane/20 border border-arcane/40 px-4 py-2.5 text-sm font-semibold text-arcane hover:bg-arcane/30 transition-colors"
              @click="playCurrent"
            >
              ▶ Jouer la session courante
            </button>

            <button
              class="w-full rounded bg-gold/10 border border-gold/30 px-4 py-2.5 text-sm text-gold hover:bg-gold/20 transition-colors"
              @click="showAdvance = true"
            >
              {{ selectedCampaign.session_ids.length === 0 ? '+ Démarrer une session' : '→ Session suivante (transférer personnages)' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Advance modal -->
    <div
      v-if="showAdvance"
      class="fixed inset-0 z-50 flex items-center justify-center bg-ink/80 p-4"
    >
      <div class="w-full max-w-md rounded border border-gold/30 bg-ink p-6 shadow-xl">
        <h2 class="mb-2 text-lg font-semibold text-gold">Nouvelle session</h2>
        <p class="mb-4 text-sm text-parchment/60">
          Les personnages seront transférés avec leurs stats actuelles (PV restaurés).
        </p>
        <input
          v-model="newSessionName"
          class="w-full rounded border border-gold/30 bg-ink/60 px-3 py-2 text-parchment focus:border-gold/60 focus:outline-none"
          placeholder="Nom de la nouvelle session..."
          @keydown.enter="handleAdvance"
        />
        <div class="mt-4 flex justify-end gap-2">
          <button
            class="rounded border border-gold/20 px-4 py-2 text-sm text-parchment/60 hover:text-parchment transition-colors"
            @click="showAdvance = false"
          >
            Annuler
          </button>
          <button
            class="rounded bg-gold/20 border border-gold/40 px-4 py-2 text-sm text-gold hover:bg-gold/30 transition-colors"
            @click="handleAdvance"
          >
            Créer et transférer
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
