import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AdvisoryModal } from "./AdvisoryModal";

vi.mock("./VoiceAdvisor", () => ({
  VoiceAdvisor: ({ pendingVoiceAction }: { pendingVoiceAction: string | null }) => (
    <div data-testid="voice-advisor-stub">{pendingVoiceAction ?? "none"}</div>
  ),
}));

describe("AdvisoryModal", () => {
  it("renders nothing when closed", () => {
    const { container } = render(
      <AdvisoryModal
        open={false}
        profile={null}
        prediction={null}
        depreciation={null}
        snapshot={null}
        faults={[]}
        market={null}
        pendingVoiceAction={null}
        onPendingVoiceActionHandled={() => undefined}
        onClose={() => undefined}
        onBookInspection={() => undefined}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renders VoiceAdvisor with the forwarded pending action when open", () => {
    render(
      <AdvisoryModal
        open
        profile={null}
        prediction={null}
        depreciation={null}
        snapshot={null}
        faults={[]}
        market={null}
        pendingVoiceAction="demo"
        onPendingVoiceActionHandled={() => undefined}
        onClose={() => undefined}
        onBookInspection={() => undefined}
      />,
    );
    expect(screen.getByTestId("voice-advisor-stub")).toHaveTextContent("demo");
  });
});
