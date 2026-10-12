// Mise en page PURE des cartes Région et Ville (refonte lot 5) : cadrage plein
// cadre sans déformation, étiquettes anti-collision, état des routes, échelle en
// jours de marche, pictos par type de lieu. Aucune dépendance Vue : testé seul.

import type { MapEdge, MapNode, NodeStatus } from '../../types'

// ─── Cadrage ─────────────────────────────────────────────────────────────────

/** Projection monde (0..100) → pixels : px = x * scale + tx. Échelle UNIFORME. */
export interface Viewport {
  scale: number
  tx: number
  ty: number
}

export interface Point {
  x: number
  y: number
}

/**
 * Cadre les lieux dans le conteneur : boîte englobante + marge, échelle uniforme
 * (un cercle reste un cercle — l'ancien `preserveAspectRatio="none"` étirait la
 * carte), centrée. `minSpan` évite de zoomer à l'absurde sur 2 lieux voisins.
 */
export function fitViewport(
  points: Point[],
  width: number,
  height: number,
  options: { padding?: number; minSpan?: number } = {},
): Viewport {
  const padding = options.padding ?? 72
  const minSpan = options.minSpan ?? 40
  if (width <= 0 || height <= 0) return { scale: 1, tx: 0, ty: 0 }
  const xs = points.length ? points.map((p) => p.x) : [0, 100]
  const ys = points.length ? points.map((p) => p.y) : [0, 100]
  let minX = Math.min(...xs)
  let maxX = Math.max(...xs)
  let minY = Math.min(...ys)
  let maxY = Math.max(...ys)
  const cx = (minX + maxX) / 2
  const cy = (minY + maxY) / 2
  const spanX = Math.max(maxX - minX, minSpan)
  const spanY = Math.max(maxY - minY, minSpan)
  minX = cx - spanX / 2
  maxX = cx + spanX / 2
  minY = cy - spanY / 2
  maxY = cy + spanY / 2
  const usableW = Math.max(40, width - padding * 2)
  const usableH = Math.max(40, height - padding * 2)
  const scale = Math.min(usableW / (maxX - minX), usableH / (maxY - minY))
  return {
    scale,
    tx: width / 2 - cx * scale,
    ty: height / 2 - cy * scale,
  }
}

export function project(view: Viewport, point: Point): Point {
  return { x: point.x * view.scale + view.tx, y: point.y * view.scale + view.ty }
}

/** Zoom autour d'un point écran (molette), borné. */
export function zoomAt(view: Viewport, factor: number, at: Point, bounds: { min: number; max: number }): Viewport {
  const scale = Math.min(bounds.max, Math.max(bounds.min, view.scale * factor))
  const k = scale / view.scale
  return { scale, tx: at.x - (at.x - view.tx) * k, ty: at.y - (at.y - view.ty) * k }
}

// ─── Étiquettes ──────────────────────────────────────────────────────────────

export interface LabelMetrics {
  lines: string[]
  width: number
  height: number
}

/**
 * Taille estimée d'une étiquette (≤ maxLines lignes, ellipse au-delà). Estimation
 * volontairement généreuse (Cinzel est large) : mieux vaut un écart qu'un chevauchement.
 */
export function measureLabel(
  text: string,
  options: { fontPx?: number; maxWidth?: number; maxLines?: number; lineHeight?: number; charRatio?: number } = {},
): LabelMetrics {
  const fontPx = options.fontPx ?? 11
  const maxWidth = options.maxWidth ?? 150
  const maxLines = options.maxLines ?? 2
  const lineHeight = options.lineHeight ?? Math.round(fontPx * 1.3)
  const charW = fontPx * (options.charRatio ?? 0.64)
  const maxChars = Math.max(4, Math.floor(maxWidth / charW))
  const words = text.trim().split(/\s+/).filter(Boolean)
  const lines: string[] = []
  let current = ''
  for (const word of words) {
    const candidate = current ? `${current} ${word}` : word
    if (candidate.length <= maxChars || !current) {
      current = candidate
    } else {
      lines.push(current)
      current = word
    }
  }
  if (current) lines.push(current)
  if (lines.length > maxLines) {
    const kept = lines.slice(0, maxLines)
    const last = kept[maxLines - 1] ?? ''
    kept[maxLines - 1] = `${last.slice(0, Math.max(1, maxChars - 1)).trimEnd()}…`
    lines.splice(0, lines.length, ...kept)
  }
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i] ?? ''
    if (line.length > maxChars) lines[i] = `${line.slice(0, maxChars - 1)}…`
  }
  const width = Math.min(maxWidth, Math.max(...lines.map((line) => line.length), 1) * charW) + 10
  return { lines, width, height: lines.length * lineHeight + 6 }
}

export interface LabelRequest {
  id: string
  /** Ancre écran (centre du picto). */
  x: number
  y: number
  width: number
  height: number
  /** Rayon du picto : l'étiquette se pose à côté, jamais dessus. */
  radius: number
  /** Plus petit = placé en premier (lieu courant, puis visités…). */
  priority: number
}

export type LabelSide = 'below' | 'above' | 'right' | 'left' | 'below-right' | 'below-left' | 'above-right' | 'above-left'

export interface PlacedLabel {
  id: string
  left: number
  top: number
  width: number
  height: number
  side: LabelSide
}

interface Box {
  left: number
  top: number
  width: number
  height: number
}

const SIDES: LabelSide[] = ['below', 'above', 'right', 'left', 'below-right', 'below-left', 'above-right', 'above-left']
const GAP = 5

function candidateBox(request: LabelRequest, side: LabelSide): Box {
  const { x, y, width: w, height: h, radius: r } = request
  const d = r + GAP
  switch (side) {
    case 'below': return { left: x - w / 2, top: y + d, width: w, height: h }
    case 'above': return { left: x - w / 2, top: y - d - h, width: w, height: h }
    case 'right': return { left: x + d, top: y - h / 2, width: w, height: h }
    case 'left': return { left: x - d - w, top: y - h / 2, width: w, height: h }
    case 'below-right': return { left: x + r * 0.6, top: y + r * 0.6 + GAP, width: w, height: h }
    case 'below-left': return { left: x - r * 0.6 - w, top: y + r * 0.6 + GAP, width: w, height: h }
    case 'above-right': return { left: x + r * 0.6, top: y - r * 0.6 - GAP - h, width: w, height: h }
    case 'above-left': return { left: x - r * 0.6 - w, top: y - r * 0.6 - GAP - h, width: w, height: h }
  }
}

export function overlapArea(a: Box, b: Box): number {
  const w = Math.min(a.left + a.width, b.left + b.width) - Math.max(a.left, b.left)
  const h = Math.min(a.top + a.height, b.top + b.height) - Math.max(a.top, b.top)
  return w > 0 && h > 0 ? w * h : 0
}

function outside(box: Box, bounds: { width: number; height: number }, margin: number): number {
  const dx = Math.max(0, margin - box.left) + Math.max(0, box.left + box.width - (bounds.width - margin))
  const dy = Math.max(0, margin - box.top) + Math.max(0, box.top + box.height - (bounds.height - margin))
  return dx * box.height + dy * box.width
}

/**
 * Place les étiquettes autour de leur picto sans chevauchement (glouton par
 * priorité, 8 positions candidates) : ni sur une autre étiquette, ni sur un
 * picto, ni hors cadre. À défaut de place nette, la position la moins gênante.
 */
export function placeLabels(
  requests: LabelRequest[],
  bounds: { width: number; height: number },
  options: { margin?: number } = {},
): PlacedLabel[] {
  const margin = options.margin ?? 6
  const pins: Box[] = requests.map((r) => ({ left: r.x - r.radius, top: r.y - r.radius, width: r.radius * 2, height: r.radius * 2 }))
  const placed: (Box & { id: string; side: LabelSide })[] = []
  const ordered = [...requests].sort((a, b) => a.priority - b.priority || a.id.localeCompare(b.id))
  for (const request of ordered) {
    let best: { box: Box; side: LabelSide; cost: number } | null = null
    for (const side of SIDES) {
      const box = candidateBox(request, side)
      let cost = outside(box, bounds, margin) * 4
      for (const other of placed) cost += overlapArea(box, other) * 10
      pins.forEach((pin, index) => {
        if (requests[index]?.id !== request.id) cost += overlapArea(box, pin) * 6
      })
      // Légère préférence pour l'ordre des côtés (sous le picto d'abord).
      cost += SIDES.indexOf(side) * 0.01
      if (!best || cost < best.cost) best = { box, side, cost }
      if (cost < 1) break
    }
    if (best) placed.push({ ...best.box, id: request.id, side: best.side })
  }
  return placed.map(({ id, left, top, width, height, side }) => ({ id, left, top, width, height, side }))
}

// ─── Routes et statuts ───────────────────────────────────────────────────────

export type EdgeState = 'traveled' | 'known' | 'rumored'

const KNOWN_STATUSES = new Set<NodeStatus>(['visited', 'current'])

/** Parcourue (deux bouts visités), rumeur (un bout rumeur), sinon connue. */
export function edgeState(edge: MapEdge, byId: Map<string, MapNode>): EdgeState {
  const a = byId.get(edge.from)
  const b = byId.get(edge.to)
  if (a?.status === 'rumored' || b?.status === 'rumored') return 'rumored'
  if (a && b && KNOWN_STATUSES.has(a.status) && KNOWN_STATUSES.has(b.status)) return 'traveled'
  return 'known'
}

/** Routes affichables : jamais une route cachée, ni une route vers un lieu absent. */
export function visibleEdges(edges: MapEdge[], byId: Map<string, MapNode>): MapEdge[] {
  return edges.filter((edge) => !edge.hidden && byId.has(edge.from) && byId.has(edge.to))
}

export const STATUS_PRIORITY: Record<NodeStatus, number> = { current: 0, visited: 1, known: 2, rumored: 3 }

// ─── Échelle ─────────────────────────────────────────────────────────────────

/** Durée de trajet (jours) lue dans un indice libre : « 2 jours », « une demi-journée », « 6 h ». */
export function parseTravelDays(hint: string | null | undefined): number | null {
  if (!hint) return null
  const text = hint.toLowerCase()
  if (/demi[- ]journ[ée]e/.test(text)) return 0.5
  const words: Record<string, number> = { un: 1, une: 1, deux: 2, trois: 3, quatre: 4, cinq: 5, six: 6, sept: 7, huit: 8, dix: 10 }
  const match = text.match(/(\d+(?:[.,]\d+)?|un|une|deux|trois|quatre|cinq|six|sept|huit|dix)\s*(jours?|journ[ée]es?|days?|heures?|h\b|hours?)/)
  if (!match) return null
  const raw = match[1] ?? ''
  const value = words[raw] ?? Number(raw.replace(',', '.'))
  if (!Number.isFinite(value) || value <= 0) return null
  const unit = match[2] ?? ''
  return /^(heure|h|hour)/.test(unit) ? value / 10 : value // ~10 h de marche par jour
}

/**
 * Unités carte par jour de marche (médiane des routes chiffrées), ou null : sans
 * aucune durée dans les données, on n'invente pas d'échelle.
 */
export function unitsPerDay(edges: MapEdge[], byId: Map<string, MapNode>): number | null {
  const ratios: number[] = []
  for (const edge of edges) {
    const days = parseTravelDays(edge.travel_hint)
    const a = byId.get(edge.from)
    const b = byId.get(edge.to)
    if (!days || !a || !b) continue
    const distance = Math.hypot(a.position.x - b.position.x, a.position.y - b.position.y)
    if (distance > 0) ratios.push(distance / days)
  }
  if (!ratios.length) return null
  ratios.sort((x, y) => x - y)
  return ratios[Math.floor(ratios.length / 2)] ?? null
}

// ─── Pictos ──────────────────────────────────────────────────────────────────

export type MapGlyph =
  | 'village' | 'city' | 'port' | 'temple' | 'tower' | 'landmark' | 'forest' | 'mountain'
  | 'oasis' | 'cave' | 'ruin' | 'crossroads' | 'mine' | 'camp'
  | 'tavern' | 'shop' | 'palace' | 'gate' | 'square' | 'district' | 'house'
  | 'vault' | 'lair' | 'trap' | 'passage' | 'door'

const NAME_GLYPHS: [RegExp, MapGlyph][] = [
  [/\b(port|havre|quai|docks?|harbou?r)\b/i, 'port'],
  [/temple|sanctuaire|chapelle|abbaye|monast|cath[ée]drale|autel|shrine/i, 'temple'],
  [/\btour\b|donjon|citadelle|forteresse|fort\b|bastion|tower|keep/i, 'tower'],
  [/oasis|palmeraie/i, 'oasis'],
  [/\bmines?\b|carri[èe]re/i, 'mine'],
  [/for[êe]t|\bbois\b|sylve|futaie|forest|woods?/i, 'forest'],
  [/\bmonts?\b|montagne|\bcol\b|\bpic\b|sommet|massif|cr[êe]te|mountain|peak/i, 'mountain'],
  [/grotte|caverne|gouffre|antre|cave/i, 'cave'],
  [/ruine|vestige|d[ée]combre|ruin/i, 'ruin'],
  [/camp|bivouac|campement/i, 'camp'],
  [/carrefour|croisement|crossroad/i, 'crossroads'],
  [/\bcit[ée]\b|capitale|ville|city/i, 'city'],
]

const KIND_GLYPHS: Record<string, MapGlyph> = {
  settlement: 'village',
  landmark: 'landmark',
  wilderness: 'forest',
  dungeon: 'cave',
  crossroads: 'crossroads',
  ruin: 'ruin',
  district: 'district',
  building: 'house',
  square: 'square',
  gate: 'gate',
  docks: 'port',
  temple: 'temple',
  tavern: 'tavern',
  shop: 'shop',
  palace: 'palace',
  gateway: 'door',
  chamber: 'house',
  vault: 'vault',
  lair: 'lair',
  snare: 'trap',
  passage: 'passage',
}

/** Picto d'un lieu : le nom précise le type (« Port Nyanzaru » → ancre), sinon le kind. */
export function glyphFor(node: Pick<MapNode, 'kind' | 'name'>, scope: 'region' | 'city'): MapGlyph {
  if (scope === 'region') {
    for (const [pattern, glyph] of NAME_GLYPHS) {
      if (pattern.test(node.name)) return glyph
    }
  }
  return KIND_GLYPHS[node.kind] ?? (scope === 'region' ? 'landmark' : 'house')
}
