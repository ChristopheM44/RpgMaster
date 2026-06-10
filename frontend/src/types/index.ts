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
  xp?: number
  gp?: number
  sp?: number
  cp?: number
  equipment?: Array<Record<string, unknown> | EquipmentItem>
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
  xp: number
  gp: number
  sp: number
  cp: number
  xp_to_next_level: number
  pending_asi?: boolean
  equipment: EquipmentItem[]
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
  xp?: number
  gp?: number
  sp?: number
  cp?: number
  equipment?: EquipmentItem[]
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

export type EquipmentSlot =
  | 'main_hand'
  | 'off_hand'
  | 'body'
  | 'head'
  | 'hands'
  | 'feet'
  | 'neck'
  | 'ring_1'
  | 'ring_2'
  | 'back'
  | 'waist'

export type ItemType = 'weapon' | 'armor' | 'shield' | 'gear' | 'consumable' | 'magic'

export interface EquipmentItem {
  [key: string]: unknown
  id: string
  template_id?: string
  name?: string
  name_fr?: string
  category?: string
  item_type?: ItemType
  quantity?: number
  equipped?: boolean
  slot?: EquipmentSlot | string | null
  occupied_slots?: string[]
  weight_lb?: number
  cost_gp?: number
  rarity?: string
  attunement_required?: boolean
  attuned?: boolean
  identified?: boolean
  hidden_properties?: Record<string, unknown>
  properties?: string[]
  damage_dice?: string
  damage_type?: string
  base_ac?: number
  dex_cap?: number | null
  effect?: Record<string, unknown>
  detail?: string
  damage?: number
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
  name_fr?: string
  type?: string
  description?: string
  attack_bonus?: number
  reach_m?: number
  range_normal_m?: number
  range_long_m?: number
  targets?: number
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
  subtype?: string | null
  alignment: string
  ac: number
  ac_source?: string | null
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
  traits: { name: string; name_fr?: string; description?: string }[]
  actions: SrdMonsterAction[]
  reactions?: SrdMonsterAction[]
  legendary_actions?: SrdMonsterAction[]
  description?: string
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

// GameStateResponse est défini plus bas après SessionStatePayload

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

// ── Décor visuel (set-once, émis par le MJ) ──────────────────────────────────
export type CoastlineSide = 'west' | 'east' | 'north' | 'south'

export interface ForestSpot {
  x: number
  y: number
  radius?: number   // default 3.0
  opacity?: number  // default 0.4
}

export interface MountainSpot {
  x: number
  y: number
  height?: number   // default 5.0
}

export interface Coastline {
  side: CoastlineSide
  points: MapNodePosition[]
}

export interface RiverPath {
  path: string      // SVG path en coords 0..100
  width?: number    // default 1.5
}

export interface MapDecor {
  forests?: ForestSpot[]
  mountains?: MountainSpot[]
  coastline?: Coastline
  river?: RiverPath
  decorative_roads?: string[]  // paths SVG décoratifs
}

export type MapVisualAssetStatus = 'prompt_ready' | 'generating' | 'ready' | 'failed'

export interface MapVisualAsset {
  provider: string
  model: string
  status: MapVisualAssetStatus
  prompt: string
  prompt_hash: string
  url?: string
  generated_at?: string
  error?: string
}
// ─────────────────────────────────────────────────────────────────────────────

export interface RegionMap {
  id: string
  name: string
  current_node_id?: string
  nodes: MapNode[]
  edges: MapEdge[]
  background_seed?: string
  decor?: MapDecor
  visual_asset?: MapVisualAsset
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
  decor?: MapDecor
  visual_asset?: MapVisualAsset
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
  'session_reset',
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
  'xp_updated',
  'currency_updated',
  'level_up_available',
  'character_leveled_up',
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
  'clock_updated',
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
  source?: string
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
  element_id?: string
  state?: string
  visibility?: 'visible' | 'subtle' | 'hidden'
  discovered?: boolean
  physical_state?: string
  facts?: string[]
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
  mechanics?: ScenePoiInteractionMechanics
}

export interface ScenePoiRollMechanic {
  type?: 'check' | 'save'
  ability: 'str' | 'dex' | 'con' | 'int' | 'wis' | 'cha'
  skill?: string
  dc: number
  reason?: string
}

export interface ScenePoiInteractionMechanics {
  roll?: ScenePoiRollMechanic
  safe_observation?: boolean
  reveal_tier?: 'surface' | 'interpreted' | 'deep'
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
  element_id?: string
  placement?: 'edge' | 'embedded'
  active?: boolean
}

export type SceneTheme =
  | 'forest'
  | 'beach'
  | 'coastal'
  | 'rocky'
  | 'mountain'
  | 'dungeon'
  | 'cave'
  | 'city'
  | 'plains'
  | 'swamp'
  | 'desert'

export interface SceneLayout {
  cols: number
  rows: number
  cell_size_m: number
  terrain?: string
  scene_theme?: SceneTheme
  pois: PointOfInterest[]
  exits: SceneExit[]
  party_positions: Record<string, GridPosition>
  elements?: SceneElement[]
  visual_asset?: MapVisualAsset
  scene_id?: string
  region_node_id?: string
  city_node_id?: string
  state?: string
  physical_state?: string
  facts?: string[]
  /** Hints 3D optionnels émis par le MJ (défauts sûrs côté client et backend). */
  ambiance?: SceneAmbiance
  vegetation_density?: number
}

export interface SceneAmbiance {
  light?: 'day' | 'dusk' | 'night' | 'torchlit' | 'overcast'
  fog_density?: number
}

export type SceneElementKind =
  | 'wall'
  | 'door'
  | 'window'
  | 'furniture'
  | 'cover'
  | 'hazard'
  | 'light'
  | 'stairs'
  | 'terrain'
  | 'decor'

export type SceneElementGeometry =
  | { type: 'line'; from: { col: number; row: number }; to: { col: number; row: number } }
  | { type: 'rect'; col: number; row: number; width: number; height: number }
  | { type: 'ellipse'; col: number; row: number; radius_col: number; radius_row: number }

export type SceneTerrainType = 'road' | 'street' | 'path' | 'plaza_paving' | 'water' | 'mud'

export interface SceneElement {
  id: string
  name: string
  kind: SceneElementKind
  geometry: SceneElementGeometry
  terrain_type?: SceneTerrainType
  description?: string
  blocks_movement?: boolean
  opaque?: boolean
  interactive?: boolean
  visibility?: 'visible' | 'subtle' | 'hidden'
  discovered?: boolean
  state?: string
  physical_state?: string
  facts?: string[]
  /** Hints 3D optionnels (mètres) — défauts par kind si absents. */
  height_m?: number
  elevation_m?: number
}

export interface SceneLayoutChangedPayload {
  scene: SceneLayout
}

export type SceneClockSeverity = 'low' | 'medium' | 'high' | 'critical'
export type SceneClockStatus = 'active' | 'paused' | 'filled' | 'resolving' | 'resolved'

export interface SceneClockOnFill {
  mode?: 'roll' | 'narrative' | 'transition'
  roll?: ScenePoiRollMechanic
  narration?: string
  next_clock?: Partial<SceneClock>
}

export interface SceneClock {
  id: string
  label: string
  scope: string
  current: number
  max: number
  severity: SceneClockSeverity
  status: SceneClockStatus
  tick_on?: string
  linked_quest_id?: string | null
  on_fill?: SceneClockOnFill
}

export type ClockUpdatedPayload = SceneClock

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
  reachable_cells?: Record<string, ReachableCells>
  adventure_journal?: AdventureJournal
  quests?: Quest[]
  chronicle?: ChronicleEntry[]
  current_scene?: SceneLayout | null
  scene_clocks?: SceneClock[]
  region_map?: RegionMap | null
  city_maps?: Record<string, CityMap>
  active_city_id?: string | null
}

export interface GameStateResponse extends SessionStatePayload {}

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
  narration_id?: string
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
  critical?: boolean
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
  equipment: EquipmentItem[]
  added?: EquipmentItem[]
  removed?: string
  source?: string
}

export interface XpUpdatedPayload {
  character_id: string
  old_xp?: number
  new_xp: number
  xp?: number
  level: number
  target_level?: number
  xp_to_next_level: number
}

export interface CurrencyUpdatedPayload {
  character_id: string
  gp: number
  sp: number
  cp: number
}

export interface LevelUpAvailablePayload {
  character_id: string
  current_level: number
  target_level: number
  xp: number
}

export interface CharacterLeveledUpPayload {
  character_id: string
  old_level: number
  new_level: number
  level?: number
  hp_delta: number
  hp: number
  hp_max: number
  spell_slots: Record<string, { total: number; used: number }>
  hit_dice: HitDiceState
  asi_levels_granted?: number[]
  requires_asi?: boolean
  xp_to_next_level?: number
}

export interface LevelUpApiResponse {
  character: Character
  old_level: number
  new_level: number
  hp_gained: number
  requires_asi: boolean
  asi_levels_granted: number[]
}

export interface AsiChoicePayload {
  mode: 'plus_two' | 'plus_one_two'
  ability?: string
  abilities?: [string, string]
}

export interface TurnStartPayload {
  combatant_id: string
  combatant_name?: string
}

export interface AiThinkingPayload {
  agent_kind: 'gm' | 'player_ai' | 'npc'
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
  narration_id?: string
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
  scene_theme?: SceneTheme
}

export interface GridDecoration {
  obstacles?: GridPosition[]
  difficult?: GridPosition[]
  zones?: Array<{ id: string; name: string; cells: GridPosition[]; kind?: string; icon?: string; type?: string }>
}

export interface ReachableCells {
  free: GridPosition[]
  with_dash: GridPosition[]
  paths?: Record<string, GridPosition[]>
}

export interface CombatantMovedPayload {
  combatant_id: string
  position: GridPosition
  movement_used_m: number
  path?: GridPosition[]
  interrupted?: boolean
  reason?: string
}

export interface ActionEconomyChangedPayload {
  combatant_id: string
  action_economy: NonNullable<CombatantState['action_economy']>
  reachable_cells?: ReachableCells
}

export interface OpportunityAttackTriggeredPayload {
  attacker_id: string
  attacker_name?: string
  target_id: string
  target_name?: string
  hit: boolean
  critical?: boolean
  d20?: number
  attack_total?: number
  target_ac?: number
  damage: number
  damage_notation?: string
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
  speed_m?: number
  reach_m?: number
  attack_range_m?: number
  actions?: Array<{
    name: string
    type?: string
    attack_bonus?: number
    damage_dice?: string
    damage_type?: string
    reach_m?: number
    range_m?: number
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
  reachable_cells?: Record<string, ReachableCells>
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

export interface TtsVoiceSettings {
  preset_id: string
  voice_id_local: string
  lang: string
  speed: number
}

export interface TtsSettings {
  tts_enabled: boolean
  tts_backend: TtsBackend
  tts_async: boolean
  voxtral_base_url: string
  voxtral_model: string
  gm_voice: TtsVoiceSettings
  npc_voice_enabled: boolean
}

export interface TtsHealthResponse {
  kokoro: boolean
  vllm: boolean
}

export interface TtsPreviewRequest {
  text: string
  gm_voice?: TtsVoiceSettings
}

export interface TtsPreviewResponse {
  audio_b64: string
}

export interface AudioPayload {
  narration_id: string
  status?: 'generating' | 'ready' | 'error'
  audio_b64?: string
  speaker?: string
  speaker_kind?: NarrationPayload['speaker_kind']
  message?: string
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
  source_max_chars: number
}

export interface LlmSettingsUpdate {
  ollama_base_url?: string
  gm_model?: string
  player_model?: string
  llm_provider?: LlmProvider
  openai_base_url?: string
  openai_api_key?: string
  ollama_api_key?: string
  source_max_chars?: number
}

export interface OllamaModelInfo {
  model: string
  family: string | null
  families: string[]
  parameter_size: string | null
  quantization_level: string | null
  format: string | null
  context_length: number | null
  num_ctx: number | null
}

export type ImageGenerationProvider = 'openai_compatible' | 'local'

export interface ImageGenerationSettings {
  enabled: boolean
  provider: ImageGenerationProvider
  base_url: string
  model: string
  api_key_set: boolean
  size: string
}

export interface ImageGenerationSettingsUpdate {
  enabled?: boolean
  provider?: ImageGenerationProvider
  base_url?: string
  model?: string
  api_key?: string
  size?: string
}

// ─── Campaign ─────────────────────────────────────────────────────────────────

export interface Campaign {
  id: string
  name: string
  description: string
  starting_level: number
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
  session_summaries?: CampaignSessionSummary[]
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

export interface CampaignSessionSummary {
  id: string
  name: string
  status: SessionStatus
  created_at: string
  updated_at: string
  character_count: number
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

export interface CampaignForgeJobEvent {
  at: string
  type: string
  phase?: string
  message: string
  provider?: string
  attempt?: number
  max_attempts?: number
  delay?: number
  error?: string
}

export interface CampaignForgeJobResponse {
  job_id: string
  campaign_id: string
  status: 'queued' | 'running' | 'completed' | 'failed'
  generation_status: CampaignGenerationStatus
  phase: string
  current_step: number
  total_steps: number
  retry_count: number
  events: CampaignForgeJobEvent[]
  message: string
  player_contract?: CampaignPlayerContract | null
  active_chapter_id?: string
  error?: string | null
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

export interface CampaignResetResponse {
  campaign: Campaign
  session_id: string
  characters_reset: number
  sessions_removed: number
}

export interface ChronicleArchiveManifest {
  campaign: {
    id: string
    name: string
    updated_at?: string
  }
  sessions: Array<{
    id: string
    name: string
    status: SessionStatus | string
    created_at?: string
    updated_at?: string
  }>
  includes: {
    gm_private: boolean
    messages: number
    save_slots: number
    characters: number
    assets: boolean
  }
  warnings?: string[]
  [key: string]: unknown
}

export interface ChronicleArchivePayload {
  format: 'rpgmaster.chronicle'
  format_version: number
  exported_at?: string
  app_version?: string
  manifest?: ChronicleArchiveManifest
  campaign?: Record<string, unknown>
  dossier?: Record<string, unknown> | null
  sessions?: Array<Record<string, unknown>>
  [key: string]: unknown
}

export interface ChronicleImportConflict {
  kind: string
  id: string
}

export interface ChronicleImportPreview {
  manifest: ChronicleArchiveManifest
  conflicts: ChronicleImportConflict[]
  warnings: string[]
}

export interface ChronicleImportResponse {
  campaign: Campaign
  active_session_id: string | null
  imported: {
    sessions: number
    characters: number
    messages: number
    save_slots: number
    game_states?: number
  }
  warnings: string[]
}
