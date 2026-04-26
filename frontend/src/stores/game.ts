import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type {
  NarrativeEntry,
  CombatantState,
  DeathSaves,
  GridConfig,
  CombatantMovedPayload,
  SessionStatePayload,
  NarrationPayload,
  RollResultPayload,
  TurnStartPayload,
  HpChangedPayload,
  HistoryMessage,
  CombatActionPayload,
  AdventureJournal,
  Quest,
  ChronicleEntry,
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

  // ─── World state ────────────────────────────────────────────────────────────
  const adventureJournal = ref<AdventureJournal | null>(null)
  const quests = ref<Quest[]>([])
  const chronicle = ref<ChronicleEntry[]>([])

  // ─── Combat ─────────────────────────────────────────────────────────────────
  const combatants = ref<CombatantState[]>([])
  const selectedCombatantId = ref<string | null>(null)
  const gridConfig = ref<GridConfig | null>(null)

  // ─── Connection ─────────────────────────────────────────────────────────────
  const connected = ref(false)
  const error = ref<string | null>(null)
  const isProcessing = ref(false)
  const isGmThinking = ref(false)
  const thinkingCharacterIds = ref<Set<string>>(new Set())
  const seenEventIds = ref<Set<string>>(new Set())

  // ─── Computed ───────────────────────────────────────────────────────────────
  const isInCombat = computed(() => phase.value === 'combat')
  const activeCombatant = computed(() =>
    combatants.value.find((c) => c.id === currentTurnId.value) ?? null,
  )
  const isAnyAiThinking = computed(() => isGmThinking.value || thinkingCharacterIds.value.size > 0)

  // ─── Actions ────────────────────────────────────────────────────────────────
  function applyJournalUpdated(payload: { journal: AdventureJournal }) {
    adventureJournal.value = payload.journal
  }

  function applyQuestUpdated(payload: { quests: Quest[] }) {
    quests.value = payload.quests
  }

  function applyChronicleUpdated(payload: { chronicle: ChronicleEntry[] }) {
    chronicle.value = payload.chronicle
  }

  function applySessionState(payload: SessionStatePayload) {
    const prevPhase = phase.value
    phase.value = payload.phase
    turnNumber.value = payload.turn_number
    roundNumber.value = payload.round_number
    validTransitions.value = payload.valid_transitions
    if (payload.adventure_journal) adventureJournal.value = payload.adventure_journal
    if (payload.quests) quests.value = payload.quests
    if (payload.chronicle) chronicle.value = payload.chronicle

    if (payload.turn_order.length > 0) {
      const idx = payload.current_turn_index
      currentTurnId.value = payload.turn_order[idx]?.id ?? null
      const turnById = new Map(payload.turn_order.map((entry) => [entry.id, entry]))
      combatants.value = combatants.value.map((combatant) => {
        const entry = turnById.get(combatant.id)
        if (!entry) return combatant
        const isAiControlled = Boolean(entry.is_ai_controlled ?? entry.is_ai)
        return {
          ...combatant,
          is_ai: combatant.kind === 'pc' ? isAiControlled : combatant.is_ai,
          is_ai_controlled: combatant.kind === 'pc' ? isAiControlled : false,
          is_active: combatant.id === currentTurnId.value,
        }
      })
    }

    // Only log when phase actually changes (avoids spam on turn-end broadcasts)
    if (prevPhase !== payload.phase) {
      addSystemEntry(`Phase : ${payload.phase}`)
    }
  }

  function addNarration(payload: NarrationPayload) {
    isProcessing.value = false
    isGmThinking.value = false
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

  function addCombatAction(payload: CombatActionPayload) {
    narrativeLog.value.push({
      id: crypto.randomUUID(),
      type: 'combat_action',
      combatAction: payload,
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
    selectedCombatantId.value = payload.combatant_id
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
    if (newPhase !== 'combat') {
      combatants.value = []
      selectedCombatantId.value = null
    }
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
    const active = list.find((c) => c.is_active)
    const stillExists = list.some((c) => c.id === selectedCombatantId.value)
    if (!selectedCombatantId.value || !stillExists) {
      selectedCombatantId.value = active?.id ?? list[0]?.id ?? null
    }
  }

  function setSelectedCombatant(id: string | null) {
    selectedCombatantId.value = id
  }

  function setGridConfig(config: GridConfig) {
    gridConfig.value = config
  }

  function moveCombatant(payload: CombatantMovedPayload) {
    const idx = combatants.value.findIndex((c) => c.id === payload.combatant_id)
    if (idx !== -1) {
      combatants.value[idx] = { ...combatants.value[idx]!, position: payload.position } as CombatantState
    }
  }

  function applyHpChanged(payload: HpChangedPayload) {
    const idx = combatants.value.findIndex((c) => c.id === payload.combatant_id)
    if (idx !== -1) {
      const existing = combatants.value[idx]
      combatants.value[idx] = { ...existing, hp_current: payload.hp } as CombatantState
    }
  }

  function applyConditionChanged(combatantId: string, condition: string, added: boolean) {
    const idx = combatants.value.findIndex((c) => c.id === combatantId)
    if (idx !== -1) {
      const existing = combatants.value[idx]!
      const conditions = added
        ? [...new Set([...existing.conditions, condition])]
        : existing.conditions.filter((c) => c !== condition)
      combatants.value[idx] = { ...existing, conditions }
    }
  }

  function applyDeathSaveUpdated(combatantId: string, deathSaves: DeathSaves) {
    const idx = combatants.value.findIndex((c) => c.id === combatantId)
    if (idx !== -1) {
      combatants.value[idx] = { ...combatants.value[idx]!, death_saves: deathSaves }
    }
  }

  function setConnected(val: boolean) {
    connected.value = val
    if (!val) addSystemEntry('Déconnecté du serveur.')
  }

  function setError(msg: string | null) {
    isProcessing.value = false
    isGmThinking.value = false
    error.value = msg
    if (msg) addSystemEntry(`Erreur : ${msg}`)
  }

  function setProcessing(val: boolean) {
    isProcessing.value = val
  }

  function applyAiThinking(payload: { agent_kind: 'gm' | 'player_ai'; thinking: boolean; character_id?: string }) {
    if (payload.agent_kind === 'gm') {
      isGmThinking.value = payload.thinking
      if (payload.thinking) {
        isProcessing.value = true
      }
      return
    }

    if (!payload.character_id) return

    const next = new Set(thinkingCharacterIds.value)
    if (payload.thinking) {
      next.add(payload.character_id)
    } else {
      next.delete(payload.character_id)
    }
    thinkingCharacterIds.value = next
  }

  function isCharacterThinking(characterId?: string | null): boolean {
    if (!characterId) return false
    return thinkingCharacterIds.value.has(characterId)
  }

  function consumeEventId(eventId?: string): boolean {
    if (!eventId) return true
    if (seenEventIds.value.has(eventId)) return false
    seenEventIds.value.add(eventId)
    return true
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
    selectedCombatantId.value = null
    gridConfig.value = null
    phase.value = 'lobby'
    currentTurnId.value = null
    connected.value = false
    error.value = null
    isProcessing.value = false
    isGmThinking.value = false
    thinkingCharacterIds.value = new Set()
    seenEventIds.value = new Set()
    adventureJournal.value = null
    quests.value = []
    chronicle.value = []
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
    selectedCombatantId,
    gridConfig,
    adventureJournal,
    quests,
    chronicle,
    connected,
    error,
    isProcessing,
    isGmThinking,
    isAnyAiThinking,
    isInCombat,
    activeCombatant,
    applyJournalUpdated,
    applyQuestUpdated,
    applyChronicleUpdated,
    applySessionState,
    addNarration,
    addRollResult,
    addSystemEntry,
    addCombatAction,
    addPlayerEntry,
    applyTurnStart,
    applyPhaseChange,
    updateCombatant,
    setCombatants,
    setSelectedCombatant,
    setGridConfig,
    moveCombatant,
    applyHpChanged,
    applyConditionChanged,
    applyDeathSaveUpdated,
    setConnected,
    setError,
    setProcessing,
    applyAiThinking,
    isCharacterThinking,
    consumeEventId,
    restoreHistory,
    reset,
  }
})
