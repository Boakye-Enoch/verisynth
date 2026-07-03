import { ATTACK_COLORS, SEVERITY_COLORS, VERDICT_COLORS } from './types'

export function trustColor(score: number): string {
  if (score >= 0.7) return '#10b981'
  if (score >= 0.45) return '#f59e0b'
  if (score >= 0.25) return '#f97316'
  return '#ef4444'
}

export function verdictColor(verdict: string): string {
  return VERDICT_COLORS[verdict] ?? '#94a3b8'
}

export function attackColor(type: string): string {
  return ATTACK_COLORS[type] ?? '#94a3b8'
}

export function severityColor(sev: string): string {
  return SEVERITY_COLORS[sev] ?? '#94a3b8'
}

export function formatTime(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  return [h, m, s].map(v => String(v).padStart(2, '0')).join(':')
}

export function formatSimTime(simTime: number): string {
  const base = 14 * 3600 + 32 * 60 + 18
  const t = base + simTime
  const h = Math.floor(t / 3600) % 24
  const m = Math.floor((t % 3600) / 60)
  const s = Math.floor(t % 60)
  return [h, m, s].map(v => String(v).padStart(2, '0')).join(':')
}

export function threatLevel(alerts: number, isolated: number): { level: string; color: string } {
  if (isolated > 2 || alerts > 20) return { level: 'CRITICAL', color: '#dc2626' }
  if (isolated > 0 || alerts > 5)  return { level: 'HIGH',     color: '#ef4444' }
  if (alerts > 0)                   return { level: 'MEDIUM',   color: '#f59e0b' }
  return { level: 'LOW', color: '#10b981' }
}
