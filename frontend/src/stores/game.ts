import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type {
  NarrativeEntry,
  CombatantState,
  SessionStatePayload,
  NarrationPayload,
  RollResultPayload,
  TurnStartPayload,
  HpChangedPayload,
  HistoryMessage,
} from '../types'

export const useGameStore = defineStore('game', () => {
  // ─── Session state ──────────────────────────────────────────────────────────
  const sessionId = ref<string | null>(null)
  const phase = ref<string>('lobby')
  const turnNumber = ref(0)
  const roundNumber = ref(0)
  const currentTurnId = ref<string | null>(null)
  const validTransitions = ref<string[]>([])

  // ─── Narrative log ──────────────────────────────────────────────────────────
  const narrativeLog = ref<NarrativeEntry[]>([])

  // ─── Combat ─────────────────────────────────────────────────────────────────
  const combatants = ref<CombatantState[]>([])

  // ─── Connection ─────────────────────────────────────────────────────────────
  const connected = ref(false)
  const error = ref<string | null>(null)

  // ─── Computed ───────────────────────────────────────────────────────────────
  const isInCombat = computed(() => phase.value === 'combat')
  const activeCombatant = computed(() =>
    combatants.value.find((c) => c.id === currentTurnId.value) ?? null,
  )

  // ─── Actions ────────────────────────────────────────────────────────────────
  function applySessionState(payload: SessionStatePayload) {
    const prevPhase = phase.value
    phase.value = payload.phase
    turnNumber.value = payload.turn_number
    roundNumber.value = payload.round_number
    validTransitions.value = payload.valid_transitions

    if (payload.turn_order.length > 0) {
      const idx = payload.current_turn_index
      currentTurnId.value = payload.turn_order[idx]?.id ?? null
    }

    // Only log when phase actually changes (avoids spam on turn-end broadcasts)
    if (prevPhase !== payload.phase) {
      addSystemEntry(`Phase : ${payload.phase}`)
    }
  }

  function addNarration(payload: NarrationPayload) {
    narrativeLog.value.push({
      id: crypto.randomUUID(),
      type: 'narration',
      text: payload.text,
      speaker: payload.speaker,
      timestamp: new Date().toISOString(),
    })
  }

  function addRollResult(payload: RollResultPayload) {
    narrativeLog.value.push({
      id: crypto.randomUUID(),
      type: 'roll',
      roll: payload,
      timestamp: new Date().toISOString(),
    })
  }

  function addSystemEntry(text: string) {
    narrativeLog.value.push({
      id: crypto.randomUUID(),
      type: 'system',
      text,
      timestamp: new Date().toISOString(),
    })
  }

  function addPlayerEntry(text: string, speaker?: string) {
    narrativeLog.value.push({
      id: crypto.randomUUID(),
      type: 'player',
      text,
      speaker,
      timestamp: new Date().toISOString(),
    })
  }

  function applyTurnStart(payload: TurnStartPayload) {
    currentTurnId.value = payload.combatant_id
    combatants.value = combatants.value.map((c) => ({
      ...c,
      is_active: c.id === payload.combatant_id,
    }))
    if (payload.combatant_name) {
      addSystemEntry(`Tour de ${payload.combatant_name}`)
    }
  }

  function applyPhaseChange(newPhase: string) {
    phase.value = newPhase
    if (newPhase !== 'combat') combatants.value = []
    addSystemEntry(`Phase changée → ${newPhase}`)
  }

  function updateCombatant(id: string, updates: Partial<CombatantState>) {
    const idx = combatants.value.findIndex((c) => c.id === id)
    if (idx !== -1) {
      combatants.value[idx] = { ...combatants.value[idx], ...updates } as CombatantState
    }
  }

  function setCombatants(list: CombatantState[]) {
    combatants.value = list
  }

  function applyHpChanged(payload: HpChangedPayload) {
    const idx = combatants.value.findIndex((c) => c.id === payload.combatant_id)
    if (idx !== -1) {
      const existing = combatants.value[idx]
      combatants.value[idx] = { ...existing, hp_current: payload.hp } as CombatantState
    }
  }

  function setConnected(val: boolean) {
    connected.value = val
    if (!val) addSystemEntry('Déconnecté du serveur.')
  }

  function setError(msg: string | null) {
    error.value = msg
    if (msg) addSystemEntry(`Erreur : ${msg}`)
  }

  function restoreHistory(messages: HistoryMessage[]) {
    narrativeLog.value = messages.map((m) => {
      if (m.message_type === 'roll_result' && m.metadata) {
        return {
          id: m.id,
          type: 'roll' as const,
          roll: {
            dice_notation: String(m.metadata.dice ?? ''),
            rolls: (m.metadata.rolls as number[]) ?? [],
            total: Number(m.metadata.total ?? 0),
            modifier: Number(m.metadata.modifier ?? 0),
            label: m.content,
            success: m.metadata.success as boolean | undefined,
            character_name: m.speaker,
          },
          timestamp: m.created_at,
        }
      }
      const type =
        m.role === 'system'
          ? ('system' as const)
          : m.role === 'player'
            ? ('player' as const)
            : ('narration' as const)
      return {
        id: m.id,
        type,
        text: m.content,
        speaker: m.speaker,
        timestamp: m.created_at,
      }
    })
  }

  function reset() {
    narrativeLog.value = []
    combatants.value = []
    phase.value = 'lobby'
    currentTurnId.value = null
    connected.value = false
    error.value = null
  }

  return {
    sessionId,
    phase,
    turnNumber,
    roundNumber,
    currentTurnId,
    validTransitions,
    narrativeLog,
    combatants,
    connected,
    error,
    isInCombat,
    activeCombatant,
    applySessionState,
    addNarration,
    addRollResult,
    addSystemEntry,
    addPlayerEntry,
    applyTurnStart,
    applyPhaseChange,
    updateCombatant,
    setCombatants,
    applyHpChanged,
    setConnected,
    setError,
    restoreHistory,
    reset,
  }
})
