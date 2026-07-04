import { configureStore, createSlice, PayloadAction } from '@reduxjs/toolkit';
import type { DashboardState, SimulationStatus, DashboardMetrics, Vehicle, Attack, AttackAlert, PerformanceMetrics, TrustMetrics, TimelineEvent, NetworkNode, NetworkEdge, ActionLog, SystemHealth } from './types';

const initialState: DashboardState = {
  simulation: {
    state: 'IDLE',
    currentTime: '00:00:00',
    simTime: '00:00:00',
    date: new Date().toLocaleDateString(),
    threatLevel: 'LOW',
    threatPercentage: 0,
  },
  metrics: {
    totalVehicles: 0,
    activeVehicles: 0,
    idleVehicles: 0,
    totalMessages: 0,
    messagesPerSecond: 0,
    packetsPerSecond: 0,
    activeAttacks: 0,
    detectedAttacks: 0,
    detectionRate: 0,
    falsePositives: 0,
    falsePositiveRate: 0,
    liveIDSAlerts: 0,
  },
  vehicles: [],
  attacks: [],
  alerts: [],
  performance: {
    detectionRate: 0,
    precision: 0,
    f1Score: 0,
    fpr: 0,
    latency: 0,
    throughput: 0,
  },
  trust: {
    averageTrustScore: 0,
    trustHistory: [],
  },
  timeline: [],
  network: {
    nodes: [],
    edges: [],
  },
  actions: [],
  health: {
    status: 'healthy',
    score: 100,
    dataCollection: 'healthy',
    featureExtraction: 'healthy',
    mlModel: 'healthy',
    anomalyDetector: 'healthy',
    trustManager: 'healthy',
    alertManager: 'healthy',
  },
  loading: false,
  error: null,
};

const dashboardSlice = createSlice({
  name: 'dashboard',
  initialState,
  reducers: {
    setSimulationStatus: (state, action: PayloadAction<Partial<SimulationStatus>>) => {
      state.simulation = { ...state.simulation, ...action.payload };
    },
    setMetrics: (state, action: PayloadAction<Partial<DashboardMetrics>>) => {
      state.metrics = { ...state.metrics, ...action.payload };
    },
    setVehicles: (state, action: PayloadAction<Vehicle[]>) => {
      state.vehicles = action.payload;
    },
    addAttack: (state, action: PayloadAction<Attack>) => {
      state.attacks.push(action.payload);
    },
    addAlert: (state, action: PayloadAction<AttackAlert>) => {
      state.alerts.push(action.payload);
      if (state.alerts.length > 10) {
        state.alerts.shift();
      }
    },
    setPerformance: (state, action: PayloadAction<PerformanceMetrics>) => {
      state.performance = action.payload;
    },
    setTrust: (state, action: PayloadAction<TrustMetrics>) => {
      state.trust = action.payload;
    },
    addTimelineEvent: (state, action: PayloadAction<TimelineEvent>) => {
      state.timeline.push(action.payload);
    },
    setNetwork: (state, action: PayloadAction<{ nodes: NetworkNode[]; edges: NetworkEdge[] }>) => {
      state.network = action.payload;
    },
    addAction: (state, action: PayloadAction<ActionLog>) => {
      state.actions.unshift(action.payload);
      if (state.actions.length > 50) {
        state.actions.pop();
      }
    },
    setHealth: (state, action: PayloadAction<SystemHealth>) => {
      state.health = action.payload;
    },
    setLoading: (state, action: PayloadAction<boolean>) => {
      state.loading = action.payload;
    },
    setError: (state, action: PayloadAction<string | null>) => {
      state.error = action.payload;
    },
    resetDashboard: () => initialState,
  },
});

export const {
  setSimulationStatus,
  setMetrics,
  setVehicles,
  addAttack,
  addAlert,
  setPerformance,
  setTrust,
  addTimelineEvent,
  setNetwork,
  addAction,
  setHealth,
  setLoading,
  setError,
  resetDashboard,
} = dashboardSlice.actions;

export const store = configureStore({
  reducer: {
    dashboard: dashboardSlice.reducer,
  },
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
