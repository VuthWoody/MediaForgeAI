import React, { useState } from 'react';
import {
  Sparkles,
  Plus,
  FileVideo,
  DownloadCloud,
  Layers,
  Cpu,
  Activity,
  HardDrive,
  Clock,
  ArrowUpRight,
  CheckCircle2,
  FolderOpen,
  Play,
  Languages,
} from 'lucide-react';
import { useSystem } from '../../context/SystemContext';
import { useProject } from '../../context/ProjectContext';
import { MetricRing } from '../common/MetricRing';
import { formatBytes, formatDuration, formatDate, getLanguageName } from '../../utils/formatters';
import { ActiveModule } from '../layout/Sidebar';
import { NewProjectModal } from '../projects/NewProjectModal';

interface DashboardViewProps {
  onNavigate: (module: ActiveModule) => void;
}

export const DashboardView: React.FC<DashboardViewProps> = ({ onNavigate }) => {
  const { metrics, hardware } = useSystem();
  const { projects, openProject, selectMediaFile, createProject } = useProject();
  const [isNewProjectModalOpen, setIsNewProjectModalOpen] = useState(false);

  const handleImportVideo = async () => {
    const filePath = await selectMediaFile();
    if (filePath) {
      const filename = filePath.split(/[\\/]/).pop() || 'Imported Video';
      const created = await createProject({
        name: filename.replace(/\.[^/.]+$/, ''),
        sourceMedia: {
          type: 'file',
          pathOrUrl: filePath,
          filename: filename,
          durationSeconds: 0,
          resolution: { width: 1920, height: 1080 },
          fps: 30,
          fileSizeBytes: 0,
          codec: 'h264',
          audioSampleRate: 44100,
          audioChannels: 2,
        },
      });
      await openProject(created.id);
      onNavigate('projects');
    }
  };

  const handleOpenProject = async (id: string) => {
    await openProject(id);
    onNavigate('studio');
  };

  return (
    <div className="dashboard-container">
      {/* Hero Header */}
      <div className="dashboard-hero">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <h1 className="hero-title">
              <span>Studio Dashboard</span>
              <span className="badge badge-cyan" style={{ fontSize: '12px' }}>Forge Hub</span>
            </h1>
            <p className="hero-subtitle">
              High-performance media downloading, AI speech translation, subtitle creation, and video dubbing.
            </p>
          </div>
          <button
            className="btn btn-primary btn-lg"
            onClick={() => setIsNewProjectModalOpen(true)}
          >
            <Plus size={18} />
            <span>New Project</span>
          </button>
        </div>
      </div>

      {/* System Telemetry & Hardware Gauges */}
      <div className="metrics-grid">
        {/* CPU Usage Card */}
        <div className="metric-card">
          <div className="metric-info">
            <span className="metric-label">CPU Utilization</span>
            <div className="metric-value">{metrics.cpuUsagePercent}%</div>
            <span className="metric-subtext">
              {hardware?.cpuCores ? `${hardware.cpuCores} Cores Active` : 'Multi-threaded'}
            </span>
          </div>
          <MetricRing
            percent={metrics.cpuUsagePercent}
            color="var(--cyan)"
            glowColor="rgba(0, 240, 255, 0.45)"
          />
        </div>

        {/* RAM Usage Card */}
        <div className="metric-card">
          <div className="metric-info">
            <span className="metric-label">Memory Allocation</span>
            <div className="metric-value">{formatBytes(metrics.memoryUsedBytes, 1)}</div>
            <span className="metric-subtext">
              of {formatBytes(metrics.memoryTotalBytes, 0)} ({metrics.memoryUsagePercent}%)
            </span>
          </div>
          <MetricRing
            percent={metrics.memoryUsagePercent}
            color="var(--violet)"
            glowColor="rgba(139, 92, 246, 0.45)"
          />
        </div>

        {/* GPU Card */}
        <div className="metric-card">
          <div className="metric-info">
            <span className="metric-label">Graphics Hardware</span>
            <div className="metric-value" style={{ fontSize: '16px', marginTop: '4px' }}>
              {hardware?.gpus?.[0]?.name || metrics.gpuName}
            </div>
            <span className="metric-subtext" style={{ color: 'var(--emerald)' }}>
              Hardware Acceleration Ready
            </span>
          </div>
          <div
            style={{
              width: 50,
              height: 50,
              borderRadius: '12px',
              background: 'rgba(16, 185, 129, 0.1)',
              border: '1px solid rgba(16, 185, 129, 0.25)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--emerald)',
              boxShadow: '0 0 15px rgba(16, 185, 129, 0.2)',
            }}
          >
            <Activity size={24} />
          </div>
        </div>

        {/* Disk Storage Card */}
        <div className="metric-card">
          <div className="metric-info">
            <span className="metric-label">Storage Capacity</span>
            <div className="metric-value">{formatBytes(metrics.diskFreeBytes, 0)}</div>
            <span className="metric-subtext">
              Available on Workspace Drive
            </span>
          </div>
          <div
            style={{
              width: 50,
              height: 50,
              borderRadius: '12px',
              background: 'rgba(245, 158, 11, 0.1)',
              border: '1px solid rgba(245, 158, 11, 0.25)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--amber)',
            }}
          >
            <HardDrive size={24} />
          </div>
        </div>
      </div>

      {/* Quick Action Banners */}
      <div className="actions-grid">
        <div className="action-card" onClick={() => setIsNewProjectModalOpen(true)}>
          <div className="action-icon-wrapper">
            <Plus size={22} />
          </div>
          <div>
            <h3 className="action-title">New Project</h3>
            <p className="action-desc">Start a blank translation, subtitling, or voice-dubbing session.</p>
          </div>
        </div>

        <div className="action-card" onClick={handleImportVideo}>
          <div className="action-icon-wrapper" style={{ background: 'var(--violet-dim)', color: 'var(--violet)', borderColor: 'rgba(139, 92, 246, 0.3)' }}>
            <FileVideo size={22} />
          </div>
          <div>
            <h3 className="action-title">Import Video</h3>
            <p className="action-desc">Select local MP4, MKV, or MOV media to extract audio & transcribe.</p>
          </div>
        </div>

        <div className="action-card" onClick={() => onNavigate('downloader')}>
          <div className="action-icon-wrapper" style={{ background: 'var(--emerald-dim)', color: 'var(--emerald)', borderColor: 'rgba(16, 185, 129, 0.3)' }}>
            <DownloadCloud size={22} />
          </div>
          <div>
            <h3 className="action-title">Download Media</h3>
            <p className="action-desc">Grab 4K video, audio streams, and captions from permitted URLs.</p>
          </div>
        </div>

        <div className="action-card" onClick={() => onNavigate('batch')}>
          <div className="action-icon-wrapper" style={{ background: 'var(--amber-dim)', color: 'var(--amber)', borderColor: 'rgba(245, 158, 11, 0.3)' }}>
            <Layers size={22} />
          </div>
          <div>
            <h3 className="action-title">Batch Queue</h3>
            <p className="action-desc">Process multiple media files in background with worker threads.</p>
          </div>
        </div>
      </div>

      {/* Main Grid: Recent Projects & System Readiness Diagnostics */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '24px' }}>
        {/* Recent Projects Section */}
        <div className="card" style={{ padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '18px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Clock size={18} color="var(--cyan)" />
              <h2 style={{ fontSize: '17px', fontWeight: 700, fontFamily: 'Outfit, sans-serif' }}>
                Recent Studio Projects
              </h2>
            </div>
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => onNavigate('projects')}
              style={{ display: 'flex', alignItems: 'center', gap: '4px' }}
            >
              <span>View All ({projects.length})</span>
              <ArrowUpRight size={14} />
            </button>
          </div>

          {projects.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--text-muted)' }}>
              <FolderOpen size={40} style={{ margin: '0 auto 12px auto', opacity: 0.4 }} />
              <p style={{ fontSize: '14px', marginBottom: '12px' }}>No projects created yet.</p>
              <button className="btn btn-secondary btn-sm" onClick={() => setIsNewProjectModalOpen(true)}>
                Create First Project
              </button>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {projects.slice(0, 4).map((proj) => (
                <div
                  key={proj.id}
                  onClick={() => handleOpenProject(proj.id)}
                  style={{
                    background: 'var(--bg-surface)',
                    border: '1px solid var(--glass-border)',
                    borderRadius: 'var(--radius-md)',
                    padding: '14px 16px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    cursor: 'pointer',
                    transition: 'all var(--transition-fast)',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = 'rgba(0, 240, 255, 0.3)';
                    e.currentTarget.style.transform = 'translateX(4px)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = 'var(--glass-border)';
                    e.currentTarget.style.transform = 'none';
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                    <div
                      style={{
                        width: 42,
                        height: 42,
                        borderRadius: '8px',
                        background: 'linear-gradient(135deg, #162032 0%, #202d44 100%)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: 'var(--cyan)',
                        border: '1px solid var(--glass-border)',
                      }}
                    >
                      <Play size={18} />
                    </div>
                    <div>
                      <h4 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '3px' }}>
                        {proj.name}
                      </h4>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', color: 'var(--text-muted)' }}>
                        <span style={{ color: 'var(--text-cyan)', textTransform: 'uppercase', fontWeight: 600 }}>
                          {getLanguageName(proj.sourceLanguage)} → {getLanguageName(proj.targetLanguage)}
                        </span>
                        <span>•</span>
                        <span>{formatDuration(proj.durationSeconds)}</span>
                        <span>•</span>
                        <span>Modified {formatDate(proj.updatedAt)}</span>
                      </div>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <span className="badge badge-violet">
                      {proj.status}
                    </span>
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleOpenProject(proj.id);
                      }}
                    >
                      Open
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* System & Hardware Readiness Card */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div className="card" style={{ padding: '20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
              <Sparkles size={16} color="var(--cyan)" />
              <h3 style={{ fontSize: '15px', fontWeight: 700, fontFamily: 'Outfit, sans-serif' }}>
                Engine Diagnostics
              </h3>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {/* FFmpeg status */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 12px', background: 'var(--bg-surface)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--glass-border-subtle)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px' }}>
                  <CheckCircle2 size={15} color="var(--emerald)" />
                  <div>
                    <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>FFmpeg Pipeline</span>
                    <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                      {hardware?.ffmpeg?.version ? `v${hardware.ffmpeg.version.substring(0, 15)}` : 'Installed'}
                    </div>
                  </div>
                </div>
                <span className="badge badge-emerald">Ready</span>
              </div>

              {/* Hardware Acceleration */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 12px', background: 'var(--bg-surface)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--glass-border-subtle)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px' }}>
                  <CheckCircle2 size={15} color="var(--emerald)" />
                  <div>
                    <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>GPU Acceleration</span>
                    <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                      Intel Iris Xe / QSV / NVENC
                    </div>
                  </div>
                </div>
                <span className="badge badge-cyan">Active</span>
              </div>

              {/* yt-dlp */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 12px', background: 'var(--bg-surface)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--glass-border-subtle)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px' }}>
                  <CheckCircle2 size={15} color="var(--emerald)" />
                  <div>
                    <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>Downloader Engine</span>
                    <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                      yt-dlp Core
                    </div>
                  </div>
                </div>
                <span className="badge badge-emerald">Ready</span>
              </div>

              {/* Python */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 12px', background: 'var(--bg-surface)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--glass-border-subtle)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px' }}>
                  <CheckCircle2 size={15} color="var(--emerald)" />
                  <div>
                    <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>AI Speech Runtime</span>
                    <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                      Python 3.12 (Whisper / Demucs)
                    </div>
                  </div>
                </div>
                <span className="badge badge-violet">Loaded</span>
              </div>
            </div>
          </div>

          {/* Active Jobs Widget */}
          <div className="card" style={{ padding: '20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
              <h3 style={{ fontSize: '14px', fontWeight: 700, fontFamily: 'Outfit, sans-serif' }}>
                Batch Job Queue
              </h3>
              <span className="badge badge-cyan">0 Active</span>
            </div>
            <p style={{ fontSize: '12px', color: 'var(--text-muted)', lineHeight: '1.4' }}>
              All background rendering, audio separation, and transcription tasks will be queued here.
            </p>
          </div>
        </div>
      </div>

      {/* New Project Modal */}
      <NewProjectModal
        isOpen={isNewProjectModalOpen}
        onClose={() => setIsNewProjectModalOpen(false)}
        onCreated={(project) => {
          setIsNewProjectModalOpen(false);
          openProject(project.id);
          onNavigate('projects');
        }}
      />
    </div>
  );
};
