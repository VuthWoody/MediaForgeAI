import React, { useState } from 'react';
import { DownloadCloud, Check, Sparkles, Film, Music, Globe, Image } from 'lucide-react';
import { Modal } from '../common/Modal';
import { MediaUrlInfo, MediaFormatOption } from '../../types/downloader';
import { formatBytes, formatDuration } from '../../utils/formatters';

interface FormatModalProps {
  isOpen: boolean;
  onClose: () => void;
  mediaInfo: MediaUrlInfo | null;
  onConfirm: (options: {
    formatId: string;
    resolution: string;
    audioOnly: boolean;
    includeSubtitles: boolean;
    includeThumbnail: boolean;
  }) => void;
}

export const FormatModal: React.FC<FormatModalProps> = ({
  isOpen,
  onClose,
  mediaInfo,
  onConfirm,
}) => {
  const [selectedFormatId, setSelectedFormatId] = useState<string>('best');
  const [audioOnly, setAudioOnly] = useState(false);
  const [includeSubtitles, setIncludeSubtitles] = useState(true);
  const [includeThumbnail, setIncludeThumbnail] = useState(true);

  if (!mediaInfo) return null;

  const handleDownload = () => {
    let resLabel = 'Best Available';
    const found = mediaInfo.formats.find((f) => f.formatId === selectedFormatId);
    if (found) resLabel = found.resolution;
    if (audioOnly) resLabel = 'Audio (MP3)';

    onConfirm({
      formatId: selectedFormatId,
      resolution: resLabel,
      audioOnly,
      includeSubtitles,
      includeThumbnail,
    });
    onClose();
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Select Stream Quality & Options"
      subtitle={`Source: ${mediaInfo.uploader} • Platform: ${mediaInfo.platform.toUpperCase()}`}
      maxWidth="680px"
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary" onClick={handleDownload}>
            <DownloadCloud size={16} />
            <span>Download to Library</span>
          </button>
        </>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {/* Media Preview Card */}
        <div
          style={{
            display: 'flex',
            gap: '16px',
            background: 'var(--bg-deepest)',
            padding: '14px',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--glass-border)',
          }}
        >
          {mediaInfo.thumbnailUrl ? (
            <img
              src={mediaInfo.thumbnailUrl}
              alt={mediaInfo.title}
              style={{ width: '130px', height: '80px', objectFit: 'cover', borderRadius: '6px' }}
            />
          ) : (
            <div
              style={{
                width: '130px',
                height: '80px',
                background: 'var(--bg-surface)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                borderRadius: '6px',
                color: 'var(--text-muted)',
              }}
            >
              <Film size={24} />
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: '4px' }}>
            <h3 style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)', lineHeight: '1.3' }}>
              {mediaInfo.title}
            </h3>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', color: 'var(--text-muted)' }}>
              <span>Duration: {formatDuration(mediaInfo.durationSeconds)}</span>
              <span>•</span>
              <span style={{ color: 'var(--text-cyan)', textTransform: 'capitalize' }}>{mediaInfo.platform}</span>
            </div>
          </div>
        </div>

        {/* Mode Selector: Video vs Audio Only */}
        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            type="button"
            className={`btn btn-sm ${!audioOnly ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setAudioOnly(false)}
            style={{ flex: 1, padding: '10px' }}
          >
            <Film size={15} />
            <span>Video & Audio Stream</span>
          </button>
          <button
            type="button"
            className={`btn btn-sm ${audioOnly ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setAudioOnly(true)}
            style={{ flex: 1, padding: '10px' }}
          >
            <Music size={15} />
            <span>Audio Extraction (MP3)</span>
          </button>
        </div>

        {/* Video Resolutions List */}
        {!audioOnly && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <label className="input-label">Available Streams & Resolutions</label>
            <div
              style={{
                maxHeight: '180px',
                overflowY: 'auto',
                display: 'flex',
                flexDirection: 'column',
                gap: '6px',
                background: 'var(--bg-surface)',
                padding: '8px',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--glass-border)',
              }}
            >
              <div
                onClick={() => setSelectedFormatId('best')}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '10px 14px',
                  borderRadius: 'var(--radius-sm)',
                  background: selectedFormatId === 'best' ? 'rgba(0, 240, 255, 0.12)' : 'transparent',
                  border: selectedFormatId === 'best' ? '1px solid rgba(0, 240, 255, 0.3)' : '1px solid transparent',
                  cursor: 'pointer',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <Sparkles size={16} color="var(--cyan)" />
                  <div>
                    <span style={{ fontWeight: 600, fontSize: '13px', color: 'var(--text-primary)' }}>
                      Best Available Quality (Auto)
                    </span>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                      Highest available resolution & audio bitrate
                    </div>
                  </div>
                </div>
                {selectedFormatId === 'best' && <Check size={16} color="var(--cyan)" />}
              </div>

              {mediaInfo.formats
                .filter((f) => f.isVideo && f.height > 0)
                .slice(0, 8)
                .map((f) => {
                  const isSelected = selectedFormatId === f.formatId;
                  return (
                    <div
                      key={f.formatId}
                      onClick={() => setSelectedFormatId(f.formatId)}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '8px 14px',
                        borderRadius: 'var(--radius-sm)',
                        background: isSelected ? 'rgba(0, 240, 255, 0.12)' : 'transparent',
                        border: isSelected ? '1px solid rgba(0, 240, 255, 0.3)' : '1px solid transparent',
                        cursor: 'pointer',
                      }}
                    >
                      <div>
                        <span style={{ fontWeight: 600, fontSize: '13px', color: 'var(--text-primary)' }}>
                          {f.resolution}
                        </span>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                          {f.extension.toUpperCase()} • Codec: {f.vcodec} {f.fps ? `• ${f.fps}fps` : ''}
                        </div>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        {f.filesizeApproxBytes && (
                          <span style={{ fontSize: '11px', color: 'var(--text-secondary)', fontFamily: 'JetBrains Mono' }}>
                            ~{formatBytes(f.filesizeApproxBytes)}
                          </span>
                        )}
                        {isSelected && <Check size={16} color="var(--cyan)" />}
                      </div>
                    </div>
                  );
                })}
            </div>
          </div>
        )}

        {/* Auxiliary Options */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', background: 'var(--bg-surface)', padding: '12px 16px', borderRadius: 'var(--radius-md)', border: '1px solid var(--glass-border)' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', color: 'var(--text-secondary)', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={includeSubtitles}
              onChange={(e) => setIncludeSubtitles(e.target.checked)}
              style={{ accentColor: 'var(--cyan)' }}
            />
            <span>Download Subtitles ({mediaInfo.subtitles.length} tracks available)</span>
          </label>

          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', color: 'var(--text-secondary)', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={includeThumbnail}
              onChange={(e) => setIncludeThumbnail(e.target.checked)}
              style={{ accentColor: 'var(--cyan)' }}
            />
            <span>Save Highest-Resolution Thumbnail</span>
          </label>
        </div>
      </div>
    </Modal>
  );
};
