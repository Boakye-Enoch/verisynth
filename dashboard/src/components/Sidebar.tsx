import React from 'react';
import { LayoutDashboard, Activity, Network, Truck, AlertCircle, Shield, Zap, BarChart3, FileText, RotateCw, Settings, Menu, X } from 'lucide-react';
import { useState } from 'react';

interface SidebarProps {
  activeSection: string;
  onSectionChange: (section: string) => void;
}

const Sidebar: React.FC<SidebarProps> = ({ activeSection, onSectionChange }) => {
  const [isOpen, setIsOpen] = useState(false);

  const menuItems = [
    { id: 'dashboard', label: 'DASHBOARD', icon: LayoutDashboard },
    { id: 'live-view', label: 'LIVE VIEW', icon: Activity },
    { id: 'network-topology', label: 'NETWORK TOPOLOGY', icon: Network },
    { id: 'vehicles', label: 'VEHICLES', icon: Truck },
    { id: 'ids-detections', label: 'IDS DETECTIONS', icon: AlertCircle },
    { id: 'trust-manager', label: 'TRUST MANAGER', icon: Shield },
    { id: 'attack-analysis', label: 'ATTACK ANALYSIS', icon: Zap },
    { id: 'traffic-monitor', label: 'TRAFFIC MONITOR', icon: BarChart3 },
    { id: 'performance', label: 'PERFORMANCE', icon: BarChart3 },
    { id: 'logs-events', label: 'LOGS & EVENTS', icon: FileText },
    { id: 'replay', label: 'REPLAY', icon: RotateCw },
    { id: 'reports', label: 'REPORTS', icon: FileText },
    { id: 'settings', label: 'SETTINGS', icon: Settings },
  ];

  return (
    <>
      {/* Mobile Toggle */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="lg:hidden fixed top-4 left-4 z-50 p-2 bg-slate-800 text-white rounded"
      >
        {isOpen ? <X size={24} /> : <Menu size={24} />}
      </button>

      {/* Sidebar */}
      <aside
        className={`${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        } lg:translate-x-0 fixed lg:relative left-0 top-0 h-screen w-64 bg-gradient-to-b from-slate-900 via-slate-800 to-slate-900 border-r border-blue-900/30 transition-transform duration-300 z-40 pt-20 lg:pt-0 overflow-y-auto`}
      >
        <div className="p-6 border-b border-blue-900/30">
          <div className="flex items-center gap-3">
            <Shield className="w-8 h-8 text-blue-500" />
            <div>
              <h1 className="font-bold text-white text-lg">VERISYNTH</h1>
              <p className="text-xs text-blue-300">V2X Security</p>
            </div>
          </div>
        </div>

        <nav className="p-4 space-y-2">
          {menuItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeSection === item.id;
            return (
              <button
                key={item.id}
                onClick={() => {
                  onSectionChange(item.id);
                  setIsOpen(false);
                }}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 ${
                  isActive
                    ? 'bg-blue-600/20 text-blue-400 border-l-2 border-blue-400'
                    : 'text-slate-300 hover:bg-slate-700/50 hover:text-slate-100'
                }`}
              >
                <Icon size={18} />
                <span className="text-sm font-medium">{item.label}</span>
              </button>
            );
          })}
        </nav>
      </aside>
    </>
  );
};

export default Sidebar;
