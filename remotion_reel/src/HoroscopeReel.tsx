import React from "react";
import {
  AbsoluteFill,
  Audio,
  Easing,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig
} from "remotion";
import {HoroscopeBundle, HoroscopeSign, SignGroup} from "./types";

const introFrames = 90;
const outroFrames = 90;

type ReelItem = {
  label: string;
  sublabel: string;
  badge: string;
  lines: string[];
  accent: string;
  palette: string[];
};

const textStyle: React.CSSProperties = {
  fontFamily: "'Inter', 'Roboto', sans-serif",
  color: "white",
  letterSpacing: 0
};

const clampText = (text: string | undefined, fallback: string) => {
  const value = String(text || "").trim();
  return value || fallback;
};

const sizeFor = (text: string, large: number, medium: number, small: number) => {
  if (text.length > 92) {
    return small;
  }
  if (text.length > 62) {
    return medium;
  }
  return large;
};

const asItems = (bundle: HoroscopeBundle): ReelItem[] => {
  if (Array.isArray(bundle.signs) && bundle.signs.length > 0) {
    return bundle.signs.map((sign: HoroscopeSign) => ({
      label: sign.sign,
      sublabel: sign.element || sign.symbol || "Zodiac",
      badge: sign.theme || sign.symbol || sign.sign,
      lines: [
        ...(Array.isArray(sign.reel_lines) ? sign.reel_lines : []),
        sign.screenshot_line,
        sign.shift
      ].filter(Boolean).slice(0, 3),
      accent: sign.palette?.[2] || "#FFB86B",
      palette: sign.palette?.length ? sign.palette : ["#0B0B0D", "#22252E", "#FFB86B"]
    }));
  }

  return (bundle.groups || []).map((group: SignGroup) => {
    const splitLines = group.message.split(/[.!?]/).map(l => l.trim()).filter(Boolean);
    return {
      label: group.group_name,
      sublabel: group.signs_included.join(" / "),
      badge: group.visual_cue,
      lines: [
        splitLines[0] || group.message,
        splitLines[1] || group.visual_cue,
        splitLines[2] || "Read it twice."
      ].slice(0, 3),
      accent: "#FF6AA2",
      palette: ["#0B0B0D", "#281A33", "#FF6AA2"]
    };
  });
};

const bundleHook = (bundle: HoroscopeBundle) =>
  clampText(bundle.meta?.hook || bundle.hook, "This sign message is not subtle.");

const bundleCover = (bundle: HoroscopeBundle) =>
  clampText(bundle.meta?.cover_text || bundle.targeting?.headline || bundleHook(bundle), "YOUR SIGN GOT CALLED OUT");

const bundleCta = (bundle: HoroscopeBundle) =>
  clampText(bundle.meta?.cta || bundle.CTA, "Save this and send it to the sign that got read.");

const bundleLabel = (bundle: HoroscopeBundle) =>
  clampText(bundle.targeting?.label || bundle.meta?.title, "Astrology check");

const bundleDescription = (bundle: HoroscopeBundle) =>
  clampText(bundle.meta?.description || (bundle as any).description, "");

const Background: React.FC<{items: ReelItem[]}> = ({items}) => {
  const frame = useCurrentFrame();
  const palette = items[0]?.palette || ["#08080A", "#1A1A22", "#FFB86B"];
  const drift = interpolate(frame % 180, [0, 90, 180], [0, 1, 0]);

  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(${180 + drift * 18}deg, ${palette[0]} 0%, #050505 44%, ${palette[1]} 100%)`
      }}
    >
      <AbsoluteFill
        style={{
          opacity: 0.34,
          backgroundImage:
            "linear-gradient(rgba(255,255,255,0.08) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.05) 1px, transparent 1px)",
          backgroundSize: "72px 72px",
          transform: `translateY(${-drift * 24}px)`
        }}
      />
    </AbsoluteFill>
  );
};

const TitleScene: React.FC<{bundle: HoroscopeBundle; items: ReelItem[]}> = ({bundle, items}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const scale = spring({fps, frame, config: {damping: 15, stiffness: 120}});
  const opacity = interpolate(frame, [0, 12, introFrames - 12, introFrames], [0, 1, 1, 0], {
    easing: Easing.out(Easing.cubic),
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp"
  });
  const cover = bundleCover(bundle);
  const hook = bundleHook(bundle);

  return (
    <AbsoluteFill style={{padding: 76, justifyContent: "center", opacity}}>
      <div style={{...textStyle, fontSize: 28, fontWeight: 800, color: items[0]?.accent || "#FFB86B", textTransform: "uppercase"}}>
        {bundleLabel(bundle)}
      </div>
      <div
        style={{
          ...textStyle,
          marginTop: 24,
          fontSize: sizeFor(cover, 86, 74, 62),
          fontWeight: 900,
          lineHeight: 0.98,
          textTransform: "uppercase",
          transform: `scale(${0.94 + scale * 0.06})`,
          textShadow: "0px 14px 34px rgba(0,0,0,0.75)"
        }}
      >
        {cover}
      </div>
      <div style={{...textStyle, marginTop: 34, fontSize: 38, lineHeight: 1.18, color: "rgba(255,255,255,0.82)", maxWidth: 880}}>
        {hook}
      </div>
      {bundleDescription(bundle) && (
        <div style={{...textStyle, marginTop: 24, fontSize: 24, color: "rgba(255,255,255,0.5)", textTransform: "uppercase", letterSpacing: 2}}>
          {bundleDescription(bundle)}
        </div>
      )}
    </AbsoluteFill>
  );
};

const SignScene: React.FC<{item: ReelItem; index: number; total: number; duration: number}> = ({item, index, total, duration}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const enter = spring({fps, frame, config: {damping: 18, stiffness: 130}});
  const opacity = interpolate(frame, [0, 10, duration - 12, duration], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp"
  });
  const lineOne = clampText(item.lines[0], "This one is for you.");
  const lineTwo = clampText(item.lines[1], "You already know why.");
  const lineThree = clampText(item.lines[2], "Do not ignore the pattern.");

  return (
    <AbsoluteFill style={{padding: 64, opacity}}>
      <div style={{display: "flex", justifyContent: "space-between", alignItems: "center"}}>
        <div style={{...textStyle, fontSize: 32, fontWeight: 900, color: item.accent, textTransform: "uppercase"}}>
          {item.label}
        </div>
        <div style={{...textStyle, fontSize: 26, fontWeight: 700, color: "rgba(255,255,255,0.62)"}}>
          {String(index + 1).padStart(2, "0")} / {String(total).padStart(2, "0")}
        </div>
      </div>

      <div style={{...textStyle, marginTop: 14, fontSize: 28, color: "rgba(255,255,255,0.56)", textTransform: "uppercase"}}>
        {item.sublabel}
      </div>

      <div
        style={{
          marginTop: 96,
          transform: `translateY(${(1 - enter) * 42}px)`,
          borderLeft: `8px solid ${item.accent}`,
          paddingLeft: 30
        }}
      >
        <div style={{...textStyle, fontSize: 18, fontWeight: 800, color: "rgba(255,255,255,0.4)", marginBottom: 8, letterSpacing: 1}}>
          THE VIBE
        </div>
        <div
          style={{
            ...textStyle,
            fontSize: sizeFor(lineOne, 74, 64, 54),
            fontWeight: 900,
            lineHeight: 1.04,
            textTransform: "uppercase",
            textShadow: "0px 12px 34px rgba(0,0,0,0.72)"
          }}
        >
          {lineOne}
        </div>

        <div style={{...textStyle, fontSize: 18, fontWeight: 800, color: "rgba(255,255,255,0.4)", marginTop: 42, marginBottom: 8, letterSpacing: 1}}>
          THE REASON
        </div>
        <div style={{...textStyle, fontSize: sizeFor(lineTwo, 48, 42, 36), fontWeight: 700, lineHeight: 1.16, color: "rgba(255,255,255,0.88)"}}>
          {lineTwo}
        </div>

        <div style={{...textStyle, fontSize: 18, fontWeight: 800, color: item.accent, opacity: 0.7, marginTop: 34, marginBottom: 8, letterSpacing: 1.5}}>
          THE SHIFT
        </div>
        <div style={{...textStyle, fontSize: sizeFor(lineThree, 42, 36, 32), fontWeight: 800, lineHeight: 1.18, color: item.accent}}>
          {lineThree}
        </div>
      </div>

      <div
        style={{
          ...textStyle,
          position: "absolute",
          left: 64,
          right: 64,
          bottom: 84,
          paddingTop: 22,
          borderTop: "1px solid rgba(255,255,255,0.18)",
          fontSize: 30,
          fontWeight: 800,
          color: "rgba(255,255,255,0.76)",
          textTransform: "uppercase"
        }}
      >
        {item.badge}
      </div>
    </AbsoluteFill>
  );
};

const OutroScene: React.FC<{bundle: HoroscopeBundle}> = ({bundle}) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 14, outroFrames - 12, outroFrames], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp"
  });
  const cta = bundleCta(bundle);

  return (
    <AbsoluteFill style={{padding: 74, justifyContent: "center", opacity}}>
      <div style={{...textStyle, fontSize: 30, fontWeight: 900, color: "#FFB86B", textTransform: "uppercase"}}>
        Your turn
      </div>
      <div style={{...textStyle, marginTop: 24, fontSize: sizeFor(cta, 66, 56, 46), fontWeight: 900, lineHeight: 1.08, textTransform: "uppercase"}}>
        {cta}
      </div>
    </AbsoluteFill>
  );
};

export const HoroscopeReel: React.FC<{bundle: HoroscopeBundle}> = ({bundle}) => {
  const {durationInFrames} = useVideoConfig();
  const items = asItems(bundle);
  const middleFrames = Math.max(1, durationInFrames - introFrames - outroFrames);
  const framesPerItem = Math.max(75, Math.floor(middleFrames / Math.max(1, items.length)));

  return (
    <AbsoluteFill style={{backgroundColor: "#050505"}}>
      <Background items={items} />

      {bundle._internal_audio_path && (
        <Audio 
          src={staticFile(bundle._internal_audio_path)} 
          loop
          volume={(f) =>
            interpolate(
              f,
              [durationInFrames - 60, durationInFrames],
              [1, 0],
              {extrapolateLeft: "clamp", extrapolateRight: "clamp"}
            )
          }
        />
      )}

      <Sequence from={0} durationInFrames={introFrames}>
        <TitleScene bundle={bundle} items={items} />
      </Sequence>

      {items.map((item, index) => (
        <Sequence
          key={`${item.label}-${index}`}
          from={introFrames + index * framesPerItem}
          durationInFrames={framesPerItem}
        >
          <SignScene item={item} index={index} total={items.length} duration={framesPerItem} />
        </Sequence>
      ))}

      <Sequence
        from={introFrames + items.length * framesPerItem}
        durationInFrames={outroFrames}
      >
        <OutroScene bundle={bundle} />
      </Sequence>
    </AbsoluteFill>
  );
};
