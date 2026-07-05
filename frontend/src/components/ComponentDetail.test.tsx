import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ComponentDetail } from "./ComponentDetail";

describe("ComponentDetail", () => {
  it("renders the battery card at its left anchor", () => {
    const { container } = render(
      <ComponentDetail selected="battery" profile={null} snapshot={null} faults={[]} market={null} />,
    );

    const card = container.querySelector(".component-callout");
    expect(card).not.toBeNull();
    expect(card).toHaveClass("component-callout--left");
    expect(card?.querySelector(".component-callout__code")?.textContent).toBe("BAT");
    expect(container.querySelector(".component-detail")).toBeNull();
  });

  it("renders the engine card at its top anchor", () => {
    const { container } = render(
      <ComponentDetail selected="engine" profile={null} snapshot={null} faults={[]} market={null} />,
    );

    expect(container.querySelector(".component-callout--top")).not.toBeNull();
  });

  it("renders the brakes card at its lower-right anchor", () => {
    const { container } = render(
      <ComponentDetail selected="brakes" profile={null} snapshot={null} faults={[]} market={null} />,
    );

    expect(container.querySelector(".component-callout--lower-right")).not.toBeNull();
  });
});
