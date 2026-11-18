import { describe, expect, it } from "vitest";
import type { WinProbPoint } from "../api/client";
import { clockTime, currentRun, isStale } from "./live";

/** Win-probability samples from [ours, theirs] scores; only the score matters here. */
const at = (...scores: [number, number][]): WinProbPoint[] =>
  scores.map(([pts, opp_pts], i) => ({ t: i * 10, clock: "", win_prob: 50, pts, opp_pts }));

describe("currentRun", () => {
  it("counts our points since their last basket", () => {
    // 51-41 when they last scored, then 12 straight: a 12-0 run.
    expect(currentRun(at([51, 39], [51, 41], [56, 41], [63, 41]))).toEqual({ by: "team", pts: 12 });
  });

  it("counts theirs the same way", () => {
    expect(currentRun(at([20, 18], [22, 18], [22, 21], [22, 25]))).toEqual({ by: "opponent", pts: 7 });
  });

  it("is a run from tip-off if the other team hasn't scored", () => {
    expect(currentRun(at([0, 0], [3, 0], [5, 0]))).toEqual({ by: "team", pts: 5 });
  });

  it("is nothing before anyone scores", () => {
    expect(currentRun(at([0, 0], [0, 0]))).toBeNull();
    expect(currentRun([])).toBeNull();
  });
});

describe("live freshness", () => {
  const updated = "2026-11-19T02:42:00Z"; // 8:42 PM in Lawrence
  it("shows the update time in Kansas time", () => {
    expect(clockTime(updated)).toBe("8:42 PM");
  });

  it("is stale after two minutes without new data", () => {
    const t = new Date(updated).getTime();
    expect(isStale(updated, t + 90_000)).toBe(false);
    expect(isStale(updated, t + 150_000)).toBe(true);
  });
});
