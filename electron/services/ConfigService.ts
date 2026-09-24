import fs from 'fs';
import path from 'path';
import { getAppDataDir, getDefaultProjectsDir, getDefaultDownloadsDir } from '../utils/paths';
import { LoggerService } from './LoggerService';

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
    maxConcurrentThreads: number;
    preferredResolution: 'best' | '4k' | '1080p' | '720p' | 'audio_only';
    preferredFormat: 'mp4' | 'mkv' | 'webm';
    autoDownloadSubtitles: boolean;
    autoDownloadThumbnail: boolean;
    downloadSpeedLimitKbps: number;
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

export class ConfigService {
  private static instance: ConfigService;
  private configPath: string;
  private settings: AppSettings;
  private logger = LoggerService.getInstance();

  private constructor() {
    const appDir = getAppDataDir();
    this.configPath = path.join(appDir, 'config.json');
    this.settings = this.loadSettings();
  }

  public static getInstance(): ConfigService {
    if (!ConfigService.instance) {
      ConfigService.instance = new ConfigService();
    }
    return ConfigService.instance;
  }

  private getDefaultSettings(): AppSettings {
    return {
      general: {
        theme: 'dark-forge',
        defaultSourceLanguage: 'en',
        defaultTargetLanguage: 'km', // Khmer as requested in vision
        projectsDirectory: getDefaultProjectsDir(),
        autoSaveIntervalSeconds: 60,
        startOnDashboard: true,
        enableHardwareGauges: true,
      },
      downloader: {
        downloadDirectory: getDefaultDownloadsDir(),
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
  }

  private loadSettings(): AppSettings {
    const defaults = this.getDefaultSettings();
    try {
      if (fs.existsSync(this.configPath)) {
        const data = fs.readFileSync(this.configPath, 'utf8');
        const parsed = JSON.parse(data);
        return {
          general: { ...defaults.general, ...(parsed.general || {}) },
          downloader: { ...defaults.downloader, ...(parsed.downloader || {}) },
          ai: { ...defaults.ai, ...(parsed.ai || {}) },
          hardware: { ...defaults.hardware, ...(parsed.hardware || {}) },
        };
      }
    } catch (err) {
      this.logger.error('main', 'Failed to read config file, falling back to defaults', err);
    }

    this.settings = defaults;
    try {
      fs.writeFileSync(this.configPath, JSON.stringify(defaults, null, 2), 'utf8');
      this.logger.info('main', 'Default config file written to ' + this.configPath);
    } catch (err) {
      this.logger.error('main', 'Failed to save default config', err);
    }
    return defaults;
  }

  public getSettings(): AppSettings {
    return this.settings || this.getDefaultSettings();
  }

  public saveSettings(newSettings: Partial<AppSettings>): boolean {
    const current = this.settings || this.getDefaultSettings();
    try {
      this.settings = {
        general: { ...current.general, ...(newSettings.general || {}) },
        downloader: { ...current.downloader, ...(newSettings.downloader || {}) },
        ai: { ...current.ai, ...(newSettings.ai || {}) },
        hardware: { ...current.hardware, ...(newSettings.hardware || {}) },
      };

      fs.writeFileSync(this.configPath, JSON.stringify(this.settings, null, 2), 'utf8');
      this.logger.info('main', 'Application settings saved successfully.');
      return true;
    } catch (err) {
      this.logger.error('main', 'Failed to save settings', err);
      return false;
    }
  }

  public resetSettings(): AppSettings {
    const defaults = this.getDefaultSettings();
    this.saveSettings(defaults);
    return defaults;
  }
}
