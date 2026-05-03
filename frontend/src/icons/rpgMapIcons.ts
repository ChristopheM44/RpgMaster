import iconReferences from '@rpg-icons/icons-reference.json'
import type { CombatantState, PointOfInterest, SceneExit } from '../types'

export const RPG_MAP_ICON_IDS = [
  'player-pos',
  'ally-member',
  'ai-companion',
  'exit-dir',
  'secret-passage',
  'door',
  'poi',
  'clue',
  'trap-danger',
  'fog',
  'light',
  'ruins',
  'chest',
  'npc',
  'safe-zone',
  'unknown-zone',
  'c-ally',
  'c-active-turn',
  'c-selection',
  'c-move-tile',
  'c-move-dest',
  'c-atk-target',
  'c-spell-target',
  'c-enemy',
  'c-enemy-elite',
  'c-enemy-defeated',
  'c-enemy-flee',
  'c-enemy-surrender',
  'c-body-down',
  'c-obstacle',
  'c-half-cover',
  'c-full-cover',
  'c-difficult',
  'c-danger-zone',
  'c-aoe',
  'c-los',
] as const

export type RpgMapIconId = typeof RPG_MAP_ICON_IDS[number]
export type RpgMapIconVariant = 'color' | 'mono'
export type RpgMapIconState = 'normal' | 'hover' | 'active' | 'disabled'
export type RpgMapIconCategory = 'exploration' | 'combat-ally' | 'combat-enemy' | 'combat-terrain'
export type PoiSemanticRole =
  | 'enemy'
  | 'npc'
  | 'hazard'
  | 'cover'
  | 'loot'
  | 'exit'
  | 'passage'
  | 'clue'
  | 'fog'
  | 'light'
  | 'ruins'
  | 'safe'
  | 'unknown'
  | 'point'

export interface RpgMapIconDefinition {
  id: RpgMapIconId
  name: string
  category: RpgMapIconCategory
  color: string
  colorSrc: string
  monoSrc: string
}

interface RawIconReference {
  id: string
  name: string
  category: string
  color: string
  file_color: string
  file_mono: string
}

type CombatZone = { id: string; name: string; kind?: string; icon?: string; type?: string }
type ExitWithHints = SceneExit & { icon?: string; kind?: string; type?: string }
type CombatantWithRank = CombatantState & { rank?: string; role?: string; threat?: string; elite?: boolean }

const EXPLORATION_ICON_IDS = RPG_MAP_ICON_IDS.filter((id) => !id.startsWith('c-'))
const COMBAT_ICON_IDS = RPG_MAP_ICON_IDS.filter((id) => id.startsWith('c-'))
const iconIdSet = new Set<string>(RPG_MAP_ICON_IDS)
const explorationIconIdSet = new Set<string>(EXPLORATION_ICON_IDS)
const combatIconIdSet = new Set<string>(COMBAT_ICON_IDS)
const poiCompatibleCombatIconIdSet = new Set<RpgMapIconId>([
  'c-enemy',
  'c-enemy-elite',
  'c-enemy-defeated',
  'c-enemy-flee',
  'c-enemy-surrender',
  'c-body-down',
  'c-obstacle',
  'c-half-cover',
  'c-full-cover',
  'c-difficult',
  'c-danger-zone',
])

const colorIconModules = import.meta.glob('@rpg-icons/color/*.svg', {
  eager: true,
  import: 'default',
  query: '?url',
}) as Record<string, string>

const monoIconModules = import.meta.glob('@rpg-icons/mono/*.svg', {
  eager: true,
  import: 'default',
  query: '?url',
}) as Record<string, string>

const colorAssets = normalizeSvgAssets(colorIconModules)
const monoAssets = normalizeSvgAssets(monoIconModules)

export const rpgMapIconRegistry = buildRegistry(iconReferences as RawIconReference[])

export function isRpgMapIconId(value: unknown): value is RpgMapIconId {
  return typeof value === 'string' && iconIdSet.has(value)
}

export function resolveRpgMapIconId(value: unknown, fallback: RpgMapIconId = 'poi'): RpgMapIconId {
  return toKnownIconId(value) ?? fallback
}

export function resolveRpgMapIcon(value: unknown, fallback: RpgMapIconId = 'poi'): RpgMapIconDefinition {
  const iconId = resolveRpgMapIconId(value, fallback)
  return rpgMapIconRegistry[iconId] ?? rpgMapIconRegistry[fallback]
}

export function iconForPoi(poi: PointOfInterest): RpgMapIconId {
  const kindRole = roleFromKind(poi.kind)
  if (kindRole) return iconForPoiRole(kindRole, poi)

  const directIcon = toKnownPoiIconId(poi.icon)
  if (directIcon) return directIcon

  const iconRole = roleFromText(poi.icon)
  if (iconRole) return iconForPoiRole(iconRole, poi)

  const nameRole = roleFromText(poi.name)
  if (nameRole) return iconForPoiRole(nameRole, poi)

  const descriptionRole = roleFromText(poi.description)
  if (descriptionRole) return iconForPoiRole(descriptionRole, poi)

  return 'poi'
}

export function semanticRoleForPoi(poi: PointOfInterest): PoiSemanticRole {
  return roleFromKind(poi.kind)
    ?? roleFromText(poi.icon)
    ?? roleFromText(poi.name)
    ?? roleFromText(poi.description)
    ?? 'point'
}

export function iconForExit(exit: SceneExit): RpgMapIconId {
  const hintedExit = exit as ExitWithHints
  const directIcon = toKnownExplorationIconId(hintedExit.icon)
    ?? toKnownExplorationIconId(hintedExit.kind)
    ?? toKnownExplorationIconId(hintedExit.type)
  if (directIcon) return directIcon

  const search = normalizeText([
    hintedExit.icon,
    hintedExit.kind,
    hintedExit.type,
    exit.label,
    exit.leads_to,
    exit.description,
  ].filter(Boolean).join(' '))

  if (containsAny(search, ['secret', 'hidden', 'cache', 'passage'])) return 'secret-passage'
  if (containsAny(search, ['door', 'porte', 'gate', 'portail', 'grille', 'sas'])) return 'door'
  if (containsAny(search, ['unknown', 'inconnu', 'mystery', 'mystere'])) return 'unknown-zone'
  return 'exit-dir'
}

export function iconForPartyMember(options: { isCurrentPlayer?: boolean; isAi?: boolean }): RpgMapIconId {
  if (options.isCurrentPlayer) return 'player-pos'
  if (options.isAi) return 'ai-companion'
  return 'ally-member'
}

export function iconForCombatant(combatant: CombatantState): RpgMapIconId {
  const status = normalizeText(combatant.status)
  if (combatant.hp_current <= 0 || containsAny(status, ['defeated', 'vaincu', 'dead', 'mort'])) {
    return combatant.kind === 'monster' ? 'c-enemy-defeated' : 'c-body-down'
  }
  if (containsAny(status, ['fled', 'flee', 'fuite', 'escaped'])) return 'c-enemy-flee'
  if (containsAny(status, ['surrender', 'surrendered', 'rendu', 'capitule'])) return 'c-enemy-surrender'
  if (combatant.kind === 'monster') return isEliteCombatant(combatant) ? 'c-enemy-elite' : 'c-enemy'
  return 'c-ally'
}

export function iconForCombatZone(zone: CombatZone): RpgMapIconId {
  const directIcon = toKnownCombatIconId(zone.icon) ?? toKnownCombatIconId(zone.kind) ?? toKnownCombatIconId(zone.type)
  if (directIcon) return directIcon

  const search = normalizeText([zone.icon, zone.kind, zone.type, zone.name].filter(Boolean).join(' '))
  if (containsAny(search, ['full_cover', 'full cover', 'heavy cover', 'couvert lourd', 'total cover'])) return 'c-full-cover'
  if (containsAny(search, ['half_cover', 'half cover', 'partial cover', 'couvert partiel'])) return 'c-half-cover'
  if (containsAny(search, ['difficult', 'rough', 'terrain difficile', 'difficile', 'mud', 'boue'])) return 'c-difficult'
  if (containsAny(search, ['danger', 'hazard', 'trap', 'fire', 'flame', 'lava', 'poison', 'piege', 'brasier'])) return 'c-danger-zone'
  if (containsAny(search, ['line of sight', 'los', 'sight', 'vue', 'ligne'])) return 'c-los'
  if (containsAny(search, ['obstacle', 'block', 'blocked', 'mur', 'wall'])) return 'c-obstacle'
  return 'c-aoe'
}

function buildRegistry(rawReferences: RawIconReference[]): Record<RpgMapIconId, RpgMapIconDefinition> {
  const registry = {} as Record<RpgMapIconId, RpgMapIconDefinition>

  for (const reference of rawReferences) {
    const id = toKnownIconId(reference.id)
    if (!id) continue

    const colorSrc = colorAssets[id]
    const monoSrc = monoAssets[id]
    if (!colorSrc || !monoSrc) continue

    registry[id] = {
      id,
      name: reference.name,
      category: toKnownCategory(reference.category),
      color: reference.color,
      colorSrc,
      monoSrc,
    }
  }

  return registry
}

function normalizeSvgAssets(modules: Record<string, string>): Partial<Record<RpgMapIconId, string>> {
  const assets: Partial<Record<RpgMapIconId, string>> = {}
  for (const [path, url] of Object.entries(modules)) {
    const id = toKnownIconId(filenameWithoutExtension(path))
    if (id) assets[id] = url
  }
  return assets
}

function filenameWithoutExtension(path: string): string {
  const filename = path.split('/').at(-1) ?? path
  return filename.replace(/\.svg(?:\?.*)?$/, '')
}

function toKnownIconId(value: unknown): RpgMapIconId | null {
  if (typeof value !== 'string') return null
  const normalized = value.trim().toLowerCase().replace(/_/g, '-')
  return iconIdSet.has(normalized) ? normalized as RpgMapIconId : null
}

function toKnownExplorationIconId(value: unknown): RpgMapIconId | null {
  const iconId = toKnownIconId(value)
  return iconId && explorationIconIdSet.has(iconId) ? iconId : null
}

function toKnownCombatIconId(value: unknown): RpgMapIconId | null {
  const iconId = toKnownIconId(value)
  return iconId && combatIconIdSet.has(iconId) ? iconId : null
}

function toKnownPoiIconId(value: unknown): RpgMapIconId | null {
  const iconId = toKnownIconId(value)
  if (!iconId) return null
  if (explorationIconIdSet.has(iconId) || poiCompatibleCombatIconIdSet.has(iconId)) return iconId
  return null
}

function toKnownCategory(value: string): RpgMapIconCategory {
  if (value === 'combat-ally' || value === 'combat-enemy' || value === 'combat-terrain') return value
  return 'exploration'
}

function roleFromKind(value: unknown): PoiSemanticRole | null {
  return roleFromText(value, true)
}

function roleFromText(value: unknown, explicitKind = false): PoiSemanticRole | null {
  const search = normalizeText(value)
  if (!search) return null

  if (matchesAny(search, ['enemy', 'enemies', 'hostile', 'foe', 'monster', 'adversaire', 'ennemi', 'bandit', 'cultist', 'cultiste', 'zhentarim'])) return 'enemy'
  if (matchesAny(search, ['npc', 'pnj', 'personnage', 'villager', 'merchant', 'marchand', 'spy', 'espion', 'emissaire'])) return 'npc'
  if (matchesAny(search, ['hazard', 'danger', 'trap', 'piege', 'menace', 'staircase', 'stairs', 'escalier', 'trappe'])) return 'hazard'
  if (matchesAny(search, ['cover', 'couvert', 'half cover', 'full cover', 'barrel', 'barrels', 'baril', 'tonneau', 'tonneaux', 'barricade', 'crate', 'caisse'])) return 'cover'
  if (matchesAny(search, ['loot', 'chest', 'coffre', 'treasure', 'tresor', 'item', 'objet'])) return 'loot'
  if (matchesAny(search, ['secret', 'hidden', 'cache', 'passage'])) return 'passage'
  if (matchesAny(search, ['exit', 'sortie', 'issue', 'door', 'porte', 'gate', 'portail', 'grille', 'sas'])) return 'exit'
  if (matchesAny(search, ['clue', 'indice', 'hint', 'trace', 'investigate', 'examiner'])) return 'clue'
  if (matchesAny(search, ['mist', 'fog', 'brume', 'brouillard', 'smoke', 'fumee'])) return 'fog'
  if (matchesAny(search, ['lantern', 'light', 'lumiere', 'torch', 'torche'])) return 'light'
  if (matchesAny(search, ['rubble', 'ruin', 'ruins', 'debris', 'gravats', 'obstacle'])) return explicitKind ? 'cover' : 'ruins'
  if (matchesAny(search, ['safe', 'refuge', 'rest', 'camp', 'sanctuary', 'sanctuaire'])) return 'safe'
  if (matchesAny(search, ['unknown', 'inconnu', 'mystery', 'mystere'])) return 'unknown'
  return null
}

function iconForPoiRole(role: PoiSemanticRole, poi: PointOfInterest): RpgMapIconId {
  switch (role) {
    case 'enemy':
      return 'c-enemy'
    case 'npc':
      return 'npc'
    case 'hazard':
      return 'trap-danger'
    case 'cover':
      return coverIconForPoi(poi)
    case 'loot':
      return 'chest'
    case 'exit':
      return exitIconForPoi(poi)
    case 'passage':
      return passageIconForPoi(poi)
    case 'clue':
      return 'clue'
    case 'fog':
      return 'fog'
    case 'light':
      return 'light'
    case 'ruins':
      return 'ruins'
    case 'safe':
      return 'safe-zone'
    case 'unknown':
      return 'unknown-zone'
    case 'point':
      return 'poi'
  }
}

function coverIconForPoi(poi: PointOfInterest): RpgMapIconId {
  const search = normalizeText([poi.kind, poi.icon, poi.name].filter(Boolean).join(' '))
  if (matchesAny(search, ['full cover', 'couvert lourd', 'total cover'])) return 'c-full-cover'
  if (matchesAny(search, ['obstacle', 'blocked', 'block', 'mur', 'wall'])) return 'c-obstacle'
  return 'c-half-cover'
}

function exitIconForPoi(poi: PointOfInterest): RpgMapIconId {
  const search = normalizeText([poi.kind, poi.icon, poi.name].filter(Boolean).join(' '))
  if (matchesAny(search, ['secret', 'hidden', 'cache', 'passage'])) return 'secret-passage'
  if (matchesAny(search, ['door', 'porte', 'gate', 'portail', 'grille', 'sas'])) return 'door'
  return 'exit-dir'
}

function passageIconForPoi(poi: PointOfInterest): RpgMapIconId {
  const search = normalizeText([poi.kind, poi.icon, poi.name].filter(Boolean).join(' '))
  if (matchesAny(search, ['door', 'porte', 'gate', 'portail', 'grille', 'sas'])) return 'door'
  return 'secret-passage'
}

function isEliteCombatant(combatant: CombatantState): boolean {
  const withRank = combatant as CombatantWithRank
  if (withRank.elite) return true
  const search = normalizeText([
    withRank.rank,
    withRank.role,
    withRank.threat,
    combatant.status,
    combatant.name,
  ].filter(Boolean).join(' '))
  if (containsAny(search, ['elite', 'boss', 'champion', 'leader', 'chef'])) return true
  const cr = typeof combatant.cr === 'number' ? combatant.cr : Number.parseFloat(String(combatant.cr ?? ''))
  return Number.isFinite(cr) && cr >= 2
}

function containsAny(search: string, needles: string[]): boolean {
  return needles.some((needle) => search.includes(normalizeText(needle)))
}

function matchesAny(search: string, needles: string[]): boolean {
  const tokens = new Set(search.split(/\s+/).filter(Boolean))
  return needles.some((needle) => {
    const normalizedNeedle = normalizeText(needle)
    if (!normalizedNeedle) return false
    if (normalizedNeedle.includes(' ')) return ` ${search} `.includes(` ${normalizedNeedle} `)
    return tokens.has(normalizedNeedle)
  })
}

function normalizeText(value: unknown): string {
  if (typeof value !== 'string') return ''
  return value
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .toLowerCase()
    .replace(/[_-]+/g, ' ')
    .replace(/[^a-z0-9\s]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}
