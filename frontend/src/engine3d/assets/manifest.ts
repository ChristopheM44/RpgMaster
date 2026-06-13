// Manifest des modèles 3D CC0 (KayKit / Kenney) committés dans public/models/.
// Chaque clé est résolue par AssetRegistry ; toute résolution peut échouer →
// le fallback procédural prend le relais (invariant testé).

import type { ScatterKind } from '../core/ThemeProvider'

export interface ModelDef {
  /** Chemin relatif sous public/models/. */
  file: string
  /** 'height' = mise à l'échelle sur la hauteur cible ; 'footprint' = sur l'empreinte XZ. */
  fit: 'height' | 'footprint'
  animated?: boolean
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
  'prop/shelf_large': { file: 'dungeon/shelf_large.glb', fit: 'footprint' },
  'prop/shelf_small': { file: 'dungeon/shelf_small.glb', fit: 'footprint' },
  'prop/pillar': { file: 'dungeon/pillar.glb', fit: 'footprint' },
  'prop/rubble_large': { file: 'dungeon/rubble_large.glb', fit: 'footprint' },
  'prop/bed_frame': { file: 'dungeon/bed_frame.glb', fit: 'footprint' },
  'prop/stairs': { file: 'dungeon/stairs.glb', fit: 'footprint' },
  'prop/torch_lit': { file: 'dungeon/torch_lit.glb', fit: 'height' },
  // Nature (Kenney Nature Kit).
  'nature/tree_pine_a': { file: 'nature/tree_pine_a.glb', fit: 'height' },
  'nature/tree_pine_b': { file: 'nature/tree_pine_b.glb', fit: 'height' },
  'nature/tree_dark': { file: 'nature/tree_dark.glb', fit: 'height' },
  'nature/tree_palm_tall': { file: 'nature/tree_palm_tall.glb', fit: 'height' },
  'nature/tree_palm_bend': { file: 'nature/tree_palm_bend.glb', fit: 'height' },
  'nature/bush': { file: 'nature/bush.glb', fit: 'height' },
  'nature/bush_large': { file: 'nature/bush_large.glb', fit: 'height' },
  'nature/grass_large': { file: 'nature/grass_large.glb', fit: 'height' },
  'nature/flower_purple': { file: 'nature/flower_purple.glb', fit: 'height' },
  'nature/flower_yellow': { file: 'nature/flower_yellow.glb', fit: 'height' },
  'nature/mushroom_red': { file: 'nature/mushroom_red.glb', fit: 'height' },
  'nature/mushroom_tan': { file: 'nature/mushroom_tan.glb', fit: 'height' },
  'nature/rock_large_a': { file: 'nature/rock_large_a.glb', fit: 'height' },
  'nature/rock_large_b': { file: 'nature/rock_large_b.glb', fit: 'height' },
  'nature/rock_small_a': { file: 'nature/rock_small_a.glb', fit: 'height' },
  'nature/rock_small_b': { file: 'nature/rock_small_b.glb', fit: 'height' },
  'nature/stone_large_a': { file: 'nature/stone_large_a.glb', fit: 'height' },
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

// ─── PNJ : nom/description → modèle de personnage (défaut = pion) ────────────

const NPC_KEYWORDS: [RegExp, string][] = [
  [/garde|soldat|chevalier|capitaine|sentinelle|milicien|guard|knight|soldier/i, 'char/knight'],
  [/mage|sorci[èe]r|magicien|érudit|erudit|prêtre|pretre|prêtresse|oracle|wizard|witch|priest/i, 'char/mage'],
  [/encapuchonn|capuche|voleur|espion|mendiant|rôdeur|rodeur|hooded|thief|spy/i, 'char/rogue_hooded'],
  [/brute|colosse|forgeron|bûcheron|bucheron|barbare|blacksmith|brawler/i, 'char/barbarian'],
  [/marchand|aubergiste|tavernier|villageois|paysan|merchant|innkeep|villager/i, 'char/rogue'],
]

export function modelForNpc(corpus: string | null | undefined): string | null {
  if (!corpus) return null
  for (const [pattern, key] of NPC_KEYWORDS) {
    if (pattern.test(corpus)) return key
  }
  return null
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

const FURNITURE_KEYWORDS: [RegExp, string][] = [
  [/table|étal|etal|comptoir|bureau|autel/i, 'prop/table_medium'],
  [/banc|chaise|chair/i, 'prop/chair'],
  [/tabouret|stool/i, 'prop/stool'],
  [/tonneau|baril|barrel|fût|fut/i, 'prop/barrel_small'],
  [/keg|tonnelet/i, 'prop/keg'],
  [/caisse|crate|cageot/i, 'prop/crates_stacked'],
  [/coffre|chest|malle/i, 'prop/chest'],
  [/étag|etag|biblioth|shelf|rayonnage|armoire/i, 'prop/shelf_large'],
  [/lit|bed|couchette|paillasse/i, 'prop/bed_frame'],
  [/pilier|colonne|pillar|column/i, 'prop/pillar'],
  [/gravat|débris|debris|rubble|éboulis|eboulis/i, 'prop/rubble_large'],
]

export function modelForElement(kind: string, name: string, footprint: { x: number; z: number }): string | null {
  if (kind === 'furniture' || kind === 'cover' || kind === 'decor') {
    for (const [pattern, key] of FURNITURE_KEYWORDS) {
      if (pattern.test(name)) {
        if (key === 'prop/table_medium' && Math.max(footprint.x, footprint.z) >= 2.2) return 'prop/table_long'
        return key
      }
    }
    if (kind === 'cover') return 'prop/crates_stacked'
    return null
  }
  if (kind === 'light' && /torche|torch|brasero|brazier/i.test(name)) return 'prop/torch_lit'
  return null
}

// ─── Scatter : kind → variantes de modèles ───────────────────────────────────

export const SCATTER_MODELS: Record<ScatterKind, string[]> = {
  // tree_pine_c.glb n'a jamais été committé — variante retirée (fallback bruyant sinon).
  tree_pine: ['nature/tree_pine_a', 'nature/tree_pine_b'],
  tree_palm: ['nature/tree_palm_tall', 'nature/tree_palm_bend'],
  tree_dark: ['nature/tree_dark'],
  bush: ['nature/bush', 'nature/bush_large'],
  grass: ['nature/grass_large'],
  flower: ['nature/flower_purple', 'nature/flower_yellow'],
  mushroom: ['nature/mushroom_red', 'nature/mushroom_tan'],
  rock: ['nature/rock_large_a', 'nature/rock_large_b'],
  stone: ['nature/rock_small_a', 'nature/rock_small_b', 'nature/stone_large_a'],
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
