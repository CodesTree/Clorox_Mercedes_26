import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { VoiceVisualizer } from "./VoiceVisualizer";

describe("VoiceVisualizer", () => {
  it("renders 7 bars", () => {
    render(<VoiceVisualizer level={0.5} idle={false} />);
    const container = screen.getByTestId("voice-visualizer");
    expect(container.querySelectorAll(".voice-visualizer__bar")).toHaveLength(7);
  });

  it("sets bar heights from the level prop when not idle", () => {
    render(<VoiceVisualizer level={1} idle={false} />);
    const bars = screen.getByTestId("voice-visualizer").querySelectorAll<HTMLSpanElement>(".voice-visualizer__bar");
    expect(bars[3].style.height).toBe("28px");
    expect(bars[0].style.height).toBe("20px");
  });

  it("adds the idle modifier class and skips inline heights when idle", () => {
    render(<VoiceVisualizer level={0.8} idle />);
    const container = screen.getByTestId("voice-visualizer");
    expect(container.className).toContain("voice-visualizer--idle");
    const bars = container.querySelectorAll<HTMLSpanElement>(".voice-visualizer__bar");
    expect(bars[0].style.height).toBe("");
  });
});
