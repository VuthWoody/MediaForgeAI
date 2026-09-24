import React, { useState } from 'react';
import {
  Settings,
  Sliders,
  DownloadCloud,
  Cpu,
  Sparkles,
  Check,
  RotateCcw,
  FolderOpen,
  CheckCircle2,
  Terminal,
  Zap,
  Key,
  ExternalLink,
  AlertCircle,
  Loader2,
} from 'lucide-react';
import { useSettings } from '../../context/SettingsContext';
import { useSystem } from '../../context/SystemContext';
import { AppSettings } from '../../types/settings';

type SettingsTab = 'general' | 'downloader' | 'ai' | 'hardware' | 'diagnostics';

export const SettingsView: React.FC = () => {
  const { settings, saveSettings, resetSettings } = useSettings();
  const { hardware, refreshHardware } = useSystem();

  const [activeTab, setActiveTab] = useState<SettingsTab>('general');
  const [formData, setFormData] = useState<AppSettings>(settings);
  const [savedNotice, setSavedNotice] = useState(false);
  const [diagnosticLog, setDiagnosticLog] = useState<string[]>([]);
  const [testingKey, setTestingKey] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, { success: boolean; latencyMs?: number; error?: string }>>({});

  const handleTestKey = async (engine: string, apiKey?: string, endpoint?: string) => {
    if (!window.electronAPI?.aiTestTranslationKey) return;
    setTestingKey(engine);
    try {
      const res = await window.electronAPI.aiTestTranslationKey({
        engine,
        apiKey: apiKey?.trim(),
        endpoint: endpoint?.trim(),
      });
      setTestResults((prev) => ({
        ...prev,
        [engine]: {
          success: res.success,
          latencyMs: res.latencyMs,
          error: res.error,
        },
      }));
    } catch (err: any) {
      setTestResults((prev) => ({
        ...prev,
        [engine]: {
          success: false,
          error: err.message || 'Connection test failed',
        },
      }));
    } finally {
      setTestingKey(null);
    }
  };

  const handleSave = async () => {
    const success = await saveSettings(formData);
    if (success) {
      setSavedNotice(true);
      setTimeout(() => setSavedNotice(false), 2500);
    }
  };

  const handleReset = async () => {
    if (window.confirm('Reset all settings to factory defaults?')) {
      await resetSettings();
      setFormData(settings);
    }
  };

  const runDiagnosticTest = async (testName: string) => {
    setDiagnosticLog((prev) => [...prev, `[${new Date().toLocaleTimeString()}] Testing ${testName}...`]);
    await refreshHardware();
    if (testName === 'FFmpeg') {
      setDiagnosticLog((prev) => [
        ...prev,
        `[${new Date().toLocaleTimeString()}] FFmpeg: ${hardware?.ffmpeg.version || 'Detected'}`,
        `[${new Date().toLocaleTimeString()}] Supported Encoders: ${hardware?.ffmpeg.supportedEncoders.join(', ') || 'Auto'}`,
      ]);
    } else if (testName === 'GPU') {
      setDiagnosticLog((prev) => [
        ...prev,
        `[${new Date().toLocaleTimeString()}] GPU: ${hardware?.gpus?.[0]?.name || 'Unknown'}`,
      ]);
    } else if (testName === 'Downloader') {
      setDiagnosticLog((prev) => [
        ...prev,
        `[${new Date().toLocaleTimeString()}] yt-dlp: ${hardware?.ytDlp.version ? `v${hardware.ytDlp.version}` : 'Ready'}`,
      ]);
    } else if (testName === 'Python') {
      setDiagnosticLog((prev) => [
        ...prev,
        `[${new Date().toLocaleTimeString()}] Python: ${hardware?.python.version || '3.12'}`,
      ]);
    }
  };

  return (
    <div className="settings-container" style={{ maxWidth: '960px', width: '100%', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
        <div>
          <h1 style={{ fontSize: '26px', fontWeight: 700, fontFamily: 'Outfit, sans-serif', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Settings size={26} color="var(--cyan)" />
            <span>Preferences & System Settings</span>
          </h1>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px' }}>
            Configure downloading engines, AI transcription, language defaults, and GPU hardware acceleration.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {savedNotice && (
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--emerald)', fontSize: '13px', fontWeight: 600 }}>
              <CheckCircle2 size={16} />
              <span>Saved!</span>
            </span>
          )}
          <button className="btn btn-secondary" onClick={handleReset} title="Reset to default settings">
            <RotateCcw size={15} />
            <span>Defaults</span>
          </button>
          <button className="btn btn-primary" onClick={handleSave}>
            <Check size={16} />
            <span>Save Preferences</span>
          </button>
        </div>
      </div>

      {/* Tabs Switcher */}
      <div
        style={{
          display: 'flex',
          gap: '4px',
          background: 'var(--bg-surface)',
          padding: '4px',
          borderRadius: 'var(--radius-lg)',
          border: '1px solid var(--glass-border)',
          marginBottom: '24px',
        }}
      >
        <button
          className={`btn btn-sm ${activeTab === 'general' ? 'btn-primary' : 'btn-ghost'}`}
          onClick={() => setActiveTab('general')}
          style={{ flex: 1 }}
        >
          <Sliders size={14} />
          <span>General</span>
        </button>
        <button
          className={`btn btn-sm ${activeTab === 'downloader' ? 'btn-primary' : 'btn-ghost'}`}
          onClick={() => setActiveTab('downloader')}
          style={{ flex: 1 }}
        >
          <DownloadCloud size={14} />
          <span>Downloader</span>
        </button>
        <button
          className={`btn btn-sm ${activeTab === 'ai' ? 'btn-primary' : 'btn-ghost'}`}
          onClick={() => setActiveTab('ai')}
          style={{ flex: 1 }}
        >
          <Sparkles size={14} />
          <span>AI & Studio</span>
        </button>
        <button
          className={`btn btn-sm ${activeTab === 'hardware' ? 'btn-primary' : 'btn-ghost'}`}
          onClick={() => setActiveTab('hardware')}
          style={{ flex: 1 }}
        >
          <Cpu size={14} />
          <span>Hardware & GPU</span>
        </button>
        <button
          className={`btn btn-sm ${activeTab === 'diagnostics' ? 'btn-primary' : 'btn-ghost'}`}
          onClick={() => setActiveTab('diagnostics')}
          style={{ flex: 1 }}
        >
          <Terminal size={14} />
          <span>Diagnostics</span>
        </button>
      </div>

      {/* Tab 1: General */}
      {activeTab === 'general' && (
        <div className="card" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <h2 style={{ fontSize: '16px', fontWeight: 700, fontFamily: 'Outfit, sans-serif' }}>
            General Application Settings
          </h2>

          <div className="input-group">
            <label className="input-label">Interface Theme Palette</label>
            <select
              className="select-field"
              value={formData.general.theme}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  general: { ...formData.general, theme: e.target.value as any },
                })
              }
            >
              <option value="dark-forge">Dark Forge (Obsidian & Electric Cyan)</option>
              <option value="midnight">Midnight Pro (Deep Navy & Neon Purple)</option>
              <option value="cyberpunk">Cyberpunk Neon (Violet & Hot Cyan)</option>
            </select>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            <div className="input-group">
              <label className="input-label">Default Source Language</label>
              <select
                className="select-field"
                value={formData.general.defaultSourceLanguage}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    general: { ...formData.general, defaultSourceLanguage: e.target.value },
                  })
                }
              >
                <option value="en">English</option>
                <option value="zh">Chinese (中文)</option>
                <option value="ja">Japanese (日本語)</option>
                <option value="ko">Korean (한국어)</option>
                <option value="km">Khmer (ភាសាខ្មែរ)</option>
              </select>
            </div>

            <div className="input-group">
              <label className="input-label">Default Target Translation Language</label>
              <select
                className="select-field"
                value={formData.general.defaultTargetLanguage}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    general: { ...formData.general, defaultTargetLanguage: e.target.value },
                  })
                }
              >
                <option value="km">Khmer (ភាសាខ្មែរ)</option>
                <option value="en">English</option>
                <option value="zh">Chinese (中文)</option>
                <option value="ja">Japanese (日本語)</option>
                <option value="ko">Korean (한국어)</option>
              </select>
            </div>
          </div>

          <div className="input-group">
            <label className="input-label">Projects Workspace Directory</label>
            <input
              type="text"
              className="input-field"
              value={formData.general.projectsDirectory}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  general: { ...formData.general, projectsDirectory: e.target.value },
                })
              }
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            <div className="input-group">
              <label className="input-label">Project Auto-Save Interval</label>
              <select
                className="select-field"
                value={formData.general.autoSaveIntervalSeconds}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    general: {
                      ...formData.general,
                      autoSaveIntervalSeconds: Number(e.target.value),
                    },
                  })
                }
              >
                <option value={30}>Every 30 seconds</option>
                <option value={60}>Every 1 minute</option>
                <option value={120}>Every 2 minutes</option>
                <option value={300}>Every 5 minutes</option>
              </select>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginTop: '22px' }}>
              <input
                type="checkbox"
                id="gauges-toggle"
                checked={formData.general.enableHardwareGauges}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    general: { ...formData.general, enableHardwareGauges: e.target.checked },
                  })
                }
                style={{ width: '16px', height: '16px', accentColor: 'var(--cyan)' }}
              />
              <label htmlFor="gauges-toggle" style={{ fontSize: '13px', cursor: 'pointer' }}>
                Enable live CPU, RAM & GPU telemetry polling
              </label>
            </div>
          </div>
        </div>
      )}

      {/* Tab 2: Downloader */}
      {activeTab === 'downloader' && (
        <div className="card" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <h2 style={{ fontSize: '16px', fontWeight: 700, fontFamily: 'Outfit, sans-serif' }}>
            Multi-Platform Media Downloader Engine (Phase 2 Ready)
          </h2>

          <div className="input-group">
            <label className="input-label">Default Download Directory</label>
            <input
              type="text"
              className="input-field"
              value={formData.downloader.downloadDirectory}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  downloader: { ...formData.downloader, downloadDirectory: e.target.value },
                })
              }
            />
          </div>

          <div className="input-group">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <label className="input-label">Concurrent Download Workers / Threads</label>
              <span className="badge badge-cyan">{formData.downloader.maxConcurrentThreads} Threads</span>
            </div>
            <input
              type="range"
              min={1}
              max={32}
              value={formData.downloader.maxConcurrentThreads}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  downloader: {
                    ...formData.downloader,
                    maxConcurrentThreads: Number(e.target.value),
                  },
                })
              }
              style={{ width: '100%', accentColor: 'var(--cyan)', marginTop: '8px' }}
            />
            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              Supports parallel video & audio chunk downloads up to 32 worker threads.
            </span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            <div className="input-group">
              <label className="input-label">Preferred Video Resolution</label>
              <select
                className="select-field"
                value={formData.downloader.preferredResolution}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    downloader: {
                      ...formData.downloader,
                      preferredResolution: e.target.value as any,
                    },
                  })
                }
              >
                <option value="best">Best Available (Up to 8K/4K)</option>
                <option value="4k">4K (2160p)</option>
                <option value="1080p">Full HD (1080p)</option>
                <option value="720p">HD (720p)</option>
                <option value="audio_only">Audio Only (Extract Highest Bitrate)</option>
              </select>
            </div>

            <div className="input-group">
              <label className="input-label">Preferred Output Container</label>
              <select
                className="select-field"
                value={formData.downloader.preferredFormat}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    downloader: {
                      ...formData.downloader,
                      preferredFormat: e.target.value as any,
                    },
                  })
                }
              >
                <option value="mp4">MP4 (Universal Compatibility)</option>
                <option value="mkv">MKV (Multi-track Subtitles & Audio)</option>
                <option value="webm">WebM</option>
              </select>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <input
                type="checkbox"
                id="sub-auto-toggle"
                checked={formData.downloader.autoDownloadSubtitles}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    downloader: {
                      ...formData.downloader,
                      autoDownloadSubtitles: e.target.checked,
                    },
                  })
                }
                style={{ width: '16px', height: '16px', accentColor: 'var(--cyan)' }}
              />
              <label htmlFor="sub-auto-toggle" style={{ fontSize: '13px', cursor: 'pointer' }}>
                Auto-download platform subtitles & captions
              </label>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <input
                type="checkbox"
                id="thumb-auto-toggle"
                checked={formData.downloader.autoDownloadThumbnail}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    downloader: {
                      ...formData.downloader,
                      autoDownloadThumbnail: e.target.checked,
                    },
                  })
                }
                style={{ width: '16px', height: '16px', accentColor: 'var(--cyan)' }}
              />
              <label htmlFor="thumb-auto-toggle" style={{ fontSize: '13px', cursor: 'pointer' }}>
                Auto-download highest quality thumbnail
              </label>
            </div>
          </div>
        </div>
      )}

      {/* Tab 3: AI & Studio */}
      {activeTab === 'ai' && (
        <div className="card" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <h2 style={{ fontSize: '16px', fontWeight: 700, fontFamily: 'Outfit, sans-serif' }}>
            AI Speech, Translation & Voice Dubbing Pipeline
          </h2>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            <div className="input-group">
              <label className="input-label">Whisper STT Model Size</label>
              <select
                className="select-field"
                value={formData.ai.whisperModel}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    ai: { ...formData.ai, whisperModel: e.target.value as any },
                  })
                }
              >
                <option value="tiny">Tiny (~75MB, fastest)</option>
                <option value="base">Base (~145MB, lightweight)</option>
                <option value="small">Small (~480MB, recommended balance)</option>
                <option value="medium">Medium (~1.5GB, high accuracy)</option>
                <option value="large-v3">Large v3 (~3GB, maximum precision)</option>
              </select>
            </div>

            <div className="input-group">
              <label className="input-label">Default Translation Engine</label>
              <select
                className="select-field"
                value={formData.ai.translationEngine}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    ai: { ...formData.ai, translationEngine: e.target.value as any },
                  })
                }
              >
                <option value="gemini">Google Gemini 2.0 / 1.5 Flash (★ Recommended for Khmer)</option>
                <option value="openai">OpenAI GPT-4o / GPT-4o-mini</option>
                <option value="deepseek">DeepSeek Chat / V3 (Ultra Cost-Effective)</option>
                <option value="smart-contextual">Smart Contextual Refiner (Built-in / Offline)</option>
                <option value="local-llm">Local LLM (Ollama / vLLM / OpenAI-compatible)</option>
                <option value="google-translate">Google Translate (Fast NMT)</option>
              </select>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            <div className="input-group">
              <label className="input-label">Default Content Genre & Tone</label>
              <select
                className="select-field"
                value={formData.ai.defaultContentGenre}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    ai: { ...formData.ai, defaultContentGenre: e.target.value as any },
                  })
                }
              >
                <option value="auto">Auto-Detect Video Tone (Contextual Analysis)</option>
                <option value="documentary">🦁 Documentary & Nature (Elevated Phrasing & Wildlife)</option>
                <option value="conversational">💬 Conversational Vlog (Casual Spoken Khmer)</option>
                <option value="cinematic">🎬 Cinematic Drama (Poetic & Character Dialogue)</option>
                <option value="news">📰 News & Formal (Authoritative & Dignified)</option>
                <option value="tutorial">💻 Tech & Tutorial (Clear & Instructive)</option>
              </select>
            </div>

            <div className="input-group">
              <label className="input-label">Voice Dubbing (TTS) Engine</label>
              <select
                className="select-field"
                value={formData.ai.dubbingEngine}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    ai: { ...formData.ai, dubbingEngine: e.target.value as any },
                  })
                }
              >
                <option value="edge-tts">Microsoft Edge TTS (High Quality, Free, Natural)</option>
                <option value="voxcpm">VOXCPM Voice Cloning (Zero-Shot AI Voice Actor)</option>
                <option value="elevenlabs">ElevenLabs (Premium Cloud Voice Cloning)</option>
                <option value="piper">Piper TTS (Fast Local Neural)</option>
              </select>
            </div>
          </div>

          <div className="input-group">
            <label className="input-label">Vocal & Music Separation Engine</label>
            <select
              className="select-field"
              value={formData.ai.separationEngine}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  ai: { ...formData.ai, separationEngine: e.target.value as any },
                })
              }
            >
              <option value="demucs">Demucs v4 (Meta AI Source Separation)</option>
              <option value="uvr5">Ultimate Vocal Remover (UVR5)</option>
            </select>
          </div>

          {/* AI Translation API Keys & Connection Tests */}
          <div
            style={{
              marginTop: '8px',
              padding: '16px',
              background: 'rgba(10, 15, 26, 0.65)',
              border: '1px solid var(--glass-border)',
              borderRadius: 'var(--radius-md)',
              display: 'flex',
              flexDirection: 'column',
              gap: '14px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Key size={15} color="var(--cyan)" />
                <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '0.02em' }}>
                  AI Translation Provider Credentials & Endpoints
                </span>
              </div>
              <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                API keys are stored locally and encrypted on your machine
              </span>
            </div>

            {/* Google Gemini Key */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <label className="input-label" style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ color: 'var(--cyan)', fontWeight: 600 }}>Google Gemini API Key</span>
                  <span className="badge badge-cyan" style={{ fontSize: '10px', padding: '1px 6px' }}>Top Accuracy for Khmer</span>
                </label>
                <a
                  href="https://aistudio.google.com/app/apikey"
                  target="_blank"
                  rel="noreferrer"
                  style={{ fontSize: '11px', color: 'var(--cyan)', display: 'flex', alignItems: 'center', gap: '4px', textDecoration: 'none' }}
                >
                  <span>Get Free Key at Google AI Studio</span>
                  <ExternalLink size={11} />
                </a>
              </div>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <input
                  type="password"
                  className="input-field"
                  placeholder="AIzaSy... (Gemini 2.0 / 1.5 Flash)"
                  value={formData.ai.geminiApiKey}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      ai: { ...formData.ai, geminiApiKey: e.target.value },
                    })
                  }
                  style={{ flex: 1, fontFamily: 'monospace', fontSize: '12px' }}
                />
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  disabled={testingKey === 'gemini'}
                  onClick={() => handleTestKey('gemini', formData.ai.geminiApiKey)}
                  style={{ minWidth: '95px' }}
                >
                  {testingKey === 'gemini' ? (
                    <Loader2 size={13} className="spin" />
                  ) : (
                    <Zap size={13} />
                  )}
                  <span>Test Key</span>
                </button>
              </div>
              {testResults['gemini'] && (
                <div style={{ fontSize: '11px', display: 'flex', alignItems: 'center', gap: '5px', marginTop: '2px' }}>
                  {testResults['gemini'].success ? (
                    <span style={{ color: 'var(--emerald)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <CheckCircle2 size={12} />
                      Connected to Gemini Flash ({testResults['gemini'].latencyMs}ms)
                    </span>
                  ) : (
                    <span style={{ color: 'var(--rose)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <AlertCircle size={12} />
                      {testResults['gemini'].error}
                    </span>
                  )}
                </div>
              )}
            </div>

            {/* OpenAI Key */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <label className="input-label" style={{ margin: 0, fontWeight: 600 }}>
                  OpenAI API Key (GPT-4o / GPT-4o-mini)
                </label>
              </div>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <input
                  type="password"
                  className="input-field"
                  placeholder="sk-proj-..."
                  value={formData.ai.openaiApiKey}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      ai: { ...formData.ai, openaiApiKey: e.target.value },
                    })
                  }
                  style={{ flex: 1, fontFamily: 'monospace', fontSize: '12px' }}
                />
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  disabled={testingKey === 'openai'}
                  onClick={() => handleTestKey('openai', formData.ai.openaiApiKey)}
                  style={{ minWidth: '95px' }}
                >
                  {testingKey === 'openai' ? (
                    <Loader2 size={13} className="spin" />
                  ) : (
                    <Zap size={13} />
                  )}
                  <span>Test Key</span>
                </button>
              </div>
              {testResults['openai'] && (
                <div style={{ fontSize: '11px', display: 'flex', alignItems: 'center', gap: '5px', marginTop: '2px' }}>
                  {testResults['openai'].success ? (
                    <span style={{ color: 'var(--emerald)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <CheckCircle2 size={12} />
                      Connected to OpenAI ({testResults['openai'].latencyMs}ms)
                    </span>
                  ) : (
                    <span style={{ color: 'var(--rose)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <AlertCircle size={12} />
                      {testResults['openai'].error}
                    </span>
                  )}
                </div>
              )}
            </div>

            {/* DeepSeek Key */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <label className="input-label" style={{ margin: 0, fontWeight: 600 }}>
                  DeepSeek API Key (DeepSeek-V3)
                </label>
              </div>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <input
                  type="password"
                  className="input-field"
                  placeholder="sk-..."
                  value={formData.ai.deepseekApiKey}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      ai: { ...formData.ai, deepseekApiKey: e.target.value },
                    })
                  }
                  style={{ flex: 1, fontFamily: 'monospace', fontSize: '12px' }}
                />
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  disabled={testingKey === 'deepseek'}
                  onClick={() => handleTestKey('deepseek', formData.ai.deepseekApiKey)}
                  style={{ minWidth: '95px' }}
                >
                  {testingKey === 'deepseek' ? (
                    <Loader2 size={13} className="spin" />
                  ) : (
                    <Zap size={13} />
                  )}
                  <span>Test Key</span>
                </button>
              </div>
              {testResults['deepseek'] && (
                <div style={{ fontSize: '11px', display: 'flex', alignItems: 'center', gap: '5px', marginTop: '2px' }}>
                  {testResults['deepseek'].success ? (
                    <span style={{ color: 'var(--emerald)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <CheckCircle2 size={12} />
                      Connected to DeepSeek ({testResults['deepseek'].latencyMs}ms)
                    </span>
                  ) : (
                    <span style={{ color: 'var(--rose)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <AlertCircle size={12} />
                      {testResults['deepseek'].error}
                    </span>
                  )}
                </div>
              )}
            </div>

            {/* Local LLM Endpoint */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <label className="input-label" style={{ margin: 0, fontWeight: 600 }}>
                  Local LLM Endpoint (Ollama / Local Server)
                </label>
              </div>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <input
                  type="text"
                  className="input-field"
                  placeholder="http://localhost:11434/v1"
                  value={formData.ai.customLlmEndpoint}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      ai: { ...formData.ai, customLlmEndpoint: e.target.value },
                    })
                  }
                  style={{ flex: 1, fontFamily: 'monospace', fontSize: '12px' }}
                />
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  disabled={testingKey === 'local-llm'}
                  onClick={() => handleTestKey('local-llm', '', formData.ai.customLlmEndpoint)}
                  style={{ minWidth: '95px' }}
                >
                  {testingKey === 'local-llm' ? (
                    <Loader2 size={13} className="spin" />
                  ) : (
                    <Zap size={13} />
                  )}
                  <span>Test Endpoint</span>
                </button>
              </div>
              {testResults['local-llm'] && (
                <div style={{ fontSize: '11px', display: 'flex', alignItems: 'center', gap: '5px', marginTop: '2px' }}>
                  {testResults['local-llm'].success ? (
                    <span style={{ color: 'var(--emerald)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <CheckCircle2 size={12} />
                      Connected to Local LLM ({testResults['local-llm'].latencyMs}ms)
                    </span>
                  ) : (
                    <span style={{ color: 'var(--rose)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <AlertCircle size={12} />
                      {testResults['local-llm'].error}
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Tab 4: Hardware & GPU */}
      {activeTab === 'hardware' && (
        <div className="card" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <h2 style={{ fontSize: '16px', fontWeight: 700, fontFamily: 'Outfit, sans-serif' }}>
            Hardware Acceleration & FFmpeg Encoder Configuration
          </h2>

          <div className="input-group">
            <label className="input-label">Preferred Hardware Video Encoder</label>
            <select
              className="select-field"
              value={formData.hardware.preferredEncoder}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  hardware: { ...formData.hardware, preferredEncoder: e.target.value as any },
                })
              }
            >
              <option value="auto">Auto-Detect Best Available (Recommended)</option>
              <option value="qsv">Intel QuickSync (h264_qsv / hevc_qsv)</option>
              <option value="nvenc">NVIDIA NVENC (h264_nvenc / hevc_nvenc)</option>
              <option value="amf">AMD AMF (h264_amf / hevc_amf)</option>
              <option value="cpu">Software CPU (libx264 / libx265)</option>
            </select>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <input
                type="checkbox"
                id="hw-dec-toggle"
                checked={formData.hardware.enableHardwareDecoding}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    hardware: {
                      ...formData.hardware,
                      enableHardwareDecoding: e.target.checked,
                    },
                  })
                }
                style={{ width: '16px', height: '16px', accentColor: 'var(--cyan)' }}
              />
              <label htmlFor="hw-dec-toggle" style={{ fontSize: '13px', cursor: 'pointer' }}>
                Enable GPU Hardware Decoding for Player
              </label>
            </div>

            <div className="input-group">
              <label className="input-label">FFmpeg Thread Pool Count</label>
              <select
                className="select-field"
                value={formData.hardware.workerThreads}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    hardware: {
                      ...formData.hardware,
                      workerThreads: Number(e.target.value),
                    },
                  })
                }
              >
                <option value={2}>2 Threads</option>
                <option value={4}>4 Threads</option>
                <option value={8}>8 Threads</option>
                <option value={16}>16 Threads</option>
              </select>
            </div>
          </div>

          <div className="input-group">
            <label className="input-label">Custom FFmpeg Path (Leave empty to use System PATH)</label>
            <input
              type="text"
              className="input-field"
              placeholder="e.g. C:\ffmpeg\bin\ffmpeg.exe"
              value={formData.hardware.customFFmpegPath || ''}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  hardware: { ...formData.hardware, customFFmpegPath: e.target.value },
                })
              }
            />
          </div>
        </div>
      )}

      {/* Tab 5: Diagnostics */}
      {activeTab === 'diagnostics' && (
        <div className="card" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <h2 style={{ fontSize: '16px', fontWeight: 700, fontFamily: 'Outfit, sans-serif' }}>
            System Environment Diagnostics & Engine Tests
          </h2>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px' }}>
            <button className="btn btn-secondary" onClick={() => runDiagnosticTest('FFmpeg')}>
              <Zap size={14} color="var(--cyan)" />
              <span>Test FFmpeg</span>
            </button>
            <button className="btn btn-secondary" onClick={() => runDiagnosticTest('GPU')}>
              <Cpu size={14} color="var(--emerald)" />
              <span>Probe GPU</span>
            </button>
            <button className="btn btn-secondary" onClick={() => runDiagnosticTest('Downloader')}>
              <DownloadCloud size={14} color="var(--amber)" />
              <span>Test yt-dlp</span>
            </button>
            <button className="btn btn-secondary" onClick={() => runDiagnosticTest('Python')}>
              <Terminal size={14} color="var(--violet)" />
              <span>Check Python</span>
            </button>
          </div>

          <div
            style={{
              background: 'var(--bg-deepest)',
              border: '1px solid var(--glass-border)',
              borderRadius: 'var(--radius-md)',
              padding: '16px',
              fontFamily: 'JetBrains Mono, monospace',
              fontSize: '12px',
              color: 'var(--text-secondary)',
              minHeight: '160px',
              maxHeight: '260px',
              overflowY: 'auto',
            }}
          >
            {diagnosticLog.length === 0 ? (
              <span style={{ color: 'var(--text-dim)' }}>Click a test button above to run diagnostic probes...</span>
            ) : (
              diagnosticLog.map((line, idx) => <div key={idx} style={{ marginBottom: '4px' }}>{line}</div>)
            )}
          </div>
        </div>
      )}
    </div>
  );
};
