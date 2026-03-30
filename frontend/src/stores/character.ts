import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { characterApi } from '../services/api'
import type { Character } from '../types'

export const useCharacterStore = defineStore('character', () => {
  const myCharacter = ref<Character | null>(null)
  const sessionCharacters = ref<Character[]>([])
  const selectedCharacter = ref<Character | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const abilityModifier = computed(() => (score: number) => Math.floor((score - 10) / 2))

  const myAbilityModifiers = computed(() => {
    if (!myCharacter.value) return {}
    return Object.fromEntries(
      Object.entries(myCharacter.value.ability_scores).map(([k, v]) => [
        k,
        Math.floor((v - 10) / 2),
      ]),
    )
  })

  async function loadCharacter(id: string) {
    loading.value = true
    error.value = null
    try {
      myCharacter.value = await characterApi.get(id)
    } catch {
      error.value = 'Impossible de charger le personnage.'
    } finally {
      loading.value = false
    }
  }

  async function loadSessionCharacters(sessionId: string) {
    loading.value = true
    error.value = null
    try {
      const data = await characterApi.list(sessionId)
      sessionCharacters.value = data.characters
    } catch {
      error.value = 'Impossible de charger les personnages.'
    } finally {
      loading.value = false
    }
  }

  function updateHp(characterId: string, hpCurrent: number) {
    if (myCharacter.value?.id === characterId) {
      myCharacter.value = { ...myCharacter.value, hp_current: hpCurrent }
    }
    const idx = sessionCharacters.value.findIndex((c) => c.id === characterId)
    if (idx !== -1) {
      const existing = sessionCharacters.value[idx]
      sessionCharacters.value[idx] = { ...existing, hp_current: hpCurrent } as Character
    }
  }

  function setMyCharacter(character: Character) {
    myCharacter.value = character
  }

  function setSelectedCharacter(character: Character) {
    selectedCharacter.value = character
  }

  return {
    myCharacter,
    sessionCharacters,
    selectedCharacter,
    loading,
    error,
    abilityModifier,
    myAbilityModifiers,
    loadCharacter,
    loadSessionCharacters,
    updateHp,
    setMyCharacter,
    setSelectedCharacter,
  }
})
