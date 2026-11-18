"""Game-clock helpers.

Everything in killshot measures time as *game seconds elapsed*: 0 at tip-off,
1200 at halftime, 2400 at the end of regulation, then +300 per overtime.
That turns "period 2, 14:20 left" into one number we can subtract.
"""

HALF = 1200  # men's college basketball plays two 20-minute halves
OT = 300     # each overtime is 5 minutes


def period_start(period: int) -> int:
    """Game seconds elapsed when a period begins (period 1 = 1st half)."""
    if period <= 2:
        return (period - 1) * HALF
    return 2 * HALF + (period - 3) * OT


def period_length(period: int) -> int:
    return HALF if period <= 2 else OT


def elapsed(period: int, clock: str) -> float:
    """Convert a period number and clock text ("14:20", or "45.2" under a minute) to game seconds."""
    if ":" in clock:
        minutes, seconds = clock.split(":")
        left = int(minutes) * 60 + float(seconds)
    else:  # under a minute, clocks show just seconds
        left = float(clock)
    return period_start(period) + period_length(period) - left


def label(t: float) -> str:
    """Game seconds back to a readable clock, e.g. 1285 -> '2nd 18:35'."""
    if t <= HALF:
        name, left = "1st", HALF - t
    elif t <= 2 * HALF:
        name, left = "2nd", 2 * HALF - t
    else:
        n = int((t - 2 * HALF - 1e-9) // OT) + 1
        name, left = ("OT" if n == 1 else f"OT{n}"), 2 * HALF + n * OT - t
    return f"{name} {int(left // 60)}:{int(left % 60):02d}"
