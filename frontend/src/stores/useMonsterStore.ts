import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type { AbilityKey, Monster, MonsterFeature, MonsterType, MonsterSize } from '@/types/library';
import { crToNum } from '@/types/library';
import type { SrdMonster, SrdMonsterAction } from '@/types';
import { srdApi } from '@/services/api';

type SrdMonsterFeature = {
  name: string;
  name_fr?: string;
  description?: string;
};

type SrdMonsterExtended = SrdMonster & {
  subtype?: string | null;
  ac_source?: string | null;
  traits: SrdMonsterFeature[];
  actions: (SrdMonsterAction & { name_fr?: string })[];
  reactions?: (SrdMonsterAction & { name_fr?: string })[];
  legendary_actions?: (SrdMonsterAction & { name_fr?: string })[];
};

const SIZE_MAP: Record<string, MonsterSize> = {
  Tiny: 'Très petit',
  Small: 'Petit',
  Medium: 'Moyen',
  Large: 'Grand',
  Huge: 'Très grand',
  Gargantuan: 'Gigantesque',
  'Très petit': 'Très petit',
  Petit: 'Petit',
  Moyen: 'Moyen',
  Grand: 'Grand',
  'Très grand': 'Très grand',
  Gigantesque: 'Gigantesque',
};

const TYPE_MAP: Record<string, MonsterType> = {
  aberration: 'Aberration',
  beast: 'Bête',
  celestial: 'Céleste',
  construct: 'Constructe',
  dragon: 'Dragon',
  elemental: 'Élémentaire',
  fey: 'Fée',
  fiend: 'Fiélon',
  giant: 'Géant',
  humanoid: 'Humanoïde',
  monstrosity: 'Monstruosité',
  ooze: 'Vase',
  plant: 'Plante',
  undead: 'Mort-vivant',
};

const ABILITY_MAP: Record<string, AbilityKey> = {
  strength: 'FOR',
  dexterity: 'DEX',
  constitution: 'CON',
  intelligence: 'INT',
  wisdom: 'SAG',
  charisma: 'CHA',
};

const SKILL_MAP: Record<string, string> = {
  acrobatics: 'Acrobaties',
  animal_handling: 'Dressage',
  arcana: 'Arcanes',
  athletics: 'Athlétisme',
  deception: 'Tromperie',
  history: 'Histoire',
  insight: 'Intuition',
  intimidation: 'Intimidation',
  investigation: 'Investigation',
  medicine: 'Médecine',
  nature: 'Nature',
  perception: 'Perception',
  performance: 'Représentation',
  persuasion: 'Persuasion',
  religion: 'Religion',
  sleight_of_hand: 'Escamotage',
  stealth: 'Discrétion',
  survival: 'Survie',
};

const DAMAGE_TYPE_MAP: Record<string, string> = {
  acid: 'acide',
  bludgeoning: 'contondant',
  cold: 'froid',
  fire: 'feu',
  force: 'force',
  lightning: 'foudre',
  necrotic: 'nécrotique',
  piercing: 'perforant',
  poison: 'poison',
  psychic: 'psychique',
  radiant: 'radiant',
  slashing: 'tranchant',
  thunder: 'tonnerre',
};

const CONDITION_MAP: Record<string, string> = {
  blinded: 'aveuglé',
  charmed: 'charmé',
  deafened: 'assourdi',
  exhaustion: 'épuisement',
  frightened: 'effrayé',
  grappled: 'agrippé',
  incapacitated: 'neutralisé',
  invisible: 'invisible',
  paralyzed: 'paralysé',
  petrified: 'pétrifié',
  poisoned: 'empoisonné',
  prone: 'à terre',
  restrained: 'entravé',
  stunned: 'étourdi',
  unconscious: 'inconscient',
};

const ALIGNMENT_MAP: Record<string, string> = {
  unaligned: 'Non-aligné',
  neutral: 'Neutre',
  'neutral good': 'Neutre Bon',
  'neutral evil': 'Neutre Mauvais',
  'lawful good': 'Loyal Bon',
  'lawful neutral': 'Loyal Neutre',
  'lawful evil': 'Loyal Mauvais',
  'chaotic good': 'Chaotique Bon',
  'chaotic neutral': 'Chaotique Neutre',
  'chaotic evil': 'Chaotique Mauvais',
  'any alignment': 'Tout alignement',
};

function formatSigned(value: number): string {
  return value >= 0 ? `+${value}` : `${value}`;
}

function abilityModifier(score: number): string {
  return formatSigned(Math.floor((score - 10) / 2));
}

function crToLabel(cr: number): string {
  if (cr === 0) return '0';
  if (cr === 0.125) return '1/8';
  if (cr === 0.25) return '1/4';
  if (cr === 0.5) return '1/2';
  if (Number.isInteger(cr)) return String(cr);
  return cr.toLocaleString('fr-FR', { maximumFractionDigits: 3 });
}

function normalizeText(value: string | null | undefined): string {
  return value?.replace(/\s+/g, ' ').trim() ?? '';
}

function mapList(values: string[], labels: Record<string, string>): string[] {
  return values.map((value) => labels[value] ?? value);
}

function mapRecord(
  values: Record<string, number> | null | undefined,
  labels: Record<string, string>,
): Record<string, string> | null {
  if (!values || Object.keys(values).length === 0) return null;

  return Object.fromEntries(
    Object.entries(values).map(([key, value]) => [
      labels[key] ?? key,
      formatSigned(value),
    ]),
  );
}

function formatAcSource(value: string | null | undefined): string | null {
  if (!value) return null;

  const labels: Record<string, string> = {
    'natural armor': 'armure naturelle',
    'leather armor': 'armure de cuir',
    shield: 'bouclier',
    'hide armor': 'armure de peaux',
    'chain mail': 'cotte de mailles',
    'plate armor': 'harnois',
    'armor scraps': "vestiges d'armure",
    'patchwork armor': 'armure composite',
  };

  return value
    .split(',')
    .map((part) => labels[part.trim()] ?? part.trim())
    .join(', ');
}

function formatSpeed(speed: Record<string, number>): Monster['speed'] {
  const labels: Record<string, keyof Monster['speed']> = {
    walk: 'marche',
    fly: 'vol',
    swim: 'nage',
    burrow: 'fouissement',
    climb: 'escalade',
  };

  return Object.fromEntries(
    Object.entries(speed)
      .filter(([, value]) => value !== undefined && value !== null)
      .map(([key, value]) => [labels[key] ?? key, `${value} m`]),
  ) as Monster['speed'];
}

function formatSenses(senses: Record<string, number | string>): string {
  const labels: Record<string, string> = {
    darkvision_m: 'Vision dans le noir',
    blindsight_m: 'Vision aveugle',
    truesight_m: 'Vision véritable',
    tremorsense_m: 'Perception des vibrations',
  };

  const parts = Object.entries(senses).map(([key, value]) => {
    if (key === 'passive_perception') return `Perception passive ${value}`;
    const label = labels[key] ?? key;
    return typeof value === 'number' ? `${label} ${value} m` : `${label} ${value}`;
  });

  return parts.join(', ');
}

function formatDistance(value: number): string {
  return `${value.toLocaleString('fr-FR', { maximumFractionDigits: 1 })} m`;
}

function formatTargetCount(value: number | undefined): string {
  if (!value) return 'une cible';
  return value === 1 ? 'une cible' : `${value} cibles`;
}

function buildActionDescription(action: SrdMonsterAction): string {
  const description = normalizeText(action.description);
  if (description) return description;

  const parts: string[] = [];
  const attackBonus = action.attack_bonus !== undefined ? formatSigned(action.attack_bonus) : null;
  const targets = formatTargetCount(action.targets);

  if (attackBonus && action.reach_m !== undefined) {
    parts.push(`Corps à corps : ${attackBonus} pour toucher, allonge ${formatDistance(action.reach_m)}, ${targets}.`);
  } else if (attackBonus && action.range_normal_m !== undefined) {
    const range = action.range_long_m !== undefined
      ? `${formatDistance(action.range_normal_m)}/${formatDistance(action.range_long_m)}`
      : formatDistance(action.range_normal_m);
    parts.push(`À distance : ${attackBonus} pour toucher, portée ${range}, ${targets}.`);
  } else if (attackBonus) {
    parts.push(`Attaque : ${attackBonus} pour toucher, ${targets}.`);
  }

  if (action.damage_dice) {
    const damageType = action.damage_type
      ? (DAMAGE_TYPE_MAP[action.damage_type] ?? action.damage_type)
      : null;
    parts.push(`Dégâts : ${action.damage_dice}${damageType ? ` ${damageType}` : ''}.`);
  }

  return parts.join(' ') || 'Action spéciale.';
}

function mapFeature(feature: SrdMonsterFeature | SrdMonsterAction): MonsterFeature {
  return {
    name: feature.name_fr || feature.name,
    desc: 'attack_bonus' in feature || 'damage_dice' in feature
      ? buildActionDescription(feature)
      : normalizeText(feature.description) || 'Capacité spéciale.',
  };
}

function mapSrdMonster(monster: SrdMonsterExtended): Monster {
  const scores = monster.ability_scores;

  return {
    id: monster.id,
    name: monster.name_fr || monster.name,
    size: SIZE_MAP[monster.size] ?? 'Moyen',
    type: TYPE_MAP[monster.type] ?? 'Monstruosité',
    subtype: monster.subtype ?? null,
    alignment: ALIGNMENT_MAP[monster.alignment] ?? monster.alignment,
    ac: monster.ac,
    ac_type: formatAcSource(monster.ac_source),
    hp: monster.hp,
    hp_dice: monster.hit_dice,
    speed: formatSpeed(monster.speed),
    abilities: {
      FOR: { v: scores.strength ?? 10, m: abilityModifier(scores.strength ?? 10) },
      DEX: { v: scores.dexterity ?? 10, m: abilityModifier(scores.dexterity ?? 10) },
      CON: { v: scores.constitution ?? 10, m: abilityModifier(scores.constitution ?? 10) },
      INT: { v: scores.intelligence ?? 10, m: abilityModifier(scores.intelligence ?? 10) },
      SAG: { v: scores.wisdom ?? 10, m: abilityModifier(scores.wisdom ?? 10) },
      CHA: { v: scores.charisma ?? 10, m: abilityModifier(scores.charisma ?? 10) },
    },
    saving_throws: mapRecord(monster.saving_throws, ABILITY_MAP),
    skills: mapRecord(monster.skills, SKILL_MAP),
    damage_resistances: mapList(monster.damage_resistances, DAMAGE_TYPE_MAP),
    damage_immunities: mapList(monster.damage_immunities, DAMAGE_TYPE_MAP),
    condition_immunities: mapList(monster.condition_immunities, CONDITION_MAP),
    senses: formatSenses(monster.senses),
    languages: monster.languages.length > 0 ? monster.languages.join(', ') : '—',
    challenge: crToLabel(monster.cr),
    xp: monster.xp,
    traits: monster.traits.map(mapFeature),
    actions: monster.actions.map(mapFeature),
    reactions: monster.reactions?.length ? monster.reactions.map(mapFeature) : null,
    legendary_actions: monster.legendary_actions?.length
      ? monster.legendary_actions.map(mapFeature)
      : null,
    environment: [],
    source: 'SRD 5.2',
  };
}

export const useMonsterStore = defineStore('monsters', () => {
  // ─── State ───
  const monsters = ref<Monster[]>([]);
  const isLoading = ref(false);

  // Filtres
  const search = ref('');
  const crFilter = ref('');
  const typeFilter = ref<MonsterType | ''>('');
  const sizeFilter = ref<MonsterSize | ''>('');

  // Sélection
  const selectedId = ref<string | null>(null);

  // ─── Getters ───

  /** Monstres filtrés selon tous les critères actifs */
  const filtered = computed<Monster[]>(() => {
    return monsters.value.filter((m) => {
      if (search.value) {
        const q = search.value.toLowerCase();
        if (!m.name.toLowerCase().includes(q)) return false;
      }
      if (crFilter.value && m.challenge !== crFilter.value) return false;
      if (typeFilter.value && m.type !== typeFilter.value) return false;
      if (sizeFilter.value && m.size !== sizeFilter.value) return false;
      return true;
    });
  });

  /** Monstres groupés par FP, triés par FP croissant */
  const grouped = computed(() => {
    const map = new Map<string, Monster[]>();
    for (const m of filtered.value) {
      const arr = map.get(m.challenge) ?? [];
      arr.push(m);
      map.set(m.challenge, arr);
    }
    return [...map.entries()]
      .sort(([a], [b]) => crToNum(a) - crToNum(b))
      .map(([cr, items]) => ({ cr, items }));
  });

  /** Monstre actuellement sélectionné */
  const selected = computed<Monster | null>(() => {
    if (!selectedId.value) return null;
    return monsters.value.find((m) => m.id === selectedId.value) ?? null;
  });

  /** FP disponibles dans les données (pour le select) */
  const availableCRs = computed(() => {
    return [...new Set(monsters.value.map((m) => m.challenge))]
      .sort((a, b) => crToNum(a) - crToNum(b));
  });

  /** Types disponibles dans les données */
  const availableTypes = computed(() => {
    return [...new Set(monsters.value.map((m) => m.type))].sort();
  });

  /** Tailles disponibles dans les données */
  const availableSizes = computed(() => {
    const order: MonsterSize[] = [
      'Très petit', 'Petit', 'Moyen', 'Grand', 'Très grand', 'Gigantesque',
    ];
    const present = new Set(monsters.value.map((m) => m.size));
    return order.filter((s) => present.has(s));
  });

  /** Nombre de filtres actifs */
  const activeFilterCount = computed(() => {
    let count = 0;
    if (search.value) count++;
    if (crFilter.value) count++;
    if (typeFilter.value) count++;
    if (sizeFilter.value) count++;
    return count;
  });

  // ─── Actions ───

  function select(id: string) {
    selectedId.value = id;
  }

  function clearFilters() {
    search.value = '';
    crFilter.value = '';
    typeFilter.value = '';
    sizeFilter.value = '';
  }

  /**
   * Charger les monstres depuis l'API.
   */
  async function fetchMonsters() {
    isLoading.value = true;
    try {
      const response = await srdApi.listMonsters();
      monsters.value = response.monsters.map((monster) => mapSrdMonster(monster));
    } catch (error) {
      console.error('[useMonsterStore] Erreur chargement monstres:', error);
    } finally {
      isLoading.value = false;
    }
  }

  return {
    // State
    monsters,
    isLoading,
    search,
    crFilter,
    typeFilter,
    sizeFilter,
    selectedId,

    // Getters
    filtered,
    grouped,
    selected,
    availableCRs,
    availableTypes,
    availableSizes,
    activeFilterCount,

    // Actions
    select,
    clearFilters,
    fetchMonsters,
  };
});
