import { useSOCStore } from '../store'

const TOWNS = ['Town01','Town02','Town03','Town04','Town05','Town06','Town07','Town10']
const WEATHERS = ['ClearNoon','ClearSunset','CloudyNoon','WetNoon','HeavyRain','DenseFog','Night','NightRain','StormySunset','HardRainNoon','MidRainyNight']
const DAYTIMES = [
  { id: 'day',     label: '☀ Day' },
  { id: 'sunset',  label: '🌅 Sunset' },
  { id: 'night',   label: '🌙 Night' },
  { id: 'sunrise', label: '🌄 Sunrise' },
  { id: 'cycle',   label: '🔄 Cycle' },
]

export default function ScenePanel() {
  const sim         = useSOCStore(s => s.sim)
  const changeScene = useSOCStore(s => s.changeScene)

  return (
    <div style={{
      background: 'var(--bg2)', border: '1px solid var(--border)',
      borderRadius: 8, overflow: 'hidden',
    }}>
      <div style={{
        padding: '8px 12px', borderBottom: '1px solid var(--border)',
        background: 'var(--bg1)', fontSize: 12, fontWeight: 600,
      }}>Scene Controller</div>

      <div style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 16 }}>

        {/* Current */}
        <div style={{ display: 'flex', gap: 12 }}>
          <Badge label="Town" value={sim.current_town} color="#06b6d4" />
          <Badge label="Weather" value={sim.current_weather} color="#8b5cf6" />
        </div>

        {/* Towns */}
        <div>
          <div style={{ fontSize: 10, color: '#64748b', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '.8px' }}>
            Switch Town
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 4 }}>
            {TOWNS.map(t => (
              <button key={t} onClick={() => changeScene('town', t)} style={{
                padding: '5px 4px', borderRadius: 4, fontSize: 10, fontWeight: 600,
                background: sim.current_town === t ? 'rgba(6,182,212,.2)' : 'var(--bg3)',
                color: sim.current_town === t ? '#06b6d4' : '#94a3b8',
                border: `1px solid ${sim.current_town === t ? 'rgba(6,182,212,.4)' : 'var(--border)'}`,
                cursor: 'pointer',
              }}>{t}</button>
            ))}
          </div>
        </div>

        {/* Weather */}
        <div>
          <div style={{ fontSize: 10, color: '#64748b', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '.8px' }}>
            Weather Preset
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 4 }}>
            {WEATHERS.map(w => (
              <button key={w} onClick={() => changeScene('weather', w)} style={{
                padding: '5px 4px', borderRadius: 4, fontSize: 9, fontWeight: 600,
                background: sim.current_weather === w ? 'rgba(139,92,246,.2)' : 'var(--bg3)',
                color: sim.current_weather === w ? '#a78bfa' : '#94a3b8',
                border: `1px solid ${sim.current_weather === w ? 'rgba(139,92,246,.4)' : 'var(--border)'}`,
                cursor: 'pointer',
              }}>{w}</button>
            ))}
          </div>
        </div>

        {/* Day/Night */}
        <div>
          <div style={{ fontSize: 10, color: '#64748b', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '.8px' }}>
            Time of Day
          </div>
          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
            {DAYTIMES.map(d => (
              <button key={d.id} onClick={() => changeScene('daytime', d.id)} style={{
                padding: '5px 10px', borderRadius: 4, fontSize: 10, fontWeight: 600,
                background: 'var(--bg3)', color: '#94a3b8',
                border: '1px solid var(--border)', cursor: 'pointer',
              }}>{d.label}</button>
            ))}
          </div>
        </div>

      </div>
    </div>
  )
}

function Badge({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={{
      flex: 1, background: `${color}12`, border: `1px solid ${color}33`,
      borderRadius: 6, padding: '8px 12px',
    }}>
      <div style={{ fontSize: 9, color: '#64748b', textTransform: 'uppercase', letterSpacing: '.8px' }}>{label}</div>
      <div style={{ fontSize: 14, fontWeight: 700, color, marginTop: 2 }}>{value}</div>
    </div>
  )
}
