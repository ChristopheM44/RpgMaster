// ─── Session ──────────────────────────────────────────────────────────────────

export type SessionStatus =
  | 'lobby'
  | 'character_creation'
  | 'exploration'
  | 'encounter_start'
  | 'combat'
  | 'encounter_end'
  | 'rest'
  | 'level_up'
  | 'session_end'

export interface Session {
  id: string
  name: string
  status: SessionStatus
  created_at: string
  updated_at: string
}

export interface SessionListResponse {
  sessions: Session[]
  total: number
}

export interface SessionCreate {
  name: string
}

export interface SessionUpdate {
  name?: string
  status?: SessionStatus
}

// ─── SRD Types ────────────────────────────────────────────────────────────────

export interface SrdTrait {
  name: string
  name_fr: string
  description: string
}

export interface SrdSpecies {
  id: string
  name: string
  name_fr: string
  size: string
  speed: number
  darkvision_ft: number
  ability_bonuses: Record<string, number>
  skill_proficiencies: string[]
  languages: string[]
  traits: SrdTrait[]
  description: string
}

export interface SrdFeature {
  name: string
  name_fr: string
  description: string
}

export interface SrdEquipmentEntry {
  choice?: string[][]
  fixed?: string[]
}

export interface SrdClass {
  id: string
  name: string
  name_fr: string
  hit_die: number
  primary_abilities: string[]
  saving_throw_proficiencies: string[]
  armor_proficiencies: string[]
  weapon_proficiencies: string[]
  tool_proficiencies: string[]
  skill_choices: string[]
  num_skill_choices: number
  spellcasting_ability: string | null
  caster_type: string | null
  level_1_features: SrdFeature[]
  starting_equipment: SrdEquipmentEntry[]
  description: string
}

// ─── Character ────────────────────────────────────────────────────────────────

export interface CharacterCreate {
  name: string
  player_name?: string
  is_ai: boolean
  species: string
  char_class: string
  level?: number
  background?: string
  ability_scores: Record<string, number>
  hp_current: number
  hp_max: number
  hp_temp: number
  equipment?: Record<string, unknown>[]
  proficiencies?: Record<string, unknown>
  session_id?: string
}

export interface Character {
  id: string
  name: string
  player_name: string | null
  is_ai: boolean
  species: string
  char_class: string
  level: number
  background: string | null
  ability_scores: Record<string, number>
  hp_current: number
  hp_max: number
  hp_temp: number
  equipment: Record<string, unknown>[]
  spell_slots: Record<string, unknown>
  known_spells: string[]
  conditions: string[]
  proficiencies: Record<string, unknown>
  personality: Record<string, unknown>
  session_id: string | null
  created_at: string
  updated_at: string
}

export interface CharacterUpdate {
  name?: string
  player_name?: string
  level?: number
  background?: string
  ability_scores?: Record<string, number>
  hp_current?: number
  hp_max?: number
  hp_temp?: number
  equipment?: Record<string, unknown>[]
  spell_slots?: Record<string, unknown>
  known_spells?: string[]
  conditions?: string[]
  proficiencies?: Record<string, unknown>
  personality?: Record<string, unknown>
  session_id?: string
}

export interface CharacterListResponse {
  characters: Character[]
  total: number
}

// ─── SRD Extended Types ───────────────────────────────────────────────────────

export interface SrdSpell {
  id: string
  name: string
  name_fr: string
  level: number
  school: string
  casting_time: string
  range_ft: number
  components: string[]
  duration: string
  concentration: boolean
  classes: string[]
  attack_type: string | null
  damage_dice: string | null
  damage_type: string | null
  upcast_extra_dice: string | null
  upcast_breakpoints: number[] | null
  save: { ability: string; on_success: string } | null
  description: string
}

export interface SrdMonsterAction {
  name: string
  description: string
  attack_bonus?: number
  damage_dice?: string
  damage_type?: string
}

export interface SrdMonster {
  id: string
  name: string
  name_fr: string
  cr: number
  xp: number
  size: string
  type: string
  alignment: string
  ac: number
  ac_source: string
  hp: number
  hit_dice: string
  speed: Record<string, number>
  ability_scores: Record<string, number>
  saving_throws: Record<string, number>
  skills: Record<string, number>
  damage_immunities: string[]
  damage_resistances: string[]
  condition_immunities: string[]
  senses: Record<string, number | string>
  languages: string[]
  proficiency_bonus: number
  traits: { name: string; description: string }[]
  actions: SrdMonsterAction[]
  description: string
}

export interface SrdEquipmentItem {
  id: string
  name: string
  name_fr: string
  category: string
  damage_dice?: string
  damage_type?: string
  properties?: string[]
  range_normal?: number | null
  range_long?: number | null
  versatile_dice?: string | null
  ac_base?: number
  dex_bonus?: boolean
  max_dex_bonus?: number | null
  stealth_disadvantage?: boolean
  weight?: number
  cost_gp?: number
  contents?: Record<string, unknown>[]
}

// ─── Game State ───────────────────────────────────────────────────────────────

export interface GameStateResponse {
  session_id: string
  phase: string
}

// ─── WebSocket Protocol ───────────────────────────────────────────────────────

export type WsEventType =
  | 'session_state'
  | 'narration'
  | 'roll_result'
  | 'turn_start'
  | 'turn_end'
  | 'phase_change'
  | 'combat_start'
  | 'combat_end'
  | 'hp_changed'
  | 'player_joined'
  | 'player_left'
  | 'error'
  | 'pong'

export interface WsEvent<T = unknown> {
  event_type: WsEventType
  session_id?: string
  payload: T
  timestamp?: string
}

export interface SessionStatePayload {
  session_id: string
  phase: string
  turn_number: number
  round_number: number
  turn_order: TurnEntry[]
  current_turn_index: number
  valid_transitions: string[]
}

export interface TurnEntry {
  id: string
  name: string
  initiative: number
  is_ai: boolean
  is_player: boolean
}

export interface NarrationPayload {
  text: string
  speaker?: string
}

export interface RollResultPayload {
  dice_notation: string
  rolls: number[]
  total: number
  modifier: number
  label?: string
  success?: boolean
  character_name?: string
}

export interface PhaseChangePayload {
  phase: string
}

export interface TurnStartPayload {
  combatant_id: string
  combatant_name?: string
}

// ─── Game UI State ────────────────────────────────────────────────────────────

export type NarrativeEntryType = 'narration' | 'roll' | 'system' | 'player'

export interface NarrativeEntry {
  id: string
  type: NarrativeEntryType
  text?: string
  speaker?: string
  roll?: RollResultPayload
  timestamp: string
}

export interface CombatantState {
  id: string
  name: string
  initiative: number
  hp_current: number
  hp_max: number
  conditions: string[]
  is_ai: boolean
  is_active: boolean
}

export interface HpChangedPayload {
  combatant_id: string
  hp: number
  delta: number
}

export interface CombatStartPayload {
  combatants: CombatantState[]
}
