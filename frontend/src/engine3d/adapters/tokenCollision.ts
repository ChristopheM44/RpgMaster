// Anti-chevauchement PUR : quand plusieurs tokens partagent une cellule, les
// suivants reçoivent un offset monde sub-cellule en anneau autour du centre.
// Déterministe et insensible à l'ordre d'entrée (tri interne par priorité de
// kind puis id) — évite la « danse » des tokens quand le store réordonne.

import type { TokenKind, TokenSpec } from '../types'

/** Personnages au centre, marqueurs autour. */
const KIND_PRIORITY: Record<TokenKind, number> = {
  hero: 0,
  combatant: 0,
  npc: 1,
  poi: 2,
  exit: 3,
}

/** Rayon de l'anneau en unités monde (1 unité = 1 cellule) — reste dans la cellule. */
const RING_RADIUS = 0.3

export function resolveTokenOverlaps(tokens: TokenSpec[]): TokenSpec[] {
  const byCell = new Map<string, TokenSpec[]>()
  for (const token of tokens) {
    const key = `${token.col},${token.row}`
    const group = byCell.get(key)
    if (group) group.push(token)
    else byCell.set(key, [token])
  }

  const offsets = new Map<string, { x: number; z: number }>()
  for (const group of byCell.values()) {
    if (group.length < 2) continue
    const sorted = [...group].sort(
      (a, b) => KIND_PRIORITY[a.kind] - KIND_PRIORITY[b.kind] || a.id.localeCompare(b.id),
    )
    sorted.forEach((token, index) => {
      if (index === 0) return // prioritaire au centre
      const angle = -Math.PI / 2 + ((index - 1) * 2 * Math.PI) / (sorted.length - 1)
      offsets.set(token.id, {
        x: RING_RADIUS * Math.cos(angle),
        z: RING_RADIUS * Math.sin(angle),
      })
    })
  }

  if (offsets.size === 0) return tokens
  return tokens.map((token) => {
    const offset = offsets.get(token.id)
    return offset ? { ...token, offsetX: offset.x, offsetZ: offset.z } : token
  })
}
