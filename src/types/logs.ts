export type LogLevel = 'DEBUG' | 'INFO' | 'WARN' | 'ERROR';

export interface LogEntry {
  id: string;
  timestamp: string;
  level: LogLevel;
  source: 'main' | 'renderer' | 'ffmpeg' | 'downloader' | 'ai';
  message: string;
  details?: any;
}
