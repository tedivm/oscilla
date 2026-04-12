/**
 * TypeScript interfaces mirroring the Pydantic response models from the Oscilla API.
 * Field names are snake_case to match FastAPI's default JSON serialization (no alias_generator).
 * UUIDs are typed as string; timestamps are ISO 8601 strings from datetime fields,
 * and integer tick/epoch values are typed as number.
 */

// ── Auth ─────────────────────────────────────────────────────────────────────

export interface TokenPairRead {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
}

export interface UserRead {
  id: string;
  email: string | null;
  display_name: string | null;
  is_email_verified: boolean;
  is_active: boolean;
  created_at: string;
}

// ── Games ────────────────────────────────────────────────────────────────────

export interface GameFeatureFlags {
  has_skills: boolean;
  has_quests: boolean;
  has_archetypes: boolean;
  has_ingame_time: boolean;
  has_recipes: boolean;
  has_loot_tables: boolean;
}

export interface GameRead {
  name: string;
  display_name: string;
  description: string | null;
  features: GameFeatureFlags;
}

// ── Characters ───────────────────────────────────────────────────────────────

/** Lightweight summary returned by GET /characters. */
export interface CharacterSummaryRead {
  id: string;
  name: string;
  game_name: string;
  prestige_count: number;
  created_at: string;
}

/**
 * A single stat value. `value` uses the raw stored type.
 * NOTE: `display_name` may be null — fall back to `ref` for display.
 */
export interface StatValue {
  ref: string;
  display_name: string | null;
  value: number | boolean | null;
}

/** Stackable inventory item. Use `ref` for display — no display_name field. */
export interface StackedItemRead {
  ref: string;
  quantity: number;
}

/** Non-stackable item instance. */
export interface ItemInstanceRead {
  instance_id: string;
  item_ref: string;
  charges_remaining: number | null;
  modifiers: Record<string, number>;
}

/**
 * A skill known by the character.
 * NOTE: cooldown state is NOT available from this model and must never be shown.
 */
export interface SkillRead {
  ref: string;
  display_name: string | null;
}

/** An active persistent buff. All expiry fields are optional ticks/epoch. */
export interface BuffRead {
  ref: string;
  remaining_turns: number | null;
  tick_expiry: number | null;
  game_tick_expiry: number | null;
  real_ts_expiry: number | null;
}

/** A quest currently tracked by the character. */
export interface ActiveQuestRead {
  ref: string;
  current_stage: string;
}

/** A milestone held by the character. */
export interface MilestoneRead {
  ref: string;
  grant_tick: number;
  grant_timestamp: number;
}

/** An archetype held by the character this iteration. */
export interface ArchetypeRead {
  ref: string;
  grant_tick: number;
  grant_timestamp: number;
}

/** The adventure and step the character is currently on. */
export interface ActiveAdventureRead {
  adventure_ref: string;
  step_index: number;
}

/**
 * Full character state. `character_class` is always null in the current API
 * and is scheduled for removal — do NOT use it.
 */
export interface CharacterStateRead {
  // Identity
  id: string;
  name: string;
  game_name: string;
  /** @deprecated Always null. Will be removed in a future API version. */
  character_class: string | null;
  prestige_count: number;
  pronoun_set: string;
  created_at: string;

  // Location
  current_location: string | null;
  current_location_name: string | null;
  current_region_name: string | null;

  // Stats
  stats: Record<string, StatValue>;

  // Inventory
  stacks: Record<string, StackedItemRead>;
  instances: ItemInstanceRead[];
  equipment: Record<string, ItemInstanceRead>;

  // Skills
  skills: SkillRead[];

  // Buffs
  active_buffs: BuffRead[];

  // Quests
  active_quests: ActiveQuestRead[];
  completed_quests: string[];
  failed_quests: string[];

  // Milestones
  milestones: Record<string, MilestoneRead>;

  // Archetypes
  archetypes: ArchetypeRead[];

  // Progress counters
  internal_ticks: number;
  game_ticks: number;

  // Active adventure (null when between adventures)
  active_adventure: ActiveAdventureRead | null;
}

// ── Play / SSE ────────────────────────────────────────────────────────────────

export interface AdventureOptionRead {
  ref: string;
  display_name: string;
  description: string;
}

export interface LocationOptionRead {
  ref: string;
  display_name: string;
  is_current: boolean;
}

export interface RegionGraphNode {
  id: string;
  label: string;
  kind: string;
}

export interface RegionGraphEdge {
  source: string;
  target: string;
  label: string;
}

export interface RegionGraphRead {
  nodes: RegionGraphNode[];
  edges: RegionGraphEdge[];
}

export interface OverworldStateRead {
  character_id: string;
  current_location: string | null;
  current_location_name: string | null;
  current_region_name: string | null;
  available_adventures: AdventureOptionRead[];
  navigation_options: LocationOptionRead[];
  region_graph: RegionGraphRead;
}

/**
 * Raw backend response from GET /play/current.
 * The client transforms this into CurrentPlayState (see api/play.ts).
 */
export interface PendingStateRead {
  character_id: string;
  pending_event: Record<string, unknown> | null;
  session_output: Record<string, unknown>[];
}

// ── SSE event data shapes ─────────────────────────────────────────────────────

export interface NarrativeEventData {
  text: string;
}

export interface ChoiceEventData {
  prompt: string;
  options: string[];
}

export interface CombatantState {
  name: string;
  hp: number;
  max_hp: number;
  is_player: boolean;
}

export interface CombatStateEventData {
  round: number;
  combatants: CombatantState[];
}

export interface TextInputEventData {
  prompt: string;
}

export interface SkillMenuEntry {
  id: string;
  name: string;
  description: string;
  on_cooldown: boolean;
}

export interface SkillMenuEventData {
  skills: SkillMenuEntry[];
}

export interface AdventureCompleteEventData {
  outcome: string;
  narrative: string;
}
