import React, { useState } from 'react';
import {
  DownloadCloud,
  Search,
  Layers,
  Play,
  Pause,
  RotateCcw,
  X,
  Trash2,
  FolderOpen,
  Sparkles,
  Zap,
  Globe,
  CheckCircle2,
  AlertTriangle,
  Clock,
} from 'lucide-react';
import { useDownloader } from '../../context/DownloaderContext';
import { useSettings } from '../../context/SettingsContext';
import { formatBytes, formatDuration } from '../../utils/formatters';
import { FormatModal } from './FormatModal';
import { BulkImportModal } from './BulkImportModal';
import { PlatformType } from '../../types/downloader';

export const DownloaderView: React.FC = () => {
  const {
    queue,
    analyzedMedia,
    isAnalyzing,
    error,
    analyzeUrl,
    clearAnalyzed,
    addJob,
    addBulkJobs,
    pauseJob,
    resumeJob,
    cancelJob,
    retryJob,
    clearCompleted,
    detectPlatform,
  } = useDownloader();

  const { settings, saveSettings } = useSettings();

  const [inputUrl, setInputUrl] = useState('');
  const [isBulkModalOpen, setIsBulkModalOpen] = useState(false);

  const detectedPlatform = detectPlatform(inputUrl);

  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputUrl.trim()) return;
    await analyzeUrl(inputUrl.trim());
  };

  const handleFormatConfirm = async (options: {
    formatId: string;
    resolution: string;
    audioOnly: boolean;
    includeSubtitles: boolean;
    includeThumbnail: boolean;
  }) => {
    if (analyzedMedia) {
      await addJob({
        url: analyzedMedia.url,
        platform: analyzedMedia.platform,
        title: analyzedMedia.title,
        uploader: analyzedMedia.uploader,
        thumbnailUrl: analyzedMedia.thumbnailUrl,
        selectedFormatId: options.formatId,
        selectedResolution: options.resolution,
        audioOnly: options.audioOnly,
        includeSubtitles: options.includeSubtitles,
        includeThumbnail: options.includeThumbnail,
      });
      setInputUrl('');
      clearAnalyzed();
    }
  };

  const handleBulkImport = async (urls: string[]) => {
    await addBulkJobs(urls);
  };

  // Compute aggregate speed
  const totalSpeed = queue
    .filter((j) => j.status === 'downloading')
    .reduce((acc, j) => acc + (j.speedBytesPerSec || 0), 0);

  const activeDownloadsCount = queue.filter((j) => j.status === 'downloading').length;
  const completedCount = queue.filter((j) => j.status === 'completed').length;

  const getPlatformBadge = (platform: PlatformType) => {
    const colors: Record<string, string> = {
      youtube: '#ff0000',
      tiktok: '#00f2fe',
      facebook: '#1877f2',
      twitter: '#1da1f2',
      bilibili: '#00a1d6',
      instagram: '#e1306c',
      vimeo: '#1ab7ea',
      twitch: '#9146ff',
      custom: 'var(--cyan)',
    };
    const c = colors[platform] || 'var(--cyan)';
    return (
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '4px',
          fontSize: '10px',
          fontWeight: 700,
          textTransform: 'uppercase',
          padding: '2px 8px',
          borderRadius: '4px',
          background: `${c}1a`,
          color: c,
          border: `1px solid ${c}40`,
        }}
      >
        {platform}
      </span>
    );
  };

  return (
    <div className="downloader-container" style={{ display: 'flex', flexDirection: 'column', gap: '22px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ fontSize: '26px', fontWeight: 700, fontFamily: 'Outfit, sans-serif', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <DownloadCloud size={26} color="var(--cyan)" />
            <span>Multi-Platform Media Downloader</span>
            <span className="badge badge-cyan">Phase 2 Pro</span>
          </h1>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px' }}>
            Download 8K/4K videos, audio streams, multi-language captions, and thumbnails from YouTube, TikTok, Facebook, and more.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button className="btn btn-secondary" onClick={() => setIsBulkModalOpen(true)}>
            <Layers size={15} />
            <span>Bulk URL Import</span>
          </button>
          <button className="btn btn-ghost" onClick={clearCompleted} title="Clear completed jobs">
            <Trash2 size={15} />
            <span>Clear Completed</span>
          </button>
        </div>
      </div>

      {/* URL Input Bar */}
      <div className="card" style={{ padding: '20px' }}>
        <form onSubmit={handleAnalyze} style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <div style={{ position: 'relative', flex: 1, display: 'flex', alignItems: 'center' }}>
            <Globe
              size={18}
              style={{ position: 'absolute', left: '14px', color: 'var(--text-muted)' }}
            />
            <input
              type="text"
              className="input-field"
              placeholder="Paste media link here (YouTube, TikTok, Facebook, Twitter, Bilibili, Vimeo, etc.)..."
              value={inputUrl}
              onChange={(e) => setInputUrl(e.target.value)}
              style={{ width: '100%', paddingLeft: '42px', paddingRight: '120px', height: '46px', fontSize: '14px' }}
            />
            {inputUrl && (
              <div style={{ position: 'absolute', right: '12px' }}>
                {getPlatformBadge(detectedPlatform)}
              </div>
            )}
          </div>

          <button
            type="submit"
            className="btn btn-primary btn-lg"
            disabled={!inputUrl.trim() || isAnalyzing}
            style={{ height: '46px' }}
          >
            <Sparkles size={16} />
            <span>{isAnalyzing ? 'Inspecting Streams...' : 'Analyze Media'}</span>
          </button>
        </form>

        {error && (
          <div style={{ marginTop: '12px', padding: '10px 14px', borderRadius: '6px', background: 'var(--rose-dim)', border: '1px solid rgba(244, 63, 94, 0.3)', color: '#fda4af', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <AlertTriangle size={15} color="var(--rose)" />
            <span>{error}</span>
          </div>
        )}
      </div>

      {/* Real-time Telemetry & Queue Stats Banner */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: '14px',
          background: 'var(--bg-surface)',
          padding: '16px',
          borderRadius: 'var(--radius-lg)',
          border: '1px solid var(--glass-border)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ width: 40, height: 40, borderRadius: '10px', background: 'rgba(0, 240, 255, 0.1)', color: 'var(--cyan)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Zap size={20} />
          </div>
          <div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>
              Transfer Speed
            </div>
            <div style={{ fontSize: '18px', fontWeight: 700, fontFamily: 'Outfit, sans-serif', color: 'var(--text-primary)' }}>
              {totalSpeed > 0 ? `${formatBytes(totalSpeed)}/s` : '0 B/s'}
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ width: 40, height: 40, borderRadius: '10px', background: 'rgba(139, 92, 246, 0.12)', color: '#c084fc', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <DownloadCloud size={20} />
          </div>
          <div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>
              Active Jobs
            </div>
            <div style={{ fontSize: '18px', fontWeight: 700, fontFamily: 'Outfit, sans-serif', color: 'var(--text-primary)' }}>
              {activeDownloadsCount} Running
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ width: 40, height: 40, borderRadius: '10px', background: 'rgba(16, 185, 129, 0.12)', color: 'var(--emerald)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <CheckCircle2 size={20} />
          </div>
          <div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>
              Completed
            </div>
            <div style={{ fontSize: '18px', fontWeight: 700, fontFamily: 'Outfit, sans-serif', color: 'var(--text-primary)' }}>
              {completedCount} Saved
            </div>
          </div>
        </div>

        {/* Worker Threads Slider */}
        <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: '4px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>
            <span>Concurrency</span>
            <span style={{ color: 'var(--cyan)' }}>{settings.downloader.maxConcurrentThreads} Workers</span>
          </div>
          <input
            type="range"
            min={1}
            max={32}
            value={settings.downloader.maxConcurrentThreads}
            onChange={(e) =>
              saveSettings({
                downloader: {
                  ...settings.downloader,
                  maxConcurrentThreads: Number(e.target.value),
                },
              })
            }
            style={{ width: '100%', accentColor: 'var(--cyan)' }}
          />
        </div>
      </div>

      {/* Download Queue View */}
      <div className="card" style={{ padding: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
          <h2 style={{ fontSize: '17px', fontWeight: 700, fontFamily: 'Outfit, sans-serif' }}>
            Download Pipeline Queue ({queue.length})
          </h2>
          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            Destination: {settings.downloader.downloadDirectory}
          </span>
        </div>

        {queue.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '50px 20px', color: 'var(--text-muted)' }}>
            <DownloadCloud size={44} style={{ margin: '0 auto 14px auto', opacity: 0.3 }} />
            <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '6px' }}>
              Download queue is empty
            </h3>
            <p style={{ fontSize: '13px' }}>
              Paste a video URL above or import a bulk list to begin high-speed media downloads.
            </p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {queue.map((job) => (
              <div
                key={job.id}
                style={{
                  background: 'var(--bg-surface)',
                  border: '1px solid var(--glass-border)',
                  borderRadius: 'var(--radius-md)',
                  padding: '16px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '12px',
                  transition: 'all var(--transition-fast)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    {job.thumbnailUrl ? (
                      <img
                        src={job.thumbnailUrl}
                        alt={job.title}
                        style={{ width: '56px', height: '36px', objectFit: 'cover', borderRadius: '4px' }}
                      />
                    ) : (
                      <div style={{ width: '56px', height: '36px', background: 'var(--bg-card)', borderRadius: '4px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
                        <DownloadCloud size={16} />
                      </div>
                    )}
                    <div>
                      <h4 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>
                        {job.title}
                      </h4>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', color: 'var(--text-muted)' }}>
                        <span>{job.uploader}</span>
                        <span>•</span>
                        {getPlatformBadge(job.platform)}
                        <span>•</span>
                        <span style={{ color: 'var(--text-cyan)' }}>{job.selectedResolution}</span>
                      </div>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {job.status === 'downloading' && (
                      <button className="btn btn-ghost btn-sm" onClick={() => pauseJob(job.id)} title="Pause">
                        <Pause size={14} />
                      </button>
                    )}
                    {job.status === 'paused' && (
                      <button className="btn btn-ghost btn-sm" onClick={() => resumeJob(job.id)} title="Resume">
                        <Play size={14} color="var(--emerald)" />
                      </button>
                    )}
                    {(job.status === 'failed' || job.status === 'cancelled') && (
                      <button className="btn btn-ghost btn-sm" onClick={() => retryJob(job.id)} title="Retry">
                        <RotateCcw size={14} color="var(--cyan)" />
                      </button>
                    )}
                    {job.status !== 'completed' && (
                      <button className="btn btn-ghost btn-sm" onClick={() => cancelJob(job.id)} style={{ color: 'var(--rose)' }} title="Cancel">
                        <X size={14} />
                      </button>
                    )}
                    {job.outputFilePath && (
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => window.electronAPI?.showItemInFolder?.(job.outputFilePath!)}
                        title="Show in File Explorer"
                      >
                        <FolderOpen size={14} />
                        <span>Show</span>
                      </button>
                    )}
                  </div>
                </div>

                {/* Progress Bar & Telemetry */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <div style={{ height: '6px', width: '100%', background: 'rgba(255, 255, 255, 0.08)', borderRadius: '3px', overflow: 'hidden' }}>
                    <div
                      style={{
                        height: '100%',
                        width: `${job.progressPercent}%`,
                        background:
                          job.status === 'completed'
                            ? 'var(--emerald)'
                            : job.status === 'failed'
                            ? 'var(--rose)'
                            : 'var(--gradient-brand)',
                        transition: 'width 0.3s ease',
                      }}
                    />
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'JetBrains Mono, monospace' }}>
                    <div style={{ display: 'flex', gap: '12px' }}>
                      <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>
                        {job.progressPercent.toFixed(1)}%
                      </span>
                      {job.speedBytesPerSec > 0 && (
                        <span style={{ color: 'var(--cyan)' }}>
                          {formatBytes(job.speedBytesPerSec)}/s
                        </span>
                      )}
                      {job.etaSeconds > 0 && (
                        <span>ETA: {formatDuration(job.etaSeconds)}</span>
                      )}
                    </div>

                    <div>
                      <span style={{ textTransform: 'capitalize', fontWeight: 600, color: job.status === 'completed' ? 'var(--emerald)' : job.status === 'failed' ? 'var(--rose)' : 'var(--text-secondary)' }}>
                        {job.status}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Format Inspection Modal */}
      <FormatModal
        isOpen={!!analyzedMedia}
        onClose={clearAnalyzed}
        mediaInfo={analyzedMedia}
        onConfirm={handleFormatConfirm}
      />

      {/* Bulk Import Modal */}
      <BulkImportModal
        isOpen={isBulkModalOpen}
        onClose={() => setIsBulkModalOpen(false)}
        onImport={handleBulkImport}
      />
    </div>
  );
};
