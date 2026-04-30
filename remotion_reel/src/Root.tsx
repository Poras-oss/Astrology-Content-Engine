import React from "react";
import {Composition} from "remotion";
import {HoroscopeReel} from "./HoroscopeReel";
import {HoroscopeBundle} from "./types";
import renderBundle from "./data/render-bundle.json";

const fps = 30;
const sampleBundle = renderBundle as HoroscopeBundle;
const cardCount =
  sampleBundle.signs?.length ||
  sampleBundle.groups?.length ||
  4;
const durationInFrames = (6 + cardCount * 4) * fps;

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="HoroscopeReel"
      component={HoroscopeReel}
      width={1080}
      height={1920}
      fps={fps}
      durationInFrames={durationInFrames}
      defaultProps={{bundle: sampleBundle}}
    />
  );
};
