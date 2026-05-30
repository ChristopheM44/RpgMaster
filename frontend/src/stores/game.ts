import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type {
  NarrativeEntry,
  CombatantState,
  DeathSaves,
  GridConfig,
  CombatantMovedPayload,
  ActionEconomyChangedPayload,
  SessionStatePayload,
  NarrationPayload,
  RollResultPayload,
  TurnStartPayload,
  HpChangedPayload,
  HistoryMessage,
  CombatActionPayload,
  CombatantStatusChangedPayload,
  AdventureJournal,
  Quest,
  ChronicleEntry,
  ClockUpdatedPayload,
  SceneLayout,
  SceneLayoutChangedPayload,
  GridDecoration,
  RegionMap,
  CityMap,
  RegionMapUpdatedPayload,
  CityMapUpdatedPayload,
  NodeStatus,
  ReachableCells,
} from '../types'

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function stripSpeakerPrefix(text: string, speaker?: string): string {
  const cleaned = text.trimStart()
  const speakerName = speaker?.trim()
  if (!speakerName || !cleaned) return text

  const names = [speakerName]
  const firstName = speakerName.split(/\s+/)[0]
  if (firstName && firstName !== speakerName) names.push(firstName)

  for (const name of names.sort((a, b) => b.length - a.length)) {
    const fullPrefix = new RegExp(`^${escapeRegExp(name)}\\s*(?:[:：,\\-–—]\\s*|\\s+)(.+)$`, 'i')
    const match = cleaned.match(fullPrefix)
    if (match?.[1]) return match[1]
  }
  return text
}

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
  const currentScene = ref<SceneLayout | null>(null)
  const sceneClocks = ref<ClockUpdatedPayload[]>([])
  const regionMap = ref<RegionMap | null>(null)
  const cityMaps = ref<Record<string, CityMap>>({})
  const activeCityId = ref<string | null>(null)

  // ─── Combat ─────────────────────────────────────────────────────────────────
  const combatants = ref<CombatantState[]>([])
  const selectedCombatantId = ref<string | null>(null)
  const gridConfig = ref<GridConfig | null>(null)
  const gridDecoration = ref<GridDecoration | null>(null)
  const reachableCells = ref<Record<string, ReachableCells>>({})

  // ─── Connection ─────────────────────────────────────────────────────────────
  const connected = ref(false)
  const error = ref<string | null>(null)
  const isProcessing = ref(false)
  const isGmThinking = ref(false)
  const thinkingCharacterIds = ref<Set<string>>(new Set())
  const thinkingCharacterNames = ref<Record<string, string>>({})
  const seenEventIds = ref<Set<string>>(new Set())

  // ─── Computed ───────────────────────────────────────────────────────────────
  const isInCombat = computed(() => phase.value === 'combat')
  const activeCombatant = computed(() =>
    combatants.value.find((c) => c.id === currentTurnId.value) ?? null,
  )
  const isAnyAiThinking = computed(() => isGmThinking.value || thinkingCharacterIds.value.size > 0)
  const isPlayerAiThinking = computed(() => thinkingCharacterIds.value.size > 0)
  const playerAiThinkingNames = computed(() =>
    [...thinkingCharacterIds.value].map((id) => thinkingCharacterNames.value[id] ?? id),
  )

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

  function applySceneLayout(payload: SceneLayoutChangedPayload | SceneLayout) {
    currentScene.value = 'scene' in payload ? payload.scene : payload
  }

  function applyClockUpdated(payload: ClockUpdatedPayload) {
    const index = sceneClocks.value.findIndex((clock) => clock.id === payload.id)
    if (index >= 0) {
      sceneClocks.value[index] = { ...sceneClocks.value[index]!, ...payload }
    } else {
      sceneClocks.value.push(payload)
    }
  }

  function applyRegionMap(payload: RegionMapUpdatedPayload | RegionMap | null) {
    if (payload && 'region_map' in payload) {
      regionMap.value = payload.region_map
      if ('active_city_id' in payload) activeCityId.value = payload.active_city_id ?? null
      return
    }
    regionMap.value = payload
  }

  function applyCityMap(payload: CityMapUpdatedPayload | CityMap | null) {
    const cityMap = payload && 'city_map' in payload ? payload.city_map : payload
    if (payload && 'active_city_id' in payload) {
      activeCityId.value = payload.active_city_id ?? cityMap?.id ?? null
    } else if (cityMap) {
      activeCityId.value = cityMap.id
    }
    if (!cityMap) return
    cityMaps.value = { ...cityMaps.value, [cityMap.id]: cityMap }
  }

  function applyNodeStatus(
    scope: 'region' | 'city',
    nodeId: string,
    status: NodeStatus,
    cityId?: string | null,
  ) {
    if (scope === 'region' && regionMap.value) {
      regionMap.value = {
        ...regionMap.value,
        nodes: regionMap.value.nodes.map((node) =>
          node.id === nodeId ? { ...node, status } : node,
        ),
      }
      return
    }
    if (scope === 'city' && cityId && cityMaps.value[cityId]) {
      const cityMap = cityMaps.value[cityId]!
      cityMaps.value = {
        ...cityMaps.value,
        [cityId]: {
          ...cityMap,
          nodes: cityMap.nodes.map((node) =>
            node.id === nodeId ? { ...node, status } : node,
          ),
        },
      }
    }
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
    if ('current_scene' in payload) currentScene.value = payload.current_scene ?? null
    if ('scene_clocks' in payload) sceneClocks.value = payload.scene_clocks ?? []
    if ('region_map' in payload) regionMap.value = payload.region_map ?? null
    if ('city_maps' in payload) cityMaps.value = payload.city_maps ?? {}
    if ('active_city_id' in payload) activeCityId.value = payload.active_city_id ?? null
    if (payload.combatants) setCombatants(payload.combatants)
    if (payload.grid_config) gridConfig.value = payload.grid_config
    if ('grid_decoration' in payload) gridDecoration.value = payload.grid_decoration ?? null
    if ('reachable_cells' in payload) reachableCells.value = payload.reachable_cells ?? {}

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
    const type =
      payload.entry_kind === 'dialogue'
        ? 'dialogue'
        : payload.entry_kind === 'action'
          ? 'player'
          : 'narration'
    narrativeLog.value.push({
      id: crypto.randomUUID(),
      type,
      text: type === 'dialogue' ? stripSpeakerPrefix(payload.text, payload.speaker) : payload.text,
      speaker: payload.speaker,
      speaker_id: payload.speaker_id,
      speaker_kind: payload.speaker_kind,
      entry_kind: payload.entry_kind,
      scene_id: payload.scene_id,
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
      gridDecoration.value = null
      reachableCells.value = {}
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

  function setGridDecoration(decoration: GridDecoration | null | undefined) {
    gridDecoration.value = decoration ?? null
  }

  function setReachableCells(cells: Record<string, ReachableCells> | null | undefined) {
    reachableCells.value = cells ?? {}
  }

  function setReachableCellsFor(combatantId: string, cells: ReachableCells | null | undefined) {
    if (!cells) {
      const next = { ...reachableCells.value }
      delete next[combatantId]
      reachableCells.value = next
      return
    }
    reachableCells.value = { ...reachableCells.value, [combatantId]: cells }
  }

  function moveCombatant(payload: CombatantMovedPayload) {
    const idx = combatants.value.findIndex((c) => c.id === payload.combatant_id)
    if (idx !== -1) {
      combatants.value[idx] = { ...combatants.value[idx]!, position: payload.position } as CombatantState
    }
  }

  function applyActionEconomyChanged(payload: ActionEconomyChangedPayload) {
    updateCombatant(payload.combatant_id, { action_economy: payload.action_economy })
    if ('reachable_cells' in payload) {
      setReachableCellsFor(payload.combatant_id, payload.reachable_cells)
    }
  }

  function applyCombatantStatusChanged(payload: CombatantStatusChangedPayload) {
    const idx = combatants.value.findIndex((c) => c.id === payload.combatant_id)
    if (idx !== -1) {
      combatants.value[idx] = { ...combatants.value[idx]!, status: payload.status }
    }
  }

  function removeCombatant(id: string) {
    combatants.value = combatants.value.filter((c) => c.id !== id)
    if (selectedCombatantId.value === id) {
      selectedCombatantId.value =
        combatants.value.find((c) => c.is_active)?.id ?? combatants.value[0]?.id ?? null
    }
    if (currentTurnId.value === id) {
      currentTurnId.value = combatants.value.find((c) => c.is_active)?.id ?? null
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
    const wasConnected = connected.value
    connected.value = val
    if (wasConnected && !val) addSystemEntry('Déconnecté du serveur.')
  }

  function setError(msg: string | null) {
    isProcessing.value = false
    isGmThinking.value = false
    thinkingCharacterIds.value = new Set()
    thinkingCharacterNames.value = {}
    error.value = msg
    if (msg) addSystemEntry(`Erreur : ${msg}`)
  }

  function setProcessing(val: boolean) {
    isProcessing.value = val
  }

  function clearProcessingState() {
    isProcessing.value = false
    isGmThinking.value = false
    thinkingCharacterIds.value = new Set()
    thinkingCharacterNames.value = {}
  }

  function applyAiThinking(payload: { agent_kind: 'gm' | 'player_ai'; thinking: boolean; character_id?: string; character_name?: string }) {
    if (payload.agent_kind === 'gm') {
      isGmThinking.value = payload.thinking
      if (payload.thinking) {
        isProcessing.value = true
      }
      return
    }

    if (!payload.character_id) return

    const next = new Set(thinkingCharacterIds.value)
    const nextNames = { ...thinkingCharacterNames.value }
    if (payload.thinking) {
      next.add(payload.character_id)
      if (payload.character_name) nextNames[payload.character_id] = payload.character_name
    } else {
      next.delete(payload.character_id)
      delete nextNames[payload.character_id]
    }
    thinkingCharacterIds.value = next
    thinkingCharacterNames.value = nextNames
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
      const metadata = m.metadata ?? {}
      const metadataString = (key: string) => {
        const value = metadata[key]
        return typeof value === 'string' ? value : undefined
      }
      if (m.message_type === 'roll_result' && m.metadata) {
        const meta = m.metadata as Record<string, unknown>
        return {
          id: m.id,
          type: 'roll' as const,
          roll: {
            dice_notation: String(meta.dice_notation ?? meta.dice ?? ''),
            rolls: (meta.rolls as number[]) ?? [],
            total: Number(meta.total ?? 0),
            modifier: Number(meta.modifier ?? 0),
            dc: (meta.dc as number | null | undefined) ?? null,
            d20: meta.d20 as number | undefined,
            breakdown: meta.breakdown as string | undefined,
            success: meta.success as boolean | undefined,
            critical: meta.critical as boolean | undefined,
            label: (meta.label as string | undefined) ?? m.content,
            character_name: (meta.character_name as string | undefined) ?? m.speaker,
          },
          timestamp: m.created_at,
        }
      }
      const rawSpeakerKind = metadataString('speaker_kind')
      const speakerKind = (
        rawSpeakerKind && ['gm', 'human', 'companion', 'npc', 'monster'].includes(rawSpeakerKind)
          ? rawSpeakerKind
          : undefined
      ) as NarrationPayload['speaker_kind'] | undefined
      const entryKind =
        m.message_type === 'dialogue'
          ? ('dialogue' as const)
          : m.message_type === 'action'
            ? ('action' as const)
            : undefined
      const type =
        m.role === 'system'
          ? ('system' as const)
          : m.message_type === 'dialogue'
            ? ('dialogue' as const)
          : m.role === 'player'
            ? ('player' as const)
            : ('narration' as const)
      return {
        id: m.id,
        type,
        text: type === 'dialogue' ? stripSpeakerPrefix(m.content, m.speaker) : m.content,
        speaker: m.speaker,
        speaker_id: metadataString('speaker_id') ?? metadataString('character_id'),
        speaker_kind: speakerKind,
        entry_kind: entryKind,
        scene_id: metadataString('scene_id'),
        timestamp: m.created_at,
      }
    })
  }

  function reset() {
    narrativeLog.value = []
    combatants.value = []
    selectedCombatantId.value = null
    gridConfig.value = null
    gridDecoration.value = null
    reachableCells.value = {}
    phase.value = 'lobby'
    currentTurnId.value = null
    connected.value = false
    error.value = null
    isProcessing.value = false
    isGmThinking.value = false
    thinkingCharacterIds.value = new Set()
    thinkingCharacterNames.value = {}
    seenEventIds.value = new Set()
    adventureJournal.value = null
    quests.value = []
    chronicle.value = []
    currentScene.value = null
    sceneClocks.value = []
    regionMap.value = null
    cityMaps.value = {}
    activeCityId.value = null
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
    gridDecoration,
    reachableCells,
    adventureJournal,
    quests,
    chronicle,
    currentScene,
    sceneClocks,
    regionMap,
    cityMaps,
    activeCityId,
    connected,
    error,
    isProcessing,
    isGmThinking,
    isAnyAiThinking,
    isPlayerAiThinking,
    playerAiThinkingNames,
    isInCombat,
    activeCombatant,
    applyJournalUpdated,
    applyQuestUpdated,
    applyChronicleUpdated,
    applySceneLayout,
    applyClockUpdated,
    applyRegionMap,
    applyCityMap,
    applyNodeStatus,
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
    setGridDecoration,
    setReachableCells,
    setReachableCellsFor,
    moveCombatant,
    applyActionEconomyChanged,
    applyCombatantStatusChanged,
    removeCombatant,
    applyHpChanged,
    applyConditionChanged,
    applyDeathSaveUpdated,
    setConnected,
    setError,
    setProcessing,
    clearProcessingState,
    applyAiThinking,
    isCharacterThinking,
    consumeEventId,
    restoreHistory,
    reset,
  }
})
