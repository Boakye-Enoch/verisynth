import { useSOCStore } from '../store'
import { threatLevel } from '../utils'

export default function KPIRow() {
  const vehicles = useSOCStore(s => s.vehicles)
  const alerts   = useSOCStore(s => s.alerts)
  const attacks  = useSOCStore(s => s.attacks)
  const sim      = useSOCStore(s => s.sim)
  const health   = useSOCStore(s => s.health)

  const isolated    = vehicles.filter(v => v.is_isolated).length
  const warned      = vehicles.filter(v => v.verdict === 'WARN').length
  const activeAtks  = attacks.filter(a => a.active).length
  const totalInj    = attacks.reduce((a, b) => a + b.total_injected, 0)
  const avgTrust    = vehicles.length > 0
    ? (vehicles.reduce((a, v) => a + v.trust_score, 0) / vehicles.length).toFixed(3)
    : '0.000'
  const threat = threatLevel(alerts.length, isolated)

  const kpis = [
    { label: 'Vehicles',      value: vehicles.length, sub: `Isolated: ${isolated}`, color: '#60a5fa' },
    { label: 'Active Attacks', value: activeAtks,      sub: `${totalInj.toLocaleString()} injected`, color: activeAtks > 0 ? '#ef4444' : '#10b981' },
    { label: 'IDS Alerts',    value: alerts.length,   sub: `Session total`, color: '#f59e0b' },
    { label: 'Avg Trust',     value: avgTrust,         sub: `Warned: ${warned}`, color: '#10b981' },
    { label: 'Threat Level',  value: threat.level,     sub: `${isolated} isolated`, color: threat.color },
    { label: 'Sim Step',      value: sim.sim_step.toLocaleString(), sub: `of 6,000`, color: '#8b5cf6' },
  ]

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6,1fr)', gap: 8 }}>
      {kpis.map(k => (
        <div key={k.label} style={{
          background: 'var(--bg2)', border: '1px solid var(--border)',
          borderRadius: 8, padding: '10px 12px',
        }}>
          <div style={{ fontSize: 9, color: '#64748b', textTransform: 'uppercase', letterSpacing: '.8px', marginBottom: 4 }}>
            {k.label}
          </div>
          <div style={{ fontSize: 20, fontWeight: 700, color: k.color, lineHeight: 1 }}>
            {k.value}
          </div>
          <div style={{ fontSize: 10, color: '#64748b', marginTop: 3 }}>{k.sub}</div>
        </div>
      ))}
    </div>
  )
}
