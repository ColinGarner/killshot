import { describe, expect, it } from "vitest";
import { currentSeason, gameDate, lineupLabel, signed, tipTime, venuePrefix } from "./format";

describe("format", () => {
  it("always shows a sign on ratings, with a true minus", () => {
    expect(signed(8.25)).toBe("+8.3");
    expect(signed(-12)).toBe("−12.0");
    expect(signed(0)).toBe("0.0");
    expect(signed(11, 0)).toBe("+11");
  });

  it("shows dates and tip times in Kansas time", () => {
    // 02:30 UTC on Nov 18 is 8:30 PM on Nov 17 in Lawrence.
    expect(gameDate("2026-11-18T02:30:00.000Z")).toBe("Nov 17");
    expect(tipTime("2026-11-18T02:30:00.000Z")).toBe("8:30 PM CT");
  });

  it("writes venues the way schedules do", () => {
    expect([venuePrefix("home"), venuePrefix("away"), venuePrefix("neutral")]).toEqual(["vs", "at", "vs (N)"]);
  });

  it("labels a lineup by sorted short names", () => {
    const players = ["White", "Blyden", "Stokes", "Kinney", "Dawes"].map((short_name) => ({ short_name }));
    expect(lineupLabel(players)).toBe("Blyden\u00a0· Dawes\u00a0· Kinney\u00a0· Stokes\u00a0· White");
  });

  it("names seasons for the year they end", () => {
    expect(currentSeason(new Date("2026-11-18"))).toBe(2027);
    expect(currentSeason(new Date("2027-03-20"))).toBe(2027);
  });
});
