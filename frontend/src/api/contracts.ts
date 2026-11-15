// ABOUTME: TypeScript types of the LunarNav contracts and API requests, generated from Pydantic
// ABOUTME: Do not edit: run `uv run python scripts/api_export_types.py` after a contract change

export type AiAnswer = {
  requirements: MissionRequirements
  ranking: SiteRanking | null
  message: string
}

export type AiRequest = {
  text: string
  history: ChatMessage[]
  requirements: MissionRequirements | null
  locked_fields: string[]
  default_window: TimeWindow
}

export type ChatMessage = {
  role: "user" | "assistant"
  text: string
}

export type CompareRequest = {
  scenarios: EvaluateRequest[]
}

export type DateShiftResult = {
  shift_days: number
  metrics: VisibilityMetrics
}

export type DispersionSample = {
  location: GeoPoint
  offset_m: number
  metrics: VisibilityMetrics
  slope_max_deg: number
}

export type EphemerisSeries = {
  location: GeoPoint
  times_utc: string[]
  sun_azimuth_deg: number[]
  sun_elevation_deg: number[]
  earth_azimuth_deg: number[]
  earth_elevation_deg: number[]
  source: string
}

export type EvaluateRequest = {
  site_id?: string | null
  location?: GeoPointInput | null
  window: TimeWindowInput
  area?: OperationsAreaInput
}

export type Evaluation = {
  site_id: string | null
  location: GeoPoint
  window: TimeWindow
  area: OperationsArea
  times_utc: string[]
  sun_azimuth_deg: number[]
  sun_elevation_deg: number[]
  sun_horizon_elevation_deg: number[]
  sun_visible: boolean[]
  earth_azimuth_deg: number[]
  earth_elevation_deg: number[]
  earth_horizon_elevation_deg: number[]
  earth_visible: boolean[]
  horizon: HorizonMask
  terrain: TerrainStats
  metrics: VisibilityMetrics
}

export type ExplainRequest = {
  ranking: SiteRankingInput
  language_hint?: string
}

export type GeoPointInput = {
  lat_deg: number
  lon_deg: number
  height_m?: number | null
}

export type GeoPoint = {
  lat_deg: number
  lon_deg: number
  height_m: number | null
}

export type HorizonMask = {
  location: GeoPoint
  azimuth_deg: number[]
  horizon_elevation_deg: number[]
  dem_source: string
  dem_resolution_m: number
  max_distance_m: number
}

export type MissionAnalysisRequest = {
  site_id?: string | null
  location?: GeoPointInput | null
  window: TimeWindowInput
  area?: OperationsAreaInput
  shifts_days?: number[]
}

export type MissionRequirementsInput = {
  window?: TimeWindowInput | null
  area?: OperationsAreaInput | null
  min_illumination_fraction?: number | null
  min_continuous_light_h?: number | null
  max_continuous_dark_h?: number | null
  min_sun_elevation_deg?: number | null
  min_earth_visibility_fraction?: number | null
  min_continuous_earth_visibility_h?: number | null
  max_earth_outage_h?: number | null
  min_sun_and_earth_visible_fraction?: number | null
  max_slope_deg?: number | null
  latitude_min_deg?: number | null
  latitude_max_deg?: number | null
  origins?: Origin[] | null
  archetype_id?: string | null
  field_sources?: Record<string, RequirementSource>
  rationale?: Record<string, string>
  source_request?: string | null
}

export type MissionRequirements = {
  window: TimeWindow | null
  area: OperationsArea | null
  min_illumination_fraction: number | null
  min_continuous_light_h: number | null
  max_continuous_dark_h: number | null
  min_sun_elevation_deg: number | null
  min_earth_visibility_fraction: number | null
  min_continuous_earth_visibility_h: number | null
  max_earth_outage_h: number | null
  min_sun_and_earth_visible_fraction: number | null
  max_slope_deg: number | null
  latitude_min_deg: number | null
  latitude_max_deg: number | null
  origins: Origin[] | null
  archetype_id: string | null
  field_sources: Record<string, RequirementSource>
  rationale: Record<string, string>
  source_request: string | null
}

export type OperationsAreaInput = {
  landing_precision_m?: number
  operating_range_m?: number
  traverse_slope_limit_deg?: number
  observer_height_above_ground_m?: number
}

export type OperationsArea = {
  landing_precision_m: number
  operating_range_m: number
  traverse_slope_limit_deg: number
  observer_height_above_ground_m: number
}

export type Origin = "apollo" | "luna" | "surveyor" | "change" | "chandrayaan" | "slim" | "clps" | "artemis" | "other" | "user"

export type RequirementSource = "user" | "archetype" | "default"

export type RobustnessReport = {
  site_id: string | null
  nominal: VisibilityMetrics
  date_shifts: DateShiftResult[]
  dispersion: DispersionSample[]
  summary: string | null
}

export type Site = {
  id: string
  name: string
  location: GeoPoint
  origin: Origin
  status: "landed" | "planned" | "candidate" | "custom"
  mission: string | null
  agency: string | null
  landing_date_utc: string | null
  landing_ellipse_m: number | null
  description: string
  sources: string[]
}

export type SiteRankingInput = {
  requirements: MissionRequirementsInput
  results: SiteScoreInput[]
  weights?: Record<string, number>
  unavailable?: Record<string, string>
}

export type SiteRanking = {
  requirements: MissionRequirements
  results: SiteScore[]
  weights: Record<string, number>
  unavailable: Record<string, string>
}

export type SiteScoreInput = {
  site_id: string
  rank: number
  score: number
  constraints_met: Record<string, boolean>
  criterion_values?: Record<string, number>
  all_constraints_met: boolean
  metrics: VisibilityMetrics
  landing_slope_max_deg: number
  rationale?: string | null
}

export type SiteScore = {
  site_id: string
  rank: number
  score: number
  constraints_met: Record<string, boolean>
  criterion_values: Record<string, number>
  all_constraints_met: boolean
  metrics: VisibilityMetrics
  landing_slope_max_deg: number
  rationale: string | null
}

export type SkyState = {
  time_utc: string
  subsolar: GeoPoint
  sub_earth: GeoPoint
  source: string
}

export type TerrainStats = {
  location: GeoPoint
  radius_m: number
  elevation_m: number
  slope_mean_deg: number
  slope_max_deg: number
  landing_radius_m: number
  landing_slope_mean_deg: number
  landing_slope_max_deg: number
  traverse_slope_limit_deg: number
  reachable_fraction: number | null
  dem_source: string
  dem_resolution_m: number
}

export type TimeWindowInput = {
  start_utc: string
  end_utc: string
  step_minutes?: number
}

export type TimeWindow = {
  start_utc: string
  end_utc: string
  step_minutes: number
}

export type UpdateSiteRequest = {
  name?: string | null
  description?: string | null
}

export type VisibilityMetrics = {
  illumination_fraction: number
  sun_elevation_max_deg: number
  sun_elevation_mean_visible_deg: number | null
  longest_light_h: number
  longest_light_truncated: boolean
  longest_dark_h: number
  longest_dark_truncated: boolean
  earth_visibility_fraction: number
  earth_elevation_mean_visible_deg: number | null
  longest_earth_visible_h: number
  longest_earth_visible_truncated: boolean
  longest_earth_hidden_h: number
  longest_earth_hidden_truncated: boolean
  sun_and_earth_visible_fraction: number
  sun_visible_at_start: boolean
  earth_visible_at_start: boolean
  next_sunset_utc: string | null
  next_sunrise_utc: string | null
  next_earthset_utc: string | null
  next_earthrise_utc: string | null
}
