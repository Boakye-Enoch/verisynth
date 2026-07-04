import React, { useState } from 'react'
import { useSOCStore } from '../store'

export default function TopBar(): JSX.Element {
  const connected = useSOCStore(s => s.connected)
  const sim = useSOCStore(s => s.sim)
  const alerts = useSOCStore(s => s.alerts)
  const vehicles = useSOCStore(s => s.vehicles)
  const attacks = useSOCStore(s => s.attacks)
  const securityMode = useSOCStore(s => s.securityMode)
  const deactivateAll = useSOCStore(s => s.deactivateAll)
  const setSecurityMode = useSOCStore(s => s.setSecurityMode)
  const wsError = useSOCStore(s => s.wsError)
  const lastWsMessage = useSOCStore(s => s.lastWsMessage)
  const reconnectAttempts = useSOCStore(s => s.reconnectAttempts)
  const connect = useSOCStore(s => s.connect)
  const disconnect = useSOCStore(s => s.disconnect)

  const isolated = vehicles.filter(v => v.is_isolated).length
  const anyActive = attacks.some(a => a.active)

  // threat level heuristic (reuse existing util if available) — simple for UI
  const threatScore = Math.min(1, Math.max(0, (alerts.length + isolated * 2) / 50))
  const threatLabel = threatScore > 0.66 ? 'HIGH' : threatScore > 0.33 ? 'MEDIUM' : 'LOW'

  const [showDetails, setShowDetails] = useState(false)

  return (
    <header className="w-full bg-gradient-to-r from-slate-900 to-slate-950 border-b border-slate-800 px-4 py-2 flex items-center gap-4">
      {/* Logo */}
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-md bg-gradient-to-br from-sky-500 to-violet-500 flex items-center justify-center text-white font-bold">V</div>
        <div className="leading-tight">
          <div className="text-white font-semibold text-sm">VERISYNTH</div>
          <div className="text-slate-400 text-xs">V2X Security Operations Center</div>
        </div>
      </div>

      {/* Divider */}
      <div className="w-px h-8 bg-slate-800" />

      {/* Simulation status cluster */}
      <div className="flex items-center gap-4">
        <div className={`px-3 py-1 rounded-full text-xs font-semibold ${sim.running ? 'bg-emerald-900 text-emerald-300 border border-emerald-800' : 'bg-slate-800 text-slate-400 border border-slate-700'}`}>
          <span className="inline-block w-2 h-2 mr-2 rounded-full" style={{ background: sim.running ? '#10b981' : '#64748b' }} />
          {sim.running ? 'RUNNING' : 'STOPPED'}
        </div>

        <div className="flex items-baseline gap-3 text-xs text-slate-300">
          <div className="flex flex-col">
            <span className="text-slate-400 text-[11px]">SIM TIME</span>
            <span className="text-white font-semibold">{formatSimTime(sim.sim_time)}</span>
          </div>

          <div className="flex flex-col">
            <span className="text-slate-400 text-[11px]">STEP</span>
            <span className="text-white font-semibold">{sim.sim_step.toLocaleString()}</span>
          </div>

          <div className="flex flex-col">
            <span className="text-slate-400 text-[11px]">TOWN</span>
            <span className="text-white font-semibold">{sim.current_town}</span>
          </div>

          <div className="flex flex-col">
            <span className="text-slate-400 text-[11px]">WEATHER</span>
            <span className="text-white font-semibold">{sim.current_weather}</span>
          </div>
        </div>
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Live counters (compact) */}
      <div className="hidden md:flex items-center gap-6 mr-6">
        <Metric label="Total Vehicles" value={`${vehicles.length}`} />
        <Metric label="Active Attacks" value={`${attacks.filter(a => a.active).length}`} />
        <Metric label="Alerts" value={`${alerts.length}`} />
      </div>

      {/* Threat bar */}
      <div className="flex items-center gap-3">
        <div className="flex flex-col items-start mr-3">
          <div className="text-slate-400 text-[11px]">THREAT LEVEL</div>
          <div className="w-40 bg-slate-800 rounded h-3 overflow-hidden border border-slate-700">
            <div className={`h-3 rounded bg-red-600`} style={{ width: `${Math.round(threatScore * 100)}%`, transition: 'width 400ms ease' }} />
          </div>
        </div>

        {/* Connection indicator */}
        <div className="flex items-center gap-3">
          <div className="text-xs text-slate-300 flex items-center gap-2">
            <span className={`w-3 h-3 rounded-full ${connected ? 'bg-emerald-400' : 'bg-red-500'}`} />
            <span>{connected ? 'LIVE' : 'RECONNECTING'}</span>
            {wsError && <span className="text-red-400 ml-2">{wsError}</span>}
          </div>

          <button onClick={() => { disconnect(); setTimeout(connect, 300) }} className="text-xs px-3 py-1 bg-slate-800 hover:bg-slate-700 rounded text-slate-300">Reconnect</button>

          <button onClick={() => setShowDetails(s => !s)} className="text-xs px-3 py-1 bg-slate-800 hover:bg-slate-700 rounded text-slate-300">{showDetails ? 'Hide' : 'Details'}</button>
        </div>
      </div>

      {/* Details popover */}
      {showDetails && (
        <div className="absolute right-6 top-16 w-80 bg-slate-900 border border-slate-800 rounded shadow-lg p-3 text-xs text-slate-300">
          <div className="mb-2"><strong>Reconnect attempts:</strong> {reconnectAttempts}</div>
          <div className="mb-2"><strong>Last WS message:</strong> <div className="mt-1 p-2 bg-slate-800 rounded text-[12px] text-slate-200 max-h-28 overflow-auto">{lastWsMessage ?? '—'}</div></div>
          <div className="flex justify-end mt-2">
            <button onClick={() => { disconnect(); setTimeout(connect, 300) }} className="px-3 py-1 bg-red-700 text-white rounded text-xs">Reconnect</button>
          </div>
        </div>
      )}

      {/* Security toggle and emergency stop */}
      <div className="flex items-center gap-3 ml-4">
        <div className="text-xs text-slate-400 uppercase">Security</div>
        <button onClick={() => setSecurityMode(!securityMode)} className={`px-3 py-1 rounded text-xs font-semibold ${securityMode ? 'bg-emerald-800 text-emerald-300 border border-emerald-700' : 'bg-rose-800 text-rose-300 border border-rose-700'}`}>
          {securityMode ? '🛡 PROTECTED' : '⚠ UNPROTECTED'}
        </button>

        {anyActive && (
          <button onClick={() => deactivateAll()} className="ml-2 px-3 py-1 bg-rose-700 text-white rounded text-xs">⬛ STOP ALL</button>
        )}
      </div>

    </header>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col text-right">
      <div className="text-slate-400 text-[11px]">{label}</div>
      <div className="text-white font-semibold">{value}</div>
    </div>
  )
}

// helper to format sim time — reuse util if available
function formatSimTime(simTime: number) {
  try {
    const seconds = Math.floor(simTime)
    const hh = String(Math.floor(seconds / 3600)).padStart(2, '0')
    const mm = String(Math.floor((seconds % 3600) / 60)).padStart(2, '0')
    const ss = String(seconds % 60).padStart(2, '0')
    return `${hh}:${mm}:${ss}`
  } catch {
    return '--:--:--'
  }
}
