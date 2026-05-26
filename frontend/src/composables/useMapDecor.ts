/**
 * useMapDecor — résout le décor visuel d'une carte (RegionMap ou CityMap).
 *
 * Si `decor` est fourni par le backend, on l'utilise tel quel.
 * Sinon, on génère un décor procédural déterministe à partir du seed
 * (background_seed ?? id) pour que la carte ne soit jamais vide.
 *
 * Pour les RegionMaps, on tente de détecter le biome à partir des noms de
 * nœuds (mots-clés côtiers, désertiques, etc.) pour éviter d'afficher une
 * forêt sur une île rocailleuse ou un littoral.
 */

import type { MapDecor, ForestSpot, MountainSpot, Coastline, RiverPath } from '../types'

// ─── PRNG déterministe (mulberry32) ──────────────────────────────────────────

function hashSeed(s: string): number {
  let h = 0
  for (let i = 0; i < s.length; i++) {
    h = Math.imul(31, h) + s.charCodeAt(i) | 0
  }
  return h >>> 0
}

function makePrng(seed: string) {
  let state = hashSeed(seed || 'default')
  return function rand(): number {
    state += 0x6d2b79f5
    let t = Math.imul(state ^ (state >>> 15), 1 | state)
    t ^= t + Math.imul(t ^ (t >>> 7), 61 | t)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

// ─── Génération procédurale ───────────────────────────────────────────────────

// ─── Détection biome par mots-clés ───────────────────────────────────────────

const COASTAL_KEYWORDS = [
  'rivage', 'plage', 'côte', 'cote', 'mer', 'île', 'ile', 'baie', 'port',
  'quai', 'littoral', 'grève', 'greve', 'anse', 'falaise', 'estuaire',
  'beach', 'coast', 'shore', 'sea', 'island', 'bay', 'harbor', 'harbour',
]
const DESERT_KEYWORDS = [
  'désert', 'desert', 'sable', 'dune', 'oasis', 'aride', 'steppe',
]
const MOUNTAIN_KEYWORDS = [
  'mont', 'sommet', 'pic', 'col', 'massif', 'alpin', 'alpine', 'crête',
  'crete', 'mountain', 'peak', 'ridge', 'pass', 'highland',
]

type RegionBiome = 'coastal' | 'mountain' | 'desert' | 'default'

/**
 * Infère le biome d'une région à partir d'un corpus de texte (IDs + noms de nœuds).
 * Retourne 'default' (forêts) si aucun mot-clé n'est trouvé.
 */
export function inferRegionBiome(corpus: string): RegionBiome {
  const lower = corpus.toLowerCase()
  if (COASTAL_KEYWORDS.some(kw => lower.includes(kw))) return 'coastal'
  if (DESERT_KEYWORDS.some(kw => lower.includes(kw))) return 'desert'
  if (MOUNTAIN_KEYWORDS.some(kw => lower.includes(kw))) return 'mountain'
  return 'default'
}

/**
 * Génère un décor de région côtière : grande zone d'eau, peu de forêts,
 * rochers/falaises représentés par des clusters de cercles gris.
 */
export function generateCoastalRegionDecor(seed: string): MapDecor {
  const rand = makePrng(`coastal:${seed}`)

  // Quelques forêts limitées — surtout à l'intérieur des terres (haut de carte)
  const forests: ForestSpot[] = []
  const forestCount = 3 + Math.floor(rand() * 4)
  for (let i = 0; i < forestCount; i++) {
    forests.push({
      x: Math.round((5 + rand() * 90) * 10) / 10,
      y: Math.round((5 + rand() * 40) * 10) / 10, // terres intérieures = haut
      radius: 2 + rand() * 2,
      opacity: 0.25 + rand() * 0.2,
    })
  }

  // Côte — favoriser côté ouest ou sud
  const sides = ['west', 'south', 'east'] as const
  const side = sides[Math.floor(rand() * sides.length)] as Coastline['side']
  const coastline: Coastline = { side, points: _coastlinePoints(side, rand) }

  // Routes décoratives — moins nombreuses, côté terrestre
  const decorativeRoads: string[] = []
  const roadCount = 1 + Math.floor(rand() * 2)
  for (let i = 0; i < roadCount; i++) {
    decorativeRoads.push(_randomRoadPath(rand))
  }

  return { forests, coastline, decorative_roads: decorativeRoads }
}

/**
 * Génère un décor de région désertique : dunes, pas de forêts, pas de rivière.
 */
export function generateDesertRegionDecor(seed: string): MapDecor {
  const rand = makePrng(`desert:${seed}`)

  // "Forêts" remplacées par des touffes de végétation désertique (très petites)
  const forests: ForestSpot[] = []
  const clusterCount = 4 + Math.floor(rand() * 4)
  for (let i = 0; i < clusterCount; i++) {
    forests.push({
      x: Math.round((5 + rand() * 90) * 10) / 10,
      y: Math.round((5 + rand() * 90) * 10) / 10,
      radius: 1.2 + rand() * 1.5,
      opacity: 0.15 + rand() * 0.12,
    })
  }

  const decorativeRoads: string[] = []
  const roadCount = 1 + Math.floor(rand() * 2)
  for (let i = 0; i < roadCount; i++) {
    decorativeRoads.push(_randomRoadPath(rand))
  }

  return { forests, decorative_roads: decorativeRoads }
}

/**
 * Génère un décor de région montagneuse : nombreux triangles, peu de forêts.
 */
export function generateMountainRegionDecor(seed: string): MapDecor {
  const rand = makePrng(`mountain:${seed}`)

  // Forêts dans les vallées (bas de carte)
  const forests: ForestSpot[] = []
  const forestCount = 4 + Math.floor(rand() * 5)
  for (let i = 0; i < forestCount; i++) {
    forests.push({
      x: Math.round((5 + rand() * 90) * 10) / 10,
      y: Math.round((50 + rand() * 45) * 10) / 10, // vallées = bas
      radius: 2.5 + rand() * 2,
      opacity: 0.30 + rand() * 0.15,
    })
  }

  // Beaucoup de montagnes — toute la moitié supérieure
  const mountains: MountainSpot[] = []
  const mountainCount = 7 + Math.floor(rand() * 5)
  for (let i = 0; i < mountainCount; i++) {
    mountains.push({
      x: 5 + rand() * 90,
      y: 5 + rand() * 55,
      height: 5 + rand() * 7,
    })
  }

  const decorativeRoads: string[] = []
  const roadCount = 2 + Math.floor(rand() * 2)
  for (let i = 0; i < roadCount; i++) {
    decorativeRoads.push(_randomRoadPath(rand))
  }

  return { forests, mountains, decorative_roads: decorativeRoads }
}

// ─── Génération principale ────────────────────────────────────────────────────

/**
 * Génère un décor de région (forêts dispersées, montagnes NE, mer optionnelle).
 * Similaire à la preview Côte des Épées mais adapté à chaque seed.
 */
export function generateRegionDecor(seed: string): MapDecor {
  const rand = makePrng(`region:${seed}`)

  // Forêts — 10 à 16 cercles dispersés évitant le centre
  const forests: ForestSpot[] = []
  const forestCount = 10 + Math.floor(rand() * 6)
  for (let i = 0; i < forestCount; i++) {
    // Évite la zone centrale (30..70 x 30..70) pour laisser de la place aux nodes
    let x: number, y: number
    do {
      x = 5 + rand() * 90
      y = 5 + rand() * 90
    } while (x > 25 && x < 75 && y > 25 && y < 75)

    forests.push({
      x: Math.round(x * 10) / 10,
      y: Math.round(y * 10) / 10,
      radius: 2.5 + rand() * 2,
      opacity: 0.3 + rand() * 0.2,
    })
  }

  // Montagnes — 3 à 6 triangles, plutôt au NE ou NO
  const mountains: MountainSpot[] = []
  const mountainCount = 3 + Math.floor(rand() * 4)
  for (let i = 0; i < mountainCount; i++) {
    mountains.push({
      x: 60 + rand() * 35,
      y: 5 + rand() * 40,
      height: 4 + rand() * 5,
    })
  }

  // Mer/côte — 50 % de chance, côté déterministe selon seed
  let coastline: Coastline | undefined
  if (rand() > 0.5) {
    const sides = ['west', 'east', 'north'] as const
    const side = sides[Math.floor(rand() * sides.length)] as Coastline['side']
    // Points terrain-mer simplifiés selon le côté
    const coastPoints = _coastlinePoints(side, rand)
    coastline = { side, points: coastPoints }
  }

  // Rivière — 40 % de chance
  let river: RiverPath | undefined
  if (rand() > 0.6) {
    river = _randomRiver(rand)
  }

  // Routes décoratives — 2 à 4 paths
  const decorativeRoads: string[] = []
  const roadCount = 2 + Math.floor(rand() * 2)
  for (let i = 0; i < roadCount; i++) {
    decorativeRoads.push(_randomRoadPath(rand))
  }

  return { forests, mountains, coastline, river, decorative_roads: decorativeRoads }
}

/**
 * Génère un décor de ville (forêts en périphérie, rivière optionnelle, routes).
 */
export function generateCityDecor(seed: string): MapDecor {
  const rand = makePrng(`city:${seed}`)

  // Forêts en périphérie (bords de la carte)
  const forests: ForestSpot[] = []
  const forestCount = 6 + Math.floor(rand() * 6)
  for (let i = 0; i < forestCount; i++) {
    // Zone périphérique (bords 0..20 ou 80..100)
    const onVertical = rand() > 0.5
    forests.push({
      x: onVertical ? (rand() > 0.5 ? rand() * 15 : 85 + rand() * 15) : 5 + rand() * 90,
      y: onVertical ? 5 + rand() * 90 : (rand() > 0.5 ? rand() * 15 : 85 + rand() * 15),
      radius: 2 + rand() * 2.5,
      opacity: 0.35 + rand() * 0.15,
    })
  }

  // Routes décoratives — 2 à 3 en plus des edges
  const decorativeRoads: string[] = []
  const roadCount = 2 + Math.floor(rand() * 2)
  for (let i = 0; i < roadCount; i++) {
    decorativeRoads.push(_randomRoadPath(rand))
  }

  // Rivière — 35 % de chance
  let river: RiverPath | undefined
  if (rand() > 0.65) {
    river = _randomRiver(rand)
  }

  return { forests, decorative_roads: decorativeRoads, river }
}

// ─── Helpers internes ─────────────────────────────────────────────────────────

function _coastlinePoints(side: Coastline['side'], rand: () => number) {
  // Génère 3 points pour un contour côtier simple
  if (side === 'west') {
    const top = rand() * 20
    const bot = 80 + rand() * 20
    const indent = 8 + rand() * 12
    return [
      { x: 0, y: 0 },
      { x: indent, y: 0 },
      { x: indent - rand() * 6, y: 30 },
      { x: indent + rand() * 4, y: 60 },
      { x: indent, y: 100 },
      { x: 0, y: 100 },
    ]
  }
  if (side === 'east') {
    const indent = 88 - rand() * 12
    return [
      { x: 100, y: 0 },
      { x: indent, y: 0 },
      { x: indent + rand() * 6, y: 30 },
      { x: indent - rand() * 4, y: 60 },
      { x: indent, y: 100 },
      { x: 100, y: 100 },
    ]
  }
  // north
  const indent = 8 + rand() * 12
  return [
    { x: 0, y: 0 },
    { x: 0, y: indent },
    { x: 30, y: indent - rand() * 4 },
    { x: 70, y: indent + rand() * 4 },
    { x: 100, y: indent },
    { x: 100, y: 0 },
  ]
}

function _randomRiver(rand: () => number): RiverPath {
  // Rivière horizontale traversant la carte avec courbure
  const y1 = 30 + rand() * 40
  const y2 = y1 + (rand() - 0.5) * 20
  const y3 = y1 + (rand() - 0.5) * 15
  const path = `M 0 ${y1.toFixed(0)} Q ${(20 + rand() * 20).toFixed(0)} ${y2.toFixed(0)} ${(50 + rand() * 10).toFixed(0)} ${((y1 + y2) / 2).toFixed(0)} T 100 ${y3.toFixed(0)}`
  return { path, width: 1.2 + rand() * 1 }
}

function _randomRoadPath(rand: () => number): string {
  // Route diagonale ou horizontale couvrant la carte
  const startX = rand() > 0.5 ? 0 : rand() * 30
  const startY = rand() * 100
  const endX = rand() > 0.5 ? 100 : 70 + rand() * 30
  const endY = rand() * 100
  const midX = 30 + rand() * 40
  const midY = (startY + endY) / 2 + (rand() - 0.5) * 20
  return `M ${startX.toFixed(0)} ${startY.toFixed(0)} Q ${midX.toFixed(0)} ${midY.toFixed(0)} ${endX.toFixed(0)} ${endY.toFixed(0)}`
}

// ─── Export principal ─────────────────────────────────────────────────────────

/**
 * Résout le décor effectif d'une carte.
 *
 * @param backendDecor - Décor fourni par le backend (peut être undefined).
 * @param seed - background_seed ou id de la carte, utilisé si backendDecor est absent.
 * @param kind - 'region' ou 'city' — détermine le type de décor procédural.
 * @param nodeCorpus - Texte libre (IDs + noms de nœuds concaténés) pour détecter
 *                     le biome d'une RegionMap quand le backend n'a pas fourni de décor.
 */
export function resolveMapDecor(
  backendDecor: MapDecor | undefined | null,
  seed: string,
  kind: 'region' | 'city',
  nodeCorpus?: string,
): MapDecor {
  if (backendDecor) return backendDecor
  if (kind === 'city') return generateCityDecor(seed)

  // Région : choisir le générateur selon le biome inféré
  const biome = nodeCorpus ? inferRegionBiome(nodeCorpus) : 'default'
  switch (biome) {
    case 'coastal': return generateCoastalRegionDecor(seed)
    case 'mountain': return generateMountainRegionDecor(seed)
    case 'desert': return generateDesertRegionDecor(seed)
    default: return generateRegionDecor(seed)
  }
}
