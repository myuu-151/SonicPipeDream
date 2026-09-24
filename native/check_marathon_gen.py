"""Check zones the GAME generated (MarathonGen.lua) against the ring-check rule.

    python native/check_marathon_gen.py <dir>        (needs numpy)

Make the zones first: run the game with S2_MENU_CHOOSE=marathon and S2_GEN_DUMP=<dir> (and
S2_GEN_ZONES=<n>, S2_GEN_RUNS=<m>): it builds zones 1..n of m runs and writes each as
gen_<run>_<zone>.json. For every section this solves the best clean line (ring_solver.py, the
"real" player) and reports what the check asks as a share of it -- the rule is at most
TAKEABLE_SHARE. The game cannot run the solver; it sizes a section by the takeable rings of its
modules added up, times MarathonGen.SAFETY, and this is what SAFETY is set from.
"""

import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ring_solver as rs                  # noqa: E402


def main():
    folder = sys.argv[1]
    files = sorted(glob.glob(os.path.join(folder, "gen_*.json")),
                   key=lambda p: tuple(int(x) for x in re.findall(r"\d+", os.path.basename(p))))
    worst, broken, n = 0.0, 0, 0
    for path in files:
        zone = json.load(open(path))
        prev = None
        for k, sec in enumerate(zone["sections"]):
            f0 = sec["first_frame"] if prev is None else min(sec["first_frame"], prev + rs.THUMBS_TIME * rs.SPEED)
            best = rs.best_line([tuple(o) for o in sec["objects"]], f0, sec["check_frame"]) or 0
            share = sec["asks"] / float(best) if best else 9.0
            n += 1
            worst = max(worst, share)
            bad = share > rs.TAKEABLE_SHARE + 1e-9
            broken += bad
            print("%-16s section %d  diff %5.2f  asks %3d  takeable %3d  best %3d  -> asks %3.0f%% of best%s"
                  % (os.path.basename(path), k + 1, sec["difficulty"], sec["asks"], sec["takeable"], best,
                     100 * share, "   BREAKS THE RULE" if bad else ""), flush=True)
            prev = sec["check_frame"]
    print("\n%d sections, %d break the rule; the highest ask is %.0f%% of its best line" % (n, broken, 100 * worst))


if __name__ == "__main__":
    main()
