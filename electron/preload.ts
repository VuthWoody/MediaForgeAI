import { contextBridge, ipcRenderer } from 'electron';
import { ProjectData, ProjectSummary } from '../src/types/project';
import { AppSettings } from '../src/types/settings';
import { SystemMetrics, HardwareInfo } from '../src/types/system';
import { LogEntry } from '../src/types/logs';
import { MediaUrlInfo, DownloadJob, DownloadProgress } from '../src/types/downloader';
import { MediaLibraryItem, MediaFilterOptions } from '../src/types/mediaLibrary';
import { WaveformData, AudioExtractionResult, FrameCaptureResult, MediaProbeResult } from '../src/types/studio';

contextBridge.exposeInMainWorld('electronAPI', {
  // Window controls
  minimizeWindow: () => ipcRenderer.invoke('window-minimize'),
  maximizeWindow: () => ipcRenderer.invoke('window-maximize'),
  closeWindow: () => ipcRenderer.invoke('window-close'),
  isWindowMaximized: () => ipcRenderer.invoke('window-is-maximized'),

  // Project operations
  listProjects: (): Promise<ProjectSummary[]> => ipcRenderer.invoke('project-list'),
  getProject: (id: string): Promise<ProjectData | null> => ipcRenderer.invoke('project-get', id),
  createProject: (data: Partial<ProjectData>): Promise<ProjectData> => ipcRenderer.invoke('project-create', data),
  updateProject: (data: ProjectData): Promise<ProjectData> => ipcRenderer.invoke('project-update', data),
  deleteProject: (id: string): Promise<boolean> => ipcRenderer.invoke('project-delete', id),
  duplicateProject: (id: string): Promise<ProjectData> => ipcRenderer.invoke('project-duplicate', id),
  openProjectFolder: (id: string): Promise<void> => ipcRenderer.invoke('project-open-folder', id),
  selectMediaFile: (): Promise<{ canceled: boolean; filePath?: string }> => ipcRenderer.invoke('dialog-select-media-file'),

  // Settings
  getSettings: (): Promise<AppSettings> => ipcRenderer.invoke('settings-get'),
  saveSettings: (settings: AppSettings): Promise<boolean> => ipcRenderer.invoke('settings-save', settings),
  resetSettings: (): Promise<AppSettings> => ipcRenderer.invoke('settings-reset'),

  // System & Hardware
  getSystemMetrics: (): Promise<SystemMetrics> => ipcRenderer.invoke('system-get-metrics'),
  onMetricsUpdate: (callback: (metrics: SystemMetrics) => void) => {
    const handler = (_: any, metrics: SystemMetrics) => callback(metrics);
    ipcRenderer.on('system-metrics-update', handler);
    return () => {
      ipcRenderer.removeListener('system-metrics-update', handler);
    };
  },
  getHardwareInfo: (): Promise<HardwareInfo> => ipcRenderer.invoke('hardware-get-info'),

  // Downloader Module (Phase 2)
  downloaderAnalyzeUrl: (url: string): Promise<MediaUrlInfo> => ipcRenderer.invoke('downloader-analyze-url', url),
  downloaderAddJob: (options: Partial<DownloadJob>): Promise<DownloadJob> => ipcRenderer.invoke('downloader-add-job', options),
  downloaderAddBulkJobs: (urls: string[]): Promise<DownloadJob[]> => ipcRenderer.invoke('downloader-add-bulk', urls),
  downloaderPauseJob: (id: string): Promise<boolean> => ipcRenderer.invoke('downloader-pause-job', id),
  downloaderResumeJob: (id: string): Promise<boolean> => ipcRenderer.invoke('downloader-resume-job', id),
  downloaderCancelJob: (id: string): Promise<boolean> => ipcRenderer.invoke('downloader-cancel-job', id),
  downloaderRetryJob: (id: string): Promise<boolean> => ipcRenderer.invoke('downloader-retry-job', id),
  downloaderClearCompleted: (): Promise<boolean> => ipcRenderer.invoke('downloader-clear-completed'),
  downloaderGetQueue: (): Promise<DownloadJob[]> => ipcRenderer.invoke('downloader-get-queue'),
  onDownloadProgress: (callback: (progress: DownloadProgress) => void) => {
    const handler = (_: any, progress: DownloadProgress) => callback(progress);
    ipcRenderer.on('download-progress', handler);
    return () => {
      ipcRenderer.removeListener('download-progress', handler);
    };
  },

  // Media Library Module (Phase 2)
  mediaLibraryList: (filters?: MediaFilterOptions): Promise<MediaLibraryItem[]> => ipcRenderer.invoke('media-library-list', filters),
  mediaLibraryImportFile: (filePath: string): Promise<MediaLibraryItem> => ipcRenderer.invoke('media-library-import-file', filePath),
  mediaLibraryDelete: (id: string, deleteFromDisk: boolean): Promise<boolean> => ipcRenderer.invoke('media-library-delete', id, deleteFromDisk),
  mediaLibraryCreateProject: (mediaId: string): Promise<ProjectData> => ipcRenderer.invoke('media-library-create-project', mediaId),

  // FFmpeg Studio & Media Processing (Phase 3)
  ffmpegProbe: (filePath: string): Promise<MediaProbeResult> => ipcRenderer.invoke('ffmpeg-probe', filePath),
  ffmpegExtractAudio: (inputPath: string, outputPath?: string): Promise<AudioExtractionResult> => ipcRenderer.invoke('ffmpeg-extract-audio', inputPath, outputPath),
  ffmpegGenerateWaveform: (mediaPath: string, numBuckets?: number): Promise<WaveformData> => ipcRenderer.invoke('ffmpeg-generate-waveform', mediaPath, numBuckets),
  ffmpegCaptureFrame: (videoPath: string, timestampSeconds: number, outputPath?: string): Promise<FrameCaptureResult> => ipcRenderer.invoke('ffmpeg-capture-frame', videoPath, timestampSeconds, outputPath),

  // AI Pipeline (Phase 4, 5, 7: Whisper STT, Neural Translation & Edge-TTS Dubbing)
  aiTranscribe: (options: { audioPath: string; modelSize?: string; sourceLang?: string }) => ipcRenderer.invoke('ai-transcribe', options),
  aiTranslate: (options: {
    segments: any[];
    targetLang?: string;
    sourceLang?: string;
    style?: string;
    genre?: string;
    engine?: string;
    endpoint?: string;
    prompt?: string;
    apiKey?: string;
  }) => ipcRenderer.invoke('ai-translate', options),
  aiTestTranslationKey: (options: { engine: string; apiKey?: string; endpoint?: string }) =>
    ipcRenderer.invoke('ai-test-translation-key', options),
  aiDetectGenre: (segments: any[]) => ipcRenderer.invoke('ai-detect-genre', segments),
  aiDub: (options: {
    segments: any[];
    outputDir: string;
    voiceName?: string;
    projectDuration?: number;
    targetLang?: string;
    engine?: string;
    referenceAudioPath?: string;
    voiceStylePrompt?: string;
    voxcpmActor?: string;
  }) => ipcRenderer.invoke('ai-dub', options),
  aiGetVoices: (langFilter?: string) => ipcRenderer.invoke('ai-get-voices', langFilter),
  aiGetVoxCpmActors: () => ipcRenderer.invoke('ai-get-voxcpm-actors'),
  aiSelectReferenceAudio: () => ipcRenderer.invoke('ai-select-reference-audio'),
  aiGetClonedVoices: () => ipcRenderer.invoke('ai-get-cloned-voices'),
  aiSaveClonedVoice: (profile: any) => ipcRenderer.invoke('ai-save-cloned-voice', profile),
  aiDeleteClonedVoice: (id: string) => ipcRenderer.invoke('ai-delete-cloned-voice', id),
  aiRunFullPipeline: (projectId: string, options?: any) => ipcRenderer.invoke('ai-run-full-pipeline', { projectId, options }),
  onAiProgress: (callback: (progress: any) => void) => {
    const handler = (_: any, progress: any) => callback(progress);
    ipcRenderer.on('ai-progress', handler);
    return () => {
      ipcRenderer.removeListener('ai-progress', handler);
    };
  },

  // Logging & Diagnostics
  getLogs: (limit?: number): Promise<LogEntry[]> => ipcRenderer.invoke('logs-get', limit),
  onLogMessage: (callback: (entry: LogEntry) => void) => {
    const handler = (_: any, entry: LogEntry) => callback(entry);
    ipcRenderer.on('log-message', handler);
    return () => {
      ipcRenderer.removeListener('log-message', handler);
    };
  },
  log: (level: LogEntry['level'], source: LogEntry['source'], message: string, details?: any): Promise<void> => {
    return ipcRenderer.invoke('log-add', { level, source, message, details });
  },
  clearLogs: (): Promise<boolean> => ipcRenderer.invoke('logs-clear'),
  exportLogs: (): Promise<{ success: boolean; path?: string }> => ipcRenderer.invoke('logs-export'),

  // Shell & Utilities
  openExternal: (url: string) => ipcRenderer.invoke('shell-open-external', url),
  showItemInFolder: (path: string) => ipcRenderer.invoke('shell-show-item', path),
  getAppVersion: () => ipcRenderer.invoke('app-get-version'),
});
