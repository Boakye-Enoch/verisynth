import { create } from 'zustand'
import type {
  VehicleState, AttackInfo, IDSAlert, TrustEntry,
  ModelStatus, SystemHealth, SimState, BusEvent,
} from './types'

const API = 'http://localhost:8001'
const WS  = 'ws://localhost:8001/ws'

interface SOCStore {
  // Connection
  connected:      boolean
  wsError:        string | null
  lastSeq:        number

  // Simulation
  sim:            SimState
  vehicles:       VehicleState[]
  attacks:        AttackInfo[]
  alerts:         IDSAlert[]        // last 100
  trustEntries:   TrustEntry[]
  model:          ModelStatus | null
  health:         SystemHealth | null

  // Timeline (last 200 events for attack timeline panel)
  timeline:       BusEvent[]

  // Security mode
  securityMode:   boolean
  securityMessage: string

  // Selected vehicle (inspector panel)
  selectedVehicle: string | null

  // UI state
  activePanel:    string

  // Actions
  connect:        () => void
  setSecurityMode:(enabled: boolean) => Promise<void>
  disconnect:     () => void
  selectVehicle:  (id: string | null) => void
  setActivePanel: (panel: string) => void
  activateAttack: (type: string, duration?: number) => Promise<void>
  deactivateAttack:(type: string) => Promise<void>
  deactivateAll:  () => Promise<void>
  changeScene:    (changeType: string, value: string) => Promise<void>
}

let ws: WebSocket | null = null

export const useSOCStore = create<SOCStore>((set, get) => ({
  connected:       false,
  wsError:         null,
  lastSeq:         0,
  sim: {
    running: false, sim_step: 0, sim_time: 0,
    current_town: 'Town04', current_weather: 'ClearNoon',
    peak_vehicles: 0, total_alerts: 0, total_injected: 0, wall_time_s: 0,
  },
  vehicles:        [],
  attacks:         [],
  alerts:          [],
  trustEntries:    [],
  model:           null,
  health:          null,
  timeline:        [],
  securityMode:    true,
  securityMessage: '',
  selectedVehicle: null,
  activePanel:     'dashboard',

  connect: () => {
    if (ws) ws.close()

    ws = new WebSocket(WS)

    ws.onopen = () => {
      set({ connected: true, wsError: null })
      // Fetch initial REST state
      fetch(`${API}/sim/status`)
        .then(r => r.json())
        .then(data => set({ sim: data }))
        .catch(() => {})
    }

    ws.onclose = () => {
      set({ connected: false })
      // Reconnect after 3s
      setTimeout(() => get().connect(), 3000)
    }

    ws.onerror = () => {
      set({ wsError: 'WebSocket connection failed' })
    }

    ws.onmessage = (evt) => {
      try {
        const event: BusEvent = JSON.parse(evt.data)
        get()._handleEvent(event)
      } catch { /* ignore parse errors */ }
    }
  },

  disconnect: () => {
    if (ws) { ws.close(); ws = null }
    set({ connected: false })
  },

  selectVehicle:  (id) => set({ selectedVehicle: id }),
  setActivePanel: (panel) => set({ activePanel: panel }),

  // @ts-ignore internal handler
  _handleEvent: (event: BusEvent) => {
    const { type, payload, sim_step, sim_time } = event

    // Track timeline
    set(s => ({
      lastSeq:  event.seq,
      timeline: [...s.timeline.slice(-199), event],
    }))

    switch (type) {
      case 'SIM_START':
        set(s => ({
          sim: { ...s.sim, running: true,
            current_town: (payload.town as string) || s.sim.current_town,
            current_weather: (payload.weather as string) || s.sim.current_weather,
          }
        }))
        break

      case 'SIM_STOP':
        set(s => ({
          sim: { ...s.sim, running: false,
            total_alerts: (payload.total_alerts as number) || s.sim.total_alerts,
            total_injected: (payload.total_injected as number) || s.sim.total_injected,
          }
        }))
        break

      case 'VEHICLE_UPDATE': {
        const p = payload as Record<string, unknown>
        set({
          vehicles: (p.vehicles as VehicleState[]) || [],
          sim: {
            ...get().sim,
            running: true,
            sim_step,
            sim_time,
          }
        })
        break
      }

      case 'ATTACK_STATUS':
        set({ attacks: (payload.attacks as AttackInfo[]) || [] })
        break

      case 'IDS_ALERT': {
        const alert: IDSAlert = {
          ...(payload as unknown as IDSAlert),
          sim_step,
          sim_time,
          received_at: Date.now(),
        }
        set(s => ({ alerts: [alert, ...s.alerts].slice(0, 100) }))
        // Increment alert count
        set(s => ({ sim: { ...s.sim, total_alerts: s.sim.total_alerts + 1 } }))
        break
      }

      case 'TRUST_SNAPSHOT':
        set({ trustEntries: (payload.vehicles as TrustEntry[]) || [] })
        break

      case 'MODEL_STATUS':
        set({ model: payload as unknown as ModelStatus })
        break

      case 'SYSTEM_HEALTH':
        set({ health: payload as unknown as SystemHealth })
        set(s => ({
          sim: { ...s.sim, running: (payload.sim_step as number) > 0 }
        }))
        break

      case 'SECURITY_MODE':
        set({
          securityMode: payload.enabled as boolean,
          securityMessage: payload.message as string,
        })
        break

      case 'SCENE_CHANGE':
        set(s => ({
          sim: {
            ...s.sim,
            current_town: (payload.current_town as string) || s.sim.current_town,
            current_weather: (payload.current_weather as string) || s.sim.current_weather,
          }
        }))
        break
    }
  },

  activateAttack: async (attackType, duration) => {
    await fetch(`${API}/attacks/activate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ attack_type: attackType, duration_steps: duration }),
    })
  },

  deactivateAttack: async (attackType) => {
    await fetch(`${API}/attacks/deactivate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ attack_type: attackType }),
    })
  },

  deactivateAll: async () => {
    await fetch(`${API}/attacks/deactivate_all`, { method: 'POST' })
  },

  setSecurityMode: async (enabled: boolean) => {
    const res = await fetch(`${API}/security/mode`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled }),
    })
    const data = await res.json()
    set({ securityMode: enabled, securityMessage: data.message || '' })
  },

  changeScene: async (changeType, value) => {
    await fetch(`${API}/scene/change`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ change_type: changeType, value }),
    })
  },
}))

// Security mode is appended separately — see setSecurityMode action
