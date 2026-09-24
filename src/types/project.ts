export type ProjectStatus = 'draft' | 'transcribing' | 'transcribed' | 'translating' | 'translated' | 'dubbing' | 'dubbed' | 'exporting' | 'completed' | 'failed';

export interface SourceMediaInfo {
  type: 'file' | 'url';
  pathOrUrl: string;
  filename: string;
  durationSeconds: number;
  resolution: {
    width: number;
    height: number;
  };
  fps: number;
  fileSizeBytes: number;
  codec: string;
  audioSampleRate: number;
  audioChannels: number;
  thumbnailPath?: string;
  platform?: 'youtube' | 'facebook' | 'tiktok' | 'twitter' | 'bilibili' | 'instagram' | 'vimeo' | 'twitch' | 'custom' | 'local';
}

export interface SpeechSegment {
  id: string;
  start: number; // in seconds
  end: number;
  speakerId: string;
  speakerName: string;
  originalText: string;
  translatedText?: string;
  confidence: number;
  audioStemPath?: string;
  dubbedAudioPath?: string;
  isEdited?: boolean;
}

export interface SpeakerProfile {
  id: string;
  name: string;
  color: string;
  gender: 'male' | 'female' | 'other';
  assignedVoiceId: string;
  voiceProvider: 'edge-tts' | 'elevenlabs' | 'piper' | 'custom';
  pitchMultiplier: number;
  rateMultiplier: number;
  volumeMultiplier: number;
}

export interface SubtitleStyle {
  fontFamily: string;
  fontSize: number;
  primaryColor: string;
  outlineColor: string;
  outlineWidth: number;
  shadowColor: string;
  shadowBlur: number;
  position: 'bottom' | 'middle' | 'top';
  marginVertical: number;
  alignment: 'left' | 'center' | 'right';
  bold: boolean;
  italic: boolean;
}

export type VoiceMode = 'clean-dub' | 'voice-over' | 'custom-mix' | 'original-only';
export type DubbingEngine = 'edge-tts' | 'voxcpm';

export type TranslationStyle = 'natural' | 'formal' | 'cinematic' | 'concise';
export type ContentGenre = 'auto' | 'documentary' | 'conversational' | 'cinematic' | 'news' | 'tutorial';
export type TranslationEngine = 'gemini' | 'openai' | 'deepseek' | 'local-llm' | 'smart-contextual' | 'google-translate';

export interface ClonedVoiceProfile {
  id: string;
  name: string;
  referenceAudioPath?: string;
  audioPath?: string;
  durationSeconds?: number;
  duration?: number;
  pitchHz?: number;
  pitchF0?: number;
  gender?: 'male' | 'female' | 'custom' | string;
  createdAt: string;
  description?: string;
}

export interface AudioStemsInfo {
  isSeparated?: boolean;
  originalAudioPath?: string;
  vocalsPath?: string;
  musicPath?: string;
  sfxPath?: string;
  dubbedVocalsPath?: string;
  dubbedAudioRevision?: number;
  vocalVolume: number; // 0.0 to 2.0
  musicVolume: number;
  sfxVolume: number;
  dubbedVolume: number;
  voiceMode?: VoiceMode;
  duckingLevel?: number; // 0.0 to 1.0 (auto-ducking multiplier during speech)
  dubbingEngine?: DubbingEngine;
  voxcpmActor?: string;
  voxcpmPrompt?: string;
  referenceAudioPath?: string;
  translationStyle?: TranslationStyle;
  translationPrompt?: string;
  translationEngine?: TranslationEngine;
  contentGenre?: ContentGenre;
  detectedGenre?: ContentGenre;
}

export interface ExportSettings {
  format: 'mp4' | 'mkv' | 'mov' | 'webm' | 'mp3' | 'wav';
  resolutionPreset: 'original' | '4k' | '1080p' | '720p';
  videoCodec: 'auto' | 'h264_nvenc' | 'h264_qsv' | 'h264_amf' | 'libx264' | 'libx265';
  crf: number;
  bitrateKbps: number;
  hardwareAcceleration: boolean;
  burnInSubtitles: boolean;
  includeDubbedAudio: boolean;
  outputPath: string;
}

export interface ProjectData {
  id: string;
  name: string;
  description: string;
  version: string;
  createdAt: string;
  updatedAt: string;
  lastOpenedAt: string;
  status: ProjectStatus;
  progressPercent: number;
  projectDirectory: string;
  
  sourceLanguage: string; // e.g. "en"
  targetLanguage: string; // e.g. "km" (Khmer), "zh", "ja"
  secondaryTargetLanguages?: string[];
  
  sourceMedia?: SourceMediaInfo;
  speakers: SpeakerProfile[];
  segments: SpeechSegment[];
  stems: AudioStemsInfo;
  subtitleStyle: SubtitleStyle;
  exportSettings: ExportSettings;
  
  tags?: string[];
  notes?: string;
}

export interface ProjectSummary {
  id: string;
  name: string;
  description: string;
  status: ProjectStatus;
  progressPercent: number;
  createdAt: string;
  updatedAt: string;
  lastOpenedAt: string;
  sourceLanguage: string;
  targetLanguage: string;
  durationSeconds: number;
  thumbnailUrl?: string;
  projectDirectory: string;
}
