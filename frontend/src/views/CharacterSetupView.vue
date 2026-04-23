<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { characterApi, pregenApi, gameApi, sessionApi } from '../services/api'
import type { Character, PregenTemplate, Session } from '../types'
import AdventureStartModal from '../components/ui/AdventureStartModal.vue'

const route = useRoute()
const router = useRouter()
const sessionId = route.params.id as string
const backRoute = (route.query.back as string) ?? 'lobby'

// ─── State ────────────────────────────────────────────────────────────────────

const session = ref<Session | null>(null)
const characters = ref<Character[]>([])
const pregenTemplates = ref<PregenTemplate[]>([])

const loadingSession = ref(false)
const loadingChars = ref(false)
const loadingPregens = ref(false)
const startingGame = ref(false)

const errorMsg = ref<string | null>(null)

// Modal prétiré
const showStartModal = ref(false)
const showPregenModal = ref(false)
const selectedPregen = ref<PregenTemplate | null>(null)
const pregenCustomName = ref('')
const addingPregen = ref(false)
const pregenError = ref<string | null>(null)

// ─── Computed ─────────────────────────────────────────────────────────────────

const canStart = computed(() => characters.value.length > 0)
const isLoading = computed(() => loadingSession.value || loadingChars.value || loadingPregens.value)

const CLASS_ICONS: Record<string, string> = {
  fighter: '⚔',
  barbarian: '🪓',
  paladin: '🛡',
  ranger: '🏹',
  rogue: '🗡',
  monk: '👊',
  wizard: '📖',
  sorcerer: '✨',
  warlock: '🌑',
  cleric: '☀',
  druid: '🌿',
  bard: '🎵',
}

const SPECIES_LABELS: Record<string, string> = {
  human: 'Humain',
  elf: 'Elfe',
  dwarf: 'Nain',
  halfling: 'Halfelin',
  dragonborn: 'Drakéide',
  gnome: 'Gnome',
  half_elf: 'Demi-elfe',
  half_orc: 'Demi-orc',
  tiefling: 'Tieflin',
}

const BACKGROUND_LABELS: Record<string, string> = {
  acolyte: 'Acolyte',
  criminal: 'Criminel',
  folk_hero: 'Héros du Peuple',
  noble: 'Noble',
  sage: 'Sage',
  soldier: 'Soldat',
}

// ─── Data loading ─────────────────────────────────────────────────────────────

async function loadAll() {
  loadingSession.value = true
  loadingChars.value = true
  loadingPregens.value = true
  errorMsg.value = null

  try {
    const [sessionData, charsData, pregens] = await Promise.all([
      sessionApi.get(sessionId),
      characterApi.list(sessionId),
      pregenApi.list(),
    ])
    session.value = sessionData
    characters.value = charsData.characters
    pregenTemplates.value = pregens
  } catch {
    errorMsg.value = 'Impossible de charger les données de la session.'
  } finally {
    loadingSession.value = false
    loadingChars.value = false
    loadingPregens.value = false
  }
}

async function refreshCharacters() {
  loadingChars.value = true
  try {
    const data = await characterApi.list(sessionId)
    characters.value = data.characters
  } catch {
    errorMsg.value = 'Impossible de rafraîchir les personnages.'
  } finally {
    loadingChars.value = false
  }
}

onMounted(loadAll)

// ─── Pre-gen selection ────────────────────────────────────────────────────────

function openPregenModal() {
  selectedPregen.value = null
  pregenCustomName.value = ''
  pregenError.value = null
  showPregenModal.value = true
}

function selectPregen(pregen: PregenTemplate) {
  selectedPregen.value = pregen
  pregenCustomName.value = pregen.name
  pregenError.value = null
}

function cancelPregen() {
  selectedPregen.value = null
  pregenCustomName.value = ''
  pregenError.value = null
  showPregenModal.value = false
}

async function confirmPregen() {
  if (!selectedPregen.value) return
  addingPregen.value = true
  pregenError.value = null
  try {
    await pregenApi.create(selectedPregen.value.class_id, {
      session_id: sessionId,
      name: pregenCustomName.value.trim() || selectedPregen.value.name,
    })
    await refreshCharacters()
    cancelPregen()
  } catch {
    pregenError.value = 'Impossible d\'ajouter ce personnage. Réessayez.'
  } finally {
    addingPregen.value = false
  }
}

// ─── Character delete ─────────────────────────────────────────────────────────

const confirmDeleteId = ref<string | null>(null)

async function deleteCharacter(id: string) {
  try {
    await characterApi.delete(id)
    characters.value = characters.value.filter((c) => c.id !== id)
    confirmDeleteId.value = null
  } catch {
    errorMsg.value = 'Impossible de supprimer le personnage.'
  }
}

// ─── Start game ───────────────────────────────────────────────────────────────

async function startGame(mode: 'libre' | 'script' | 'auto', script?: string) {
  if (!canStart.value) return
  showStartModal.value = false
  startingGame.value = true
  errorMsg.value = null
  try {
    const body =
      mode === 'script' && script
        ? { adventure_script: script }
        : mode === 'auto'
          ? { auto_generate: true }
          : undefined
    await gameApi.start(sessionId, body)
    router.push({ name: 'game-session', params: { id: sessionId } })
  } catch {
    errorMsg.value = 'Impossible de lancer la partie. Vérifiez que le backend est démarré.'
  } finally {
    startingGame.value = false
  }
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function getConMod(scores: Record<string, number>): number {
  return Math.floor((scores.con - 10) / 2)
}

function speciesLabel(s: string): string {
  return SPECIES_LABELS[s] ?? s
}

function backgroundLabel(b: string | null): string {
  if (!b) return ''
  return BACKGROUND_LABELS[b] ?? b
}

function classIcon(classId: string): string {
  return CLASS_ICONS[classId] ?? '🎲'
}
</script>

<template>
  <div class="mx-auto max-w-4xl px-6 py-10">

    <!-- En-tête -->
    <div class="mb-8 flex items-start justify-between">
      <div>
        <h1 class="mb-1 text-4xl font-bold text-gold">
          {{ session?.name ?? 'Session' }}
        </h1>
        <p class="text-parchment-dark">Constituez votre groupe avant de lancer l'aventure.</p>
      </div>
      <button
        class="rounded border border-stone/50 px-4 py-2 text-sm text-parchment-dark transition hover:border-gold hover:text-gold"
        @click="router.push({ name: backRoute })"
      >
        ← {{ backRoute === 'campaigns' ? 'Campagnes' : 'Lobby' }}
      </button>
    </div>

    <!-- Erreur globale -->
    <div
      v-if="errorMsg"
      class="mb-6 rounded border border-blood bg-blood/10 px-4 py-3 text-blood-light"
    >
      {{ errorMsg }}
    </div>

    <!-- Chargement initial -->
    <div v-if="isLoading && characters.length === 0" class="py-20 text-center text-parchment-dark">
      Chargement...
    </div>

    <template v-else>

      <!-- Personnages actuels -->
      <section class="mb-8">
        <h2 class="mb-4 text-xl font-semibold text-parchment">
          Groupe
          <span class="ml-2 text-sm font-normal text-parchment-dark">
            ({{ characters.length }} personnage{{ characters.length > 1 ? 's' : '' }})
          </span>
        </h2>

        <!-- Liste vide -->
        <div
          v-if="characters.length === 0"
          class="rounded-lg border border-dashed border-stone py-10 text-center text-parchment-dark"
        >
          Aucun personnage. Ajoutez un personnage prétiré ou créez le vôtre.
        </div>

        <!-- Cards personnages -->
        <div v-else class="grid gap-3 sm:grid-cols-2">
          <div
            v-for="char in characters"
            :key="char.id"
            class="flex items-center justify-between rounded-lg border border-stone bg-ink-light px-4 py-3"
          >
            <div class="flex items-center gap-3">
              <span class="text-2xl">{{ classIcon(char.char_class) }}</span>
              <div>
                <div class="font-semibold text-parchment">
                  {{ char.name }}
                  <span v-if="char.is_ai" class="ml-1 rounded bg-arcane/20 px-1 text-xs text-arcane-light">IA</span>
                </div>
                <div class="text-sm text-parchment-dark">
                  {{ speciesLabel(char.species) }} · Niv. {{ char.level }} · {{ char.char_class }}
                </div>
                <div class="text-xs text-stone-light">
                  {{ char.hp_max }} PV
                  <span v-if="char.background"> · {{ backgroundLabel(char.background) }}</span>
                </div>
              </div>
            </div>

            <!-- Actions -->
            <div class="flex items-center gap-2">
              <template v-if="confirmDeleteId === char.id">
                <span class="mr-1 text-xs text-blood-light">Supprimer ?</span>
                <button
                  class="rounded bg-blood px-2 py-1 text-xs text-parchment transition hover:bg-blood-light"
                  @click="deleteCharacter(char.id)"
                >
                  Oui
                </button>
                <button
                  class="rounded border border-stone px-2 py-1 text-xs text-parchment-dark transition hover:text-parchment"
                  @click="confirmDeleteId = null"
                >
                  Non
                </button>
              </template>
              <button
                v-else
                class="rounded border border-stone/50 px-2 py-1 text-xs text-parchment-dark transition hover:border-blood hover:text-blood-light"
                @click="confirmDeleteId = char.id"
              >
                Retirer
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- Actions d'ajout -->
      <section class="mb-8">
        <h2 class="mb-4 text-xl font-semibold text-parchment">Ajouter un personnage</h2>
        <div class="flex flex-wrap gap-3">
          <button
            class="rounded border border-gold/50 bg-gold/10 px-5 py-3 font-semibold text-gold transition hover:bg-gold/20"
            @click="openPregenModal"
          >
            🎲 Personnage prétiré
          </button>
          <button
            class="rounded border border-arcane/50 bg-arcane/10 px-5 py-3 font-semibold text-arcane-light transition hover:bg-arcane/20"
            @click="router.push({ name: 'character-creation', params: { id: sessionId } })"
          >
            ✏ Créer un personnage
          </button>
        </div>
      </section>

      <!-- Lancer la partie -->
      <section class="border-t border-stone pt-8">
        <button
          :disabled="!canStart || startingGame"
          class="w-full rounded-lg bg-blood py-4 text-xl font-bold text-parchment transition hover:bg-blood-light disabled:cursor-not-allowed disabled:opacity-40"
          @click="showStartModal = true"
        >
          <span v-if="startingGame">Démarrage en cours...</span>
          <span v-else-if="!canStart">Ajoutez au moins un personnage pour commencer</span>
          <span v-else>⚔ Lancer la Partie</span>
        </button>
      </section>

    </template>

    <!-- ─── Modal Personnages Prétirés ─────────────────────────────────────── -->
    <Teleport to="body">
      <div
        v-if="showPregenModal"
        class="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/70 p-4 pt-16"
        @click.self="cancelPregen"
      >
        <div class="w-full max-w-3xl rounded-xl border border-stone bg-ink shadow-2xl">

          <!-- Header modal -->
          <div class="flex items-center justify-between border-b border-stone px-6 py-4">
            <h3 class="text-xl font-bold text-gold">Choisir un personnage prétiré</h3>
            <button
              class="text-parchment-dark transition hover:text-parchment"
              @click="cancelPregen"
            >
              ✕
            </button>
          </div>

          <!-- Contenu -->
          <div class="p-6">

            <!-- Grille des classes (si aucune sélectionnée) -->
            <div v-if="!selectedPregen">
              <p class="mb-4 text-sm text-parchment-dark">
                Sélectionnez une classe pour voir les détails du personnage prétiré.
              </p>
              <div class="grid grid-cols-2 gap-3 sm:grid-cols-3">
                <button
                  v-for="pregen in pregenTemplates"
                  :key="pregen.class_id"
                  class="rounded-lg border border-stone bg-ink-light p-4 text-left transition hover:border-gold hover:bg-gold/5"
                  @click="selectPregen(pregen)"
                >
                  <div class="mb-1 flex items-center gap-2">
                    <span class="text-xl">{{ classIcon(pregen.class_id) }}</span>
                    <span class="font-semibold text-parchment">{{ pregen.class_name_fr }}</span>
                  </div>
                  <div class="text-sm text-parchment-dark">{{ pregen.name }}</div>
                  <div class="mt-1 text-xs text-stone-light">
                    {{ speciesLabel(pregen.species) }} · {{ pregen.hp_max }} PV
                  </div>
                </button>
              </div>
            </div>

            <!-- Fiche de confirmation (classe sélectionnée) -->
            <div v-else>
              <button
                class="mb-4 text-sm text-parchment-dark transition hover:text-parchment"
                @click="selectedPregen = null"
              >
                ← Retour à la liste
              </button>

              <div class="rounded-lg border border-stone bg-ink-light p-4">
                <div class="mb-3 flex items-center gap-3">
                  <span class="text-3xl">{{ classIcon(selectedPregen.class_id) }}</span>
                  <div>
                    <div class="text-xl font-bold text-gold">{{ selectedPregen.class_name_fr }}</div>
                    <div class="text-sm text-parchment-dark">
                      {{ speciesLabel(selectedPregen.species) }} ·
                      {{ backgroundLabel(selectedPregen.background) }} ·
                      {{ selectedPregen.hp_max }} PV max
                    </div>
                  </div>
                </div>

                <p class="mb-4 text-sm text-parchment-dark">{{ selectedPregen.description }}</p>

                <!-- Stats compactes -->
                <div class="mb-4 grid grid-cols-6 gap-2 text-center">
                  <div
                    v-for="(val, key) in selectedPregen.ability_scores"
                    :key="key"
                    class="rounded border border-stone bg-ink p-2"
                  >
                    <div class="text-xs font-bold uppercase text-stone-light">{{ key }}</div>
                    <div class="text-lg font-bold text-parchment">{{ val }}</div>
                    <div class="text-xs text-parchment-dark">
                      {{ val >= 10 ? '+' : '' }}{{ Math.floor((val - 10) / 2) }}
                    </div>
                  </div>
                </div>

                <!-- Champ nom -->
                <label class="mb-1 block text-sm font-semibold text-parchment">
                  Nom du personnage
                </label>
                <input
                  v-model="pregenCustomName"
                  type="text"
                  maxlength="100"
                  :placeholder="selectedPregen.name"
                  class="mb-4 w-full rounded border border-stone bg-ink px-4 py-2 text-parchment placeholder-stone-light outline-none transition focus:border-gold"
                />

                <!-- Erreur pregen -->
                <div v-if="pregenError" class="mb-3 text-sm text-blood-light">
                  {{ pregenError }}
                </div>

                <!-- Boutons -->
                <div class="flex gap-3">
                  <button
                    class="flex-1 rounded bg-blood py-2 font-semibold text-parchment transition hover:bg-blood-light disabled:opacity-50"
                    :disabled="addingPregen"
                    @click="confirmPregen"
                  >
                    {{ addingPregen ? 'Ajout en cours...' : 'Ajouter ce personnage' }}
                  </button>
                  <button
                    class="rounded border border-stone px-4 py-2 text-parchment-dark transition hover:text-parchment"
                    @click="cancelPregen"
                  >
                    Annuler
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- ─── Modal Lancement de l'aventure ────────────────────────────────────── -->
    <Teleport to="body">
      <AdventureStartModal
        v-if="showStartModal"
        @confirm="startGame"
        @cancel="showStartModal = false"
      />
    </Teleport>

  </div>
</template>
