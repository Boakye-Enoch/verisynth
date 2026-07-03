import { useSOCStore } from '../store'
import { attackColor } from '../utils'

export default function TimelinePanel() {
  const timeline = useSOCStore(s => s.timeline)
  const sim      = useSOCStore(s => s.sim)

  const attackEvents = timeline.filter(e =>
    e.type === 'ATTACK_START' || e.type === 'ATTACK_END' || e.type === 'IDS_ALERT'
  ).slice(-20)

  const maxStep = Math.max(sim.sim_step, 6000)

  return (
    <div style={{
      background: 'var(--bg2)', border: '1px solid var(--border)',
      borderRadius: 8, overflow: 'hidden',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '8px 12px', borderBottom: '1px solid var(--border)',
        background: 'var(--bg1)',
      }}>
        <span style={{ fontSize: 12, fontWeight: 600 }}>Attack Timeline</span>
        <span style={{ fontSize: 10, color: '#64748b' }}>Step {sim.sim_step} / {maxStep}</span>
      </div>

      <div style={{ padding: '10px 12px' }}>
        {/* Progress bar */}
        <div style={{
          height: 4, background: 'var(--bg3)', borderRadius: 4, marginBottom: 8,
          position: 'relative',
        }}>
          <div style={{
            height: 4, background: '#3b82f6', borderRadius: 4,
            width: `${(sim.sim_step / maxStep) * 100}%`,
            transition: 'width .5s',
          }} />
          {/* Attack markers */}
          {attackEvents.map((e, i) => {
            const pct = (e.sim_step / maxStep) * 100
            const col = e.type === 'IDS_ALERT'
              ? '#10b981'
              : attackColor((e.payload as Record<string, unknown>).attack_type as string ?? '')
            return (
              <div key={i} style={{
                position: 'absolute', top: -4, left: `${pct}%`,
                width: 2, height: 12, background: col,
                borderRadius: 1,
                transform: 'translateX(-50%)',
              }} title={`${e.type} @ step ${e.sim_step}`} />
            )
          })}
        </div>

        {/* Recent events */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {attackEvents.slice(-6).reverse().map((e, i) => {
            const col = e.type === 'IDS_ALERT' ? '#10b981'
              : e.type === 'ATTACK_START' ? '#ef4444' : '#64748b'
            const atype = (e.payload as Record<string, unknown>).attack_type as string
              || (e.payload as Record<string, unknown>).alert_type as string
              || ''
            return (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: 8,
                fontSize: 10, padding: '2px 0',
                borderBottom: '1px solid var(--border)',
                color: '#94a3b8',
              }}>
                <div style={{ width: 8, height: 8, borderRadius: '50%', background: col, flexShrink: 0 }} />
                <span style={{ color: col, fontWeight: 600, minWidth: 80 }}>
                  {e.type.replace(/_/g, ' ')}
                </span>
                <span>{atype.replace(/_/g, ' ')}</span>
                <span style={{ marginLeft: 'auto', color: '#475569', fontFamily: 'monospace' }}>
                  step {e.sim_step}
                </span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
