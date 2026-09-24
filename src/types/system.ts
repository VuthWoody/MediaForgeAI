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
