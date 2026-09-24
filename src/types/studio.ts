import { TranslationEngine, ContentGenre } from './project';

export type AspectRatioType = 'original' | '9:16' | '16:9' | '1:1' | '4:5' | '21:9';
export type AspectRatioFitMode = 'contain' | 'cover' | 'blur-fill';

export interface AspectRatioPreset {
  id: AspectRatioType;
  label: string;
  ratio: number | null; // width / height, null = original
  icon: string;
  platform: string;
  description: string;
}

export interface PlaybackState {
  currentTime: number; // in seconds
  duration: number; // in seconds
  isPlaying: boolean;
  playbackRate: number; // 0.25 to 2.0
  volume: number; // 0.0 to 1.0
  isMuted: boolean;
  fps: number; // e.g. 24, 25, 30, 60
  isLooping: boolean;
}

export interface WaveformData {
  peaks: number[]; // Normalized amplitudes between 0.0 and 1.0
  durationSeconds: number;
}

export interface AudioExtractionResult {
  success: boolean;
  wavPath: string;
  fileSizeBytes: number;
  durationSeconds: number;
  sampleRate: number;
  channels: number;
  errorMessage?: string;
}

export interface FrameCaptureResult {
  success: boolean;
  imagePath: string;
  timestampSeconds: number;
  errorMessage?: string;
}

export interface StreamInfo {
  index: number;
  codecType: 'video' | 'audio' | 'subtitle' | string;
  codecName: string;
  codecLongName?: string;
  width?: number;
  height?: number;
  fps?: number;
  sampleRate?: number;
  channels?: number;
  channelLayout?: string;
  bitrate?: number;
  duration?: number;
}

export interface MediaProbeResult {
  formatName: string;
  formatLongName: string;
  durationSeconds: number;
  fileSizeBytes: number;
  overallBitrate: number;
  videoStreams: StreamInfo[];
  audioStreams: StreamInfo[];
  subtitleStreams: StreamInfo[];
}

export interface AiPipelineProgress {
  type: 'progress';
  stage: 'transcribing' | 'translating' | 'dubbing' | 'completed' | 'error';
  percent: number;
  message: string;
  timestamp: number;
}

export interface VoiceOption {
  shortName: string;
  locale: string;
  gender: string;
  friendlyName: string;
}

export type VoiceTrackMode = 'clean-dub' | 'voice-over' | 'custom-mix' | 'original-only';
export type DubbingEngineType = 'edge-tts' | 'voxcpm';

export interface VoxCpmActor {
  id: string;
  name: string;
  gender: 'male' | 'female';
  styleDescription: string;
  recommendedUse: string;
  isClone?: boolean;
}

export type TranslationStyleType = 'natural' | 'formal' | 'cinematic' | 'concise';

export interface PipelineOptions {
  modelSize?: 'tiny' | 'base' | 'small' | 'medium';
  sourceLanguage?: string;
  targetLanguage?: string;
  voiceName?: string;
  style?: TranslationStyleType;
  prompt?: string;
  apiKey?: string;
  engine?: DubbingEngineType;
  referenceAudioPath?: string;
  voiceStylePrompt?: string;
  voxcpmActor?: string;
  translationEngine?: TranslationEngine;
  contentGenre?: ContentGenre;
  endpoint?: string;
}


