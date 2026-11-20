import type { OnOff, PlayerAdvanced } from "../api/client";

/** Player id -> their CBBD season stats, from a season's on/off list.
 * null means the worker hasn't synced that player's stats yet, not that they don't exist. */
export function advancedById(onOff: OnOff[]): Record<string, PlayerAdvanced | null | undefined> {
  return Object.fromEntries(onOff.map((r) => [r.player.id, r.advanced]));
}
