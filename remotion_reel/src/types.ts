export type AudioDirection =
  | string
  | {
      voice_tone?: string;
      bg_music_keywords?: string[];
      pacing?: string;
    };

export type ViralityHooks = {
  controversy_level: number;
  identity_trigger: string;
  share_mechanic: string;
};

export type SignGroup = {
  group_name: string;
  signs_included: string[];
  message: string;
  visual_cue: string;
};

export type HoroscopeMeta = {
  title: string;
  hook: string;
  theme: string;
  description?: string;
  caption_hook: string;
  caption_body: string;
  cta: string;
  audio_direction: AudioDirection;
  cover_text: string;
};

export type HoroscopeSign = {
  sign: string;
  element: string;
  symbol: string;
  palette: string[];
  theme: string;
  private_truth: string;
  tension: string;
  shift: string;
  screenshot_line: string;
  share_line: string;
  reel_lines: string[];
  keywords: string[];
};

export type HoroscopeBundle = {
  generated_at?: string;
  theme_request?: string;
  reel_style?: string;
  targeting?: {
    label: string;
    headline: string;
    target_signs: string[];
  };
  meta?: HoroscopeMeta;
  signs?: HoroscopeSign[];
  hook?: string;
  body?: string;
  CTA?: string;
  groups?: SignGroup[];
  caption?: string;
  hashtags?: string[];
  audio_direction?: AudioDirection;
  virality_hooks?: ViralityHooks;
  _internal_audio_path?: string;
};
