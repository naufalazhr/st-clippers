import { describe, it, expect, vi, beforeEach } from "vitest";
import { getTimeline, recutClip } from "../lib/apiClient";
import type { TimelineData, ClipFile, ClipCandidate } from "../types/clip.type";

beforeEach(() => {
  vi.unstubAllGlobals();
});

const mockTimeline: TimelineData = {
  source_url: "http://localhost:8010/outputs/test.mp4",
  duration: 120,
  segments: [{ start: 0, end: 10, text: "hello" }],
  candidates: [],
};

const mockClip: ClipFile = {
  name: "clip_0.mp4",
  url: "/outputs/clip_0.mp4",
  size_bytes: 1024,
};

const mockCandidate: ClipCandidate = {
  index: 0,
  start: 5,
  end: 25,
  duration: 20,
  score: 0.9,
  title: "Test clip",
  reason: "high score",
  text: "hello world",
};

describe("getTimeline", () => {
  it("returns typed TimelineData on ok response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockTimeline),
    }));

    const result = await getTimeline("job-123");
    expect(result).toEqual(mockTimeline);
    expect((fetch as ReturnType<typeof vi.fn>)).toHaveBeenCalledWith(
      expect.stringContaining("/api/jobs/job-123/timeline"),
      expect.any(Object),
    );
  });

  it("throws on non-ok response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce({
      ok: false,
      text: () => Promise.resolve("Not found"),
    }));

    await expect(getTimeline("bad-job")).rejects.toThrow("Not found");
  });
});

describe("recutClip", () => {
  it("returns typed RecutResponse on ok response", async () => {
    const mockResponse = { clip: mockClip, candidate: mockCandidate };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockResponse),
    }));

    const result = await recutClip("job-123", { index: 0, start: 5, end: 25 });
    expect(result).toEqual(mockResponse);
    expect((fetch as ReturnType<typeof vi.fn>)).toHaveBeenCalledWith(
      expect.stringContaining("/api/jobs/job-123/recut"),
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ index: 0, start: 5, end: 25 }),
      }),
    );
  });

  it("throws on non-ok response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce({
      ok: false,
      text: () => Promise.resolve("Server error"),
    }));

    await expect(recutClip("job-123", { index: 0, start: 5, end: 25 })).rejects.toThrow("Server error");
  });
});
