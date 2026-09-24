import fs from 'fs';
import path from 'path';
import { BrowserWindow } from 'electron';
import { getAppDataDir } from '../utils/paths';

export type LogLevel = 'DEBUG' | 'INFO' | 'WARN' | 'ERROR';

export interface LogEntry {
  id: string;
  timestamp: string;
  level: LogLevel;
  source: 'main' | 'renderer' | 'ffmpeg' | 'downloader' | 'ai';
  message: string;
  details?: any;
}

export class LoggerService {
  private static instance: LoggerService;
  private logFilePath: string;
  private memoryLogs: LogEntry[] = [];
  private maxMemoryLogs: number = 1000;
  private mainWindow: BrowserWindow | null = null;

  private constructor() {
    const appDir = getAppDataDir();
    this.logFilePath = path.join(appDir, 'mediaforge.log');
    this.info('main', 'LoggerService initialized. Log file: ' + this.logFilePath);
  }

  public static getInstance(): LoggerService {
    if (!LoggerService.instance) {
      LoggerService.instance = new LoggerService();
    }
    return LoggerService.instance;
  }

  public setMainWindow(window: BrowserWindow | null) {
    this.mainWindow = window;
  }

  public log(level: LogLevel, source: LogEntry['source'], message: string, details?: any) {
    const entry: LogEntry = {
      id: Math.random().toString(36).substring(2, 11) + '-' + Date.now(),
      timestamp: new Date().toISOString(),
      level,
      source,
      message,
      details: details ? (typeof details === 'object' ? JSON.stringify(details) : String(details)) : undefined,
    };

    this.memoryLogs.push(entry);
    if (this.memoryLogs.length > this.maxMemoryLogs) {
      this.memoryLogs.shift();
    }

    const logLine = `[${entry.timestamp}] [${entry.level}] [${entry.source}] ${entry.message}${entry.details ? ' ' + entry.details : ''}\n`;
    try {
      fs.appendFileSync(this.logFilePath, logLine, 'utf8');
    } catch (err) {
      console.error('Failed to write log file:', err);
    }

    console.log(logLine.trim());

    if (this.mainWindow && !this.mainWindow.isDestroyed()) {
      this.mainWindow.webContents.send('log-message', entry);
    }
  }

  public debug(source: LogEntry['source'], message: string, details?: any) {
    this.log('DEBUG', source, message, details);
  }

  public info(source: LogEntry['source'], message: string, details?: any) {
    this.log('INFO', source, message, details);
  }

  public warn(source: LogEntry['source'], message: string, details?: any) {
    this.log('WARN', source, message, details);
  }

  public error(source: LogEntry['source'], message: string, details?: any) {
    this.log('ERROR', source, message, details);
  }

  public getLogs(limit: number = 200): LogEntry[] {
    return this.memoryLogs.slice(-limit);
  }

  public clearLogs(): boolean {
    this.memoryLogs = [];
    try {
      fs.writeFileSync(this.logFilePath, '', 'utf8');
      this.info('main', 'Log file cleared by user.');
      return true;
    } catch (err) {
      this.error('main', 'Failed to clear log file', err);
      return false;
    }
  }

  public getLogFilePath(): string {
    return this.logFilePath;
  }
}
