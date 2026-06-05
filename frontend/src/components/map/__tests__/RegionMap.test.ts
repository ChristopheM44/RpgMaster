import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import RegionMap from '../RegionMap.vue'
import NodeMap from '../NodeMap.vue'
import type { MapNode, NodeStatus, RegionMap as RegionMapType } from '../../../types'

function seededMap(endpointStatus: NodeStatus): RegionMapType {
  return {
    id: 'region',
    name: 'Région',
    current_node_id: 'depart',
    nodes: [
      {
        id: 'depart',
        name: 'Oasis',
        kind: 'settlement',
        position: { x: 30, y: 58 },
        status: 'current',
      },
      {
        id: 'source',
        name: 'Les Profondeurs noyées',
        kind: 'dungeon',
        position: { x: 68, y: 40 },
        status: endpointStatus,
      },
    ],
    edges: [{ id: 'vers_source', from: 'depart', to: 'source', kind: 'path', hidden: false }],
    updated_at: '2026-06-05T00:00:00Z',
  }
}

async function selectEndpointAndGetTravelButton(endpointStatus: NodeStatus) {
  const map = seededMap(endpointStatus)
  const wrapper = mount(RegionMap, { props: { map } })
  const endpoint = map.nodes.find((node: MapNode) => node.id === 'source')!
  // Mirror a player clicking the endpoint pin (NodeMap re-emits marker select).
  await wrapper.findComponent(NodeMap).vm.$emit('select', endpoint)
  await wrapper.vm.$nextTick()
  return wrapper.findAll('button').find((button) => button.text() === 'Voyager')
}

describe('RegionMap travel gating (N3)', () => {
  it('keeps the rumored objective endpoint a visible lead but NOT a one-click travel target', async () => {
    const travel = await selectEndpointAndGetTravelButton('rumored')
    expect(travel).toBeTruthy()
    // Visible & sélectionnable (la piste s'affiche), mais voyage désactivé → pas de
    // téléportation vers l'aboutissement de l'objectif au tour 1.
    expect(travel?.attributes('disabled')).toBeDefined()
  })

  it('allows travel once the endpoint is confirmed (known)', async () => {
    const travel = await selectEndpointAndGetTravelButton('known')
    expect(travel?.attributes('disabled')).toBeUndefined()
  })
})
