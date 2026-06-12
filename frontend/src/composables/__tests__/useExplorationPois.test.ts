import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useGameStore } from '../../stores/game'
import { useExplorationPois } from '../useExplorationPois'

describe('useExplorationPois', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('preserves NPC and clue semantics from scene POIs', () => {
    const gameStore = useGameStore()
    gameStore.applySceneLayout({
      scene: {
        cols: 12,
        rows: 12,
        cell_size_m: 1.5,
        scene_theme: 'desert',
        pois: [
          {
            id: 'khalid_guide',
            name: 'Khalid le Guide',
            kind: 'npc',
            icon: 'npc',
            position: { col: 5, row: 5 },
            element_id: 'guide_marker',
            description: 'Un homme brûlé par le soleil.',
            interactions: [
              {
                id: 'talk_khalid',
                label: 'Parler',
                intent: 'talk',
                prompt: "Je m'approche de Khalid et lui parle.",
              },
            ],
          },
          {
            id: 'corps_corrompu',
            name: 'Cadavre anormal',
            kind: 'clue',
            icon: 'clue',
            position: { col: 4, row: 4 },
            description: 'Des veines noires parcourent la peau.',
            state: 'discovered',
            visibility: 'subtle',
            discovered: true,
            physical_state: 'chair froide, traces noires sèches',
            facts: ['Les traces convergent vers le puits.'],
          },
        ],
        exits: [
          {
            id: 'route_oasis',
            label: "Vers l'Oasis",
            position: { col: 11, row: 7 },
            element_id: 'oasis_gate',
            leads_to: 'Oasis',
          },
        ],
        party_positions: {},
      },
    })

    const { pois, reperes, sorties } = useExplorationPois()
    const npc = pois.value.find((p) => p.id === 'khalid_guide')
    const clue = pois.value.find((p) => p.id === 'corps_corrompu')

    expect(npc).toMatchObject({
      kind: 'npc',
      iconId: 'npc',
      actionLabel: 'Parler',
      interactionId: 'talk_khalid',
      prompt: "Je m'approche de Khalid et lui parle.",
      elementId: 'guide_marker',
    })
    expect(clue).toMatchObject({
      kind: 'clue',
      iconId: 'clue',
      actionLabel: 'Examiner',
      state: 'discovered',
      visibility: 'subtle',
      discovered: true,
      physicalState: 'chair froide, traces noires sèches',
      facts: ['Les traces convergent vers le puits.'],
    })
    expect(reperes.value).toHaveLength(2)
    expect(sorties.value).toHaveLength(1)
  })

  it('hides undiscovered hidden POIs and keeps discovered hidden POIs visible', () => {
    const gameStore = useGameStore()
    gameStore.applySceneLayout({
      scene: {
        cols: 12,
        rows: 12,
        cell_size_m: 1.5,
        scene_theme: 'dungeon',
        pois: [
          {
            id: 'secret_door',
            name: 'Porte secrète',
            kind: 'clue',
            position: { col: 4, row: 4 },
            visibility: 'hidden',
            discovered: false,
          },
          {
            id: 'revealed_cache',
            name: 'Cache révélée',
            kind: 'loot',
            position: { col: 6, row: 4 },
            visibility: 'hidden',
            discovered: true,
          },
        ],
        exits: [],
        party_positions: {},
      },
    })

    const { pois } = useExplorationPois()

    expect(pois.value.find((poi) => poi.id === 'secret_door')).toBeUndefined()
    expect(pois.value.find((poi) => poi.id === 'revealed_cache')).toBeTruthy()
  })

  it('uses backend exit active flag and defaults exits to active', () => {
    const gameStore = useGameStore()
    gameStore.applySceneLayout({
      scene: {
        cols: 12,
        rows: 12,
        cell_size_m: 1.5,
        scene_theme: 'forest',
        pois: [],
        exits: [
          {
            id: 'open_path',
            label: 'Sentier ouvert',
            position: { col: 0, row: 5 },
            leads_to: 'clearing',
          },
          {
            id: 'sealed_gate',
            label: 'Grille scellée',
            position: { col: 11, row: 5 },
            leads_to: 'vault',
            active: false,
          },
        ],
        party_positions: {},
      },
    })

    const { sorties } = useExplorationPois()

    expect(sorties.value.find((exit) => exit.id === 'open_path')?.active).toBe(true)
    expect(sorties.value.find((exit) => exit.id === 'sealed_gate')?.active).toBe(false)
  })

  it("nettoie un libellé d'affordance à la 1re personne en verbe court (prompt préservé)", () => {
    const gameStore = useGameStore()
    gameStore.applySceneLayout({
      scene: {
        cols: 12,
        rows: 12,
        cell_size_m: 1.5,
        scene_theme: 'plains',
        pois: [
          {
            id: 'elara_pnj',
            name: 'Elara',
            kind: 'npc',
            icon: 'npc',
            position: { col: 5, row: 5 },
            interactions: [
              {
                id: 'ask_elara',
                label: 'je demande un avertissement',
                intent: 'talk',
                prompt: 'Je demande à Elara un avertissement.',
              },
            ],
          },
          {
            id: 'puits',
            name: 'Puits',
            kind: 'hazard',
            icon: 'trap-danger',
            position: { col: 7, row: 5 },
            interactions: [
              {
                id: 'corde',
                label: 'Jeter une corde',
                intent: 'use',
                prompt: 'Je jette une corde dans le puits.',
              },
            ],
          },
        ],
        exits: [],
        party_positions: {},
      },
    })

    const { pois } = useExplorationPois()
    const npc = pois.value.find((p) => p.id === 'elara_pnj')
    // Le bouton affiche un verbe court, pas la phrase à la 1re personne…
    expect(npc?.actionLabel).toBe('Parler')
    // …mais le prompt réellement envoyé reste intact.
    expect(npc?.prompt).toBe('Je demande à Elara un avertissement.')

    // Faux positif à éviter : un libellé impératif commençant par « Je… »
    // (« Jeter ») ne doit PAS être écrasé.
    const puits = pois.value.find((p) => p.id === 'puits')
    expect(puits?.actionLabel).toBe('Jeter une corde')
  })
})
