import { describe, expect, it, vi } from "vitest";
import { loadWithRetry } from "../lib/utils";

const noSleep = async () => {};

describe("loadWithRetry", () => {
  it("keeps trying until the backend answers", async () => {
    // The frozen backend needs a few seconds to bind; the window opens first.
    let calls = 0;
    const load = vi.fn(async () => {
      calls += 1;
      if (calls < 4) throw new Error("ECONNREFUSED");
    });

    const ok = await loadWithRetry(load, { attempts: 20, delayMs: 1, sleep: noSleep });
    expect(ok).toBe(true);
    expect(load).toHaveBeenCalledTimes(4);
  });

  it("succeeds immediately when the backend is already up", async () => {
    const load = vi.fn(async () => {});
    expect(await loadWithRetry(load, { attempts: 5, delayMs: 1, sleep: noSleep })).toBe(true);
    expect(load).toHaveBeenCalledTimes(1);
  });

  it("gives up after the attempt budget instead of looping forever", async () => {
    const load = vi.fn(async () => {
      throw new Error("down");
    });
    expect(await loadWithRetry(load, { attempts: 3, delayMs: 1, sleep: noSleep })).toBe(false);
    expect(load).toHaveBeenCalledTimes(3);
  });

  it("stops when the component unmounts mid-retry", async () => {
    let cancelled = false;
    const load = vi.fn(async () => {
      cancelled = true; // unmount happens during the first attempt
      throw new Error("down");
    });

    const ok = await loadWithRetry(load, {
      attempts: 10,
      delayMs: 1,
      sleep: noSleep,
      isCancelled: () => cancelled,
    });
    expect(ok).toBe(false);
    expect(load).toHaveBeenCalledTimes(1);
  });

  it("waits between attempts", async () => {
    const sleep = vi.fn(async () => {});
    let calls = 0;
    await loadWithRetry(
      async () => {
        calls += 1;
        if (calls < 3) throw new Error("down");
      },
      { attempts: 5, delayMs: 1500, sleep },
    );
    expect(sleep).toHaveBeenCalledWith(1500);
    expect(sleep).toHaveBeenCalledTimes(2);
  });
});

describe("startup history load", () => {
  it("is wired through the retry helper", () => {
    const source = require("node:fs").readFileSync(
      require("node:path").resolve(__dirname, "..", "app/page.tsx"),
      "utf-8",
    );
    expect(source).toContain("loadWithRetry(loadJobs");
    // A bare swallowed failure here is what emptied the history.
    expect(source).not.toContain("loadJobs().catch(() => undefined);\n   }, [loadJobs]);");
  });
});
