import { barHeightPx } from "./voiceVisualizerLogic";

interface VoiceVisualizerProps {
  level: number;
  idle: boolean;
}

const BAR_COUNT = 7;

export function VoiceVisualizer({ level, idle }: VoiceVisualizerProps) {
  return (
    <div
      className={`voice-visualizer${idle ? " voice-visualizer--idle" : ""}`}
      data-testid="voice-visualizer"
      aria-hidden="true"
    >
      {Array.from({ length: BAR_COUNT }, (_, index) => (
        <span
          key={index}
          className="voice-visualizer__bar"
          style={idle ? undefined : { height: `${barHeightPx(level, index, BAR_COUNT)}px` }}
        />
      ))}
    </div>
  );
}
