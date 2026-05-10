import type { MapEdge, MapNode } from '../types'

export function findReachableNodes(nodes: MapNode[], edges: MapEdge[], fromId?: string | null): MapNode[] {
  if (!fromId) return []
  const nodeById = new Map(nodes.map((node) => [node.id, node]))
  const reachableIds = new Set<string>()
  for (const edge of edges) {
    if (edge.hidden) continue
    if (edge.from === fromId) reachableIds.add(edge.to)
    if (edge.to === fromId) reachableIds.add(edge.from)
  }
  return [...reachableIds].map((id) => nodeById.get(id)).filter((node): node is MapNode => Boolean(node))
}

export function pathBetween(nodes: MapNode[], edges: MapEdge[], fromId: string, toId: string): string[] {
  const nodeIds = new Set(nodes.map((node) => node.id))
  if (!nodeIds.has(fromId) || !nodeIds.has(toId)) return []

  const links = new Map<string, string[]>()
  for (const edge of edges) {
    if (edge.hidden) continue
    if (!nodeIds.has(edge.from) || !nodeIds.has(edge.to)) continue
    links.set(edge.from, [...(links.get(edge.from) ?? []), edge.to])
    links.set(edge.to, [...(links.get(edge.to) ?? []), edge.from])
  }

  const queue = [fromId]
  const cameFrom = new Map<string, string | null>([[fromId, null]])
  while (queue.length > 0) {
    const current = queue.shift()!
    if (current === toId) break
    for (const next of links.get(current) ?? []) {
      if (cameFrom.has(next)) continue
      cameFrom.set(next, current)
      queue.push(next)
    }
  }
  if (!cameFrom.has(toId)) return []

  const path: string[] = []
  let current: string | null = toId
  while (current) {
    path.unshift(current)
    current = cameFrom.get(current) ?? null
  }
  return path
}

export function prepareSvgViewBox(nodes: MapNode[]): string {
  if (nodes.length === 0) return '0 0 100 100'
  const xs = nodes.map((node) => node.position.x)
  const ys = nodes.map((node) => node.position.y)
  const minX = Math.max(0, Math.min(...xs) - 8)
  const minY = Math.max(0, Math.min(...ys) - 8)
  const maxX = Math.min(100, Math.max(...xs) + 8)
  const maxY = Math.min(100, Math.max(...ys) + 8)
  return `${minX} ${minY} ${Math.max(20, maxX - minX)} ${Math.max(20, maxY - minY)}`
}
