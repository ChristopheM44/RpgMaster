<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useSessionStore } from '../stores/session'
import type { Session } from '../types'

const router = useRouter()
const sessionStore = useSessionStore()

const newSessionName = ref('')
const confirmDeleteId = ref<string | null>(null)

const STATUS_LABELS: Record<string, string> = {
  lobby: 'En attente',
  character_creation: 'Création',
  exploration: 'Exploration',
  encounter_start: 'Rencontre',
  combat: 'Combat',
  encounter_end: 'Fin de rencontre',
  rest: 'Repos',
  level_up: 'Montée de niveau',
  session_end: 'Terminée',
}

const STATUS_COLORS: Record<string, string> = {
  lobby: 'border-stone text-parchment-dark',
  character_creation: 'border-arcane text-arcane-light',
  exploration: 'border-forest text-forest-light',
  encounter_start: 'border-blood text-blood-light',
  combat: 'border-blood text-blood-light',
  encounter_end: 'border-gold text-gold',
  rest: 'border-forest text-forest-light',
  level_up: 'border-gold text-gold-light',
  session_end: 'border-stone text-stone-light',
}

onMounted(() => {
  sessionStore.fetchSessions()
})

async function handleCreate() {
  const name = newSessionName.value.trim()
  if (!name) return
  const session = await sessionStore.createSession(name)
  if (session) {
    newSessionName.value = ''
    router.push({ name: 'character-setup', params: { id: session.id } })
  }
}

async function handleJoin(session: Session) {
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
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}
</script>

<template>
  <div class="mx-auto max-w-4xl px-6 py-10">
    <!-- Titre -->
    <div class="mb-10 flex items-start justify-between">
      <div>
        <h1 class="mb-2 text-4xl font-bold text-gold">Lobby</h1>
        <p class="text-parchment-dark">
          Créez une nouvelle session ou reprenez une partie en cours.
        </p>
      </div>
      <button
        class="rounded border border-gold/30 bg-gold/10 px-4 py-2 text-sm font-semibold text-gold transition hover:bg-gold/20"
        @click="router.push({ name: 'campaigns' })"
      >
        ⚔ Campagnes
      </button>
    </div>

    <!-- Erreur globale -->
    <div
      v-if="sessionStore.error"
      class="mb-6 rounded border border-blood bg-blood/10 px-4 py-3 text-blood-light"
    >
      {{ sessionStore.error }}
    </div>

    <!-- Section : Nouvelle session -->
    <section class="mb-10 rounded-lg border border-stone bg-ink-light p-6">
      <h2 class="mb-4 text-xl font-semibold text-parchment">Nouvelle Partie</h2>
      <form class="flex gap-3" @submit.prevent="handleCreate">
        <input
          v-model="newSessionName"
          type="text"
          placeholder="Nom de la session..."
          maxlength="100"
          class="flex-1 rounded border border-stone bg-ink px-4 py-2 text-parchment placeholder-stone-light outline-none transition focus:border-gold"
        />
        <button
          type="submit"
          :disabled="!newSessionName.trim() || sessionStore.loading"
          class="rounded bg-blood px-5 py-2 font-display font-semibold text-parchment transition hover:bg-blood-light disabled:cursor-not-allowed disabled:opacity-50"
        >
          Créer
        </button>
      </form>
    </section>

    <!-- Section : Sessions sauvegardées -->
    <section>
      <h2 class="mb-4 text-xl font-semibold text-parchment">Sessions Sauvegardées</h2>

      <!-- Chargement -->
      <div
        v-if="sessionStore.loading && sessionStore.sessions.length === 0"
        class="py-12 text-center text-parchment-dark"
      >
        Chargement...
      </div>

      <!-- Aucune session -->
      <div
        v-else-if="!sessionStore.loading && sessionStore.sessions.length === 0"
        class="rounded-lg border border-dashed border-stone py-12 text-center text-parchment-dark"
      >
        Aucune session sauvegardée. Créez votre première aventure !
      </div>

      <!-- Liste des sessions -->
      <ul v-else class="space-y-3">
        <li
          v-for="session in sessionStore.sessions"
          :key="session.id"
          class="flex items-center justify-between rounded-lg border border-stone bg-ink-light px-5 py-4 transition hover:border-gold/50"
        >
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-3">
              <span class="truncate font-display text-lg font-semibold text-parchment">
                {{ session.name }}
              </span>
              <span
                :class="[
                  'shrink-0 rounded border px-2 py-0.5 text-xs font-medium',
                  STATUS_COLORS[session.status] ?? 'border-stone text-parchment-dark',
                ]"
              >
                {{ STATUS_LABELS[session.status] ?? session.status }}
              </span>
            </div>
            <p class="mt-1 text-xs text-stone-light">
              Modifiée le {{ formatDate(session.updated_at) }}
            </p>
          </div>

          <div class="ml-4 flex shrink-0 items-center gap-2">
            <!-- Confirmation de suppression -->
            <template v-if="confirmDeleteId === session.id">
              <span class="text-sm text-parchment-dark">Confirmer ?</span>
              <button
                class="rounded border border-blood px-3 py-1 text-sm text-blood-light transition hover:bg-blood hover:text-parchment"
                @click="handleDelete(session.id)"
              >
                Oui
              </button>
              <button
                class="rounded border border-stone px-3 py-1 text-sm text-parchment-dark transition hover:border-gold hover:text-parchment"
                @click="confirmDeleteId = null"
              >
                Non
              </button>
            </template>

            <template v-else>
              <button
                v-if="session.status === 'lobby' || session.status === 'character_creation'"
                class="rounded border border-arcane/60 px-3 py-1 font-display text-sm text-arcane transition hover:bg-arcane/10"
                @click="handleAddCharacter(session)"
              >
                + Perso
              </button>
              <button
                class="rounded border border-gold px-4 py-1 font-display text-sm text-gold transition hover:bg-gold hover:text-ink"
                @click="handleJoin(session)"
              >
                {{ session.status === 'session_end' ? 'Voir' : 'Rejoindre' }}
              </button>
              <button
                class="rounded border border-stone px-3 py-1 text-sm text-stone-light transition hover:border-blood hover:text-blood-light"
                @click="confirmDeleteId = session.id"
              >
                Supprimer
              </button>
            </template>
          </div>
        </li>
      </ul>

      <p
        v-if="sessionStore.total > sessionStore.sessions.length"
        class="mt-4 text-center text-sm text-parchment-dark"
      >
        {{ sessionStore.sessions.length }} / {{ sessionStore.total }} sessions affichées
      </p>
    </section>
  </div>
</template>
