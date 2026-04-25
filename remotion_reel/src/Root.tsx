import React from "react";
import {Composition} from "remotion";
import {HoroscopeReel} from "./HoroscopeReel";
import {HoroscopeBundle} from "./types";
import renderBundle from "./data/render-bundle.json";

const fps = 30;
const introFrames = 90;
const signFrames = 120;
const outroFrames = 90;

const sampleBundle = renderBundle as HoroscopeBundle;

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="HoroscopeReel"
      component={HoroscopeReel}
      width={1080}
      height={1920}
      fps={fps}
      durationInFrames={introFrames + sampleBundle.signs.length * signFrames + outroFrames}
      defaultProps={{bundle: sampleBundle}}
      calculateMetadata={({props}) => {
        const bundle = props.bundle as HoroscopeBundle;
        const totalSigns = Math.max(1, bundle.signs.length);
        return {
          durationInFrames: introFrames + totalSigns * signFrames + outroFrames
        };
      }}
    />
  );
};
