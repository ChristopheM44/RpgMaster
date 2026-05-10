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
  character_count: number
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
  hit_dice?: HitDiceState
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
  hit_dice: HitDiceState
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
  hit_dice?: HitDiceState
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

export interface HitDiceState {
  die: number
  total: number
  used: number
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

// ─── Campaign Maps ───────────────────────────────────────────────────────────

export type NodeStatus = 'visited' | 'known' | 'current' | 'rumored'
export type RegionNodeKind = 'settlement' | 'landmark' | 'wilderness' | 'dungeon' | 'crossroads' | 'ruin'
export type CityNodeKind = 'district' | 'building' | 'square' | 'gate' | 'docks' | 'temple' | 'tavern' | 'shop' | 'palace'
export type EdgeKind = 'road' | 'path' | 'river' | 'sea_route' | 'secret' | 'street' | 'alley'

export interface MapNodePosition {
  x: number
  y: number
}

export interface MapNode {
  id: string
  name: string
  kind: RegionNodeKind | CityNodeKind
  position: MapNodePosition
  status: NodeStatus
  icon?: string
  description?: string
  short_label?: string
  city_id?: string
  scene_ids?: string[]
}

export interface MapEdge {
  id: string
  from: string
  to: string
  kind: EdgeKind
  travel_hint?: string
  hidden?: boolean
}

export interface RegionMap {
  id: string
  name: string
  current_node_id?: string
  nodes: MapNode[]
  edges: MapEdge[]
  background_seed?: string
  updated_at: string
}

export interface CityMap {
  id: string
  region_node_id: string
  name: string
  current_node_id?: string
  nodes: MapNode[]
  edges: MapEdge[]
  background_seed?: string
  updated_at: string
}

export interface RegionMapUpdatedPayload {
  region_map: RegionMap | null
  active_city_id?: string | null
}

export interface CityMapUpdatedPayload {
  city_map: CityMap | null
  active_city_id?: string | null
}

// ─── WebSocket Protocol ───────────────────────────────────────────────────────

export const WS_EVENT_TYPES_LIST = [
  'session_state',
  'narration',
  'dialogue',
  'roll_result',
  'damage_applied',
  'turn_start',
  'turn_end',
  'round_start',
  'phase_change',
  'combat_start',
  'combat_end',
  'combat_action',
  'combatant_moved',
  'combatant_status_changed',
  'combatant_removed',
  'action_economy_changed',
  'opportunity_attack_triggered',
  'hp_changed',
  'condition_changed',
  'death_save_updated',
  'spell_slot_updated',
  'equipment_updated',
  'hit_dice_updated',
  'player_joined',
  'player_left',
  'ai_thinking',
  'audio',
  'error',
  'pong',
  'journal_updated',
  'quest_updated',
  'chronicle_updated',
  'scene_layout_changed',
  'social_outcome',
  'region_map_updated',
  'city_map_updated',
] as const

export type WsEventType = typeof WS_EVENT_TYPES_LIST[number]

export interface WsEvent<T = unknown> {
  event_type: WsEventType
  event_id?: string
  session_id?: string
  payload: T
  timestamp?: string
}

export type TimeOfDay = 'dawn' | 'morning' | 'noon' | 'afternoon' | 'dusk' | 'night'

export interface AdventureJournal {
  location_region: string | null
  location_place: string | null
  time_of_day: TimeOfDay
  day_number: number
  calendar_date: string | null
  weather: string | null
}

export type QuestCategory = 'principale' | 'secondaire' | 'rumeur'
export type QuestStatus = 'active' | 'completed' | 'failed'

export interface Quest {
  id: string
  category: QuestCategory
  title: string
  summary: string
  urgency?: string | null
  status: QuestStatus
}

export type ChronicleKind = 'npc' | 'location'

export interface ChronicleEntry {
  id: string
  kind: ChronicleKind
  name: string
  note: string
}

export interface PointOfInterest {
  id: string
  name: string
  kind: string
  position: GridPosition
  icon?: string
  description?: string
  action_hint?: string
  interactions?: ScenePoiInteraction[]
}

export type ScenePoiInteractionIntent =
  | 'approach'
  | 'talk'
  | 'examine'
  | 'listen'
  | 'search'
  | 'use'
  | 'custom'

export interface ScenePoiInteraction {
  id?: string
  label: string
  intent: ScenePoiInteractionIntent
  prompt?: string
  icon?: string
  default?: boolean
}

export interface SceneExit {
  id: string
  label: string
  position: GridPosition
  leads_to?: string
  description?: string
  icon?: string
  kind?: string
  type?: string
}

export interface SceneLayout {
  cols: number
  rows: number
  cell_size_m: number
  terrain?: string
  pois: PointOfInterest[]
  exits: SceneExit[]
  party_positions: Record<string, GridPosition>
  scene_id?: string
  region_node_id?: string
  city_node_id?: string
}

export interface SceneLayoutChangedPayload {
  scene: SceneLayout
}

export interface SessionStatePayload {
  session_id: string
  phase: string
  turn_number: number
  round_number: number
  turn_order: TurnEntry[]
  current_turn_index: number
  valid_transitions: string[]
  combatants?: CombatantState[]
  grid_config?: GridConfig
  grid_decoration?: GridDecoration | null
  adventure_journal?: AdventureJournal
  quests?: Quest[]
  chronicle?: ChronicleEntry[]
  current_scene?: SceneLayout | null
  region_map?: RegionMap | null
  city_maps?: Record<string, CityMap>
  active_city_id?: string | null
}

export interface TurnEntry {
  id: string
  name: string
  initiative: number
  is_ai: boolean
  is_ai_controlled?: boolean
  is_player: boolean
}

export interface NarrationPayload {
  text: string
  speaker?: string
  speaker_id?: string
  speaker_kind?: 'gm' | 'human' | 'companion' | 'npc' | 'monster'
  entry_kind?: 'narration' | 'dialogue' | 'action' | 'system'
  scene_id?: string
}

export interface RollResultPayload {
  dice_notation: string
  rolls: number[]
  total: number
  modifier: number
  dc?: number | null
  d20?: number
  breakdown?: string
  character_id?: string | null
  social_target_id?: string | null
  label?: string
  success?: boolean
  character_name?: string
}

export interface SocialOutcomePayload {
  npc_id: string
  attitude?: string
  note?: string
  new_quest?: Quest
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

export interface AiThinkingPayload {
  agent_kind: 'gm' | 'player_ai'
  thinking: boolean
  character_id?: string
  character_name?: string
}

// ─── Game UI State ────────────────────────────────────────────────────────────

export type NarrativeEntryType = 'narration' | 'dialogue' | 'roll' | 'system' | 'player' | 'combat_action'

export interface NarrativeEntry {
  id: string
  type: NarrativeEntryType
  text?: string
  speaker?: string
  speaker_id?: string
  speaker_kind?: NarrationPayload['speaker_kind']
  entry_kind?: NarrationPayload['entry_kind']
  scene_id?: string
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

export interface GridDecoration {
  obstacles?: GridPosition[]
  zones?: Array<{ id: string; name: string; cells: GridPosition[]; kind?: string; icon?: string; type?: string }>
}

export interface CombatantMovedPayload {
  combatant_id: string
  position: GridPosition
  movement_used_m: number
}

export interface ActionEconomyChangedPayload {
  combatant_id: string
  action_economy: NonNullable<CombatantState['action_economy']>
}

export interface OpportunityAttackTriggeredPayload {
  attacker_id: string
  target_id: string
  hit: boolean
  damage: number
}

export interface CombatantStatusChangedPayload {
  combatant_id: string
  combatant_name?: string
  status: 'active' | 'defeated' | 'surrendered' | 'fled' | string
  reason?: string
}

export interface CombatantRemovedPayload {
  combatant_id: string
  combatant_name?: string
  status: 'defeated' | 'surrendered' | 'fled' | string
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
  kind: 'pc' | 'monster'
  status?: 'active' | 'defeated' | 'surrendered' | 'fled' | string
  conditions: string[]
  is_ai: boolean
  is_ai_controlled?: boolean
  is_active: boolean
  position?: GridPosition
  death_saves?: DeathSaves
  ac: number
  attack_bonus?: number
  damage_notation?: string
  species?: string
  cr?: number | string
  token?: string
  color?: string
  ability_scores?: Record<string, number>
  actions?: Array<{
    name: string
    attack_bonus?: number
    damage_dice?: string
    description?: string
  }>
  description?: string
  action_economy?: {
    action: boolean
    bonus_action: boolean
    reaction: boolean
    movement: number
    movement_max?: number
    has_dashed?: boolean
    has_disengaged?: boolean
  }
  avatar_url?: string
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

export interface HitDiceUpdatedPayload {
  character_id: string
  hit_dice: HitDiceState
}

export interface CombatStartPayload {
  combatants: CombatantState[]
  grid_config?: GridConfig
  grid_decoration?: GridDecoration | null
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
  tagline: string
  generation_status: CampaignGenerationStatus
  active_chapter: CampaignVisibleChapter | Record<string, never>
  progress: CampaignProgress
  counts: CampaignCounts
}

export interface CampaignCreate {
  name: string
  description?: string
}

export type CampaignGenerationStatus = 'empty' | 'drafting' | 'draft' | 'validated' | 'failed'

export interface CampaignVisibleChapter {
  id: string
  num: string
  title: string
  state: 'done' | 'active' | 'planned'
  sessions: number
  summary: string
}

export interface CampaignProgress {
  done: number
  total: number
}

export interface CampaignCounts {
  sessions: number
  characters: number
  quests_active: number
  quests_done: number
  chronicle_entries: number
  npcs: number
  places: number
}

export interface CampaignPlayerContract {
  title: string
  pitch_public: string
  tones: string[]
  duration: string
  hook: string
  visible_chapters: CampaignVisibleChapter[]
  known_objectives: string[]
  played_summary: string
}

export interface CampaignScenario {
  campaign_id: string
  generation_status: CampaignGenerationStatus
  player_contract: CampaignPlayerContract
  timeline: CampaignVisibleChapter[]
  current_chapter: CampaignVisibleChapter | Record<string, never>
  known_objectives: string[]
  quests: Array<Record<string, unknown>>
  played_summary: string
}

export interface CampaignGmChapter {
  id?: string
  title?: string
  state?: 'done' | 'active' | 'planned' | string
  objective?: string
  stakes?: string
  initial_state?: string
  key_locations?: unknown[]
  involved_npcs?: unknown[]
  clues?: unknown[]
  secrets?: unknown[]
  complications?: unknown[]
  possible_exits?: unknown[]
  indicative_dcs?: unknown[]
  possible_srd_encounters?: string[]
}

export interface CampaignGmDossier {
  narrative_arc?: string
  chapters?: CampaignGmChapter[]
  important_npcs?: unknown[]
  locations?: unknown[]
  factions?: unknown[]
  secrets?: unknown[]
  revelations?: unknown[]
  fronts?: unknown[]
  quests?: unknown[]
  complications?: unknown[]
  clues?: unknown[]
  light_mechanics?: unknown[]
  [key: string]: unknown
}

export interface CampaignGmDossierResponse {
  campaign_id: string
  generation_status: CampaignGenerationStatus
  active_chapter_id: string
  gm_dossier: CampaignGmDossier
}

export interface CampaignForgeDraftResponse {
  campaign_id: string
  generation_status: CampaignGenerationStatus
  player_contract: CampaignPlayerContract
  active_chapter_id: string
}

export interface CampaignImportSourceBody {
  kind: 'url' | 'text' | 'file_text'
  title?: string
  url?: string
  content?: string
  filename?: string
}

export interface CampaignImportSourceResponse {
  source: {
    id: string
    kind: string
    title: string
    url?: string | null
    filename?: string | null
    created_at: string
  }
  source_count: number
}

export interface CampaignAdvanceBody {
  new_session_name: string
}

export interface CampaignAdvanceResponse {
  campaign: Campaign
  new_session_id: string
  characters_transferred: number
}
