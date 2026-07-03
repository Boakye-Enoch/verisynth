// ── Core event types (mirror server/event_bus.py constants) ──────────────────

export const EVENT_TYPES = {
  SIM_START:      'SIM_START',
  SIM_STOP:       'SIM_STOP',
  VEHICLE_UPDATE: 'VEHICLE_UPDATE',
  ATTACK_STATUS:  'ATTACK_STATUS',
  ATTACK_START:   'ATTACK_START',
  ATTACK_END:     'ATTACK_END',
  IDS_ALERT:      'IDS_ALERT',
  TRUST_CHANGE:   'TRUST_CHANGE',
  TRUST_SNAPSHOT: 'TRUST_SNAPSHOT',
  SCENE_CHANGE:   'SCENE_CHANGE',
  MODEL_STATUS:   'MODEL_STATUS',
  SYSTEM_HEALTH:  'SYSTEM_HEALTH',
  PING:           'PING',
} as const

export type EventType = typeof EVENT_TYPES[keyof typeof EVENT_TYPES]

// ── Payloads ──────────────────────────────────────────────────────────────────

export interface BusEvent {
  event_id: string
  seq:      number
  type:     string
  payload:  Record<string, unknown>
  timestamp: number
  sim_step: number
  sim_time: number
}

export interface VehicleState {
  vehicle_id:      string
  x:               number
  y:               number
  speed:           number
  heading:         number
  trust_score:     number
  composite_score: number
  verdict:         'NORMAL' | 'WARN' | 'ISOLATE' | 'RESTORE'
  is_attacked:     boolean
  attack_type:     string | null
  is_isolated:     boolean
  ids_confidence:  number
  anomaly_score:   number
}

export interface VehicleUpdate {
  vehicles:       VehicleState[]
  active_count:   number
  isolated_count: number
  warned_count:   number
  avg_trust:      number
}

export interface AttackInfo {
  attack_type:    string
  enabled:        boolean
  active:         boolean
  start_step:     number
  end_step:       number
  total_injected: number
  run_count:      number
}

export interface AttackStatus {
  attacks:        AttackInfo[]
  total_injected: number
  any_active:     boolean
}

export interface IDSAlert {
  vehicle_id:     string
  alert_type:     string
  severity:       'HIGH' | 'MEDIUM' | 'LOW' | 'CRITICAL'
  confidence:     number
  action:         string
  source:         string
  rule_triggered: string | null
  anomaly_score:  number
  fused_score:    number
  n_detectors:    number
  corroborated:   boolean
  trust_at_alert: number
  // added by store
  sim_step?:      number
  sim_time?:      number
  received_at?:   number
}

export interface TrustEntry {
  vehicle_id:      string
  trust_score:     number
  composite_score: number
  verdict:         string
  isolated:        boolean
  warned:          boolean
}

export interface TrustSnapshot {
  vehicles:       TrustEntry[]
  avg_trust:      number
  min_trust:      number
  max_trust:      number
  isolated_count: number
  warned_count:   number
}

export interface ModelStatus {
  cnn_trained:        boolean
  cnn_val_acc:        number
  cnn_rounds:         number
  ae_trained:         boolean
  ae_threshold:       number
  ae_drift_count:     number
  ae_drift_retrains:  number
  ae_replay_buf_size: number
  zero_day_alerts:    number
  critical_alerts:    number
  zero_day_vehicles:  string[]
  fl_round:           number
  fl_strategy:        string
  total_predictions:  number
  detection_rate:     number
}

export interface SystemHealth {
  cpu_percent:         number
  memory_percent:      number
  gpu_percent:         number
  ws_clients:          number
  event_bus_published: number
  event_bus_dropped:   number
  sim_step:            number
  sim_fps:             number
  packet_throughput:   number
}

export interface SimState {
  running:         boolean
  sim_step:        number
  sim_time:        number
  current_town:    string
  current_weather: string
  peak_vehicles:   number
  total_alerts:    number
  total_injected:  number
  wall_time_s:     number
}

export interface SceneChange {
  change_type:     string
  value:           string
  success:         boolean
  current_town:    string
  current_weather: string
  sun_altitude:    number
  requested_by:    string
}

// ── Attack colors & icons (for UI rendering) ──────────────────────────────────

export const ATTACK_COLORS: Record<string, string> = {
  REPLAY:      '#f59e0b',
  SPOOFING:    '#ef4444',
  DOS:         '#f97316',
  SYBIL:       '#8b5cf6',
  GPS_SPOOFING:'#06b6d4',
  FORCEFUL:    '#ec4899',
}

export const SEVERITY_COLORS: Record<string, string> = {
  HIGH:     '#ef4444',
  CRITICAL: '#dc2626',
  MEDIUM:   '#f59e0b',
  LOW:      '#10b981',
}

export const VERDICT_COLORS: Record<string, string> = {
  NORMAL:  '#10b981',
  WARN:    '#f59e0b',
  ISOLATE: '#ef4444',
  RESTORE: '#06b6d4',
}
