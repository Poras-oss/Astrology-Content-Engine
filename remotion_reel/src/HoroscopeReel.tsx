import React from "react";
import {
  AbsoluteFill,
  Easing,
  Sequence,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig
} from "remotion";
import {HoroscopeBundle, SignCard} from "./types";

const introFrames = 90;
const signFrames = 120;
const outroFrames = 90;

const textStyle: React.CSSProperties = {
  fontFamily: "Georgia, 'Times New Roman', serif",
  color: "white",
  letterSpacing: "-0.02em"
};

const Badge: React.FC<{label: string}> = ({label}) => (
  <div
    style={{
      border: "1px solid rgba(255,255,255,0.18)",
      borderRadius: 999,
      padding: "12px 20px",
      fontSize: 28,
      color: "rgba(255,255,255,0.72)",
      backdropFilter: "blur(12px)",
      background: "rgba(255,255,255,0.06)"
    }}
  >
    {label}
  </div>
);

const Background: React.FC<{palette: string[]; accentOpacity?: number}> = ({palette, accentOpacity = 0.3}) => {
  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(circle at 20% 15%, ${withAlpha(palette[2], accentOpacity)} 0%, transparent 30%),
          radial-gradient(circle at 85% 25%, rgba(255,255,255,0.12) 0%, transparent 24%),
          radial-gradient(circle at 50% 80%, ${withAlpha(palette[1], 0.45)} 0%, transparent 35%),
          linear-gradient(155deg, ${palette[0]} 0%, ${palette[1]} 60%, #050505 100%)`
      }}
    />
  );
};

const withAlpha = (hex: string, alpha: number): string => {
  const normalized = hex.replace("#", "");
  if (normalized.length !== 6) {
    return hex;
  }
  const r = Number.parseInt(normalized.slice(0, 2), 16);
  const g = Number.parseInt(normalized.slice(2, 4), 16);
  const b = Number.parseInt(normalized.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
};

const TitleScene: React.FC<{bundle: HoroscopeBundle}> = ({bundle}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const scale = spring({fps, frame, config: {damping: 16, stiffness: 110}});
  const opacity = interpolate(frame, [0, 18, 58, 75], [0, 1, 1, 0], {
    easing: Easing.out(Easing.cubic),
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp"
  });

  return (
    <AbsoluteFill style={{padding: 72, justifyContent: "space-between", opacity}}>
      <Background palette={["#060816", "#24143C", "#FF8A5B"]} accentOpacity={0.38} />
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "linear-gradient(180deg, rgba(0,0,0,0.15) 0%, rgba(0,0,0,0.22) 30%, rgba(0,0,0,0.62) 100%)"
        }}
      />
      <div style={{position: "relative", zIndex: 1}}>
        <div
          style={{
            ...textStyle,
            fontSize: 30,
            textTransform: "uppercase",
            color: "rgba(255,255,255,0.68)",
            marginBottom: 28,
            letterSpacing: "0.22em"
          }}
        >
          Viral All-Signs Reel
        </div>
        <div
          style={{
            ...textStyle,
            fontSize: 110,
            fontWeight: 700,
            lineHeight: 0.95,
            maxWidth: 850,
            transform: `scale(${0.92 + scale * 0.08})`,
            transformOrigin: "left top"
          }}
        >
          {bundle.meta.cover_text}
        </div>
      </div>

      <div style={{position: "relative", zIndex: 1, maxWidth: 880}}>
        <div
          style={{
            ...textStyle,
            fontSize: 54,
            lineHeight: 1.08,
            marginBottom: 34,
            color: "#FFF2E8"
          }}
        >
          {bundle.meta.hook}
        </div>
        <div style={{display: "flex", gap: 16, flexWrap: "wrap"}}>
          <Badge label={bundle.meta.theme} />
          <Badge label={bundle.meta.audio_direction} />
        </div>
      </div>
    </AbsoluteFill>
  );
};

const SignScene: React.FC<{card: SignCard}> = ({card}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const enter = spring({fps, frame, config: {damping: 18, stiffness: 130}});
  const accentRise = interpolate(frame, [0, signFrames], [120, -40], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp"
  });

  return (
    <AbsoluteFill style={{padding: 60}}>
      <Background palette={card.palette as string[]} />
      <div
        style={{
          position: "absolute",
          inset: 24,
          borderRadius: 40,
          border: "1px solid rgba(255,255,255,0.08)",
          background: "linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.01))"
        }}
      />
      <div
        style={{
          position: "absolute",
          right: 40,
          top: accentRise,
          width: 360,
          height: 360,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${withAlpha(card.palette[2], 0.72)} 0%, transparent 70%)`,
          filter: "blur(10px)"
        }}
      />

      <div style={{position: "relative", zIndex: 1, display: "flex", flexDirection: "column", height: "100%"}}>
        <div style={{display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 50}}>
          <div>
            <div
              style={{
                ...textStyle,
                fontSize: 28,
                textTransform: "uppercase",
                color: "rgba(255,255,255,0.62)",
                letterSpacing: "0.2em",
                marginBottom: 16
              }}
            >
              {card.element} Sign
            </div>
            <div
              style={{
                ...textStyle,
                fontSize: 96,
                fontWeight: 700,
                lineHeight: 0.92,
                transform: `translateY(${(1 - enter) * 20}px)`,
                opacity: enter
              }}
            >
              {card.sign}
            </div>
          </div>
          <Badge label={card.theme} />
        </div>

        <div
          style={{
            ...textStyle,
            fontSize: 50,
            lineHeight: 1.08,
            maxWidth: 920,
            marginBottom: 36,
            color: "#FFF7EF"
          }}
        >
          {card.private_truth}
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr",
            gap: 22,
            marginBottom: 36
          }}
        >
          {[card.tension, card.shift].map((line) => (
            <div
              key={line}
              style={{
                ...textStyle,
                fontSize: 32,
                lineHeight: 1.25,
                padding: "24px 28px",
                borderRadius: 28,
                color: "rgba(255,255,255,0.84)",
                background: "rgba(0,0,0,0.22)",
                border: "1px solid rgba(255,255,255,0.08)",
                backdropFilter: "blur(14px)"
              }}
            >
              {line}
            </div>
          ))}
        </div>

        <div
          style={{
            marginTop: "auto",
            padding: "34px 36px",
            borderRadius: 32,
            background: "rgba(255,255,255,0.08)",
            border: "1px solid rgba(255,255,255,0.14)",
            boxShadow: "0 24px 80px rgba(0,0,0,0.3)"
          }}
        >
          <div
            style={{
              ...textStyle,
              fontSize: 24,
              textTransform: "uppercase",
              color: "rgba(255,255,255,0.58)",
              letterSpacing: "0.16em",
              marginBottom: 16
            }}
          >
            Screenshot This
          </div>
          <div style={{...textStyle, fontSize: 58, lineHeight: 1.03, marginBottom: 18}}>
            {card.screenshot_line}
          </div>
          <div style={{...textStyle, fontSize: 30, lineHeight: 1.2, color: "rgba(255,255,255,0.72)"}}>
            {card.share_line}
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

const OutroScene: React.FC<{bundle: HoroscopeBundle}> = ({bundle}) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 16, outroFrames - 18, outroFrames], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp"
  });

  return (
    <AbsoluteFill style={{padding: 72, justifyContent: "flex-end", opacity}}>
      <Background palette={["#080B16", "#2A1336", "#F7A072"]} accentOpacity={0.4} />
      <div
        style={{
          position: "relative",
          zIndex: 1,
          padding: "46px 44px",
          borderRadius: 36,
          background: "rgba(0,0,0,0.26)",
          border: "1px solid rgba(255,255,255,0.1)"
        }}
      >
        <div style={{...textStyle, fontSize: 84, fontWeight: 700, lineHeight: 0.96, marginBottom: 20}}>
          Save this.
          <br />
          Send it.
          <br />
          Come back to it.
        </div>
        <div style={{...textStyle, fontSize: 34, lineHeight: 1.18, color: "rgba(255,255,255,0.74)"}}>
          {bundle.meta.cta}
        </div>
      </div>
    </AbsoluteFill>
  );
};

export const HoroscopeReel: React.FC<{bundle: HoroscopeBundle}> = ({bundle}) => {
  const cards = bundle.signs.slice(0, 12);

  return (
    <AbsoluteFill style={{backgroundColor: "#050505"}}>
      <Sequence from={0} durationInFrames={introFrames}>
        <TitleScene bundle={bundle} />
      </Sequence>

      {cards.map((card, index) => (
        <Sequence
          key={card.sign}
          from={introFrames + index * signFrames}
          durationInFrames={signFrames}
        >
          <SignScene card={card} />
        </Sequence>
      ))}

      <Sequence
        from={introFrames + cards.length * signFrames}
        durationInFrames={outroFrames}
      >
        <OutroScene bundle={bundle} />
      </Sequence>
    </AbsoluteFill>
  );
};
