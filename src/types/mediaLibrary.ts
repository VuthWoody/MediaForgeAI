import { PlatformType } from './downloader';

export interface MediaLibraryItem {
  id: string;
  title: string;
  filename: string;
  filePath: string;
  platform: PlatformType;
  creator: string;
  durationSeconds: number;
  resolution: {
    width: number;
    height: number;
  };
  fps: number;
  fileSizeBytes: number;
  codec: string;
  audioSampleRate: number;
  audioChannels: number;
  thumbnailPath?: string;
  importedAt: string;
  downloadJobId?: string;
  sourceUrl?: string;
  tags: string[];
  linkedProjectId?: string;
}

export interface MediaFilterOptions {
  platform?: string;
  creator?: string;
  searchQuery?: string;
  sortBy: 'date-desc' | 'date-asc' | 'duration-desc' | 'size-desc' | 'title';
}
