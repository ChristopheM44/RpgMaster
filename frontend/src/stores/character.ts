import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { characterApi } from '../services/api'
import type { Character, CharacterLeveledUpPayload, EquipmentItem, HitDiceState } from '../types'

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
    patchCharacter(characterId, { hp_current: hpCurrent })
  }

  function updateEquipment(characterId: string, equipment: EquipmentItem[]) {
    patchCharacter(characterId, { equipment })
  }

  function updateSpellSlots(
    characterId: string,
    spellSlots: Record<string, { total: number; used: number }>,
  ) {
    patchCharacter(characterId, { spell_slots: spellSlots })
  }

  function updateHitDice(characterId: string, hitDice: HitDiceState) {
    patchCharacter(characterId, { hit_dice: hitDice })
  }

  function updateXp(characterId: string, xp: number, level?: number, xpToNext?: number) {
    patchCharacter(characterId, {
      xp,
      ...(level !== undefined ? { level } : {}),
      ...(xpToNext !== undefined ? { xp_to_next_level: xpToNext } : {}),
    })
  }

  function updateCurrency(characterId: string, gp: number, sp: number, cp: number) {
    patchCharacter(characterId, { gp, sp, cp })
  }

  function applyLevelUp(payload: CharacterLeveledUpPayload) {
    patchCharacter(payload.character_id, {
      level: payload.new_level,
      hp_current: payload.hp,
      hp_max: payload.hp_max,
      spell_slots: payload.spell_slots,
      hit_dice: payload.hit_dice,
      pending_asi: Boolean(payload.requires_asi),
      ...(payload.xp_to_next_level !== undefined
        ? { xp_to_next_level: payload.xp_to_next_level }
        : {}),
    })
  }

  function setPendingAsi(characterId: string, value: boolean) {
    patchCharacter(characterId, { pending_asi: value })
  }

  function patchCharacter(characterId: string, patch: Partial<Character>) {
    if (myCharacter.value?.id === characterId) {
      myCharacter.value = { ...myCharacter.value, ...patch }
    }
    if (selectedCharacter.value?.id === characterId) {
      selectedCharacter.value = { ...selectedCharacter.value, ...patch }
    }
    const idx = sessionCharacters.value.findIndex((c) => c.id === characterId)
    if (idx !== -1) {
      sessionCharacters.value[idx] = { ...sessionCharacters.value[idx], ...patch } as Character
    }
  }

  function setMyCharacter(character: Character) {
    myCharacter.value = character
  }

  function setSelectedCharacter(character: Character) {
    selectedCharacter.value = character
  }

  async function toggleAiControl(characterId: string) {
    const char = sessionCharacters.value.find((c) => c.id === characterId)
    if (!char) return
    const newValue = !char.is_ai
    try {
      const updated = await characterApi.update(characterId, { is_ai: newValue })
      const idx = sessionCharacters.value.findIndex((c) => c.id === characterId)
      if (idx !== -1) sessionCharacters.value[idx] = updated
      if (selectedCharacter.value?.id === characterId) selectedCharacter.value = updated
      if (myCharacter.value?.id === characterId) myCharacter.value = updated
    } catch {
      error.value = 'Impossible de modifier le contrôle du personnage.'
    }
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
    updateEquipment,
    updateSpellSlots,
    updateHitDice,
    updateXp,
    updateCurrency,
    applyLevelUp,
    setPendingAsi,
    setMyCharacter,
    setSelectedCharacter,
    toggleAiControl,
  }
})
