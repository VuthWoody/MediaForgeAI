import React, { createContext, useContext, useEffect, useState } from 'react';
import { MediaLibraryItem, MediaFilterOptions } from '../types/mediaLibrary';
import { ProjectData } from '../types/project';
import { useProject } from './ProjectContext';

interface MediaLibraryContextType {
  items: MediaLibraryItem[];
  selectedItem: MediaLibraryItem | null;
  filters: MediaFilterOptions;
  isLoading: boolean;
  setFilters: React.Dispatch<React.SetStateAction<MediaFilterOptions>>;
  selectItem: (item: MediaLibraryItem | null) => void;
  loadMedia: () => Promise<void>;
  importFile: () => Promise<MediaLibraryItem | null>;
  deleteMedia: (id: string, deleteFromDisk: boolean) => Promise<boolean>;
  createStudioProject: (mediaId: string) => Promise<ProjectData | null>;
}

const DEFAULT_FILTERS: MediaFilterOptions = {
  platform: 'all',
  creator: '',
  searchQuery: '',
  sortBy: 'date-desc',
};

const MediaLibraryContext = createContext<MediaLibraryContextType>({
  items: [],
  selectedItem: null,
  filters: DEFAULT_FILTERS,
  isLoading: true,
  setFilters: () => {},
  selectItem: () => {},
  loadMedia: async () => {},
  importFile: async () => null,
  deleteMedia: async () => false,
  createStudioProject: async () => null,
});

export const MediaLibraryProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [items, setItems] = useState<MediaLibraryItem[]>([]);
  const [selectedItem, setSelectedItem] = useState<MediaLibraryItem | null>(null);
  const [filters, setFilters] = useState<MediaFilterOptions>(DEFAULT_FILTERS);
  const [isLoading, setIsLoading] = useState(true);
  const { loadProjects } = useProject();

  const loadMedia = async () => {
    setIsLoading(true);
    if (window.electronAPI?.mediaLibraryList) {
      try {
        const list = await window.electronAPI.mediaLibraryList(filters);
        setItems(list);
      } catch (err) {
        console.error('Failed to load media library:', err);
      }
    } else {
      // Mock fallback
      setItems([
        {
          id: 'media-sample-cyberpunk',
          title: 'Cyberpunk 2077: Night City Secrets',
          filename: 'cyberpunk_secrets_4k.mp4',
          filePath: 'C:\\Videos\\cyberpunk_secrets_4k.mp4',
          platform: 'youtube',
          creator: 'CD PROJEKT RED Official',
          durationSeconds: 142.5,
          resolution: { width: 3840, height: 2160 },
          fps: 60,
          fileSizeBytes: 148592000,
          codec: 'hevc',
          audioSampleRate: 48000,
          audioChannels: 2,
          importedAt: new Date(Date.now() - 86400000 * 2).toISOString(),
          tags: ['Cyberpunk', 'Gaming', '4K HDR', 'Sample'],
          linkedProjectId: 'sample-cyberpunk-doc',
        },
      ]);
    }
    setIsLoading(false);
  };

  const importFile = async (): Promise<MediaLibraryItem | null> => {
    if (window.electronAPI?.selectMediaFile && window.electronAPI?.mediaLibraryImportFile) {
      try {
        const res = await window.electronAPI.selectMediaFile();
        if (!res.canceled && res.filePath) {
          const item = await window.electronAPI.mediaLibraryImportFile(res.filePath);
          await loadMedia();
          return item;
        }
      } catch (err) {
        console.error('Failed to import media file:', err);
      }
    }
    return null;
  };

  const deleteMedia = async (id: string, deleteFromDisk: boolean): Promise<boolean> => {
    if (window.electronAPI?.mediaLibraryDelete) {
      try {
        const ok = await window.electronAPI.mediaLibraryDelete(id, deleteFromDisk);
        if (ok) {
          if (selectedItem?.id === id) setSelectedItem(null);
          await loadMedia();
        }
        return ok;
      } catch (err) {
        console.error('Failed to delete media:', err);
        return false;
      }
    }
    setItems((prev) => prev.filter((i) => i.id !== id));
    return true;
  };

  const createStudioProject = async (mediaId: string): Promise<ProjectData | null> => {
    if (window.electronAPI?.mediaLibraryCreateProject) {
      try {
        const proj = await window.electronAPI.mediaLibraryCreateProject(mediaId);
        await loadProjects();
        await loadMedia();
        return proj;
      } catch (err) {
        console.error('Failed to bridge project from media:', err);
        return null;
      }
    }
    return null;
  };

  useEffect(() => {
    loadMedia();
  }, [filters]);

  return (
    <MediaLibraryContext.Provider
      value={{
        items,
        selectedItem,
        filters,
        isLoading,
        setFilters,
        selectItem: setSelectedItem,
        loadMedia,
        importFile,
        deleteMedia,
        createStudioProject,
      }}
    >
      {children}
    </MediaLibraryContext.Provider>
  );
};

export const useMediaLibrary = () => useContext(MediaLibraryContext);
