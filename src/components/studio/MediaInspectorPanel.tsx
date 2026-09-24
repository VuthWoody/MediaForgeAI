import React, { useState } from 'react';
import { useStudio, formatDuration } from '../../context/StudioContext';
import { useProject } from '../../context/ProjectContext';
import { useSettings } from '../../context/SettingsContext';
import { toMediaUrl } from '../../utils/mediaUrl';

export const MediaInspectorPanel: React.FC = () => {
  const {
    mediaProbe,
    isProbing,
    isExtractingAudio,
    extractionResult,
    extractSpeechAudio,
    activeTab,
    setActiveTab,
    snapshots,
    updateStemVolume,
    // AI Pipeline
    isTranscribing,
    isTranslating,
    isDubbing,
    isPipelineRunning,
    aiProgress,
    voices,
    selectedVoice,
    setSelectedVoice,
    targetLanguage,
    setTargetLanguage,
    whisperModel,
    setWhisperModel,
    transcribeSpeech,
    translateSubtitles,
    generateDubbing,
    runFullAiPipeline,
    updateSegment,
    deleteSegment,
    previewSegment,
    voiceMode,
    setVoiceMode,
    duckingLevel,
    setDuckingLevel,
    dubbingEngine,
    setDubbingEngine,
    voxcpmActor,
    setVoxcpmActor,
    voxcpmPrompt,
    setVoxcpmPrompt,
    referenceAudioPath,
    setReferenceAudioPath,
    voxcpmActors,
    translationEngine,
    setTranslationEngine,
    contentGenre,
    setContentGenre,
    detectedGenre,
    testTranslationApiKey,
    translationStyle,
    setTranslationStyle,
    translationPrompt,
    setTranslationPrompt,
    clonedVoices,
    loadClonedVoices,
    selectReferenceAudioFile,
    saveClonedVoice,
    deleteClonedVoice,
  } = useStudio();

  const { settings, updateSettings } = useSettings();
  const [keyTestState, setKeyTestState] = useState<{ testing: boolean; success?: boolean; latencyMs?: number; error?: string } | null>(null);
  const [apiKeyInput, setApiKeyInput] = useState<string>('');
  const [isEditingApiKey, setIsEditingApiKey] = useState(false);

  const { activeProject } = useProject();
  const [editingSegmentId, setEditingSegmentId] = useState<string | null>(null);
  const [newCloneName, setNewCloneName] = useState('');
  const [isSavingClone, setIsSavingClone] = useState(false);

  // AI Dubbing View Mode: 'quick' (clean presets) vs 'advanced' (4 stages)
  const [dubbingMode, setDubbingMode] = useState<'quick' | 'advanced'>('quick');
  const [openStages, setOpenStages] = useState<Record<number, boolean>>({
    1: false,
    2: true, // Stage 2 open by default
    3: false,
    4: false,
  });
  const [activePreset, setActivePreset] = useState<string | null>('documentary');

  const toggleStage = (stageNum: number) => {
    setOpenStages(prev => ({
      ...prev,
      [stageNum]: !prev[stageNum],
    }));
  };

  const applyPreset = (presetId: string) => {
    setActivePreset(presetId);
    if (presetId === 'documentary') {
      setWhisperModel('small');
      setTranslationEngine('gemini');
      setContentGenre('documentary');
      setTranslationStyle('natural');
      setDubbingEngine('edge-tts');
      setVoiceMode('clean-dub');
      setTranslationPrompt('Documentary nature narrative, dignified wildlife terminology, eloquent spoken Khmer');
      if (targetLanguage === 'km') {
        setSelectedVoice('km-KH-PisethNeural');
      }
    } else if (presetId === 'fast-free') {
      setWhisperModel('base');
      setTranslationEngine('smart-contextual');
      setContentGenre('auto');
      setTranslationStyle('natural');
      setDubbingEngine('edge-tts');
      setVoiceMode('clean-dub');
      setTranslationPrompt('');
      if (targetLanguage === 'km') {
        setSelectedVoice('km-KH-PisethNeural');
      }
    } else if (presetId === 'voice-clone') {
      setWhisperModel('small');
      setTranslationEngine('gemini');
      setContentGenre('conversational');
      setTranslationStyle('natural');
      setDubbingEngine('voxcpm');
      setVoxcpmActor('voice_clone_original');
      setVoiceMode('clean-dub');
      setTranslationPrompt('');
    } else if (presetId === 'vlog-ducking') {
      setWhisperModel('base');
      setTranslationEngine('gemini');
      setContentGenre('conversational');
      setTranslationStyle('natural');
      setDubbingEngine('edge-tts');
      setVoiceMode('voice-over');
      setDuckingLevel(0.15);
      setTranslationPrompt('Friendly casual tone, natural colloquial Khmer');
      if (targetLanguage === 'km') {
        setSelectedVoice('km-KH-SreymomNeural');
      }
    }
  };

  const getTranslationEngineDisplay = () => {
    switch (translationEngine) {
      case 'gemini': return { name: 'Google Gemini 2.0', badge: '⭐ Recommended' };
      case 'openai': return { name: 'OpenAI GPT-4o', badge: 'Cloud' };
      case 'deepseek': return { name: 'DeepSeek V3', badge: '🇨🇳 Chinese Specialist' };
      case 'smart-contextual': return { name: 'Smart Contextual', badge: '🌐 Free Offline' };
      case 'local-llm': return { name: 'Local Ollama LLM', badge: '🖥️ Local' };
      case 'google-translate': return { name: 'Google NMT', badge: 'Fast Web' };
      default: return { name: translationEngine, badge: '' };
    }
  };

  const getEngineKeyStatus = () => {
    if (translationEngine === 'smart-contextual' || translationEngine === 'google-translate') {
      return { ready: true, text: 'Free (No Key Needed)' };
    }
    if (translationEngine === 'local-llm') {
      return { ready: true, text: 'Local Endpoint' };
    }
    const hasKey = translationEngine === 'gemini' ? Boolean(settings.ai.geminiApiKey) :
                   translationEngine === 'openai' ? Boolean(settings.ai.openaiApiKey) :
                   translationEngine === 'deepseek' ? Boolean(settings.ai.deepseekApiKey) :
                   Boolean(settings.ai.translationApiKey);
    return hasKey ? { ready: true, text: 'API Configured ✓' } : { ready: false, text: '⚠️ Key Missing' };
  };

  const getDubbingEngineDisplay = () => {
    if (dubbingEngine === 'voxcpm') {
      const actorName = voxcpmActor === 'voice_clone_original'
        ? 'Clone Video Speaker'
        : voxcpmActor === 'voice_clone_custom'
        ? 'Custom Audio Clone'
        : clonedVoices.find(c => c.id === voxcpmActor)?.name
        ? `Clone: ${clonedVoices.find(c => c.id === voxcpmActor)?.name}`
        : voxcpmActors.find(a => a.id === voxcpmActor)?.name || voxcpmActor;
      return { name: 'OpenBMB VoxCPM', detail: actorName, isClone: true };
    }
    const voiceFriendly = voices.find(v => v.shortName === selectedVoice)?.friendlyName || selectedVoice.replace(/Neural$/, '');
    return { name: 'Edge-TTS Neural', detail: voiceFriendly || 'Neural Voice', isClone: false };
  };

  const hasExtractedWav = Boolean(
    activeProject?.stems?.originalAudioPath || extractionResult?.wavPath
  );

  const wavPath =
    extractionResult?.wavPath || activeProject?.stems?.originalAudioPath || '';

  const hasDubbedAudio = Boolean(activeProject?.stems?.dubbedVocalsPath);
  const dubbedPath = activeProject?.stems?.dubbedVocalsPath || '';

  const vStream = mediaProbe?.videoStreams?.[0];
  const aStream = mediaProbe?.audioStreams?.[0];

  const isAnyAiBusy = isPipelineRunning || isTranscribing || isTranslating || isDubbing || isExtractingAudio;

  const targetLanguages = [
    { code: 'km', name: 'Khmer (ភាសាខ្មែរ)' },
    { code: 'en', name: 'English' },
    { code: 'zh-CN', name: 'Chinese (中文)' },
    { code: 'ja', name: 'Japanese (日本語)' },
    { code: 'ko', name: 'Korean (한국어)' },
    { code: 'th', name: 'Thai (ภาษาไทย)' },
    { code: 'vi', name: 'Vietnamese (Tiếng Việt)' },
    { code: 'es', name: 'Spanish (Español)' },
    { code: 'fr', name: 'French (Français)' },
    { code: 'de', name: 'German (Deutsch)' },
  ];

  return (
    <div
      className="media-inspector-panel"
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        backgroundColor: '#0c0e15',
        borderRadius: '10px',
        border: '1px solid var(--border-subtle)',
        overflow: 'hidden',
      }}
    >
      {/* Panel Header & Navigation Tabs */}
      <div
        style={{
          display: 'flex',
          borderBottom: '1px solid var(--border-subtle)',
          backgroundColor: '#090b10',
          padding: '4px',
          gap: '4px',
        }}
      >
        <button
          onClick={() => setActiveTab('inspector')}
          style={{
            flex: 1,
            padding: '8px 10px',
            fontSize: '12px',
            fontWeight: 600,
            borderRadius: '6px',
            border: 'none',
            backgroundColor: activeTab === 'inspector' ? 'var(--bg-card)' : 'transparent',
            color: activeTab === 'inspector' ? 'var(--accent-cyan)' : 'var(--text-secondary)',
            cursor: 'pointer',
            transition: 'all 0.15s ease',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '6px',
          }}
        >
          <span>🔍</span> Info
        </button>

        <button
          onClick={() => setActiveTab('stems')}
          style={{
            flex: 1,
            padding: '8px 10px',
            fontSize: '12px',
            fontWeight: 600,
            borderRadius: '6px',
            border: 'none',
            backgroundColor: activeTab === 'stems' ? 'var(--bg-card)' : 'transparent',
            color: activeTab === 'stems' ? 'var(--accent-cyan)' : 'var(--text-secondary)',
            cursor: 'pointer',
            transition: 'all 0.15s ease',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '6px',
          }}
        >
          <span>⚡</span> AI Dubbing
        </button>

        <button
          onClick={() => setActiveTab('subtitles')}
          style={{
            flex: 1,
            padding: '8px 10px',
            fontSize: '12px',
            fontWeight: 600,
            borderRadius: '6px',
            border: 'none',
            backgroundColor: activeTab === 'subtitles' ? 'var(--bg-card)' : 'transparent',
            color: activeTab === 'subtitles' ? 'var(--accent-cyan)' : 'var(--text-secondary)',
            cursor: 'pointer',
            transition: 'all 0.15s ease',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '6px',
          }}
        >
          <span>💬</span> Subtitles {activeProject?.segments && activeProject.segments.length > 0 ? `(${activeProject.segments.length})` : ''}
        </button>
      </div>

      {/* Tab Body */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px' }}>
        {/* TAB 1: STREAM INSPECTOR */}
        {activeTab === 'inspector' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {/* Media Metadata Card */}
            <div
              style={{
                backgroundColor: 'rgba(255, 255, 255, 0.02)',
                borderRadius: '8px',
                border: '1px solid var(--border-subtle)',
                padding: '14px',
              }}
            >
              <h4
                style={{
                  fontSize: '13px',
                  fontWeight: 600,
                  color: 'var(--text-primary)',
                  marginBottom: '10px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                <span>Container & File</span>
                {isProbing && <span style={{ fontSize: '11px', color: 'var(--accent-cyan)' }}>Probing...</span>}
              </h4>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '12px' }}>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Format: </span>
                  <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>
                    {mediaProbe?.formatName || activeProject?.sourceMedia?.codec || 'MP4 / Matroska'}
                  </span>
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Duration: </span>
                  <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>
                    {formatDuration(mediaProbe?.durationSeconds || activeProject?.sourceMedia?.durationSeconds || 0)}
                  </span>
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>File Size: </span>
                  <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>
                    {((mediaProbe?.fileSizeBytes || activeProject?.sourceMedia?.fileSizeBytes || 0) / 1024 / 1024).toFixed(1)} MB
                  </span>
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Bitrate: </span>
                  <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>
                    {mediaProbe?.overallBitrate
                      ? `${Math.round(mediaProbe.overallBitrate / 1000)} kbps`
                      : 'Auto'}
                  </span>
                </div>
              </div>
            </div>

            {/* Video Stream Card */}
            <div
              style={{
                backgroundColor: 'rgba(255, 255, 255, 0.02)',
                borderRadius: '8px',
                border: '1px solid var(--border-subtle)',
                padding: '14px',
              }}
            >
              <h4
                style={{
                  fontSize: '13px',
                  fontWeight: 600,
                  color: 'var(--text-primary)',
                  marginBottom: '10px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <span>📹 Video Stream</span>
                {vStream && (
                  <span
                    style={{
                      fontSize: '10px',
                      padding: '1px 6px',
                      borderRadius: '4px',
                      backgroundColor: 'rgba(0, 240, 255, 0.15)',
                      color: 'var(--accent-cyan)',
                    }}
                  >
                    #{vStream.index} {vStream.codecName.toUpperCase()}
                  </span>
                )}
              </h4>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '12px' }}>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Resolution: </span>
                  <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>
                    {vStream?.width && vStream?.height
                      ? `${vStream.width} × ${vStream.height}`
                      : activeProject?.sourceMedia?.resolution
                      ? `${activeProject.sourceMedia.resolution.width} × ${activeProject.sourceMedia.resolution.height}`
                      : 'Unknown'}
                  </span>
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Framerate: </span>
                  <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>
                    {vStream?.fps
                      ? `${vStream.fps} FPS`
                      : activeProject?.sourceMedia?.fps
                      ? `${activeProject.sourceMedia.fps} FPS`
                      : '30 FPS'}
                  </span>
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Codec: </span>
                  <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>
                    {vStream?.codecName || 'h264'}
                  </span>
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Stream Bitrate: </span>
                  <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>
                    {vStream?.bitrate ? `${Math.round(vStream.bitrate / 1000)} kbps` : 'VBR'}
                  </span>
                </div>
              </div>
            </div>

            {/* Audio Stream Card */}
            <div
              style={{
                backgroundColor: 'rgba(255, 255, 255, 0.02)',
                borderRadius: '8px',
                border: '1px solid var(--border-subtle)',
                padding: '14px',
              }}
            >
              <h4
                style={{
                  fontSize: '13px',
                  fontWeight: 600,
                  color: 'var(--text-primary)',
                  marginBottom: '10px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <span>🔊 Audio Stream</span>
                {aStream && (
                  <span
                    style={{
                      fontSize: '10px',
                      padding: '1px 6px',
                      borderRadius: '4px',
                      backgroundColor: 'rgba(139, 92, 246, 0.15)',
                      color: 'var(--accent-purple)',
                    }}
                  >
                    #{aStream.index} {aStream.codecName.toUpperCase()}
                  </span>
                )}
              </h4>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '12px' }}>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Codec: </span>
                  <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>
                    {aStream?.codecName || 'aac'}
                  </span>
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Sample Rate: </span>
                  <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>
                    {aStream?.sampleRate
                      ? `${aStream.sampleRate} Hz`
                      : `${activeProject?.sourceMedia?.audioSampleRate || 44100} Hz`}
                  </span>
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Channels: </span>
                  <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>
                    {aStream?.channels
                      ? `${aStream.channels} Ch (${aStream.channelLayout || 'stereo'})`
                      : '2 Ch (stereo)'}
                  </span>
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Bitrate: </span>
                  <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>
                    {aStream?.bitrate ? `${Math.round(aStream.bitrate / 1000)} kbps` : '192 kbps'}
                  </span>
                </div>
              </div>
            </div>

            {/* Captured Snapshots Gallery */}
            {snapshots.length > 0 && (
              <div
                style={{
                  backgroundColor: 'rgba(255, 255, 255, 0.02)',
                  borderRadius: '8px',
                  border: '1px solid var(--border-subtle)',
                  padding: '14px',
                }}
              >
                <h4 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '10px' }}>
                  📸 Captured Frames ({snapshots.length})
                </h4>
                <div style={{ display: 'flex', gap: '8px', overflowX: 'auto', paddingBottom: '4px' }}>
                  {snapshots.map((snap, idx) => (
                    <div
                      key={idx}
                      style={{
                        minWidth: '80px',
                        backgroundColor: '#000',
                        borderRadius: '6px',
                        overflow: 'hidden',
                        border: '1px solid var(--border-subtle)',
                      }}
                    >
                      <div
                        style={{
                          fontSize: '9px',
                          color: 'var(--accent-cyan)',
                          padding: '2px 4px',
                          textAlign: 'center',
                          backgroundColor: '#0a0d14',
                        }}
                      >
                        {snap.timestampSeconds.toFixed(2)}s
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* TAB 2: AI DUBBING & AUDIO STEMS */}
        {activeTab === 'stems' && (() => {
          const transInfo = getTranslationEngineDisplay();
          const keyStatus = getEngineKeyStatus();
          const dubInfo = getDubbingEngineDisplay();

          return (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {/* ================================================================= */}
              {/* 1. ACTIVE PIPELINE ENGINE BLUEPRINT (LIVE ENGINE HUD) */}
              {/* ================================================================= */}
              <div
                style={{
                  background: 'linear-gradient(135deg, rgba(10, 15, 25, 0.95) 0%, rgba(15, 20, 35, 0.95) 100%)',
                  borderRadius: '10px',
                  border: '1px solid rgba(0, 240, 255, 0.35)',
                  padding: '14px',
                  boxShadow: '0 4px 20px rgba(0, 0, 0, 0.4)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '10px',
                }}
              >
                {/* HUD Header */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span
                      style={{
                        display: 'inline-block',
                        width: '8px',
                        height: '8px',
                        borderRadius: '50%',
                        backgroundColor: '#00ff88',
                        boxShadow: '0 0 10px #00ff88',
                      }}
                    />
                    <span style={{ fontSize: '11px', fontWeight: 700, letterSpacing: '0.6px', textTransform: 'uppercase', color: 'var(--text-primary)' }}>
                      Active Engine Blueprint
                    </span>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span
                      style={{
                        fontSize: '10px',
                        fontWeight: 700,
                        padding: '2px 8px',
                        borderRadius: '12px',
                        backgroundColor: 'rgba(0, 240, 255, 0.12)',
                        color: 'var(--accent-cyan)',
                        border: '1px solid rgba(0, 240, 255, 0.3)',
                      }}
                    >
                      {(activeProject?.sourceLanguage || 'EN').toUpperCase()} ➔ {targetLanguage.toUpperCase()}
                    </span>
                    <span
                      style={{
                        fontSize: '10px',
                        fontWeight: 600,
                        padding: '2px 8px',
                        borderRadius: '12px',
                        backgroundColor: hasDubbedAudio ? 'rgba(0, 255, 136, 0.15)' : 'rgba(255, 170, 0, 0.15)',
                        color: hasDubbedAudio ? 'var(--status-success)' : 'var(--status-warning)',
                        border: `1px solid ${hasDubbedAudio ? 'rgba(0, 255, 136, 0.3)' : 'rgba(255, 170, 0, 0.3)'}`,
                      }}
                    >
                      {hasDubbedAudio ? '✓ Track Ready' : 'Ready to Dub'}
                    </span>
                  </div>
                </div>

                {/* Live Connected Nodes */}
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '1fr 1fr',
                    gap: '8px',
                    backgroundColor: '#05070c',
                    borderRadius: '8px',
                    padding: '10px',
                    border: '1px solid rgba(255, 255, 255, 0.06)',
                  }}
                >
                  {/* Node 1: STT Engine */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                    <span style={{ fontSize: '9px', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600 }}>
                      1. STT Engine
                    </span>
                    <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--accent-cyan)' }}>
                      🎙️ Whisper ({whisperModel.toUpperCase()})
                    </span>
                    <span style={{ fontSize: '9px', color: 'var(--text-muted)' }}>
                      Local Faster-Whisper
                    </span>
                  </div>

                  {/* Node 2: Translation Engine */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                    <span style={{ fontSize: '9px', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600 }}>
                      2. Translation Engine
                    </span>
                    <span style={{ fontSize: '11px', fontWeight: 600, color: '#c084fc' }}>
                      🧠 {transInfo.name}
                    </span>
                    <span style={{ fontSize: '9px', color: keyStatus.ready ? '#00ff88' : '#ffaa00', fontWeight: 500 }}>
                      {keyStatus.text}
                    </span>
                  </div>

                  {/* Node 3: Dubbing Engine */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                    <span style={{ fontSize: '9px', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600 }}>
                      3. Voice Synthesis
                    </span>
                    <span style={{ fontSize: '11px', fontWeight: 600, color: dubInfo.isClone ? '#e9d5ff' : 'var(--accent-cyan)' }}>
                      {dubInfo.isClone ? '🧬' : '🗣️'} {dubInfo.name}
                    </span>
                    <span style={{ fontSize: '9px', color: 'var(--text-secondary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {dubInfo.detail}
                    </span>
                  </div>

                  {/* Node 4: Tone & Audio Mix */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                    <span style={{ fontSize: '9px', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600 }}>
                      4. Narrative & Audio
                    </span>
                    <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--status-success)' }}>
                      🎭 {contentGenre.toUpperCase()}
                    </span>
                    <span style={{ fontSize: '9px', color: 'var(--text-muted)' }}>
                      {voiceMode === 'clean-dub' ? '🎧 Clean Dub (Mutes Org)' : voiceMode === 'voice-over' ? '🎙️ Auto-Ducking' : voiceMode}
                    </span>
                  </div>
                </div>

                {/* Subtitle Path Summary */}
                <div style={{ fontSize: '10px', color: 'var(--text-muted)', borderTop: '1px solid rgba(255, 255, 255, 0.05)', paddingTop: '6px' }}>
                  <span style={{ color: 'var(--accent-cyan)', fontWeight: 600 }}>Active Route: </span>
                  Whisper ({whisperModel}) ➔ {transInfo.name} ({contentGenre}) ➔ {dubInfo.detail} ➔ {voiceMode}
                </div>
              </div>

              {/* ================================================================= */}
              {/* 2. MODE TOGGLE: QUICK DUB VS ADVANCED PIPELINE */}
              {/* ================================================================= */}
              <div
                style={{
                  display: 'flex',
                  backgroundColor: '#06080e',
                  padding: '3px',
                  borderRadius: '8px',
                  border: '1px solid var(--border-subtle)',
                }}
              >
                <button
                  type="button"
                  onClick={() => setDubbingMode('quick')}
                  style={{
                    flex: 1,
                    padding: '8px 10px',
                    fontSize: '11px',
                    fontWeight: 700,
                    borderRadius: '6px',
                    border: 'none',
                    backgroundColor: dubbingMode === 'quick' ? 'rgba(0, 240, 255, 0.16)' : 'transparent',
                    color: dubbingMode === 'quick' ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px',
                    transition: 'all 0.15s ease',
                  }}
                >
                  <span>⚡ Quick Dub</span>
                  <span style={{ fontSize: '9px', padding: '1px 5px', borderRadius: '4px', backgroundColor: 'rgba(0, 240, 255, 0.2)', color: '#fff' }}>Presets</span>
                </button>

                <button
                  type="button"
                  onClick={() => setDubbingMode('advanced')}
                  style={{
                    flex: 1,
                    padding: '8px 10px',
                    fontSize: '11px',
                    fontWeight: 700,
                    borderRadius: '6px',
                    border: 'none',
                    backgroundColor: dubbingMode === 'advanced' ? 'rgba(192, 132, 252, 0.18)' : 'transparent',
                    color: dubbingMode === 'advanced' ? '#d8b4fe' : 'var(--text-secondary)',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px',
                    transition: 'all 0.15s ease',
                  }}
                >
                  <span>🛠️ Advanced Pipeline</span>
                  <span style={{ fontSize: '9px', padding: '1px 5px', borderRadius: '4px', backgroundColor: 'rgba(192, 132, 252, 0.25)', color: '#fff' }}>4 Stages</span>
                </button>
              </div>

              {/* ================================================================= */}
              {/* SUBVIEW A: QUICK DUB (PRESETS & STREAMLINED 1-CLICK) */}
              {/* ================================================================= */}
              {dubbingMode === 'quick' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                  {/* Curated 1-Click Studio Presets */}
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                      <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                        1-Click Studio Presets
                      </span>
                      <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                        Selects optimal engines automatically
                      </span>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                      {[
                        {
                          id: 'documentary',
                          icon: '🦁',
                          title: 'Khmer Documentary',
                          desc: 'Gemini 2.0 + NatGeo Narration + Piseth Voice',
                          badge: 'Broadcast',
                        },
                        {
                          id: 'fast-free',
                          icon: '⚡',
                          title: 'Fast & Free Neural',
                          desc: 'Smart Contextual + 100% Free Offline STT',
                          badge: 'No API Key',
                        },
                        {
                          id: 'voice-clone',
                          icon: '🧬',
                          title: 'Speaker Voice Clone',
                          desc: 'OpenBMB VoxCPM + Original Speaker Timbre',
                          badge: 'Zero-Shot',
                        },
                        {
                          id: 'vlog-ducking',
                          icon: '💬',
                          title: 'Vlog & Interview',
                          desc: 'Gemini 2.0 + Auto-Ducking Voice-Over',
                          badge: 'Auto-Ducking',
                        },
                      ].map((preset) => {
                        const isSel = activePreset === preset.id;
                        return (
                          <button
                            key={preset.id}
                            type="button"
                            onClick={() => applyPreset(preset.id)}
                            disabled={isAnyAiBusy}
                            style={{
                              padding: '10px',
                              borderRadius: '8px',
                              border: isSel ? '1px solid var(--accent-cyan)' : '1px solid var(--border-subtle)',
                              backgroundColor: isSel ? 'rgba(0, 240, 255, 0.1)' : '#07090f',
                              cursor: 'pointer',
                              textAlign: 'left',
                              display: 'flex',
                              flexDirection: 'column',
                              gap: '4px',
                              transition: 'all 0.15s ease',
                              boxShadow: isSel ? '0 0 12px rgba(0, 240, 255, 0.15)' : 'none',
                            }}
                          >
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <span style={{ fontSize: '12px', fontWeight: 700, color: isSel ? 'var(--accent-cyan)' : 'var(--text-primary)' }}>
                                {preset.icon} {preset.title}
                              </span>
                              <span
                                style={{
                                  fontSize: '8px',
                                  padding: '1px 5px',
                                  borderRadius: '4px',
                                  backgroundColor: isSel ? 'rgba(0, 240, 255, 0.25)' : 'rgba(255, 255, 255, 0.06)',
                                  color: isSel ? 'var(--accent-cyan)' : 'var(--text-muted)',
                                  fontWeight: 600,
                                }}
                              >
                                {preset.badge}
                              </span>
                            </div>
                            <span style={{ fontSize: '10px', color: 'var(--text-secondary)', lineHeight: 1.3 }}>
                              {preset.desc}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  {/* Primary Simple Controls */}
                  <div
                    style={{
                      backgroundColor: '#07090f',
                      borderRadius: '8px',
                      border: '1px solid var(--border-subtle)',
                      padding: '12px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '10px',
                    }}
                  >
                    {/* Target Language */}
                    <div>
                      <label style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block', marginBottom: '4px', fontWeight: 600 }}>
                        Target Language
                      </label>
                      <select
                        value={targetLanguage}
                        onChange={(e) => setTargetLanguage(e.target.value)}
                        disabled={isAnyAiBusy}
                        style={{
                          width: '100%',
                          backgroundColor: '#0a0d14',
                          color: 'var(--text-primary)',
                          border: '1px solid var(--border-subtle)',
                          borderRadius: '6px',
                          padding: '7px 10px',
                          fontSize: '12px',
                        }}
                      >
                        {targetLanguages.map(l => (
                          <option key={l.code} value={l.code}>{l.name}</option>
                        ))}
                      </select>
                    </div>

                    {/* Narrator Voice */}
                    <div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                        <label style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>
                          Narrator Voice / Actor
                        </label>
                        <span style={{ fontSize: '10px', color: dubbingEngine === 'voxcpm' ? '#d8b4fe' : 'var(--accent-cyan)' }}>
                          {dubbingEngine === 'voxcpm' ? '🎙️ VoxCPM Engine' : '⚡ Edge-TTS Engine'}
                        </span>
                      </div>

                      {dubbingEngine === 'voxcpm' ? (
                        <select
                          value={voxcpmActor}
                          onChange={(e) => {
                            const val = e.target.value;
                            setVoxcpmActor(val);
                            const foundClone = clonedVoices.find(c => c.id === val);
                            if (foundClone) {
                              setReferenceAudioPath(foundClone.audioPath || foundClone.referenceAudioPath || '');
                            }
                          }}
                          disabled={isAnyAiBusy}
                          style={{
                            width: '100%',
                            backgroundColor: '#0a0d14',
                            color: '#e9d5ff',
                            border: '1px solid rgba(192, 132, 252, 0.5)',
                            borderRadius: '6px',
                            padding: '7px 10px',
                            fontSize: '12px',
                          }}
                        >
                          {clonedVoices.length > 0 && (
                            <optgroup label="👤 Your Cloned Voice Profiles">
                              {clonedVoices.map(c => (
                                <option key={c.id} value={c.id}>
                                  ⭐ {c.name} {c.gender ? `(${c.gender})` : ''}
                                </option>
                              ))}
                            </optgroup>
                          )}
                          <optgroup label="🧬 Zero-Shot Voice Cloning">
                            <option value="voice_clone_original">⚡ Clone from Original Video Speaker</option>
                            <option value="voice_clone_custom">📁 Custom Uploaded Reference Audio</option>
                          </optgroup>
                          <optgroup label="🇰🇭 Khmer Native Voice Actors">
                            <option value="khmer_piseth_actor">Master Piseth — Khmer Host (ពិសិដ្ឋ)</option>
                            <option value="khmer_sreymom_actor">Sreymom — Expressive Host (ស្រីមុំ)</option>
                            <option value="khmer_storyteller">Lok Ta — Elder Storyteller (លោកតា)</option>
                            <option value="khmer_young_male">Sokha — Dynamic Tech Reviewer (សុខា)</option>
                            <option value="khmer_expressive_female">Kolap — Gentle Documentary (កុលាប)</option>
                          </optgroup>
                          <optgroup label="🎬 International Narrators">
                            <option value="cinematic_narrator">Marcus Vance — Movie & Trailer</option>
                            <option value="documentary_storyteller">David Attenborough — Natural Historian</option>
                            <option value="tech_reviewer">Alex Mercer — Dynamic Tech Host</option>
                          </optgroup>
                        </select>
                      ) : (
                        <select
                          value={selectedVoice}
                          onChange={(e) => setSelectedVoice(e.target.value)}
                          disabled={isAnyAiBusy}
                          style={{
                            width: '100%',
                            backgroundColor: '#0a0d14',
                            color: 'var(--text-primary)',
                            border: '1px solid var(--border-subtle)',
                            borderRadius: '6px',
                            padding: '7px 10px',
                            fontSize: '12px',
                          }}
                        >
                          {voices.length > 0 ? (
                            voices.map(v => (
                              <option key={v.shortName} value={v.shortName}>
                                {v.shortName.replace(/Neural$/, '')} ({v.gender})
                              </option>
                            ))
                          ) : (
                            <option value={selectedVoice}>{selectedVoice}</option>
                          )}
                        </select>
                      )}
                    </div>
                  </div>

                  {/* Progress Bar & Status Message */}
                  {isAnyAiBusy && aiProgress && (
                    <div style={{ backgroundColor: '#07090f', padding: '10px', borderRadius: '8px', border: '1px solid rgba(0, 240, 255, 0.3)' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginBottom: '4px' }}>
                        <span style={{ color: 'var(--accent-cyan)', fontWeight: 700, textTransform: 'capitalize' }}>
                          ⚡ {aiProgress.stage}...
                        </span>
                        <span style={{ color: 'var(--text-primary)', fontWeight: 700 }}>
                          {aiProgress.percent}%
                        </span>
                      </div>
                      <div style={{ width: '100%', height: '6px', backgroundColor: '#000', borderRadius: '3px', overflow: 'hidden' }}>
                        <div
                          style={{
                            width: `${Math.max(5, aiProgress.percent)}%`,
                            height: '100%',
                            background: 'linear-gradient(90deg, var(--accent-cyan), var(--accent-purple))',
                            transition: 'width 0.3s ease',
                          }}
                        />
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '5px' }}>
                        {aiProgress.message}
                      </div>
                    </div>
                  )}

                  {/* Master 1-Click Run Button */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    <button
                      className="btn btn-primary"
                      onClick={runFullAiPipeline}
                      disabled={isAnyAiBusy || !activeProject?.sourceMedia?.pathOrUrl}
                      style={{
                        width: '100%',
                        fontSize: '13px',
                        fontWeight: 700,
                        padding: '12px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '8px',
                        background: 'linear-gradient(135deg, var(--accent-cyan) 0%, var(--accent-purple) 100%)',
                        border: 'none',
                        color: '#fff',
                        cursor: isAnyAiBusy ? 'not-allowed' : 'pointer',
                        opacity: isAnyAiBusy ? 0.7 : 1,
                        boxShadow: '0 4px 16px rgba(0, 240, 255, 0.35)',
                        borderRadius: '8px',
                      }}
                    >
                      {isPipelineRunning ? (
                        <>
                          <span className="spinner-dots">●</span> Processing Full Pipeline...
                        </>
                      ) : hasDubbedAudio ? (
                        `⚡ Re-Dub Full Pipeline (${targetLanguage.toUpperCase()})`
                      ) : (
                        `⚡ 1-Click Auto Translate & Dub (${targetLanguage.toUpperCase()})`
                      )}
                    </button>
                    <span style={{ fontSize: '10px', color: 'var(--text-muted)', textAlign: 'center' }}>
                      Transcribes speech, translates to {targetLanguage.toUpperCase()}, and synthesizes timeline voice automatically
                    </span>
                  </div>

                  {/* Quick Individual Operations */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '6px' }}>
                    <button
                      className="btn btn-outline"
                      onClick={transcribeSpeech}
                      disabled={isAnyAiBusy || !activeProject?.sourceMedia?.pathOrUrl}
                      style={{ fontSize: '11px', padding: '6px 4px' }}
                      title="Run Whisper STT transcription only"
                    >
                      {isTranscribing ? 'Transcribing...' : '🎙️ Transcribe'}
                    </button>

                    <button
                      className="btn btn-outline"
                      onClick={() => translateSubtitles(targetLanguage)}
                      disabled={isAnyAiBusy || !activeProject?.segments || activeProject.segments.length === 0}
                      style={{ fontSize: '11px', padding: '6px 4px' }}
                      title="Translate existing subtitles"
                    >
                      {isTranslating ? 'Translating...' : '🌐 Translate'}
                    </button>

                    <button
                      className="btn btn-outline"
                      onClick={() => generateDubbing(dubbingEngine === 'voxcpm' ? voxcpmActor : selectedVoice)}
                      disabled={isAnyAiBusy || !activeProject?.segments || activeProject.segments.length === 0}
                      style={{ fontSize: '11px', padding: '6px 4px' }}
                      title="Synthesize voice dubbing audio"
                    >
                      {isDubbing ? 'Dubbing...' : '🗣️ Dub Voice'}
                    </button>
                  </div>

                  {/* Master Dub Track Info */}
                  {hasDubbedAudio && (
                    <div
                      style={{
                        backgroundColor: '#06080d',
                        padding: '8px 10px',
                        borderRadius: '6px',
                        border: '1px solid rgba(0, 255, 136, 0.25)',
                        fontSize: '11px',
                        color: 'var(--status-success)',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '2px',
                      }}
                    >
                      <span style={{ fontWeight: 700 }}>🔊 Master Dubbed Audio Ready:</span>
                      <span style={{ fontFamily: 'monospace', color: 'var(--text-muted)', fontSize: '10px', wordBreak: 'break-all' }}>
                        {dubbedPath}
                      </span>
                    </div>
                  )}

                  {/* Helpful Guide Footer */}
                  <div
                    style={{
                      padding: '10px 12px',
                      borderRadius: '6px',
                      backgroundColor: 'rgba(255, 255, 255, 0.02)',
                      border: '1px dashed var(--border-subtle)',
                      fontSize: '11px',
                      color: 'var(--text-muted)',
                      lineHeight: 1.4,
                    }}
                  >
                    💡 Want to change Whisper model size, configure API keys, add custom translation glossary rules, or balance audio stems? Switch to <span style={{ color: '#d8b4fe', fontWeight: 600, cursor: 'pointer' }} onClick={() => setDubbingMode('advanced')}>🛠️ Advanced Pipeline</span> above.
                  </div>
                </div>
              )}

              {/* ================================================================= */}
              {/* SUBVIEW B: ADVANCED PIPELINE (4 SEQUENTIAL STAGES) */}
              {/* ================================================================= */}
              {dubbingMode === 'advanced' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {/* STAGE 1: SPEECH-TO-TEXT (WHISPER) */}
                  <div
                    style={{
                      backgroundColor: '#07090f',
                      borderRadius: '8px',
                      border: '1px solid var(--border-subtle)',
                      overflow: 'hidden',
                    }}
                  >
                    <div
                      onClick={() => toggleStage(1)}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '10px 14px',
                        cursor: 'pointer',
                        backgroundColor: openStages[1] ? 'rgba(0, 240, 255, 0.06)' : 'transparent',
                        borderBottom: openStages[1] ? '1px solid var(--border-subtle)' : 'none',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontSize: '14px' }}>🎙️</span>
                        <div>
                          <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-primary)' }}>
                            Stage 1: Speech-to-Text (Whisper)
                          </span>
                        </div>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontSize: '10px', color: 'var(--accent-cyan)', fontWeight: 600 }}>
                          Model: {whisperModel.toUpperCase()}
                        </span>
                        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                          {openStages[1] ? '▲' : '▼'}
                        </span>
                      </div>
                    </div>

                    {openStages[1] && (
                      <div style={{ padding: '14px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                        <p style={{ fontSize: '11px', color: 'var(--text-secondary)', margin: 0 }}>
                          Transcribes spoken audio into timestamped dialogue segments with local Faster-Whisper.
                        </p>

                        {/* Model Size */}
                        <div>
                          <label style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block', marginBottom: '5px' }}>
                            Whisper Model Size
                          </label>
                          <div style={{ display: 'flex', gap: '6px' }}>
                            {[
                              { id: 'tiny', label: 'TINY', desc: 'Fastest CPU' },
                              { id: 'base', label: 'BASE', desc: 'Balanced' },
                              { id: 'small', label: 'SMALL', desc: 'Accurate' },
                            ].map((m) => {
                              const isSel = whisperModel === m.id;
                              return (
                                <button
                                  key={m.id}
                                  type="button"
                                  onClick={() => setWhisperModel(m.id as any)}
                                  disabled={isAnyAiBusy}
                                  style={{
                                    flex: 1,
                                    padding: '6px 8px',
                                    fontSize: '11px',
                                    borderRadius: '6px',
                                    border: isSel ? '1px solid var(--accent-cyan)' : '1px solid var(--border-subtle)',
                                    backgroundColor: isSel ? 'rgba(0, 240, 255, 0.15)' : '#0a0d14',
                                    color: isSel ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                                    cursor: 'pointer',
                                    fontWeight: isSel ? 700 : 400,
                                    display: 'flex',
                                    flexDirection: 'column',
                                    alignItems: 'center',
                                    gap: '2px',
                                  }}
                                >
                                  <span>{m.label}</span>
                                  <span style={{ fontSize: '8px', color: isSel ? '#80f5ff' : 'var(--text-muted)' }}>{m.desc}</span>
                                </button>
                              );
                            })}
                          </div>
                        </div>

                        {/* 16kHz Extraction & Action */}
                        <div style={{ display: 'flex', gap: '8px' }}>
                          <button
                            className="btn btn-outline"
                            onClick={extractSpeechAudio}
                            disabled={isAnyAiBusy || !activeProject?.sourceMedia?.pathOrUrl}
                            style={{ flex: 1, fontSize: '11px', padding: '7px' }}
                          >
                            {isExtractingAudio ? 'Extracting...' : hasExtractedWav ? '✓ 16k WAV Ready' : '🎙️ Extract 16k WAV'}
                          </button>

                          <button
                            className="btn btn-primary"
                            onClick={transcribeSpeech}
                            disabled={isAnyAiBusy || !activeProject?.sourceMedia?.pathOrUrl}
                            style={{ flex: 1, fontSize: '11px', padding: '7px' }}
                          >
                            {isTranscribing ? 'Transcribing...' : '🎙️ Transcribe Dialogue'}
                          </button>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* STAGE 2: AI TRANSLATION & TONE INTELLIGENCE */}
                  <div
                    style={{
                      backgroundColor: '#07090f',
                      borderRadius: '8px',
                      border: '1px solid var(--border-subtle)',
                      overflow: 'hidden',
                    }}
                  >
                    <div
                      onClick={() => toggleStage(2)}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '10px 14px',
                        cursor: 'pointer',
                        backgroundColor: openStages[2] ? 'rgba(192, 132, 252, 0.06)' : 'transparent',
                        borderBottom: openStages[2] ? '1px solid var(--border-subtle)' : 'none',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontSize: '14px' }}>🧠</span>
                        <div>
                          <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-primary)' }}>
                            Stage 2: AI Translation & Tone Intelligence
                          </span>
                        </div>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontSize: '10px', color: '#c084fc', fontWeight: 600 }}>
                          {transInfo.name} ({contentGenre})
                        </span>
                        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                          {openStages[2] ? '▲' : '▼'}
                        </span>
                      </div>
                    </div>

                    {openStages[2] && (
                      <div style={{ padding: '14px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                        {/* Translation Engine Selector */}
                        <div>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                            <span style={{ fontSize: '10px', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>
                              Select Translation Engine
                            </span>
                            <span style={{ fontSize: '10px', color: 'var(--accent-cyan)' }}>
                              {transInfo.badge}
                            </span>
                          </div>

                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '6px' }}>
                            {[
                              { id: 'gemini', label: '🌟 Gemini 2.0', badge: 'Recommended', desc: 'Google Gemini 2.0/1.5 Flash: World-class Khmer & Asian contextual phrasing' },
                              { id: 'openai', label: '🤖 OpenAI GPT-4o', badge: 'Cloud', desc: 'OpenAI GPT-4o-mini: High-accuracy narrative translation' },
                              { id: 'deepseek', label: '⚡ DeepSeek V3', badge: 'Chinese Specialist', desc: 'DeepSeek: Exceptional Chinese and English to Khmer idiomatic accuracy' },
                              { id: 'smart-contextual', label: '🌐 Smart Contextual', badge: 'Free / No Key', desc: 'Fast neural translation with built-in documentary glossary refiner' },
                              { id: 'local-llm', label: '🖥️ Local LLM', badge: 'Ollama', desc: 'Local private LLM running on your computer via Ollama or custom API' },
                              { id: 'google-translate', label: '⚡ Google NMT', badge: 'Fast Web', desc: 'Standard machine translation with Khmer linguistic post-processing' },
                            ].map((eng) => {
                              const isSel = translationEngine === eng.id;
                              return (
                                <button
                                  key={eng.id}
                                  type="button"
                                  onClick={() => setTranslationEngine(eng.id as any)}
                                  disabled={isAnyAiBusy}
                                  title={eng.desc}
                                  style={{
                                    padding: '7px 8px',
                                    fontSize: '10px',
                                    borderRadius: '6px',
                                    border: isSel ? '1px solid var(--accent-cyan)' : '1px solid var(--border-subtle)',
                                    backgroundColor: isSel ? 'rgba(0, 240, 255, 0.16)' : '#05070c',
                                    color: isSel ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                                    cursor: 'pointer',
                                    textAlign: 'left',
                                    display: 'flex',
                                    flexDirection: 'column',
                                    gap: '2px',
                                  }}
                                >
                                  <span style={{ fontWeight: isSel ? 700 : 500 }}>{eng.label}</span>
                                  <span style={{ fontSize: '8px', color: isSel ? '#80f5ff' : 'var(--text-muted)' }}>{eng.badge}</span>
                                </button>
                              );
                            })}
                          </div>
                        </div>

                        {/* API Key Status & 1-Click Test Connection Bar */}
                        {translationEngine !== 'smart-contextual' && translationEngine !== 'google-translate' && (
                          <div
                            style={{
                              backgroundColor: '#05070c',
                              borderRadius: '6px',
                              padding: '8px 10px',
                              border: '1px solid rgba(255, 255, 255, 0.08)',
                              display: 'flex',
                              flexDirection: 'column',
                              gap: '6px',
                            }}
                          >
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                                  {translationEngine === 'gemini' ? 'Gemini Key:' : translationEngine === 'openai' ? 'OpenAI Key:' : translationEngine === 'deepseek' ? 'DeepSeek Key:' : 'Endpoint:'}
                                </span>
                                <span style={{ fontSize: '10px', color: 'var(--text-primary)', fontFamily: 'monospace' }}>
                                  {translationEngine === 'gemini' && settings.ai.geminiApiKey ? `${settings.ai.geminiApiKey.substring(0, 7)}••••` :
                                   translationEngine === 'openai' && settings.ai.openaiApiKey ? `${settings.ai.openaiApiKey.substring(0, 7)}••••` :
                                   translationEngine === 'deepseek' && settings.ai.deepseekApiKey ? `${settings.ai.deepseekApiKey.substring(0, 7)}••••` :
                                   translationEngine === 'local-llm' ? (settings.ai.customLlmEndpoint || 'http://localhost:11434/v1') :
                                   settings.ai.translationApiKey ? `${settings.ai.translationApiKey.substring(0, 7)}••••` :
                                   <span style={{ color: '#ffaa00' }}>⚠️ No Key Set</span>}
                                </span>
                              </div>

                              <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                                <button
                                  type="button"
                                  onClick={() => {
                                    setIsEditingApiKey(!isEditingApiKey);
                                    const cur = translationEngine === 'gemini' ? settings.ai.geminiApiKey :
                                                translationEngine === 'openai' ? settings.ai.openaiApiKey :
                                                translationEngine === 'deepseek' ? settings.ai.deepseekApiKey :
                                                settings.ai.translationApiKey;
                                    setApiKeyInput(cur || '');
                                  }}
                                  style={{
                                    background: 'transparent',
                                    border: '1px solid var(--border-subtle)',
                                    color: 'var(--text-secondary)',
                                    borderRadius: '4px',
                                    padding: '2px 6px',
                                    fontSize: '10px',
                                    cursor: 'pointer',
                                  }}
                                >
                                  {isEditingApiKey ? 'Cancel' : 'Edit Key'}
                                </button>

                                <button
                                  type="button"
                                  onClick={async () => {
                                    setKeyTestState({ testing: true });
                                    try {
                                      const curKey = translationEngine === 'gemini' ? settings.ai.geminiApiKey :
                                                     translationEngine === 'openai' ? settings.ai.openaiApiKey :
                                                     translationEngine === 'deepseek' ? settings.ai.deepseekApiKey :
                                                     settings.ai.translationApiKey;
                                      const res = await testTranslationApiKey(translationEngine, curKey, settings.ai.customLlmEndpoint);
                                      setKeyTestState({
                                        testing: false,
                                        success: res.success,
                                        latencyMs: res.latencyMs,
                                        error: res.error,
                                      });
                                    } catch (err: any) {
                                      setKeyTestState({
                                        testing: false,
                                        success: false,
                                        error: err?.message || 'Connection test failed',
                                      });
                                    }
                                  }}
                                  disabled={keyTestState?.testing || isAnyAiBusy}
                                  style={{
                                    background: 'rgba(0, 240, 255, 0.1)',
                                    border: '1px solid rgba(0, 240, 255, 0.3)',
                                    color: 'var(--accent-cyan)',
                                    borderRadius: '4px',
                                    padding: '2px 8px',
                                    fontSize: '10px',
                                    cursor: 'pointer',
                                    fontWeight: 600,
                                  }}
                                >
                                  {keyTestState?.testing ? 'Testing...' : '⚡ Test Connection'}
                                </button>
                              </div>
                            </div>

                            {isEditingApiKey && (
                              <div style={{ display: 'flex', gap: '6px', marginTop: '4px' }}>
                                <input
                                  type="password"
                                  placeholder={translationEngine === 'gemini' ? 'Paste Gemini API Key (e.g. AIzaSy...)' : 'Paste API Key'}
                                  value={apiKeyInput}
                                  onChange={(e) => setApiKeyInput(e.target.value)}
                                  style={{
                                    flex: 1,
                                    backgroundColor: '#0a0d14',
                                    border: '1px solid var(--border-subtle)',
                                    borderRadius: '4px',
                                    color: '#fff',
                                    fontSize: '10px',
                                    padding: '4px 6px',
                                  }}
                                />
                                <button
                                  type="button"
                                  onClick={async () => {
                                    if (translationEngine === 'gemini') {
                                      await updateSettings({ ai: { ...settings.ai, geminiApiKey: apiKeyInput } });
                                    } else if (translationEngine === 'openai') {
                                      await updateSettings({ ai: { ...settings.ai, openaiApiKey: apiKeyInput } });
                                    } else if (translationEngine === 'deepseek') {
                                      await updateSettings({ ai: { ...settings.ai, deepseekApiKey: apiKeyInput } });
                                    } else {
                                      await updateSettings({ ai: { ...settings.ai, translationApiKey: apiKeyInput } });
                                    }
                                    setIsEditingApiKey(false);
                                    setKeyTestState(null);
                                  }}
                                  style={{
                                    backgroundColor: 'var(--accent-cyan)',
                                    color: '#000',
                                    fontWeight: 700,
                                    border: 'none',
                                    borderRadius: '4px',
                                    padding: '4px 10px',
                                    fontSize: '10px',
                                    cursor: 'pointer',
                                  }}
                                >
                                  Save
                                </button>
                              </div>
                            )}

                            {keyTestState && (
                              <div style={{ fontSize: '9px', marginTop: '2px' }}>
                                {keyTestState.testing && <span style={{ color: 'var(--accent-cyan)' }}>⏳ Testing API connectivity...</span>}
                                {keyTestState.success && (
                                  <span style={{ color: '#00ff88', fontWeight: 600 }}>
                                    ✓ Connected successfully ({keyTestState.latencyMs}ms latency)
                                  </span>
                                )}
                                {keyTestState.success === false && (
                                  <span style={{ color: '#ff4d4d' }}>
                                    ✕ Connection failed: {keyTestState.error || 'Invalid API key or network timeout'}.
                                  </span>
                                )}
                              </div>
                            )}
                          </div>
                        )}

                        {/* Video Content Genre & Tone */}
                        <div>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '5px' }}>
                            <span style={{ fontSize: '10px', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>
                              Video Narrative Genre & Tone
                            </span>
                            {detectedGenre && (
                              <span className="badge" style={{ backgroundColor: 'rgba(0, 255, 136, 0.1)', color: '#00ff88', fontSize: '9px', border: '1px solid rgba(0, 255, 136, 0.3)' }}>
                                ✨ Auto-Detected: {detectedGenre.toUpperCase()}
                              </span>
                            )}
                          </div>

                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '5px' }}>
                            {[
                              { id: 'documentary', label: '🦁 Documentary', kh: 'ភាពយន្តឯកសារ' },
                              { id: 'conversational', label: '💬 Vlog / Casual', kh: 'ការសន្ទនា' },
                              { id: 'cinematic', label: '🎬 Cinematic', kh: 'ភាពយន្ត' },
                              { id: 'news', label: '📰 News & Formal', kh: 'ព័ត៌មាន' },
                              { id: 'tutorial', label: '💻 Tech / Tutorial', kh: 'បច្ចេកវិទ្យា' },
                              { id: 'auto', label: '🔍 Auto-Detect', kh: 'ស្វ័យប្រវត្តិ' },
                            ].map((g) => {
                              const isSel = contentGenre === g.id;
                              return (
                                <button
                                  key={g.id}
                                  type="button"
                                  onClick={() => setContentGenre(g.id as any)}
                                  disabled={isAnyAiBusy}
                                  style={{
                                    padding: '6px 6px',
                                    fontSize: '10px',
                                    borderRadius: '6px',
                                    border: isSel ? '1px solid #c084fc' : '1px solid var(--border-subtle)',
                                    backgroundColor: isSel ? 'rgba(192, 132, 252, 0.16)' : '#05070c',
                                    color: isSel ? '#d8b4fe' : 'var(--text-secondary)',
                                    cursor: 'pointer',
                                    textAlign: 'left',
                                    display: 'flex',
                                    flexDirection: 'column',
                                    gap: '2px',
                                  }}
                                >
                                  <span style={{ fontWeight: isSel ? 700 : 500 }}>{g.label}</span>
                                  <span style={{ fontSize: '8px', color: isSel ? '#e9d5ff' : 'var(--text-muted)' }}>{g.kh}</span>
                                </button>
                              );
                            })}
                          </div>
                        </div>

                        {/* Delivery Style */}
                        <div>
                          <label style={{ fontSize: '10px', color: 'var(--text-muted)', display: 'block', marginBottom: '4px', fontWeight: 600, textTransform: 'uppercase' }}>
                            Delivery Phrasing & Syllables
                          </label>
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '4px' }}>
                            {[
                              { id: 'natural', label: '🌿 Natural' },
                              { id: 'formal', label: '👔 Dignified' },
                              { id: 'cinematic', label: '🎭 Evocative' },
                              { id: 'concise', label: '⏱️ Dub-Fit' },
                            ].map((st) => {
                              const isSel = translationStyle === st.id;
                              return (
                                <button
                                  key={st.id}
                                  type="button"
                                  onClick={() => setTranslationStyle(st.id as any)}
                                  disabled={isAnyAiBusy}
                                  style={{
                                    padding: '5px 4px',
                                    fontSize: '10px',
                                    borderRadius: '4px',
                                    border: isSel ? '1px solid var(--accent-cyan)' : '1px solid var(--border-subtle)',
                                    backgroundColor: isSel ? 'rgba(0, 240, 255, 0.14)' : '#05070c',
                                    color: isSel ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                                    cursor: 'pointer',
                                    textAlign: 'center',
                                    fontWeight: isSel ? 700 : 400,
                                  }}
                                >
                                  {st.label}
                                </button>
                              );
                            })}
                          </div>
                        </div>

                        {/* Custom Glossary Rules */}
                        <div>
                          <label style={{ fontSize: '10px', color: 'var(--text-muted)', display: 'block', marginBottom: '3px' }}>
                            Custom Phrasing Instructions / Vocabulary Rules (Optional)
                          </label>
                          <input
                            type="text"
                            placeholder="e.g. Wildlife documentary; keep predator names dignified; keep loan words clean"
                            value={translationPrompt}
                            onChange={(e) => setTranslationPrompt(e.target.value)}
                            disabled={isAnyAiBusy}
                            style={{
                              width: '100%',
                              backgroundColor: '#05070c',
                              color: 'var(--text-primary)',
                              border: '1px solid var(--border-subtle)',
                              borderRadius: '4px',
                              padding: '6px 8px',
                              fontSize: '11px',
                            }}
                          />
                        </div>

                        <button
                          className="btn btn-primary"
                          onClick={() => translateSubtitles(targetLanguage)}
                          disabled={isAnyAiBusy || !activeProject?.segments || activeProject.segments.length === 0}
                          style={{ width: '100%', fontSize: '11px', padding: '8px' }}
                        >
                          {isTranslating ? 'Translating...' : '🌐 Translate Subtitles Only'}
                        </button>
                      </div>
                    )}
                  </div>

                  {/* STAGE 3: VOICE DUBBING & AUDIO CLONING */}
                  <div
                    style={{
                      backgroundColor: '#07090f',
                      borderRadius: '8px',
                      border: '1px solid var(--border-subtle)',
                      overflow: 'hidden',
                    }}
                  >
                    <div
                      onClick={() => toggleStage(3)}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '10px 14px',
                        cursor: 'pointer',
                        backgroundColor: openStages[3] ? 'rgba(0, 240, 255, 0.06)' : 'transparent',
                        borderBottom: openStages[3] ? '1px solid var(--border-subtle)' : 'none',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontSize: '14px' }}>🗣️</span>
                        <div>
                          <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-primary)' }}>
                            Stage 3: Voice Dubbing & Audio Cloning
                          </span>
                        </div>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontSize: '10px', color: 'var(--accent-cyan)', fontWeight: 600 }}>
                          {dubInfo.name}
                        </span>
                        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                          {openStages[3] ? '▲' : '▼'}
                        </span>
                      </div>
                    </div>

                    {openStages[3] && (
                      <div style={{ padding: '14px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                        {/* Dubbing Engine Switcher */}
                        <div>
                          <label style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block', marginBottom: '4px', fontWeight: 600 }}>
                            Voice Synthesis Engine
                          </label>
                          <div style={{ display: 'flex', gap: '6px' }}>
                            <button
                              type="button"
                              onClick={() => setDubbingEngine('edge-tts')}
                              disabled={isAnyAiBusy}
                              style={{
                                flex: 1,
                                padding: '7px 8px',
                                fontSize: '11px',
                                borderRadius: '6px',
                                border: dubbingEngine === 'edge-tts' ? '1px solid var(--accent-cyan)' : '1px solid var(--border-subtle)',
                                backgroundColor: dubbingEngine === 'edge-tts' ? 'rgba(0, 240, 255, 0.15)' : '#05070c',
                                color: dubbingEngine === 'edge-tts' ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                                cursor: 'pointer',
                                fontWeight: dubbingEngine === 'edge-tts' ? 700 : 400,
                              }}
                            >
                              ⚡ Edge-TTS Neural
                            </button>

                            <button
                              type="button"
                              onClick={() => setDubbingEngine('voxcpm')}
                              disabled={isAnyAiBusy}
                              style={{
                                flex: 1,
                                padding: '7px 8px',
                                fontSize: '11px',
                                borderRadius: '6px',
                                border: dubbingEngine === 'voxcpm' ? '1px solid #c084fc' : '1px solid var(--border-subtle)',
                                backgroundColor: dubbingEngine === 'voxcpm' ? 'rgba(192, 132, 252, 0.2)' : '#05070c',
                                color: dubbingEngine === 'voxcpm' ? '#d8b4fe' : 'var(--text-secondary)',
                                cursor: 'pointer',
                                fontWeight: dubbingEngine === 'voxcpm' ? 700 : 400,
                              }}
                            >
                              🎙️ OpenBMB VoxCPM
                            </button>
                          </div>
                        </div>

                        {/* Voice / Actor Select */}
                        <div>
                          <label style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block', marginBottom: '4px', fontWeight: 600 }}>
                            {dubbingEngine === 'voxcpm' ? 'VoxCPM Actor / Clone' : 'Neural Voice'}
                          </label>
                          {dubbingEngine === 'voxcpm' ? (
                            <select
                              value={voxcpmActor}
                              onChange={(e) => {
                                const val = e.target.value;
                                setVoxcpmActor(val);
                                const foundClone = clonedVoices.find(c => c.id === val);
                                if (foundClone) {
                                  setReferenceAudioPath(foundClone.audioPath || foundClone.referenceAudioPath || '');
                                }
                              }}
                              disabled={isAnyAiBusy}
                              style={{
                                width: '100%',
                                backgroundColor: '#0a0d14',
                                color: '#e9d5ff',
                                border: '1px solid rgba(192, 132, 252, 0.5)',
                                borderRadius: '6px',
                                padding: '7px 10px',
                                fontSize: '12px',
                              }}
                            >
                              {clonedVoices.length > 0 && (
                                <optgroup label="👤 Your Cloned Voice Profiles">
                                  {clonedVoices.map(c => (
                                    <option key={c.id} value={c.id}>
                                      ⭐ {c.name} {c.gender ? `(${c.gender})` : ''}
                                    </option>
                                  ))}
                                </optgroup>
                              )}
                              <optgroup label="🧬 Zero-Shot Voice Cloning">
                                <option value="voice_clone_original">⚡ Clone from Original Video Speaker</option>
                                <option value="voice_clone_custom">📁 Custom Uploaded Audio File</option>
                              </optgroup>
                              <optgroup label="🇰🇭 Khmer Native Voice Actors">
                                <option value="khmer_piseth_actor">Master Piseth — Khmer Host (ពិសិដ្ឋ)</option>
                                <option value="khmer_sreymom_actor">Sreymom — Expressive Host (ស្រីមុំ)</option>
                                <option value="khmer_storyteller">Lok Ta — Elder Storyteller (លោកតា)</option>
                                <option value="khmer_young_male">Sokha — Dynamic Tech Reviewer (សុខា)</option>
                                <option value="khmer_expressive_female">Kolap — Gentle Documentary (កុលាប)</option>
                              </optgroup>
                              <optgroup label="🎬 International Narrators">
                                <option value="cinematic_narrator">Marcus Vance — Movie & Trailer</option>
                                <option value="documentary_storyteller">David Attenborough — Natural Historian</option>
                                <option value="tech_reviewer">Alex Mercer — Dynamic Tech Host</option>
                              </optgroup>
                            </select>
                          ) : (
                            <select
                              value={selectedVoice}
                              onChange={(e) => setSelectedVoice(e.target.value)}
                              disabled={isAnyAiBusy}
                              style={{
                                width: '100%',
                                backgroundColor: '#0a0d14',
                                color: 'var(--text-primary)',
                                border: '1px solid var(--border-subtle)',
                                borderRadius: '6px',
                                padding: '7px 10px',
                                fontSize: '12px',
                              }}
                            >
                              {voices.length > 0 ? (
                                voices.map(v => (
                                  <option key={v.shortName} value={v.shortName}>
                                    {v.shortName.replace(/Neural$/, '')} ({v.gender})
                                  </option>
                                ))
                              ) : (
                                <option value={selectedVoice}>{selectedVoice}</option>
                              )}
                            </select>
                          )}
                        </div>

                        {/* Reference Audio File for Cloning (VoxCPM) */}
                        {dubbingEngine === 'voxcpm' && (
                          <div
                            style={{
                              backgroundColor: '#05070c',
                              borderRadius: '6px',
                              border: '1px dashed rgba(192, 132, 252, 0.4)',
                              padding: '10px',
                              display: 'flex',
                              flexDirection: 'column',
                              gap: '8px',
                            }}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                              <span style={{ fontSize: '11px', fontWeight: 600, color: '#d8b4fe' }}>
                                🎵 Reference Audio for Voice Learning (3-15s)
                              </span>
                              <button
                                type="button"
                                onClick={async () => {
                                  const p = await selectReferenceAudioFile();
                                  if (p) {
                                    setVoxcpmActor('voice_clone_custom');
                                  }
                                }}
                                disabled={isAnyAiBusy}
                                style={{
                                  fontSize: '10px',
                                  padding: '4px 8px',
                                  backgroundColor: 'rgba(192, 132, 252, 0.2)',
                                  color: '#e9d5ff',
                                  border: '1px solid rgba(192, 132, 252, 0.4)',
                                  borderRadius: '4px',
                                  cursor: 'pointer',
                                  fontWeight: 600,
                                }}
                              >
                                📁 Choose File...
                              </button>
                            </div>

                            {referenceAudioPath ? (
                              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '11px' }}>
                                  <span style={{ color: 'var(--text-primary)', wordBreak: 'break-all', fontFamily: 'monospace' }}>
                                    ✓ {referenceAudioPath.split(/[\/\\]/).pop()}
                                  </span>
                                  <button
                                    type="button"
                                    onClick={() => setReferenceAudioPath('')}
                                    style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '11px' }}
                                  >
                                    ✕ Clear
                                  </button>
                                </div>
                                <audio controls src={toMediaUrl(referenceAudioPath)} style={{ width: '100%', height: '28px' }} />
                                <div style={{ display: 'flex', gap: '6px', marginTop: '2px' }}>
                                  <input
                                    type="text"
                                    placeholder="Profile name (e.g. Master Piseth Host)"
                                    value={newCloneName}
                                    onChange={(e) => setNewCloneName(e.target.value)}
                                    style={{
                                      flex: 1,
                                      backgroundColor: '#0a0d14',
                                      color: '#fff',
                                      border: '1px solid var(--border-subtle)',
                                      borderRadius: '4px',
                                      padding: '4px 6px',
                                      fontSize: '10px',
                                    }}
                                  />
                                  <button
                                    type="button"
                                    disabled={!newCloneName.trim() || isSavingClone}
                                    onClick={async () => {
                                      if (!newCloneName.trim() || !referenceAudioPath) return;
                                      setIsSavingClone(true);
                                      try {
                                        const saved = await saveClonedVoice(newCloneName.trim(), referenceAudioPath);
                                        if (saved) {
                                          setVoxcpmActor(saved.id);
                                          setNewCloneName('');
                                        }
                                      } finally {
                                        setIsSavingClone(false);
                                      }
                                    }}
                                    style={{
                                      fontSize: '10px',
                                      padding: '4px 8px',
                                      backgroundColor: 'rgba(0, 255, 136, 0.15)',
                                      color: 'var(--status-success)',
                                      border: '1px solid rgba(0, 255, 136, 0.3)',
                                      borderRadius: '4px',
                                      cursor: newCloneName.trim() ? 'pointer' : 'not-allowed',
                                      fontWeight: 600,
                                    }}
                                  >
                                    💾 Save Profile
                                  </button>
                                </div>
                              </div>
                            ) : (
                              <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                                No custom audio selected. Voice will clone from speaker or use chosen actor preset.
                              </div>
                            )}
                          </div>
                        )}

                        <button
                          className="btn btn-primary"
                          onClick={() => generateDubbing(dubbingEngine === 'voxcpm' ? voxcpmActor : selectedVoice)}
                          disabled={isAnyAiBusy || !activeProject?.segments || activeProject.segments.length === 0}
                          style={{ width: '100%', fontSize: '11px', padding: '8px' }}
                        >
                          {isDubbing ? 'Dubbing...' : '🗣️ Synthesize Dubbing Only'}
                        </button>
                      </div>
                    )}
                  </div>

                  {/* STAGE 4: STEM MIXING CONSOLE */}
                  <div
                    style={{
                      backgroundColor: '#07090f',
                      borderRadius: '8px',
                      border: '1px solid var(--border-subtle)',
                      overflow: 'hidden',
                    }}
                  >
                    <div
                      onClick={() => toggleStage(4)}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '10px 14px',
                        cursor: 'pointer',
                        backgroundColor: openStages[4] ? 'rgba(0, 255, 136, 0.06)' : 'transparent',
                        borderBottom: openStages[4] ? '1px solid var(--border-subtle)' : 'none',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontSize: '14px' }}>🎛️</span>
                        <div>
                          <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-primary)' }}>
                            Stage 4: Audio Mixing & Stem Console
                          </span>
                        </div>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontSize: '10px', color: 'var(--status-success)', fontWeight: 600 }}>
                          {voiceMode === 'clean-dub' ? 'Clean Dub' : voiceMode === 'voice-over' ? 'Auto-Duck' : voiceMode}
                        </span>
                        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                          {openStages[4] ? '▲' : '▼'}
                        </span>
                      </div>
                    </div>

                    {openStages[4] && (
                      <div style={{ padding: '14px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                        {/* Audio Mode Selectors */}
                        <div>
                          <label style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block', marginBottom: '6px' }}>
                            Playback Voice Mixing Mode
                          </label>
                          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
                            {[
                              { id: 'clean-dub', label: '🎧 Clean Dub (No Echo)', desc: 'Mutes original video voice completely to prevent duplicate speech' },
                              { id: 'voice-over', label: '🎙️ Voice-Over (Auto-Duck)', desc: 'Ducks original audio during speech, restores during pauses' },
                              { id: 'custom-mix', label: '🎚️ Custom Mix', desc: 'Manual multi-stem volume balance' },
                              { id: 'original-only', label: '🔈 Original Only', desc: 'Original media audio only' },
                            ].map((m) => {
                              const isActive = voiceMode === m.id;
                              return (
                                <button
                                  key={m.id}
                                  type="button"
                                  onClick={() => setVoiceMode(m.id as any)}
                                  title={m.desc}
                                  style={{
                                    padding: '6px 8px',
                                    fontSize: '11px',
                                    borderRadius: '6px',
                                    border: isActive ? '1px solid var(--accent-cyan)' : '1px solid var(--border-subtle)',
                                    backgroundColor: isActive ? 'rgba(0, 240, 255, 0.18)' : '#05070c',
                                    color: isActive ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                                    cursor: 'pointer',
                                    fontWeight: isActive ? 600 : 400,
                                    textAlign: 'left',
                                  }}
                                >
                                  {m.label}
                                </button>
                              );
                            })}
                          </div>
                        </div>

                        {/* Mode Description */}
                        {voiceMode === 'clean-dub' && (
                          <div style={{ backgroundColor: 'rgba(0, 255, 136, 0.07)', border: '1px solid rgba(0, 255, 136, 0.25)', borderRadius: '6px', padding: '8px 10px', fontSize: '11px', color: 'var(--status-success)' }}>
                            <strong>✓ Clean Dubbing:</strong> Original video voice is muted automatically so you only hear crisp, translated dubbing without echo.
                          </div>
                        )}

                        {voiceMode === 'voice-over' && (
                          <div style={{ backgroundColor: 'rgba(192, 132, 252, 0.08)', border: '1px solid rgba(192, 132, 252, 0.3)', borderRadius: '6px', padding: '10px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px' }}>
                              <span style={{ color: '#d8b4fe', fontWeight: 600 }}>Dialogue Auto-Ducking:</span>
                              <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{Math.round(duckingLevel * 100)}%</span>
                            </div>
                            <input
                              type="range"
                              min={0}
                              max={0.5}
                              step={0.05}
                              value={duckingLevel}
                              onChange={(e) => setDuckingLevel(parseFloat(e.target.value))}
                              style={{ width: '100%', accentColor: '#c084fc' }}
                            />
                          </div>
                        )}

                        {/* Stem Volume Faders */}
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                          <div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginBottom: '3px' }}>
                              <span style={{ color: 'var(--status-success)', fontWeight: 600 }}>🗣️ AI Dubbed Voice</span>
                              <span style={{ color: 'var(--text-secondary)' }}>{Math.round((activeProject?.stems?.dubbedVolume ?? 1.2) * 100)}%</span>
                            </div>
                            <input
                              type="range"
                              min={0}
                              max={2}
                              step={0.05}
                              value={activeProject?.stems?.dubbedVolume ?? 1.2}
                              onChange={(e) => updateStemVolume('dubbedVolume', parseFloat(e.target.value))}
                              style={{ width: '100%', accentColor: 'var(--status-success)' }}
                            />
                          </div>

                          <div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginBottom: '3px' }}>
                              <span style={{ color: 'var(--accent-cyan)', fontWeight: 500 }}>Original Vocals</span>
                              <span style={{ color: 'var(--text-secondary)' }}>{Math.round((activeProject?.stems?.vocalVolume ?? 1.0) * 100)}%</span>
                            </div>
                            <input
                              type="range"
                              min={0}
                              max={2}
                              step={0.05}
                              value={activeProject?.stems?.vocalVolume ?? 1.0}
                              onChange={(e) => updateStemVolume('vocalVolume', parseFloat(e.target.value))}
                              style={{ width: '100%', accentColor: 'var(--accent-cyan)' }}
                            />
                          </div>

                          <div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginBottom: '3px' }}>
                              <span style={{ color: 'var(--accent-purple)', fontWeight: 500 }}>Background Music</span>
                              <span style={{ color: 'var(--text-secondary)' }}>{Math.round((activeProject?.stems?.musicVolume ?? 0.8) * 100)}%</span>
                            </div>
                            <input
                              type="range"
                              min={0}
                              max={2}
                              step={0.05}
                              value={activeProject?.stems?.musicVolume ?? 0.8}
                              onChange={(e) => updateStemVolume('musicVolume', parseFloat(e.target.value))}
                              style={{ width: '100%', accentColor: 'var(--accent-purple)' }}
                            />
                          </div>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Master 1-Click Button in Advanced View */}
                  <div style={{ marginTop: '6px' }}>
                    <button
                      className="btn btn-primary"
                      onClick={runFullAiPipeline}
                      disabled={isAnyAiBusy || !activeProject?.sourceMedia?.pathOrUrl}
                      style={{
                        width: '100%',
                        fontSize: '13px',
                        fontWeight: 700,
                        padding: '12px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '8px',
                        background: 'linear-gradient(135deg, var(--accent-cyan) 0%, var(--accent-purple) 100%)',
                        border: 'none',
                        color: '#fff',
                        cursor: isAnyAiBusy ? 'not-allowed' : 'pointer',
                        opacity: isAnyAiBusy ? 0.7 : 1,
                        boxShadow: '0 4px 14px rgba(0, 240, 255, 0.3)',
                        borderRadius: '8px',
                      }}
                    >
                      {isPipelineRunning ? (
                        <>
                          <span className="spinner-dots">●</span> Running Configured Pipeline...
                        </>
                      ) : (
                        `⚡ Run Configured Full Pipeline (${targetLanguage.toUpperCase()})`
                      )}
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })()}

        {/* TAB 3: SUBTITLES PREVIEW & LIST */}
        {activeTab === 'subtitles' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: '4px',
              }}
            >
              <h4 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
                Speech Segments ({activeProject?.segments?.length || 0})
              </h4>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ fontSize: '11px', color: 'var(--accent-cyan)', fontWeight: 600 }}>
                  {activeProject?.sourceLanguage?.toUpperCase() || 'EN'} →{' '}
                  {targetLanguage?.toUpperCase() || activeProject?.targetLanguage?.toUpperCase() || 'KM'}
                </span>
              </div>
            </div>

            {/* Quick Translation Style Selector for Subtitles */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', flexWrap: 'wrap' }}>
              <span style={{ color: 'var(--text-muted)', fontSize: '10px' }}>Style:</span>
              {(['natural', 'formal', 'cinematic', 'concise'] as const).map((st) => (
                <button
                  key={st}
                  type="button"
                  onClick={() => setTranslationStyle(st)}
                  disabled={isAnyAiBusy}
                  style={{
                    padding: '2px 8px',
                    fontSize: '10px',
                    borderRadius: '12px',
                    border: translationStyle === st ? '1px solid var(--accent-cyan)' : '1px solid var(--border-subtle)',
                    backgroundColor: translationStyle === st ? 'rgba(0, 240, 255, 0.15)' : 'transparent',
                    color: translationStyle === st ? 'var(--accent-cyan)' : 'var(--text-muted)',
                    cursor: 'pointer',
                    textTransform: 'capitalize',
                  }}
                >
                  {st === 'natural' ? '🌿 Natural' : st === 'formal' ? '👔 Formal' : st === 'cinematic' ? '🎬 Cinematic' : '⏱️ Concise'}
                </button>
              ))}
            </div>

            {/* Quick Actions Header */}
            <div style={{ display: 'flex', gap: '6px' }}>
              <button
                className="btn btn-outline"
                onClick={transcribeSpeech}
                disabled={isAnyAiBusy || !activeProject?.sourceMedia?.pathOrUrl}
                style={{ flex: 1, fontSize: '11px', padding: '6px' }}
              >
                {isTranscribing ? 'Transcribing...' : '🎙️ Re-Transcribe'}
              </button>
              <button
                className="btn btn-outline"
                onClick={() => translateSubtitles(targetLanguage)}
                disabled={isAnyAiBusy || !activeProject?.segments || activeProject.segments.length === 0}
                style={{ flex: 1, fontSize: '11px', padding: '6px' }}
              >
                {isTranslating ? 'Translating...' : '🌐 Re-Translate'}
              </button>
              <button
                className="btn btn-outline"
                onClick={() => generateDubbing(dubbingEngine === 'voxcpm' ? voxcpmActor : selectedVoice)}
                disabled={isAnyAiBusy || !activeProject?.segments || activeProject.segments.length === 0}
                style={{ flex: 1, fontSize: '11px', padding: '6px' }}
              >
                {isDubbing ? 'Dubbing...' : '🗣️ Re-Dub'}
              </button>
            </div>

            {(!activeProject?.segments || activeProject.segments.length === 0) ? (
              <div
                style={{
                  textAlign: 'center',
                  padding: '40px 10px',
                  backgroundColor: 'rgba(255, 255, 255, 0.02)',
                  borderRadius: '8px',
                  border: '1px dashed var(--border-subtle)',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: '12px',
                }}
              >
                <div style={{ fontSize: '32px' }}>🎙️</div>
                <div style={{ fontSize: '13px', color: 'var(--text-secondary)', maxWidth: '280px', lineHeight: 1.4 }}>
                  No speech segments yet. Run the Whisper AI Speech-to-Text pipeline to automatically transcribe and timestamp dialogue.
                </div>
                <button
                  className="btn btn-primary"
                  onClick={runFullAiPipeline}
                  disabled={isAnyAiBusy || !activeProject?.sourceMedia?.pathOrUrl}
                  style={{ fontSize: '12px', padding: '8px 16px', marginTop: '4px' }}
                >
                  ⚡ Start Auto Transcribe & Dub
                </button>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {activeProject.segments.map((seg) => (
                  <div
                    key={seg.id}
                    style={{
                      padding: '12px',
                      borderRadius: '8px',
                      backgroundColor: 'rgba(255, 255, 255, 0.03)',
                      border: '1px solid var(--border-subtle)',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '8px',
                      transition: 'border-color 0.15s ease',
                    }}
                  >
                    {/* Segment Header */}
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        fontSize: '11px',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <button
                          onClick={() => previewSegment(seg)}
                          style={{
                            backgroundColor: 'rgba(0, 240, 255, 0.15)',
                            color: 'var(--accent-cyan)',
                            border: 'none',
                            borderRadius: '4px',
                            padding: '2px 6px',
                            cursor: 'pointer',
                            fontSize: '10px',
                            fontWeight: 600,
                          }}
                          title="Seek and play this segment"
                        >
                          ▶ Play
                        </button>
                        <span style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>{seg.speakerName}</span>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span style={{ color: 'var(--accent-cyan)', fontFamily: 'monospace' }}>
                          {formatDuration(seg.start)} - {formatDuration(seg.end)}
                        </span>
                        <button
                          onClick={() => deleteSegment(seg.id)}
                          style={{
                            background: 'transparent',
                            border: 'none',
                            color: 'var(--text-muted)',
                            cursor: 'pointer',
                            padding: '2px',
                            fontSize: '12px',
                          }}
                          title="Delete segment"
                        >
                          ✕
                        </button>
                      </div>
                    </div>

                    {/* Original Source Text */}
                    <div style={{ fontSize: '12px', color: 'var(--text-primary)', lineHeight: 1.4 }}>
                      {seg.originalText}
                    </div>

                    {/* Translated Text (Editable) */}
                    <div>
                      {editingSegmentId === seg.id ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                          <textarea
                            value={seg.translatedText || ''}
                            onChange={(e) => updateSegment(seg.id, { translatedText: e.target.value })}
                            onBlur={() => setEditingSegmentId(null)}
                            autoFocus
                            rows={2}
                            style={{
                              width: '100%',
                              backgroundColor: '#0a0d14',
                              color: 'var(--accent-purple)',
                              border: '1px solid var(--accent-purple)',
                              borderRadius: '4px',
                              padding: '6px',
                              fontSize: '12px',
                              fontFamily: 'inherit',
                              resize: 'vertical',
                            }}
                          />
                          <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Click outside to save</span>
                        </div>
                      ) : (
                        <div
                          onClick={() => setEditingSegmentId(seg.id)}
                          style={{
                            fontSize: '12px',
                            color: seg.translatedText ? 'var(--accent-purple)' : 'var(--text-muted)',
                            fontStyle: seg.translatedText ? 'normal' : 'italic',
                            lineHeight: 1.4,
                            cursor: 'pointer',
                            padding: '4px 6px',
                            borderRadius: '4px',
                            backgroundColor: 'rgba(139, 92, 246, 0.06)',
                            border: '1px dashed rgba(139, 92, 246, 0.25)',
                          }}
                          title="Click to edit translated text"
                        >
                          {seg.translatedText || 'Click to add translation...'}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
