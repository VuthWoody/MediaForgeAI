import React, { useMemo, useEffect, useRef, useState, useCallback } from 'react';
import { useStudio, formatSMPTE } from '../../context/StudioContext';
import { useProject } from '../../context/ProjectContext';
import { toMediaUrl } from '../../utils/mediaUrl';
import { ASPECT_RATIO_PRESETS } from '../../utils/aspectRatio';

interface VideoPlayerProps {
  sourcePath?: string;
  onOpenSelectMedia?: () => void;
}

export const VideoPlayer: React.FC<VideoPlayerProps> = ({ sourcePath, onOpenSelectMedia }) => {
  const {
    playback,
    videoRef,
    togglePlay,
    seek,
    stepFrame,
    setPlaybackRate,
    setVolume,
    toggleMute,
    updateCurrentTime,
    updateDuration,
    captureSnapshot,
    aspectRatio,
    setAspectRatio,
    fitMode,
    setFitMode,
    showSafeZones,
    setShowSafeZones,
    videoNaturalSize,
    setVideoNaturalSize,
    setIsPlaying,
    toggleLoop,
    handleEnded,
    voiceMode,
    setVoiceMode,
    duckingLevel,
  } = useStudio();

  const { activeProject } = useProject();
  const playerContainerRef = useRef<HTMLDivElement | null>(null);
  const dubbedAudioRef = useRef<HTMLAudioElement | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [snapshotToast, setSnapshotToast] = useState<string | null>(null);
  const [isScrubbing, setIsScrubbing] = useState(false);
  const [mediaError, setMediaError] = useState<string | null>(null);

  // Construct bulletproof base64url media://play/ URL safe against spaces, hashtags (#), and emojis
  const mediaSrc = useMemo(() => {
    return toMediaUrl(sourcePath || '');
  }, [sourcePath]);

  // Construct dubbed audio track URL if available with revision cache-busting
  const dubbedAudioSrc = useMemo(() => {
    const p = activeProject?.stems?.dubbedVocalsPath;
    const rev = activeProject?.stems?.dubbedAudioRevision || 0;
    return p ? `${toMediaUrl(p)}?rev=${rev}` : '';
  }, [activeProject?.stems?.dubbedVocalsPath, activeProject?.stems?.dubbedAudioRevision]);

  // Reset error when source path changes
  useEffect(() => {
    setMediaError(null);
  }, [sourcePath]);

  // Find active speech segment at current time for live subtitle rendering and voice auto-ducking
  const activeSegment = useMemo(() => {
    if (!activeProject?.segments || activeProject.segments.length === 0) return null;
    const t = playback.currentTime;
    return activeProject.segments.find(s => t >= s.start && t <= s.end) || null;
  }, [activeProject?.segments, playback.currentTime]);

  // Synchronize volumes for original video and dubbed audio according to voiceMode
  useEffect(() => {
    if (!videoRef.current) return;

    if (playback.isMuted) {
      videoRef.current.volume = 0;
      return;
    }

    // If there is no dubbed audio track, normal video volume applies
    if (!dubbedAudioSrc) {
      const origVol = activeProject?.stems?.vocalVolume ?? 1.0;
      videoRef.current.volume = Math.min(1.0, Math.max(0, playback.volume * origVol));
      return;
    }

    // Dubbed audio track exists: apply voiceMode mixing rules
    if (voiceMode === 'clean-dub') {
      // Clean dub: completely mute original video to prevent duplicate / echoing voices
      videoRef.current.volume = 0;
    } else if (voiceMode === 'voice-over') {
      // Voice-over with auto-ducking:
      // When dialogue is actively speaking, duck original audio to duckingLevel (e.g. 15%).
      // When in pauses/silence, restore original audio smoothly.
      const targetDucking = activeSegment ? duckingLevel : 0.95;
      const origVol = activeProject?.stems?.vocalVolume ?? 1.0;
      videoRef.current.volume = Math.min(1.0, Math.max(0, playback.volume * origVol * targetDucking));
    } else if (voiceMode === 'custom-mix') {
      // Custom mix from stem sliders
      const origVol = activeProject?.stems?.vocalVolume ?? 0.5;
      videoRef.current.volume = Math.min(1.0, Math.max(0, playback.volume * origVol));
    } else if (voiceMode === 'original-only') {
      // Original video only
      const origVol = activeProject?.stems?.vocalVolume ?? 1.0;
      videoRef.current.volume = Math.min(1.0, Math.max(0, playback.volume * origVol));
    }
  }, [
    playback.volume,
    playback.isMuted,
    dubbedAudioSrc,
    voiceMode,
    duckingLevel,
    activeSegment,
    activeProject?.stems?.vocalVolume,
  ]);

  useEffect(() => {
    if (!dubbedAudioRef.current) return;
    dubbedAudioRef.current.playbackRate = playback.playbackRate;

    if (playback.isMuted || !dubbedAudioSrc) {
      dubbedAudioRef.current.volume = 0;
      return;
    }

    if (voiceMode === 'original-only') {
      dubbedAudioRef.current.volume = 0;
    } else if (voiceMode === 'custom-mix') {
      const dubbedVol = activeProject?.stems?.dubbedVolume ?? 1.0;
      dubbedAudioRef.current.volume = Math.min(1.0, Math.max(0, playback.volume * (dubbedVol / 1.5)));
    } else {
      // clean-dub or voice-over: crisp full clarity dubbed dialogue
      const dubbedVol = activeProject?.stems?.dubbedVolume ?? 1.2;
      dubbedAudioRef.current.volume = Math.min(1.0, Math.max(0, playback.volume * (dubbedVol / 1.2)));
    }
  }, [
    playback.playbackRate,
    playback.volume,
    playback.isMuted,
    dubbedAudioSrc,
    voiceMode,
    activeProject?.stems?.dubbedVolume,
  ]);

  // Synchronize dubbed audio when source updates or mounts
  useEffect(() => {
    if (dubbedAudioRef.current) {
      dubbedAudioRef.current.load();
      if (videoRef.current) {
        dubbedAudioRef.current.currentTime = videoRef.current.currentTime;
        if (!videoRef.current.paused) {
          dubbedAudioRef.current.play().catch(() => {});
        }
      }
    }
  }, [dubbedAudioSrc]);

  // Determine active aspect ratio preset & numeric ratio
  const activePreset = useMemo(() => {
    return ASPECT_RATIO_PRESETS.find(p => p.id === aspectRatio) || ASPECT_RATIO_PRESETS[0];
  }, [aspectRatio]);

  const targetRatio = useMemo(() => {
    if (activePreset.ratio !== null) {
      return activePreset.ratio;
    }
    // For 'original': match native media width / height
    if (videoNaturalSize.width > 0 && videoNaturalSize.height > 0) {
      return videoNaturalSize.width / videoNaturalSize.height;
    }
    return null;
  }, [activePreset, videoNaturalSize]);

  // Check whether playback is currently at the end of the video
  const isAtEnd = useMemo(() => {
    return (
      playback.duration > 0 &&
      playback.currentTime >= playback.duration - 0.1
    );
  }, [playback.duration, playback.currentTime]);

  // Viewport container ref & dimensions measured via ResizeObserver
  const stageContainerRef = useRef<HTMLDivElement | null>(null);
  const [containerDimensions, setContainerDimensions] = useState<{ width: number; height: number }>({
    width: 0,
    height: 0,
  });

  useEffect(() => {
    const el = stageContainerRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        if (width > 0 && height > 0) {
          setContainerDimensions({ width, height });
        }
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Compute pixel-perfect stage box dimensions that guarantee exact aspect ratio without stretching
  const stageBoxStyle = useMemo<React.CSSProperties>(() => {
    const cw = containerDimensions.width;
    const ch = containerDimensions.height;

    if (!targetRatio || cw <= 0 || ch <= 0) {
      return {
        width: '100%',
        height: '100%',
        maxWidth: '100%',
        maxHeight: '100%',
      };
    }

    const containerRatio = cw / ch;
    if (targetRatio < containerRatio) {
      // Narrower than container (e.g. 9:16 vertical in widescreen viewport):
      // Height matches container height, width scales to maintain exact ratio
      const h = ch;
      const w = Math.round(ch * targetRatio);
      return {
        width: `${w}px`,
        height: `${h}px`,
        maxWidth: '100%',
        maxHeight: '100%',
      };
    } else {
      // Wider than container (e.g. 16:9 or 21:9 in narrow/square viewport):
      // Width matches container width, height scales to maintain exact ratio
      const w = cw;
      const h = Math.round(cw / targetRatio);
      return {
        width: `${w}px`,
        height: `${h}px`,
        maxWidth: '100%',
        maxHeight: '100%',
      };
    }
  }, [containerDimensions, targetRatio]);

  // Keyboard shortcut handler
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (target && ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)) return;

      if (e.code === 'Space') {
        e.preventDefault();
        togglePlay();
      } else if (e.code === 'ArrowLeft' || e.key === 'j') {
        e.preventDefault();
        if (e.shiftKey) {
          seek(playback.currentTime - 5);
        } else {
          stepFrame(-1);
        }
      } else if (e.code === 'ArrowRight' || e.key === 'l') {
        e.preventDefault();
        if (e.shiftKey) {
          seek(playback.currentTime + 5);
        } else {
          stepFrame(1);
        }
      } else if (e.key === 'm') {
        toggleMute();
      } else if (e.key === 'f') {
        handleToggleFullscreen();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [togglePlay, stepFrame, seek, toggleMute, playback.currentTime]);

  const handleToggleFullscreen = () => {
    if (!playerContainerRef.current) return;
    if (!document.fullscreenElement) {
      playerContainerRef.current.requestFullscreen().then(() => setIsFullscreen(true)).catch(console.warn);
    } else {
      document.exitFullscreen().then(() => setIsFullscreen(false)).catch(console.warn);
    }
  };

  const handleSnapshot = async () => {
    const res = await captureSnapshot();
    if (res?.success) {
      setSnapshotToast('Frame snapshot captured!');
      setTimeout(() => setSnapshotToast(null), 2500);
    }
  };

  // Subtitle styling rules from project
  const subStyle = activeProject?.subtitleStyle || {
    fontFamily: 'Inter',
    fontSize: 22,
    primaryColor: '#ffffff',
    outlineColor: '#000000',
    outlineWidth: 3,
    position: 'bottom',
    bold: true,
  };

  return (
    <div
      ref={playerContainerRef}
      className="studio-video-viewport"
      style={{
        position: 'relative',
        width: '100%',
        height: '100%',
        minHeight: 0,
        backgroundColor: '#040508',
        borderRadius: '10px',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        border: '1px solid var(--border-subtle)',
      }}
    >
      {/* 1. TOP ASPECT RATIO & DISPLAY CONTROLS BAR */}
      <div
        className="aspect-ratio-controls-bar"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '6px 12px',
          backgroundColor: '#080a11',
          borderBottom: '1px solid var(--border-subtle)',
          fontSize: '11px',
          flexShrink: 0,
          gap: '10px',
          zIndex: 6,
          flexWrap: 'nowrap',
          overflowX: 'auto',
        }}
      >
        {/* Aspect Ratio Selector Pills */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px', flexShrink: 0 }}>
          <span style={{ color: 'var(--text-muted)', marginRight: '2px', fontWeight: 600, fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            Ratio:
          </span>
          {ASPECT_RATIO_PRESETS.map((preset) => {
            const isSelected = aspectRatio === preset.id;
            return (
              <button
                key={preset.id}
                onClick={() => setAspectRatio(preset.id)}
                title={`${preset.platform} — ${preset.description}`}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  padding: '3px 8px',
                  borderRadius: '4px',
                  border: isSelected ? '1px solid var(--accent-cyan)' : '1px solid rgba(255,255,255,0.08)',
                  backgroundColor: isSelected ? 'rgba(0, 240, 255, 0.16)' : 'rgba(255,255,255,0.02)',
                  color: isSelected ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                  fontSize: '11px',
                  fontWeight: isSelected ? 600 : 400,
                  cursor: 'pointer',
                  whiteSpace: 'nowrap',
                  transition: 'all 0.15s ease',
                }}
              >
                <span style={{ fontSize: '12px' }}>{preset.icon}</span>
                <span>{preset.label}</span>
              </button>
            );
          })}
        </div>

        {/* Fit Mode, Safe Zones & Resolution Readout */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
          {/* Fit Mode Selector (Contain / Cover / Blur Background) */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              backgroundColor: '#05070d',
              borderRadius: '4px',
              padding: '2px',
              border: '1px solid var(--border-subtle)',
            }}
          >
            {(['contain', 'cover', 'blur-fill'] as const).map((mode) => {
              const isSelected = fitMode === mode;
              const label = mode === 'contain' ? 'Fit' : mode === 'cover' ? 'Fill' : 'Blur BG';
              return (
                <button
                  key={mode}
                  onClick={() => setFitMode(mode)}
                  title={
                    mode === 'contain'
                      ? 'Fit: Show entire video without distortion (pillarbox/letterbox)'
                      : mode === 'cover'
                      ? 'Fill: Crop to fill selected aspect frame'
                      : 'Blur BG: Fill letterbox borders with ambient blurred background'
                  }
                  style={{
                    padding: '2px 7px',
                    borderRadius: '3px',
                    border: 'none',
                    backgroundColor: isSelected ? 'var(--accent-cyan)' : 'transparent',
                    color: isSelected ? '#040508' : 'var(--text-secondary)',
                    fontSize: '10px',
                    fontWeight: isSelected ? 700 : 500,
                    cursor: 'pointer',
                  }}
                >
                  {label}
                </button>
              );
            })}
          </div>

          {/* Safe Zones Guide Toggle for 9:16 (TikTok, Shorts, Reels) */}
          {aspectRatio === '9:16' && (
            <button
              onClick={() => setShowSafeZones(!showSafeZones)}
              title="Toggle TikTok / YouTube Shorts / Reels UI button overlay guides"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                padding: '3px 8px',
                borderRadius: '4px',
                border: showSafeZones ? '1px solid var(--accent-purple)' : '1px solid rgba(255,255,255,0.1)',
                backgroundColor: showSafeZones ? 'rgba(139, 92, 246, 0.22)' : 'transparent',
                color: showSafeZones ? 'var(--accent-purple)' : 'var(--text-muted)',
                fontSize: '10px',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              <span>🛡️ Safe Zones</span>
            </button>
          )}

          {/* Source Resolution Badge */}
          {videoNaturalSize.width > 0 && (
            <span
              style={{
                fontSize: '10px',
                color: 'var(--accent-cyan)',
                backgroundColor: 'rgba(0, 240, 255, 0.08)',
                border: '1px solid rgba(0, 240, 255, 0.2)',
                padding: '2px 6px',
                borderRadius: '4px',
                fontFamily: 'monospace',
              }}
              title="Native media dimensions"
            >
              {videoNaturalSize.width}×{videoNaturalSize.height}
            </span>
          )}
        </div>
      </div>

      {/* 2. MAIN VIDEO DISPLAY STAGE */}
      <div
        ref={stageContainerRef}
        style={{
          position: 'relative',
          flex: 1,
          minHeight: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: '#040508',
          overflow: 'hidden',
          padding: '8px',
          cursor: 'pointer',
        }}
        onClick={togglePlay}
      >
        {mediaSrc ? (
          /* Aspect Ratio Canvas Stage */
          <div
            className="aspect-ratio-canvas-stage"
            style={{
              position: 'relative',
              ...stageBoxStyle,
              backgroundColor: '#000000',
              boxShadow: '0 8px 32px rgba(0, 0, 0, 0.8)',
              borderRadius: aspectRatio === '9:16' ? '8px' : '4px',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              overflow: 'hidden',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'width 0.2s cubic-bezier(0.4, 0, 0.2, 1), height 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
            }}
          >
            {/* Ambient Blurred Video Background for 'blur-fill' mode */}
            {fitMode === 'blur-fill' && (
              <video
                src={mediaSrc}
                aria-hidden="true"
                muted
                style={{
                  position: 'absolute',
                  inset: 0,
                  width: '100%',
                  height: '100%',
                  objectFit: 'cover',
                  filter: 'blur(28px) brightness(0.55)',
                  transform: 'scale(1.2)',
                  pointerEvents: 'none',
                }}
              />
            )}

            {/* Foreground Main Video */}
            <video
              ref={videoRef}
              src={mediaSrc}
              playsInline
              onTimeUpdate={(e) => {
                if (!isScrubbing) {
                  const cur = e.currentTarget.currentTime;
                  updateCurrentTime(cur);
                  if (dubbedAudioRef.current && dubbedAudioSrc && !dubbedAudioRef.current.paused) {
                    const drift = Math.abs(dubbedAudioRef.current.currentTime - cur);
                    if (drift > 0.15) {
                      dubbedAudioRef.current.currentTime = cur;
                    }
                  }
                }
              }}
              onLoadedMetadata={(e) => {
                updateDuration(e.currentTarget.duration);
                const nw = e.currentTarget.videoWidth;
                const nh = e.currentTarget.videoHeight;
                if (nw && nh) {
                  setVideoNaturalSize({ width: nw, height: nh });
                  if (aspectRatio === 'original' && nh > nw) {
                    setAspectRatio('9:16');
                  }
                }
                setMediaError(null);
              }}
              onPlay={() => {
                setIsPlaying(true);
                if (dubbedAudioRef.current && dubbedAudioSrc) {
                  dubbedAudioRef.current.currentTime = videoRef.current?.currentTime || 0;
                  dubbedAudioRef.current.play().catch(() => {});
                }
              }}
              onPause={() => {
                setIsPlaying(false);
                if (dubbedAudioRef.current) {
                  dubbedAudioRef.current.pause();
                }
              }}
              onSeeking={(e) => {
                if (dubbedAudioRef.current && dubbedAudioSrc) {
                  dubbedAudioRef.current.currentTime = e.currentTarget.currentTime;
                }
              }}
              onSeeked={(e) => {
                if (dubbedAudioRef.current && dubbedAudioSrc) {
                  dubbedAudioRef.current.currentTime = e.currentTarget.currentTime;
                }
              }}
              onRateChange={(e) => {
                if (dubbedAudioRef.current) {
                  dubbedAudioRef.current.playbackRate = e.currentTarget.playbackRate;
                }
              }}
              onEnded={() => {
                handleEnded();
                if (dubbedAudioRef.current) {
                  dubbedAudioRef.current.pause();
                  dubbedAudioRef.current.currentTime = 0;
                }
              }}
              onError={(e) => {
                const err = e.currentTarget.error;
                const msg = err
                  ? err.code === 4
                    ? 'File not found on disk or format cannot be demuxed'
                    : `Playback error (Code ${err.code}: ${err.message || 'unknown'})`
                  : 'Failed to load media';
                console.warn('Video element error:', msg);
                setMediaError(msg);
              }}
              style={{
                position: 'relative',
                width: '100%',
                height: '100%',
                objectFit: fitMode === 'cover' ? 'cover' : 'contain',
                display: 'block',
                zIndex: 2,
              }}
            />

            {/* Synced Dubbed Vocals Audio Track */}
            {dubbedAudioSrc && (
              <audio
                key={dubbedAudioSrc}
                ref={dubbedAudioRef}
                src={dubbedAudioSrc}
                preload="auto"
                style={{ display: 'none' }}
              />
            )}

            {/* Safe Zones Guide Overlay for 9:16 (Shorts, TikTok, Reels) */}
            {aspectRatio === '9:16' && showSafeZones && (
              <div
                className="safe-zones-overlay"
                style={{
                  position: 'absolute',
                  inset: 0,
                  pointerEvents: 'none',
                  zIndex: 8,
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  border: '1px dashed rgba(0, 240, 255, 0.4)',
                }}
              >
                {/* Top Safe Margin (Header & Search) */}
                <div
                  style={{
                    height: '12%',
                    backgroundColor: 'rgba(255, 0, 80, 0.14)',
                    borderBottom: '1px dashed rgba(255, 0, 80, 0.4)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '10px',
                    color: 'rgba(255, 255, 255, 0.8)',
                    letterSpacing: '0.5px',
                  }}
                >
                  📱 Platform Header (Search / Live)
                </div>

                {/* Right Edge Action Buttons Area (Like, Comments, Share, Disc) */}
                <div
                  style={{
                    position: 'absolute',
                    right: 0,
                    top: '32%',
                    bottom: '22%',
                    width: '18%',
                    backgroundColor: 'rgba(255, 0, 80, 0.12)',
                    borderLeft: '1px dashed rgba(255, 0, 80, 0.4)',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'space-around',
                    fontSize: '10px',
                    color: 'rgba(255, 255, 255, 0.7)',
                  }}
                >
                  <span>❤️</span>
                  <span>💬</span>
                  <span>↗️</span>
                  <span>🎵</span>
                </div>

                {/* Bottom Safe Margin (Captions & Sound Title) */}
                <div
                  style={{
                    height: '22%',
                    backgroundColor: 'rgba(255, 0, 80, 0.14)',
                    borderTop: '1px dashed rgba(255, 0, 80, 0.4)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '10px',
                    color: 'rgba(255, 255, 255, 0.8)',
                    letterSpacing: '0.5px',
                  }}
                >
                  📝 Platform Captions & Sound Title Zone
                </div>
              </div>
            )}

            {/* Live Subtitle Overlay */}
            {activeSegment && (
              <div
                style={{
                  position: 'absolute',
                  bottom: subStyle.position === 'bottom' ? (aspectRatio === '9:16' && showSafeZones ? '24%' : '24px') : subStyle.position === 'top' ? '24px' : '50%',
                  top: subStyle.position === 'top' ? (aspectRatio === '9:16' && showSafeZones ? '14%' : '24px') : 'auto',
                  left: '6%',
                  right: aspectRatio === '9:16' && showSafeZones ? '22%' : '6%',
                  textAlign: 'center',
                  pointerEvents: 'none',
                  zIndex: 10,
                }}
              >
                <span
                  style={{
                    display: 'inline-block',
                    fontFamily: subStyle.fontFamily || 'Inter, sans-serif',
                    fontSize: `${subStyle.fontSize || 20}px`,
                    fontWeight: subStyle.bold ? 700 : 500,
                    color: subStyle.primaryColor || '#ffffff',
                    textShadow: `0 0 ${subStyle.outlineWidth || 3}px ${subStyle.outlineColor || '#000'}, 0 2px 4px rgba(0,0,0,0.8)`,
                    backgroundColor: 'rgba(0, 0, 0, 0.5)',
                    padding: '4px 12px',
                    borderRadius: '6px',
                    maxWidth: '92%',
                    lineHeight: 1.35,
                  }}
                >
                  {activeSegment.translatedText || activeSegment.originalText}
                </span>
              </div>
            )}

            {/* Error Recovery Overlay */}
            {mediaError && (
              <div
                style={{
                  position: 'absolute',
                  inset: 0,
                  backgroundColor: 'rgba(8, 10, 16, 0.94)',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  padding: '24px',
                  zIndex: 15,
                  textAlign: 'center',
                }}
                onClick={(e) => e.stopPropagation()}
              >
                <div style={{ fontSize: '44px', marginBottom: '12px' }}>⚠️</div>
                <h4 style={{ color: 'var(--status-error)', fontSize: '16px', fontWeight: 600, marginBottom: '6px' }}>
                  Unable to Play Media File
                </h4>
                <p style={{ color: 'var(--text-secondary)', fontSize: '13px', maxWidth: '420px', marginBottom: '8px', lineHeight: 1.4 }}>
                  {mediaError}
                </p>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'monospace', maxWidth: '460px', wordBreak: 'break-all', marginBottom: '18px' }}>
                  {sourcePath}
                </div>
                {onOpenSelectMedia && (
                  <button
                    className="btn btn-primary"
                    onClick={onOpenSelectMedia}
                    style={{ fontSize: '13px', padding: '8px 18px' }}
                  >
                    📁 Select a Valid Media File
                  </button>
                )}
              </div>
            )}
          </div>
        ) : (
          <div
            style={{
              textAlign: 'center',
              padding: '40px 20px',
              color: 'var(--text-muted)',
            }}
          >
            <div style={{ fontSize: '48px', marginBottom: '12px' }}>🎬</div>
            <h3 style={{ color: 'var(--text-primary)', marginBottom: '8px', fontSize: '18px' }}>
              No Source Media Loaded
            </h3>
            <p style={{ fontSize: '13px', maxWidth: '360px', margin: '0 auto 16px auto', color: 'var(--text-secondary)' }}>
              Attach a video file to this project to scrub frames, extract speech audio, and preview subtitles.
            </p>
            {onOpenSelectMedia && (
              <button
                className="btn btn-primary"
                onClick={(e) => {
                  e.stopPropagation();
                  onOpenSelectMedia();
                }}
                style={{ fontSize: '13px', padding: '8px 18px' }}
              >
                + Attach Media File
              </button>
            )}
          </div>
        )}

        {/* Snapshot Toast notification */}
        {snapshotToast && (
          <div
            style={{
              position: 'absolute',
              top: '16px',
              right: '16px',
              backgroundColor: 'rgba(0, 240, 255, 0.95)',
              color: '#05070a',
              padding: '6px 14px',
              borderRadius: '6px',
              fontSize: '12px',
              fontWeight: 600,
              boxShadow: '0 4px 12px rgba(0, 240, 255, 0.4)',
              zIndex: 20,
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <span>📸</span> {snapshotToast}
          </div>
        )}
      </div>

      {/* 2.5 AUDIO TRACK MODE SELECTOR BAR (Appears when dubbed audio track is present) */}
      {dubbedAudioSrc && (
        <div
          style={{
            width: '100%',
            backgroundColor: '#070a12',
            borderTop: '1px solid rgba(0, 240, 255, 0.25)',
            borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
            padding: '5px 16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexShrink: 0,
            zIndex: 10,
            gap: '8px',
            flexWrap: 'wrap',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--accent-cyan)', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <span>🎙️</span> Audio Track Mode:
            </span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              {[
                { id: 'clean-dub', label: '🎧 Clean Dub Only', desc: 'Mutes original video audio completely to eliminate duplicate voices/echo' },
                { id: 'voice-over', label: '🎙️ Voice-Over (Auto-Duck)', desc: 'Automatically ducks original audio during speech and restores during pauses' },
                { id: 'custom-mix', label: '🎚️ Custom Mix', desc: 'Mix tracks using the stem volume sliders in Inspector' },
                { id: 'original-only', label: '🔈 Original Only', desc: 'Plays only the original video audio' },
              ].map((m) => {
                const isActive = voiceMode === m.id;
                return (
                  <button
                    key={m.id}
                    onClick={() => setVoiceMode(m.id as any)}
                    title={m.desc}
                    style={{
                      padding: '3px 9px',
                      borderRadius: '4px',
                      fontSize: '11px',
                      fontWeight: isActive ? 600 : 400,
                      cursor: 'pointer',
                      border: isActive ? '1px solid var(--accent-cyan)' : '1px solid rgba(255, 255, 255, 0.1)',
                      backgroundColor: isActive ? 'rgba(0, 240, 255, 0.2)' : 'rgba(255, 255, 255, 0.03)',
                      color: isActive ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    {m.label}
                  </button>
                );
              })}
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px' }}>
            {voiceMode === 'clean-dub' && (
              <span style={{ color: 'var(--status-success)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span>✓</span> Original Voice Muted (No Duplicate Sound)
              </span>
            )}
            {voiceMode === 'voice-over' && (
              <span style={{ color: '#d8b4fe', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span>⚡</span> Auto-Ducking: {Math.round(duckingLevel * 100)}% during speech
              </span>
            )}
            {voiceMode === 'custom-mix' && (
              <span style={{ color: 'var(--accent-cyan)' }}>
                🎛️ Stem Balance Active
              </span>
            )}
            {voiceMode === 'original-only' && (
              <span style={{ color: 'var(--text-muted)' }}>
                Dubbed Track Muted
              </span>
            )}
          </div>
        </div>
      )}

      {/* 3. SUB-SECOND SCRUBBER PROGRESS BAR */}
      <div
        style={{
          width: '100%',
          backgroundColor: '#090b12',
          padding: '4px 16px 2px 16px',
          display: 'flex',
          alignItems: 'center',
          flexShrink: 0,
        }}
      >
        <input
          type="range"
          min={0}
          max={playback.duration || 100}
          step={0.01}
          value={playback.currentTime}
          disabled={!mediaSrc}
          onMouseDown={() => setIsScrubbing(true)}
          onChange={(e) => {
            const val = parseFloat(e.target.value);
            seek(val);
          }}
          onMouseUp={() => setIsScrubbing(false)}
          style={{
            width: '100%',
            height: '5px',
            accentColor: 'var(--accent-cyan)',
            cursor: mediaSrc ? 'pointer' : 'default',
          }}
        />
      </div>

      {/* 4. MASTER TRANSPORT CONTROLS BAR (Pinned at bottom) */}
      <div
        style={{
          backgroundColor: '#080a11',
          padding: '8px 16px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderTop: '1px solid var(--border-subtle)',
          gap: '12px',
          flexShrink: 0,
          flexWrap: 'wrap',
          zIndex: 5,
        }}
      >
        {/* Left: Playback & Frame Stepping Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {/* Frame Step Back -1 Frame */}
          <button
            className="btn btn-outline"
            disabled={!mediaSrc}
            onClick={() => stepFrame(-1)}
            title="Step Backward 1 Frame (J / ←)"
            style={{
              padding: '5px 9px',
              fontSize: '12px',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            <span>⏮</span>
            <span style={{ fontSize: '10px', opacity: 0.8 }}>-1F</span>
          </button>

          {/* Main Play / Pause / Replay Button */}
          <button
            className="btn btn-primary"
            disabled={!mediaSrc}
            onClick={togglePlay}
            title={
              isAtEnd
                ? 'Replay from start (Space)'
                : playback.isPlaying
                ? 'Pause (Space)'
                : 'Play (Space)'
            }
            style={{
              padding: '5px 14px',
              fontSize: '12px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              minWidth: '85px',
              justifyContent: 'center',
            }}
          >
            <span>
              {playback.isPlaying
                ? '⏸ Pause'
                : isAtEnd
                ? '↺ Replay'
                : '▶ Play'}
            </span>
          </button>

          {/* Frame Step Forward +1 Frame */}
          <button
            className="btn btn-outline"
            disabled={!mediaSrc}
            onClick={() => stepFrame(1)}
            title="Step Forward 1 Frame (L / →)"
            style={{
              padding: '5px 9px',
              fontSize: '12px',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            <span style={{ fontSize: '10px', opacity: 0.8 }}>+1F</span>
            <span>⏭</span>
          </button>

          {/* High Precision SMPTE Timecode Display */}
          <div
            style={{
              marginLeft: '6px',
              padding: '3px 10px',
              backgroundColor: '#04060a',
              borderRadius: '6px',
              border: '1px solid rgba(0, 240, 255, 0.25)',
              fontFamily: 'Consolas, Monaco, monospace',
              fontSize: '11px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              letterSpacing: '0.5px',
            }}
          >
            <span style={{ color: 'var(--accent-cyan)', fontWeight: 600 }}>
              {formatSMPTE(playback.currentTime, playback.fps)}
            </span>
            <span style={{ color: 'var(--text-muted)' }}>/</span>
            <span style={{ color: 'var(--text-secondary)' }}>
              {formatSMPTE(playback.duration, playback.fps)}
            </span>
            <span
              style={{
                fontSize: '10px',
                color: 'var(--accent-purple)',
                paddingLeft: '4px',
                borderLeft: '1px solid rgba(255, 255, 255, 0.1)',
              }}
            >
              {playback.fps.toFixed(0)} FPS
            </span>
          </div>
        </div>

        {/* Right: Audio Volume, Playback Speed, Loop, Snapshot & Fullscreen */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {/* Seamless Loop Toggle */}
          <button
            onClick={toggleLoop}
            disabled={!mediaSrc}
            title={
              playback.isLooping
                ? 'Looping is ON (replays automatically when video reaches end)'
                : 'Looping is OFF (stops at end; click to enable seamless loop)'
            }
            style={{
              padding: '3px 8px',
              borderRadius: '4px',
              fontSize: '11px',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              cursor: mediaSrc ? 'pointer' : 'default',
              border: playback.isLooping ? '1px solid var(--accent-cyan)' : '1px solid rgba(255,255,255,0.1)',
              backgroundColor: playback.isLooping ? 'rgba(0, 240, 255, 0.18)' : 'transparent',
              color: playback.isLooping ? 'var(--accent-cyan)' : 'var(--text-muted)',
              fontWeight: playback.isLooping ? 600 : 400,
              transition: 'all 0.15s ease',
            }}
          >
            <span>🔁</span>
            <span>Loop</span>
          </button>

          {/* Playback Speed dropdown pills */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
            {[0.5, 1.0, 1.5, 2.0].map((rate) => (
              <button
                key={rate}
                onClick={() => setPlaybackRate(rate)}
                disabled={!mediaSrc}
                style={{
                  padding: '2px 6px',
                  borderRadius: '4px',
                  fontSize: '11px',
                  fontWeight: playback.playbackRate === rate ? 600 : 400,
                  backgroundColor: playback.playbackRate === rate ? 'rgba(0, 240, 255, 0.2)' : 'transparent',
                  color: playback.playbackRate === rate ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                  border: playback.playbackRate === rate ? '1px solid var(--accent-cyan)' : '1px solid transparent',
                  cursor: 'pointer',
                }}
              >
                {rate}x
              </button>
            ))}
          </div>

          {/* Volume Control */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <button
              onClick={toggleMute}
              disabled={!mediaSrc}
              style={{
                background: 'none',
                border: 'none',
                color: playback.isMuted ? 'var(--status-error)' : 'var(--text-secondary)',
                cursor: 'pointer',
                fontSize: '13px',
                padding: '2px',
              }}
              title="Mute / Unmute (M)"
            >
              {playback.isMuted || playback.volume === 0 ? '🔇' : '🔊'}
            </button>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={playback.isMuted ? 0 : playback.volume}
              onChange={(e) => setVolume(parseFloat(e.target.value))}
              disabled={!mediaSrc}
              style={{ width: '56px', height: '4px', accentColor: 'var(--accent-cyan)' }}
              title="Volume"
            />
          </div>

          {/* Frame Snapshot Button */}
          <button
            className="btn btn-outline"
            onClick={handleSnapshot}
            disabled={!mediaSrc}
            title="Capture Frame Snapshot (JPEG)"
            style={{ padding: '4px 8px', fontSize: '12px' }}
          >
            📸
          </button>

          {/* Fullscreen Button */}
          <button
            className="btn btn-outline"
            onClick={handleToggleFullscreen}
            disabled={!mediaSrc}
            title="Toggle Fullscreen (F)"
            style={{ padding: '4px 8px', fontSize: '12px' }}
          >
            {isFullscreen ? '⤦' : '⤢'}
          </button>
        </div>
      </div>
    </div>
  );
};
