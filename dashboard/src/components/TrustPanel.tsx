import { useSOCStore } from '../store'
import { trustColor } from '../utils'

export default function TrustPanel({ compact = false }: { compact?: boolean }) {
  const trustEntries    = useSOCStore(s => s.trustEntries)
  const selectedVehicle = useSOCStore(s => s.selectedVehicle)
  const selectVehicle   = useSOCStore(s => s.selectVehicle)

  const sorted = [...trustEntries].sort((a, b) => a.trust_score - b.trust_score)
  const shown  = compact ? sorted.slice(0, 8) : sorted

  return (
    <div style={{
      background: 'var(--bg2)', border: '1px solid var(--border)',
      borderRadius: 8, height: compact ? 'auto' : '100%',
      display: 'flex', flexDirection: 'column', overflow: 'hidden',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '8px 12px', borderBottom: '1px solid var(--border)',
        background: 'var(--bg1)',
      }}>
        <span style={{ fontSize: 12, fontWeight: 600 }}>Trust Scores</span>
        <span style={{ marginLeft: 'auto', fontSize: 10, color: '#64748b' }}>
          {trustEntries.filter(v => v.isolated).length} isolated
        </span>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: 8 }}>
        <div style={{
          display: 'grid',
          gridTemplateColumns: compact ? 'repeat(4,1fr)' : 'repeat(5,1fr)',
          gap: 6,
        }}>
          {shown.map(v => {
            const col = v.isolated ? '#6b7280' : trustColor(v.trust_score)
            return (
              <div
                key={v.vehicle_id}
                onClick={() => selectVehicle(v.vehicle_id === selectedVehicle ? null : v.vehicle_id)}
                style={{
                  background: v.vehicle_id === selectedVehicle ? 'rgba(59,130,246,.15)' : 'var(--bg3)',
                  border: `1px solid ${v.vehicle_id === selectedVehicle ? '#3b82f6' : 'var(--border)'}`,
                  borderRadius: 6, padding: '6px 8px', textAlign: 'center',
                  cursor: 'pointer', transition: '.15s',
                }}
              >
                <div style={{ fontSize: 9, color: '#64748b', marginBottom: 3 }}>{v.vehicle_id}</div>
                <div style={{ fontSize: 16, fontWeight: 700, color: col }}>
                  {v.trust_score.toFixed(2)}
                </div>
                <div style={{ height: 3, background: 'var(--bg0)', borderRadius: 3, margin: '4px 0' }}>
                  <div style={{
                    height: 3, borderRadius: 3,
                    width: `${v.trust_score * 100}%`,
                    background: col,
                    transition: 'width .5s',
                  }} />
                </div>
                <div style={{ fontSize: 8, color: col, fontWeight: 600 }}>
                  {v.isolated ? 'ISOLATED' : v.warned ? 'WARNED' : 'OK'}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
