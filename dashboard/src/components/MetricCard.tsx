import React from 'react';
import { ArrowUp, ArrowDown } from 'lucide-react';

interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: React.ReactNode;
  trend?: 'up' | 'down' | 'stable';
  trendValue?: string;
  color?: 'blue' | 'green' | 'red' | 'yellow' | 'purple';
  onClick?: () => void;
}

const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  subtitle,
  icon,
  trend,
  trendValue,
  color = 'blue',
  onClick,
}) => {
  const colorClasses = {
    blue: 'border-blue-500/30 hover:border-blue-500/60 bg-blue-500/5 hover:bg-blue-500/10',
    green: 'border-green-500/30 hover:border-green-500/60 bg-green-500/5 hover:bg-green-500/10',
    red: 'border-red-500/30 hover:border-red-500/60 bg-red-500/5 hover:bg-red-500/10',
    yellow: 'border-yellow-500/30 hover:border-yellow-500/60 bg-yellow-500/5 hover:bg-yellow-500/10',
    purple: 'border-purple-500/30 hover:border-purple-500/60 bg-purple-500/5 hover:bg-purple-500/10',
  };

  const trendColors = {
    blue: 'text-blue-400',
    green: 'text-green-400',
    red: 'text-red-400',
    yellow: 'text-yellow-400',
    purple: 'text-purple-400',
  };

  return (
    <div
      onClick={onClick}
      className={`p-4 rounded-lg border transition-all duration-200 cursor-pointer ${
        colorClasses[color]
      }`}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-xs font-semibold text-slate-400 mb-2 uppercase">{title}</p>
          <div className="flex items-end gap-2">
            <p className={`text-3xl font-bold ${ trendColors[color]}`}>
              {value}
            </p>
            {trend && (
              <div className={`flex items-center gap-1 mb-1 ${
                trend === 'up' ? 'text-green-400' : trend === 'down' ? 'text-red-400' : 'text-slate-400'
              }`}>
                {trend === 'up' && <ArrowUp size={16} />}
                {trend === 'down' && <ArrowDown size={16} />}
                {trendValue && <span className="text-sm font-semibold">{trendValue}</span>}
              </div>
            )}
          </div>
          {subtitle && (
            <p className="text-xs text-slate-500 mt-2">{subtitle}</p>
          )}
        </div>
        {icon && (
          <div className={`p-2 rounded-lg bg-black/20 ${ trendColors[color]}`}>
            {icon}
          </div>
        )}
      </div>
    </div>
  );
};

export default MetricCard;
