"""How many rings can a line take? The solver shared by the stage generator, the exporter and
native/solve_stages.py.

    best_line(objects, f0, f1, start="floor", model="real")  ->  the most rings

objects are (frame, angle, kind) with kind 0 a ring and 1 a bomb (or "ring" / "bomb"), angle in
256ths from the floor's centre line. It is dynamic programming over time, Sonic's angle round the
pipe and his steering speed, with the game's own numbers (SpecialStage.lua): forward at SPEED, a
hit within REACH_FRAMES along and REACH_ANGLE round, no bomb touched (a CLEAN line).

Models of the player, from hard to kind:
  "strict"    steering up to STEER only; jumps from near the floor
  "real"      as the game: past STEER the wind-up builds to STEER_MAX at about STEER_BUILD
  "generous"  STEER_MAX at once, a much quicker turn, jumps from anywhere round the pipe
Every model: speed takes time to change; three jump lengths (a full jump and two cut short by the
drop dash), and nothing is taken or hit while he is high enough off the pipe; no bounces; a ring
counts only if he is within reach at the instant he passes its frame. Standing still on a wall is
allowed (in the game he slides); stopping on the overhang is not (he falls off it).

start="floor": he begins on the floor's centre line, standing (a stage's start, or after a check's
thumbs-up); start="any": anywhere, at any speed (a module on its own, whatever came before it).
"""

import numpy as np

# SpecialStage.lua
SPEED = 15.0            # frames a second
STEER = 150.0           # 256ths a second
STEER_MAX = 320.0
STEER_BUILD = 160.0     # 256ths a second a second, past STEER
REACH_FRAMES = 0.55
REACH_ANGLE = 11.0
FALL_ANGLE = 64.0
THUMBS_TIME = 2.8       # seconds of no control after a check is passed

# THE RULE, everywhere a check is set (gen_stage.py when a stage is made, export_to_octave.py
# when one is written for the game): a check never asks for more than this share of the rings
# the best clean line through its section takes, with the "real" player. 0.9 is very hard --
# a tenth of the best line to spare, or a bomb and a few rings -- and never impossible.
TAKEABLE_SHARE = 0.9


def ask_cap(best):
    """The most a check may ask of a section whose best line takes `best` rings: the share of
    it, down to a multiple of five (checks ask in fives)."""
    return int(best * TAKEABLE_SHARE // 5) * 5

DT = 1.0 / 30.0
BINS = 512              # half-256ths round the pipe
BIN = 256.0 / BINS
SPEED_STEP = BIN / DT   # 15 256ths a second: one bin a step
REACH_BINS = int(REACH_ANGLE / BIN)
# jumps: (steps in the air, first safe step, last safe step)
JUMPS = [(26, 3, 24), (18, 3, 16), (14, 3, 12)]  # full (0.87 s); drop dashed at about 0.35 and 0.25 s

MODELS = {
    #            top speed  turn (256ths/s/s)  jumps from within
    "strict":   (STEER,     900.0,             48.0),
    "real":     (STEER_MAX, 900.0,             48.0),
    "generous": (STEER_MAX, 2700.0,            128.0),
}

NEG = np.float32(-1e9)
_NEAR = None


def _near():
    global _NEAR
    if _NEAR is None:
        idx = np.arange(BINS)
        d = np.abs(idx[:, None] - idx[None, :]) % BINS
        _NEAR = np.minimum(d, BINS - d) <= REACH_BINS
    return _NEAR


def bin_of(angle):
    return int(round(angle / BIN)) % BINS


def _signed(b):
    return ((b * BIN + 128.0) % 256.0) - 128.0


def best_line(objects, f0, f1, start="floor", model="real", want_reach=False):
    """The most rings a clean line takes between frames f0 and f1 (None: no clean line gets
    through). want_reach: also the rings (frame, angle) no clean line can touch."""
    top, turn, jump_from = MODELS[model]
    K = int(round(top / SPEED_STEP))
    KS = int(round(STEER / SPEED_STEP))           # past this, speed builds slowly (the wind-up)
    DK = max(1, int(round(turn * DT / SPEED_STEP)))
    build_every = max(1, int(round(SPEED_STEP / (STEER_BUILD * DT))))   # steps per wind-up speed step
    near = _near()
    steps = max(1, int((f1 - f0) / (SPEED * DT)) + 1)
    frame = f0 + np.arange(steps + 1) * SPEED * DT
    ring_val = np.zeros((steps + 1, BINS), np.float32)
    bomb = np.zeros((steps + 1, BINS), bool)
    rings = []
    for f, a, kind in objects:
        is_bomb = kind in (1, "bomb")
        if f < f0 - REACH_FRAMES or f > f1 + REACH_FRAMES:
            continue
        b = bin_of(a)
        if not is_bomb:
            s = int(round((f - f0) / (SPEED * DT)))
            if 0 <= s <= steps:
                ring_val[s] += near[b]
                rings.append((f, a, s, b))
        else:
            for s in np.nonzero(np.abs(frame - f) <= REACH_FRAMES)[0]:
                bomb[s] |= near[b]

    angles = np.array([_signed(c) for c in range(BINS)])
    ceiling = np.abs(angles) > FALL_ANGLE
    floorish = np.abs(angles) <= jump_from
    speeds = np.arange(-K, K + 1)
    S = len(speeds)
    move_idx = (np.arange(BINS)[None, :] - speeds[:, None]) % BINS      # where each speed comes from
    fast = np.abs(speeds) > KS

    V = np.full((steps + 1, S, BINS), NEG, np.float32)
    if start == "any":
        V[0] = 0.0
        V[0][(speeds == 0)[:, None] & ceiling[None, :]] = NEG
    else:
        V[0, K, bin_of(0.0)] = 0.0
    for s in range(steps):
        cur = V[s]
        if cur.max() <= NEG / 2:
            continue
        # speed: up to DK steps a time step up to STEER; past it, one step every build_every
        best = cur.copy()
        for dk in range(1, DK + 1):
            up = np.full_like(cur, NEG)
            up[dk:] = cur[:-dk]                 # speeding up to the right (k grows)
            down = np.full_like(cur, NEG)
            down[:-dk] = cur[dk:]
            # into the wind-up range, only one step, and only on a build step
            gate_up = (speeds > KS) & ((dk > 1) | (s % build_every != 0))
            gate_down = (speeds < -KS) & ((dk > 1) | (s % build_every != 0))
            up[gate_up] = NEG
            down[gate_down] = NEG
            best = np.maximum(best, np.maximum(up, down))
        moved = np.take_along_axis(best, move_idx, axis=1) + ring_val[s + 1][None, :]
        moved[:, bomb[s + 1]] = NEG
        moved[(speeds == 0)[:, None] & ceiling[None, :]] = NEG
        np.maximum(V[s + 1], moved, out=V[s + 1])
        # jumps, from near the floor, at the speed he has (carried sideways)
        launch = np.where(floorish[None, :], cur, NEG)
        if launch.max() <= NEG / 2:
            continue
        for dur, safe0, safe1 in JUMPS:
            if s + dur > steps:
                continue
            ok = launch
            for t in range(1, dur + 1):
                ok = np.take_along_axis(ok, move_idx, axis=1)
                if t < safe0 or t > safe1:          # low enough to take and to be hit
                    ok = ok + ring_val[s + t][None, :]
                    ok[:, bomb[s + t]] = NEG
            np.maximum(V[s + dur], ok, out=V[s + dur])
    end = float(V[steps].max())
    got = int(round(end)) if end > NEG / 2 else None
    if not want_reach:
        return got
    missed = [(f, a) for f, a, s, b in rings if not (V[s][:, near[b]] > NEG / 2).any()]
    return got, missed


def section_best(sec, prev_check=None, model="real"):
    """The best clean line through one section of a stage's data (dict with first/check frames
    and objects). Control comes back THUMBS_TIME after the last check, which can be a little
    before the section's first frame."""
    f0 = sec["first"] if prev_check is None else min(sec["first"], prev_check + THUMBS_TIME * SPEED)
    return best_line(sec["objects"], f0, sec["check"], start="floor", model=model)
