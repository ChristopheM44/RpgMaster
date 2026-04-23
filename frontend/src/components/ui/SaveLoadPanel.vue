<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { saveApi } from '../../services/api'
import { useGameStore } from '../../stores/game'
import type { SaveSlot } from '../../types'

const props = defineProps<{ sessionId: string }>()
const emit = defineEmits<{ (e: 'load-complete'): void }>()

const gameStore = useGameStore()
const saves = ref<SaveSlot[]>([])
const saveName = ref('')
const loading = ref(false)
const error = ref<string | null>(null)
const successMsg = ref<string | null>(null)

async function fetchSaves() {
  try {
    const res = await saveApi.list(props.sessionId)
    saves.value = res.saves
  } catch {
    // silencieux
  }
}

async function createSave() {
  if (!saveName.value.trim()) return
  loading.value = true
  error.value = null
  successMsg.value = null
  try {
    await saveApi.create(props.sessionId, saveName.value.trim())
    saveName.value = ''
    successMsg.value = 'Partie sauvegardée.'
    await fetchSaves()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Erreur lors de la sauvegarde.'
  } finally {
    loading.value = false
  }
}

async function loadSave(saveId: string) {
  loading.value = true
  error.value = null
  successMsg.value = null
  try {
    await saveApi.load(props.sessionId, saveId)
    successMsg.value = 'Partie restaurée. Reconnexion en cours…'
    emit('load-complete')
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Erreur lors du chargement.'
  } finally {
    loading.value = false
  }
}

async function deleteSave(saveId: string) {
  loading.value = true
  error.value = null
  try {
    await saveApi.delete(props.sessionId, saveId)
    await fetchSaves()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Erreur lors de la suppression.'
  } finally {
    loading.value = false
  }
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    year: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

onMounted(fetchSaves)
</script>

<template>
  <div class="space-y-4">
    <!-- Nouvelle sauvegarde -->
    <div class="flex gap-2">
      <input
        v-model="saveName"
        type="text"
        placeholder="Nom de la sauvegarde…"
        maxlength="100"
        class="rpg-input flex-1 text-sm"
        @keyup.enter="createSave"
      />
      <button
        :disabled="loading || !saveName.trim()"
        class="rpg-btn-primary"
        @click="createSave"
      >
        Sauvegarder
      </button>
    </div>

    <!-- Feedback -->
    <p v-if="error" class="text-blood text-xs">{{ error }}</p>
    <p v-if="successMsg" class="text-arcane text-xs">{{ successMsg }}</p>

    <!-- Liste des sauvegardes -->
    <div v-if="saves.length === 0" class="text-parchment/40 text-xs italic">
      Aucune sauvegarde pour cette session.
    </div>

    <ul v-else class="space-y-2">
      <li
        v-for="save in saves"
        :key="save.id"
        class="rpg-card flex items-center justify-between gap-2 px-3 py-2"
      >
        <div class="flex-1 min-w-0">
          <p class="text-parchment text-sm font-medium truncate">{{ save.name }}</p>
          <p class="text-parchment/50 text-xs">
            {{ save.phase }} · Tour {{ save.turn_number }} · Round {{ save.round_number }}
            <span class="ml-2">{{ formatDate(save.created_at) }}</span>
          </p>
        </div>
        <div class="flex gap-1 shrink-0">
          <button
            :disabled="loading"
            class="rpg-btn-tonal tone-teal"
            title="Charger cette sauvegarde"
            @click="loadSave(save.id)"
          >
            Charger
          </button>
          <button
            :disabled="loading"
            class="rpg-btn-tonal tone-blood"
            title="Supprimer cette sauvegarde"
            @click="deleteSave(save.id)"
          >
            ✕
          </button>
        </div>
      </li>
    </ul>
  </div>
</template>
