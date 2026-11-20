import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Player, PlayerAdvanced } from "../api/client";
import { PlayerModal } from "./PlayerModal";

afterEach(cleanup);

const player: Player = { id: "5642", name: "Tre White", short_name: "White" };

const advanced: PlayerAdvanced = {
  games: 5, starts: 5, minutes: 129, points: 97, assists: 6, turnovers: 4, steals: 3, blocks: 1, fouls: 3,
  usage: 27.5, offensive_rating: 141.1, defensive_rating: 95.3, net_rating: 45.8, porpag: 6.2,
  effective_fg_pct: 64.8, true_shooting_pct: 0.678, assists_turnover_ratio: 1.5, free_throw_rate: 39.3,
  offensive_rebound_pct: 31.8,
  field_goals: { made: 34, attempted: 61, pct: 55.7 },
  two_point_field_goals: { made: 23, attempted: 37, pct: 62.2 },
  three_point_field_goals: { made: 11, attempted: 24, pct: 45.8 },
  free_throws: { made: 18, attempted: 24, pct: 75 },
  rebounds: { offensive: 7, defensive: 15, total: 22 },
  win_shares: { offensive: 0.7, defensive: 0.3, total: 1, total_per_40: 0.31 },
};

describe("PlayerModal", () => {
  it("turns season totals into per-game numbers and shows the shooting splits", () => {
    render(<PlayerModal player={player} advanced={advanced} onClose={() => {}} />);
    expect(screen.getByText("Tre White")).toBeTruthy();
    expect(screen.getByText("19.4")).toBeTruthy(); // points per game: 97 / 5
    expect(screen.getByText("4.4")).toBeTruthy(); // rebounds per game: 22 / 5
    expect(screen.getByText("34-61")).toBeTruthy();
    expect(screen.getByText("55.7%")).toBeTruthy();
    expect(screen.getByText("+45.8")).toBeTruthy(); // net rating, signed
    expect(screen.getByText("6.2")).toBeTruthy(); // PORPAG
  });

  it("says so when the player's stats haven't synced yet", () => {
    render(<PlayerModal player={player} advanced={null} onClose={() => {}} />);
    expect(screen.getByText("No season stats synced yet.")).toBeTruthy();
    expect(screen.queryByText("19.4")).toBeNull();
  });

  it("closes on the × button, a backdrop click, and Escape", () => {
    const onClose = vi.fn();
    const { rerender } = render(<PlayerModal player={player} advanced={advanced} onClose={onClose} />);

    fireEvent.click(screen.getByLabelText("Close"));
    expect(onClose).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("dialog").parentElement!);
    expect(onClose).toHaveBeenCalledTimes(2);

    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(3);

    rerender(<PlayerModal player={player} advanced={advanced} onClose={onClose} />);
    fireEvent.click(screen.getByRole("dialog")); // clicking inside the sheet itself doesn't close it
    expect(onClose).toHaveBeenCalledTimes(3);
  });
});
