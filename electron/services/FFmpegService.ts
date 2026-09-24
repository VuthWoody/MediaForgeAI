import fs from 'fs';
import path from 'path';
import { spawn } from 'child_process';
import { LoggerService } from './LoggerService';
import { 
  WaveformData, 
  AudioExtractionResult, 
  FrameCaptureResult,
  StreamInfo,
  MediaProbeResult
} from '../../src/types/studio';

export { StreamInfo, MediaProbeResult };

export class FFmpegService {
  private static instance: FFmpegService;
  private logger = LoggerService.getInstance();

  private constructor() {}

  public static getInstance(): FFmpegService {
    if (!FFmpegService.instance) {
      FFmpegService.instance = new FFmpegService();
    }
    return FFmpegService.instance;
  }

  /**
   * Probes media metadata and stream information using ffprobe
   */
  public async probeMedia(filePath: string): Promise<MediaProbeResult> {
    return new Promise((resolve, reject) => {
      if (!fs.existsSync(filePath)) {
        return reject(new Error(`Media file not found: ${filePath}`));
      }

      const args = [
        '-v', 'quiet',
        '-print_format', 'json',
        '-show_format',
        '-show_streams',
        filePath
      ];

      const proc = spawn('ffprobe', args);
      const stdoutChunks: Buffer[] = [];
      const stderrChunks: Buffer[] = [];

      proc.stdout.on('data', (chunk) => stdoutChunks.push(chunk));
      proc.stderr.on('data', (chunk) => stderrChunks.push(chunk));

      proc.on('close', (code) => {
        if (code !== 0) {
          const errMsg = Buffer.concat(stderrChunks).toString();
          this.logger.error('ffmpeg', `ffprobe failed with exit code ${code}: ${errMsg}`);
          return reject(new Error(`ffprobe failed: ${errMsg}`));
        }

        try {
          const raw = Buffer.concat(stdoutChunks).toString('utf8');
          const parsed = JSON.parse(raw);
          const format = parsed.format || {};
          const streams = parsed.streams || [];

          const videoStreams: StreamInfo[] = [];
          const audioStreams: StreamInfo[] = [];
          const subtitleStreams: StreamInfo[] = [];

          for (const s of streams) {
            let fps: number | undefined = undefined;
            if (s.r_frame_rate) {
              const parts = s.r_frame_rate.split('/');
              if (parts.length === 2 && Number(parts[1]) > 0) {
                fps = Math.round((Number(parts[0]) / Number(parts[1])) * 100) / 100;
              } else if (!isNaN(Number(s.r_frame_rate))) {
                fps = Number(s.r_frame_rate);
              }
            }

            const info: StreamInfo = {
              index: s.index,
              codecType: s.codec_type,
              codecName: s.codec_name || 'unknown',
              codecLongName: s.codec_long_name,
              width: s.width,
              height: s.height,
              fps,
              sampleRate: s.sample_rate ? Number(s.sample_rate) : undefined,
              channels: s.channels ? Number(s.channels) : undefined,
              channelLayout: s.channel_layout,
              bitrate: s.bit_rate ? Number(s.bit_rate) : undefined,
              duration: s.duration ? Number(s.duration) : undefined,
            };

            if (s.codec_type === 'video') {
              videoStreams.push(info);
            } else if (s.codec_type === 'audio') {
              audioStreams.push(info);
            } else if (s.codec_type === 'subtitle') {
              subtitleStreams.push(info);
            }
          }

          const durationSeconds = Number(format.duration) || 0;
          const fileSizeBytes = Number(format.size) || (fs.existsSync(filePath) ? fs.statSync(filePath).size : 0);
          const overallBitrate = Number(format.bit_rate) || 0;

          resolve({
            formatName: format.format_name || 'unknown',
            formatLongName: format.format_long_name || '',
            durationSeconds,
            fileSizeBytes,
            overallBitrate,
            videoStreams,
            audioStreams,
            subtitleStreams,
          });
        } catch (err: any) {
          this.logger.error('ffmpeg', 'Failed to parse ffprobe json output', err);
          reject(err);
        }
      });

      proc.on('error', (err) => {
        this.logger.error('ffmpeg', 'Failed to spawn ffprobe', err);
        reject(err);
      });
    });
  }

  /**
   * Extracts audio optimized for Whisper STT (16kHz, mono, 16-bit PCM WAV)
   */
  public async extractAudio(inputPath: string, outputPath?: string): Promise<AudioExtractionResult> {
    try {
      if (!fs.existsSync(inputPath)) {
        return {
          success: false,
          wavPath: '',
          fileSizeBytes: 0,
          durationSeconds: 0,
          sampleRate: 16000,
          channels: 1,
          errorMessage: `Input file not found: ${inputPath}`,
        };
      }

      let dest = outputPath;
      if (!dest) {
        const ext = path.extname(inputPath);
        const dir = path.dirname(inputPath);
        const base = path.basename(inputPath, ext);
        dest = path.join(dir, `${base}_speech_16k.wav`);
      }

      const destDir = path.dirname(dest);
      if (!fs.existsSync(destDir)) {
        fs.mkdirSync(destDir, { recursive: true });
      }

      this.logger.info('ffmpeg', `Starting speech audio extraction: ${inputPath} -> ${dest}`);

      const args = [
        '-y',
        '-i', inputPath,
        '-vn',
        '-acodec', 'pcm_s16le',
        '-ar', '16000',
        '-ac', '1',
        dest,
      ];

      await new Promise<void>((resolve, reject) => {
        const proc = spawn('ffmpeg', args);
        const stderrChunks: Buffer[] = [];

        proc.stderr.on('data', (chunk) => stderrChunks.push(chunk));

        proc.on('close', (code) => {
          if (code === 0) {
            resolve();
          } else {
            const errDetails = Buffer.concat(stderrChunks).toString();
            reject(new Error(`FFmpeg audio extraction failed (exit ${code}): ${errDetails}`));
          }
        });

        proc.on('error', (err) => reject(err));
      });

      const stats = fs.statSync(dest);
      let durationSeconds = 0;

      try {
        const probe = await this.probeMedia(dest);
        durationSeconds = probe.durationSeconds;
      } catch {
        // Estimate from 16kHz 16-bit mono PCM: 1 sec = 32000 bytes (+ 44 bytes header)
        durationSeconds = Math.max(0, (stats.size - 44) / 32000);
      }

      this.logger.info('ffmpeg', `Speech audio extracted successfully: ${dest} (${(stats.size / 1024 / 1024).toFixed(2)} MB, ${durationSeconds.toFixed(1)}s)`);

      return {
        success: true,
        wavPath: dest,
        fileSizeBytes: stats.size,
        durationSeconds,
        sampleRate: 16000,
        channels: 1,
      };
    } catch (err: any) {
      this.logger.error('ffmpeg', 'Speech audio extraction failed', err);
      return {
        success: false,
        wavPath: '',
        fileSizeBytes: 0,
        durationSeconds: 0,
        sampleRate: 16000,
        channels: 1,
        errorMessage: err.message || String(err),
      };
    }
  }

  /**
   * Generates amplitude waveform peak data (0.0 to 1.0) for visual timeline display
   */
  public async generateWaveform(mediaPath: string, numBuckets = 500): Promise<WaveformData> {
    try {
      if (!fs.existsSync(mediaPath)) {
        return { peaks: new Array(numBuckets).fill(0), durationSeconds: 0 };
      }

      this.logger.info('ffmpeg', `Generating waveform for: ${mediaPath} (${numBuckets} buckets)`);

      // Stream 8kHz mono 16-bit PCM directly from ffmpeg pipe:1
      const args = [
        '-y',
        '-i', mediaPath,
        '-vn',
        '-acodec', 'pcm_s16le',
        '-ar', '8000',
        '-ac', '1',
        '-f', 's16le',
        'pipe:1',
      ];

      const stdoutChunks: Buffer[] = [];

      await new Promise<void>((resolve, reject) => {
        const proc = spawn('ffmpeg', args);

        proc.stdout.on('data', (chunk) => stdoutChunks.push(chunk));
        proc.on('close', (code) => {
          if (code === 0) resolve();
          else resolve(); // Still process whatever samples we got
        });
        proc.on('error', (err) => reject(err));
      });

      const buffer = Buffer.concat(stdoutChunks);
      const sampleCount = Math.floor(buffer.length / 2);

      if (sampleCount === 0) {
        return { peaks: new Array(numBuckets).fill(0.02), durationSeconds: 0 };
      }

      const samples = new Int16Array(buffer.buffer, buffer.byteOffset, sampleCount);
      const durationSeconds = sampleCount / 8000;
      const peaks: number[] = [];
      const bucketSize = sampleCount / numBuckets;

      for (let b = 0; b < numBuckets; b++) {
        const start = Math.floor(b * bucketSize);
        const end = Math.min(sampleCount, Math.floor((b + 1) * bucketSize));
        let max = 0;
        for (let i = start; i < end; i++) {
          const abs = Math.abs(samples[i]);
          if (abs > max) max = abs;
        }
        // Normalize 0 to 32768 -> 0.0 to 1.0
        const normalized = Math.min(1.0, Math.max(0.01, Number((max / 32768).toFixed(4))));
        peaks.push(normalized);
      }

      this.logger.info('ffmpeg', `Waveform generated: ${peaks.length} peaks, ${durationSeconds.toFixed(1)}s`);
      return { peaks, durationSeconds };
    } catch (err: any) {
      this.logger.error('ffmpeg', 'Waveform generation error', err);
      return { peaks: new Array(numBuckets).fill(0.05), durationSeconds: 0 };
    }
  }

  /**
   * Captures a high quality JPEG frame snapshot at the specified timestamp
   */
  public async captureFrame(videoPath: string, timestampSeconds: number, outputPath?: string): Promise<FrameCaptureResult> {
    try {
      if (!fs.existsSync(videoPath)) {
        return {
          success: false,
          imagePath: '',
          timestampSeconds,
          errorMessage: `Video file not found: ${videoPath}`,
        };
      }

      let dest = outputPath;
      if (!dest) {
        const dir = path.dirname(videoPath);
        const base = path.basename(videoPath, path.extname(videoPath));
        const cleanTs = Math.round(timestampSeconds * 1000);
        dest = path.join(dir, `${base}_frame_${cleanTs}.jpg`);
      }

      const destDir = path.dirname(dest);
      if (!fs.existsSync(destDir)) {
        fs.mkdirSync(destDir, { recursive: true });
      }

      const safeTs = Math.max(0, timestampSeconds).toFixed(3);
      const args = [
        '-ss', safeTs,
        '-i', videoPath,
        '-vframes', '1',
        '-q:v', '2',
        '-y',
        dest,
      ];

      await new Promise<void>((resolve, reject) => {
        const proc = spawn('ffmpeg', args);
        const stderrChunks: Buffer[] = [];
        proc.stderr.on('data', (c) => stderrChunks.push(c));
        proc.on('close', (code) => {
          if (code === 0 && fs.existsSync(dest)) resolve();
          else reject(new Error(`Frame capture failed with code ${code}: ${Buffer.concat(stderrChunks).toString()}`));
        });
        proc.on('error', (err) => reject(err));
      });

      this.logger.info('ffmpeg', `Captured frame snapshot at ${safeTs}s: ${dest}`);
      return {
        success: true,
        imagePath: dest,
        timestampSeconds,
      };
    } catch (err: any) {
      this.logger.error('ffmpeg', 'Frame capture failed', err);
      return {
        success: false,
        imagePath: '',
        timestampSeconds,
        errorMessage: err.message || String(err),
      };
    }
  }
}
