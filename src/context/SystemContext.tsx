import React, { createContext, useContext, useEffect, useState } from 'react';
import { SystemMetrics, HardwareInfo } from '../types/system';

interface SystemContextType {
  metrics: SystemMetrics;
  hardware: HardwareInfo | null;
  isLoading: boolean;
  refreshMetrics: () => Promise<void>;
  refreshHardware: () => Promise<void>;
}

const DEFAULT_METRICS: SystemMetrics = {
  cpuUsagePercent: 14.2,
  memoryUsedBytes: 8.2 * 1024 * 1024 * 1024,
  memoryTotalBytes: 16 * 1024 * 1024 * 1024,
  memoryFreeBytes: 7.8 * 1024 * 1024 * 1024,
  memoryUsagePercent: 51.2,
  diskFreeBytes: 142 * 1024 * 1024 * 1024,
  diskTotalBytes: 512 * 1024 * 1024 * 1024,
  diskUsagePercent: 72.3,
  gpuName: 'Intel(R) Iris(R) Xe Graphics',
  gpuMemoryBytes: 1024 * 1024 * 1024,
  activeJobsCount: 0,
  completedJobsCount: 0,
  timestamp: Date.now(),
};

const SystemContext = createContext<SystemContextType>({
  metrics: DEFAULT_METRICS,
  hardware: null,
  isLoading: true,
  refreshMetrics: async () => {},
  refreshHardware: async () => {},
});

export const SystemProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [metrics, setMetrics] = useState<SystemMetrics>(DEFAULT_METRICS);
  const [hardware, setHardware] = useState<HardwareInfo | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const refreshMetrics = async () => {
    if (window.electronAPI?.getSystemMetrics) {
      try {
        const data = await window.electronAPI.getSystemMetrics();
        setMetrics(data);
      } catch (err) {
        console.error('Failed to get system metrics:', err);
      }
    }
  };

  const refreshHardware = async () => {
    if (window.electronAPI?.getHardwareInfo) {
      try {
        const data = await window.electronAPI.getHardwareInfo();
        setHardware(data);
      } catch (err) {
        console.error('Failed to get hardware info:', err);
      }
    }
  };

  useEffect(() => {
    let unsubscribe: (() => void) | undefined;

    const init = async () => {
      setIsLoading(true);
      await Promise.all([refreshMetrics(), refreshHardware()]);
      setIsLoading(false);

      if (window.electronAPI?.onMetricsUpdate) {
        unsubscribe = window.electronAPI.onMetricsUpdate((newMetrics) => {
          setMetrics(newMetrics);
        });
      }
    };

    init();

    return () => {
      if (unsubscribe) unsubscribe();
    };
  }, []);

  return (
    <SystemContext.Provider
      value={{
        metrics,
        hardware,
        isLoading,
        refreshMetrics,
        refreshHardware,
      }}
    >
      {children}
    </SystemContext.Provider>
  );
};

export const useSystem = () => useContext(SystemContext);
