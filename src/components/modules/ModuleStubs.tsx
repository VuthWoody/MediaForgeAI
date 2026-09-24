import React from 'react';
import {
  DownloadCloud,
  Film,
  Languages,
  Layers,
  Sparkles,
  ArrowRight,
  ShieldCheck,
  CheckCircle2,
} from 'lucide-react';
import { ActiveModule } from '../layout/Sidebar';

interface ModuleStubProps {
  module: 'downloader' | 'library' | 'studio' | 'batch';
  onNavigate: (module: ActiveModule) => void;
}

export const ModuleStub: React.FC<ModuleStubProps> = ({ module, onNavigate }) => {
  const configs = {
    downloader: {
      title: 'Multi-Platform Media Downloader',
      phase: 'Phase 2 Architecture Target',
      icon: <DownloadCloud size={40} color="var(--cyan)" />,
      desc: 'Automatic platform detection, 8K/4K stream selection, multi-threaded parallel chunk download workers (1–32 threads), and caption extraction.',
      features: [
        'URL input with auto platform detection (YouTube, Facebook, TikTok, X/Twitter, Bilibili, custom)',
        'Video & audio stream selector (8K, 4K, 1080p, 720p, audio-only extraction)',
        'Parallel download workers with real-time speed, ETA, and progress metrics',
        'Auto-download platform subtitles, captions, and high-res thumbnails',
        'Bulk URL queue with drag-and-drop support',
      ],
      nextStep: 'Phase 1 Shell & Projects are active. Downloader queue will be built in Phase 2.',
    },
    library: {
      title: 'Media Library & Asset Manager',
      phase: 'Phase 2 Architecture Target',
      icon: <Film size={40} color="var(--emerald)" />,
      desc: 'Hierarchical media catalog organizing downloaded and imported files by Platform -> Creator/Channel -> Project -> Date.',
      features: [
        'Automated directory scanner with thumbnail extraction via FFmpeg',
        'Tagging, search, filter by resolution, duration, and processing status',
        'Direct 1-click import into AI Video Translation Studio projects',
        'Metadata inspection (audio sample rate, video codec, bitrates)',
      ],
      nextStep: 'Media Library will hook into the Downloader database in Phase 2.',
    },
    studio: {
      title: 'AI Video Translation & Dubbing Studio',
      phase: 'Phases 3–8 Architecture Target',
      icon: <Languages size={40} color="var(--violet)" />,
      desc: 'Multi-track timeline, Whisper speech transcription, Khmer/Chinese/Japanese neural translation, Demucs audio separation, and Edge-TTS voice dubbing.',
      features: [
        'Whisper STT engine with word-level timestamps & automatic language detection',
        'Speaker Diarization & multi-speaker profile assignment',
        'Demucs neural audio separation (isolate vocals from background music/SFX)',
        'AI Voice Dubbing with timeline auto-synchronization & speech stretching',
        'Rich Subtitle editor with SRT, VTT, ASS, and hardware-accelerated video rendering',
      ],
      nextStep: 'Studio timeline, waveform rendering, and media player will be implemented in Phases 3–8.',
    },
    batch: {
      title: 'Batch Processing & Parallel Worker Engine',
      phase: 'Phase 9 Architecture Target',
      icon: <Layers size={40} color="var(--amber)" />,
      desc: 'High-throughput job queue running multiple video translation, rendering, and downloading jobs in parallel.',
      features: [
        'Dynamic thread pool allocation based on detected CPU cores & GPU VRAM',
        'Job prioritization, retry policies, and background progress tracking',
        'GPU hardware acceleration via Intel QuickSync / NVIDIA NVENC / AMD AMF',
      ],
      nextStep: 'Batch queue will orchestrate pipelines once Studio and Downloader modules are active.',
    },
  };

  const item = configs[module];

  return (
    <div style={{ maxWidth: '820px', margin: '30px auto', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div className="card" style={{ padding: '36px', position: 'relative', overflow: 'hidden' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '20px', marginBottom: '20px' }}>
          <div
            style={{
              width: 72,
              height: 72,
              borderRadius: '16px',
              background: 'rgba(255, 255, 255, 0.04)',
              border: '1px solid var(--glass-border)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}
          >
            {item.icon}
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
              <span className="badge badge-cyan">{item.phase}</span>
            </div>
            <h1 style={{ fontSize: '24px', fontWeight: 700, fontFamily: 'Outfit, sans-serif', color: 'var(--text-primary)', marginBottom: '8px' }}>
              {item.title}
            </h1>
            <p style={{ fontSize: '14px', color: 'var(--text-secondary)', lineHeight: '1.5' }}>
              {item.desc}
            </p>
          </div>
        </div>

        {/* Feature Highlights */}
        <div
          style={{
            background: 'var(--bg-surface)',
            border: '1px solid var(--glass-border-subtle)',
            borderRadius: 'var(--radius-md)',
            padding: '20px',
            marginBottom: '24px',
          }}
        >
          <h3 style={{ fontSize: '13px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.6px', color: 'var(--text-muted)', marginBottom: '14px' }}>
            Architectural Pipeline Specification
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {item.features.map((feat, idx) => (
              <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '13px', color: 'var(--text-primary)' }}>
                <CheckCircle2 size={16} color="var(--cyan)" style={{ flexShrink: 0 }} />
                <span>{feat}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Next Step & Navigation */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: '16px', borderTop: '1px solid var(--glass-border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', color: 'var(--text-muted)' }}>
            <Sparkles size={14} color="var(--violet)" />
            <span>{item.nextStep}</span>
          </div>

          <div style={{ display: 'flex', gap: '10px' }}>
            <button className="btn btn-secondary" onClick={() => onNavigate('projects')}>
              Go to Projects
            </button>
            <button className="btn btn-primary" onClick={() => onNavigate('dashboard')}>
              <span>Back to Dashboard</span>
              <ArrowRight size={14} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
