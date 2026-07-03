import { useSOCStore } from '../store'
import { attackColor } from '../utils'

const ATTACK_DESCS: Record<string, string> = {
  REPLAY:      'Capture & replay BSM packets',
  SPOOFING:    'False position injection',
  DOS:         'Channel flooding attack',
  SYBIL:       'Fake identity creation',
  GPS_SPOOFING:'GNSS signal manipulation',
  FORCEFUL:    'HMAC brute-force attack',
}

export default function AttackPanel({ compact = false }: { compact?: boolean }) {
  const attacks          = useSOCStore(s => s.attacks)
  const activateAttack   = useSOCStore(s => s.activateAttack)
  const deactivateAttack = useSOCStore(s => s.deactivateAttack)
  const deactivateAll    = useSOCStore(s => s.deactivateAll)
  const sim              = useSOCStore(s => s.sim)

  return (
    <div style={{
      background: 'var(--bg2)', border: '1px solid var(--border)',
      borderRadius: 8, display: 'flex', flexDirection: 'column', overflow: 'hidden',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '8px 12px', borderBottom: '1px solid var(--border)',
        background: 'var(--bg1)',
      }}>
        <span style={{ fontSize: 12, fontWeight: 600 }}>Attack Control</span>
        <span style={{ marginLeft: 'auto', fontSize: 10, color: '#64748b' }}>
          {attacks.filter(a => a.active).length} active
        </span>
        {attacks.some(a => a.active) && (
          <button
            onClick={() => deactivateAll()}
            style={{
              padding: '2px 8px', borderRadius: 4, fontSize: 10, fontWeight: 600,
              background: 'rgba(239,68,68,.2)', color: '#ef4444',
              border: '1px solid rgba(239,68,68,.4)', cursor: 'pointer',
            }}
          >Stop All</button>
        )}
      </div>

      <div style={{ padding: 8, display: 'flex', flexDirection: 'column', gap: 4 }}>
        {attacks.map(attack => {
          const col = attackColor(attack.attack_type)
          return (
            <div key={attack.attack_type} style={{
              display: 'flex', alignItems: 'center', gap: 8,
              padding: '6px 8px', borderRadius: 6,
              background: attack.active ? `${col}12` : 'var(--bg3)',
              border: `1px solid ${attack.active ? col + '44' : 'var(--border)'}`,
            }}>
              <div style={{
                width: 8, height: 8, borderRadius: '50%',
                background: attack.active ? col : '#374151',
                animation: attack.active ? 'pulse-ring 1.5s infinite' : 'none',
              }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: attack.active ? col : '#94a3b8' }}>
                  {attack.attack_type.replace(/_/g, ' ')}
                </div>
                {!compact && (
                  <div style={{ fontSize: 9, color: '#475569', marginTop: 1 }}>
                    {ATTACK_DESCS[attack.attack_type]} · {attack.total_injected.toLocaleString()} injected
                  </div>
                )}
              </div>
              <button
                onClick={() => attack.active
                  ? deactivateAttack(attack.attack_type)
                  : activateAttack(attack.attack_type)
                }
                disabled={!sim.running}
                style={{
                  padding: '3px 10px', borderRadius: 4, fontSize: 10, fontWeight: 600,
                  background: attack.active ? 'rgba(239,68,68,.2)' : `${col}22`,
                  color: attack.active ? '#ef4444' : col,
                  border: `1px solid ${attack.active ? 'rgba(239,68,68,.4)' : col + '44'}`,
                  cursor: sim.running ? 'pointer' : 'not-allowed',
                  opacity: sim.running ? 1 : 0.5,
                }}
              >
                {attack.active ? 'Stop' : 'Start'}
              </button>
            </div>
          )
        })}
      </div>
    </div>
  )
}
