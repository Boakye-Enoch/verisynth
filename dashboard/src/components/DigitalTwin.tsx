import { useRef, useEffect, useCallback } from 'react'
import { useSOCStore } from '../store'
import { trustColor, attackColor } from '../utils'
import type { VehicleState } from '../types'

// Town04 approximate bounding box from SUMO coordinates
const MAP_BOUNDS = { minX: 0, maxX: 1000, minY: 0, maxY: 900 }

export default function DigitalTwin() {
  const canvasRef    = useRef<HTMLCanvasElement>(null)
  const animFrameRef = useRef<number>(0)
  const tickRef      = useRef(0)

  const vehicles        = useSOCStore(s => s.vehicles)
  const attacks         = useSOCStore(s => s.attacks)
  const selectedVehicle = useSOCStore(s => s.selectedVehicle)
  const selectVehicle   = useSOCStore(s => s.selectVehicle)
  const sim             = useSOCStore(s => s.sim)
  const securityMode    = useSOCStore(s => s.securityMode)

  const draw = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const W = canvas.width
    const H = canvas.height
    tickRef.current++

    ctx.clearRect(0, 0, W, H)

    // Background
    ctx.fillStyle = '#0a0c10'
    ctx.fillRect(0, 0, W, H)

    // Grid
    ctx.strokeStyle = 'rgba(30,36,51,0.6)'
    ctx.lineWidth = 0.5
    for (let x = 0; x < W; x += 40) {
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke()
    }
    for (let y = 0; y < H; y += 40) {
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke()
    }

    if (vehicles.length === 0) {
      ctx.fillStyle = '#475569'
      ctx.font = '14px Inter,sans-serif'
      ctx.textAlign = 'center'
      ctx.fillText('Waiting for simulation data...', W / 2, H / 2)
      return
    }

    // Scale coordinates to canvas
    const { minX, maxX, minY, maxY } = MAP_BOUNDS
    const pad = 40
    const scaleX = (v: number) => pad + ((v - minX) / (maxX - minX)) * (W - pad * 2)
    const scaleY = (v: number) => pad + ((v - minY) / (maxY - minY)) * (H - pad * 2)

    const activeAttacksMap = new Map<string, string>()
    attacks.filter(a => a.active).forEach(a => {
      // We'll colour vehicles by their own attack_type from vehicle state
    })

    // Draw communication links (simplified: lines between attacked vehicles and their neighbours)
    vehicles.filter(v => v.is_attacked).forEach(atk => {
      vehicles.slice(0, 8).forEach(nb => {
        if (nb.vehicle_id === atk.vehicle_id) return
        ctx.beginPath()
        ctx.strokeStyle = 'rgba(239,68,68,0.12)'
        ctx.lineWidth = 0.8
        ctx.setLineDash([3, 3])
        ctx.moveTo(scaleX(atk.x), scaleY(atk.y))
        ctx.lineTo(scaleX(nb.x), scaleY(nb.y))
        ctx.stroke()
        ctx.setLineDash([])
      })
    })

    // Draw V2V links for normal vehicles
    for (let i = 0; i < Math.min(vehicles.length, 30); i++) {
      for (let j = i + 1; j < Math.min(vehicles.length, 30); j++) {
        const a = vehicles[i], b = vehicles[j]
        const dist = Math.hypot(a.x - b.x, a.y - b.y)
        if (dist < 120) {
          ctx.beginPath()
          ctx.strokeStyle = 'rgba(59,130,246,0.06)'
          ctx.lineWidth = 0.4
          ctx.moveTo(scaleX(a.x), scaleY(a.y))
          ctx.lineTo(scaleX(b.x), scaleY(b.y))
          ctx.stroke()
        }
      }
    }

    // Draw vehicles
    vehicles.forEach(v => {
      const cx = scaleX(v.x)
      const cy = scaleY(v.y)
      // When security is OFF, vehicles don't show attack/isolation states
      // This visually demonstrates that without VERISYNTH, attacks are invisible
      const effectiveIsAttacked = securityMode ? v.is_attacked : false
      const effectiveIsIsolated = securityMode ? v.is_isolated : false
      const effectiveVerdict    = securityMode ? v.verdict : 'NORMAL'
      const effectiveTrust      = securityMode ? v.trust_score : 0.70

      const col = effectiveIsIsolated
        ? '#6b7280'
        : effectiveIsAttacked
          ? (attackColor(v.attack_type ?? '') || '#ef4444')
          : trustColor(effectiveTrust)

      const isSelected = v.vehicle_id === selectedVehicle

      // Pulse ring for attacked vehicles
      if (effectiveIsAttacked) {
        const r = 12 + Math.sin(tickRef.current * 0.08) * 4
        ctx.beginPath()
        ctx.arc(cx, cy, r, 0, Math.PI * 2)
        ctx.fillStyle = `${col}18`
        ctx.fill()
      }

      // Selection ring
      if (isSelected) {
        ctx.beginPath()
        ctx.arc(cx, cy, 14, 0, Math.PI * 2)
        ctx.strokeStyle = '#fff'
        ctx.lineWidth = 1.5
        ctx.stroke()
      }

      // Vehicle circle
      ctx.beginPath()
      ctx.arc(cx, cy, 8, 0, Math.PI * 2)
      ctx.fillStyle = `${col}22`
      ctx.fill()
      ctx.strokeStyle = col
      ctx.lineWidth = isSelected ? 2 : 1.5
      ctx.stroke()

      // Inner dot
      ctx.beginPath()
      ctx.arc(cx, cy, 3.5, 0, Math.PI * 2)
      ctx.fillStyle = col
      ctx.fill()

      // Label
      ctx.fillStyle = col
      ctx.font = 'bold 8px Inter,sans-serif'
      ctx.textAlign = 'center'
      ctx.fillText(v.vehicle_id, cx, cy - 13)

      // Trust score
      ctx.fillStyle = 'rgba(148,163,184,0.85)'
      ctx.font = '7px Inter,sans-serif'
      ctx.fillText(v.trust_score.toFixed(2), cx, cy - 5)

      // Attack badge
      if (effectiveIsAttacked && v.attack_type && securityMode) {
        ctx.fillStyle = col
        ctx.font = 'bold 6px Inter,sans-serif'
        ctx.fillText(v.attack_type.replace('_', ' '), cx, cy + 16)
      }
    })

    // Legend
    const legend = [
      { col: '#10b981', label: 'Normal' },
      { col: '#f59e0b', label: 'Warned' },
      { col: '#ef4444', label: 'Attacked' },
      { col: '#6b7280', label: 'Isolated' },
    ]
    legend.forEach((l, i) => {
      ctx.beginPath()
      ctx.arc(12, H - 60 + i * 14, 4, 0, Math.PI * 2)
      ctx.fillStyle = l.col; ctx.fill()
      ctx.fillStyle = '#94a3b8'
      ctx.font = '9px Inter,sans-serif'
      ctx.textAlign = 'left'
      ctx.fillText(l.label, 20, H - 57 + i * 14)
    })

    // Stats overlay
    ctx.fillStyle = 'rgba(15,17,23,0.8)'
    ctx.fillRect(W - 140, 8, 132, 44)
    ctx.strokeStyle = 'var(--border)'
    ctx.lineWidth = 1
    ctx.strokeRect(W - 140, 8, 132, 44)
    ctx.fillStyle = '#94a3b8'
    ctx.font = '9px Inter,sans-serif'
    ctx.textAlign = 'left'
    ctx.fillText(`Vehicles: ${vehicles.length}`, W - 132, 24)
    ctx.fillText(`Attacked: ${vehicles.filter(v => v.is_attacked).length}`, W - 132, 36)
    ctx.fillText(`Isolated: ${vehicles.filter(v => v.is_isolated).length}`, W - 132, 48)

  }, [vehicles, attacks, selectedVehicle])

  // Animation loop
  useEffect(() => {
    const loop = () => {
      draw()
      animFrameRef.current = requestAnimationFrame(loop)
    }
    animFrameRef.current = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(animFrameRef.current)
  }, [draw])

  // Resize
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ro = new ResizeObserver(() => {
      canvas.width  = canvas.offsetWidth
      canvas.height = canvas.offsetHeight
    })
    ro.observe(canvas)
    canvas.width  = canvas.offsetWidth
    canvas.height = canvas.offsetHeight
    return () => ro.disconnect()
  }, [])

  // Click to select vehicle
  const handleClick = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current
    if (!canvas || vehicles.length === 0) return
    const rect = canvas.getBoundingClientRect()
    const mx = e.clientX - rect.left
    const my = e.clientY - rect.top
    const W = canvas.width, H = canvas.height
    const { minX, maxX, minY, maxY } = MAP_BOUNDS
    const pad = 40
    const scaleX = (v: number) => pad + ((v - minX) / (maxX - minX)) * (W - pad * 2)
    const scaleY = (v: number) => pad + ((v - minY) / (maxY - minY)) * (H - pad * 2)

    let closest: VehicleState | null = null
    let minDist = 20
    vehicles.forEach(v => {
      const d = Math.hypot(mx - scaleX(v.x), my - scaleY(v.y))
      if (d < minDist) { minDist = d; closest = v }
    })
    selectVehicle(closest ? (closest as VehicleState).vehicle_id : null)
  }, [vehicles, selectVehicle])

  return (
    <div style={{
      background: 'var(--bg2)', border: '1px solid var(--border)',
      borderRadius: 8, overflow: 'hidden', height: '100%',
      display: 'flex', flexDirection: 'column',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '8px 12px', borderBottom: '1px solid var(--border)',
        background: 'var(--bg1)',
      }}>
        <span style={{ fontSize: 12, fontWeight: 600 }}>Live V2X Digital Twin — {sim.current_town}</span>
        <span style={{
          fontSize: 9, padding: '2px 7px', borderRadius: 10, fontWeight: 600,
          background: 'rgba(16,185,129,.2)', color: '#10b981',
        }}>● LIVE</span>
        <span style={{ marginLeft: 'auto', fontSize: 10, color: '#64748b' }}>
          {sim.current_weather} · Click vehicle to inspect
        </span>
      </div>
      {!securityMode && (
        <div style={{
          background: 'rgba(239,68,68,.15)',
          border: '1px solid rgba(239,68,68,.4)',
          color: '#f87171',
          padding: '4px 12px',
          fontSize: 11, fontWeight: 700,
          textAlign: 'center',
          letterSpacing: '1px',
        }}>
          ⚠ SECURITY MECHANISMS DISABLED — ATTACKS ARE UNDETECTED AND UNMITIGATED
        </div>
      )}
      <canvas
        ref={canvasRef}
        style={{ flex: 1, width: '100%', cursor: 'crosshair' }}
        onClick={handleClick}
      />
    </div>
  )
}
