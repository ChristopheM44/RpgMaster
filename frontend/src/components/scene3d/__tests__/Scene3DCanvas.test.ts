import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'

import Scene3DCanvas from '../Scene3DCanvas.vue'
import type { ArrivalSpec, SceneSpec } from '../../../engine3d/types'

// Moteur mocké : on vérifie l'ORDONNANCEMENT de la transition de scène
// (travelling → fondu → update unique → arrivée → spec en attente appliquée).
const { runtimeMock } = vi.hoisted(() => ({
  runtimeMock: {
    update: vi.fn(),
    moveToken: vi.fn(),
    projectCell: vi.fn(() => ({ x: 0, y: 0 })),
    projectToken: vi.fn(() => ({ x: 0, y: 0 })),
    setZoomPreset: vi.fn(),
    setRunning: vi.fn(),
    setBrightness: vi.fn(),
    focusCell: vi.fn(() => Promise.resolve()),
    arriveAt: vi.fn(),
    resize: vi.fn(),
    dispose: vi.fn(),
  },
}))

vi.mock('../../../engine3d', () => ({ createSceneRuntime: () => runtimeMock }))

function spec(sceneId: string, arrival: ArrivalSpec | null = null, extra = 0): SceneSpec {
  return {
    ground: {
      cols: 12,
      rows: 12,
      cellSizeM: 1.5,
      theme: 'dungeon',
      sceneId,
      visualAssetUrl: null,
      ambiance: { light: 'torchlit', fogDensity: 0.25 },
      vegetationDensity: extra,
    },
    elements: [],
    tokens: [
      { id: 'hero', kind: 'hero', name: 'Thorvald', col: 5, row: 5, accent: '#f0c764', modelKey: null, initials: 'T',
        hpRatio: 1, selected: false, highlighted: false, active: false, targetable: null, defeated: false, iconId: null,
        exitActive: false },
      { id: 'exit_2', kind: 'exit', name: 'Descendre', col: 8, row: 11, accent: '#f0c764', modelKey: null, initials: '',
        hpRatio: null, selected: false, highlighted: false, active: false, targetable: null, defeated: false,
        iconId: null, exitActive: true },
    ],
    overlay: { reachable: [], reachableEmphasis: 'idle', destination: null, path: [], aoe: null, zones: [], obstacles: [], cellPicking: false },
    scatterBlockedCells: [],
    elevationByCell: {},
    arrival,
  }
}

const arrival: ArrivalSpec = {
  exitId: 'retour', col: 8, row: 0, facing: 'north', verticalDirection: 'up',
  fromSceneId: 'jardin', viaExitId: 'exit_2', label: 'Remonter',
}

describe('Scene3DCanvas — transition de scène', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    Object.values(runtimeMock).forEach((fn) => fn.mockClear())
  })
  afterEach(() => vi.useRealTimers())

  it('travelling vers la sortie, fondu, une seule reconstruction, arrivée et spec en attente', async () => {
    const wrapper = mount(Scene3DCanvas, { props: { spec: spec('jardin') } })
    await vi.runAllTimersAsync() // import dynamique du moteur (mocké)
    expect(runtimeMock.update).toHaveBeenCalledTimes(1)

    await wrapper.setProps({ spec: spec('caveau', arrival) })
    await nextTick()
    // Départ : le héros marche vers la sortie empruntée, la caméra la suit.
    expect(runtimeMock.moveToken).toHaveBeenCalledWith('hero', expect.arrayContaining([{ col: 8, row: 11 }]))
    expect(runtimeMock.focusCell).toHaveBeenCalledWith(8, 11, 0.9)
    expect(runtimeMock.update).toHaveBeenCalledTimes(1) // pas encore reconstruit

    // Une spec qui arrive PENDANT la transition attend son tour.
    await wrapper.setProps({ spec: spec('caveau', arrival, 0.5) })
    await vi.advanceTimersByTimeAsync(300) // fondu
    expect(runtimeMock.update).toHaveBeenCalledTimes(2)
    expect(runtimeMock.update.mock.calls[1]![0].ground.sceneId).toBe('caveau')
    expect(runtimeMock.arriveAt).toHaveBeenCalledWith(8, 0, 1.0)
    expect(wrapper.text()).toContain('Arrivée · Remonter')

    await vi.advanceTimersByTimeAsync(300)
    expect(runtimeMock.update).toHaveBeenCalledTimes(3)
    expect(runtimeMock.update.mock.calls[2]![0].ground.vegetationDensity).toBe(0.5)
    wrapper.unmount()
  })

  it('même scène : mise à jour directe, sans transition', async () => {
    const wrapper = mount(Scene3DCanvas, { props: { spec: spec('jardin') } })
    await vi.runAllTimersAsync()
    await wrapper.setProps({ spec: spec('jardin', null, 0.3) })
    await nextTick()
    expect(runtimeMock.update).toHaveBeenCalledTimes(2)
    expect(runtimeMock.focusCell).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})
