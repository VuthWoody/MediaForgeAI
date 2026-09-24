import React, { useRef, useEffect, useState, useCallback } from 'react';
import { WaveformData } from '../../types/studio';
import { SpeechSegment } from '../../types/project';
import { formatDuration } from '../../context/StudioContext';

interface WaveformCanvasProps {
  waveform: WaveformData | null;
  currentTime: number;
  duration: number;
  isLoading?: boolean;
  segments?: SpeechSegment[];
  selectedSegmentId?: string | null;
  onSeek: (seconds: number) => void;
  onSelectSegment?: (segmentId: string) => void;
}

export const WaveformCanvas: React.FC<WaveformCanvasProps> = ({
  waveform,
  currentTime,
  duration,
  isLoading = false,
  segments = [],
  selectedSegmentId = null,
  onSeek,
  onSelectSegment,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [hoverTime, setHoverTime] = useState<number | null>(null);
  const [hoverX, setHoverX] = useState<number | null>(null);

  // Resize canvas when container width changes
  useEffect(() => {
    const handleResize = () => {
      if (containerRef.current && canvasRef.current) {
        const dpr = window.devicePixelRatio || 1;
        const width = containerRef.current.clientWidth;
        const height = 110;

        canvasRef.current.width = width * dpr;
        canvasRef.current.height = height * dpr;
        canvasRef.current.style.width = `${width}px`;
        canvasRef.current.style.height = `${height}px`;

        const ctx = canvasRef.current.getContext('2d');
        if (ctx) {
          ctx.scale(dpr, dpr);
        }
      }
    };

    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Main canvas render loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = parseFloat(canvas.style.width) || canvas.width;
    const height = parseFloat(canvas.style.height) || canvas.height;

    // Clear background
    ctx.clearRect(0, 0, width, height);

    // Background gradient
    const bgGrad = ctx.createLinearGradient(0, 0, 0, height);
    bgGrad.addColorStop(0, '#090b10');
    bgGrad.addColorStop(1, '#0e1118');
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, width, height);

    // Center baseline
    const centerY = (height - 20) / 2;
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, centerY);
    ctx.lineTo(width, centerY);
    ctx.stroke();

    const safeDuration = Math.max(0.1, duration);
    const playheadRatio = Math.max(0, Math.min(1, currentTime / safeDuration));
    const playheadX = playheadRatio * width;

    // Draw speech segments background boxes
    if (segments && segments.length > 0) {
      for (const seg of segments) {
        const segStartX = (seg.start / safeDuration) * width;
        const segEndX = (seg.end / safeDuration) * width;
        const segWidth = Math.max(2, segEndX - segStartX);
        const isSelected = seg.id === selectedSegmentId;

        ctx.fillStyle = isSelected
          ? 'rgba(0, 240, 255, 0.22)'
          : 'rgba(139, 92, 246, 0.12)';
        ctx.fillRect(segStartX, 2, segWidth, height - 24);

        ctx.strokeStyle = isSelected ? '#00f0ff' : 'rgba(139, 92, 246, 0.4)';
        ctx.lineWidth = isSelected ? 2 : 1;
        ctx.strokeRect(segStartX, 2, segWidth, height - 24);

        // Segment label
        if (segWidth > 45) {
          ctx.font = '10px Inter, sans-serif';
          ctx.fillStyle = isSelected ? '#00f0ff' : '#a0aec0';
          ctx.fillText(seg.speakerName || 'Speaker', segStartX + 4, 14);
        }
      }
    }

    // Draw Waveform peaks
    const peaks = waveform?.peaks;
    if (peaks && peaks.length > 0) {
      const barCount = peaks.length;
      const barWidth = Math.max(1.5, width / barCount);
      const maxHeight = (height - 30) * 0.88;

      for (let i = 0; i < barCount; i++) {
        const barX = (i / barCount) * width;
        const peakVal = peaks[i];
        const barHeight = Math.max(2, peakVal * maxHeight);
        const topY = centerY - barHeight / 2;

        const isPlayed = barX <= playheadX;

        if (isPlayed) {
          // Vivid cyan to purple gradient for played audio
          const grad = ctx.createLinearGradient(0, topY, 0, topY + barHeight);
          grad.addColorStop(0, '#00f0ff');
          grad.addColorStop(1, '#8b5cf6');
          ctx.fillStyle = grad;
        } else {
          // Slate gray for unplayed
          ctx.fillStyle = 'rgba(148, 163, 184, 0.28)';
        }

        ctx.fillRect(barX, topY, Math.max(1, barWidth - 1), barHeight);
      }
    } else if (isLoading) {
      // Animated shimmer bars when loading waveform
      const barCount = 60;
      const barWidth = width / barCount;
      const t = Date.now() / 400;
      for (let i = 0; i < barCount; i++) {
        const h = 8 + Math.abs(Math.sin(t + i * 0.2)) * 30;
        ctx.fillStyle = 'rgba(0, 240, 255, 0.25)';
        ctx.fillRect(i * barWidth, centerY - h / 2, barWidth - 2, h);
      }
    } else {
      // Empty placeholder wave
      const barCount = 80;
      const barWidth = width / barCount;
      for (let i = 0; i < barCount; i++) {
        const h = 4 + Math.sin(i * 0.3) * 3;
        ctx.fillStyle = 'rgba(255, 255, 255, 0.08)';
        ctx.fillRect(i * barWidth, centerY - h / 2, barWidth - 2, h);
      }
    }

    // Time Ruler at bottom
    ctx.fillStyle = '#07090e';
    ctx.fillRect(0, height - 18, width, 18);
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
    ctx.beginPath();
    ctx.moveTo(0, height - 18);
    ctx.lineTo(width, height - 18);
    ctx.stroke();

    // Ruler markers
    const stepSeconds = safeDuration > 300 ? 60 : safeDuration > 60 ? 15 : 5;
    const numMarkers = Math.floor(safeDuration / stepSeconds);
    ctx.font = '9px monospace';
    ctx.fillStyle = '#64748b';
    ctx.textAlign = 'center';

    for (let m = 0; m <= numMarkers; m++) {
      const markTime = m * stepSeconds;
      const markX = (markTime / safeDuration) * width;

      // Tick line
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.15)';
      ctx.beginPath();
      ctx.moveTo(markX, height - 18);
      ctx.lineTo(markX, height - 12);
      ctx.stroke();

      // Time label
      ctx.fillText(formatDuration(markTime), markX, height - 4);
    }

    // Hover line & timestamp tooltip
    if (hoverX !== null && hoverTime !== null) {
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.35)';
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(hoverX, 0);
      ctx.lineTo(hoverX, height - 18);
      ctx.stroke();
      ctx.setLineDash([]);

      // Tooltip pill
      const tipText = formatDuration(hoverTime);
      ctx.font = '10px monospace';
      const textWidth = ctx.measureText(tipText).width;
      const tipX = Math.max(20, Math.min(width - 25, hoverX));

      ctx.fillStyle = 'rgba(15, 23, 42, 0.9)';
      ctx.fillRect(tipX - textWidth / 2 - 4, 4, textWidth + 8, 16);
      ctx.strokeStyle = '#00f0ff';
      ctx.strokeRect(tipX - textWidth / 2 - 4, 4, textWidth + 8, 16);
      ctx.fillStyle = '#00f0ff';
      ctx.textAlign = 'center';
      ctx.fillText(tipText, tipX, 16);
    }

    // Playhead Line & Glowing Diamond Indicator
    ctx.strokeStyle = '#00f0ff';
    ctx.lineWidth = 2;
    ctx.shadowColor = 'rgba(0, 240, 255, 0.6)';
    ctx.shadowBlur = 6;
    ctx.beginPath();
    ctx.moveTo(playheadX, 0);
    ctx.lineTo(playheadX, height);
    ctx.stroke();

    // Diamond cap at playhead top
    ctx.fillStyle = '#00f0ff';
    ctx.beginPath();
    ctx.moveTo(playheadX, 0);
    ctx.lineTo(playheadX + 5, 6);
    ctx.lineTo(playheadX, 12);
    ctx.lineTo(playheadX - 5, 6);
    ctx.closePath();
    ctx.fill();

    // Reset shadow
    ctx.shadowBlur = 0;
  }, [waveform, currentTime, duration, isLoading, segments, selectedSegmentId, hoverX, hoverTime]);

  const handlePointerSeek = useCallback((clientX: number) => {
    if (!canvasRef.current || duration <= 0) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const x = Math.max(0, Math.min(clientX - rect.left, rect.width));
    const targetSeconds = (x / rect.width) * duration;
    onSeek(targetSeconds);

    // Check if clicked inside a segment
    if (segments && onSelectSegment) {
      const clickedSeg = segments.find(s => targetSeconds >= s.start && targetSeconds <= s.end);
      if (clickedSeg) {
        onSelectSegment(clickedSeg.id);
      }
    }
  }, [duration, onSeek, segments, onSelectSegment]);

  const onMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    setIsDragging(true);
    handlePointerSeek(e.clientX);
  };

  const onMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!canvasRef.current || duration <= 0) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const x = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
    setHoverX(x);
    setHoverTime((x / rect.width) * duration);

    if (isDragging) {
      handlePointerSeek(e.clientX);
    }
  };

  const onMouseLeave = () => {
    setIsDragging(false);
    setHoverX(null);
    setHoverTime(null);
  };

  const onMouseUp = () => {
    setIsDragging(false);
  };

  return (
    <div 
      ref={containerRef} 
      className="waveform-timeline-container" 
      style={{ 
        position: 'relative', 
        width: '100%', 
        height: '110px', 
        borderRadius: '8px', 
        overflow: 'hidden',
        border: '1px solid var(--border-subtle)',
        background: '#090b10',
        cursor: 'crosshair',
        userSelect: 'none',
      }}
    >
      <canvas
        ref={canvasRef}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
        onMouseLeave={onMouseLeave}
        style={{ display: 'block', width: '100%', height: '100%' }}
      />
      {isLoading && (
        <div style={{
          position: 'absolute',
          top: '8px',
          right: '12px',
          fontSize: '11px',
          color: 'var(--accent-cyan)',
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          background: 'rgba(0, 0, 0, 0.7)',
          padding: '2px 8px',
          borderRadius: '4px',
          border: '1px solid rgba(0, 240, 255, 0.3)'
        }}>
          <span className="spinner-dots">●</span> Generating Waveform...
        </div>
      )}
    </div>
  );
};
