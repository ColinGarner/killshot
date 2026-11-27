import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { TeamBox } from "../api/client";
import { BoxScoreTable, displayName, sharedShortNames } from "./BoxScoreTable";
import { Segmented } from "./Segmented";

afterEach(cleanup);

const zero = {
  pts: 0,
  fgm: 0,
  fga: 0,
  tpm: 0,
  tpa: 0,
  ftm: 0,
  fta: 0,
  oreb: 0,
  dreb: 0,
  ast: 0,
  stl: 0,
  blk: 0,
  tov: 0,
  pf: 0,
};
const white = { id: "1", name: "Tre White", short_name: "White" };
const box: TeamBox = {
  team: { id: "131", name: "Kansas" },
  players: [
    {
      ...zero,
      player: white,
      minutes: 34.1,
      pts: 30,
      fgm: 11,
      fga: 16,
      tpm: 4,
      tpa: 8,
      ftm: 4,
      fta: 4,
      oreb: 2,
      dreb: 4,
      plus_minus: 17,
    },
  ],
  totals: { ...zero, pts: 89, fgm: 32, fga: 69, tpm: 10, tpa: 26, ftm: 15, fta: 23, oreb: 12, dreb: 28 },
};

describe("BoxScoreTable", () => {
  it("shows a player's line and the team line", () => {
    render(<BoxScoreTable box={box} />);
    const [, player, team] = screen.getAllByRole("row");
    expect(
      within(player)
        .getAllByRole("cell")
        .map((c) => c.textContent),
    ).toEqual(["White", "34", "30", "11-16", "4-8", "4-4", "6", "2", "0", "0", "0", "0", "0", "+17"]);
    expect(within(team).getByText("89")).toBeTruthy();
    expect(within(team).getByText("32-69")).toBeTruthy();
  });

  it("opens a player's season stats from their name, when allowed", () => {
    const onSelect = vi.fn();
    render(<BoxScoreTable box={box} onSelectPlayer={onSelect} />);
    fireEvent.click(screen.getByRole("button", { name: "White" }));
    expect(onSelect).toHaveBeenCalledWith(white);
  });

  it("says so before anyone has a stat", () => {
    render(<BoxScoreTable box={{ ...box, players: [] }} />);
    expect(screen.getByText("No stats yet.")).toBeTruthy();
  });
});

describe("names", () => {
  it("adds a first initial only when two players share a short name", () => {
    const mason = { id: "2", name: "Mason Williams", short_name: "Williams" };
    const jasper = { id: "3", name: "Jasper Williams", short_name: "Williams" };
    const shared = sharedShortNames([white, mason, jasper]);
    expect([white, mason, jasper].map((p) => displayName(p, shared))).toEqual(["White", "M. Williams", "J. Williams"]);
  });
});

describe("Segmented", () => {
  it("marks the chosen option and reports a new choice", () => {
    const onChange = vi.fn();
    render(
      <Segmented
        label="View"
        value="lineups"
        onChange={onChange}
        options={[
          { value: "lineups", label: "Lineups" },
          { value: "box", label: "Box score" },
        ]}
      />,
    );
    expect(screen.getByRole("radio", { name: "Lineups" }).getAttribute("aria-checked")).toBe("true");
    fireEvent.click(screen.getByRole("radio", { name: "Box score" }));
    expect(onChange).toHaveBeenCalledWith("box");
  });
});
