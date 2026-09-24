import os from 'os';
import { exec } from 'child_process';
import util from 'util';
import { BrowserWindow } from 'electron';
import { LoggerService } from './LoggerService';

const execAsync = util.promisify(exec);

export interface SystemMetrics {
  cpuUsagePercent: number;
  memoryUsedBytes: number;
  memoryTotalBytes: number;
  memoryFreeBytes: number;
  memoryUsagePercent: number;
  diskFreeBytes: number;
  diskTotalBytes: number;
  diskUsagePercent: number;
  gpuName: string;
  gpuMemoryBytes: number;
  activeJobsCount: number;
  completedJobsCount: number;
  timestamp: number;
}

export class SystemMetricsService {
  private static instance: SystemMetricsService;
  private timer: NodeJS.Timeout | null = null;
  private mainWindow: BrowserWindow | null = null;
  private lastCpuTimes: { idle: number; total: number } | null = null;
  private lastDiskInfo = { free: 50 * 1024 * 1024 * 1024, total: 512 * 1024 * 1024 * 1024 };
  private activeJobsCount = 0;
  private completedJobsCount = 0;
  private gpuName = 'Intel(R) Iris(R) Xe Graphics';
  private gpuMemoryBytes = 1024 * 1024 * 1024;
  private logger = LoggerService.getInstance();

  private constructor() {
    this.refreshDiskStats();
  }

  public static getInstance(): SystemMetricsService {
    if (!SystemMetricsService.instance) {
      SystemMetricsService.instance = new SystemMetricsService();
    }
    return SystemMetricsService.instance;
  }

  public setMainWindow(window: BrowserWindow | null) {
    this.mainWindow = window;
  }

  public setGpuDetails(name: string, ramBytes: number) {
    this.gpuName = name;
    this.gpuMemoryBytes = ramBytes;
  }

  public setJobCounts(active: number, completed: number) {
    this.activeJobsCount = active;
    this.completedJobsCount = completed;
  }

  public startSampling(intervalMs: number = 2000) {
    if (this.timer) {
      clearInterval(this.timer);
    }
    this.timer = setInterval(async () => {
      const metrics = await this.getCurrentMetrics();
      if (this.mainWindow && !this.mainWindow.isDestroyed()) {
        this.mainWindow.webContents.send('system-metrics-update', metrics);
      }
    }, intervalMs);
  }

  public stopSampling() {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }

  private getCpuTimes(): { idle: number; total: number } {
    const cpus = os.cpus();
    let idle = 0;
    let total = 0;
    for (const cpu of cpus) {
      idle += cpu.times.idle;
      total += cpu.times.user + cpu.times.nice + cpu.times.sys + cpu.times.irq + cpu.times.idle;
    }
    return { idle, total };
  }

  private calculateCpuUsage(): number {
    const current = this.getCpuTimes();
    if (!this.lastCpuTimes) {
      this.lastCpuTimes = current;
      return 12; // Initial reasonable estimate
    }

    const idleDelta = current.idle - this.lastCpuTimes.idle;
    const totalDelta = current.total - this.lastCpuTimes.total;
    this.lastCpuTimes = current;

    if (totalDelta <= 0) return 0;
    const usage = 100 - (idleDelta / totalDelta) * 100;
    return Math.max(0, Math.min(100, Math.round(usage * 10) / 10));
  }

  private async refreshDiskStats() {
    try {
      const { stdout } = await execAsync('powershell -Command "Get-PSDrive -PSProvider FileSystem | Select-Object -First 1 Free, Used | ConvertTo-Json"');
      const parsed = JSON.parse(stdout.trim());
      if (parsed) {
        const free = Number(parsed.Free) || 0;
        const used = Number(parsed.Used) || 0;
        if (free > 0 || used > 0) {
          this.lastDiskInfo = {
            free,
            total: free + used,
          };
        }
      }
    } catch {
      // Fallback
    }
  }

  public async getCurrentMetrics(): Promise<SystemMetrics> {
    const totalMem = os.totalmem();
    const freeMem = os.freemem();
    const usedMem = totalMem - freeMem;
    const memUsagePercent = Math.round((usedMem / totalMem) * 1000) / 10;
    const cpuUsagePercent = this.calculateCpuUsage();

    const diskTotal = this.lastDiskInfo.total;
    const diskFree = this.lastDiskInfo.free;
    const diskUsed = diskTotal - diskFree;
    const diskUsagePercent = diskTotal > 0 ? Math.round((diskUsed / diskTotal) * 1000) / 10 : 0;

    return {
      cpuUsagePercent,
      memoryUsedBytes: usedMem,
      memoryTotalBytes: totalMem,
      memoryFreeBytes: freeMem,
      memoryUsagePercent: memUsagePercent,
      diskFreeBytes: diskFree,
      diskTotalBytes: diskTotal,
      diskUsagePercent,
      gpuName: this.gpuName,
      gpuMemoryBytes: this.gpuMemoryBytes,
      activeJobsCount: this.activeJobsCount,
      completedJobsCount: this.completedJobsCount,
      timestamp: Date.now(),
    };
  }
}
