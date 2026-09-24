import React, { createContext, useContext, useEffect, useRef, useState, useCallback } from 'react';
import { 
  PlaybackState, 
  WaveformData, 
  AudioExtractionResult, 
  FrameCaptureResult, 
  MediaProbeResult,
  AspectRatioType,
  AspectRatioFitMode,
  AiPipelineProgress,
  VoiceOption,
  PipelineOptions,
  VoxCpmActor,
  VoiceTrackMode,
  DubbingEngineType
} from '../types/studio';
import { SpeechSegment, ProjectData, VoiceMode, DubbingEngine, TranslationStyle, ClonedVoiceProfile, ContentGenre, TranslationEngine } from '../types/project';
import { useProject } from './ProjectContext';

export function formatSMPTE(seconds: number, fps = 30): string {
  if (isNaN(seconds) || seconds < 0) seconds = 0;
  const safeFps = Math.max(1, fps);
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  const frames = Math.floor((seconds - Math.floor(seconds)) * safeFps);
  return `${hrs.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}:${frames.toString().padStart(2, '0')}`;
}

export function formatDuration(seconds: number): string {
  if (isNaN(seconds) || seconds < 0) seconds = 0;
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

interface StudioContextType {
  playback: PlaybackState;
  waveform: WaveformData | null;
  isWaveformLoading: boolean;
  isExtractingAudio: boolean;
  extractionResult: AudioExtractionResult | null;
  mediaProbe: MediaProbeResult | null;
  isProbing: boolean;
  activeTab: 'inspector' | 'stems' | 'subtitles';
  setActiveTab: (tab: 'inspector' | 'stems' | 'subtitles') => void;
  selectedSegmentId: string | null;
  setSelectedSegmentId: (id: string | null) => void;
  snapshots: FrameCaptureResult[];
  
  // Aspect ratio & display framing
  aspectRatio: AspectRatioType;
  setAspectRatio: (ratio: AspectRatioType) => void;
  fitMode: AspectRatioFitMode;
  setFitMode: (mode: AspectRatioFitMode) => void;
  showSafeZones: boolean;
  setShowSafeZones: (show: boolean) => void;
  videoNaturalSize: { width: number; height: number };
  setVideoNaturalSize: (size: { width: number; height: number }) => void;

  // Video element binding
  videoRef: React.RefObject<HTMLVideoElement | null>;

  // AI Pipeline State & Actions (Whisper STT, Translation, Dubbing)
  isTranscribing: boolean;
  isTranslating: boolean;
  isDubbing: boolean;
  isPipelineRunning: boolean;
  aiProgress: AiPipelineProgress | null;
  voices: VoiceOption[];
  selectedVoice: string;
  setSelectedVoice: (voice: string) => void;
  targetLanguage: string;
  setTargetLanguage: (lang: string) => void;
  whisperModel: 'tiny' | 'base' | 'small' | 'medium';
  setWhisperModel: (model: 'tiny' | 'base' | 'small' | 'medium') => void;

  // Translation Engine, Genre & Style
  translationEngine: TranslationEngine;
  setTranslationEngine: (engine: TranslationEngine) => void;
  contentGenre: ContentGenre;
  setContentGenre: (genre: ContentGenre) => void;
  detectedGenre: ContentGenre | null;
  testTranslationApiKey: (engine: string, apiKey?: string, endpoint?: string) => Promise<{
    success: boolean;
    latencyMs?: number;
    error?: string;
    sample?: string;
  }>;
  translationStyle: TranslationStyle;
  setTranslationStyle: (style: TranslationStyle) => void;
  translationPrompt: string;
  setTranslationPrompt: (prompt: string) => void;

  // Dual-Voice Mixing & Voice-Over Controls
  voiceMode: VoiceMode;
  setVoiceMode: (mode: VoiceMode) => void;
  duckingLevel: number;
  setDuckingLevel: (level: number) => void;

  // AI Voice Engine & VoxCPM Cloning
  dubbingEngine: DubbingEngine;
  setDubbingEngine: (engine: DubbingEngine) => void;
  voxcpmActor: string;
  setVoxcpmActor: (actorId: string) => void;
  voxcpmPrompt: string;
  setVoxcpmPrompt: (prompt: string) => void;
  referenceAudioPath: string;
  setReferenceAudioPath: (path: string) => void;
  voxcpmActors: VoxCpmActor[];
  clonedVoices: ClonedVoiceProfile[];
  loadClonedVoices: () => Promise<void>;
  selectReferenceAudioFile: () => Promise<string | null>;
  saveClonedVoice: (name: string, audioPath: string) => Promise<ClonedVoiceProfile | null>;
  deleteClonedVoice: (id: string) => Promise<boolean>;

  // AI Operations
  transcribeSpeech: () => Promise<void>;
  translateSubtitles: (targetLang?: string) => Promise<void>;
  generateDubbing: (voiceName?: string) => Promise<void>;
  runFullAiPipeline: () => Promise<void>;
  updateSegment: (segmentId: string, partial: Partial<SpeechSegment>) => void;
  deleteSegment: (segmentId: string) => void;
  previewSegment: (segment: SpeechSegment) => void;

  // Controls
  play: () => void;
  pause: () => void;
  togglePlay: () => void;
  seek: (seconds: number) => void;
  stepFrame: (deltaFrames: number) => void;
  setPlaybackRate: (rate: number) => void;
  setVolume: (volume: number) => void;
  toggleMute: () => void;
  extractSpeechAudio: () => Promise<AudioExtractionResult | null>;
  captureSnapshot: () => Promise<FrameCaptureResult | null>;
  loadWaveform: (mediaPath: string) => Promise<void>;
  probeMediaFile: (mediaPath: string) => Promise<void>;
  updateCurrentTime: (time: number) => void;
  updateDuration: (duration: number) => void;
  updateStemVolume: (stem: 'vocalVolume' | 'musicVolume' | 'sfxVolume' | 'dubbedVolume', val: number) => void;
  setIsPlaying: (isPlaying: boolean) => void;
  toggleLoop: () => void;
  handleEnded: () => void;
}

const StudioContext = createContext<StudioContextType | undefined>(undefined);

export const StudioProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { activeProject, updateProject } = useProject();
  const videoRef = useRef<HTMLVideoElement | null>(null);

  const [playback, setPlayback] = useState<PlaybackState>({
    currentTime: 0,
    duration: activeProject?.sourceMedia?.durationSeconds || 0,
    isPlaying: false,
    playbackRate: 1.0,
    volume: 1.0,
    isMuted: false,
    fps: activeProject?.sourceMedia?.fps || 30,
    isLooping: false,
  });

  const [waveform, setWaveform] = useState<WaveformData | null>(null);
  const [isWaveformLoading, setIsWaveformLoading] = useState<boolean>(false);
  const [isExtractingAudio, setIsExtractingAudio] = useState<boolean>(false);
  const [extractionResult, setExtractionResult] = useState<AudioExtractionResult | null>(null);
  const [mediaProbe, setMediaProbe] = useState<MediaProbeResult | null>(null);
  const [isProbing, setIsProbing] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<'inspector' | 'stems' | 'subtitles'>('inspector');
  const [selectedSegmentId, setSelectedSegmentId] = useState<string | null>(null);
  const [snapshots, setSnapshots] = useState<FrameCaptureResult[]>([]);

  // AI Pipeline States (Whisper STT, Neural Translation, Voice Dubbing)
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [isTranslating, setIsTranslating] = useState(false);
  const [isDubbing, setIsDubbing] = useState(false);
  const [isPipelineRunning, setIsPipelineRunning] = useState(false);
  const [aiProgress, setAiProgress] = useState<AiPipelineProgress | null>(null);
  const [voices, setVoices] = useState<VoiceOption[]>([]);
  const [selectedVoice, setSelectedVoice] = useState<string>('km-KH-PisethNeural');
  const [targetLanguage, setTargetLanguage] = useState<string>(activeProject?.targetLanguage || 'km');
  const [whisperModel, setWhisperModel] = useState<'tiny' | 'base' | 'small' | 'medium'>('tiny');
  const [translationStyle, setTranslationStyleState] = useState<TranslationStyle>(
    activeProject?.stems?.translationStyle || 'natural'
  );
  const [translationPrompt, setTranslationPromptState] = useState<string>(
    activeProject?.stems?.translationPrompt || ''
  );
  const [translationEngine, setTranslationEngineState] = useState<TranslationEngine>(
    activeProject?.stems?.translationEngine || 'gemini'
  );
  const [contentGenre, setContentGenreState] = useState<ContentGenre>(
    activeProject?.stems?.contentGenre || 'auto'
  );
  const [detectedGenre, setDetectedGenre] = useState<ContentGenre | null>(
    activeProject?.stems?.detectedGenre || null
  );
  const [clonedVoices, setClonedVoices] = useState<ClonedVoiceProfile[]>([]);

  // Dual-Voice Mixing & Voice-Over Mode State
  const [voiceMode, setVoiceModeState] = useState<VoiceMode>(
    activeProject?.stems?.voiceMode || (activeProject?.stems?.dubbedVocalsPath ? 'clean-dub' : 'original-only')
  );
  const [duckingLevel, setDuckingLevelState] = useState<number>(activeProject?.stems?.duckingLevel ?? 0.12);

  // VoxCPM & Dubbing Engine State
  const [dubbingEngine, setDubbingEngineState] = useState<DubbingEngine>(activeProject?.stems?.dubbingEngine || 'edge-tts');
  const [voxcpmActor, setVoxcpmActorState] = useState<string>(activeProject?.stems?.voxcpmActor || 'khmer_piseth_actor');
  const [voxcpmPrompt, setVoxcpmPromptState] = useState<string>(activeProject?.stems?.voxcpmPrompt || '');
  const [referenceAudioPath, setReferenceAudioPathState] = useState<string>(activeProject?.stems?.referenceAudioPath || '');
  const [voxcpmActors, setVoxcpmActors] = useState<VoxCpmActor[]>([]);

  // Aspect ratio & framing display states
  const [aspectRatio, setAspectRatio] = useState<AspectRatioType>('original');
  const [fitMode, setFitMode] = useState<AspectRatioFitMode>('contain');
  const [showSafeZones, setShowSafeZones] = useState<boolean>(false);
  const [videoNaturalSize, setVideoNaturalSize] = useState<{ width: number; height: number }>({
    width: 1920,
    height: 1080,
  });

  // Load waveform for media file
  const loadWaveform = useCallback(async (mediaPath: string) => {
    if (!mediaPath || !window.electronAPI?.ffmpegGenerateWaveform) return;
    setIsWaveformLoading(true);
    try {
      const data = await window.electronAPI.ffmpegGenerateWaveform(mediaPath, 600);
      setWaveform(data);
    } catch (err) {
      console.error('Failed to generate waveform:', err);
    } finally {
      setIsWaveformLoading(false);
    }
  }, []);

  // Probe media streams
  const probeMediaFile = useCallback(async (mediaPath: string) => {
    if (!mediaPath || !window.electronAPI?.ffmpegProbe) return;
    setIsProbing(true);
    try {
      const probe = await window.electronAPI.ffmpegProbe(mediaPath);
      setMediaProbe(probe);
      if (probe.videoStreams.length > 0) {
        const v = probe.videoStreams[0];
        if (v.fps) {
          setPlayback(prev => ({ ...prev, fps: v.fps || 30 }));
        }
        if (v.width && v.height) {
          setVideoNaturalSize({ width: v.width, height: v.height });
          // Auto-detect vertical vs horizontal ratio
          if (v.height > v.width) {
            setAspectRatio('9:16');
          } else if (Math.abs(v.width / v.height - 16 / 9) < 0.1) {
            setAspectRatio('16:9');
          } else if (v.width === v.height) {
            setAspectRatio('1:1');
          } else {
            setAspectRatio('original');
          }
        }
      }
      if (probe.durationSeconds > 0) {
        setPlayback(prev => ({ ...prev, duration: probe.durationSeconds }));
      }
    } catch (err) {
      console.error('Failed to probe media:', err);
    } finally {
      setIsProbing(false);
    }
  }, []);

  // When active project changes, reset and load media analysis
  useEffect(() => {
    if (activeProject?.sourceMedia?.pathOrUrl) {
      const mediaPath = activeProject.sourceMedia.pathOrUrl;
      const initialFps = activeProject.sourceMedia.fps || 30;
      const initialDuration = activeProject.sourceMedia.durationSeconds || 0;

      setPlayback(prev => ({
        ...prev,
        currentTime: 0,
        duration: initialDuration,
        isPlaying: false,
        fps: initialFps,
      }));

      probeMediaFile(mediaPath);
      loadWaveform(mediaPath);
    } else {
      setPlayback(prev => ({ ...prev, currentTime: 0, duration: 0, isPlaying: false }));
      setWaveform(null);
      setMediaProbe(null);
    }
  }, [activeProject?.id, activeProject?.sourceMedia?.pathOrUrl, probeMediaFile, loadWaveform]);

  // Video playback controls
  const play = useCallback(() => {
    if (videoRef.current) {
      // If at or near the end, restart smoothly from 0
      if (
        videoRef.current.ended ||
        (videoRef.current.duration > 0 && videoRef.current.currentTime >= videoRef.current.duration - 0.1)
      ) {
        videoRef.current.currentTime = 0;
      }
      videoRef.current.play().catch(err => console.warn('Video play prevented:', err));
    }
    setPlayback(prev => ({ ...prev, isPlaying: true }));
  }, []);

  const pause = useCallback(() => {
    if (videoRef.current) {
      videoRef.current.pause();
    }
    setPlayback(prev => ({ ...prev, isPlaying: false }));
  }, []);

  const togglePlay = useCallback(() => {
    const video = videoRef.current;
    if (video) {
      // If at or near the end of video, restart smoothly from the beginning
      if (
        video.ended ||
        (video.duration > 0 && video.currentTime >= video.duration - 0.1)
      ) {
        video.currentTime = 0;
        video.play().catch(err => console.warn('Replay play error:', err));
        setPlayback(prev => ({ ...prev, currentTime: 0, isPlaying: true }));
        return;
      }

      if (video.paused) {
        video.play().catch(err => console.warn('Play error:', err));
        setPlayback(prev => ({ ...prev, isPlaying: true }));
      } else {
        video.pause();
        setPlayback(prev => ({ ...prev, isPlaying: false }));
      }
    } else {
      setPlayback(prev => ({ ...prev, isPlaying: !prev.isPlaying }));
    }
  }, []);

  const setIsPlaying = useCallback((isPlaying: boolean) => {
    setPlayback(prev => (prev.isPlaying === isPlaying ? prev : { ...prev, isPlaying }));
  }, []);

  const toggleLoop = useCallback(() => {
    setPlayback(prev => ({ ...prev, isLooping: !prev.isLooping }));
  }, []);

  const handleEnded = useCallback(() => {
    setPlayback(prev => {
      if (prev.isLooping) {
        if (videoRef.current) {
          videoRef.current.currentTime = 0;
          videoRef.current.play().catch(err => console.warn('Loop replay error:', err));
        }
        return { ...prev, currentTime: 0, isPlaying: true };
      } else {
        return { ...prev, isPlaying: false };
      }
    });
  }, []);

  const seek = useCallback((seconds: number) => {
    const clamped = Math.max(0, Math.min(seconds, playback.duration || 999999));
    if (videoRef.current) {
      videoRef.current.currentTime = clamped;
    }
    setPlayback(prev => ({ ...prev, currentTime: clamped }));
  }, [playback.duration]);

  const stepFrame = useCallback((deltaFrames: number) => {
    const frameDuration = 1 / (playback.fps || 30);
    const targetTime = Math.max(0, Math.min(playback.currentTime + deltaFrames * frameDuration, playback.duration));
    if (videoRef.current) {
      if (!videoRef.current.paused) {
        videoRef.current.pause();
      }
      videoRef.current.currentTime = targetTime;
    }
    setPlayback(prev => ({ ...prev, currentTime: targetTime, isPlaying: false }));
  }, [playback.currentTime, playback.duration, playback.fps]);

  const setPlaybackRate = useCallback((rate: number) => {
    if (videoRef.current) {
      videoRef.current.playbackRate = rate;
    }
    setPlayback(prev => ({ ...prev, playbackRate: rate }));
  }, []);

  const setVolume = useCallback((volume: number) => {
    const clamped = Math.max(0, Math.min(1.0, volume));
    if (videoRef.current) {
      videoRef.current.volume = clamped;
      videoRef.current.muted = clamped === 0;
    }
    setPlayback(prev => ({ ...prev, volume: clamped, isMuted: clamped === 0 }));
  }, []);

  const toggleMute = useCallback(() => {
    setPlayback(prev => {
      const nextMuted = !prev.isMuted;
      if (videoRef.current) {
        videoRef.current.muted = nextMuted;
      }
      return { ...prev, isMuted: nextMuted };
    });
  }, []);

  const updateCurrentTime = useCallback((time: number) => {
    setPlayback(prev => ({ ...prev, currentTime: time }));
  }, []);

  const updateDuration = useCallback((duration: number) => {
    setPlayback(prev => ({ ...prev, duration }));
  }, []);

  // Speech Audio Extraction for Whisper (16kHz mono WAV)
  const extractSpeechAudio = useCallback(async (): Promise<AudioExtractionResult | null> => {
    if (!activeProject?.sourceMedia?.pathOrUrl || !window.electronAPI?.ffmpegExtractAudio) {
      return null;
    }
    setIsExtractingAudio(true);
    try {
      const sourcePath = activeProject.sourceMedia.pathOrUrl;
      const result = await window.electronAPI.ffmpegExtractAudio(sourcePath);
      setExtractionResult(result);

      if (result.success && activeProject) {
        const updated = {
          ...activeProject,
          stems: {
            ...activeProject.stems,
            originalAudioPath: result.wavPath,
          },
        };
        await updateProject(updated);
      }
      return result;
    } catch (err) {
      console.error('Failed to extract speech audio:', err);
      return null;
    } finally {
      setIsExtractingAudio(false);
    }
  }, [activeProject, updateProject]);

  // Capture frame snapshot
  const captureSnapshot = useCallback(async (): Promise<FrameCaptureResult | null> => {
    if (!activeProject?.sourceMedia?.pathOrUrl || !window.electronAPI?.ffmpegCaptureFrame) {
      return null;
    }
    try {
      const sourcePath = activeProject.sourceMedia.pathOrUrl;
      const res = await window.electronAPI.ffmpegCaptureFrame(sourcePath, playback.currentTime);
      if (res.success) {
        setSnapshots(prev => [res, ...prev.slice(0, 9)]);
      }
      return res;
    } catch (err) {
      console.error('Frame snapshot error:', err);
      return null;
    }
  }, [activeProject?.sourceMedia?.pathOrUrl, playback.currentTime]);

  // Stem Volume Updater
  const updateStemVolume = useCallback((stem: 'vocalVolume' | 'musicVolume' | 'sfxVolume' | 'dubbedVolume', val: number) => {
    if (!activeProject) return;
    const updated = {
      ...activeProject,
      stems: {
        ...activeProject.stems,
        [stem]: val,
      },
    };
    updateProject(updated);
  }, [activeProject, updateProject]);

  // Load VoxCPM actors on mount
  useEffect(() => {
    if (!window.electronAPI?.aiGetVoxCpmActors) return;
    window.electronAPI.aiGetVoxCpmActors().then((actors) => {
      if (actors && actors.length > 0) {
        setVoxcpmActors(actors);
      }
    }).catch(console.error);
  }, []);

  // Sync project voiceMode when active project changes
  useEffect(() => {
    if (activeProject?.stems?.voiceMode) {
      setVoiceModeState(activeProject.stems.voiceMode);
    } else if (activeProject?.stems?.dubbedVocalsPath) {
      setVoiceModeState('clean-dub');
    }
    if (activeProject?.stems?.duckingLevel !== undefined) {
      setDuckingLevelState(activeProject.stems.duckingLevel);
    }
    if (activeProject?.stems?.dubbingEngine) {
      setDubbingEngineState(activeProject.stems.dubbingEngine);
    }
    if (activeProject?.stems?.voxcpmActor) {
      setVoxcpmActorState(activeProject.stems.voxcpmActor);
    }
    if (activeProject?.stems?.referenceAudioPath) {
      setReferenceAudioPathState(activeProject.stems.referenceAudioPath);
    }
  }, [activeProject?.id, activeProject?.stems?.voiceMode, activeProject?.stems?.dubbedVocalsPath]);

  const setVoiceMode = useCallback((mode: VoiceMode) => {
    setVoiceModeState(mode);
    if (activeProject) {
      updateProject({
        ...activeProject,
        stems: {
          ...activeProject.stems,
          voiceMode: mode,
        }
      });
    }
  }, [activeProject, updateProject]);

  const setDuckingLevel = useCallback((level: number) => {
    setDuckingLevelState(level);
    if (activeProject) {
      updateProject({
        ...activeProject,
        stems: {
          ...activeProject.stems,
          duckingLevel: level,
        }
      });
    }
  }, [activeProject, updateProject]);

  const setDubbingEngine = useCallback((engine: DubbingEngine) => {
    setDubbingEngineState(engine);
    if (activeProject) {
      updateProject({
        ...activeProject,
        stems: {
          ...activeProject.stems,
          dubbingEngine: engine,
        }
      });
    }
  }, [activeProject, updateProject]);

  const setVoxcpmActor = useCallback((actorId: string) => {
    setVoxcpmActorState(actorId);
    if (activeProject) {
      updateProject({
        ...activeProject,
        stems: {
          ...activeProject.stems,
          voxcpmActor: actorId,
        }
      });
    }
  }, [activeProject, updateProject]);

  const setVoxcpmPrompt = useCallback((prompt: string) => {
    setVoxcpmPromptState(prompt);
    if (activeProject) {
      updateProject({
        ...activeProject,
        stems: {
          ...activeProject.stems,
          voxcpmPrompt: prompt,
        }
      });
    }
  }, [activeProject, updateProject]);

  const setReferenceAudioPath = useCallback((path: string) => {
    setReferenceAudioPathState(path);
    if (activeProject) {
      updateProject({
        ...activeProject,
        stems: {
          ...activeProject.stems,
          referenceAudioPath: path,
        }
      });
    }
  }, [activeProject, updateProject]);

  const setTranslationStyle = useCallback((style: TranslationStyle) => {
    setTranslationStyleState(style);
    if (activeProject) {
      updateProject({
        ...activeProject,
        stems: {
          ...activeProject.stems,
          translationStyle: style,
        }
      });
    }
  }, [activeProject, updateProject]);

  const setTranslationPrompt = useCallback((prompt: string) => {
    setTranslationPromptState(prompt);
    if (activeProject) {
      updateProject({
        ...activeProject,
        stems: {
          ...activeProject.stems,
          translationPrompt: prompt,
        }
      });
    }
  }, [activeProject, updateProject]);

  const setTranslationEngine = useCallback((engine: TranslationEngine) => {
    setTranslationEngineState(engine);
    if (activeProject) {
      updateProject({
        ...activeProject,
        stems: {
          ...activeProject.stems,
          translationEngine: engine,
        }
      });
    }
  }, [activeProject, updateProject]);

  const setContentGenre = useCallback((genre: ContentGenre) => {
    setContentGenreState(genre);
    if (activeProject) {
      updateProject({
        ...activeProject,
        stems: {
          ...activeProject.stems,
          contentGenre: genre,
        }
      });
    }
  }, [activeProject, updateProject]);

  const testTranslationApiKey = useCallback(async (engine: string, apiKey?: string, endpoint?: string) => {
    if (!window.electronAPI?.aiTestTranslationKey) {
      return { success: false, engine, error: 'Translation test service unavailable' };
    }
    try {
      return await window.electronAPI.aiTestTranslationKey({ engine, apiKey, endpoint });
    } catch (err: any) {
      return { success: false, engine, error: err?.message || 'Connection test failed' };
    }
  }, []);

  const loadClonedVoices = useCallback(async () => {
    if (!window.electronAPI?.aiGetClonedVoices) return;
    try {
      const list = await window.electronAPI.aiGetClonedVoices();
      setClonedVoices(list || []);
    } catch (err) {
      console.error('Failed to load cloned voices:', err);
    }
  }, []);

  const selectReferenceAudioFile = useCallback(async () => {
    if (!window.electronAPI?.aiSelectReferenceAudio) return null;
    try {
      const res = await window.electronAPI.aiSelectReferenceAudio();
      if (!res.canceled && res.filePath) {
        setReferenceAudioPathState(res.filePath);
        if (activeProject) {
          updateProject({
            ...activeProject,
            stems: {
              ...activeProject.stems,
              referenceAudioPath: res.filePath,
            }
          });
        }
        return res.filePath;
      }
    } catch (err) {
      console.error('Error selecting reference audio:', err);
    }
    return null;
  }, [activeProject, updateProject]);

  const saveClonedVoice = useCallback(async (name: string, audioPath: string) => {
    if (!window.electronAPI?.aiSaveClonedVoice) return null;
    try {
      const profile = await window.electronAPI.aiSaveClonedVoice({
        id: `clone_${Date.now()}`,
        name,
        audioPath,
        createdAt: new Date().toISOString(),
      });
      await loadClonedVoices();
      return profile;
    } catch (err) {
      console.error('Error saving cloned voice:', err);
      return null;
    }
  }, [loadClonedVoices]);

  const deleteClonedVoice = useCallback(async (id: string) => {
    if (!window.electronAPI?.aiDeleteClonedVoice) return false;
    try {
      const ok = await window.electronAPI.aiDeleteClonedVoice(id);
      await loadClonedVoices();
      return ok;
    } catch (err) {
      console.error('Error deleting cloned voice:', err);
      return false;
    }
  }, [loadClonedVoices]);

  // AI Pipeline Event Listeners & State Sync
  useEffect(() => {
    if (!window.electronAPI?.onAiProgress) return;
    const unsub = window.electronAPI.onAiProgress((p: AiPipelineProgress) => {
      setAiProgress(p);
    });
    return () => {
      unsub();
    };
  }, []);

  useEffect(() => {
    loadClonedVoices();
    if (window.electronAPI?.aiGetVoxCpmActors) {
      window.electronAPI.aiGetVoxCpmActors().then(actors => {
        if (actors && actors.length > 0) {
          setVoxcpmActors(actors);
        }
      }).catch(console.error);
    }
  }, [loadClonedVoices]);

  useEffect(() => {
    if (activeProject?.stems?.translationStyle) {
      setTranslationStyleState(activeProject.stems.translationStyle);
    }
    if (activeProject?.stems?.translationPrompt !== undefined) {
      setTranslationPromptState(activeProject.stems.translationPrompt);
    }
  }, [activeProject?.id, activeProject?.stems?.translationStyle, activeProject?.stems?.translationPrompt]);

  useEffect(() => {
    if (activeProject?.targetLanguage) {
      setTargetLanguage(activeProject.targetLanguage);
    }
  }, [activeProject?.id, activeProject?.targetLanguage]);

  useEffect(() => {
    if (!window.electronAPI?.aiGetVoices) return;
    const lang = targetLanguage || 'km';
    window.electronAPI.aiGetVoices(lang).then(vList => {
      setVoices(vList);
      if (vList.length > 0) {
        if (!vList.some(v => v.shortName === selectedVoice)) {
          setSelectedVoice(vList[0].shortName);
        }
      }
    }).catch(console.error);
  }, [targetLanguage]);

  // AI Operation 1: Transcribe Speech via faster-whisper
  const transcribeSpeech = useCallback(async () => {
    if (!activeProject) return;
    setIsTranscribing(true);
    setAiProgress({
      type: 'progress',
      stage: 'transcribing',
      percent: 5,
      message: 'Preparing speech audio for Whisper STT...',
      timestamp: Date.now(),
    });

    try {
      let wavPath = activeProject.stems?.originalAudioPath || extractionResult?.wavPath;
      if (!wavPath && activeProject.sourceMedia?.pathOrUrl && window.electronAPI?.ffmpegExtractAudio) {
        const extRes = await window.electronAPI.ffmpegExtractAudio(activeProject.sourceMedia.pathOrUrl);
        if (extRes.success) {
          wavPath = extRes.wavPath;
          setExtractionResult(extRes);
        }
      }

      if (!wavPath) {
        throw new Error('Could not find or extract 16kHz speech audio from source media.');
      }

      if (!window.electronAPI?.aiTranscribe) {
        throw new Error('AI Speech Transcription service is not available.');
      }

      const res = await window.electronAPI.aiTranscribe({
        audioPath: wavPath,
        modelSize: whisperModel,
        sourceLang: activeProject.sourceLanguage || 'auto',
      });

      if (!res.success) {
        throw new Error((res as any).error || 'Transcription failed');
      }

      let detectedContentGenre: ContentGenre = 'documentary';
      if (window.electronAPI?.aiDetectGenre && res.segments && res.segments.length > 0) {
        try {
          const gRes = await window.electronAPI.aiDetectGenre(res.segments);
          if (gRes.success && gRes.detectedGenre) {
            detectedContentGenre = gRes.detectedGenre as ContentGenre;
            setDetectedGenre(detectedContentGenre);
          }
        } catch {}
      }

      const updatedProject: ProjectData = {
        ...activeProject,
        sourceLanguage: res.detectedLanguage || activeProject.sourceLanguage,
        status: 'transcribed',
        segments: res.segments || [],
        stems: {
          ...activeProject.stems,
          originalAudioPath: wavPath,
          detectedGenre: detectedContentGenre,
        },
        updatedAt: new Date().toISOString(),
      };

      await updateProject(updatedProject);
      setActiveTab('subtitles');
    } catch (err: any) {
      console.error('Transcription error:', err);
      setAiProgress({
        type: 'progress',
        stage: 'error',
        percent: 0,
        message: err.message || 'Transcription failed',
        timestamp: Date.now(),
      });
    } finally {
      setIsTranscribing(false);
    }
  }, [activeProject, extractionResult, whisperModel, updateProject]);

  // AI Operation 2: Translate Subtitles
  const translateSubtitles = useCallback(async (tl?: string) => {
    if (!activeProject || !activeProject.segments || activeProject.segments.length === 0) return;
    setIsTranslating(true);
    const effectiveTarget = tl || targetLanguage || activeProject.targetLanguage || 'km';

    setAiProgress({
      type: 'progress',
      stage: 'translating',
      percent: 5,
      message: `Translating ${activeProject.segments.length} segments to ${effectiveTarget.toUpperCase()} using ${translationEngine.toUpperCase()} (${contentGenre} tone)...`,
      timestamp: Date.now(),
    });

    try {
      if (!window.electronAPI?.aiTranslate) {
        throw new Error('AI Translation service is not available.');
      }

      const res = await window.electronAPI.aiTranslate({
        segments: activeProject.segments,
        targetLang: effectiveTarget,
        sourceLang: activeProject.sourceLanguage || 'auto',
        style: translationStyle,
        genre: contentGenre,
        engine: translationEngine,
        prompt: translationPrompt,
      });

      if (!res.success) {
        throw new Error((res as any).error || 'Translation failed');
      }

      if (res.detectedGenre) {
        setDetectedGenre(res.detectedGenre as ContentGenre);
      }

      const updatedProject: ProjectData = {
        ...activeProject,
        targetLanguage: effectiveTarget,
        status: 'translated',
        segments: res.segments,
        stems: {
          ...activeProject.stems,
          translationStyle,
          translationPrompt,
          translationEngine: (res.translationEngine as any) || translationEngine,
          contentGenre,
          detectedGenre: (res.detectedGenre as any) || detectedGenre || undefined,
        },
        updatedAt: new Date().toISOString(),
      };

      await updateProject(updatedProject);
      setActiveTab('subtitles');
    } catch (err: any) {
      console.error('Translation error:', err);
      setAiProgress({
        type: 'progress',
        stage: 'error',
        percent: 0,
        message: err.message || 'Translation failed',
        timestamp: Date.now(),
      });
    } finally {
      setIsTranslating(false);
    }
  }, [activeProject, targetLanguage, translationStyle, translationPrompt, translationEngine, contentGenre, detectedGenre, updateProject]);

  // AI Operation 3: Generate Neural Voice Dubbing with edge-tts
  const generateDubbing = useCallback(async (vName?: string) => {
    if (!activeProject || !activeProject.segments || activeProject.segments.length === 0) return;
    setIsDubbing(true);
    const chosenVoice = vName || selectedVoice || 'km-KH-PisethNeural';
    const outputDir = `${activeProject.projectDirectory}/stems`;

    setAiProgress({
      type: 'progress',
      stage: 'dubbing',
      percent: 5,
      message: `Synthesizing neural voice dubbing with ${chosenVoice}...`,
      timestamp: Date.now(),
    });

    try {
      if (!window.electronAPI?.aiDub) {
        throw new Error('AI Voice Dubbing service is not available.');
      }

      const effectiveRefAudio = referenceAudioPath || (voxcpmActor === 'voice_clone_original' ? activeProject.stems?.originalAudioPath : undefined);
      const res = await window.electronAPI.aiDub({
        segments: activeProject.segments,
        outputDir,
        voiceName: chosenVoice,
        projectDuration: activeProject.sourceMedia?.durationSeconds || 0,
        targetLang: activeProject.targetLanguage || 'km',
        engine: dubbingEngine,
        referenceAudioPath: effectiveRefAudio,
        voiceStylePrompt: voxcpmPrompt,
        voxcpmActor,
      });

      if (!res.success) {
        throw new Error((res as any).error || 'Dubbing synthesis failed');
      }

      const nextRevision = (activeProject.stems?.dubbedAudioRevision || 0) + 1;
      const updatedProject: ProjectData = {
        ...activeProject,
        status: 'dubbed',
        segments: res.segments,
        stems: {
          ...activeProject.stems,
          dubbedVocalsPath: res.masterDubbedAudioPath,
          dubbedAudioRevision: nextRevision,
          dubbedVolume: activeProject.stems?.dubbedVolume ?? 1.2,
          vocalVolume: activeProject.stems?.vocalVolume ?? 1.0,
          voiceMode: 'clean-dub', // Auto-switch to clean dub so original voice is muted!
          duckingLevel,
          dubbingEngine,
          voxcpmActor,
          referenceAudioPath,
        },
        updatedAt: new Date().toISOString(),
      };

      setVoiceModeState('clean-dub');
      await updateProject(updatedProject);
      setActiveTab('stems');
    } catch (err: any) {
      console.error('Dubbing error:', err);
      setAiProgress({
        type: 'progress',
        stage: 'error',
        percent: 0,
        message: err.message || 'Voice dubbing failed',
        timestamp: Date.now(),
      });
    } finally {
      setIsDubbing(false);
    }
  }, [activeProject, selectedVoice, dubbingEngine, referenceAudioPath, voxcpmActor, voxcpmPrompt, duckingLevel, updateProject]);

  // AI Operation 4: 1-Click End-to-End Pipeline
  const runFullAiPipeline = useCallback(async () => {
    if (!activeProject) return;
    setIsPipelineRunning(true);
    setAiProgress({
      type: 'progress',
      stage: 'transcribing',
      percent: 2,
      message: 'Starting 1-Click Auto Transcribe, Translate & Dub pipeline...',
      timestamp: Date.now(),
    });

    try {
      let currentProject = activeProject;
      if (!currentProject.stems?.originalAudioPath && currentProject.sourceMedia?.pathOrUrl && window.electronAPI?.ffmpegExtractAudio) {
        const extRes = await window.electronAPI.ffmpegExtractAudio(currentProject.sourceMedia.pathOrUrl);
        if (extRes.success) {
          setExtractionResult(extRes);
          currentProject = {
            ...currentProject,
            stems: {
              ...currentProject.stems,
              originalAudioPath: extRes.wavPath,
            }
          };
          await updateProject(currentProject);
        }
      }

      if (!window.electronAPI?.aiRunFullPipeline) {
        throw new Error('AI Pipeline execution service is not available.');
      }

      const effectiveRefAudio = referenceAudioPath || (voxcpmActor === 'voice_clone_original' ? currentProject.stems?.originalAudioPath : undefined);
      const updated = await window.electronAPI.aiRunFullPipeline(currentProject.id, {
        modelSize: whisperModel,
        targetLanguage,
        sourceLanguage: currentProject.sourceLanguage || 'auto',
        voiceName: selectedVoice,
        style: translationStyle,
        prompt: translationPrompt,
        engine: dubbingEngine,
        referenceAudioPath: effectiveRefAudio,
        voiceStylePrompt: voxcpmPrompt,
        voxcpmActor,
        translationEngine,
        contentGenre,
      });

      setVoiceModeState('clean-dub');
      await updateProject(updated);
      setActiveTab('subtitles');
    } catch (err: any) {
      console.error('Full AI pipeline error:', err);
      setAiProgress({
        type: 'progress',
        stage: 'error',
        percent: 0,
        message: err.message || 'Pipeline failed',
        timestamp: Date.now(),
      });
    } finally {
      setIsPipelineRunning(false);
    }
  }, [activeProject, whisperModel, targetLanguage, selectedVoice, translationStyle, translationPrompt, dubbingEngine, referenceAudioPath, voxcpmActor, voxcpmPrompt, translationEngine, contentGenre, setActiveTab, updateProject]);

  // Segment management
  const updateSegment = useCallback((segmentId: string, partial: Partial<SpeechSegment>) => {
    if (!activeProject) return;
    const updatedSegments = (activeProject.segments || []).map(seg => {
      if (seg.id === segmentId) {
        return { ...seg, ...partial, isEdited: true };
      }
      return seg;
    });
    updateProject({
      ...activeProject,
      segments: updatedSegments,
    });
  }, [activeProject, updateProject]);

  const deleteSegment = useCallback((segmentId: string) => {
    if (!activeProject) return;
    const filtered = (activeProject.segments || []).filter(s => s.id !== segmentId);
    updateProject({
      ...activeProject,
      segments: filtered,
    });
  }, [activeProject, updateProject]);

  const previewSegment = useCallback((seg: SpeechSegment) => {
    seek(seg.start);
    if (videoRef.current && videoRef.current.paused) {
      videoRef.current.play().catch(console.error);
    }
  }, [seek]);

  return (
    <StudioContext.Provider
      value={{
        playback,
        waveform,
        isWaveformLoading,
        isExtractingAudio,
        extractionResult,
        mediaProbe,
        isProbing,
        activeTab,
        setActiveTab,
        selectedSegmentId,
        setSelectedSegmentId,
        snapshots,
        aspectRatio,
        setAspectRatio,
        fitMode,
        setFitMode,
        showSafeZones,
        setShowSafeZones,
        videoNaturalSize,
        setVideoNaturalSize,
        videoRef,
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
        clonedVoices,
        loadClonedVoices,
        selectReferenceAudioFile,
        saveClonedVoice,
        deleteClonedVoice,
        transcribeSpeech,
        translateSubtitles,
        generateDubbing,
        runFullAiPipeline,
        updateSegment,
        deleteSegment,
        previewSegment,
        play,
        pause,
        togglePlay,
        seek,
        stepFrame,
        setPlaybackRate,
        setVolume,
        toggleMute,
        extractSpeechAudio,
        captureSnapshot,
        loadWaveform,
        probeMediaFile,
        updateCurrentTime,
        updateDuration,
        updateStemVolume,
        setIsPlaying,
        toggleLoop,
        handleEnded,
      }}
    >
      {children}
    </StudioContext.Provider>
  );
};

export const useStudio = () => {
  const context = useContext(StudioContext);
  if (!context) {
    throw new Error('useStudio must be used within a StudioProvider');
  }
  return context;
};
