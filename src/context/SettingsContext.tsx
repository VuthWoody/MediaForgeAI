import React, { createContext, useContext, useEffect, useState } from 'react';
import { AppSettings, DEFAULT_SETTINGS } from '../types/settings';

interface SettingsContextType {
  settings: AppSettings;
  isLoading: boolean;
  saveSettings: (newSettings: Partial<AppSettings>) => Promise<boolean>;
  updateSettings: (newSettings: Partial<AppSettings>) => Promise<boolean>;
  resetSettings: () => Promise<void>;
  reloadSettings: () => Promise<void>;
}

const SettingsContext = createContext<SettingsContextType>({
  settings: DEFAULT_SETTINGS,
  isLoading: true,
  saveSettings: async () => false,
  updateSettings: async () => false,
  resetSettings: async () => {},
  reloadSettings: async () => {},
});

export const SettingsProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [settings, setSettings] = useState<AppSettings>(DEFAULT_SETTINGS);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const applyTheme = (theme: string) => {
    document.documentElement.setAttribute('data-theme', theme);
  };

  const reloadSettings = async () => {
    if (window.electronAPI?.getSettings) {
      try {
        const loaded = await window.electronAPI.getSettings();
        setSettings(loaded);
        applyTheme(loaded.general.theme);
      } catch (err) {
        console.error('Failed to load settings:', err);
      }
    } else {
      // Browser fallback (localStorage)
      try {
        const saved = localStorage.getItem('mediaforge_settings');
        if (saved) {
          const parsed = JSON.parse(saved);
          setSettings(parsed);
          applyTheme(parsed.general.theme);
        }
      } catch {
        // use defaults
      }
    }
  };

  const saveSettings = async (newSettings: Partial<AppSettings>): Promise<boolean> => {
    const merged: AppSettings = {
      general: { ...settings.general, ...(newSettings.general || {}) },
      downloader: { ...settings.downloader, ...(newSettings.downloader || {}) },
      ai: { ...settings.ai, ...(newSettings.ai || {}) },
      hardware: { ...settings.hardware, ...(newSettings.hardware || {}) },
    };

    setSettings(merged);
    applyTheme(merged.general.theme);

    if (window.electronAPI?.saveSettings) {
      try {
        return await window.electronAPI.saveSettings(merged);
      } catch (err) {
        console.error('Failed to save settings to Electron:', err);
        return false;
      }
    } else {
      localStorage.setItem('mediaforge_settings', JSON.stringify(merged));
      return true;
    }
  };

  const resetSettings = async () => {
    if (window.electronAPI?.resetSettings) {
      try {
        const defaults = await window.electronAPI.resetSettings();
        setSettings(defaults);
        applyTheme(defaults.general.theme);
      } catch (err) {
        console.error('Failed to reset settings:', err);
      }
    } else {
      setSettings(DEFAULT_SETTINGS);
      localStorage.removeItem('mediaforge_settings');
      applyTheme(DEFAULT_SETTINGS.general.theme);
    }
  };

  useEffect(() => {
    const init = async () => {
      setIsLoading(true);
      await reloadSettings();
      setIsLoading(false);
    };
    init();
  }, []);

  return (
    <SettingsContext.Provider
      value={{
        settings,
        isLoading,
        saveSettings,
        updateSettings: saveSettings,
        resetSettings,
        reloadSettings,
      }}
    >
      {children}
    </SettingsContext.Provider>
  );
};

export const useSettings = () => useContext(SettingsContext);
