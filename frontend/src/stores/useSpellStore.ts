import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type { Spell, SpellSchool, SpellClass } from '@/types/library';
import type { SrdSpell } from '@/types';
import { srdApi } from '@/services/api';

type SrdSpellExtended = SrdSpell & {
  ritual?: boolean;
  upcast_extra_targets?: number | null;
  upcast_extra_rays?: number | null;
  upcast_extra_darts?: number | null;
};

const SCHOOL_MAP: Record<string, SpellSchool> = {
  abjuration: 'Abjuration',
  conjuration: 'Conjuration',
  divination: 'Divination',
  enchantment: 'Enchantement',
  evocation: 'Évocation',
  illusion: 'Illusion',
  necromancy: 'Nécromancie',
  transmutation: 'Transmutation',
};

const CLASS_MAP: Record<string, SpellClass> = {
  bard: 'Barde',
  cleric: 'Clerc',
  druid: 'Druide',
  sorcerer: 'Ensorceleur',
  wizard: 'Magicien',
  warlock: 'Occultiste',
  paladin: 'Paladin',
  ranger: 'Rôdeur',
};

const DAMAGE_TYPE_MAP: Record<string, string> = {
  acid: 'Acide',
  bludgeoning: 'Contondant',
  cold: 'Froid',
  fire: 'Feu',
  force: 'Force',
  lightning: 'Foudre',
  necrotic: 'Nécrotique',
  piercing: 'Perforant',
  poison: 'Poison',
  psychic: 'Psychique',
  radiant: 'Radiant',
  slashing: 'Tranchant',
  thunder: 'Tonnerre',
};

function formatRange(range: number | null | undefined): string {
  if (range === null || range === undefined) return '—';
  if (range === 0) return 'Personnel';
  return `${range.toLocaleString('fr-FR', { maximumFractionDigits: 1 })} m`;
}

function formatCastingTime(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) return '—';
  if (/^\d/.test(trimmed)) return trimmed;
  return `1 ${trimmed.toLowerCase()}`;
}

function formatDamageType(value: string | null): string | null {
  if (!value) return null;
  return DAMAGE_TYPE_MAP[value.toLowerCase()] ?? value;
}

function buildHigherLevels(spell: SrdSpellExtended): string | null {
  if (spell.level === 0 && spell.upcast_breakpoints?.length) {
    return `Amélioration de sort mineur aux niveaux ${spell.upcast_breakpoints.join(', ')}.`;
  }

  const suffix = spell.level === 1 ? 'au-delà du 1er' : `au-delà du ${spell.level}e`;
  if (spell.upcast_extra_dice) {
    return `Les dégâts ou soins augmentent de ${spell.upcast_extra_dice} par niveau d'emplacement ${suffix}.`;
  }
  if (spell.upcast_extra_targets) {
    return `Vous ciblez ${spell.upcast_extra_targets} cible supplémentaire par niveau d'emplacement ${suffix}.`;
  }
  if (spell.upcast_extra_rays) {
    return `Vous créez ${spell.upcast_extra_rays} rayon supplémentaire par niveau d'emplacement ${suffix}.`;
  }
  if (spell.upcast_extra_darts) {
    return `Vous créez ${spell.upcast_extra_darts} projectile supplémentaire par niveau d'emplacement ${suffix}.`;
  }
  return null;
}

function mapSrdSpell(spell: SrdSpellExtended): Spell {
  const componentSet = new Set(spell.components ?? []);

  return {
    id: spell.id,
    name: spell.name_fr || spell.name,
    level: spell.level,
    school: SCHOOL_MAP[spell.school.toLowerCase()] ?? 'Évocation',
    casting_time: formatCastingTime(spell.casting_time),
    range: formatRange(spell.range_m),
    components: {
      V: componentSet.has('V'),
      S: componentSet.has('S'),
      M: componentSet.has('M') ? 'Composante matérielle indiquée dans la description du sort.' : null,
    },
    duration: spell.duration,
    concentration: spell.concentration,
    ritual: Boolean(spell.ritual),
    description: spell.description,
    higher_levels: buildHigherLevels(spell),
    classes: spell.classes
      .map((classId) => CLASS_MAP[classId])
      .filter((className): className is SpellClass => Boolean(className)),
    damage_type: formatDamageType(spell.damage_type),
    source: 'SRD 5.2',
  };
}

export const useSpellStore = defineStore('spells', () => {
  // ─── State ───
  const spells = ref<Spell[]>([]);
  const isLoading = ref(false);

  // Filtres
  const search = ref('');
  const levelFilter = ref<number | null>(null);
  const schoolFilter = ref<SpellSchool | ''>('');
  const classFilter = ref<SpellClass | ''>('');
  const concentrationOnly = ref(false);
  const ritualOnly = ref(false);

  // Sélection
  const selectedId = ref<string | null>(null);

  // ─── Getters ───

  /** Sorts filtrés selon tous les critères actifs */
  const filtered = computed<Spell[]>(() => {
    return spells.value.filter((s) => {
      if (search.value) {
        const q = search.value.toLowerCase();
        if (!s.name.toLowerCase().includes(q)) return false;
      }
      if (levelFilter.value !== null && s.level !== levelFilter.value) return false;
      if (schoolFilter.value && s.school !== schoolFilter.value) return false;
      if (classFilter.value && !s.classes.includes(classFilter.value)) return false;
      if (concentrationOnly.value && !s.concentration) return false;
      if (ritualOnly.value && !s.ritual) return false;
      return true;
    });
  });

  /** Sorts groupés par niveau, triés par niveau croissant */
  const grouped = computed(() => {
    const map = new Map<number, Spell[]>();
    for (const s of filtered.value) {
      const arr = map.get(s.level) ?? [];
      arr.push(s);
      map.set(s.level, arr);
    }
    return [...map.entries()]
      .sort(([a], [b]) => a - b)
      .map(([level, items]) => ({ level, items }));
  });

  /** Sort actuellement sélectionné */
  const selected = computed<Spell | null>(() => {
    if (!selectedId.value) return null;
    return spells.value.find((s) => s.id === selectedId.value) ?? null;
  });

  /** Niveaux disponibles dans les données (pour le select) */
  const availableLevels = computed(() => {
    return [...new Set(spells.value.map((s) => s.level))].sort((a, b) => a - b);
  });

  /** Nombre de filtres actifs */
  const activeFilterCount = computed(() => {
    let count = 0;
    if (search.value) count++;
    if (levelFilter.value !== null) count++;
    if (schoolFilter.value) count++;
    if (classFilter.value) count++;
    if (concentrationOnly.value) count++;
    if (ritualOnly.value) count++;
    return count;
  });

  // ─── Actions ───

  function select(id: string) {
    selectedId.value = id;
  }

  function clearFilters() {
    search.value = '';
    levelFilter.value = null;
    schoolFilter.value = '';
    classFilter.value = '';
    concentrationOnly.value = false;
    ritualOnly.value = false;
  }

  /**
   * Charger les sorts depuis l'API.
   */
  async function fetchSpells() {
    isLoading.value = true;
    try {
      const response = await srdApi.listSpells();
      spells.value = response.spells.map((spell) => mapSrdSpell(spell));
    } catch (error) {
      console.error('[useSpellStore] Erreur chargement sorts:', error);
    } finally {
      isLoading.value = false;
    }
  }

  return {
    // State
    spells,
    isLoading,
    search,
    levelFilter,
    schoolFilter,
    classFilter,
    concentrationOnly,
    ritualOnly,
    selectedId,

    // Getters
    filtered,
    grouped,
    selected,
    availableLevels,
    activeFilterCount,

    // Actions
    select,
    clearFilters,
    fetchSpells,
  };
});
