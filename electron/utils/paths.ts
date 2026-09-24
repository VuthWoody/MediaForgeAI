import path from 'path';
import os from 'os';
import fs from 'fs';

export function getAppDataDir(): string {
  const baseDir = process.env.APPDATA || path.join(os.homedir(), 'AppData', 'Roaming');
  const appDir = path.join(baseDir, 'MediaForgeAI');
  if (!fs.existsSync(appDir)) {
    fs.mkdirSync(appDir, { recursive: true });
  }
  return appDir;
}

export function getDefaultProjectsDir(): string {
  const appData = getAppDataDir();
  const projDir = path.join(appData, 'Projects');
  if (!fs.existsSync(projDir)) {
    fs.mkdirSync(projDir, { recursive: true });
  }
  return projDir;
}

export function getDefaultDownloadsDir(): string {
  const downloads = path.join(os.homedir(), 'Downloads', 'MediaForgeAI');
  if (!fs.existsSync(downloads)) {
    fs.mkdirSync(downloads, { recursive: true });
  }
  return downloads;
}
