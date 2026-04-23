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
  darkvision_m: number
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
  known_spells?: string[]
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
  is_ai?: boolean
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

// ─── Pregen ───────────────────────────────────────────────────────────────────

export interface PregenTemplate {
  class_id: string
  class_name_fr: string
  name: string
  description: string
  species: string
  background: string
  ability_scores: Record<string, number>
  hp_max: number
}

// ─── SRD Extended Types ───────────────────────────────────────────────────────

export interface SrdSpell {
  id: string
  name: string
  name_fr: string
  level: number
  school: string
  casting_time: string
  range_m: number
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
  | 'combat_action'
  | 'combatant_moved'
  | 'hp_changed'
  | 'condition_changed'
  | 'death_save_updated'
  | 'spell_slot_updated'
  | 'equipment_updated'
  | 'player_joined'
  | 'player_left'
  | 'audio'
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

export interface EquipmentUpdatedPayload {
  character_id: string
  equipment: Record<string, unknown>[]
}

export interface TurnStartPayload {
  combatant_id: string
  combatant_name?: string
}

// ─── Game UI State ────────────────────────────────────────────────────────────

export type NarrativeEntryType = 'narration' | 'roll' | 'system' | 'player' | 'combat_action'

export interface NarrativeEntry {
  id: string
  type: NarrativeEntryType
  text?: string
  speaker?: string
  roll?: RollResultPayload
  combatAction?: CombatActionPayload
  timestamp: string
}

export interface GridPosition {
  col: number
  row: number
}

export interface GridConfig {
  cols: number
  rows: number
  cell_size_m: number
}

export interface CombatantMovedPayload {
  combatant_id: string
  position: GridPosition
  movement_used_m: number
}

export interface DeathSaves {
  successes: number
  failures: number
  stable: boolean
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
  position?: GridPosition
  death_saves?: DeathSaves
}

export interface HpChangedPayload {
  combatant_id: string
  hp: number
  delta: number
}

export interface ConditionChangedPayload {
  combatant_id: string
  condition: string
  added: boolean
}

export interface DeathSaveUpdatedPayload {
  combatant_id: string
  death_saves: DeathSaves
}

export interface SpellSlotUpdatedPayload {
  character_id: string
  spell_slots: Record<string, { total: number; used: number }>
}

export interface CombatStartPayload {
  combatants: CombatantState[]
  grid_config?: GridConfig
}

export interface CombatActionPayload {
  attacker_id: string
  attacker_name: string
  target_id: string | null
  target_name: string
  action_type: 'attack' | 'spell' | 'ability'
  action_name: string
  d20: number
  attack_roll: number
  attack_bonus: number
  target_ac: number
  hit: boolean
  critical: boolean
  damage: number | null
  damage_notation: string
}

// ─── TTS / Audio ──────────────────────────────────────────────────────────────

export type TtsBackend = 'kokoro' | 'vllm'

export interface TtsSettings {
  tts_enabled: boolean
  tts_backend: TtsBackend
  tts_async: boolean
  voxtral_base_url: string
  voxtral_model: string
}

export interface TtsHealthResponse {
  kokoro: boolean
  vllm: boolean
}

export interface AudioPayload {
  audio_b64: string
  narration_id: string
}

// ─── Save / Load ──────────────────────────────────────────────────────────────

export interface SaveSlot {
  id: string
  session_id: string
  name: string
  phase: string
  turn_number: number
  round_number: number
  characters_count: number
  created_at: string
}

export interface SaveSlotListResponse {
  saves: SaveSlot[]
  total: number
}

export interface HistoryMessage {
  id: string
  role: 'gm' | 'player' | 'system'
  speaker: string
  message_type: 'narration' | 'dialogue' | 'action' | 'roll_result' | 'system'
  content: string
  metadata: Record<string, unknown> | null
  created_at: string
}

export interface HistoryResponse {
  messages: HistoryMessage[]
  total: number
}

// ─── LLM / Provider ───────────────────────────────────────────────────────────

export type LlmProvider = 'ollama' | 'openai_compatible'

export interface OllamaHealthResponse {
  available: boolean
  models: string[]
  gm_model: string
  player_model: string
}

export interface LlmSettings {
  ollama_base_url: string
  gm_model: string
  player_model: string
  llm_provider: LlmProvider
  openai_base_url: string
  api_key_set: boolean
  ollama_api_key_set: boolean
}

export interface LlmSettingsUpdate {
  ollama_base_url?: string
  gm_model?: string
  player_model?: string
  llm_provider?: LlmProvider
  openai_base_url?: string
  openai_api_key?: string
  ollama_api_key?: string
}

// ─── Campaign ─────────────────────────────────────────────────────────────────

export interface Campaign {
  id: string
  name: string
  description: string
  session_ids: string[]
  current_session_index: number
  character_ids: string[]
  xp_pool: Record<string, number>
  created_at: string
  updated_at: string
}

export interface CampaignCreate {
  name: string
  description?: string
}

export interface CampaignAdvanceBody {
  new_session_name: string
}

export interface CampaignAdvanceResponse {
  campaign: Campaign
  new_session_id: string
  characters_transferred: number
}
