// Manifest des modèles 3D CC0 (KayKit / Kenney) committés dans public/models/.
// Chaque clé est résolue par AssetRegistry ; toute résolution peut échouer →
// le fallback procédural prend le relais (invariant testé).

import type { ScatterKind } from '../core/ThemeProvider'
import type { ElementTint } from '../types'
import { hashSeed } from '../utils/seededRandom'
import { CATALOG_ELEMENT_KINDS, PROCEDURAL_PROP_KEYS, PROP_RULES, TINT_RULES } from './propCatalog.generated'

export interface ModelDef {
  /** Chemin relatif sous public/models/. */
  file: string
  /** 'height' = mise à l'échelle sur la hauteur cible ; 'footprint' = sur l'empreinte XZ. */
  fit: 'height' | 'footprint'
  animated?: boolean
  /** Rotation Y (rad) additionnelle si l'axe avant du modèle ne suit pas la convention +Z du moteur. */
  rotationOffsetY?: number
}

export const MODEL_MANIFEST: Record<string, ModelDef> = {
  // Personnages (KayKit Adventurers — rigged, clips Idle/Walking).
  'char/knight': { file: 'adventurers/knight.glb', fit: 'height', animated: true },
  'char/barbarian': { file: 'adventurers/barbarian.glb', fit: 'height', animated: true },
  'char/mage': { file: 'adventurers/mage.glb', fit: 'height', animated: true },
  'char/rogue': { file: 'adventurers/rogue.glb', fit: 'height', animated: true },
  'char/rogue_hooded': { file: 'adventurers/rogue_hooded.glb', fit: 'height', animated: true },
  // Monstres (KayKit Skeletons).
  'monster/skeleton_warrior': { file: 'skeletons/skeleton_warrior.glb', fit: 'height', animated: true },
  'monster/skeleton_mage': { file: 'skeletons/skeleton_mage.glb', fit: 'height', animated: true },
  'monster/skeleton_rogue': { file: 'skeletons/skeleton_rogue.glb', fit: 'height', animated: true },
  'monster/skeleton_minion': { file: 'skeletons/skeleton_minion.glb', fit: 'height', animated: true },
  // Props (KayKit Dungeon Remastered).
  'prop/wall': { file: 'dungeon/wall.glb', fit: 'footprint' },
  'prop/wall_corner': { file: 'dungeon/wall_corner.glb', fit: 'footprint' },
  'prop/table_medium': { file: 'dungeon/table_medium.glb', fit: 'footprint' },
  'prop/table_long': { file: 'dungeon/table_long.glb', fit: 'footprint' },
  'prop/table_small': { file: 'dungeon/table_small.glb', fit: 'footprint' },
  'prop/chair': { file: 'dungeon/chair.glb', fit: 'footprint' },
  'prop/stool': { file: 'dungeon/stool.glb', fit: 'footprint' },
  'prop/keg': { file: 'dungeon/keg.glb', fit: 'footprint' },
  'prop/barrel_small': { file: 'dungeon/barrel_small.glb', fit: 'footprint' },
  'prop/barrel_large': { file: 'dungeon/barrel_large.glb', fit: 'footprint' },
  'prop/crates_stacked': { file: 'dungeon/crates_stacked.glb', fit: 'footprint' },
  'prop/chest': { file: 'dungeon/chest.glb', fit: 'footprint' },
  'prop/chest_gold': { file: 'dungeon/chest_gold.glb', fit: 'footprint' },
  'prop/shelf_large': { file: 'dungeon/shelf_large.glb', fit: 'footprint' },
  'prop/shelf_small': { file: 'dungeon/shelf_small.glb', fit: 'footprint' },
  'prop/pillar': { file: 'dungeon/pillar.glb', fit: 'footprint' },
  'prop/rubble_large': { file: 'dungeon/rubble_large.glb', fit: 'footprint' },
  'prop/bed_frame': { file: 'dungeon/bed_frame.glb', fit: 'footprint' },
  // stairs.glb monte vers -Z (l'extrémité haute est en Z=0) : inverse de la
  // convention +Z attendue par plusZRotationToFacing, d'où l'offset de 180°.
  'prop/stairs': { file: 'dungeon/stairs.glb', fit: 'footprint', rotationOffsetY: Math.PI },
  'prop/door': { file: 'dungeon/wall_doorway.glb', fit: 'footprint' },
  'prop/torch_lit': { file: 'dungeon/torch_lit.glb', fit: 'height' },
  'prop/torch_mounted': { file: 'dungeon/torch_mounted.glb', fit: 'height' },
  // Décor d'extérieur / campement (Kenney Nature Kit).
  'prop/campfire': { file: 'nature/campfire.glb', fit: 'footprint' },
  'prop/tent': { file: 'nature/tent.glb', fit: 'footprint' },
  'prop/pot': { file: 'nature/pot.glb', fit: 'footprint' },
  'prop/statue': { file: 'nature/statue.glb', fit: 'height' },
  'prop/obelisk': { file: 'nature/obelisk.glb', fit: 'height' },
  // Nature — KayKit Forest (migration du scatter tempéré, cf. nature/forest/).
  'nature/tree_pine_a': { file: 'nature/forest/Tree_4_A_Color1.gltf', fit: 'height' },
  'nature/tree_pine_b': { file: 'nature/forest/Tree_4_B_Color1.gltf', fit: 'height' },
  'nature/tree_dark': { file: 'nature/forest/Tree_Bare_1_A_Color1.gltf', fit: 'height' },
  'nature/bush': { file: 'nature/forest/Bush_1_A_Color1.gltf', fit: 'height' },
  'nature/bush_large': { file: 'nature/forest/Bush_2_A_Color1.gltf', fit: 'height' },
  'nature/grass_large': { file: 'nature/forest/Grass_1_A_Color1.gltf', fit: 'height' },
  'nature/grass_small': { file: 'nature/forest/Grass_2_A_Color1.gltf', fit: 'height' },
  'nature/rock_large_a': { file: 'nature/forest/Rock_1_A_Color1.gltf', fit: 'height' },
  'nature/rock_large_b': { file: 'nature/forest/Rock_3_A_Color1.gltf', fit: 'height' },
  'nature/rock_small_a': { file: 'nature/forest/Rock_2_A_Color1.gltf', fit: 'height' },
  'nature/rock_small_b': { file: 'nature/forest/Rock_2_B_Color1.gltf', fit: 'height' },
  // Nature — Kenney Nature Kit (pas d'équivalent dans KayKit Forest : palmier, fleurs,
  // champignons, souche/rondin, cactus, nénuphar).
  'nature/tree_palm_tall': { file: 'nature/tree_palm_tall.glb', fit: 'height' },
  'nature/tree_palm_bend': { file: 'nature/tree_palm_bend.glb', fit: 'height' },
  'nature/flower_purple': { file: 'nature/flower_purple.glb', fit: 'height' },
  'nature/flower_yellow': { file: 'nature/flower_yellow.glb', fit: 'height' },
  'nature/mushroom_red': { file: 'nature/mushroom_red.glb', fit: 'height' },
  'nature/mushroom_tan': { file: 'nature/mushroom_tan.glb', fit: 'height' },
  'nature/stump': { file: 'nature/stump.glb', fit: 'height' },
  'nature/log': { file: 'nature/log.glb', fit: 'height' },
  'nature/cactus_short': { file: 'nature/cactus_short.glb', fit: 'height' },
  'nature/cactus_tall': { file: 'nature/cactus_tall.glb', fit: 'height' },
  'nature/lily': { file: 'nature/lily.glb', fit: 'height' },
}

// ─── Personnages : classe D&D → modèle ───────────────────────────────────────

const CLASS_MODEL: Record<string, string> = {
  fighter: 'char/knight',
  paladin: 'char/knight',
  cleric: 'char/knight',
  barbarian: 'char/barbarian',
  monk: 'char/barbarian',
  wizard: 'char/mage',
  sorcerer: 'char/mage',
  warlock: 'char/mage',
  rogue: 'char/rogue',
  bard: 'char/rogue',
  ranger: 'char/rogue_hooded',
  druid: 'char/rogue_hooded',
}

// Les adapters reçoivent parfois le libellé FR (ExHero.cls) — on remappe.
const CLASS_FR_TO_RAW: Record<string, string> = {
  guerrier: 'fighter',
  mage: 'wizard',
  magicien: 'wizard',
  clerc: 'cleric',
  roublard: 'rogue',
  rodeur: 'ranger',
  rôdeur: 'ranger',
  paladin: 'paladin',
  barbare: 'barbarian',
  barde: 'bard',
  druide: 'druid',
  moine: 'monk',
  ensorceleur: 'sorcerer',
  occultiste: 'warlock',
}

export function modelForClass(charClass: string | null | undefined): string | null {
  if (!charClass) return null
  const lower = charClass.trim().toLowerCase()
  const raw = CLASS_MODEL[lower] ? lower : CLASS_FR_TO_RAW[lower]
  return raw ? CLASS_MODEL[raw] ?? null : null
}

// ─── PNJ : nom/description → modèle de personnage ───────────────────────────
// Buckets distinctifs d'abord (silhouette nette) ; tout le reste tombe sur le
// défaut « quidam » plutôt que sur un pion abstrait.

const NPC_KEYWORDS: [RegExp, string][] = [
  [/garde|soldat|chevalier|capitaine|sentinelle|milicien|paladin|templier|v[ée]t[ée]ran|officier|lieutenant|gardien|l[ée]gionnaire|guerrier|guard|knight|soldier|warrior|guardian/i, 'char/knight'],
  [/mage|sorci[èe]r|magicien|[ée]rudit|pr[êe]tre|oracle|enchanteur|alchimiste|astrologue|gu[ée]risseur|archimage|occultiste|apothicaire|mystique|devineresse|wizard|witch|priest|sorcerer|warlock|cleric/i, 'char/mage'],
  [/encapuchonn|capuche|voleur|espion|mendiant|r[ôo]deur|assassin|chasseur|pisteur|traqueur|contrebandier|vagabond|p[èe]lerin|ermite|cultiste|moine|nomade|[ée]claireur|hooded|thief|spy|ranger|scout|hunter/i, 'char/rogue_hooded'],
  [/brute|colosse|forgeron|b[ûu]cheron|barbare|gladiateur|lutteur|docker|charpentier|costaud|blacksmith|brawler|smith/i, 'char/barbarian'],
  [/marchand|aubergiste|tavernier|villageois|paysan|noble|dame|seigneur|femme|vieil|vieux|enfant|fermi[èe]r|p[êe]cheur|artisan|boulanger|m[ée]nestrel|barde|conteur|matelot|scribe|bourgeois|citadin|habitant|herboriste|merchant|innkeep|villager|peasant|farmer|bard/i, 'char/rogue'],
]

// Apparences « tout-venant » pour un PNJ sans rôle reconnaissable : un humanoïde
// crédible (le backend n'envoie souvent qu'un nom, cf. _make_npc_poi) au lieu du pion.
// Volontairement des silhouettes « gens ordinaires » (pas le barbare torse nu, qui
// jurerait pour un·e villageois·e ou un ancien).
const COMMONER_MODELS = ['char/rogue', 'char/rogue_hooded'] as const

export function modelForNpc(corpus: string | null | undefined): string | null {
  if (!corpus) return null
  for (const [pattern, key] of NPC_KEYWORDS) {
    if (pattern.test(corpus)) return key
  }
  // Défaut déterministe par hash du corpus : même PNJ = même apparence stable,
  // tout en variant entre PNJ anonymes. Plus jamais de pion pour un PNJ.
  return COMMONER_MODELS[hashSeed(corpus) % COMMONER_MODELS.length] ?? 'char/rogue'
}

// ─── Monstres : espèce/nom → modèle (défaut = pion procédural) ───────────────

export function modelForMonster(corpus: string | null | undefined): string | null {
  if (!corpus) return null
  const search = corpus.toLowerCase()
  if (/lich|liche|necroman/.test(search)) return 'monster/skeleton_mage'
  if (/squelette.*(arc|mage)|skeleton.*(mage|arch)/.test(search)) return 'monster/skeleton_mage'
  if (/squelette|skelet|undead|mort-vivant|revenant|zombi/.test(search)) return 'monster/skeleton_warrior'
  // Approximations humanoïdes — silhouette crédible faute de modèle dédié.
  // Le rôle de lanceur (chamane…) prime sur l'espèce (gnoll…).
  if (/chamane|shaman|cultiste|cultist|sorci[èe]r|warlock|n[ée]cromant/.test(search)) return 'monster/skeleton_mage'
  if (/gobelin|goblin|kobold|diablotin|imp\b|gremlin/.test(search)) return 'monster/skeleton_minion'
  if (/orc|ogre|troll|gnoll|hobgobelin|hobgoblin|bugbear/.test(search)) return 'monster/skeleton_warrior'
  if (/assassin|éclaireur|eclaireur|scout|stalker|spectre|wraith|ombre|shadow/.test(search)) return 'monster/skeleton_rogue'
  // Bêtes (loup, araignée, ours…) : pion procédural — un squelette serait pire.
  return null
}

// ─── Éléments : kind + nom → prop ────────────────────────────────────────────
// Catalogue sémantique PARTAGÉ avec le backend (source : backend/app/engine/
// prop_catalog.py, généré dans propCatalog.generated.ts). Le backend écrit déjà
// l'asset_key correspondant au nom (y compris pour les scènes sauvegardées, au
// rechargement) ; cette résolution sert de repli quand aucun asset_key n'est fourni.

const PROCEDURAL_KEYS = new Set<string>(PROCEDURAL_PROP_KEYS)
const ELEMENT_TINTS = new Set<string>(TINT_RULES.map(([tint]) => tint))

export function isModelKey(key: string | null | undefined): key is string {
  return typeof key === 'string' && MODEL_MANIFEST[key] != null
}

/** Clé dessinée par ProceduralFactory (fontaine, autel, sarcophage…), pas un GLB. */
export function isProceduralPropKey(key: string | null | undefined): key is string {
  return typeof key === 'string' && PROCEDURAL_KEYS.has(key)
}

/** Clé d'asset acceptée par le moteur : modèle du manifeste ou prop procédural. */
export function isPropKey(key: string | null | undefined): key is string {
  return isModelKey(key) || isProceduralPropKey(key)
}

export function isElementTint(value: unknown): value is ElementTint {
  return typeof value === 'string' && ELEMENT_TINTS.has(value)
}

/** Texte désaccentué, minuscule, mots séparés par une espace, bordé d'espaces (miroir Python). */
export function normalizeWords(text: string | null | undefined): string {
  const stripped = (text ?? '').toLowerCase().normalize('NFD').replace(/\p{M}+/gu, '')
  return ` ${stripped.replace(/[^a-z0-9]+/g, ' ').trim()} `
}

function hasKeyword(words: string, keywords: readonly string[]): boolean {
  return keywords.some((keyword) => words.includes(` ${keyword}`))
}

/** Clé d'asset du premier mot-clé reconnu dans le nom, sinon null (miroir de match_prop). */
export function matchProp(text: string | null | undefined): string | null {
  const words = normalizeWords(text)
  for (const rule of PROP_RULES) {
    if (hasKeyword(words, rule.any) && (rule.requires.length === 0 || hasKeyword(words, rule.requires))) {
      return rule.assetKey
    }
  }
  return null
}

/** Teinte de matière évoquée par le texte (pétrifié, calciné…), sinon null (miroir de match_tint). */
export function matchTint(text: string | null | undefined): ElementTint | null {
  const words = normalizeWords(text)
  for (const [tint, keywords] of TINT_RULES) {
    if (hasKeyword(words, keywords) && isElementTint(tint)) return tint
  }
  return null
}

export function modelForElement(kind: string, name: string, footprint: { x: number; z: number }): string | null {
  if (kind === 'wall') return /angle|corner|coin/i.test(name) ? 'prop/wall_corner' : 'prop/wall'
  if (kind === 'door') return 'prop/door'
  if (CATALOG_ELEMENT_KINDS.includes(kind)) {
    const key = matchProp(name)
    // Pas de correspondance → procédural neutre (plus de repli « couvert = caisses »).
    return key ? refineByFootprint(key, footprint) : null
  }
  if (kind === 'light') {
    if (/feu de camp|foyer|bivouac|brasier/i.test(name)) return 'prop/campfire'
    if (/murale|applique|wall|mounted/i.test(name)) return 'prop/torch_mounted'
    if (/torche|torch|brasero|brazier|flambeau|chandelier/i.test(name)) return 'prop/torch_lit'
    return null
  }
  if (kind === 'stairs') return 'prop/stairs'
  return null
}

/** Variante de prop selon l'empreinte — active table_small / barrel_large / shelf_small. */
export function refineByFootprint(key: string, footprint: { x: number; z: number }): string {
  const span = Math.max(footprint.x, footprint.z)
  if (key === 'prop/table_medium') {
    if (span >= 2.2) return 'prop/table_long'
    if (span <= 1.1) return 'prop/table_small'
  } else if (key === 'prop/barrel_small' && span >= 1.4) {
    return 'prop/barrel_large'
  } else if (key === 'prop/shelf_large' && span <= 1.1) {
    return 'prop/shelf_small'
  }
  return key
}

/**
 * Props verticaux instanciés à une hauteur INTRINSÈQUE (mètres) plutôt qu'ajustés
 * à l'empreinte : une statue dans une empreinte 1×1 serait sinon écrasée par le
 * plafond `maxHeight` (dérivé du défaut `decor` = 0.6 m). Consommé par ElementsLayer.
 */
export const PROP_TARGET_HEIGHT_M: Record<string, number> = {
  'prop/statue': 2.2,
  'prop/obelisk': 2.8,
  // Végétation posée comme élément (arbre pétrifié, buisson…) : hauteur réelle,
  // sinon le plafond du kind `decor` (0,6 m) en ferait des bonsaïs.
  'nature/tree_dark': 3.4,
  'nature/tree_pine_a': 3.4,
  'nature/tree_palm_tall': 3.2,
  'nature/cactus_tall': 1.5,
  'nature/bush': 0.9,
  'nature/grass_large': 0.6,
  'nature/stump': 0.55,
}

/**
 * Hauteur minimale (mètres) admise pour un meuble ajusté à l'empreinte : le plafond
 * `maxHeight` dérive du kind (mobilier 0,8 m) et écraserait un rayonnage ou un pilier.
 */
export const PROP_MIN_HEIGHT_M: Record<string, number> = {
  'prop/shelf_large': 2.2,
  'prop/shelf_small': 1.8,
  'prop/pillar': 2.8,
  'prop/tent': 2.2,
}

// ─── Scatter : kind → variantes de modèles ───────────────────────────────────

export const SCATTER_MODELS: Record<ScatterKind, string[]> = {
  // tree_pine_c.glb n'a jamais été committé — variante retirée (fallback bruyant sinon).
  tree_pine: ['nature/tree_pine_a', 'nature/tree_pine_b'],
  tree_palm: ['nature/tree_palm_tall', 'nature/tree_palm_bend'],
  tree_dark: ['nature/tree_dark'],
  bush: ['nature/bush', 'nature/bush_large'],
  grass: ['nature/grass_large', 'nature/grass_small'],
  flower: ['nature/flower_purple', 'nature/flower_yellow'],
  mushroom: ['nature/mushroom_red', 'nature/mushroom_tan'],
  rock: ['nature/rock_large_a', 'nature/rock_large_b'],
  stone: ['nature/rock_small_a', 'nature/rock_small_b'],
  stump: ['nature/stump'],
  log: ['nature/log'],
  cactus: ['nature/cactus_short', 'nature/cactus_tall'],
  lily: ['nature/lily'],
  crate: ['prop/crates_stacked', 'prop/barrel_small'],
  torch: ['prop/torch_lit'],
}

/** Hauteurs cibles (mètres) par famille de scatter — randomisées ±25 % ensuite. */
export const SCATTER_TARGET_HEIGHT_M: Record<ScatterKind, number> = {
  tree_pine: 3.4,
  tree_palm: 3.2,
  tree_dark: 3.8,
  bush: 0.7,
  grass: 0.35,
  flower: 0.4,
  mushroom: 0.35,
  rock: 0.8,
  stone: 0.45,
  stump: 0.45,
  log: 0.35,
  cactus: 1.1,
  lily: 0.06,
  crate: 0.9,
  torch: 1.6,
}
