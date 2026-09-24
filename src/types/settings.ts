export interface AppSettings {
  general: {
    theme: 'dark-forge' | 'midnight' | 'cyberpunk';
    defaultSourceLanguage: string;
    defaultTargetLanguage: string;
    projectsDirectory: string;
    autoSaveIntervalSeconds: number;
    startOnDashboard: boolean;
    enableHardwareGauges: boolean;
  };
  downloader: {
    downloadDirectory: string;
    maxConcurrentThreads: number; // 1 - 32
    preferredResolution: 'best' | '4k' | '1080p' | '720p' | 'audio_only';
    preferredFormat: 'mp4' | 'mkv' | 'webm';
    autoDownloadSubtitles: boolean;
    autoDownloadThumbnail: boolean;
    downloadSpeedLimitKbps: number; // 0 for unlimited
    userAgent: string;
  };
  ai: {
    whisperModel: 'tiny' | 'base' | 'small' | 'medium' | 'large-v3';
    whisperEngine: 'local' | 'faster-whisper' | 'cloud-api';
    enableSpeakerDiarization: boolean;
    translationEngine: 'gemini' | 'openai' | 'deepseek' | 'local-llm' | 'smart-contextual' | 'google-translate';
    translationApiKey: string;
    geminiApiKey: string;
    openaiApiKey: string;
    deepseekApiKey: string;
    customLlmEndpoint: string;
    defaultContentGenre: 'auto' | 'documentary' | 'conversational' | 'cinematic' | 'news' | 'tutorial';
    dubbingEngine: 'edge-tts' | 'voxcpm' | 'elevenlabs' | 'piper';
    elevenLabsApiKey: string;
    separationEngine: 'demucs' | 'uvr5';
    demucsModel: 'htdemucs' | 'htdemucs_ft' | 'mdx_extra';
  };
  hardware: {
    preferredEncoder: 'auto' | 'nvenc' | 'qsv' | 'amf' | 'cpu';
    enableHardwareDecoding: boolean;
    workerThreads: number;
    customFFmpegPath?: string;
  };
}

export const DEFAULT_SETTINGS: AppSettings = {
  general: {
    theme: 'dark-forge',
    defaultSourceLanguage: 'en',
    defaultTargetLanguage: 'km',
    projectsDirectory: '',
    autoSaveIntervalSeconds: 60,
    startOnDashboard: true,
    enableHardwareGauges: true,
  },
  downloader: {
    downloadDirectory: '',
    maxConcurrentThreads: 8,
    preferredResolution: '1080p',
    preferredFormat: 'mp4',
    autoDownloadSubtitles: true,
    autoDownloadThumbnail: true,
    downloadSpeedLimitKbps: 0,
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
  },
  ai: {
    whisperModel: 'small',
    whisperEngine: 'local',
    enableSpeakerDiarization: true,
    translationEngine: 'gemini',
    translationApiKey: '',
    geminiApiKey: '',

    openaiApiKey: '',
    deepseekApiKey: '',
    customLlmEndpoint: 'http://localhost:11434/v1',
    defaultContentGenre: 'documentary',
    dubbingEngine: 'edge-tts',
    elevenLabsApiKey: '',
    separationEngine: 'demucs',
    demucsModel: 'htdemucs',
  },
  hardware: {
    preferredEncoder: 'auto',
    enableHardwareDecoding: true,
    workerThreads: 4,
    customFFmpegPath: '',
  },
};
