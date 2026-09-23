"""Can every stage be cleared? A solver over the stage data, not a playthrough.

    python native/solve_stages.py [stage ...]      (needs numpy; all seven by default)

For each section it finds the most rings a CLEAN line takes -- no bomb touched -- by dynamic
programming over time, Sonic's angle round the pipe and his steering speed, with the game's own
numbers (SpecialStage.lua): forward at SPEED, steering up to STEER, a hit within REACH_FRAMES along
and REACH_ANGLE round. Rings carry over from section to section, and each check's quota is the
running total, so a check passes if the best clean totals so far add up to its quota.

The model errs on the HARD side wherever it is unsure, so a pass here is a real pass:
  - steering only up to STEER (the wound-up STEER_MAX is left out), and it takes time to change
    (STEER_ACCEL here, below the game's grip at full tilt)
  - jumps: three lengths only (a full jump, and two cut short by the drop dash), from near the
    floor, and nothing is taken or hit while he is high enough off the pipe; no bounces
  - a ring counts only if he is within reach at the instant he passes its frame
It errs the other way in one place: standing still on a wall is allowed (in the game he slides).
Stopping on the overhang is not (he falls off it).

Also listed: the rings no clean line can take in each section, where there are any.
"""

import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "proj", "Scripts")

# SpecialStage.lua
SPEED = 15.0            # frames a second
STEER = 150.0           # 256ths a second
REACH_FRAMES = 0.55
REACH_ANGLE = 11.0
FALL_ANGLE = 64.0
THUMBS_TIME = 2.8       # seconds of no control after a check is passed

DT = 1.0 / 30.0
BINS = 512              # half-256ths round the pipe
BIN = 256.0 / BINS
SPEED_STEP = BIN / DT   # 15 256ths a second: one bin a step
K = int(STEER / SPEED_STEP)                     # speeds -K..K
STEER_ACCEL = 900.0     # 256ths a second a second
DK = int(round(STEER_ACCEL * DT / SPEED_STEP))  # speed steps per time step
REACH_BINS = int(REACH_ANGLE / BIN)
# jumps: (steps in the air, first safe step, last safe step)
JUMPS = [(26, 3, 24), (18, 3, 16), (14, 3, 12)]  # full (0.87 s); drop dashed at about 0.35 and 0.25 s
JUMP_FROM = 48.0        # only from within this of the floor's centre line

# SOLVER_GENEROUS=1: the other extreme -- the wound-up STEER_MAX at once, a much quicker turn,
# jumps from anywhere round the pipe. A check that fails even so cannot be passed at all.
if os.environ.get("SOLVER_GENEROUS"):
    STEER, STEER_ACCEL, JUMP_FROM = 320.0, 2700.0, 128.0
    K = int(STEER / SPEED_STEP)
    DK = int(round(STEER_ACCEL * DT / SPEED_STEP))

# SOLVER_HITS=1: a bomb may be hit, at its cost (BOMB_COST rings; the stumble after it is left out),
# in case a hit opens the way to more than it takes.
HITS = bool(os.environ.get("SOLVER_HITS"))
BOMB_COST = 10

NEG = -1e9


def read_stage(n):
    s = open(os.path.join(SCRIPTS, "StageData%d.lua" % n), encoding="utf-8").read()
    body = s[s.index("sections = {"):]
    sections = []
    for m in re.finditer(r"first_frame = ([\d.]+),\s*check_frame = ([\d.]+),\s*last_frame = ([\d.]+),\s*"
                         r"quota = (\d+),\s*asks = (\d+),\s*rings = (\d+),\s*leads_to = \"([^\"]*)\",\s*"
                         r"objects = \{(.*?)\n      \}", body, re.S):
        objs = [(float(a), float(b), int(c)) for a, b, c in re.findall(r"\{(-?[\d.]+),(-?[\d.]+),([01])\}", m.group(8))]
        sections.append(dict(first=float(m.group(1)), check=float(m.group(2)), quota=int(m.group(4)),
                             asks=int(m.group(5)), rings=int(m.group(6)), leads=m.group(7), objects=objs))
    return sections


def bin_of(angle):
    return int(round(angle / BIN)) % BINS


def circ_dist(a, b):
    d = abs(a - b) % BINS
    return min(d, BINS - d)


def solve_section(sec, start=None):
    # control comes back THUMBS_TIME after the last check, which can be a little before the section
    f0, f1 = (sec["first"] if start is None else start), sec["check"]
    steps = int((f1 - f0) / (SPEED * DT)) + 1
    frame = f0 + np.arange(steps + 1) * SPEED * DT
    ring_val = np.zeros((steps + 1, BINS), np.float32)
    bomb = np.zeros((steps + 1, BINS), bool)
    bomb_cost = np.zeros((steps + 1, BINS), np.float32)
    near = np.array([[circ_dist(b, c) <= REACH_BINS for c in range(BINS)] for b in range(BINS)])
    rings = []
    for f, a, kind in sec["objects"]:
        if f < f0 or f > f1:
            continue
        b = bin_of(a)
        if kind == 0:
            s = int(round((f - f0) / (SPEED * DT)))
            if 0 <= s <= steps:
                ring_val[s] += near[b]
                rings.append((f, a, s, b))
        else:
            for s in np.nonzero(np.abs(frame - f) <= REACH_FRAMES)[0]:
                bomb[s] |= near[b]
            s = int(round((f - f0) / (SPEED * DT)))
            if 0 <= s <= steps:
                bomb_cost[s] += near[b] * BOMB_COST
    ceiling = np.array([abs(((c * BIN + 128) % 256) - 128) > FALL_ANGLE for c in range(BINS)])
    floorish = np.array([abs(((c * BIN + 128) % 256) - 128) <= JUMP_FROM for c in range(BINS)])
    speeds = np.arange(-K, K + 1)

    V = np.full((steps + 1, 2 * K + 1, BINS), NEG, np.float32)
    V[0, K, bin_of(0.0)] = 0.0
    for s in range(steps):
        cur = V[s]
        if cur.max() <= NEG / 2:
            continue
        # on the ground: change speed by up to DK steps, then move
        best = np.full_like(cur, NEG)
        for dk in range(-DK, DK + 1):
            shifted = np.full_like(cur, NEG)
            if dk >= 0:
                shifted[dk:] = cur[:2 * K + 1 - dk] if dk else cur
            else:
                shifted[:dk] = cur[-dk:]
            best = np.maximum(best, shifted)
        for i, k in enumerate(speeds):
            row = np.roll(best[i], k) + ring_val[s + 1]
            if HITS:
                row -= bomb_cost[s + 1]
            else:
                row[bomb[s + 1]] = NEG
            if k == 0:
                row[ceiling] = NEG
            V[s + 1, i] = np.maximum(V[s + 1, i], row)
        # jumps, from near the floor
        for dur, safe0, safe1 in JUMPS:
            if s + dur > steps:
                continue
            for i, k in enumerate(speeds):
                row = np.where(floorish, cur[i], NEG).astype(np.float32)
                if row.max() <= NEG / 2:
                    continue
                ok = row.copy()
                for t in range(1, dur + 1):
                    ok = np.roll(ok, k)
                    if t < safe0 or t > safe1:          # low enough to take and to be hit
                        ok = ok + ring_val[s + t]
                        if HITS:
                            ok -= bomb_cost[s + t]
                        else:
                            ok[bomb[s + t]] = NEG
                V[s + dur, i] = np.maximum(V[s + dur, i], ok)
    best_end = float(V[steps].max())
    # which rings no clean line reaches: a ring is reachable if some clean state sits on it
    reachable = []
    for f, a, s, b in rings:
        cols = near[b]
        reachable.append(bool((V[s][:, cols] > NEG / 2).any()))
    missed = [(f, a) for (f, a, s, b), r in zip(rings, reachable) if not r]
    return int(round(best_end)) if best_end > NEG / 2 else None, len(rings), missed


def main():
    stages = [int(a) for a in sys.argv[1:]] or list(range(1, 8))
    for n in stages:
        secs = read_stage(n)
        total = 0
        print("STAGE %d" % n)
        for i, sec in enumerate(secs):
            start = None if i == 0 else min(sec["first"], secs[i - 1]["check"] + THUMBS_TIME * SPEED)
            got, count, missed = solve_section(sec, start)
            total += got or 0
            ok = got is not None and total >= sec["quota"]
            print("  section %d: best clean line %s of %d rings; running total %d, check needs %d -> %s (spare %d)"
                  % (i + 1, got, count, total, sec["quota"], "PASS" if ok else "FAIL", total - sec["quota"]))
            if missed:
                print("    no clean line reaches %d ring(s): %s" % (len(missed), ", ".join(
                    "frame %.0f angle %.0f" % m for m in missed[:12]) + (" ..." if len(missed) > 12 else "")))
        sys.stdout.flush()


if __name__ == "__main__":
    main()
