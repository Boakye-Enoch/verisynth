// Simulation & Status Types
export interface SimulationStatus {
  state: 'RUNNING' | 'PAUSED' | 'STOPPED' | 'IDLE';
  currentTime: string;
  simTime: string;
  date: string;
  threatLevel: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  threatPercentage: number;
}

// Vehicle Types
export interface Vehicle {
  id: string;
  type: 'normal' | 'attacked' | 'isolated';
  speed: number;
  threat: number;
  position: [number, number];
  status: 'active' | 'inactive' | 'compromised';
  communication: 'normal' | 'malicious';
}

// Attack Types
export type AttackType = 'SPOOFING' | 'REPLAY' | 'DOS' | 'SYBIL' | 'ANOMALY';

export interface Attack {
  id: string;
  type: AttackType;
  vehicleId: string;
  targetVehicleId?: string;
  timestamp: number;
  confidence: number;
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  source: string;
  status: 'detected' | 'mitigated' | 'blocked';
}

export interface AttackAlert {
  id: string;
  type: AttackType;
  vehicle: string;
  confidence: number;
  source: string;
  timestamp: number;
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
}

// IDS Detection
export interface IDSDetection {
  id: string;
  type: string;
  vehicleId: string;
  timestamp: number;
  confidence: number;
  detectionRate: number;
  falsePositives: number;
}

// Metrics Types
export interface DashboardMetrics {
  totalVehicles: number;
  activeVehicles: number;
  idleVehicles: number;
  totalMessages: number;
  messagesPerSecond: number;
  packetsPerSecond: number;
  activeAttacks: number;
  detectedAttacks: number;
  detectionRate: number;
  falsePositives: number;
  falsePositiveRate: number;
  liveIDSAlerts: number;
}

// Performance Metrics
export interface PerformanceMetrics {
  detectionRate: number;
  precision: number;
  f1Score: number;
  fpr: number;
  latency: number;
  throughput: number;
}

// Trust Metrics
export interface TrustMetrics {
  averageTrustScore: number;
  trustHistory: Array<{
    timestamp: number;
    score: number;
  }>;
}

// Attack Timeline Event
export interface TimelineEvent {
  id: string;
  timestamp: number;
  type: 'SIM_START' | 'SPOOFING' | 'REPLAY' | 'DOS' | 'SYBIL' | 'SIM_END';
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
}

// Network Topology
export interface NetworkNode {
  id: string;
  label: string;
  type: 'vehicle' | 'rsu' | 'gateway';
  status: 'healthy' | 'attacked' | 'isolated';
  position: [number, number];
}

export interface NetworkEdge {
  source: string;
  target: string;
  type: 'normal' | 'malicious' | 'isolated';
}

// Action Log
export interface ActionLog {
  id: string;
  timestamp: number;
  vehicle: string;
  action: string;
  performedBy: string;
  status: 'completed' | 'pending' | 'failed';
}

// System Health
export interface SystemHealth {
  status: 'healthy' | 'warning' | 'critical';
  score: number; // 0-100
  dataCollection: 'healthy' | 'warning' | 'critical';
  featureExtraction: 'healthy' | 'warning' | 'critical';
  mlModel: 'healthy' | 'warning' | 'critical';
  anomalyDetector: 'healthy' | 'warning' | 'critical';
  trustManager: 'healthy' | 'warning' | 'critical';
  alertManager: 'healthy' | 'warning' | 'critical';
}

// Redux State
export interface DashboardState {
  simulation: SimulationStatus;
  metrics: DashboardMetrics;
  vehicles: Vehicle[];
  attacks: Attack[];
  alerts: AttackAlert[];
  performance: PerformanceMetrics;
  trust: TrustMetrics;
  timeline: TimelineEvent[];
  network: {
    nodes: NetworkNode[];
    edges: NetworkEdge[];
  };
  actions: ActionLog[];
  health: SystemHealth;
  loading: boolean;
  error: string | null;
}
