import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const read = (p: string) => readFileSync(resolve(__dirname, "..", p), "utf-8");

describe("recut shows progress instead of freezing the dialog", () => {
  it("closes the dialog immediately rather than awaiting the render", () => {
    const source = read("app/_components/EditCaptionDialog.tsx");
    const close = source.indexOf("onClose();");
    const success = source.indexOf("onSuccess();");
    // Close first so the card's progress overlay is what the user watches.
    expect(close).toBeGreaterThan(-1);
    expect(close).toBeLessThan(success);
  });

  it("polls again once a recut puts the job back to running", () => {
    const source = read("app/page.tsx");
    // Status-keyed effect: stops when settled, restarts when running resumes.
    expect(source).toContain("const activeStatus = job?.status;");
    expect(source).toMatch(/\[activeJobId, activeStatus, loadJobs\]/);
    expect(source).not.toContain("window.clearInterval(interval);\n           loadJobs");
  });

  it("marks only the clip being re-rendered as busy", () => {
    const source = read("app/_components/ResultsSection.tsx");
    expect(source).toContain("recut_index");
    expect(source).toContain("clipCard--rerendering");
    expect(source).toContain("Merender ulang");
  });

  it("reports a failed background recut to the user", () => {
    const source = read("app/_components/ResultsSection.tsx");
    expect(source).toContain("recut_error");
    expect(source).toContain("toast.error");
  });
});

describe("clip URLs", () => {
  it("are used verbatim so the cache-busting query survives", () => {
    // getOutputUrl must not strip or rebuild the query the backend adds.
    const source = read("lib/apiClient.ts");
    expect(source).toContain("export const getOutputUrl = (path: string) => `${API_BASE}${path}`");
  });
});
