import { exec } from 'child_process';
import util from 'util';
import os from 'os';
import { LoggerService } from './LoggerService';

const execAsync = util.promisify(exec);

export interface HardwareInfo {
  osPlatform: string;
  osRelease: string;
  osArch: string;
  cpuModel: string;
  cpuCores: number;
  totalMemoryBytes: number;
  gpus: Array<{
    name: string;
    adapterRamBytes: number;
  }>;
  ffmpeg: {
    installed: boolean;
    version: string;
    path: string;
    supportedEncoders: string[];
  };
  ytDlp: {
    installed: boolean;
    version: string;
    path: string;
  };
  python: {
    installed: boolean;
    version: string;
    path: string;
  };
}

export class HardwareService {
  private static instance: HardwareService;
  private cachedInfo: HardwareInfo | null = null;
  private logger = LoggerService.getInstance();

  private constructor() {}

  public static getInstance(): HardwareService {
    if (!HardwareService.instance) {
      HardwareService.instance = new HardwareService();
    }
    return HardwareService.instance;
  }

  public async getHardwareInfo(forceRefresh = false): Promise<HardwareInfo> {
    if (this.cachedInfo && !forceRefresh) {
      return this.cachedInfo;
    }

    const cpus = os.cpus();
    const cpuModel = cpus.length > 0 ? cpus[0].model : 'Unknown Processor';
    const cpuCores = cpus.length;
    const totalMemoryBytes = os.totalmem();

    // Query GPUs via PowerShell on Windows
    const gpus: Array<{ name: string; adapterRamBytes: number }> = [];
    try {
      const { stdout } = await execAsync('powershell -Command "Get-CimInstance Win32_VideoController | Select-Object Name, AdapterRAM | ConvertTo-Json"');
      const parsed = JSON.parse(stdout.trim());
      const items = Array.isArray(parsed) ? parsed : [parsed];
      for (const item of items) {
        if (item && item.Name) {
          gpus.push({
            name: item.Name,
            adapterRamBytes: Number(item.AdapterRAM) || 0,
          });
        }
      }
    } catch (err) {
      this.logger.warn('main', 'Failed to retrieve GPU details via CIM', err);
      gpus.push({ name: 'Generic Display Adapter', adapterRamBytes: 0 });
    }

    // Probe FFmpeg
    let ffmpegInstalled = false;
    let ffmpegVersion = '';
    let ffmpegPath = 'ffmpeg';
    const supportedEncoders: string[] = [];

    try {
      const { stdout: versionOut } = await execAsync('ffmpeg -version');
      ffmpegInstalled = true;
      const match = versionOut.match(/ffmpeg version ([^\s]+)/i);
      ffmpegVersion = match ? match[1] : 'Installed';

      // Check encoders
      const { stdout: encOut } = await execAsync('ffmpeg -encoders');
      if (encOut.includes('h264_nvenc')) supportedEncoders.push('h264_nvenc (NVIDIA)');
      if (encOut.includes('hevc_nvenc')) supportedEncoders.push('hevc_nvenc (NVIDIA)');
      if (encOut.includes('h264_qsv')) supportedEncoders.push('h264_qsv (Intel QuickSync)');
      if (encOut.includes('hevc_qsv')) supportedEncoders.push('hevc_qsv (Intel QuickSync)');
      if (encOut.includes('h264_amf')) supportedEncoders.push('h264_amf (AMD AMF)');
      if (encOut.includes('libx264')) supportedEncoders.push('libx264 (CPU)');
      if (encOut.includes('libx265')) supportedEncoders.push('libx265 (CPU)');

      this.logger.info('ffmpeg', `FFmpeg detected: version ${ffmpegVersion}, Encoders: ${supportedEncoders.join(', ')}`);
    } catch (err) {
      this.logger.warn('ffmpeg', 'FFmpeg not detected in PATH');
    }

    // Probe yt-dlp
    let ytDlpInstalled = false;
    let ytDlpVersion = '';
    let ytDlpPath = 'yt-dlp';
    try {
      const { stdout: ytOut } = await execAsync('yt-dlp --version');
      ytDlpInstalled = true;
      ytDlpVersion = ytOut.trim();
      this.logger.info('downloader', `yt-dlp detected: version ${ytDlpVersion}`);
    } catch (err) {
      this.logger.warn('downloader', 'yt-dlp not detected in PATH');
    }

    // Probe Python
    let pythonInstalled = false;
    let pythonVersion = '';
    let pythonPath = 'python';
    try {
      const { stdout: pyOut } = await execAsync('python --version');
      pythonInstalled = true;
      pythonVersion = pyOut.trim();
      this.logger.info('ai', `Python environment detected: ${pythonVersion}`);
    } catch (err) {
      this.logger.warn('ai', 'Python environment not detected');
    }

    this.cachedInfo = {
      osPlatform: os.platform(),
      osRelease: os.release(),
      osArch: os.arch(),
      cpuModel,
      cpuCores,
      totalMemoryBytes,
      gpus,
      ffmpeg: {
        installed: ffmpegInstalled,
        version: ffmpegVersion,
        path: ffmpegPath,
        supportedEncoders,
      },
      ytDlp: {
        installed: ytDlpInstalled,
        version: ytDlpVersion,
        path: ytDlpPath,
      },
      python: {
        installed: pythonInstalled,
        version: pythonVersion,
        path: pythonPath,
      },
    };

    return this.cachedInfo;
  }
}
