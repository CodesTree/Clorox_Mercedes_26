import { render, screen } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import App from "./App";

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ status: "ok", version: "0.1.0" }),
    }),
  );
});

test("renders the AssetIQ shell and reports API status", async () => {
  render(<App />);
  expect(screen.getByText(/AssetIQ/)).toBeInTheDocument();
  expect(await screen.findByTestId("api-status")).toHaveTextContent(/API online - v0.1.0/);
});
