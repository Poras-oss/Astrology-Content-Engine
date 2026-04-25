export type SignCard = {
  sign: string;
  element: string;
  symbol: string;
  palette: [string, string, string] | string[];
  theme: string;
  private_truth: string;
  tension: string;
  shift: string;
  screenshot_line: string;
  share_line: string;
  reel_lines: [string, string, string] | string[];
  keywords: [string, string, string] | string[];
};

export type HoroscopeBundle = {
  generated_at: string;
  theme_request: string;
  meta: {
    title: string;
    hook: string;
    theme: string;
    caption_hook: string;
    caption_body: string;
    cta: string;
    audio_direction: string;
    cover_text: string;
  };
  signs: SignCard[];
};
