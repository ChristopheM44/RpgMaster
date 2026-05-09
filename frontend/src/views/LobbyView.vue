<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useSessionStore } from '../stores/session'
import { useCharacterStore } from '../stores/character'
import type { Session } from '../types'
import ConfirmDialog from '../components/common/ConfirmDialog.vue'

const router = useRouter()
const sessionStore = useSessionStore()
const characterStore = useCharacterStore()

const newSessionName = ref('')
const confirmDeleteId = ref<string | null>(null)
const selectedId = ref<string | null>(null)

const STATUS_META: Record<string, { label: string; tone: string }> = {
  lobby:              { label: 'En attente', tone: 'rpg-tone-muted' },
  character_creation: { label: 'Création', tone: 'rpg-tone-arcane' },
  exploration:        { label: 'Exploration', tone: 'rpg-tone-green' },
  encounter_start:    { label: 'Rencontre', tone: 'rpg-tone-blood' },
  combat:             { label: 'Combat', tone: 'rpg-tone-blood' },
  encounter_end:      { label: 'Fin rencontre', tone: 'rpg-tone-gold' },
  rest:               { label: 'Repos', tone: 'rpg-tone-teal' },
  level_up:           { label: 'Montée', tone: 'rpg-tone-gold' },
  session_end:        { label: 'Terminée', tone: 'rpg-tone-dim' },
}

const FALLBACK_META = { label: 'En attente', tone: 'rpg-tone-muted' }

function statusMeta(status: string): { label: string; tone: string } {
  return STATUS_META[status] ?? FALLBACK_META
}

const PULSING = new Set(['exploration', 'combat', 'encounter_start'])

onMounted(async () => {
  await sessionStore.fetchSessions()
  if (sessionStore.sessions.length) {
    selectedId.value = sessionStore.sessions[0]!.id
  }
})

watch(selectedId, async (id) => {
  if (id) await characterStore.loadSessionCharacters(id)
}, { immediate: true })

const selectedSession = computed<Session | null>(() =>
  sessionStore.sessions.find((s) => s.id === selectedId.value) ?? null,
)

const sessionToDeleteName = computed(
  () => sessionStore.sessions.find((s) => s.id === confirmDeleteId.value)?.name ?? '',
)

async function handleCreate() {
  const name = newSessionName.value.trim()
  if (!name) return
  const session = await sessionStore.createSession(name)
  if (session) {
    newSessionName.value = ''
    router.push({ name: 'character-setup', params: { id: session.id } })
  }
}

function handleJoin(session: Session) {
  sessionStore.setCurrentSession(session)
  router.push({ name: 'game-session', params: { id: session.id } })
}

function handleAddCharacter(session: Session) {
  sessionStore.setCurrentSession(session)
  router.push({ name: 'character-setup', params: { id: session.id } })
}

async function handleDelete(id: string) {
  await sessionStore.deleteSession(id)
  confirmDeleteId.value = null
  if (selectedId.value === id) {
    selectedId.value = sessionStore.sessions[0]?.id ?? null
  }
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('fr-FR', {
    day: '2-digit', month: '2-digit', year: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}
</script>

<template>
  <div class="flex h-full min-h-0 overflow-hidden">

    <!-- ─── Colonne principale : hero + liste ───────────────────────────── -->
    <div class="flex-1 min-w-0 overflow-y-auto px-14 py-10">

      <!-- Hero -->
      <section class="mb-10">
        <div class="rpg-eyebrow mb-2">✦ Vos aventures</div>
        <h1
          class="rpg-text-main font-display text-[44px] font-bold leading-[1.05] tracking-wide mb-3"
        >Lobby</h1>
        <p
          class="rpg-text-secondary max-w-xl font-serif text-[15px] italic"
        >
          Reprenez une partie en cours, ou forgez une nouvelle légende.
          Votre Maître du Jeu IA vous y attend.
        </p>
      </section>

      <!-- Erreur globale -->
      <div
        v-if="sessionStore.error"
        class="rpg-tone-blood rpg-tone-panel mb-6 rounded-lg border px-4 py-3 text-sm"
      >⚠ {{ sessionStore.error }}</div>

      <!-- New session card -->
      <section
        class="rpg-hero-create-card mb-10 flex items-center gap-5 overflow-hidden rounded-[14px] border px-6 py-5"
      >
        <div
          class="rpg-hero-create-icon relative flex h-12 w-12 shrink-0 items-center justify-center rounded-[10px] text-[22px]"
        >✦</div>

        <div class="relative flex-1 min-w-0">
          <div class="rpg-text-main font-display text-lg font-bold">Nouvelle Partie</div>
          <div class="rpg-text-muted text-xs">
            Donnez un nom à votre campagne. Le MJ se chargera du reste.
          </div>
        </div>

        <form class="relative flex items-center gap-2" @submit.prevent="handleCreate">
          <input
            v-model="newSessionName"
            type="text"
            maxlength="100"
            placeholder="Nom de la campagne…"
            class="rpg-input w-[260px]"
          />
          <button
            type="submit"
            class="rpg-btn-primary"
            :disabled="!newSessionName.trim() || sessionStore.loading"
          >Forger ⚔</button>
        </form>
      </section>

      <!-- Section title with gradient divider -->
      <div class="mb-4 flex items-baseline gap-4">
        <h2 class="rpg-section-title shrink-0">Sessions sauvegardées</h2>
        <div class="rpg-divider flex-1 h-px" />
        <span class="rpg-text-dim font-mono text-[11px]">
          {{ sessionStore.sessions.length }} campagne{{ sessionStore.sessions.length > 1 ? 's' : '' }}
        </span>
      </div>

      <!-- Loading -->
      <div
        v-if="sessionStore.loading && sessionStore.sessions.length === 0"
        class="rpg-text-muted py-16 text-center"
      >Chargement…</div>

      <!-- Empty -->
      <div
        v-else-if="!sessionStore.loading && sessionStore.sessions.length === 0"
        class="rpg-empty-state rounded-[10px] border border-dashed py-16 text-center font-serif italic"
      >Aucune session sauvegardée. Créez votre première aventure !</div>

      <!-- Sessions list -->
      <ul v-else class="flex flex-col gap-2.5">
        <li
          v-for="session in sessionStore.sessions"
          :key="session.id"
          class="rpg-session-row flex cursor-pointer items-center gap-4 rounded-[10px] border px-4 py-3 transition"
          :class="{ 'is-selected': selectedId === session.id }"
          @click="selectedId = session.id"
        >
          <!-- Status dot -->
          <span
            class="rpg-status-dot h-2.5 w-2.5 shrink-0 rounded-full"
            :class="[statusMeta(session.status).tone, { 'rpg-pulse': PULSING.has(session.status) }]"
          />

          <!-- Name + date subtitle -->
          <div class="min-w-0 flex-1">
            <div
              class="rpg-text-main truncate font-display text-base font-bold tracking-wide"
            >{{ session.name }}</div>
            <div
              class="rpg-text-muted truncate font-serif text-[11px] italic"
            >{{ formatDate(session.updated_at) }}</div>
          </div>

          <!-- Chars count -->
          <div class="flex shrink-0 items-center gap-1 text-xs">
            <span class="rpg-text-dim">✦</span>
            <span class="rpg-text-secondary font-mono font-semibold">
              {{ session.character_count }}
            </span>
            <span class="rpg-text-muted">perso.</span>
          </div>

          <!-- Status chip -->
          <div class="shrink-0 w-[100px] text-center">
            <span
              class="rpg-chip"
              :class="statusMeta(session.status).tone"
            >{{ statusMeta(session.status).label }}</span>
          </div>

          <!-- CTA button -->
          <button
            class="rpg-join-button shrink-0 rounded-md border px-4 py-1.5 text-[11px] font-bold uppercase tracking-[0.08em] transition"
            :class="{ 'is-selected': selectedId === session.id }"
            @click.stop="handleJoin(session)"
          >{{ session.status === 'session_end' ? 'Voir →' : 'Rejoindre →' }}</button>
        </li>
      </ul>

      <p
        v-if="sessionStore.total > sessionStore.sessions.length"
        class="rpg-text-muted mt-5 text-center text-xs"
      >{{ sessionStore.sessions.length }} / {{ sessionStore.total }} sessions affichées</p>
    </div>

    <!-- ─── Panneau latéral : détail de la session sélectionnée ─────────── -->
    <aside
      class="rpg-bg-elev rpg-border hidden w-[380px] shrink-0 overflow-y-auto border-l p-6 md:block"
    >
      <template v-if="selectedSession">
        <div class="rpg-eyebrow mb-2">✦ Aperçu</div>
        <h2
          class="rpg-text-main mb-1 font-display text-[24px] font-bold leading-[1.1] tracking-wide"
        >{{ selectedSession.name }}</h2>
        <p
          class="rpg-text-secondary mb-5 font-serif text-sm italic"
        >{{ statusMeta(selectedSession.status).label }}</p>

        <!-- Info block -->
        <div
          class="rpg-info-block mb-5 rounded-lg border p-3"
        >
          <div
            class="rpg-detail-row flex items-center justify-between border-b py-2 text-xs"
          >
            <span class="rpg-text-muted">Statut</span>
            <span
              class="font-bold uppercase tracking-[0.1em] text-[11px]"
              :class="[statusMeta(selectedSession.status).tone, 'rpg-tone-text']"
            >{{ statusMeta(selectedSession.status).label }}</span>
          </div>
          <div
            class="rpg-detail-row flex items-center justify-between border-b py-2 text-xs"
          >
            <span class="rpg-text-muted">Dernière modif.</span>
            <span class="rpg-text-main font-mono font-semibold">
              {{ formatDate(selectedSession.updated_at) }}
            </span>
          </div>
          <div class="flex items-center justify-between py-2 text-xs">
            <span class="rpg-text-muted">Personnages</span>
            <span class="rpg-text-main font-mono font-semibold">
              {{ selectedSession.character_count }}
            </span>
          </div>
        </div>

        <!-- Groupe (characters) -->
        <div class="mb-5">
          <div
            class="rpg-text-muted mb-2.5 font-mono text-[10px] font-bold uppercase tracking-[0.2em]"
          >Groupe</div>

          <div v-if="characterStore.sessionCharacters.length" class="flex flex-col gap-1.5">
            <div
              v-for="ch in characterStore.sessionCharacters"
              :key="ch.id"
              class="rpg-mini-panel flex items-center gap-2.5 rounded-md border px-2.5 py-2"
            >
              <!-- Avatar -->
              <div
                class="flex h-7 w-7 shrink-0 items-center justify-center rounded-md font-display text-[13px] font-bold"
                :class="ch.is_ai ? 'rpg-avatar-ai' : 'rpg-avatar-player'"
              >{{ ch.name.charAt(0).toUpperCase() }}</div>

              <!-- Info -->
              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-1.5">
                  <span
                    class="rpg-text-main truncate font-display text-xs font-semibold"
                  >{{ ch.name }}</span>
                  <span
                    v-if="ch.is_ai"
                    class="rpg-text-arcane shrink-0 text-[8px] font-bold tracking-[0.1em]"
                  >IA</span>
                </div>
                <div class="rpg-text-muted text-[10px]">
                  Niv. {{ ch.level }} · {{ ch.char_class }}
                </div>
              </div>

              <!-- HP -->
              <div class="rpg-text-muted shrink-0 font-mono text-[11px]">
                {{ ch.hp_current }}<span class="rpg-text-dim">/{{ ch.hp_max }}</span>
              </div>
            </div>
          </div>

          <div
            v-else
            class="rpg-border rpg-text-muted rounded-lg border border-dashed py-4 text-center font-serif text-xs italic"
          >Aucun personnage encore</div>
        </div>

        <!-- Actions -->
        <div class="flex flex-col gap-2">
          <button
            class="rpg-btn-primary w-full justify-center"
            @click="handleJoin(selectedSession)"
          >Rejoindre la partie</button>

          <div class="flex gap-2">
            <button
              class="rpg-btn-secondary flex-1 justify-center"
              @click="handleAddCharacter(selectedSession)"
            >+ Personnage</button>
            <button class="rpg-btn-secondary flex-1 justify-center">Exporter</button>
          </div>

          <button
            class="rpg-danger-outline mt-1 rounded-md border py-2 text-[11px] font-semibold uppercase tracking-wider transition"
            @click="confirmDeleteId = selectedSession.id"
          >Supprimer la session</button>
        </div>
      </template>

      <template v-else>
        <div
          class="rpg-empty-state mt-10 rounded-lg border border-dashed p-8 text-center font-serif italic"
        >Sélectionnez une session à gauche pour en voir le détail.</div>
      </template>
    </aside>

    <!-- Confirmation de suppression -->
    <ConfirmDialog
      v-if="confirmDeleteId"
      title="Supprimer cette session ?"
      :message="`« ${sessionToDeleteName} » sera définitivement supprimée. Les personnages et l'historique seront effacés.`"
      confirm-label="Supprimer"
      tone="danger"
      @confirm="handleDelete(confirmDeleteId)"
      @cancel="confirmDeleteId = null"
    />
  </div>
</template>
