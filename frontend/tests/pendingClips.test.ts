import { describe, expect, it } from "vitest";
import { pendingClipCount } from "../lib/utils";

describe("pendingClipCount", () => {
  it("shows one placeholder per clip still rendering", () => {
    expect(pendingClipCount("running", 4, 1)).toBe(3);
  });

  it("shows every clip as pending before the first one lands", () => {
    expect(pendingClipCount("running", 4, 0)).toBe(4);
  });

  it("shows nothing once the job finishes", () => {
    expect(pendingClipCount("completed", 4, 4)).toBe(0);
    expect(pendingClipCount("failed", 4, 1)).toBe(0);
  });

  it("covers a queued job that has not started rendering", () => {
    expect(pendingClipCount("queued", 3, 0)).toBe(3);
  });

  it("never goes negative when more clips arrive than expected", () => {
    expect(pendingClipCount("running", 2, 5)).toBe(0);
  });

  it("handles a missing expected count from an older job", () => {
    expect(pendingClipCount("running", null, 2)).toBe(0);
    expect(pendingClipCount("running", undefined, 0)).toBe(0);
  });
});
