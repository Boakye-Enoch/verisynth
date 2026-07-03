import { useSOCStore } from '../store'
import DigitalTwin from './DigitalTwin'
import AlertPanel from './AlertPanel'
import TrustPanel from './TrustPanel'
import AttackPanel from './AttackPanel'
import ModelPanel from './ModelPanel'
import ScenePanel from './ScenePanel'
import HealthPanel from './HealthPanel'
import KPIRow from './KPIRow'
import TimelinePanel from './TimelinePanel'

export default function Dashboard() {
  const activePanel = useSOCStore(s => s.activePanel)

  if (activePanel === 'map')     return <FullPanel><DigitalTwin /></FullPanel>
  if (activePanel === 'alerts')  return <FullPanel><AlertPanel /></FullPanel>
  if (activePanel === 'trust')   return <FullPanel><TrustPanel /></FullPanel>
  if (activePanel === 'attacks') return <FullPanel><AttackPanel /></FullPanel>
  if (activePanel === 'model')   return <FullPanel><ModelPanel /></FullPanel>
  if (activePanel === 'scene')   return <FullPanel><ScenePanel /></FullPanel>
  if (activePanel === 'health')  return <FullPanel><HealthPanel /></FullPanel>

  // Default dashboard view
  return (
    <div style={{
      display: 'grid',
      gridTemplateRows: 'auto 1fr auto auto',
      height: '100%',
      overflow: 'hidden',
      padding: 10,
      gap: 10,
    }}>
      <KPIRow />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 10, minHeight: 0 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, minHeight: 0 }}>
          <div style={{ flex: 1, minHeight: 0 }}><DigitalTwin /></div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, minHeight: 0 }}>
          <div style={{ flex: 1, overflow: 'hidden' }}><AlertPanel maxItems={8} /></div>
        </div>
      </div>
      <TimelinePanel />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        <TrustPanel compact />
        <AttackPanel compact />
      </div>
    </div>
  )
}

function FullPanel({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ height: '100%', overflow: 'auto', padding: 10 }}>
      {children}
    </div>
  )
}
