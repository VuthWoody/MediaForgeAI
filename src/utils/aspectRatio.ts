import { AspectRatioPreset } from '../types/studio';

export const ASPECT_RATIO_PRESETS: AspectRatioPreset[] = [
  {
    id: 'original',
    label: 'Auto',
    ratio: null,
    icon: '🎞️',
    platform: 'Native Source',
    description: 'Keep video native dimensions',
  },
  {
    id: '9:16',
    label: '9:16 Shorts / TikTok',
    ratio: 9 / 16,
    icon: '📱',
    platform: 'TikTok / YouTube Shorts / Facebook & IG Reels',
    description: 'Fullscreen mobile vertical (1080×1920)',
  },
  {
    id: '16:9',
    label: '16:9 YouTube',
    ratio: 16 / 9,
    icon: '📺',
    platform: 'YouTube / Vimeo / TV',
    description: 'Standard widescreen landscape (1920×1080)',
  },
  {
    id: '1:1',
    label: '1:1 Square',
    ratio: 1,
    icon: '⏹️',
    platform: 'Instagram / Facebook Feed Post',
    description: 'Square social feed (1080×1080)',
  },
  {
    id: '4:5',
    label: '4:5 Feed',
    ratio: 4 / 5,
    icon: '▯',
    platform: 'Instagram / Facebook Feed',
    description: 'Portrait vertical feed video (1080×1350)',
  },
  {
    id: '21:9',
    label: '21:9 Cinema',
    ratio: 21 / 9,
    icon: '🎬',
    platform: 'Cinematic Anamorphic',
    description: 'Ultra-widescreen cinematic scope',
  },
];
