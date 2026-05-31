import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useGameStore } from '../game'

describe('useGameStore map decoration state', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('stores grid decorations and clears them outside combat', () => {
    const store = useGameStore()

    store.setGridDecoration({
      obstacles: [{ col: 1, row: 2 }],
      zones: [{ id: 'fog', name: 'Brume', kind: 'hazard', cells: [{ col: 2, row: 2 }] }],
    })

    expect(store.gridDecoration?.obstacles).toEqual([{ col: 1, row: 2 }])
    expect(store.gridDecoration?.zones?.[0]?.name).toBe('Brume')

    store.applyPhaseChange('exploration')

    expect(store.gridDecoration).toBeNull()
  })

  it('resets grid decorations with the rest of combat state', () => {
    const store = useGameStore()

    store.setGridDecoration({ obstacles: [{ col: 1, row: 1 }] })
    store.reset()

    expect(store.gridDecoration).toBeNull()
  })

  it('hydrates campaign maps from session_state payloads', () => {
    const store = useGameStore()

    store.applySessionState({
      session_id: 'session-1',
      phase: 'exploration',
      turn_number: 1,
      round_number: 0,
      turn_order: [],
      current_turn_index: 0,
      valid_transitions: [],
      region_map: {
        id: 'region',
        name: 'Route des Brumes',
        current_node_id: 'camp',
        nodes: [
          {
            id: 'camp',
            name: 'Camp',
            kind: 'landmark',
            position: { x: 40, y: 60 },
            status: 'current',
          },
        ],
        edges: [],
        updated_at: '2026-05-10T00:00:00Z',
      },
      city_maps: {
        camp: {
          id: 'camp',
          region_node_id: 'camp',
          name: 'Camp',
          current_node_id: 'feu',
          nodes: [
            {
              id: 'feu',
              name: 'Feu de camp',
              kind: 'square',
              position: { x: 50, y: 50 },
              status: 'current',
            },
          ],
          edges: [],
          updated_at: '2026-05-10T00:00:00Z',
        },
      },
      active_city_id: 'camp',
    })

    expect(store.regionMap?.current_node_id).toBe('camp')
    expect(store.cityMaps.camp?.current_node_id).toBe('feu')
    expect(store.activeCityId).toBe('camp')
  })

  it('hydrates and updates optional scene clocks only when present', () => {
    const store = useGameStore()

    store.applySessionState({
      session_id: 'session-1',
      phase: 'exploration',
      turn_number: 1,
      round_number: 0,
      turn_order: [],
      current_turn_index: 0,
      valid_transitions: [],
    })
    expect(store.sceneClocks).toEqual([])

    store.applyClockUpdated({
      id: 'menace_docks',
      label: 'Menace aux docks',
      scope: 'scene',
      current: 1,
      max: 4,
      severity: 'high',
      status: 'active',
    })

    expect(store.sceneClocks).toHaveLength(1)
    expect(store.sceneClocks[0]?.current).toBe(1)

    store.applyClockUpdated({
      id: 'menace_docks',
      label: 'Menace aux docks',
      scope: 'scene',
      current: 4,
      max: 4,
      severity: 'high',
      status: 'resolved',
    })

    expect(store.sceneClocks).toEqual([])
  })

  it('logs disconnection only on connected to disconnected transitions', () => {
    const store = useGameStore()

    store.setConnected(false)
    expect(store.narrativeLog).toHaveLength(0)

    store.setConnected(true)
    store.setConnected(false)
    store.setConnected(false)

    expect(store.narrativeLog.filter((entry) => entry.text === 'Déconnecté du serveur.')).toHaveLength(1)
  })

  it('restores dialogue history as dialogue entries', () => {
    const store = useGameStore()

    store.restoreHistory([
      {
        id: 'msg-1',
        role: 'gm',
        speaker: 'Azaka',
        message_type: 'dialogue',
        content: 'Je peux vous guider.',
        metadata: {
          speaker_id: 'azaka',
          speaker_kind: 'npc',
          scene_id: 'scene-1',
        },
        created_at: '2026-05-09T12:00:00Z',
      },
    ])

    expect(store.narrativeLog[0]).toMatchObject({
      type: 'dialogue',
      text: 'Je peux vous guider.',
      speaker: 'Azaka',
      speaker_id: 'azaka',
      speaker_kind: 'npc',
      entry_kind: 'dialogue',
      scene_id: 'scene-1',
    })
  })

  it('keeps legacy narration events with dialogue entry_kind as dialogue entries', () => {
    const store = useGameStore()

    store.addNarration({
      text: 'Je reste avec toi.',
      speaker: 'Thorin',
      speaker_kind: 'companion',
      entry_kind: 'dialogue',
    })

    expect(store.narrativeLog[0]).toMatchObject({
      type: 'dialogue',
      text: 'Je reste avec toi.',
      speaker: 'Thorin',
      speaker_kind: 'companion',
      entry_kind: 'dialogue',
    })
  })

  it('tracks player AI thinking separately from GM thinking', () => {
    const store = useGameStore()

    store.applyAiThinking({
      agent_kind: 'player_ai',
      thinking: true,
      character_id: 'shade',
      character_name: 'Shade',
    })

    expect(store.isGmThinking).toBe(false)
    expect(store.isPlayerAiThinking).toBe(true)
    expect(store.isAnyAiThinking).toBe(true)
    expect(store.playerAiThinkingNames).toEqual(['Shade'])

    store.applyAiThinking({
      agent_kind: 'player_ai',
      thinking: false,
      character_id: 'shade',
    })

    expect(store.isPlayerAiThinking).toBe(false)
    expect(store.playerAiThinkingNames).toEqual([])
  })

  it('clears player AI thinking state on errors', () => {
    const store = useGameStore()

    store.applyAiThinking({
      agent_kind: 'player_ai',
      thinking: true,
      character_id: 'shade',
      character_name: 'Shade',
    })
    store.setError('Erreur test')

    expect(store.isPlayerAiThinking).toBe(false)
    expect(store.playerAiThinkingNames).toEqual([])
    expect(store.narrativeLog.at(-1)?.text).toBe('Erreur test')
  })

  it('strips redundant dialogue speaker prefixes', () => {
    const store = useGameStore()

    store.addNarration({
      text: 'Syndra laisse échapper un soupir las.',
      speaker: 'Syndra Silvane',
      speaker_kind: 'npc',
      entry_kind: 'dialogue',
    })

    expect(store.narrativeLog[0]).toMatchObject({
      type: 'dialogue',
      text: 'laisse échapper un soupir las.',
      speaker: 'Syndra Silvane',
    })
  })
})
