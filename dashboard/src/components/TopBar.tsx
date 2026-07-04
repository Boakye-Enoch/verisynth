import React from 'react';
import { AlertTriangle, Settings, Maximize2, X } from 'lucide-react';
import { SimulationStatus } from '../types';

interface TopBarProps {
  status: SimulationStatus;
}

const TopBar: React.FC<TopBarProps> = ({ status }) => {
  const getThreatColor = (level: string) => {
    switch (level) {
      case 'CRITICAL':
        return 'bg-red-900/20 border-red-500 text-red-400';
      case 'HIGH':
        return 'bg-orange-900/20 border-orange-500 text-orange-400';
      case 'MEDIUM':
        return 'bg-yellow-900/20 border-yellow-500 text-yellow-400';
      case 'LOW':
        return 'bg-green-900/20 border-green-500 text-green-400';
      default:
        return 'bg-slate-900/20 border-slate-500 text-slate-400';
    }
  };

  const getThreatBarColor = (level: string) => {
    switch (level) {
      case 'CRITICAL':
        return 'bg-gradient-to-r from-red-600 to-red-400';
      case 'HIGH':
        return 'bg-gradient-to-r from-orange-600 to-orange-400';
      case 'MEDIUM':
        return 'bg-gradient-to-r from-yellow-600 to-yellow-400';
      case 'LOW':
        return 'bg-gradient-to-r from-green-600 to-green-400';
      default:
        return 'bg-gradient-to-r from-slate-600 to-slate-400';
    }
  };

  return (
    <div className="bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 border-b border-blue-900/30 px-8 py-4">
      <div className="flex items-center justify-between">
        {/* Left Section - Status */}
        <div className="flex items-center gap-8">
          <div>
            <h2 className="text-sm font-semibold text-slate-400 mb-1">SIMULATION STATUS</h2>
            <div className="flex items-center gap-3">
              <div className={`w-3 h-3 rounded-full ${
                status.state === 'RUNNING' ? 'bg-green-500 animate-pulse' : 'bg-slate-500'
              }`} />
              <span className="text-lg font-bold text-white">{status.state}</span>
            </div>
          </div>
        </div>

        {/* Center Section - Times */}
        <div className="flex items-center gap-12">
          <div>
            <p className="text-xs text-slate-500 mb-1">TIME</p>
            <p className="font-mono text-lg text-white">{status.currentTime}</p>
          </div>
          <div>
            <p className="text-xs text-slate-500 mb-1">SIM TIME</p>
            <p className="font-mono text-lg text-white">{status.simTime}</p>
          </div>
          <div>
            <p className="text-xs text-slate-500 mb-1">DATE</p>
            <p className="font-mono text-lg text-white">{status.date}</p>
          </div>
        </div>

        {/* Right Section - Threat Level */}
        <div className="flex items-center gap-4">
          <div className="text-right">
            <p className="text-xs text-slate-500 mb-2">THREAT LEVEL</p>
            <div className={`px-4 py-1 rounded border-2 font-bold ${
              getThreatColor(status.threatLevel)
            }`}>
              {status.threatLevel}
            </div>
          </div>
          <div className="flex flex-col gap-1 min-w-[120px]">
            <div className="flex gap-1">
              {Array.from({ length: 10 }).map((_, i) => (
                <div
                  key={i}
                  className={`h-2 flex-1 rounded-sm ${
                    i < Math.ceil(status.threatPercentage / 10)
                      ? getThreatBarColor(status.threatLevel)
                      : 'bg-slate-700'
                  }`}
                />
              ))}
            </div>
            <span className="text-xs text-slate-400">{status.threatPercentage}%</span>
          </div>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-2">
          <button className="p-2 hover:bg-slate-700 rounded transition-colors">
            <Settings size={18} className="text-slate-400 hover:text-slate-200" />
          </button>
          <button className="p-2 hover:bg-slate-700 rounded transition-colors">
            <Maximize2 size={18} className="text-slate-400 hover:text-slate-200" />
          </button>
          <button className="p-2 hover:bg-red-900/30 rounded transition-colors">
            <AlertTriangle size={18} className="text-red-400 hover:text-red-300" />
          </button>
        </div>
      </div>
    </div>
  );
};

export default TopBar;
