// ABOUTME: TypeScript types of the LunarNav contracts and API requests, generated from Pydantic
// ABOUTME: Do not edit: run `uv run python scripts/api_export_types.py` after a contract change

export type AiAnswer = {
  requirements: MissionRequirements
  ranking: SiteRanking
  message: string
}

export type AskRequest = {
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
  location?: GeoPoint | null
  window: TimeWindow
  area?: OperationsArea
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

export type GeoPoint = {
  lat_deg: number
  lon_deg: number
  height_m?: number | null
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
  location?: GeoPoint | null
  window: TimeWindow
  area?: OperationsArea
  shifts_days?: number[]
}

export type MissionRequirements = {
  window?: TimeWindow | null
  area?: OperationsArea | null
  min_illumination_fraction?: number | null
  min_continuous_light_h?: number | null
  min_sun_elevation_deg?: number | null
  min_earth_visibility_fraction?: number | null
  min_continuous_earth_visibility_h?: number | null
  min_sun_and_earth_visible_fraction?: number | null
  max_slope_deg?: number | null
  latitude_min_deg?: number | null
  latitude_max_deg?: number | null
  origins?: Origin[] | null
  rationale?: Record<string, string>
  source_request?: string | null
}

export type OperationsArea = {
  landing_precision_m?: number
  operating_range_m?: number
}

export type Origin = "apollo" | "luna" | "surveyor" | "change" | "chandrayaan" | "slim" | "clps" | "artemis" | "other" | "user"

export type RobustnessReport = {
  site_id: string | null
  nominal: VisibilityMetrics
  date_shifts: DateShiftResult[]
  dispersion: DispersionSample[]
  summary?: string | null
}

export type Site = {
  id: string
  name: string
  location: GeoPoint
  origin: Origin
  status: "landed" | "planned" | "candidate" | "custom"
  mission?: string | null
  agency?: string | null
  landing_date_utc?: string | null
  landing_ellipse_m?: number | null
  description?: string
  sources?: string[]
}

export type SiteRanking = {
  requirements: MissionRequirements
  results: SiteScore[]
}

export type SiteScore = {
  site_id: string
  rank: number
  score: number
  constraints_met: Record<string, boolean>
  all_constraints_met: boolean
  metrics: VisibilityMetrics
  slope_max_deg: number
  rationale?: string | null
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
  dem_source: string
  dem_resolution_m: number
}

export type TimeWindow = {
  start_utc: string
  end_utc: string
  step_minutes?: number
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
