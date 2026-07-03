import { useSOCStore } from '../store'

function Bar({ value, color = '#3b82f6' }: { value: number; color?: string }) {
  return (
    <div style={{ height: 4, background: 'var(--bg0)', borderRadius: 4, marginTop: 3 }}>
      <div style={{
        height: 4, borderRadius: 4, background: color,
        width: `${Math.min(100, value * 100)}%`, transition: 'width .5s',
      }} />
    </div>
  )
}

export default function ModelPanel() {
  const model = useSOCStore(s => s.model)

  if (!model) return (
    <div style={{
      background: 'var(--bg2)', border: '1px solid var(--border)',
      borderRadius: 8, padding: 20, color: '#475569', textAlign: 'center',
    }}>Waiting for model data...</div>
  )

  return (
    <div style={{
      background: 'var(--bg2)', border: '1px solid var(--border)',
      borderRadius: 8, overflow: 'hidden',
    }}>
      <div style={{
        padding: '8px 12px', borderBottom: '1px solid var(--border)',
        background: 'var(--bg1)', fontSize: 12, fontWeight: 600,
      }}>AI Model Status</div>

      <div style={{ padding: 12, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <Card title="CNN-LSTM IDS" color="#3b82f6">
          <Row label="Trained" value={model.cnn_trained ? '✓ Yes' : '✗ No'} />
          <Row label="Val Accuracy" value={`${(model.cnn_val_acc * 100).toFixed(1)}%`} />
          <Bar value={model.cnn_val_acc} color="#3b82f6" />
          <Row label="Rounds" value={String(model.cnn_rounds)} />
        </Card>

        <Card title="Autoencoder (AE)" color="#8b5cf6">
          <Row label="Trained" value={model.ae_trained ? '✓ Yes' : '✗ No'} />
          <Row label="Threshold" value={model.ae_threshold.toFixed(4)} />
          <Row label="Drift Count" value={String(model.ae_drift_count)} />
          <Row label="Replay Buffer" value={model.ae_replay_buf_size.toLocaleString()} />
        </Card>

        <Card title="Zero-Day Detection" color="#ef4444">
          <Row label="ZD Alerts" value={String(model.zero_day_alerts)} />
          <Row label="Critical" value={String(model.critical_alerts)} />
          <Row label="ZD Vehicles" value={model.zero_day_vehicles.join(', ') || 'None'} />
        </Card>

        <Card title="Federated Learning" color="#10b981">
          <Row label="Round" value={String(model.fl_round)} />
          <Row label="Strategy" value={model.fl_strategy} />
          <Row label="Predictions" value={model.total_predictions.toLocaleString()} />
          <Row label="Detection Rate" value={`${(model.detection_rate * 100).toFixed(1)}%`} />
          <Bar value={model.detection_rate} color="#10b981" />
        </Card>
      </div>
    </div>
  )
}

function Card({ title, color, children }: { title: string; color: string; children: React.ReactNode }) {
  return (
    <div style={{
      background: 'var(--bg3)', border: '1px solid var(--border)',
      borderRadius: 6, padding: 10,
      borderTop: `2px solid ${color}`,
    }}>
      <div style={{ fontSize: 11, fontWeight: 700, color, marginBottom: 8 }}>{title}</div>
      {children}
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, padding: '2px 0', color: '#94a3b8' }}>
      <span>{label}</span>
      <span style={{ color: '#e2e8f0', fontWeight: 500 }}>{value}</span>
    </div>
  )
}
