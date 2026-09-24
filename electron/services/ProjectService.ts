import fs from 'fs';
import path from 'path';
import { shell } from 'electron';
import { ConfigService } from './ConfigService';
import { LoggerService } from './LoggerService';
import { ProjectData, ProjectSummary } from '../../src/types/project';

export class ProjectService {
  private static instance: ProjectService;
  private logger = LoggerService.getInstance();
  private configService = ConfigService.getInstance();

  private constructor() {
    this.ensureSampleProject();
  }

  public static getInstance(): ProjectService {
    if (!ProjectService.instance) {
      ProjectService.instance = new ProjectService();
    }
    return ProjectService.instance;
  }

  private getProjectsDir(): string {
    const settings = this.configService.getSettings();
    const dir = settings.general.projectsDirectory;
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    return dir;
  }

  private getProjectDir(id: string): string {
    return path.join(this.getProjectsDir(), id);
  }

  private getProjectFilePath(id: string): string {
    return path.join(this.getProjectDir(id), 'project.json');
  }

  public async listProjects(): Promise<ProjectSummary[]> {
    const rootDir = this.getProjectsDir();
    const summaries: ProjectSummary[] = [];

    try {
      const entries = fs.readdirSync(rootDir, { withFileTypes: true });
      for (const entry of entries) {
        if (entry.isDirectory()) {
          const projectJsonPath = path.join(rootDir, entry.name, 'project.json');
          if (fs.existsSync(projectJsonPath)) {
            try {
              const raw = fs.readFileSync(projectJsonPath, 'utf8');
              const data: ProjectData = JSON.parse(raw);
              summaries.push({
                id: data.id,
                name: data.name,
                description: data.description,
                status: data.status,
                progressPercent: data.progressPercent || 0,
                createdAt: data.createdAt,
                updatedAt: data.updatedAt,
                lastOpenedAt: data.lastOpenedAt,
                sourceLanguage: data.sourceLanguage,
                targetLanguage: data.targetLanguage,
                durationSeconds: data.sourceMedia?.durationSeconds || 0,
                thumbnailUrl: data.sourceMedia?.thumbnailPath,
                projectDirectory: path.join(rootDir, entry.name),
              });
            } catch (readErr) {
              this.logger.warn('main', `Failed to parse project.json in ${entry.name}`, readErr);
            }
          }
        }
      }
    } catch (err) {
      this.logger.error('main', 'Failed to list projects directory', err);
    }

    // Sort by lastOpenedAt descending
    return summaries.sort((a, b) => new Date(b.lastOpenedAt || b.updatedAt).getTime() - new Date(a.lastOpenedAt || a.updatedAt).getTime());
  }

  public async getProject(id: string): Promise<ProjectData | null> {
    const filePath = this.getProjectFilePath(id);
    if (!fs.existsSync(filePath)) {
      return null;
    }
    try {
      const raw = fs.readFileSync(filePath, 'utf8');
      const project: ProjectData = JSON.parse(raw);

      // Auto-heal path if needed
      if (project.sourceMedia?.pathOrUrl && !fs.existsSync(project.sourceMedia.pathOrUrl)) {
        if (project.sourceMedia.pathOrUrl.includes('dY~,')) {
          const healed = project.sourceMedia.pathOrUrl.replace(/dY~,/g, '😂');
          if (fs.existsSync(healed)) {
            project.sourceMedia.pathOrUrl = healed;
            project.sourceMedia.filename = project.sourceMedia.filename.replace(/dY~,/g, '😂');
            if (project.sourceMedia.thumbnailPath) {
              project.sourceMedia.thumbnailPath = project.sourceMedia.thumbnailPath.replace(/dY~,/g, '😂');
            }
          }
        }
      }

      // Update lastOpenedAt
      project.lastOpenedAt = new Date().toISOString();
      fs.writeFileSync(filePath, JSON.stringify(project, null, 2), 'utf8');
      return project;
    } catch (err) {
      this.logger.error('main', `Failed to read project ${id}`, err);
      return null;
    }
  }

  public async createProject(partial: Partial<ProjectData>): Promise<ProjectData> {
    const id = partial.id || 'proj-' + Math.random().toString(36).substring(2, 9) + '-' + Date.now().toString(36);
    const now = new Date().toISOString();
    const projDir = this.getProjectDir(id);

    // Create subdirectories
    fs.mkdirSync(projDir, { recursive: true });
    fs.mkdirSync(path.join(projDir, 'audio'), { recursive: true });
    fs.mkdirSync(path.join(projDir, 'stems'), { recursive: true });
    fs.mkdirSync(path.join(projDir, 'transcripts'), { recursive: true });
    fs.mkdirSync(path.join(projDir, 'subtitles'), { recursive: true });
    fs.mkdirSync(path.join(projDir, 'rendered'), { recursive: true });
    fs.mkdirSync(path.join(projDir, 'thumbnails'), { recursive: true });

    const newProject: ProjectData = {
      id,
      name: partial.name || 'Untitled Video Project',
      description: partial.description || '',
      version: '1.0.0',
      createdAt: now,
      updatedAt: now,
      lastOpenedAt: now,
      status: 'draft',
      progressPercent: 0,
      projectDirectory: projDir,
      sourceLanguage: partial.sourceLanguage || 'en',
      targetLanguage: partial.targetLanguage || 'km',
      secondaryTargetLanguages: partial.secondaryTargetLanguages || ['ja', 'zh'],
      sourceMedia: partial.sourceMedia,
      speakers: partial.speakers || [
        {
          id: 'spk-1',
          name: 'Speaker 1 (Narrator)',
          color: '#00f0ff',
          gender: 'male',
          assignedVoiceId: 'km-KH-PisethNeural',
          voiceProvider: 'edge-tts',
          pitchMultiplier: 1.0,
          rateMultiplier: 1.0,
          volumeMultiplier: 1.0,
        },
      ],
      segments: partial.segments || [],
      stems: partial.stems || {
        isSeparated: false,
        vocalVolume: 1.0,
        musicVolume: 0.85,
        sfxVolume: 0.9,
        dubbedVolume: 1.0,
      },
      subtitleStyle: partial.subtitleStyle || {
        fontFamily: 'Inter',
        fontSize: 24,
        primaryColor: '#ffffff',
        outlineColor: '#000000',
        outlineWidth: 3,
        shadowColor: 'rgba(0,0,0,0.6)',
        shadowBlur: 4,
        position: 'bottom',
        marginVertical: 40,
        alignment: 'center',
        bold: true,
        italic: false,
      },
      exportSettings: partial.exportSettings || {
        format: 'mp4',
        resolutionPreset: 'original',
        videoCodec: 'auto',
        crf: 20,
        bitrateKbps: 8000,
        hardwareAcceleration: true,
        burnInSubtitles: false,
        includeDubbedAudio: true,
        outputPath: '',
      },
      tags: partial.tags || ['media', 'translation'],
      notes: partial.notes || '',
    };

    const filePath = this.getProjectFilePath(id);
    fs.writeFileSync(filePath, JSON.stringify(newProject, null, 2), 'utf8');
    this.logger.info('main', `Created new project "${newProject.name}" (${id})`);

    return newProject;
  }

  public async updateProject(project: ProjectData): Promise<ProjectData> {
    const id = project.id;
    const projDir = this.getProjectDir(id);
    if (!fs.existsSync(projDir)) {
      fs.mkdirSync(projDir, { recursive: true });
    }

    project.updatedAt = new Date().toISOString();
    project.projectDirectory = projDir;

    const filePath = this.getProjectFilePath(id);
    fs.writeFileSync(filePath, JSON.stringify(project, null, 2), 'utf8');
    this.logger.info('main', `Updated project "${project.name}" (${id})`);

    return project;
  }

  public async deleteProject(id: string): Promise<boolean> {
    const projDir = this.getProjectDir(id);
    if (fs.existsSync(projDir)) {
      try {
        fs.rmSync(projDir, { recursive: true, force: true });
        this.logger.info('main', `Deleted project directory: ${id}`);
        return true;
      } catch (err) {
        this.logger.error('main', `Failed to delete project ${id}`, err);
        return false;
      }
    }
    return false;
  }

  public async duplicateProject(id: string): Promise<ProjectData> {
    const original = await this.getProject(id);
    if (!original) {
      throw new Error(`Project ${id} not found.`);
    }

    const duplicated = await this.createProject({
      ...original,
      id: undefined,
      name: `${original.name} (Copy)`,
      status: 'draft',
      progressPercent: 0,
    });

    this.logger.info('main', `Duplicated project ${id} -> ${duplicated.id}`);
    return duplicated;
  }

  public async openProjectFolder(id: string): Promise<void> {
    const projDir = this.getProjectDir(id);
    if (fs.existsSync(projDir)) {
      await shell.openPath(projDir);
    }
  }

  private ensureSampleProject() {
    const rootDir = this.getProjectsDir();
    const sampleId = 'sample-cyberpunk-doc';
    const sampleDir = path.join(rootDir, sampleId);
    const sampleJsonPath = path.join(sampleDir, 'project.json');

    if (!fs.existsSync(sampleJsonPath)) {
      try {
        fs.mkdirSync(sampleDir, { recursive: true });
        fs.mkdirSync(path.join(sampleDir, 'audio'), { recursive: true });
        fs.mkdirSync(path.join(sampleDir, 'stems'), { recursive: true });
        fs.mkdirSync(path.join(sampleDir, 'transcripts'), { recursive: true });
        fs.mkdirSync(path.join(sampleDir, 'subtitles'), { recursive: true });
        fs.mkdirSync(path.join(sampleDir, 'rendered'), { recursive: true });
        fs.mkdirSync(path.join(sampleDir, 'thumbnails'), { recursive: true });

        const sampleData: ProjectData = {
          id: sampleId,
          name: 'Cyberpunk 2077: Night City Secrets',
          description: 'Deep dive documentary into future tech, mega-corporations, and synthetic intelligence in Night City.',
          version: '1.0.0',
          createdAt: new Date(Date.now() - 86400000 * 2).toISOString(),
          updatedAt: new Date(Date.now() - 3600000).toISOString(),
          lastOpenedAt: new Date().toISOString(),
          status: 'translated',
          progressPercent: 70,
          projectDirectory: sampleDir,
          sourceLanguage: 'en',
          targetLanguage: 'km',
          secondaryTargetLanguages: ['ja', 'zh'],
          sourceMedia: {
            type: 'file',
            pathOrUrl: 'C:\\Videos\\cyberpunk_secrets_4k.mp4',
            filename: 'cyberpunk_secrets_4k.mp4',
            durationSeconds: 142.5,
            resolution: { width: 3840, height: 2160 },
            fps: 60,
            fileSizeBytes: 148592000,
            codec: 'hevc',
            audioSampleRate: 48000,
            audioChannels: 2,
            platform: 'youtube',
          },
          speakers: [
            {
              id: 'spk-narrator',
              name: 'Johnny Silverhand (Narrator)',
              color: '#00f0ff',
              gender: 'male',
              assignedVoiceId: 'km-KH-PisethNeural',
              voiceProvider: 'edge-tts',
              pitchMultiplier: 0.95,
              rateMultiplier: 1.0,
              volumeMultiplier: 1.0,
            },
            {
              id: 'spk-alt',
              name: 'Alt Cunningham',
              color: '#8b5cf6',
              gender: 'female',
              assignedVoiceId: 'km-KH-SreymomNeural',
              voiceProvider: 'edge-tts',
              pitchMultiplier: 1.05,
              rateMultiplier: 0.95,
              volumeMultiplier: 0.9,
            },
          ],
          segments: [
            {
              id: 'seg-1',
              start: 0.0,
              end: 4.8,
              speakerId: 'spk-narrator',
              speakerName: 'Johnny Silverhand (Narrator)',
              originalText: 'Night City wasn\'t built on dreams. It was built on neon, chrome, and broken promises.',
              translatedText: 'ទីក្រុង Night City មិនត្រូវបានសាងសង់ឡើងលើក្តីស្រមៃនោះទេ។ វាត្រូវបានសាងសង់ឡើងលើពន្លឺនេអុង ដែកក្រូម និងការសន្យាមិនពិត។',
              confidence: 0.98,
            },
            {
              id: 'seg-2',
              start: 5.2,
              end: 9.6,
              speakerId: 'spk-narrator',
              speakerName: 'Johnny Silverhand (Narrator)',
              originalText: 'Every megacorp here owns a piece of your soul before you even wake up in the morning.',
              translatedText: 'ក្រុមហ៊ុនយក្សនីមួយៗនៅទីនេះគ្រប់គ្រងព្រលឹងរបស់អ្នក មុនពេលអ្នកភ្ញាក់ពីដំណេកនៅពេលព្រឹកទៅទៀត។',
              confidence: 0.96,
            },
            {
              id: 'seg-3',
              start: 10.1,
              end: 15.4,
              speakerId: 'spk-alt',
              speakerName: 'Alt Cunningham',
              originalText: 'The Blackwall is failing, Johnny. Beyond that barrier lies something far worse than Arasaka.',
              translatedText: 'ជញ្ជាំងខ្មៅ Blackwall កំពុងបរាជ័យហើយ Johnny។ ហួសពីរបាំងនោះ គឺមានអ្វីមួយដ៏អាក្រក់ជាង Arasaka ទៅទៀត។',
              confidence: 0.97,
            },
            {
              id: 'seg-4',
              start: 16.0,
              end: 21.3,
              speakerId: 'spk-narrator',
              speakerName: 'Johnny Silverhand (Narrator)',
              originalText: 'Then let\'s burn it all down together. One last time.',
              translatedText: 'អញ្ចឹងតោះយើងដុតកម្ទេចវាចោលទាំងអស់គ្នា។ សម្រាប់លើកចុងក្រោយ។',
              confidence: 0.99,
            },
          ],
          stems: {
            isSeparated: true,
            originalAudioPath: path.join(sampleDir, 'audio', 'original.wav'),
            vocalsPath: path.join(sampleDir, 'stems', 'vocals.wav'),
            musicPath: path.join(sampleDir, 'stems', 'music.wav'),
            sfxPath: path.join(sampleDir, 'stems', 'sfx.wav'),
            vocalVolume: 0.1,
            musicVolume: 0.85,
            sfxVolume: 0.9,
            dubbedVolume: 1.0,
          },
          subtitleStyle: {
            fontFamily: 'Outfit',
            fontSize: 26,
            primaryColor: '#00f0ff',
            outlineColor: '#0c0e14',
            outlineWidth: 4,
            shadowColor: 'rgba(0, 240, 255, 0.4)',
            shadowBlur: 12,
            position: 'bottom',
            marginVertical: 45,
            alignment: 'center',
            bold: true,
            italic: false,
          },
          exportSettings: {
            format: 'mp4',
            resolutionPreset: '4k',
            videoCodec: 'auto',
            crf: 18,
            bitrateKbps: 18000,
            hardwareAcceleration: true,
            burnInSubtitles: false,
            includeDubbedAudio: true,
            outputPath: path.join(sampleDir, 'rendered', 'NightCity_KhmerDub_4K.mp4'),
          },
          tags: ['Gaming', 'Cyberpunk', 'Khmer Dubbing', '4K HDR'],
          notes: 'Demo project highlighting multi-speaker diarization and English to Khmer video translation.',
        };

        fs.writeFileSync(sampleJsonPath, JSON.stringify(sampleData, null, 2), 'utf8');
        this.logger.info('main', 'Default sample project created at ' + sampleJsonPath);
      } catch (err) {
        this.logger.warn('main', 'Failed to generate default sample project', err);
      }
    }
  }
}
