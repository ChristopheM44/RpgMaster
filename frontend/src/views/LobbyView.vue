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

const STATUS_META: Record<string, { label: string; color: string; bg: string }> = {
  lobby:               { label: 'En attente',    color: 'var(--color-text-muted)', bg: 'rgba(247,236,208,0.05)' },
  character_creation:  { label: 'Création',       color: 'var(--color-arcane)',    bg: 'rgba(192,144,255,0.10)' },
  exploration:         { label: 'Exploration',    color: 'var(--color-green)',     bg: 'rgba(111,217,111,0.10)' },
  encounter_start:     { label: 'Rencontre',      color: 'var(--color-blood)',     bg: 'rgba(232,69,69,0.10)' },
  combat:              { label: 'Combat',         color: 'var(--color-blood)',     bg: 'rgba(232,69,69,0.12)' },
  encounter_end:       { label: 'Fin rencontre',  color: 'var(--color-gold)',      bg: 'rgba(240,199,100,0.10)' },
  rest:                { label: 'Repos',          color: 'var(--color-teal)',      bg: 'rgba(79,216,192,0.10)' },
  level_up:            { label: 'Montée',         color: 'var(--color-gold)',      bg: 'rgba(240,199,100,0.12)' },
  session_end:         { label: 'Terminée',       color: 'var(--color-text-dim)',  bg: 'rgba(247,236,208,0.03)' },
}

const FALLBACK_META = { label: 'En attente', color: 'var(--color-text-muted)', bg: 'rgba(247,236,208,0.05)' }

function statusMeta(status: string): { label: string; color: string; bg: string } {
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
          class="font-display text-[44px] font-bold leading-[1.05] tracking-wide mb-3"
          :style="{ color: 'var(--color-parchment)' }"
        >Lobby</h1>
        <p
          class="max-w-xl font-serif text-[15px] italic"
          :style="{ color: 'var(--color-parchment-dark)' }"
        >
          Reprenez une partie en cours, ou forgez une nouvelle légende.
          Votre Maître du Jeu IA vous y attend.
        </p>
      </section>

      <!-- Erreur globale -->
      <div
        v-if="sessionStore.error"
        class="mb-6 rounded-lg border px-4 py-3 text-sm"
        :style="{
          borderColor: 'rgba(232,69,69,0.4)',
          background: 'rgba(232,69,69,0.1)',
          color: 'var(--color-blood-light)',
        }"
      >⚠ {{ sessionStore.error }}</div>

      <!-- New session card -->
      <section
        class="mb-10 flex items-center gap-5 overflow-hidden rounded-[14px] border px-6 py-5"
        :style="{
          borderColor: 'var(--color-border-strong)',
          background: 'linear-gradient(135deg, rgba(255,130,71,0.08), rgba(240,199,100,0.04))',
          position: 'relative',
        }"
      >
        <div
          aria-hidden="true"
          class="pointer-events-none absolute"
          :style="{
            top: '-60px', right: '-30px',
            width: '180px', height: '180px', borderRadius: '90px',
            background: 'radial-gradient(circle, rgba(255,130,71,0.20), transparent 70%)',
          }"
        />
        <div
          class="relative flex h-12 w-12 shrink-0 items-center justify-center rounded-[10px] text-[22px]"
          :style="{
            background: 'linear-gradient(135deg, var(--color-ember), var(--color-gold))',
            color: 'var(--color-bg)',
            boxShadow: '0 0 24px rgba(255,130,71,0.3)',
          }"
        >✦</div>

        <div class="relative flex-1 min-w-0">
          <div
            class="font-display text-lg font-bold"
            :style="{ color: 'var(--color-parchment)' }"
          >Nouvelle Partie</div>
          <div class="text-xs" :style="{ color: 'var(--color-text-muted)' }">
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
        <div
          class="flex-1 h-px"
          :style="{ background: 'linear-gradient(90deg, var(--color-border-strong), transparent)' }"
        />
        <span class="font-mono text-[11px]" :style="{ color: 'var(--color-text-dim)' }">
          {{ sessionStore.sessions.length }} campagne{{ sessionStore.sessions.length > 1 ? 's' : '' }}
        </span>
      </div>

      <!-- Loading -->
      <div
        v-if="sessionStore.loading && sessionStore.sessions.length === 0"
        class="py-16 text-center"
        :style="{ color: 'var(--color-text-muted)' }"
      >Chargement…</div>

      <!-- Empty -->
      <div
        v-else-if="!sessionStore.loading && sessionStore.sessions.length === 0"
        class="rounded-[10px] border border-dashed py-16 text-center font-serif italic"
        :style="{
          borderColor: 'var(--color-border-strong)',
          color: 'var(--color-text-muted)',
        }"
      >Aucune session sauvegardée. Créez votre première aventure !</div>

      <!-- Sessions list -->
      <ul v-else class="flex flex-col gap-2.5">
        <li
          v-for="session in sessionStore.sessions"
          :key="session.id"
          class="flex cursor-pointer items-center gap-4 rounded-[10px] border px-4 py-3 transition"
          :style="{
            borderColor: selectedId === session.id ? 'var(--color-ember)' : 'var(--color-border)',
            background: selectedId === session.id
              ? 'linear-gradient(90deg, rgba(255,130,71,0.10), var(--color-surface))'
              : 'var(--color-surface)',
            boxShadow: selectedId === session.id ? '0 0 20px rgba(255,130,71,0.12)' : 'none',
          }"
          @click="selectedId = session.id"
        >
          <!-- Status dot -->
          <span
            class="h-2.5 w-2.5 shrink-0 rounded-full"
            :class="{ 'rpg-pulse': PULSING.has(session.status) }"
            :style="{
              background: statusMeta(session.status).color,
              boxShadow: PULSING.has(session.status)
                ? '0 0 8px ' + statusMeta(session.status).color
                : 'none',
            }"
          />

          <!-- Name + date subtitle -->
          <div class="min-w-0 flex-1">
            <div
              class="truncate font-display text-base font-bold tracking-wide"
              :style="{ color: 'var(--color-parchment)' }"
            >{{ session.name }}</div>
            <div
              class="truncate font-serif text-[11px] italic"
              :style="{ color: 'var(--color-text-muted)' }"
            >{{ formatDate(session.updated_at) }}</div>
          </div>

          <!-- Chars count -->
          <div class="flex shrink-0 items-center gap-1 text-xs">
            <span :style="{ color: 'var(--color-text-dim)' }">✦</span>
            <span class="font-mono font-semibold" :style="{ color: 'var(--color-parchment-dark)' }">
              {{ session.character_count }}
            </span>
            <span :style="{ color: 'var(--color-text-muted)' }">perso.</span>
          </div>

          <!-- Status chip -->
          <div class="shrink-0 w-[100px] text-center">
            <span
              class="rpg-chip"
              :style="{
                color: statusMeta(session.status).color,
                background: statusMeta(session.status).bg,
                borderColor: statusMeta(session.status).color + '40',
              }"
            >{{ statusMeta(session.status).label }}</span>
          </div>

          <!-- CTA button -->
          <button
            class="shrink-0 rounded-md border px-4 py-1.5 text-[11px] font-bold uppercase tracking-[0.08em] transition"
            :style="selectedId === session.id ? {
              background: 'linear-gradient(135deg, var(--color-ember), var(--color-gold))',
              border: 'none',
              color: 'var(--color-bg)',
              boxShadow: '0 2px 12px rgba(255,130,71,0.3)',
            } : {
              background: 'transparent',
              borderColor: 'var(--color-border-strong)',
              color: 'var(--color-gold)',
            }"
            @click.stop="handleJoin(session)"
          >{{ session.status === 'session_end' ? 'Voir →' : 'Rejoindre →' }}</button>
        </li>
      </ul>

      <p
        v-if="sessionStore.total > sessionStore.sessions.length"
        class="mt-5 text-center text-xs"
        :style="{ color: 'var(--color-text-muted)' }"
      >{{ sessionStore.sessions.length }} / {{ sessionStore.total }} sessions affichées</p>
    </div>

    <!-- ─── Panneau latéral : détail de la session sélectionnée ─────────── -->
    <aside
      class="hidden w-[380px] shrink-0 overflow-y-auto border-l p-6 md:block"
      :style="{
        borderColor: 'var(--color-border)',
        background: 'var(--color-bg-elev)',
      }"
    >
      <template v-if="selectedSession">
        <div class="rpg-eyebrow mb-2">✦ Aperçu</div>
        <h2
          class="mb-1 font-display text-[24px] font-bold leading-[1.1] tracking-wide"
          :style="{ color: 'var(--color-parchment)' }"
        >{{ selectedSession.name }}</h2>
        <p
          class="mb-5 font-serif text-sm italic"
          :style="{ color: 'var(--color-parchment-dark)' }"
        >{{ statusMeta(selectedSession.status).label }}</p>

        <!-- Info block -->
        <div
          class="mb-5 rounded-lg border p-3"
          :style="{
            borderColor: 'var(--color-border)',
            background: 'var(--color-surface)',
          }"
        >
          <div
            class="flex items-center justify-between border-b py-2 text-xs"
            :style="{ borderColor: 'var(--color-border)' }"
          >
            <span :style="{ color: 'var(--color-text-muted)' }">Statut</span>
            <span
              class="font-bold uppercase tracking-[0.1em] text-[11px]"
              :style="{ color: statusMeta(selectedSession.status).color }"
            >{{ statusMeta(selectedSession.status).label }}</span>
          </div>
          <div
            class="flex items-center justify-between border-b py-2 text-xs"
            :style="{ borderColor: 'var(--color-border)' }"
          >
            <span :style="{ color: 'var(--color-text-muted)' }">Dernière modif.</span>
            <span class="font-mono font-semibold" :style="{ color: 'var(--color-parchment)' }">
              {{ formatDate(selectedSession.updated_at) }}
            </span>
          </div>
          <div class="flex items-center justify-between py-2 text-xs">
            <span :style="{ color: 'var(--color-text-muted)' }">Personnages</span>
            <span class="font-mono font-semibold" :style="{ color: 'var(--color-parchment)' }">
              {{ selectedSession.character_count }}
            </span>
          </div>
        </div>

        <!-- Groupe (characters) -->
        <div class="mb-5">
          <div
            class="mb-2.5 font-mono text-[10px] font-bold uppercase tracking-[0.2em]"
            :style="{ color: 'var(--color-text-muted)' }"
          >Groupe</div>

          <div v-if="characterStore.sessionCharacters.length" class="flex flex-col gap-1.5">
            <div
              v-for="ch in characterStore.sessionCharacters"
              :key="ch.id"
              class="flex items-center gap-2.5 rounded-md border px-2.5 py-2"
              :style="{
                background: 'var(--color-surface)',
                borderColor: 'var(--color-border)',
              }"
            >
              <!-- Avatar -->
              <div
                class="flex h-7 w-7 shrink-0 items-center justify-center rounded-md font-display text-[13px] font-bold"
                :style="{
                  background: ch.is_ai
                    ? 'linear-gradient(135deg, var(--color-arcane), #7050b0)'
                    : 'linear-gradient(135deg, var(--color-ember), var(--color-gold))',
                  color: 'var(--color-bg)',
                }"
              >{{ ch.name.charAt(0).toUpperCase() }}</div>

              <!-- Info -->
              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-1.5">
                  <span
                    class="truncate font-display text-xs font-semibold"
                    :style="{ color: 'var(--color-parchment)' }"
                  >{{ ch.name }}</span>
                  <span
                    v-if="ch.is_ai"
                    class="shrink-0 text-[8px] font-bold tracking-[0.1em]"
                    :style="{ color: 'var(--color-arcane)' }"
                  >IA</span>
                </div>
                <div class="text-[10px]" :style="{ color: 'var(--color-text-muted)' }">
                  Niv. {{ ch.level }} · {{ ch.char_class }}
                </div>
              </div>

              <!-- HP -->
              <div class="shrink-0 font-mono text-[11px]" :style="{ color: 'var(--color-text-muted)' }">
                {{ ch.hp_current }}<span :style="{ color: 'var(--color-text-dim)' }">/{{ ch.hp_max }}</span>
              </div>
            </div>
          </div>

          <div
            v-else
            class="rounded-lg border border-dashed py-4 text-center font-serif text-xs italic"
            :style="{
              borderColor: 'var(--color-border)',
              color: 'var(--color-text-muted)',
            }"
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
            class="mt-1 rounded-md border py-2 text-[11px] font-semibold uppercase tracking-wider transition"
            :style="{
              borderColor: 'rgba(232,69,69,0.25)',
              color: 'rgba(232,69,69,0.7)',
            }"
            @click="confirmDeleteId = selectedSession.id"
          >Supprimer la session</button>
        </div>
      </template>

      <template v-else>
        <div
          class="mt-10 rounded-lg border border-dashed p-8 text-center font-serif italic"
          :style="{
            borderColor: 'var(--color-border-strong)',
            color: 'var(--color-text-muted)',
          }"
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
