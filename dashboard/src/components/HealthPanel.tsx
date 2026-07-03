import { useSOCStore } from '../store'

export default function HealthPanel() {
  const health = useSOCStore(s => s.health)

  if (!health) return (
    <div style={{
      background: 'var(--bg2)', border: '1px solid var(--border)',
      borderRadius: 8, padding: 20, color: '#475569', textAlign: 'center',
    }}>Waiting for health data...</div>
  )

  const metrics = [
    { label: 'CPU',        value: health.cpu_percent,    unit: '%', color: health.cpu_percent > 80 ? '#ef4444' : '#10b981' },
    { label: 'Memory',     value: health.memory_percent, unit: '%', color: health.memory_percent > 85 ? '#ef4444' : '#f59e0b' },
    { label: 'GPU',        value: health.gpu_percent,    unit: '%', color: '#8b5cf6' },
    { label: 'Events/Bus', value: health.event_bus_published, unit: '', color: '#3b82f6' },
    { label: 'Dropped',    value: health.event_bus_dropped,   unit: '', color: health.event_bus_dropped > 0 ? '#ef4444' : '#10b981' },
    { label: 'WS Clients', value: health.ws_clients,    unit: '', color: '#06b6d4' },
    { label: 'Sim Step',   value: health.sim_step,       unit: '', color: '#94a3b8' },
    { label: 'FPS',        value: health.sim_fps,        unit: '/s', color: health.sim_fps > 10 ? '#10b981' : '#f59e0b' },
  ]

  return (
    <div style={{
      background: 'var(--bg2)', border: '1px solid var(--border)',
      borderRadius: 8, overflow: 'hidden',
    }}>
      <div style={{
        padding: '8px 12px', borderBottom: '1px solid var(--border)',
        background: 'var(--bg1)', fontSize: 12, fontWeight: 600,
      }}>System Health</div>

      <div style={{ padding: 12, display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 8 }}>
        {metrics.map(m => (
          <div key={m.label} style={{
            background: 'var(--bg3)', border: '1px solid var(--border)',
            borderRadius: 6, padding: '8px 10px',
          }}>
            <div style={{ fontSize: 9, color: '#64748b', textTransform: 'uppercase', letterSpacing: '.8px' }}>
              {m.label}
            </div>
            <div style={{ fontSize: 20, fontWeight: 700, color: m.color, marginTop: 4 }}>
              {typeof m.value === 'number' ? m.value.toLocaleString() : m.value}{m.unit}
            </div>
            {m.unit === '%' && (
              <div style={{ height: 3, background: 'var(--bg0)', borderRadius: 3, marginTop: 6 }}>
                <div style={{
                  height: 3, borderRadius: 3, background: m.color,
                  width: `${Math.min(100, m.value as number)}%`, transition: 'width .5s',
                }} />
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
