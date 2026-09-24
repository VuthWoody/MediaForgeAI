import fs from 'fs';
import path from 'path';
import { exec } from 'child_process';
import util from 'util';
import { getAppDataDir, getDefaultDownloadsDir } from '../utils/paths';
import { LoggerService } from './LoggerService';
import { ProjectService } from './ProjectService';
import { MediaLibraryItem, MediaFilterOptions } from '../../src/types/mediaLibrary';
import { PlatformType } from '../../src/types/downloader';
import { ProjectData } from '../../src/types/project';

const execAsync = util.promisify(exec);

export class MediaLibraryService {
  private static instance: MediaLibraryService;
  private catalogPath: string;
  private items: MediaLibraryItem[] = [];
  private logger = LoggerService.getInstance();

  private constructor() {
    const appDir = getAppDataDir();
    this.catalogPath = path.join(appDir, 'media_library.json');
    this.loadCatalog();
  }

  public static getInstance(): MediaLibraryService {
    if (!MediaLibraryService.instance) {
      MediaLibraryService.instance = new MediaLibraryService();
    }
    return MediaLibraryService.instance;
  }

  private loadCatalog() {
    try {
      if (fs.existsSync(this.catalogPath)) {
        const raw = fs.readFileSync(this.catalogPath, 'utf8');
        this.items = JSON.parse(raw);
        // Auto-heal any path encoding mismatches
        let modified = false;
        for (const item of this.items) {
          if (!fs.existsSync(item.filePath) && item.filePath.includes('dY~,')) {
            const healed = item.filePath.replace(/dY~,/g, '😂');
            if (fs.existsSync(healed)) {
              item.filePath = healed;
              item.title = item.title.replace(/dY~,/g, '😂');
              modified = true;
            }
          }
        }
        if (modified) {
          this.saveCatalog();
        }
        this.logger.info('main', `Loaded ${this.items.length} media library items from catalog.`);
      } else {
        this.ensureSampleMedia();
      }
    } catch (err) {
      this.logger.error('main', 'Failed to read media library catalog', err);
      this.items = [];
    }
  }

  private saveCatalog() {
    try {
      fs.writeFileSync(this.catalogPath, JSON.stringify(this.items, null, 2), 'utf8');
    } catch (err) {
      this.logger.error('main', 'Failed to save media library catalog', err);
    }
  }

  private ensureSampleMedia() {
    const sampleId = 'media-sample-cyberpunk';
    const sampleItem: MediaLibraryItem = {
      id: sampleId,
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
    };

    this.items = [sampleItem];
    this.saveCatalog();
  }

  public async listMedia(filters?: MediaFilterOptions): Promise<MediaLibraryItem[]> {
    let result = [...this.items];

    if (filters?.platform && filters.platform !== 'all') {
      result = result.filter((item) => item.platform.toLowerCase() === filters.platform?.toLowerCase());
    }

    if (filters?.creator) {
      result = result.filter((item) =>
        item.creator.toLowerCase().includes(filters.creator!.toLowerCase())
      );
    }

    if (filters?.searchQuery) {
      const q = filters.searchQuery.toLowerCase();
      result = result.filter(
        (item) =>
          item.title.toLowerCase().includes(q) ||
          item.creator.toLowerCase().includes(q) ||
          item.tags.some((t) => t.toLowerCase().includes(q))
      );
    }

    // Sort
    const sortBy = filters?.sortBy || 'date-desc';
    result.sort((a, b) => {
      switch (sortBy) {
        case 'date-asc':
          return new Date(a.importedAt).getTime() - new Date(b.importedAt).getTime();
        case 'duration-desc':
          return b.durationSeconds - a.durationSeconds;
        case 'size-desc':
          return b.fileSizeBytes - a.fileSizeBytes;
        case 'title':
          return a.title.localeCompare(b.title);
        case 'date-desc':
        default:
          return new Date(b.importedAt).getTime() - new Date(a.importedAt).getTime();
      }
    });

    return result;
  }

  public async probeMediaFile(filePath: string): Promise<{
    duration: number;
    width: number;
    height: number;
    fps: number;
    size: number;
    codec: string;
    sampleRate: number;
    channels: number;
  }> {
    let duration = 0;
    let width = 1920;
    let height = 1080;
    let fps = 30;
    let size = 0;
    let codec = 'h264';
    let sampleRate = 48000;
    let channels = 2;

    try {
      if (fs.existsSync(filePath)) {
        const stats = fs.statSync(filePath);
        size = stats.size;
      }
    } catch {
      // ignore
    }

    try {
      // Use ffprobe if available or ffmpeg -i
      const { stderr } = await execAsync(`ffmpeg -i "${filePath}" 2>&1`);
      
      // Parse duration: Duration: 00:02:22.50
      const durMatch = stderr.match(/Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)/);
      if (durMatch) {
        duration =
          parseInt(durMatch[1], 10) * 3600 +
          parseInt(durMatch[2], 10) * 60 +
          parseFloat(durMatch[3]);
      }

      // Parse video stream: Stream #0:0... Video: h264... 1920x1080... 30 fps
      const resMatch = stderr.match(/Video:.*?,\s*(\d{3,4})x(\d{3,4})/);
      if (resMatch) {
        width = parseInt(resMatch[1], 10);
        height = parseInt(resMatch[2], 10);
      }

      const fpsMatch = stderr.match(/(\d+(?:\.\d+)?)\s*fps/);
      if (fpsMatch) {
        fps = Math.round(parseFloat(fpsMatch[1]));
      }

      const codecMatch = stderr.match(/Video:\s*([a-zA-Z0-9_-]+)/);
      if (codecMatch) {
        codec = codecMatch[1].toLowerCase();
      }

      const audioMatch = stderr.match(/Audio:\s*.*?, (\d+) Hz,\s*(stereo|mono|5\.1)/i);
      if (audioMatch) {
        sampleRate = parseInt(audioMatch[1], 10);
        channels = audioMatch[2].toLowerCase() === 'stereo' ? 2 : audioMatch[2] === 'mono' ? 1 : 6;
      }
    } catch {
      // ffmpeg always returns code 1 when given just -i without output, stderr contains stream information
    }

    return { duration, width, height, fps, size, codec, sampleRate, channels };
  }

  public async extractThumbnail(filePath: string, outputThumbPath: string): Promise<boolean> {
    try {
      const thumbDir = path.dirname(outputThumbPath);
      if (!fs.existsSync(thumbDir)) {
        fs.mkdirSync(thumbDir, { recursive: true });
      }
      await execAsync(`ffmpeg -y -ss 00:00:02 -i "${filePath}" -vframes 1 -q:v 2 "${outputThumbPath}"`);
      return fs.existsSync(outputThumbPath);
    } catch {
      return false;
    }
  }

  public async addMedia(item: Omit<MediaLibraryItem, 'id' | 'importedAt'>): Promise<MediaLibraryItem> {
    const id = 'media-' + Math.random().toString(36).substring(2, 9) + '-' + Date.now().toString(36);
    const newItem: MediaLibraryItem = {
      ...item,
      id,
      importedAt: new Date().toISOString(),
    };

    this.items.unshift(newItem);
    this.saveCatalog();
    this.logger.info('main', `Added media item to library: "${newItem.title}" (${newItem.id})`);
    return newItem;
  }

  public async importLocalFile(filePath: string): Promise<MediaLibraryItem> {
    if (!fs.existsSync(filePath)) {
      throw new Error(`File not found: ${filePath}`);
    }

    const filename = path.basename(filePath);
    const title = filename.replace(/\.[^/.]+$/, '');
    const meta = await this.probeMediaFile(filePath);

    // Generate thumbnail
    const thumbDir = path.join(getAppDataDir(), 'Thumbnails');
    const thumbPath = path.join(thumbDir, `thumb_${Date.now()}_${path.parse(filename).name}.jpg`);
    await this.extractThumbnail(filePath, thumbPath);

    return await this.addMedia({
      title,
      filename,
      filePath,
      platform: 'custom',
      creator: 'Local User',
      durationSeconds: meta.duration,
      resolution: { width: meta.width, height: meta.height },
      fps: meta.fps,
      fileSizeBytes: meta.size,
      codec: meta.codec,
      audioSampleRate: meta.sampleRate,
      audioChannels: meta.channels,
      thumbnailPath: fs.existsSync(thumbPath) ? thumbPath : undefined,
      tags: ['Local Import'],
    });
  }

  public async deleteMedia(id: string, deleteFromDisk: boolean = false): Promise<boolean> {
    const item = this.items.find((i) => i.id === id);
    if (!item) return false;

    if (deleteFromDisk && fs.existsSync(item.filePath)) {
      try {
        fs.unlinkSync(item.filePath);
        this.logger.info('main', `Deleted media file from disk: ${item.filePath}`);
      } catch (err) {
        this.logger.warn('main', `Failed to delete file from disk: ${item.filePath}`, err);
      }
    }

    this.items = this.items.filter((i) => i.id !== id);
    this.saveCatalog();
    return true;
  }

  public async createStudioProjectFromMedia(mediaId: string): Promise<ProjectData> {
    const item = this.items.find((i) => i.id === mediaId);
    if (!item) {
      throw new Error(`Media item ${mediaId} not found`);
    }

    const projectService = ProjectService.getInstance();
    const createdProject = await projectService.createProject({
      name: `${item.title} (Studio)`,
      description: `Translation and voice dubbing session for ${item.title} (${item.creator}).`,
      sourceLanguage: 'en',
      targetLanguage: 'km',
      sourceMedia: {
        type: 'file',
        pathOrUrl: item.filePath,
        filename: item.filename,
        durationSeconds: item.durationSeconds,
        resolution: item.resolution,
        fps: item.fps,
        fileSizeBytes: item.fileSizeBytes,
        codec: item.codec,
        audioSampleRate: item.audioSampleRate,
        audioChannels: item.audioChannels,
        thumbnailPath: item.thumbnailPath,
        platform: item.platform,
      },
      tags: [...item.tags, item.platform],
    });

    item.linkedProjectId = createdProject.id;
    this.saveCatalog();
    this.logger.info('main', `Bridge created project ${createdProject.id} from media item ${mediaId}`);

    return createdProject;
  }
}
