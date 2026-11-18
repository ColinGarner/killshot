// Small formatting helpers shared by the pages.

/** +8.3, -12.0, 0.0: always a sign, for ratings and plus-minus. */
export function signed(value: number, decimals = 1): string {
  const text = Math.abs(value).toFixed(decimals);
  if (value > 0) return `+${text}`;
  if (value < 0) return `−${text}`; // a true minus sign, the same width as +
  return text;
}

/** "Nov 10" in Kansas time. */
export function gameDate(iso: string): string {
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", timeZone: "America/Chicago" }).format(new Date(iso));
}

/** "6:30 PM CT", for upcoming games. */
export function tipTime(iso: string): string {
  const time = new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit", timeZone: "America/Chicago" }).format(new Date(iso));
  return `${time} CT`;
}

/** "vs", "at" or "vs (N)", the way schedules write it. */
export function venuePrefix(venue: "home" | "away" | "neutral"): string {
  return venue === "away" ? "at" : venue === "neutral" ? "vs (N)" : "vs";
}

/**
 * Short player names joined for a lineup: "Blyden · Dawes · Kinney · Stokes · White".
 * The space before each dot can't break, so a long lineup wraps after a dot, never before one.
 */
export function lineupLabel(players: { short_name: string }[]): string {
  return players.map((p) => p.short_name).sort((a, b) => a.localeCompare(b)).join("\u00a0· ");
}

/** The college season (named for the year it ends) that's on now. */
export function currentSeason(today = new Date()): number {
  return today.getMonth() >= 7 ? today.getFullYear() + 1 : today.getFullYear();
}
