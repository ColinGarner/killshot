import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { GameDetail, Killshot, Lineup, OnOff } from "../api/client";
import { Killshots } from "./Killshots";
import { LiveBar, OnFloor } from "./LiveBar";
import { LineupTable } from "./LineupTable";
import { OnOffTable } from "./OnOffTable";

const player = (id: string, name: string, short_name: string) => ({ id, name, short_name });
const lineup: Lineup = {
  players: [player("1", "Leroy Blyden Jr.", "Blyden"), player("2", "Keanu Dawes", "Dawes"), player("3", "Taylen Kinney", "Kinney"),
    player("4", "Tyran Stokes", "Stokes"), player("5", "Tre White", "White")],
  stints: 2, minutes: 3.5, poss: 5.2, pts: 14, opp_pts: 6, plus_minus: 8, ortg: 269.2, drtg: 115.4, net: 154.2,
  efg: 0.7, opp_efg: 0.4, tov: 0.1, orb: 0.3, ftr: 0.2,
};

describe("LineupTable", () => {
  it("shows each lineup with its plus-minus and net rating", () => {
    render(<LineupTable lineups={[lineup]} empty="none" />);
    // Testing Library reads non-breaking spaces as ordinary ones.
    expect(screen.getByText("Blyden · Dawes · Kinney · Stokes · White")).toBeTruthy();
    expect(screen.getByText("+154.2")).toBeTruthy();
    expect(screen.getByText("+8")).toBeTruthy();
  });

  it("says so when no lineup qualifies", () => {
    render(<LineupTable lineups={[]} empty="No lineup played 3+ possessions." />);
    expect(screen.getByText("No lineup played 3+ possessions.")).toBeTruthy();
  });

  it("opens the right player when a name in the lineup is clicked", () => {
    const onSelectPlayer = vi.fn();
    render(<LineupTable lineups={[lineup]} empty="none" onSelectPlayer={onSelectPlayer} />);
    fireEvent.click(screen.getByText("White"));
    expect(onSelectPlayer).toHaveBeenCalledWith(player("5", "Tre White", "White"));
  });
});

describe("Killshots", () => {
  it("shows the run, who made it, when, and the score swing", () => {
    const shot: Killshot = { by: "team", label: "12-0", pts: 12, start: "2nd 18:35", end: "2nd 15:00", t0: 1285, t1: 1500,
      score_before: [51, 41], score_after: [63, 41] };
    render(<Killshots killshots={[shot]} opponent="Kentucky" />);
    expect(screen.getByText("12-0")).toBeTruthy();
    expect(screen.getByText("2nd 18:35 to 2nd 15:00")).toBeTruthy();
    expect(screen.getByText("51-41 → 63-41")).toBeTruthy();
  });
});

describe("OnOffTable", () => {
  it("shows net rating with the player on, off, and the difference", () => {
    const { players, stints, ...ratings } = lineup;
    void players;
    void stints;
    const row: OnOff = { player: player("9", "Tre White", "White"), on: { ...ratings, minutes: 91.5, net: 47.2 },
      off: { ...ratings, net: 29.8 }, on_off: 17.4 };
    render(<OnOffTable rows={[row]} />);
    expect(screen.getByText("White")).toBeTruthy();
    expect(screen.getByText("+47.2")).toBeTruthy();
    expect(screen.getByText("+29.8")).toBeTruthy();
    expect(screen.getByText("+17.4")).toBeTruthy();
  });

  it("opens the player when their name is clicked", () => {
    const { players, stints, ...ratings } = lineup;
    void players;
    void stints;
    const row: OnOff = { player: player("9", "Tre White", "White"), on: { ...ratings, minutes: 91.5, net: 47.2 },
      off: { ...ratings, net: 29.8 }, on_off: 17.4 };
    const onSelectPlayer = vi.fn();
    render(<OnOffTable rows={[row]} onSelectPlayer={onSelectPlayer} />);
    fireEvent.click(screen.getByText("White"));
    expect(onSelectPlayer).toHaveBeenCalledWith(row.player);
  });
});

afterEach(cleanup); // each test starts from an empty page

const liveGame = (state: "in" | "post", updatedAt = new Date().toISOString()): GameDetail => ({
  game: { id: "1", start_at: "2026-11-19T00:30:00Z", time_tbd: false, state, status: "12:41 - 2nd Half", venue: "neutral",
    opponent: { id: "2", name: "West Virginia" }, pts: 54, opp_pts: 48, result: state === "post" ? "W" : null,
    has_plays: false, live: true },
  min_poss: 3, lineups: { best: [], worst: [] }, killshots: [],
  win_prob: [{ t: 0, clock: "", win_prob: 50, pts: 0, opp_pts: 0 }, { t: 5, clock: "", win_prob: 60, pts: 40, opp_pts: 48 }, { t: 10, clock: "", win_prob: 74.6, pts: 54, opp_pts: 48 }],
  live: { updated_at: updatedAt, clock: "2nd 12:41", on_floor: lineup.players },
});

describe("LiveBar", () => {
  it("shows the score, clock, win probability and a run in progress", () => {
    render(<LiveBar detail={liveGame("in")} team="Kansas" />);
    expect(screen.getByText("54-48")).toBeTruthy();
    expect(screen.getByText("12:41 - 2nd Half")).toBeTruthy();
    expect(screen.getByText("75%")).toBeTruthy();
    expect(screen.getByText("Kansas on a 14-0 run")).toBeTruthy();
    expect(screen.getByText(/^Updated/)).toBeTruthy();
  });

  it("says when the data has gone stale", () => {
    render(<LiveBar detail={liveGame("in", new Date(Date.now() - 5 * 60_000).toISOString())} team="Kansas" />);
    expect(screen.getByText(/waiting for new data/)).toBeTruthy();
  });

  it("at ESPN's final, says official stats are coming", () => {
    render(<LiveBar detail={liveGame("post")} team="Kansas" />);
    expect(screen.getByText("Final")).toBeTruthy();
    expect(screen.getByText(/Official stats/)).toBeTruthy();
  });
});

describe("OnFloor", () => {
  it("lists the five by short name", () => {
    render(<OnFloor detail={liveGame("in")} />);
    expect(screen.getAllByRole("listitem").map((li) => li.textContent)).toEqual(["Blyden", "Dawes", "Kinney", "Stokes", "White"]);
  });

  it("opens the right player when a pill is clicked", () => {
    const onSelectPlayer = vi.fn();
    render(<OnFloor detail={liveGame("in")} onSelectPlayer={onSelectPlayer} />);
    fireEvent.click(screen.getByText("White"));
    expect(onSelectPlayer).toHaveBeenCalledWith(player("5", "Tre White", "White"));
  });
});
