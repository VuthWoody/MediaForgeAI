import { ProjectData, ProjectSummary, SpeechSegment } from './project';
import { AppSettings } from './settings';
import { SystemMetrics, HardwareInfo } from './system';
import { LogEntry } from './logs';
import { MediaUrlInfo, DownloadJob, DownloadProgress } from './downloader';
import { MediaLibraryItem, MediaFilterOptions } from './mediaLibrary';
import { 
  WaveformData, 
  AudioExtractionResult, 
  FrameCaptureResult, 
  MediaProbeResult,
  AiPipelineProgress,
  VoiceOption,
  PipelineOptions
} from './studio';

export interface ElectronAPI {
  // Window controls
  minimizeWindow: () => Promise<void>;
  maximizeWindow: () => Promise<void>;
  closeWindow: () => Promise<void>;
  isWindowMaximized: () => Promise<boolean>;

  // Project operations
  listProjects: () => Promise<ProjectSummary[]>;
  getProject: (id: string) => Promise<ProjectData | null>;
  createProject: (project: Partial<ProjectData>) => Promise<ProjectData>;
  updateProject: (project: ProjectData) => Promise<ProjectData>;
  deleteProject: (id: string) => Promise<boolean>;
  duplicateProject: (id: string) => Promise<ProjectData>;
  openProjectFolder: (id: string) => Promise<void>;
  selectMediaFile: () => Promise<{ canceled: boolean; filePath?: string }>;

  // Settings
  getSettings: () => Promise<AppSettings>;
  saveSettings: (settings: AppSettings) => Promise<boolean>;
  resetSettings: () => Promise<AppSettings>;

  // System & Hardware
  getSystemMetrics: () => Promise<SystemMetrics>;
  onMetricsUpdate: (callback: (metrics: SystemMetrics) => void) => () => void;
  getHardwareInfo: () => Promise<HardwareInfo>;

  // Downloader Module (Phase 2)
  downloaderAnalyzeUrl: (url: string) => Promise<MediaUrlInfo>;
  downloaderAddJob: (options: Partial<DownloadJob>) => Promise<DownloadJob>;
  downloaderAddBulkJobs: (urls: string[]) => Promise<DownloadJob[]>;
  downloaderPauseJob: (id: string) => Promise<boolean>;
  downloaderResumeJob: (id: string) => Promise<boolean>;
  downloaderCancelJob: (id: string) => Promise<boolean>;
  downloaderRetryJob: (id: string) => Promise<boolean>;
  downloaderClearCompleted: () => Promise<boolean>;
  downloaderGetQueue: () => Promise<DownloadJob[]>;
  onDownloadProgress: (callback: (progress: DownloadProgress) => void) => () => void;

  // Media Library Module (Phase 2)
  mediaLibraryList: (filters?: MediaFilterOptions) => Promise<MediaLibraryItem[]>;
  mediaLibraryImportFile: (filePath: string) => Promise<MediaLibraryItem>;
  mediaLibraryDelete: (id: string, deleteFromDisk: boolean) => Promise<boolean>;
  mediaLibraryCreateProject: (mediaId: string) => Promise<ProjectData>;

  // FFmpeg Studio & Media Processing (Phase 3)
  ffmpegProbe: (filePath: string) => Promise<MediaProbeResult>;
  ffmpegExtractAudio: (inputPath: string, outputPath?: string) => Promise<AudioExtractionResult>;
  ffmpegGenerateWaveform: (mediaPath: string, numBuckets?: number) => Promise<WaveformData>;
  ffmpegCaptureFrame: (videoPath: string, timestampSeconds: number, outputPath?: string) => Promise<FrameCaptureResult>;

  // AI Pipeline (Phase 4, 5, 7: Whisper STT, Neural Translation & Edge-TTS Dubbing)
  aiTranscribe: (options: { audioPath: string; modelSize?: string; sourceLang?: string }) => Promise<{
    success: boolean;
    detectedLanguage: string;
    languageProbability: number;
    durationSeconds: number;
    segments: SpeechSegment[];
  }>;
  aiTranslate: (options: {
    segments: SpeechSegment[];
    targetLang?: string;
    sourceLang?: string;
    style?: string;
    genre?: string;
    engine?: string;
    endpoint?: string;
    prompt?: string;
    apiKey?: string;
  }) => Promise<{
    success: boolean;
    sourceLanguage: string;
    targetLanguage: string;
    style?: string;
    detectedGenre?: string;
    translationEngine?: string;
    segments: SpeechSegment[];
  }>;
  aiTestTranslationKey: (options: {
    engine: string;
    apiKey?: string;
    endpoint?: string;
  }) => Promise<{
    success: boolean;
    engine: string;
    latencyMs?: number;
    sample?: string;
    error?: string;
  }>;
  aiDetectGenre: (segments: SpeechSegment[]) => Promise<{
    success: boolean;
    detectedGenre: string;
  }>;
  aiDub: (options: {
    segments: SpeechSegment[];
    outputDir: string;
    voiceName?: string;
    projectDuration?: number;
    targetLang?: string;
    engine?: 'edge-tts' | 'voxcpm';
    referenceAudioPath?: string;
    voiceStylePrompt?: string;
    voxcpmActor?: string;
  }) => Promise<{
    success: boolean;
    masterDubbedAudioPath: string;
    voice: string;
    durationSeconds: number;
    segments: SpeechSegment[];
  }>;
  aiGetVoices: (langFilter?: string) => Promise<VoiceOption[]>;
  aiGetVoxCpmActors: () => Promise<VoxCpmActor[]>;
  aiSelectReferenceAudio: () => Promise<{ canceled: boolean; filePath?: string; fileName?: string }>;
  aiGetClonedVoices: () => Promise<ClonedVoiceProfile[]>;
  aiSaveClonedVoice: (profile: ClonedVoiceProfile) => Promise<ClonedVoiceProfile>;
  aiDeleteClonedVoice: (id: string) => Promise<boolean>;
  aiRunFullPipeline: (projectId: string, options?: PipelineOptions) => Promise<ProjectData>;
  onAiProgress: (callback: (progress: AiPipelineProgress) => void) => () => void;

  // Logging & Diagnostics
  getLogs: (limit?: number) => Promise<LogEntry[]>;
  onLogMessage: (callback: (entry: LogEntry) => void) => () => void;
  log: (level: LogEntry['level'], source: LogEntry['source'], message: string, details?: any) => Promise<void>;
  clearLogs: () => Promise<boolean>;
  exportLogs: () => Promise<{ success: boolean; path?: string }>;

  // Shell & Utilities
  openExternal: (url: string) => Promise<void>;
  showItemInFolder: (path: string) => Promise<void>;
  getAppVersion: () => Promise<string>;
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI;
  }
}
