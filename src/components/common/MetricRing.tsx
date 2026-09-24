import React from 'react';

interface MetricRingProps {
  percent: number;
  size?: number;
  strokeWidth?: number;
  color?: string;
  glowColor?: string;
  label?: string;
}

export const MetricRing: React.FC<MetricRingProps> = ({
  percent,
  size = 54,
  strokeWidth = 5,
  color = 'var(--cyan)',
  glowColor = 'rgba(0, 240, 255, 0.4)',
  label,
}) => {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const clampedPercent = Math.max(0, Math.min(100, percent));
  const strokeDashoffset = circumference - (clampedPercent / 100) * circumference;

  return (
    <div style={{ position: 'relative', width: size, height: size, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        {/* Track */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="rgba(255, 255, 255, 0.08)"
          strokeWidth={strokeWidth}
          fill="transparent"
        />
        {/* Gauge Fill */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={color}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          strokeLinecap="round"
          fill="transparent"
          style={{
            transition: 'stroke-dashoffset 0.6s cubic-bezier(0.16, 1, 0.3, 1)',
            filter: `drop-shadow(0 0 6px ${glowColor})`,
          }}
        />
      </svg>
      <div
        style={{
          position: 'absolute',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '11px',
          fontWeight: 700,
          fontFamily: 'JetBrains Mono, monospace',
          color: 'var(--text-primary)',
        }}
      >
        <span>{Math.round(clampedPercent)}%</span>
      </div>
    </div>
  );
};
