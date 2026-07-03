import { useSOCStore } from '../store'
import { threatLevel, formatSimTime, formatTime } from '../utils'

export default function TopBar() {
  const connected      = useSOCStore(s => s.connected)
  const sim            = useSOCStore(s => s.sim)
  const alerts         = useSOCStore(s => s.alerts)
  const vehicles       = useSOCStore(s => s.vehicles)
  const attacks        = useSOCStore(s => s.attacks)
  const securityMode   = useSOCStore(s => s.securityMode)
  const deactivateAll  = useSOCStore(s => s.deactivateAll)
  const setSecurityMode = useSOCStore(s => s.setSecurityMode)

  const isolated  = vehicles.filter(v => v.is_isolated).length
  const anyActive = attacks.some(a => a.active)
  const threat    = threatLevel(alerts.length, isolated)

  return (
    <div style={{
      background: 'var(--bg1)',
      borderBottom: '1px solid var(--border)',
      display: 'flex',
      alignItems: 'center',
      padding: '0 16px',
      gap: '16px',
      zIndex: 100,
    }}>
      {/* Logo */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div style={{
          width: 28, height: 28,
          background: 'linear-gradient(135deg,#3b82f6,#8b5cf6)',
          borderRadius: 6,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 12, fontWeight: 900, color: '#fff',
        }}>V</div>
        <div>
          <div style={{ fontWeight: 700, fontSize: 14, color: '#fff', letterSpacing: '.5px' }}>VERISYNTH</div>
          <div style={{ fontSize: 9, color: '#64748b', letterSpacing: '1px' }}>V2X SECURITY OPERATIONS CENTER</div>
        </div>
      </div>

      <Divider />

      {/* Status */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 5,
        padding: '3px 10px', borderRadius: 20, fontSize: 11, fontWeight: 600,
        background: sim.running ? 'rgba(16,185,129,.15)' : 'rgba(100,116,139,.15)',
        color: sim.running ? '#10b981' : '#64748b',
        border: `1px solid ${sim.running ? 'rgba(16,185,129,.3)' : 'rgba(100,116,139,.3)'}`,
      }}>
        <div style={{
          width: 6, height: 6, borderRadius: '50%',
          background: sim.running ? '#10b981' : '#64748b',
          animation: sim.running ? 'pulse-ring 1.5s infinite' : 'none',
        }} />
        {sim.running ? 'RUNNING' : 'STOPPED'}
      </div>

      <Divider />

      <Stat label="Sim Time" value={formatSimTime(sim.sim_time)} />
      <Divider />
      <Stat label="Step" value={sim.sim_step.toLocaleString()} />
      <Divider />
      <Stat label="Town" value={sim.current_town} />
      <Divider />
      <Stat label="Weather" value={sim.current_weather} />

      {/* WS indicator */}
      <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 4,
          fontSize: 10, color: connected ? '#10b981' : '#ef4444',
        }}>
          <div style={{
            width: 6, height: 6, borderRadius: '50%',
            background: connected ? '#10b981' : '#ef4444',
          }} />
          {connected ? 'LIVE' : 'RECONNECTING'}
        </div>

        <Divider />

        {/* Security Mode Toggle */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 9, color: '#64748b', textTransform: 'uppercase', letterSpacing: '.8px' }}>
            Security
          </span>
          <button
            onClick={() => setSecurityMode(!securityMode)}
            style={{
              padding: '3px 12px', borderRadius: 4,
              fontSize: 11, fontWeight: 700,
              background: securityMode ? 'rgba(16,185,129,.2)' : 'rgba(239,68,68,.25)',
              color: securityMode ? '#10b981' : '#ef4444',
              border: `1px solid ${securityMode ? 'rgba(16,185,129,.4)' : 'rgba(239,68,68,.5)'}`,
              cursor: 'pointer',
              animation: !securityMode ? 'pulse-ring 1.5s infinite' : 'none',
            }}
          >
            {securityMode ? '🛡 PROTECTED' : '⚠ UNPROTECTED'}
          </button>
        </div>

        <Divider />

        {/* Threat level */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 9, color: '#64748b', textTransform: 'uppercase', letterSpacing: '.8px' }}>
            Threat
          </span>
          <span style={{
            padding: '2px 10px', borderRadius: 4,
            fontSize: 11, fontWeight: 700,
            background: `${threat.color}22`,
            color: threat.color,
            border: `1px solid ${threat.color}55`,
          }}>{threat.level}</span>
        </div>

        <Divider />

        {/* Emergency stop */}
        {anyActive && (
          <button
            onClick={() => deactivateAll()}
            style={{
              padding: '4px 12px', borderRadius: 5,
              fontSize: 11, fontWeight: 600,
              background: 'rgba(239,68,68,.2)',
              color: '#ef4444',
              border: '1px solid rgba(239,68,68,.4)',
              cursor: 'pointer',
            }}
          >⬛ STOP ALL</button>
        )}
      </div>
    </div>
  )
}

function Divider() {
  return <div style={{ width: 1, height: 24, background: 'var(--border)' }} />
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
      <div style={{ fontSize: 9, color: '#64748b', textTransform: 'uppercase', letterSpacing: '.8px' }}>{label}</div>
      <div style={{ fontSize: 13, fontWeight: 600 }}>{value}</div>
    </div>
  )
}
