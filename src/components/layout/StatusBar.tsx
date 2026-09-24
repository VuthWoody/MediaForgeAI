import React from 'react';
import { Cpu, HardDrive, Zap, CheckCircle2, AlertTriangle, Terminal } from 'lucide-react';
import { useSystem } from '../../context/SystemContext';
import { formatBytes } from '../../utils/formatters';

interface StatusBarProps {
  onOpenLogs: () => void;
}

export const StatusBar: React.FC<StatusBarProps> = ({ onOpenLogs }) => {
  const { metrics, hardware } = useSystem();

  const ffmpegReady = hardware?.ffmpeg?.installed ?? true;

  return (
    <footer className="statusbar">
      <div className="statusbar-left">
        <div className="statusbar-item">
          <div className="pulse-dot" />
          <span style={{ color: 'var(--text-secondary)' }}>System Active</span>
        </div>

        <div className="statusbar-item">
          {ffmpegReady ? (
            <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: 'var(--emerald)' }}>
              <CheckCircle2 size={12} />
              <span>FFmpeg 63.x</span>
            </span>
          ) : (
            <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: 'var(--amber)' }}>
              <AlertTriangle size={12} />
              <span>FFmpeg Missing</span>
            </span>
          )}
        </div>

        {hardware?.gpus?.[0]?.name && (
          <div className="statusbar-item">
            <span style={{ color: 'var(--text-muted)' }}>GPU:</span>
            <span style={{ color: 'var(--text-secondary)' }}>{hardware.gpus[0].name}</span>
          </div>
        )}
      </div>

      <div className="statusbar-right">
        {/* CPU Telemetry */}
        <div className="telemetry-pill active" title="Processor Load">
          <Cpu size={12} color="var(--cyan)" />
          <span>CPU {metrics.cpuUsagePercent}%</span>
        </div>

        {/* RAM Telemetry */}
        <div className="telemetry-pill" title={`Memory: ${formatBytes(metrics.memoryUsedBytes)} of ${formatBytes(metrics.memoryTotalBytes)}`}>
          <span>RAM {metrics.memoryUsagePercent}%</span>
        </div>

        {/* Disk Space */}
        <div className="telemetry-pill" title={`Available disk space: ${formatBytes(metrics.diskFreeBytes)}`}>
          <HardDrive size={12} color="var(--text-muted)" />
          <span>{formatBytes(metrics.diskFreeBytes)} Free</span>
        </div>

        {/* Logs quick button */}
        <button
          onClick={onOpenLogs}
          style={{
            background: 'transparent',
            border: 'none',
            color: 'var(--text-muted)',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            fontSize: '11px',
            padding: '2px 6px',
            borderRadius: '4px',
          }}
          title="Open Logs & Diagnostics"
        >
          <Terminal size={12} />
          <span>Console</span>
        </button>
      </div>
    </footer>
  );
};
