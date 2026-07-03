import { useEffect } from 'react'
import { useSOCStore } from './store'
import TopBar from './components/TopBar'
import Sidebar from './components/Sidebar'
import Dashboard from './components/Dashboard'

export default function App() {
  const connect = useSOCStore(s => s.connect)

  useEffect(() => {
    connect()
  }, [connect])

  return (
    <div style={{
      display: 'grid',
      gridTemplateRows: '48px 1fr',
      height: '100vh',
      overflow: 'hidden',
      background: 'var(--bg0)',
    }}>
      <TopBar />
      <div style={{
        display: 'grid',
        gridTemplateColumns: '190px 1fr',
        overflow: 'hidden',
      }}>
        <Sidebar />
        <Dashboard />
      </div>
    </div>
  )
}
