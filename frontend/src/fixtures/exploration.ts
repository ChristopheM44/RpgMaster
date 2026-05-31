// Fixtures Exploration V2 — données seed pour la démo Diptyque
// TODO: brancher backend (remplacer par WS events + REST quand l'API sera prête)

export interface ExHero {
  id: string
  token: string
  name: string
  cls: string
  species: string
  hp: number
  hpMax: number
  ai: boolean
  isMe?: boolean
  color: string
  pos: string
  x: number
  y: number
}

export interface ExPoi {
  id: string
  kind:
    | 'npc'
    | 'clue'
    | 'hazard'
    | 'cover'
    | 'loot'
    | 'exit'
    | 'passage'
    | 'fog'
    | 'light'
    | 'ruins'
    | 'safe'
    | 'unknown'
    | 'point'
    | 'sortie'
  x: number
  y: number
  label: string
  title: string
  desc: string
  skill?: string
  dc?: number
  dest?: string
  iconId?: string
  iconSymbol?: string
  actionLabel?: string
  interactionId?: string
  prompt?: string
  intent?: string
  rawKind?: string
  rawIcon?: string
  elementId?: string
  state?: string
  visibility?: 'visible' | 'subtle' | 'hidden'
  discovered?: boolean
  physicalState?: string
  facts?: string[]
  tone: 'blood' | 'arcane' | 'teal' | 'gold' | 'text'
  active?: boolean
}

export interface ExLegendItem {
  kind: 'hero' | 'poi' | 'exit'
  id: string
  label: string
  sub: string
  ref: string
}

export interface ExRoll {
  label: string
  value: number
  hit: boolean
  critical?: boolean
}

export interface ExDecisionOption {
  id: string
  label: string
  icon: string
  tone: 'gold' | 'teal' | 'blood' | 'arcane'
}

export type ExNarrativeEntry =
  | { id: number; type: 'divider'; text: string }
  | { id: number; type: 'gm'; text: string; refs?: string[] }
  | { id: number; type: 'player'; who: string; text: string; refs?: string[] }
  | { id: number; type: 'dialogue'; who: string; text: string; speakerKind?: 'companion' | 'npc' }
  | { id: number; type: 'roll'; who: string; what: string; rolls: ExRoll[]; result?: string; detail?: string }
  | { id: number; type: 'decision'; who: string; text: string; options: ExDecisionOption[] }
  | {
      id: number; type: 'combat'
      attacker: string; target: string
      d20: number; attackRoll: number; targetAc: number
      hit: boolean; damage: number | null; critical?: boolean
    }
  | { id: number; type: 'system'; text: string }

export interface ExQuest {
  id: string
  kind: 'principale' | 'secondaire' | 'rumeur'
  title: string
  desc: string
  progress: number
  steps: number | null
  due?: string
}

export interface ExMemoryEntry {
  kind: 'PNJ' | 'Lieu'
  name: string
  detail: string
  tag: string
}

export interface ExTownBuilding {
  id: string
  x: number
  y: number
  w: number
  h: number
  label: string
  tag: 'sûr' | 'objectif' | 'neutre' | 'danger'
  pin: string
}

export interface ExTown {
  name: string
  buildings: ExTownBuilding[]
  roads: string[]
}

export interface ExRegionPin {
  id: string
  x: number
  y: number
  label: string
  tag: 'sûr' | 'active' | 'danger' | 'rumeur' | 'neutre'
  state: 'visited' | 'here' | 'destination' | 'known' | 'rumor'
}

export interface ExRegion {
  pins: ExRegionPin[]
  roads: string[]
}

// ── Personnages (5 héros, 1 joueur + 4 IA compagnons) ───────────────────
// TODO: brancher backend — viendra de characterStore.sessionCharacters
export const EX_PARTY: ExHero[] = [
  { id: 'thorvald', token: 'T',  name: 'Thorvald', cls: 'Guerrier', species: 'Humain',    hp: 12, hpMax: 12, ai: false, isMe: true, color: '#ff8247', pos: 'F7', x: 5, y: 6 },
  { id: 'elara',    token: 'EL', name: 'Elara',    cls: 'Rôdeuse',  species: 'Elfe',      hp: 11, hpMax: 11, ai: true,  color: '#c090ff', pos: 'E6', x: 4, y: 5 },
  { id: 'solana',   token: 'SO', name: 'Solana',   cls: 'Clerc',    species: 'Humaine',   hp: 10, hpMax: 10, ai: true,  color: '#c090ff', pos: 'F6', x: 5, y: 5 },
  { id: 'shade',    token: 'S',  name: 'Shade',    cls: 'Roublard', species: 'Demi-elfe', hp: 10, hpMax: 10, ai: true,  color: '#c090ff', pos: 'F8', x: 5, y: 7 },
  { id: 'oaken',    token: 'O',  name: 'Oaken',    cls: 'Druide',   species: 'Demi-elfe', hp:  9, hpMax: 10, ai: true,  color: '#c090ff', pos: 'E8', x: 4, y: 7 },
]

// ── Repères et sorties sur la carte de scène ────────────────────────────
// TODO: brancher backend — viendra de gameStore.currentScene.pois / .exits
export const EX_POIS: ExPoi[] = [
  { id: 'H1', kind: 'hazard', x: 1,  y: 2, label: 'H1', title: 'Chariot renversé',
    desc: "Deux chevaux abattus, traces de pas en zigzag vers l'est. Sang frais.",
    skill: 'Investigation', dc: 12, tone: 'blood' },
  { id: 'H4', kind: 'clue', x: 7,  y: 3, label: 'H4', title: 'Lueurs sous les arbres',
    desc: 'Une faible lumière froide pulse à intervalles réguliers entre deux pins.',
    skill: 'Arcanes', dc: 14, tone: 'arcane' },
  { id: 'H2', kind: 'npc', x: 5,  y: 4, label: 'H2', title: 'Corps allongé',
    desc: 'Un humain en armure de cuir, immobile. Respiration faible.',
    skill: 'Médecine', dc: 10, tone: 'teal' },
  { id: 'H7', kind: 'sortie', x: 0,  y: 7, label: 'H7', title: 'Retour vers Phandalin',
    desc: "La piste s'élargit et redescend vers la plaine.", dest: 'Phandalin', tone: 'teal' },
  { id: 'H6', kind: 'sortie', x: 11, y: 7, label: 'H6', title: "S'enfoncer davantage",
    desc: "La piste s'enfonce encore plus profondément dans les bois.",
    dest: 'Repaire_cragmaw', tone: 'gold', active: true },
]

// ── Légende (compactée) ─────────────────────────────────────────────────
export const EX_LEGEND: ExLegendItem[] = [
  { kind: 'hero', id: 'thorvald', label: 'Thorvald', sub: 'Membre du groupe',  ref: 'F7' },
  { kind: 'hero', id: 'elara',    label: 'Elara',    sub: 'Compagnon IA',       ref: 'E6' },
  { kind: 'hero', id: 'solana',   label: 'Solana',   sub: 'Compagnon IA',       ref: 'F6' },
  { kind: 'hero', id: 'shade',    label: 'Shade',    sub: 'Compagnon IA',       ref: 'F8' },
  { kind: 'hero', id: 'oaken',    label: 'Oaken',    sub: 'Compagnon IA',       ref: 'E8' },
  { kind: 'poi',  id: 'H1',       label: 'Chariot renversé',      sub: 'Repère · investigation', ref: 'B3' },
  { kind: 'poi',  id: 'H2',       label: 'Corps allongé',          sub: 'Repère · médecine',      ref: 'F5' },
  { kind: 'poi',  id: 'H4',       label: 'Lueurs sous les arbres', sub: 'Repère · arcanes',       ref: 'H4' },
  { kind: 'exit', id: 'H7',       label: 'Retour vers Phandalin',  sub: 'Sortie ouest',           ref: 'A8' },
  { kind: 'exit', id: 'H6',       label: "S'enfoncer davantage",   sub: 'Sortie est',             ref: 'L8' },
]

// ── Récit (entrées avec entités linkées map↔texte) ──────────────────────
// TODO: brancher backend — viendra de gameStore.narrativeLog avec mapping refs
export const EX_NARRATIVE: ExNarrativeEntry[] = [
  { id: 1, type: 'divider', text: 'Triboar Trail · Matin · Jour 1' },
  { id: 2, type: 'gm',
    text: "La piste s'élargit entre deux vieux pins, jonchée de feuilles humides. Un chariot renversé barre le passage : deux chevaux abattus dans leurs harnais, et des traces de pas en zigzag qui filent vers l'est, vers le cœur des bois.",
    refs: ['H1'] },
  { id: 3, type: 'player', who: 'Thorvald',
    text: "Je m'agenouille près du chariot. Quelqu'un a essayé de défendre la cargaison — ou de la cacher. Vous voyez ces traces ? Elles sont fraîches.",
    refs: ['H1'] },
  { id: 4, type: 'roll', who: 'Thorvald', what: 'Investigation · DD 12',
    rolls: [{ label: '1d20+2', value: 19, hit: true }], result: 'Succès',
    detail: 'Cargaison disparue, traces de bottes ferrées et de pieds plus petits (gobelins ?).' },
  { id: 5, type: 'player', who: 'Elara',
    text: "Plus loin, sous les arbres, je vois une lueur qui pulse. Quelque chose d'arcanique. Ça ne devrait pas être là.",
    refs: ['H4'] },
  { id: 6, type: 'dialogue', who: 'Sildar',
    text: "Trouvez Gundren… il était avec moi sur la piste.",
    speakerKind: 'npc' },
  { id: 7, type: 'dialogue', who: 'Elara',
    text: "Je le connais. On va vous sortir de là, promis.",
    speakerKind: 'companion' },
  { id: 8, type: 'roll', who: 'Elara', what: 'Perception · DD 14',
    rolls: [{ label: '1d20+4', value: 20, hit: true, critical: true }], result: 'Critique !',
    detail: 'Elara détecte un battement de cœur dans les fourrés — des gobelins en embuscade.' },
  { id: 9, type: 'gm',
    text: "Oaken s'approche du corps en armure de cuir et pose deux doigts sur sa gorge. Encore en vie, mais à peine. Sa main serre quelque chose — un petit médaillon en cuivre frappé d'une serre de loup.",
    refs: ['H2', 'oaken'] },
  { id: 10, type: 'system', text: 'Initiative lancée. Krell commence.' },
  { id: 11, type: 'decision', who: 'Le groupe',
    text: "Choisir une direction. La piste continue vers l'est ; le retour mène à Phandalin.",
    options: [
      { id: 'H6', label: "S'enfoncer davantage", icon: '↦', tone: 'gold' },
      { id: 'H7', label: 'Retour à Phandalin',    icon: '↤', tone: 'teal' },
    ] },
]

// ── Quêtes en cours ─────────────────────────────────────────────────────
// TODO: brancher backend — viendra de gameStore.quests
export const EX_QUESTS: ExQuest[] = [
  { id: 'main',  kind: 'principale',
    title: "Livrer le chariot à Barthen's Provisions",
    desc: "Une aventure d'exploration et de mystère sur la Côte des Épées, où la redécouverte d'une mine antique cache des secrets bien plus sombres et anciens que prévu.",
    progress: 2, steps: 5, due: 'Avant la nuit' },
  { id: 'side',  kind: 'secondaire',
    title: 'Retrouver Gundren Rockseeker',
    desc: 'Le nain qui a engagé le groupe a disparu sur la même piste, il y a deux jours.',
    progress: 0, steps: 3 },
  { id: 'rumor', kind: 'rumeur',
    title: 'Le médaillon en serre de loup',
    desc: 'Plusieurs cadavres trouvés sur les routes portent le même médaillon.',
    progress: 0, steps: null },
]

// ── Carnet du chroniqueur ───────────────────────────────────────────────
// TODO: brancher backend — viendra de gameStore.chronicle
export const EX_MEMORY: ExMemoryEntry[] = [
  { kind: 'PNJ',  name: 'Gundren Rockseeker', detail: 'Nain marchand — disparu',                tag: 'à explorer' },
  { kind: 'PNJ',  name: 'Sildar Hallwinter',  detail: 'Garde de Neverwinter — blessé sur la piste', tag: 'allié' },
  { kind: 'Lieu', name: 'Phandalin',          detail: "Village — point d'origine",              tag: 'sûr' },
  { kind: 'Lieu', name: 'Repaire de Cragmaw', detail: 'Gobelinoïdes hostiles présumés',         tag: 'danger' },
]

// ── Ville (Phandalin) ───────────────────────────────────────────────────
// TODO: brancher backend — viendra de gameStore.cityMaps[activeCityId]
export const EX_TOWN: ExTown = {
  name: 'Phandalin',
  buildings: [
    { id: 'stonehill',  x: 38, y: 52, w: 14, h:  8, label: 'Stonehill Inn',         tag: 'sûr',      pin: '★' },
    { id: 'barthen',    x: 18, y: 36, w: 16, h: 10, label: "Barthen's Provisions",  tag: 'objectif', pin: '✦' },
    { id: 'townmaster', x: 56, y: 38, w: 12, h:  8, label: "Townmaster's Hall",     tag: 'neutre',   pin: '◇' },
    { id: 'shrine',     x: 24, y: 18, w: 10, h:  6, label: 'Shrine of Luck',        tag: 'neutre',   pin: '✺' },
    { id: 'tresendar',  x: 70, y: 16, w: 18, h: 10, label: 'Manoir Tresendar',      tag: 'danger',   pin: '✕' },
    { id: 'lionshield', x: 48, y: 62, w: 12, h:  7, label: 'Lionshield Coster',     tag: 'neutre',   pin: '◈' },
    { id: 'miner',      x: 64, y: 60, w: 12, h:  7, label: "Miner's Exchange",      tag: 'neutre',   pin: '◊' },
  ],
  roads: [
    'M 12 60 L 88 60',
    'M 50 12 L 50 88',
    'M 14 40 L 86 40',
  ],
}

// ── Région (Côte des Épées) ─────────────────────────────────────────────
// TODO: brancher backend — viendra de gameStore.regionMap
export const EX_REGION: ExRegion = {
  pins: [
    { id: 'phandalin',   x: 48, y: 58, label: 'Phandalin',            tag: 'sûr',     state: 'visited' },
    { id: 'triboar',     x: 26, y: 62, label: 'Triboar Trail',         tag: 'active',  state: 'here' },
    { id: 'cragmaw',     x: 70, y: 50, label: 'Repaire de Cragmaw',    tag: 'danger',  state: 'destination' },
    { id: 'neverwinter', x: 14, y: 28, label: 'Neverwinter',           tag: 'sûr',     state: 'known' },
    { id: 'tresendar',   x: 52, y: 50, label: 'Mine de Tresendar',     tag: 'rumeur',  state: 'rumor' },
    { id: 'conyberry',   x: 76, y: 78, label: 'Conyberry',             tag: 'neutre',  state: 'known' },
  ],
  roads: [
    'M 14 28 Q 30 40 48 58',
    'M 48 58 Q 38 60 26 62',
    'M 48 58 Q 60 54 70 50',
    'M 48 58 Q 60 68 76 78',
    'M 70 50 Q 60 50 52 50',
  ],
}
