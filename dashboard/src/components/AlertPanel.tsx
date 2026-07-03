import { useSOCStore } from '../store'
import { severityColor, attackColor } from '../utils'
import type { IDSAlert } from '../types'

const ATTACK_ICONS: Record<string, string> = {
  REPLAY:           '↩',
  SPOOFING:         '📍',
  DOS:              '💥',
  SYBIL:            '👻',
  GPS_SPOOFING:     '🛰',
  FORCEFUL:         '⚡',
  UNKNOWN_ANOMALY:  '⚠',
  ZERO_DAY:         '🔴',
  CRITICAL_ZERO_DAY:'🚨',
}

export default function AlertPanel({ maxItems = 50 }: { maxItems?: number }) {
  const alerts = useSOCStore(s => s.alerts)
  const shown  = alerts.slice(0, maxItems)

  return (
    <div style={{
      background: 'var(--bg2)', border: '1px solid var(--border)',
      borderRadius: 8, height: '100%', display: 'flex', flexDirection: 'column',
      overflow: 'hidden',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '8px 12px', borderBottom: '1px solid var(--border)',
        background: 'var(--bg1)',
      }}>
        <span style={{ fontSize: 12, fontWeight: 600 }}>Live IDS Alerts</span>
        <span style={{
          padding: '1px 6px', borderRadius: 10, fontSize: 9, fontWeight: 700,
          background: 'rgba(239,68,68,.2)', color: '#ef4444',
        }}>{alerts.length}</span>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '4px 0' }}>
        {shown.length === 0 ? (
          <div style={{ padding: 16, textAlign: 'center', color: '#475569', fontSize: 11 }}>
            No alerts yet
          </div>
        ) : shown.map((alert, i) => (
          <AlertRow key={`${alert.vehicle_id}-${alert.sim_step}-${i}`} alert={alert} />
        ))}
      </div>
    </div>
  )
}

function AlertRow({ alert }: { alert: IDSAlert }) {
  const col = severityColor(alert.severity)
  const icon = ATTACK_ICONS[alert.alert_type] ?? '⚠'

  return (
    <div className="alert-in" style={{
      display: 'flex', gap: 8, padding: '6px 12px',
      borderBottom: '1px solid var(--border)',
    }}>
      <div style={{
        width: 28, height: 28, borderRadius: 6, flexShrink: 0,
        background: `${col}18`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 14,
      }}>{icon}</div>

      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: col }}>
          {alert.alert_type.replace(/_/g, ' ')}
        </div>
        <div style={{ fontSize: 10, color: '#64748b', marginTop: 1 }}>
          Vehicle {alert.vehicle_id} · Conf: {alert.confidence.toFixed(3)} · {alert.source}
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 2, flexShrink: 0 }}>
        <span style={{
          fontSize: 9, padding: '1px 5px', borderRadius: 3, fontWeight: 700,
          background: `${col}22`, color: col,
        }}>{alert.severity}</span>
        <span style={{ fontSize: 9, color: '#475569' }}>
          {alert.action}
        </span>
        <span style={{ fontSize: 9, color: '#334155' }}>
          step {alert.sim_step}
        </span>
      </div>
    </div>
  )
}
