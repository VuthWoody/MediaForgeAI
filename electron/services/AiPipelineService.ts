import { BrowserWindow } from 'electron';
import path from 'path';
import fs from 'fs';
import { spawn } from 'child_process';
import { LoggerService } from './LoggerService';
import { ProjectService } from './ProjectService';
import { FFmpegService } from './FFmpegService';
import { ConfigService } from './ConfigService';
import { SpeechSegment, ProjectData, ClonedVoiceProfile } from '../../src/types/project';
import { VoxCpmActor, PipelineOptions } from '../../src/types/studio';
import { getAppDataDir } from '../utils/paths';

export interface AiPipelineProgress {
  type: 'progress';
  stage: 'transcribing' | 'translating' | 'dubbing' | 'completed' | 'error';
  percent: number;
  message: string;
  timestamp: number;
}

export interface VoiceOption {
  shortName: string;
  locale: string;
  gender: string;
  friendlyName: string;
}

export class AiPipelineService {
  private static instance: AiPipelineService;
  private logger = LoggerService.getInstance();
  private projectService = ProjectService.getInstance();
  private configService = ConfigService.getInstance();
  private mainWindow: BrowserWindow | null = null;
  private pythonPath: string | null = null;
  private scriptPath: string | null = null;

  private constructor() {
    this.resolvePythonEnvironment();
  }

  public static getInstance(): AiPipelineService {
    if (!AiPipelineService.instance) {
      AiPipelineService.instance = new AiPipelineService();
    }
    return AiPipelineService.instance;
  }

  public setMainWindow(win: BrowserWindow | null) {
    this.mainWindow = win;
  }

  private resolvePythonEnvironment() {
    // 1. Resolve Python executable
    const candidates = [
      'python',
      'python3',
      path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', 'Python312', 'python.exe'),
      path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', 'Python311', 'python.exe'),
      path.join(process.env.ProgramFiles || '', 'Python312', 'python.exe'),
    ];

    for (const cand of candidates) {
      if (cand.includes('\\')) {
        if (fs.existsSync(cand)) {
          this.pythonPath = cand;
          break;
        }
      } else {
        // Simple executable name in PATH
        this.pythonPath = cand;
        break;
      }
    }

    // 2. Resolve python/ai_pipeline.py
    const possibleScriptPaths = [
      path.join(process.cwd(), 'python', 'ai_pipeline.py'),
      path.join(__dirname, '..', '..', 'python', 'ai_pipeline.py'),
      path.join(__dirname, '..', 'python', 'ai_pipeline.py'),
    ];

    for (const sp of possibleScriptPaths) {
      if (fs.existsSync(sp)) {
        this.scriptPath = sp;
        break;
      }
    }

    if (!this.scriptPath) {
      this.scriptPath = path.join(process.cwd(), 'python', 'ai_pipeline.py');
    }

    this.logger.info('ai', `Python runtime resolved: "${this.pythonPath}", script: "${this.scriptPath}"`);
  }

  private emitProgress(progress: AiPipelineProgress) {
    if (this.mainWindow && !this.mainWindow.isDestroyed()) {
      this.mainWindow.webContents.send('ai-progress', progress);
    }
  }

  private executePythonScript<T>(args: string[]): Promise<T> {
    return new Promise((resolve, reject) => {
      const pythonExe = this.pythonPath || 'python';
      const script = this.scriptPath || path.join(process.cwd(), 'python', 'ai_pipeline.py');

      if (!fs.existsSync(script)) {
        return reject(new Error(`AI Pipeline script not found at: ${script}`));
      }

      this.logger.info('ai', `Spawning: ${pythonExe} ${script} ${args.join(' ')}`);

      const child = spawn(pythonExe, [script, ...args], {
        env: {
          ...process.env,
          PYTHONIOENCODING: 'utf-8',
        },
      });

      let resultData: T | null = null;
      let stderrText = '';
      let stdoutBuffer = '';

      child.stdout.on('data', (chunk: Buffer) => {
        stdoutBuffer += chunk.toString('utf8');
        const lines = stdoutBuffer.split('\n');
        // Keep the last partial line in buffer
        stdoutBuffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith('__PROGRESS__')) {
            try {
              const progressObj = JSON.parse(trimmed.replace(/^__PROGRESS__/, ''));
              this.emitProgress(progressObj);
            } catch (err) {
              // Ignore progress parse errors
            }
          } else if (trimmed.startsWith('__RESULT__')) {
            try {
              resultData = JSON.parse(trimmed.replace(/^__RESULT__/, ''));
            } catch (err: any) {
              this.logger.error('ai', 'Failed to parse __RESULT__ JSON', err);
            }
          }
        }
      });

      child.stderr.on('data', (chunk: Buffer) => {
        const text = chunk.toString('utf8');
        stderrText += text;
        this.logger.debug('ai', `[py stderr] ${text.trim()}`);
      });

      child.on('close', (code) => {
        // Process any remainder in stdoutBuffer
        if (stdoutBuffer.trim().startsWith('__RESULT__')) {
          try {
            resultData = JSON.parse(stdoutBuffer.trim().replace(/^__RESULT__/, ''));
          } catch {}
        }

        if (code === 0 && resultData) {
          resolve(resultData);
        } else if (resultData && (resultData as any).success === false) {
          reject(new Error((resultData as any).error || 'AI pipeline task failed'));
        } else {
          const errMessage = stderrText.trim() || `Python process exited with code ${code}`;
          this.logger.error('ai', `Execution error: ${errMessage}`);
          reject(new Error(errMessage));
        }
      });

      child.on('error', (err) => {
        this.logger.error('ai', 'Failed to spawn Python process', err);
        reject(err);
      });
    });
  }

  /**
   * Retrieves available neural TTS voices for a target language
   */
  public async getVoices(langFilter?: string): Promise<VoiceOption[]> {
    const args = ['list-voices'];
    if (langFilter) {
      args.push('--target', langFilter);
    }
    const res = await this.executePythonScript<{ success: boolean; voices: VoiceOption[] }>(args);
    return res.voices || [];
  }

  /**
   * Retrieves available VoxCPM voice actors & styles
   */
  public async getVoxCpmActors(): Promise<VoxCpmActor[]> {
    const args = ['list-actors'];
    const res = await this.executePythonScript<{ success: boolean; actors: VoxCpmActor[] }>(args);
    return res.actors || [];
  }

  /**
   * Transcribes speech audio using faster-whisper
   */
  public async transcribeAudio(
    audioPath: string,
    modelSize = 'tiny',
    sourceLang?: string
  ): Promise<{
    success: boolean;
    detectedLanguage: string;
    languageProbability: number;
    durationSeconds: number;
    segments: SpeechSegment[];
  }> {
    let effectiveAudioPath = audioPath;
    const ext = path.extname(audioPath).toLowerCase();
    if (ext !== '.wav' && fs.existsSync(audioPath)) {
      const wavCandidate = audioPath.replace(new RegExp(`\\${ext}$`, 'i'), '_speech_16k.wav');
      if (fs.existsSync(wavCandidate)) {
        effectiveAudioPath = wavCandidate;
      } else {
        const extRes = await FFmpegService.getInstance().extractAudio(audioPath, wavCandidate);
        if (extRes.success && extRes.wavPath) {
          effectiveAudioPath = extRes.wavPath;
        }
      }
    }

    const args = ['transcribe', '--input', effectiveAudioPath, '--model', modelSize];
    if (sourceLang && sourceLang !== 'auto') {
      args.push('--source', sourceLang);
    }
    return this.executePythonScript(args);
  }

  /**
   * Translates speech segments into target language with natural phrasing, genre awareness, and multi-engine LLMs
   */
  public async translateSegments(
    segments: SpeechSegment[],
    targetLang = 'km',
    sourceLang = 'auto',
    style: any = 'natural',
    options?: {
      genre?: string;
      engine?: string;
      endpoint?: string;
      prompt?: string;
      apiKey?: string;
    }
  ): Promise<{
    success: boolean;
    sourceLanguage: string;
    targetLanguage: string;
    style?: string;
    detectedGenre?: string;
    translationEngine?: string;
    segments: SpeechSegment[];
  }> {
    let effectiveStyle = 'natural';
    let effectiveOptions = options;
    if (typeof style === 'object' && style !== null && !options) {
      effectiveOptions = style;
      effectiveStyle = style.style || 'natural';
    } else if (typeof style === 'string' && style.trim()) {
      effectiveStyle = style.trim();
    }

    const settings = this.configService.getSettings();
    const effectiveEngine = effectiveOptions?.engine || settings.ai.translationEngine || 'gemini';
    const effectiveGenre = effectiveOptions?.genre || settings.ai.defaultContentGenre || 'auto';

    let effectiveApiKey = effectiveOptions?.apiKey;
    if (!effectiveApiKey) {
      if (effectiveEngine === 'gemini') {
        effectiveApiKey = settings.ai.geminiApiKey || settings.ai.translationApiKey;
      } else if (effectiveEngine === 'openai') {
        effectiveApiKey = settings.ai.openaiApiKey || settings.ai.translationApiKey;
      } else if (effectiveEngine === 'deepseek') {
        effectiveApiKey = settings.ai.deepseekApiKey || settings.ai.translationApiKey;
      } else {
        effectiveApiKey = settings.ai.translationApiKey;
      }
    }

    const effectiveEndpoint = options?.endpoint || settings.ai.customLlmEndpoint;

    // Write segments to a temporary JSON file to avoid CLI argument length limits
    const tempJsonPath = path.join(
      process.env.TEMP || process.env.TMP || '.',
      `mf_trans_${Date.now()}_${Math.random().toString(36).substring(7)}.json`
    );
    fs.writeFileSync(tempJsonPath, JSON.stringify(segments, null, 2), 'utf8');

    try {
      const args = [
        'translate',
        '--input', tempJsonPath,
        '--source', sourceLang,
        '--target', targetLang,
        '--style', effectiveStyle,
        '--genre', effectiveGenre,
        '--trans-engine', effectiveEngine,
      ];
      if (effectiveOptions?.prompt) {
        args.push('--prompt', effectiveOptions.prompt);
      }
      if (effectiveApiKey) {
        args.push('--api-key', effectiveApiKey);
      }
      if (effectiveEndpoint && effectiveEngine === 'local-llm') {
        args.push('--trans-endpoint', effectiveEndpoint);
      }
      return await this.executePythonScript(args);
    } finally {
      if (fs.existsSync(tempJsonPath)) {
        try { fs.unlinkSync(tempJsonPath); } catch {}
      }
    }
  }

  /**
   * Tests API key connectivity for chosen translation engine
   */
  public async testTranslationKey(
    engine: string,
    apiKey?: string,
    endpoint?: string
  ): Promise<{
    success: boolean;
    engine: string;
    latencyMs?: number;
    sample?: string;
    error?: string;
  }> {
    const settings = this.configService.getSettings();
    let effectiveKey = apiKey;
    if (!effectiveKey) {
      if (engine === 'gemini') effectiveKey = settings.ai.geminiApiKey || settings.ai.translationApiKey;
      else if (engine === 'openai') effectiveKey = settings.ai.openaiApiKey || settings.ai.translationApiKey;
      else if (engine === 'deepseek') effectiveKey = settings.ai.deepseekApiKey || settings.ai.translationApiKey;
      else effectiveKey = settings.ai.translationApiKey;
    }
    const effectiveEndpoint = endpoint || settings.ai.customLlmEndpoint;

    const args = ['test-key', '--trans-engine', engine];
    if (effectiveKey) args.push('--api-key', effectiveKey);
    if (effectiveEndpoint) args.push('--trans-endpoint', effectiveEndpoint);

    return await this.executePythonScript(args);
  }

  /**
   * Automatically detects the video narrative genre & tone from speech segments
   */
  public async detectGenre(
    segments: SpeechSegment[]
  ): Promise<{ success: boolean; detectedGenre: string }> {
    const tempJsonPath = path.join(
      process.env.TEMP || process.env.TMP || '.',
      `mf_genre_${Date.now()}_${Math.random().toString(36).substring(7)}.json`
    );
    fs.writeFileSync(tempJsonPath, JSON.stringify(segments, null, 2), 'utf8');

    try {
      return await this.executePythonScript(['detect-genre', '--input', tempJsonPath]);
    } finally {
      if (fs.existsSync(tempJsonPath)) {
        try { fs.unlinkSync(tempJsonPath); } catch {}
      }
    }
  }

  /**
   * Synthesizes speech dubbing per segment and combines into timeline track
   */
  public async dubSegments(
    segments: SpeechSegment[],
    outputDir: string,
    voiceName?: string,
    projectDuration = 0,
    options?: {
      engine?: 'edge-tts' | 'voxcpm';
      referenceAudioPath?: string;
      voiceStylePrompt?: string;
      voxcpmActor?: string;
      targetLang?: string;
    }
  ): Promise<{
    success: boolean;
    masterDubbedAudioPath: string;
    voice: string;
    durationSeconds: number;
    segments: SpeechSegment[];
  }> {
    const tempJsonPath = path.join(
      process.env.TEMP || process.env.TMP || '.',
      `mf_dub_${Date.now()}_${Math.random().toString(36).substring(7)}.json`
    );
    fs.writeFileSync(tempJsonPath, JSON.stringify(segments, null, 2), 'utf8');

    try {
      const args = [
        'dub',
        '--input', tempJsonPath,
        '--output-dir', outputDir,
        '--duration', projectDuration.toString(),
      ];
      if (voiceName) {
        args.push('--voice', voiceName);
      }
      if (options?.targetLang) {
        args.push('--target', options.targetLang);
      }
      if (options?.engine) {
        args.push('--engine', options.engine);
      }
      if (options?.referenceAudioPath) {
        args.push('--reference-audio', options.referenceAudioPath);
      }
      if (options?.voiceStylePrompt) {
        args.push('--voice-style', options.voiceStylePrompt);
      }
      if (options?.voxcpmActor) {
        args.push('--actor', options.voxcpmActor);
      }
      return await this.executePythonScript(args);
    } finally {
      if (fs.existsSync(tempJsonPath)) {
        try { fs.unlinkSync(tempJsonPath); } catch {}
      }
    }
  }

  /**
   * Full 1-Click Pipeline: Transcribe -> Translate -> Dub & persist to ProjectData
   */
  public async runFullPipeline(
    projectId: string,
    options: PipelineOptions = {}
  ): Promise<ProjectData> {
    const project = await this.projectService.getProject(projectId);
    if (!project) {
      throw new Error(`Project not found: ${projectId}`);
    }

    let audioPath = project.stems?.originalAudioPath;
    if (!audioPath || !fs.existsSync(audioPath)) {
      if (project.sourceMedia?.pathOrUrl && fs.existsSync(project.sourceMedia.pathOrUrl)) {
        this.emitProgress({
          type: 'progress',
          stage: 'transcribing',
          percent: 5,
          message: 'Extracting 16kHz speech WAV from source media...',
          timestamp: Date.now(),
        });
        const autoWav = path.join(project.projectDirectory, 'stems', 'speech_16k.wav');
        const ext = await FFmpegService.getInstance().extractAudio(project.sourceMedia.pathOrUrl, autoWav);
        if (ext.success && ext.wavPath && fs.existsSync(ext.wavPath)) {
          audioPath = ext.wavPath;
          project.stems = {
            ...project.stems,
            originalAudioPath: ext.wavPath,
          };
          await this.projectService.updateProject(project);
        }
      }
    }

    if (!audioPath || !fs.existsSync(audioPath)) {
      throw new Error('No valid audio file available for transcription.');
    }

    const outputDir = path.join(project.projectDirectory, 'stems');
    const modelSize = options.modelSize || 'tiny';
    const sourceLang = options.sourceLanguage || project.sourceLanguage || 'auto';
    const targetLang = options.targetLanguage || project.targetLanguage || 'km';
    const duration = project.sourceMedia?.durationSeconds || 0;
    const style = options.style || 'natural';
    const settings = this.configService.getSettings();
    const effectiveEngine = options.translationEngine || project.stems?.translationEngine || settings.ai.translationEngine || 'gemini';
    const effectiveGenre = options.contentGenre || settings.ai.defaultContentGenre || 'auto';

    let effectiveApiKey = options.apiKey;
    if (!effectiveApiKey) {
      if (effectiveEngine === 'gemini') {
        effectiveApiKey = settings.ai.geminiApiKey || settings.ai.translationApiKey;
      } else if (effectiveEngine === 'openai') {
        effectiveApiKey = settings.ai.openaiApiKey || settings.ai.translationApiKey;
      } else if (effectiveEngine === 'deepseek') {
        effectiveApiKey = settings.ai.deepseekApiKey || settings.ai.translationApiKey;
      } else {
        effectiveApiKey = settings.ai.translationApiKey;
      }
    }
    const effectiveEndpoint = options.endpoint || settings.ai.customLlmEndpoint;

    const args = [
      'pipeline',
      '--input', audioPath,
      '--source', sourceLang,
      '--target', targetLang,
      '--output-dir', outputDir,
      '--model', modelSize,
      '--duration', duration.toString(),
      '--style', style,
      '--genre', effectiveGenre,
      '--trans-engine', effectiveEngine,
    ];

    if (effectiveApiKey) {
      args.push('--api-key', effectiveApiKey);
    }
    if (effectiveEndpoint && effectiveEngine === 'local-llm') {
      args.push('--trans-endpoint', effectiveEndpoint);
    }
    if (options.prompt) {
      args.push('--prompt', options.prompt);
    }
    if (options.voiceName) {
      args.push('--voice', options.voiceName);
    }
    if (options.engine) {
      args.push('--engine', options.engine);
    }
    if (options.referenceAudioPath) {
      args.push('--reference-audio', options.referenceAudioPath);
    }
    if (options.voiceStylePrompt) {
      args.push('--voice-style', options.voiceStylePrompt);
    }
    if (options.voxcpmActor) {
      args.push('--actor', options.voxcpmActor);
    }

    const res = await this.executePythonScript<{
      success: boolean;
      sourceLanguage: string;
      targetLanguage: string;
      translationStyle?: string;
      voice: string;
      masterDubbedAudioPath: string;
      segments: SpeechSegment[];
      error?: string;
    }>(args);

    if (!res.success) {
      throw new Error(res.error || 'AI Pipeline execution failed.');
    }

    // Persist to project
    const nextRevision = (project.stems?.dubbedAudioRevision || 0) + 1;
    const updatedProject: ProjectData = {
      ...project,
      status: 'dubbed',
      sourceLanguage: res.sourceLanguage || project.sourceLanguage,
      targetLanguage: res.targetLanguage || project.targetLanguage,
      segments: res.segments || [],
      stems: {
        ...project.stems,
        dubbedVocalsPath: res.masterDubbedAudioPath,
        dubbedAudioRevision: nextRevision,
        dubbedVolume: project.stems?.dubbedVolume ?? 1.2,
        vocalVolume: project.stems?.vocalVolume ?? 1.0,
        voiceMode: project.stems?.voiceMode || 'clean-dub', // Default to clean dub to prevent duplicate audio!
        duckingLevel: project.stems?.duckingLevel ?? 0.12,
        dubbingEngine: options.engine || 'edge-tts',
        voxcpmActor: options.voxcpmActor,
        referenceAudioPath: options.referenceAudioPath,
        translationStyle: style as any,
        translationPrompt: options.prompt,
        translationEngine: effectiveEngine as any,
      },
      updatedAt: new Date().toISOString(),
    };

    await this.projectService.updateProject(updatedProject);
    this.logger.info('ai', `Full pipeline completed for project ${projectId}. Saved dubbed audio: ${res.masterDubbedAudioPath}`);

    this.emitProgress({
      type: 'progress',
      stage: 'completed',
      percent: 100,
      message: `AI Dubbing finished! Generated ${res.segments?.length || 0} translated speech segments.`,
      timestamp: Date.now(),
    });

    return updatedProject;
  }

  private getClonedVoicesFilePath(): string {
    const dir = path.join(getAppDataDir(), 'voices');
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    return path.join(dir, 'cloned_profiles.json');
  }

  public async getClonedVoices(): Promise<ClonedVoiceProfile[]> {
    try {
      const p = this.getClonedVoicesFilePath();
      if (!fs.existsSync(p)) return [];
      const content = fs.readFileSync(p, 'utf8');
      return JSON.parse(content) || [];
    } catch (err) {
      this.logger.error('ai', `Failed to load cloned voice profiles: ${err}`);
      return [];
    }
  }

  public async saveClonedVoice(profile: Omit<ClonedVoiceProfile, 'id' | 'createdAt'> & { id?: string }): Promise<ClonedVoiceProfile> {
    const list = await this.getClonedVoices();
    const newProfile: ClonedVoiceProfile = {
      id: profile.id || `voice_${Date.now()}_${Math.random().toString(36).substring(7)}`,
      name: profile.name,
      audioPath: profile.audioPath,
      createdAt: new Date().toISOString(),
      duration: profile.duration,
      pitchF0: profile.pitchF0,
      gender: profile.gender,
    };
    const existingIndex = list.findIndex(v => v.id === newProfile.id);
    if (existingIndex >= 0) {
      list[existingIndex] = newProfile;
    } else {
      list.push(newProfile);
    }
    const p = this.getClonedVoicesFilePath();
    fs.writeFileSync(p, JSON.stringify(list, null, 2), 'utf8');
    this.logger.info('ai', `Saved cloned voice profile: "${newProfile.name}" (${newProfile.id}) with audio "${newProfile.audioPath}"`);
    return newProfile;
  }

  public async deleteClonedVoice(id: string): Promise<boolean> {
    const list = await this.getClonedVoices();
    const filtered = list.filter(v => v.id !== id);
    const p = this.getClonedVoicesFilePath();
    fs.writeFileSync(p, JSON.stringify(filtered, null, 2), 'utf8');
    this.logger.info('ai', `Deleted cloned voice profile ${id}`);
    return true;
  }
}
