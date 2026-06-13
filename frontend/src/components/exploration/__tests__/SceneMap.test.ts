import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import SceneMap from '../SceneMap.vue'
import MapTooltip from '../MapTooltip.vue'
import { useGameStore } from '../../../stores/game'
import { useSessionStore } from '../../../stores/session'
import type { PickResult, RuntimeCallbacks, SceneSpec } from '../../../engine3d/types'

// Le moteur WebGL est mocké : les tests pilotent les callbacks de picking
// exactement comme le ferait un clic 3D, et inspectent la spec passée.
const { runtimeMock, harness } = vi.hoisted(() => {
  const runtimeMock = {
    update: vi.fn<(spec: SceneSpec) => void>(),
    moveToken: vi.fn(),
    projectCell: vi.fn(() => ({ x: 0, y: 0 })),
    projectToken: vi.fn(() => ({ x: 0, y: 0 })),
    setZoomPreset: vi.fn(),
    setRunning: vi.fn(),
    setBrightness: vi.fn(),
    resize: vi.fn(),
    dispose: vi.fn(),
  }
  const harness: { callbacks: RuntimeCallbacks | null } = { callbacks: null }
  return { runtimeMock, harness }
})

vi.mock('../../../engine3d', () => ({
  createSceneRuntime: (_canvas: HTMLCanvasElement, callbacks: RuntimeCallbacks) => {
    harness.callbacks = callbacks
    return runtimeMock
  },
}))

async function flushEngineBoot(): Promise<void> {
  // Laisse l'import dynamique du moteur (mocké) se résoudre.
  await new Promise((resolve) => setTimeout(resolve, 0))
}

function seedScene(): void {
  const gameStore = useGameStore()
  gameStore.applySceneLayout({
    scene: {
      cols: 12,
      rows: 12,
      cell_size_m: 1.5,
      scene_theme: 'city',
      pois: [
        {
          id: 'vibration_sol',
          name: 'Vibration anormale',
          kind: 'clue',
          position: { col: 4, row: 4 },
          element_id: 'element_vibration_sol',
        },
      ],
      exits: [
        {
          id: 'sortie_nord',
          label: 'Porte nord',
          position: { col: 6, row: 0 },
        },
      ],
      party_positions: {},
      elements: [
        {
          id: 'element_vibration_sol',
          name: 'Vibration anormale',
          kind: 'decor',
          geometry: { type: 'rect', col: 4, row: 4, width: 1, height: 1 },
          interactive: true,
        },
      ],
    },
  })
}

describe('SceneMap (3D)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    runtimeMock.update.mockClear()
    harness.callbacks = null
  })

  it('selects the linked POI when clicking a linked scene element', async () => {
    seedScene()
    const sessionStore = useSessionStore()

    mount(SceneMap)
    await flushEngineBoot()
    expect(harness.callbacks).not.toBeNull()

    const pick: PickResult = { type: 'element', id: 'element_vibration_sol' }
    harness.callbacks?.onClick?.(pick, { x: 10, y: 10 })

    expect(sessionStore.selectedId).toBe('vibration_sol')
  })

  it('selects a token (POI/sortie) on click and toggles on re-click', async () => {
    seedScene()
    const sessionStore = useSessionStore()

    mount(SceneMap)
    await flushEngineBoot()

    harness.callbacks?.onClick?.({ type: 'token', id: 'sortie_nord', tokenKind: 'exit' }, { x: 0, y: 0 })
    expect(sessionStore.selectedId).toBe('sortie_nord')

    harness.callbacks?.onClick?.({ type: 'token', id: 'sortie_nord', tokenKind: 'exit' }, { x: 0, y: 0 })
    expect(sessionStore.selectedId).toBeNull()
  })

  it('feeds the runtime with a spec built from the scene (tokens + éléments)', async () => {
    seedScene()
    mount(SceneMap)
    await flushEngineBoot()

    expect(runtimeMock.update).toHaveBeenCalled()
    const spec = runtimeMock.update.mock.calls.at(-1)?.[0] as SceneSpec
    expect(spec.ground.theme).toBe('city')
    expect(spec.elements.map((element) => element.id)).toContain('element_vibration_sol')
    const tokenIds = spec.tokens.map((token) => token.id)
    expect(tokenIds).toContain('vibration_sol')
    expect(tokenIds).toContain('sortie_nord')
    const exitToken = spec.tokens.find((token) => token.id === 'sortie_nord')
    expect(exitToken?.kind).toBe('exit')
  })

  it('shows the tooltip on hover and clears it on null hover', async () => {
    seedScene()
    const wrapper = mount(SceneMap)
    await flushEngineBoot()

    harness.callbacks?.onHover?.({ type: 'token', id: 'vibration_sol', tokenKind: 'poi' }, { x: 24, y: 36 })
    await wrapper.vm.$nextTick()
    expect(wrapper.findComponent(MapTooltip).exists()).toBe(true)

    harness.callbacks?.onHover?.(null, { x: 0, y: 0 })
    await wrapper.vm.$nextTick()
    expect(wrapper.findComponent(MapTooltip).exists()).toBe(false)
  })
})
