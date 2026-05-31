<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { characterApi, pregenApi } from '../../services/api'
import type { Character, CharacterListResponse, PregenTemplate } from '../../types'
import ConfirmDialog from '../common/ConfirmDialog.vue'

const props = defineProps<{
  sessionId: string | null
  campaignId: string
}>()

const router = useRouter()

const characters = ref<Character[]>([])
const pregenTemplates = ref<PregenTemplate[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

const showPregenModal = ref(false)
const selectedPregen = ref<PregenTemplate | null>(null)
const pregenCustomName = ref('')
const addingPregen = ref(false)
const pregenError = ref<string | null>(null)

const confirmDeleteId = ref<string | null>(null)

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

function classIcon(classId: string): string {
  return CLASS_ICONS[classId] ?? '🎲'
}
function speciesLabel(s: string): string {
  return SPECIES_LABELS[s] ?? s
}
function backgroundLabel(b: string | null): string {
  if (!b) return ''
  return BACKGROUND_LABELS[b] ?? b
}

async function loadAll() {
  if (!props.sessionId) return
  loading.value = true
  error.value = null
  try {
    const fetches: [Promise<CharacterListResponse>, Promise<PregenTemplate[]>] = [
      characterApi.list(props.sessionId),
      pregenTemplates.value.length ? Promise.resolve(pregenTemplates.value) : pregenApi.list(),
    ]
    const [charsData, pregens] = await Promise.all(fetches)
    characters.value = charsData.characters
    if (!pregenTemplates.value.length) pregenTemplates.value = pregens
  } catch {
    error.value = 'Impossible de charger les personnages.'
  } finally {
    loading.value = false
  }
}

watch(
  () => props.sessionId,
  (id) => {
    if (id) loadAll()
    else characters.value = []
  },
  { immediate: true },
)

async function refreshCharacters() {
  if (!props.sessionId) return
  const data = await characterApi.list(props.sessionId)
  characters.value = data.characters
}

// ─── Pregen modal ────────────────────────────────────────────────────────────

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
  if (!selectedPregen.value || !props.sessionId) return
  addingPregen.value = true
  pregenError.value = null
  try {
    await pregenApi.create(selectedPregen.value.class_id, {
      session_id: props.sessionId,
      name: pregenCustomName.value.trim() || selectedPregen.value.name,
    })
    await refreshCharacters()
    cancelPregen()
  } catch {
    pregenError.value = "Impossible d'ajouter ce personnage. Réessayez."
  } finally {
    addingPregen.value = false
  }
}

// ─── Character actions ───────────────────────────────────────────────────────

const characterToDelete = computed(
  () => characters.value.find((c) => c.id === confirmDeleteId.value) ?? null,
)

async function deleteCharacter(id: string) {
  try {
    await characterApi.delete(id)
    characters.value = characters.value.filter((c) => c.id !== id)
    confirmDeleteId.value = null
  } catch {
    error.value = 'Impossible de supprimer le personnage.'
  }
}

async function toggleCharacterAi(char: Character) {
  try {
    const updated = await characterApi.update(char.id, { is_ai: !char.is_ai })
    const idx = characters.value.findIndex((c) => c.id === char.id)
    if (idx !== -1) characters.value[idx] = updated
  } catch {
    error.value = 'Impossible de modifier le contrôle IA du personnage.'
  }
}

function viewSheet(char: Character) {
  router.push({ name: 'character-sheet', params: { charId: char.id } })
}

function goCreateCharacter() {
  if (!props.sessionId) return
  router.push({ name: 'character-creation', params: { id: props.sessionId } })
}
</script>

<template>
  <!-- No session -->
  <div v-if="!sessionId" class="py-12 text-center">
    <p class="font-serif italic text-text-muted">Aucune session active pour cette chronique.</p>
    <p class="mt-1 font-serif text-sm italic text-text-dim">Créez une session depuis l'onglet Sessions.</p>
  </div>

  <template v-else>
    <!-- Error -->
    <p
      v-if="error"
      class="mb-4 rounded border border-blood/30 bg-blood/10 px-3 py-2 text-sm text-blood"
    >
      {{ error }}
    </p>

    <!-- Loading -->
    <div v-if="loading && !characters.length" class="py-12 text-center font-serif italic text-text-muted">
      Chargement...
    </div>

    <template v-else>
      <!-- Header -->
      <div class="mb-4 flex items-center justify-between">
        <div class="rpg-eyebrow">
          ⚔ {{ characters.length }} Aventurier{{ characters.length !== 1 ? 's' : '' }}
        </div>
        <div class="flex gap-2">
          <button class="rpg-btn-tonal tone-gold !px-3 !py-1.5 !text-[10px]" type="button" @click="openPregenModal">
            + Prétiré
          </button>
          <button class="rpg-btn-secondary !px-3 !py-1.5 !text-[10px]" type="button" @click="goCreateCharacter">
            + Créer
          </button>
        </div>
      </div>

      <!-- Empty state -->
      <div
        v-if="!characters.length"
        class="rounded-lg border border-dashed border-border-strong py-12 text-center"
      >
        <p class="font-serif italic text-text-muted">Aucun personnage dans cette session.</p>
        <p class="mt-1 font-serif text-sm text-text-dim">Ajoutez un personnage prétiré ou créez le vôtre.</p>
      </div>

      <!-- Character list -->
      <div v-else class="space-y-2">
        <div
          v-for="char in characters"
          :key="char.id"
          class="rpg-card flex items-center gap-3 p-3"
        >
          <span class="shrink-0 text-2xl">{{ classIcon(char.char_class) }}</span>

          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2">
              <span class="font-display text-[13px] font-bold tracking-wide text-parchment">{{ char.name }}</span>
              <span
                class="rpg-chip px-1.5 py-0.5 text-[9px]"
                :class="char.is_ai ? 'rpg-tone-arcane' : 'rpg-tone-gold'"
              >{{ char.is_ai ? 'IA' : 'Joueur' }}</span>
            </div>
            <div class="font-serif text-[11px] italic text-parchment-dark">
              {{ speciesLabel(char.species) }} · Niv.&nbsp;{{ char.level }} · {{ char.char_class }}
              <span v-if="char.background"> · {{ backgroundLabel(char.background) }}</span>
            </div>
            <div class="font-mono text-[9px] text-text-dim">
              {{ char.hp_current }}/{{ char.hp_max }} PV
            </div>
          </div>

          <div class="flex shrink-0 items-center gap-1.5">
            <button
              type="button"
              class="rpg-btn-tonal !px-2 !py-1 !text-[10px]"
              :class="char.is_ai ? 'tone-arcane' : 'tone-gold'"
              :title="char.is_ai ? 'Contrôlé par l\'IA — cliquer pour joueur humain' : 'Joueur humain — cliquer pour IA'"
              @click="toggleCharacterAi(char)"
            >
              {{ char.is_ai ? '🤖 IA' : '👤 Joueur' }}
            </button>
            <button
              type="button"
              class="rpg-btn-secondary !px-2 !py-1 !text-[10px]"
              title="Consulter la fiche"
              @click="viewSheet(char)"
            >
              ◆ Fiche
            </button>
            <button
              type="button"
              class="rpg-btn-tonal tone-blood !px-2 !py-1 !text-[10px]"
              title="Retirer ce personnage"
              @click="confirmDeleteId = char.id"
            >
              ✕
            </button>
          </div>
        </div>
      </div>
    </template>
  </template>

  <!-- ─── Modal personnages prétirés ──────────────────────────────────────────── -->
  <Teleport to="body">
    <div
      v-if="showPregenModal"
      class="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/70 p-4 pt-16"
      @click.self="cancelPregen"
    >
      <div class="w-full max-w-3xl rounded-xl border border-border-strong bg-bg-elev shadow-2xl">
        <div class="flex items-center justify-between border-b border-border px-6 py-4">
          <h3 class="font-display text-lg font-bold text-parchment">Choisir un personnage prétiré</h3>
          <button
            type="button"
            class="text-text-muted transition hover:text-parchment"
            @click="cancelPregen"
          >✕</button>
        </div>

        <div class="p-6">
          <!-- Grid de classes -->
          <div v-if="!selectedPregen">
            <p class="mb-4 font-serif text-sm text-parchment-dark">
              Sélectionnez une classe pour voir les détails du personnage prétiré.
            </p>
            <div class="grid grid-cols-2 gap-3 sm:grid-cols-3">
              <button
                v-for="pregen in pregenTemplates"
                :key="pregen.class_id"
                type="button"
                class="rpg-card rounded-lg p-4 text-left transition hover:border-ember"
                @click="selectPregen(pregen)"
              >
                <div class="mb-1 flex items-center gap-2">
                  <span class="text-xl">{{ classIcon(pregen.class_id) }}</span>
                  <span class="font-display text-sm font-bold text-parchment">{{ pregen.class_name_fr }}</span>
                </div>
                <div class="font-serif text-xs text-parchment-dark">{{ pregen.name }}</div>
                <div class="mt-1 font-mono text-[9px] text-text-dim">
                  {{ speciesLabel(pregen.species) }} · {{ pregen.hp_max }} PV
                </div>
              </button>
            </div>
          </div>

          <!-- Fiche de confirmation -->
          <div v-else>
            <button
              type="button"
              class="mb-4 font-serif text-sm text-text-muted transition hover:text-parchment"
              @click="selectedPregen = null"
            >← Retour à la liste</button>

            <div class="rpg-card p-4">
              <div class="mb-3 flex items-center gap-3">
                <span class="text-3xl">{{ classIcon(selectedPregen.class_id) }}</span>
                <div>
                  <div class="font-display text-xl font-bold text-gold">{{ selectedPregen.class_name_fr }}</div>
                  <div class="font-serif text-sm text-parchment-dark">
                    {{ speciesLabel(selectedPregen.species) }} ·
                    {{ backgroundLabel(selectedPregen.background) }} ·
                    {{ selectedPregen.hp_max }} PV max
                  </div>
                </div>
              </div>

              <p class="mb-4 font-serif text-sm text-parchment-dark">{{ selectedPregen.description }}</p>

              <div class="mb-4 grid grid-cols-6 gap-2 text-center">
                <div
                  v-for="(val, key) in selectedPregen.ability_scores"
                  :key="key"
                  class="rounded border border-border bg-bg p-2"
                >
                  <div class="font-mono text-[9px] font-bold uppercase text-text-dim">{{ key }}</div>
                  <div class="font-display text-lg font-bold text-parchment">{{ val }}</div>
                  <div class="font-mono text-[9px] text-parchment-dark">
                    {{ val >= 10 ? '+' : '' }}{{ Math.floor((val - 10) / 2) }}
                  </div>
                </div>
              </div>

              <label class="mb-1 block font-display text-[11px] font-bold uppercase tracking-[0.12em] text-parchment">
                Nom du personnage
              </label>
              <input
                v-model="pregenCustomName"
                type="text"
                maxlength="100"
                :placeholder="selectedPregen.name"
                class="rpg-input mb-4 w-full"
              />

              <p v-if="pregenError" class="mb-3 text-sm text-blood">{{ pregenError }}</p>

              <div class="flex gap-3">
                <button
                  type="button"
                  class="rpg-btn-primary flex-1 justify-center"
                  :disabled="addingPregen"
                  @click="confirmPregen"
                >
                  {{ addingPregen ? 'Ajout en cours...' : 'Ajouter ce personnage' }}
                </button>
                <button
                  type="button"
                  class="rpg-btn-secondary !px-4"
                  @click="cancelPregen"
                >Annuler</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>

  <!-- ─── Confirmation suppression ───────────────────────────────────────────── -->
  <ConfirmDialog
    v-if="characterToDelete"
    title="Retirer ce personnage ?"
    :message="`« ${characterToDelete.name} » sera définitivement supprimé de cette session.`"
    confirm-label="Retirer"
    tone="danger"
    @confirm="deleteCharacter(characterToDelete.id)"
    @cancel="confirmDeleteId = null"
  />
</template>
