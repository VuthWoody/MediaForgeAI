import React, { useState } from 'react';
import { useProject } from '../../context/ProjectContext';
import { useStudio, formatSMPTE } from '../../context/StudioContext';
import { VideoPlayer } from './VideoPlayer';
import { WaveformCanvas } from './WaveformCanvas';
import { MediaInspectorPanel } from './MediaInspectorPanel';

export const StudioView: React.FC = () => {
  const { activeProject, updateProject, openProjectFolder, selectMediaFile } = useProject();
  const {
    playback,
    waveform,
    isWaveformLoading,
    seek,
    extractSpeechAudio,
    isExtractingAudio,
    selectedSegmentId,
    setSelectedSegmentId,
    runFullAiPipeline,
    isPipelineRunning,
    aiProgress,
    targetLanguage,
    setActiveTab,
  } = useStudio();

  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [projectTitle, setProjectTitle] = useState(activeProject?.name || 'Untitled Project');

  if (!activeProject) {
    return (
      <div
        className="studio-empty-state"
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100%',
          padding: '40px',
          textAlign: 'center',
        }}
      >
        <div style={{ fontSize: '56px', marginBottom: '16px' }}>🎙️</div>
        <h2 style={{ fontSize: '22px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '8px' }}>
          No Active Studio Project Selected
        </h2>
        <p style={{ color: 'var(--text-secondary)', maxWidth: '420px', marginBottom: '24px', fontSize: '14px' }}>
          Select an existing project from the Projects tab or download/import media from the Downloader or Library to begin editing.
        </p>
      </div>
    );
  }

  const handleSaveTitle = async () => {
    setIsEditingTitle(false);
    if (projectTitle.trim() && projectTitle !== activeProject.name) {
      await updateProject({ ...activeProject, name: projectTitle.trim() });
    }
  };

  const handleAttachMedia = async () => {
    const filePath = await selectMediaFile();
    if (filePath && activeProject) {
      const fileName = filePath.split(/[\\/]/).pop() || 'media.mp4';
      const updated = {
        ...activeProject,
        sourceMedia: {
          type: 'file' as const,
          pathOrUrl: filePath,
          filename: fileName,
          durationSeconds: 0,
          resolution: { width: 1920, height: 1080 },
          fps: 30,
          fileSizeBytes: 0,
          codec: 'auto',
          audioSampleRate: 44100,
          audioChannels: 2,
        },
      };
      await updateProject(updated);
    }
  };

  return (
    <div
      className="studio-view"
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        gap: '12px',
        overflow: 'hidden',
      }}
    >
      {/* Top Studio Control Bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '12px 18px',
          backgroundColor: '#0a0d14',
          borderRadius: '10px',
          border: '1px solid var(--border-subtle)',
          flexShrink: 0,
          gap: '16px',
          flexWrap: 'wrap',
        }}
      >
        {/* Left: Project title & Language Pair */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {isEditingTitle ? (
            <input
              type="text"
              value={projectTitle}
              onChange={(e) => setProjectTitle(e.target.value)}
              onBlur={handleSaveTitle}
              onKeyDown={(e) => e.key === 'Enter' && handleSaveTitle()}
              autoFocus
              className="input-field"
              style={{ fontSize: '15px', fontWeight: 600, padding: '4px 8px', width: '280px' }}
            />
          ) : (
            <h2
              onClick={() => setIsEditingTitle(true)}
              style={{
                fontSize: '16px',
                fontWeight: 600,
                color: 'var(--text-primary)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}
              title="Click to rename"
            >
              <span>{activeProject.name}</span>
              <span style={{ fontSize: '11px', opacity: 0.5 }}>✏️</span>
            </h2>
          )}

          {/* Language Pair Pill */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              backgroundColor: 'rgba(0, 240, 255, 0.08)',
              border: '1px solid rgba(0, 240, 255, 0.25)',
              padding: '3px 10px',
              borderRadius: '20px',
              fontSize: '11px',
              fontWeight: 600,
              color: 'var(--accent-cyan)',
            }}
          >
            <span>{activeProject.sourceLanguage.toUpperCase()}</span>
            <span>➔</span>
            <span>{activeProject.targetLanguage.toUpperCase()}</span>
          </div>

          {/* Project Status */}
          <span
            className={`status-pill status-${activeProject.status}`}
            style={{ fontSize: '10px', padding: '2px 8px', borderRadius: '12px' }}
          >
            {activeProject.status.toUpperCase()}
          </span>
        </div>

        {/* Right: Quick Studio Actions */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {/* Master 1-Click Auto Translate & Dub Action Button */}
          <button
            className="btn btn-primary"
            onClick={() => {
              setActiveTab('stems');
              runFullAiPipeline();
            }}
            disabled={isPipelineRunning || isExtractingAudio || !activeProject.sourceMedia?.pathOrUrl}
            style={{
              fontSize: '12px',
              padding: '6px 14px',
              background: 'linear-gradient(135deg, var(--accent-cyan) 0%, var(--accent-purple) 100%)',
              border: 'none',
              color: '#fff',
              fontWeight: 600,
              boxShadow: '0 2px 10px rgba(0, 240, 255, 0.25)',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              cursor: isPipelineRunning ? 'not-allowed' : 'pointer',
            }}
            title="Automatically extract speech, transcribe with Whisper, neural-translate, and synthesize synchronized dubbing"
          >
            {isPipelineRunning ? (
              <>
                <span className="spinner-dots">●</span>
                <span>{aiProgress ? `${aiProgress.stage}... (${aiProgress.percent}%)` : 'Dubbing...'}</span>
              </>
            ) : activeProject.stems?.dubbedVocalsPath ? (
              <>
                <span>⚡</span>
                <span>Re-Dub ({targetLanguage?.toUpperCase() || activeProject.targetLanguage?.toUpperCase() || 'KM'})</span>
              </>
            ) : (
              <>
                <span>⚡</span>
                <span>1-Click Auto Dub ({targetLanguage?.toUpperCase() || activeProject.targetLanguage?.toUpperCase() || 'KM'})</span>
              </>
            )}
          </button>

          <button
            className="btn btn-outline"
            onClick={handleAttachMedia}
            style={{ fontSize: '12px', padding: '6px 12px' }}
          >
            📁 {activeProject.sourceMedia ? 'Replace Media' : 'Attach Media'}
          </button>

          <button
            className="btn btn-outline"
            onClick={extractSpeechAudio}
            disabled={isExtractingAudio || isPipelineRunning || !activeProject.sourceMedia?.pathOrUrl}
            style={{ fontSize: '12px', padding: '6px 12px' }}
            title="Pre-extract 16kHz speech WAV for Whisper STT"
          >
            {isExtractingAudio ? 'Extracting...' : '🎙️ Extract 16k WAV'}
          </button>

          <button
            className="btn btn-outline"
            onClick={() => openProjectFolder(activeProject.id)}
            style={{ fontSize: '12px', padding: '6px 12px' }}
            title="Open project folder in Windows Explorer"
          >
            📂 Explorer
          </button>
        </div>
      </div>

      {/* Main Studio Dual-Pane Layout */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(0, 1fr) 380px',
          gap: '12px',
          flex: 1,
          minHeight: 0,
        }}
      >
        {/* Left Column: Video Viewport & Audio Waveform Timeline */}
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '10px',
            minHeight: 0,
          }}
        >
          {/* Video Player */}
          <div style={{ flex: 1, minHeight: 0, display: 'flex' }}>
            <VideoPlayer
              sourcePath={activeProject.sourceMedia?.pathOrUrl}
              onOpenSelectMedia={handleAttachMedia}
            />
          </div>

          {/* Waveform Timeline Area */}
          <div
            style={{
              backgroundColor: '#0a0d14',
              borderRadius: '10px',
              border: '1px solid var(--border-subtle)',
              padding: '12px',
              display: 'flex',
              flexDirection: 'column',
              gap: '8px',
              flexShrink: 0,
            }}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                fontSize: '11px',
                color: 'var(--text-secondary)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                  🎵 Audio Waveform & Dialogue Timeline
                </span>
                <span style={{ color: 'var(--accent-cyan)' }}>
                  Playhead: {formatSMPTE(playback.currentTime, playback.fps)}
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ opacity: 0.7 }}>Click or drag to scrub</span>
              </div>
            </div>

            {/* Interactive HTML5 Waveform Canvas */}
            <WaveformCanvas
              waveform={waveform}
              currentTime={playback.currentTime}
              duration={playback.duration}
              isLoading={isWaveformLoading}
              segments={activeProject.segments}
              selectedSegmentId={selectedSegmentId}
              onSeek={seek}
              onSelectSegment={setSelectedSegmentId}
            />
          </div>
        </div>

        {/* Right Column: Media Inspector & Stem Mix Panel */}
        <div style={{ minHeight: 0, height: '100%' }}>
          <MediaInspectorPanel />
        </div>
      </div>
    </div>
  );
};
