import { app, BrowserWindow, ipcMain, dialog, shell, protocol, net } from 'electron';
import path from 'path';
import fs from 'fs';
import { Readable } from 'stream';
import { pathToFileURL } from 'url';

function getMimeType(filePath: string): string {
  const ext = path.extname(filePath).toLowerCase();
  switch (ext) {
    case '.mp4':
    case '.m4v':
      return 'video/mp4';
    case '.webm':
      return 'video/webm';
    case '.mkv':
      return 'video/x-matroska';
    case '.mov':
      return 'video/quicktime';
    case '.ts':
      return 'video/mp2t';
    case '.mp3':
      return 'audio/mpeg';
    case '.wav':
      return 'audio/wav';
    case '.ogg':
    case '.opus':
      return 'audio/ogg';
    case '.aac':
      return 'audio/aac';
    case '.flac':
      return 'audio/flac';
    default:
      return 'application/octet-stream';
  }
}
import { ConfigService } from './services/ConfigService';
import { ProjectService } from './services/ProjectService';
import { HardwareService } from './services/HardwareService';
import { SystemMetricsService } from './services/SystemMetricsService';
import { LoggerService } from './services/LoggerService';
import { DownloaderService } from './services/DownloaderService';
import { MediaLibraryService } from './services/MediaLibraryService';
import { FFmpegService } from './services/FFmpegService';
import { AiPipelineService } from './services/AiPipelineService';

// Register custom privileged scheme for smooth sub-second media streaming and range requests
protocol.registerSchemesAsPrivileged([
  {
    scheme: 'media',
    privileges: {
      standard: true,
      secure: true,
      supportFetchAPI: true,
      corsEnabled: true,
      stream: true,
      bypassCSP: true,
    },
  },
]);

let mainWindow: BrowserWindow | null = null;

const isDev = process.env.NODE_ENV === 'development';

async function createWindow() {
  const logger = LoggerService.getInstance();
  const configService = ConfigService.getInstance();
  const projectService = ProjectService.getInstance();
  const hardwareService = HardwareService.getInstance();
  const metricsService = SystemMetricsService.getInstance();

  logger.info('main', 'Creating main application window...');

  mainWindow = new BrowserWindow({
    width: 1380,
    height: 880,
    minWidth: 1080,
    minHeight: 700,
    frame: false,
    titleBarStyle: 'hidden',
    backgroundColor: '#0a0c10',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: false,
    },
    show: false,
  });

  logger.setMainWindow(mainWindow);
  metricsService.setMainWindow(mainWindow);
  DownloaderService.getInstance().setMainWindow(mainWindow);
  AiPipelineService.getInstance().setMainWindow(mainWindow);

  // Ready-to-show handler for smooth presentation
  mainWindow.once('ready-to-show', () => {
    if (mainWindow) {
      mainWindow.show();
      mainWindow.focus();
    }
  });

  // Safety fallback to guarantee the window pops up
  setTimeout(() => {
    if (mainWindow && !mainWindow.isDestroyed() && !mainWindow.isVisible()) {
      mainWindow.show();
      mainWindow.focus();
    }
  }, 400);

  // Query hardware specs early and update metrics service
  hardwareService.getHardwareInfo().then((info) => {
    if (info.gpus.length > 0) {
      metricsService.setGpuDetails(info.gpus[0].name, info.gpus[0].adapterRamBytes);
    }
    logger.info('main', `System info initialized. GPU: ${info.gpus.map(g => g.name).join(', ')}`);
  });

  // Start periodic system telemetry sampling
  metricsService.startSampling(2000);

  mainWindow.webContents.on('did-fail-load', (_, errorCode, errorDesc) => {
    logger.error('main', `webContents did-fail-load: ${errorDesc} (${errorCode})`);
  });

  mainWindow.webContents.on('render-process-gone', (_, details) => {
    logger.error('main', `webContents render-process-gone: ${JSON.stringify(details)}`);
  });

  mainWindow.webContents.on('console-message', (_, level, message, line, sourceId) => {
    if (level >= 2) {
      logger.warn('renderer', `[${line}:${sourceId}] ${message}`);
    }
  });

  // Load production bundle from dist/index.html or dev server
  const isDev = !app.isPackaged && process.env.NODE_ENV === 'development';
  const prodHtmlCandidates = [
    path.join(__dirname, '..', '..', 'dist', 'index.html'),
    path.join(__dirname, '..', 'dist', 'index.html'),
    path.join(process.cwd(), 'dist', 'index.html'),
  ];
  const htmlPath = prodHtmlCandidates.find(p => fs.existsSync(p)) || prodHtmlCandidates[0];

  try {
    if (isDev) {
      await mainWindow.loadURL('http://localhost:5173');
    } else {
      if (fs.existsSync(htmlPath)) {
        await mainWindow.loadFile(htmlPath);
        logger.info('main', `Successfully loaded ${htmlPath} into window.`);
      } else {
        logger.warn('main', 'dist/index.html not found, attempting dev server http://localhost:5173');
        await mainWindow.loadURL('http://localhost:5173');
      }
    }
  } catch (loadErr) {
    logger.error('main', 'Failed to load window content', loadErr);
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
    logger.setMainWindow(null);
    metricsService.setMainWindow(null);
    DownloaderService.getInstance().setMainWindow(null);
    AiPipelineService.getInstance().setMainWindow(null);
  });

  if (process.env.TEST_DUB_VERIFY === '1') {
    setTimeout(async () => {
      try {
        if (!mainWindow) return;
        logger.info('main', 'TEST_DUB_VERIFY: Starting automated UI test...');
        // 1. Wait for projects to mount on Dashboard and click Open
        await mainWindow.webContents.executeJavaScript(`
          (() => {
            const openBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.trim() === 'Open');
            if (openBtn) openBtn.click();
          })()
        `);
        // 2. Wait for Studio view and media to mount
        await new Promise(r => setTimeout(r, 3500));

        // 3. Switch to Dubbing tab in inspector and select VoxCPM
        const result = await mainWindow.webContents.executeJavaScript(`
          (async () => {
            const stemsTab = Array.from(document.querySelectorAll('.media-inspector-panel button')).find(b => b.innerText.includes('Dubbing'));
            if (stemsTab) stemsTab.click();
            await new Promise(r => setTimeout(r, 600));

            // Select VoxCPM engine
            const voxBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('VoxCPM'));
            if (voxBtn) voxBtn.click();
            await new Promise(r => setTimeout(r, 600));

            // Click Voice-Over auto-duck button in stem mixing console
            const voBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Voice-Over'));
            if (voBtn) voBtn.click();

            return {
              audioModeButtons: Array.from(document.querySelectorAll('button')).filter(b => b.innerText.includes('Dub') || b.innerText.includes('Voice-Over')).map(b => b.innerText.trim()),
              hasVoxBtn: !!voxBtn
            };
          })()
        `);
        logger.info('main', `TEST_DUB_VERIFY: Executed UI interaction: ${JSON.stringify(result)}`);
        await new Promise(r => setTimeout(r, 1500));

        // 4. Capture verification screenshot
        const image = await mainWindow.capturePage();
        const savePath = path.resolve('C:/Users/sakpo/.gemini/antigravity-ide/brain/09e1e7e2-b0bd-4f74-a687-f08af038ffe2/scratch/voxcpm_voice_modes_verified.png');
        fs.writeFileSync(savePath, image.toPNG());
        logger.info('main', `TEST_DUB_VERIFY: Screenshot saved successfully to ${savePath}`);
        console.log('TEST_DUB_VERIFY: Screenshot saved successfully to', savePath);
        app.quit();
      } catch (e) {
        console.error('TEST_DUB_VERIFY error:', e);
        app.quit();
      }
    }, 4500);
  }

}

process.on('uncaughtException', (err) => {
  LoggerService.getInstance().error('main', 'Uncaught Exception', err);
});

process.on('unhandledRejection', (reason) => {
  LoggerService.getInstance().error('main', 'Unhandled Rejection', reason);
});

// App lifecycle
app.whenReady().then(() => {
  // Protocol handler for streaming local video/audio with range header support
  protocol.handle('media', (request) => {
    try {
      const url = new URL(request.url);
      let filePath = '';

      if (url.host === 'play') {
        // Format: media://play/<base64urlToken>
        const token = url.pathname.replace(/^\/+/, '');
        filePath = Buffer.from(token, 'base64url').toString('utf8');
      } else {
        // Fallback for raw format: media:///<path>
        let rawPath = request.url.replace(/^media:\/\/+/i, '');
        if (process.platform === 'win32') {
          rawPath = rawPath.replace(/^\/+([a-zA-Z]:)/, '$1');
        }
        filePath = decodeURIComponent(rawPath);
      }

      filePath = path.normalize(filePath);

      if (!fs.existsSync(filePath)) {
        LoggerService.getInstance().warn('main', `media:// file not found on disk: "${filePath}"`);
        return new Response('Media file not found on disk', { status: 404 });
      }

      const stat = fs.statSync(filePath);
      const fileSize = stat.size;
      const mimeType = getMimeType(filePath);
      const rangeHeader = request.headers.get('range');

      if (!rangeHeader) {
        const stream = fs.createReadStream(filePath);
        return new Response(Readable.toWeb(stream as any) as any, {
          status: 200,
          headers: {
            'Content-Length': fileSize.toString(),
            'Content-Type': mimeType,
            'Accept-Ranges': 'bytes',
          },
        });
      }

      const parts = rangeHeader.replace(/bytes=/, '').split('-');
      const start = parseInt(parts[0], 10) || 0;
      const end = parts[1] ? parseInt(parts[1], 10) : fileSize - 1;

      if (start >= fileSize || end >= fileSize || start > end) {
        return new Response('Requested range not satisfiable', {
          status: 416,
          headers: {
            'Content-Range': `bytes */${fileSize}`,
          },
        });
      }

      const chunkSize = end - start + 1;
      const stream = fs.createReadStream(filePath, { start, end });

      return new Response(Readable.toWeb(stream as any) as any, {
        status: 206,
        headers: {
          'Content-Range': `bytes ${start}-${end}/${fileSize}`,
          'Accept-Ranges': 'bytes',
          'Content-Length': chunkSize.toString(),
          'Content-Type': mimeType,
        },
      });
    } catch (err) {
      LoggerService.getInstance().error('main', 'Error serving media:// protocol request', err);
      return new Response('Media file error', { status: 500 });
    }
  });

  setupIpcHandlers();
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  SystemMetricsService.getInstance().stopSampling();
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

function setupIpcHandlers() {
  const logger = LoggerService.getInstance();
  const configService = ConfigService.getInstance();
  const projectService = ProjectService.getInstance();
  const hardwareService = HardwareService.getInstance();
  const metricsService = SystemMetricsService.getInstance();

  // Window Controls
  ipcMain.handle('window-minimize', () => {
    mainWindow?.minimize();
  });

  ipcMain.handle('window-maximize', () => {
    if (!mainWindow) return;
    if (mainWindow.isMaximized()) {
      mainWindow.unmaximize();
    } else {
      mainWindow.maximize();
    }
  });

  ipcMain.handle('window-close', () => {
    mainWindow?.close();
  });

  ipcMain.handle('window-is-maximized', () => {
    return mainWindow ? mainWindow.isMaximized() : false;
  });

  // Project Management
  ipcMain.handle('project-list', async () => {
    return await projectService.listProjects();
  });

  ipcMain.handle('project-get', async (_, id: string) => {
    return await projectService.getProject(id);
  });

  ipcMain.handle('project-create', async (_, data) => {
    return await projectService.createProject(data);
  });

  ipcMain.handle('project-update', async (_, data) => {
    return await projectService.updateProject(data);
  });

  ipcMain.handle('project-delete', async (_, id: string) => {
    return await projectService.deleteProject(id);
  });

  ipcMain.handle('project-duplicate', async (_, id: string) => {
    return await projectService.duplicateProject(id);
  });

  ipcMain.handle('project-open-folder', async (_, id: string) => {
    await projectService.openProjectFolder(id);
  });

  // File Dialog
  ipcMain.handle('dialog-select-media-file', async () => {
    if (!mainWindow) return { canceled: true };
    const result = await dialog.showOpenDialog(mainWindow, {
      title: 'Select Media File',
      properties: ['openFile'],
      filters: [
        { name: 'Video Files', extensions: ['mp4', 'mkv', 'mov', 'avi', 'webm', 'ts', 'flv'] },
        { name: 'Audio Files', extensions: ['mp3', 'wav', 'aac', 'm4a', 'flac', 'ogg'] },
        { name: 'All Files', extensions: ['*'] },
      ],
    });

    if (result.canceled || result.filePaths.length === 0) {
      return { canceled: true };
    }
    return { canceled: false, filePath: result.filePaths[0] };
  });

  // Downloader (Phase 2)
  const downloaderService = DownloaderService.getInstance();
  ipcMain.handle('downloader-analyze-url', async (_, url: string) => {
    return await downloaderService.analyzeUrl(url);
  });
  ipcMain.handle('downloader-add-job', async (_, options) => {
    return await downloaderService.addJob(options);
  });
  ipcMain.handle('downloader-add-bulk', async (_, urls: string[]) => {
    return await downloaderService.addBulkJobs(urls);
  });
  ipcMain.handle('downloader-pause-job', async (_, id: string) => {
    return await downloaderService.pauseJob(id);
  });
  ipcMain.handle('downloader-resume-job', async (_, id: string) => {
    return await downloaderService.resumeJob(id);
  });
  ipcMain.handle('downloader-cancel-job', async (_, id: string) => {
    return await downloaderService.cancelJob(id);
  });
  ipcMain.handle('downloader-retry-job', async (_, id: string) => {
    return await downloaderService.retryJob(id);
  });
  ipcMain.handle('downloader-clear-completed', async () => {
    return downloaderService.clearCompleted();
  });
  ipcMain.handle('downloader-get-queue', async () => {
    return downloaderService.getQueue();
  });

  // Media Library (Phase 2)
  const mediaLibraryService = MediaLibraryService.getInstance();
  ipcMain.handle('media-library-list', async (_, filters) => {
    return await mediaLibraryService.listMedia(filters);
  });
  ipcMain.handle('media-library-import-file', async (_, filePath: string) => {
    return await mediaLibraryService.importLocalFile(filePath);
  });
  ipcMain.handle('media-library-delete', async (_, id: string, deleteFromDisk: boolean) => {
    return await mediaLibraryService.deleteMedia(id, deleteFromDisk);
  });
  ipcMain.handle('media-library-create-project', async (_, mediaId: string) => {
    return await mediaLibraryService.createStudioProjectFromMedia(mediaId);
  });

  // FFmpeg Studio & Media Processing (Phase 3)
  const ffmpegService = FFmpegService.getInstance();
  ipcMain.handle('ffmpeg-probe', async (_, filePath: string) => {
    return await ffmpegService.probeMedia(filePath);
  });

  ipcMain.handle('ffmpeg-extract-audio', async (_, inputPath: string, outputPath?: string) => {
    return await ffmpegService.extractAudio(inputPath, outputPath);
  });

  ipcMain.handle('ffmpeg-generate-waveform', async (_, mediaPath: string, numBuckets?: number) => {
    return await ffmpegService.generateWaveform(mediaPath, numBuckets);
  });

  ipcMain.handle('ffmpeg-capture-frame', async (_, videoPath: string, timestampSeconds: number, outputPath?: string) => {
    return await ffmpegService.captureFrame(videoPath, timestampSeconds, outputPath);
  });

  // AI Pipeline (Whisper STT, Neural Translation & Edge-TTS Dubbing)
  const aiPipelineService = AiPipelineService.getInstance();
  ipcMain.handle('ai-transcribe', async (_, { audioPath, modelSize, sourceLang }) => {
    return await aiPipelineService.transcribeAudio(audioPath, modelSize, sourceLang);
  });

  ipcMain.handle('ai-translate', async (_, { segments, targetLang, sourceLang, style, genre, engine, endpoint, prompt, apiKey }) => {
    return await aiPipelineService.translateSegments(segments, targetLang, sourceLang, style, {
      genre,
      engine,
      endpoint,
      prompt,
      apiKey,
    });
  });

  ipcMain.handle('ai-test-translation-key', async (_, { engine, apiKey, endpoint }) => {
    return await aiPipelineService.testTranslationKey(engine, apiKey, endpoint);
  });

  ipcMain.handle('ai-detect-genre', async (_, segments) => {
    return await aiPipelineService.detectGenre(segments);
  });

  ipcMain.handle('ai-dub', async (_, { segments, outputDir, voiceName, projectDuration, targetLang, engine, referenceAudioPath, voiceStylePrompt, voxcpmActor }) => {
    return await aiPipelineService.dubSegments(segments, outputDir, voiceName, projectDuration, {
      engine,
      referenceAudioPath,
      voiceStylePrompt,
      voxcpmActor,
      targetLang,
    });
  });

  ipcMain.handle('ai-get-voices', async (_, langFilter?: string) => {
    return await aiPipelineService.getVoices(langFilter);
  });

  ipcMain.handle('ai-get-voxcpm-actors', async () => {
    return await aiPipelineService.getVoxCpmActors();
  });

  ipcMain.handle('ai-select-reference-audio', async () => {
    if (!mainWindow) return { canceled: true };
    const result = await dialog.showOpenDialog(mainWindow, {
      title: 'Select Reference Audio File for Voice Cloning (3-15 seconds clear speech)',
      properties: ['openFile'],
      filters: [
        { name: 'Audio Files (*.wav, *.mp3, *.m4a, *.aac, *.flac, *.ogg)', extensions: ['wav', 'mp3', 'm4a', 'aac', 'flac', 'ogg'] },
        { name: 'All Files', extensions: ['*'] },
      ],
    });
    if (result.canceled || result.filePaths.length === 0) {
      return { canceled: true };
    }
    const chosen = result.filePaths[0];
    return {
      canceled: false,
      filePath: chosen,
      fileName: path.basename(chosen),
    };
  });

  ipcMain.handle('ai-get-cloned-voices', async () => {
    return await aiPipelineService.getClonedVoices();
  });

  ipcMain.handle('ai-save-cloned-voice', async (_, profile) => {
    return await aiPipelineService.saveClonedVoice(profile);
  });

  ipcMain.handle('ai-delete-cloned-voice', async (_, id: string) => {
    return await aiPipelineService.deleteClonedVoice(id);
  });

  ipcMain.handle('ai-run-full-pipeline', async (_, { projectId, options }) => {
    return await aiPipelineService.runFullPipeline(projectId, options);
  });

  // Settings
  ipcMain.handle('settings-get', async () => {
    return configService.getSettings();
  });

  ipcMain.handle('settings-save', async (_, newSettings) => {
    return configService.saveSettings(newSettings);
  });

  ipcMain.handle('settings-reset', async () => {
    return configService.resetSettings();
  });

  // Hardware & Metrics
  ipcMain.handle('system-get-metrics', async () => {
    return await metricsService.getCurrentMetrics();
  });

  ipcMain.handle('hardware-get-info', async () => {
    return await hardwareService.getHardwareInfo();
  });

  // Logging
  ipcMain.handle('logs-get', async (_, limit?: number) => {
    return logger.getLogs(limit);
  });

  ipcMain.handle('log-add', async (_, { level, source, message, details }) => {
    logger.log(level, source, message, details);
  });

  ipcMain.handle('logs-clear', async () => {
    return logger.clearLogs();
  });

  ipcMain.handle('logs-export', async () => {
    if (!mainWindow) return { success: false };
    const saveDialogResult = await dialog.showSaveDialog(mainWindow, {
      title: 'Export Application Logs',
      defaultPath: `mediaforge-logs-${new Date().toISOString().replace(/[:.]/g, '-')}.log`,
      filters: [{ name: 'Log Files', extensions: ['log', 'txt'] }],
    });

    if (saveDialogResult.canceled || !saveDialogResult.filePath) {
      return { success: false };
    }

    try {
      const srcPath = logger.getLogFilePath();
      if (fs.existsSync(srcPath)) {
        fs.copyFileSync(srcPath, saveDialogResult.filePath);
      } else {
        fs.writeFileSync(saveDialogResult.filePath, 'No logs recorded.', 'utf8');
      }
      return { success: true, path: saveDialogResult.filePath };
    } catch (err) {
      logger.error('main', 'Failed to export log file', err);
      return { success: false };
    }
  });

  // Shell & Utilities
  ipcMain.handle('shell-open-external', async (_, url: string) => {
    await shell.openExternal(url);
  });

  ipcMain.handle('shell-show-item', async (_, targetPath: string) => {
    shell.showItemInFolder(targetPath);
  });

  ipcMain.handle('app-get-version', async () => {
    return app.getVersion();
  });
}
