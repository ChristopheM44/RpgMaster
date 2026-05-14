// ─── Types pour la bibliothèque : Sorts & Monstres ───

/** Composantes d'un sort */
export interface SpellComponents {
  /** Verbale */
  V: boolean;
  /** Somatique */
  S: boolean;
  /** Matérielle — description du composant, ou null */
  M: string | null;
}

/** Sort D&D 5e */
export interface Spell {
  id: string;
  name: string;
  /** 0 = cantrip, 1–9 = niveau du sort */
  level: number;
  /** École de magie */
  school:
    | 'Abjuration'
    | 'Conjuration'
    | 'Divination'
    | 'Enchantement'
    | 'Évocation'
    | 'Illusion'
    | 'Nécromancie'
    | 'Transmutation';
  /** ex: "1 action", "1 réaction", "1 minute" */
  casting_time: string;
  /** ex: "36 m", "Personnel", "Contact" */
  range: string;
  components: SpellComponents;
  /** ex: "Instantanée", "1 round", "Jusqu'à 1 minute" */
  duration: string;
  concentration: boolean;
  ritual: boolean;
  description: string;
  /** Texte de scaling par emplacement supérieur, ou null */
  higher_levels: string | null;
  /** Classes pouvant lancer ce sort */
  classes: SpellClass[];
  /** Type de dégâts (Feu, Froid, Force…) ou null */
  damage_type: string | null;
  /** ex: "SRD 5.2" */
  source: string;
}

export type SpellClass =
  | 'Barde'
  | 'Clerc'
  | 'Druide'
  | 'Ensorceleur'
  | 'Magicien'
  | 'Occultiste'
  | 'Paladin'
  | 'Rôdeur';

export type SpellSchool = Spell['school'];

// ─── Monstres ───

export interface AbilityScore {
  /** Valeur brute (ex: 16) */
  v: number;
  /** Modificateur formaté (ex: "+3") */
  m: string;
}

export type AbilityKey = 'FOR' | 'DEX' | 'CON' | 'INT' | 'SAG' | 'CHA';

/** Vitesses de déplacement */
export interface MonsterSpeed {
  marche?: string;
  vol?: string;
  nage?: string;
  fouissement?: string;
  escalade?: string;
}

/** Trait, action, réaction ou action légendaire */
export interface MonsterFeature {
  name: string;
  desc: string;
}

/** Monstre D&D 5e */
export interface Monster {
  id: string;
  name: string;
  size: MonsterSize;
  type: MonsterType;
  /** ex: "gobelinoïde", "orc", null */
  subtype: string | null;
  /** ex: "Chaotique Mauvais", "Non-aligné" */
  alignment: string;

  // ─ Défenses ─
  ac: number;
  /** ex: "armure de cuir, bouclier", null si aucune */
  ac_type: string | null;
  hp: number;
  /** ex: "2d6", "9d8+18" */
  hp_dice: string;
  speed: MonsterSpeed;

  // ─ Caractéristiques ─
  abilities: Record<AbilityKey, AbilityScore>;

  // ─ Proficiencies ─
  /** ex: { DEX: "+4", CON: "+9" } ou null */
  saving_throws: Record<string, string> | null;
  /** ex: { Discrétion: "+6" } ou null */
  skills: Record<string, string> | null;

  // ─ Résistances & immunités ─
  damage_resistances: string[];
  damage_immunities: string[];
  condition_immunities: string[];

  // ─ Sens & langues ─
  /** ex: "Vision dans le noir 18 m, Perception passive 12" */
  senses: string;
  /** ex: "Commun, gobelin" ou "—" */
  languages: string;

  // ─ Puissance ─
  /** ex: "1/4", "3", "10" */
  challenge: string;
  xp: number;

  // ─ Blocs de texte ─
  traits: MonsterFeature[];
  actions: MonsterFeature[];
  reactions: MonsterFeature[] | null;
  legendary_actions: MonsterFeature[] | null;

  // ─ Métadonnées ─
  /** ex: ["Forêt", "Collines", "Souterrain"] */
  environment: string[];
  source: string;
}

export type MonsterSize =
  | 'Très petit'
  | 'Petit'
  | 'Moyen'
  | 'Grand'
  | 'Très grand'
  | 'Gigantesque';

export type MonsterType =
  | 'Aberration'
  | 'Bête'
  | 'Céleste'
  | 'Constructe'
  | 'Dragon'
  | 'Élémentaire'
  | 'Fée'
  | 'Fiélon'
  | 'Géant'
  | 'Humanoïde'
  | 'Monstruosité'
  | 'Mort-vivant'
  | 'Plante'
  | 'Vase';

// ─── Constantes ───

export const SPELL_SCHOOLS: SpellSchool[] = [
  'Abjuration', 'Conjuration', 'Divination', 'Enchantement',
  'Évocation', 'Illusion', 'Nécromancie', 'Transmutation',
];

export const SPELL_CLASSES: SpellClass[] = [
  'Barde', 'Clerc', 'Druide', 'Ensorceleur',
  'Magicien', 'Occultiste', 'Paladin', 'Rôdeur',
];

export const MONSTER_TYPES: MonsterType[] = [
  'Aberration', 'Bête', 'Céleste', 'Constructe', 'Dragon',
  'Élémentaire', 'Fée', 'Fiélon', 'Géant', 'Humanoïde',
  'Monstruosité', 'Mort-vivant', 'Plante', 'Vase',
];

export const MONSTER_SIZES: MonsterSize[] = [
  'Très petit', 'Petit', 'Moyen', 'Grand', 'Très grand', 'Gigantesque',
];

export const SCHOOL_COLORS: Record<SpellSchool, string> = {
  Abjuration: '#4fd8c0',
  Conjuration: '#6fd96f',
  Divination: '#f0c764',
  Enchantement: '#c090ff',
  Évocation: '#ff8247',
  Illusion: '#7eb8ff',
  Nécromancie: '#e84545',
  Transmutation: '#b88a2a',
};

export const TYPE_COLORS: Record<MonsterType, string> = {
  Aberration: '#c090ff',
  Bête: '#6fd96f',
  Céleste: '#f0c764',
  Constructe: '#6b6580',
  Dragon: '#ff8247',
  Élémentaire: '#4fd8c0',
  Fée: '#c090ff',
  Fiélon: '#e84545',
  Géant: '#b88a2a',
  Humanoïde: '#f7ecd0',
  Monstruosité: '#ff8247',
  'Mort-vivant': '#e84545',
  Plante: '#6fd96f',
  Vase: '#4fd8c0',
};

export const LEVEL_LABELS: Record<number, string> = {
  0: 'Cantrip', 1: 'Niveau 1', 2: 'Niveau 2', 3: 'Niveau 3',
  4: 'Niveau 4', 5: 'Niveau 5', 6: 'Niveau 6', 7: 'Niveau 7',
  8: 'Niveau 8', 9: 'Niveau 9',
};

/** Convertit un FP string en nombre pour le tri */
export function crToNum(cr: string): number {
  if (cr.includes('/')) {
    const [a, b] = cr.split('/');
    const numerator = Number.parseInt(a ?? '0', 10);
    const denominator = Number.parseInt(b ?? '1', 10);
    return denominator === 0 ? 0 : numerator / denominator;
  }
  return Number.parseFloat(cr);
}
