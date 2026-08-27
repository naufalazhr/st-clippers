import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const read = (p: string) => readFileSync(resolve(__dirname, "..", p), "utf-8");

describe("EditCaptionDialog stability while the job keeps refreshing", () => {
  const source = read("app/_components/EditCaptionDialog.tsx");

  it("does not reload on every job refresh", () => {
    // job.candidates is a fresh array on each poll and onClose was an inline
    // arrow: either in the dep array re-ran the loader every ~2.2s, resetting
    // the form mid-edit.
    const deps = source.match(/\}, \[open, clipIndex[^\]]*\]/);
    expect(deps, "loader effect dep array not found").toBeTruthy();
    expect(deps![0]).not.toContain("job.candidates");
    expect(deps![0]).not.toContain("onClose");
  });

  it("reaches the live job through a ref instead of a dependency", () => {
    expect(source).toContain("jobRef.current");
    expect(source).toContain("onCloseRef.current");
  });
});

describe("job polling", () => {
  it("stops once the job reaches a terminal state", () => {
    const source = read("app/page.tsx");
    const settled = source.indexOf('nextJob.status === "completed"');
    const cleared = source.indexOf("window.clearInterval(interval)");
    expect(settled).toBeGreaterThan(-1);
    expect(cleared).toBeGreaterThan(settled);
  });
});

describe("ResultsSection callbacks", () => {
  it("passes a stable onClose to the dialog", () => {
    const source = read("app/_components/ResultsSection.tsx");
    expect(source).toContain("handleCloseCaptionDialog");
    expect(source).not.toContain("onClose={() => setEditCaptionClip(null)}");
  });
});
