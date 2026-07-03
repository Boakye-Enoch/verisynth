import { useSOCStore } from '../store'

const NAV = [
  { id: 'dashboard',  label: 'Dashboard',      color: '#3b82f6' },
  { id: 'map',        label: 'Digital Twin',   color: '#10b981' },
  { id: 'alerts',     label: 'IDS Alerts',     color: '#ef4444' },
  { id: 'trust',      label: 'Trust Manager',  color: '#f59e0b' },
  { id: 'attacks',    label: 'Attack Control', color: '#f97316' },
  { id: 'model',      label: 'AI Models',      color: '#8b5cf6' },
  { id: 'scene',      label: 'Scene Control',  color: '#06b6d4' },
  { id: 'health',     label: 'System Health',  color: '#64748b' },
]

export default function Sidebar() {
  const activePanel    = useSOCStore(s => s.activePanel)
  const setActivePanel = useSOCStore(s => s.setActivePanel)
  const alerts         = useSOCStore(s => s.alerts)
  const vehicles       = useSOCStore(s => s.vehicles)
  const attacks        = useSOCStore(s => s.attacks)
  const health         = useSOCStore(s => s.health)

  const unreadAlerts = alerts.filter(a =>
    a.received_at && Date.now() - a.received_at < 10000
  ).length
  const activeAttacks = attacks.filter(a => a.active).length
  const isolated = vehicles.filter(v => v.is_isolated).length

  const badges: Record<string, number> = {
    alerts:  unreadAlerts,
    attacks: activeAttacks,
    trust:   isolated,
  }

  return (
    <div style={{
      background: 'var(--bg1)',
      borderRight: '1px solid var(--border)',
      display: 'flex',
      flexDirection: 'column',
      padding: '12px 0',
      overflowY: 'auto',
    }}>
      <div style={{ padding: '4px 12px 8px', fontSize: 9, color: '#64748b', textTransform: 'uppercase', letterSpacing: '1px' }}>
        Navigation
      </div>

      {NAV.map(item => (
        <button
          key={item.id}
          onClick={() => setActivePanel(item.id)}
          style={{
            display: 'flex', alignItems: 'center', gap: 9,
            padding: '7px 14px',
            cursor: 'pointer',
            background: activePanel === item.id ? 'rgba(59,130,246,.1)' : 'transparent',
            color: activePanel === item.id ? '#60a5fa' : '#94a3b8',
            fontSize: 12,
            border: 'none',
            borderLeft: `2px solid ${activePanel === item.id ? item.color : 'transparent'}`,
            width: '100%',
            textAlign: 'left',
            transition: '.15s',
          }}
        >
          <div style={{ width: 6, height: 6, borderRadius: '50%', background: item.color, flexShrink: 0 }} />
          {item.label}
          {badges[item.id] > 0 && (
            <span style={{
              marginLeft: 'auto',
              background: 'rgba(239,68,68,.2)', color: '#ef4444',
              fontSize: 9, padding: '1px 5px', borderRadius: 10, fontWeight: 700,
            }}>{badges[item.id]}</span>
          )}
        </button>
      ))}

      {/* System health summary */}
      <div style={{ marginTop: 'auto', padding: 12, borderTop: '1px solid var(--border)' }}>
        <div style={{ fontSize: 9, color: '#64748b', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '.8px' }}>
          System
        </div>
        {health && (
          <>
            <HealthRow label="CPU" value={`${health.cpu_percent.toFixed(0)}%`} />
            <HealthRow label="Memory" value={`${health.memory_percent.toFixed(0)}%`} />
            <HealthRow label="WS Clients" value={String(health.ws_clients)} />
          </>
        )}
        <div style={{ marginTop: 8, fontSize: 9, color: '#475569', textAlign: 'center' }}>
          VERISYNTH v2.0 · IEEE 2025
        </div>
      </div>
    </div>
  )
}

function HealthRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, padding: '2px 0', color: '#94a3b8' }}>
      <span>{label}</span>
      <span style={{ color: '#10b981', fontWeight: 600 }}>{value}</span>
    </div>
  )
}
