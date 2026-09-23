"""Can every stage be cleared? A solver over the stage data, not a playthrough.

    python native/solve_stages.py [stage ...]      (needs numpy; all seven by default)
        SOLVER_MODEL=strict|real|generous          (default real; see ring_solver.py)

For each section, the most rings a CLEAN line takes -- no bomb touched -- with the game's own
steering and reach (native/ring_solver.py). Rings carry over from section to section and each
check's quota is the running total, so a check passes if the best lines so far add up to it.
Also listed: the rings no clean line can touch, where there are any.

The checks themselves are held to what a line can take when a stage is made and exported
(gen_stage.py and export_to_octave.py, TAKEABLE_SHARE); this is the check on that.
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ring_solver as rs                      # noqa: E402

SCRIPTS = os.path.join(HERE, "..", "proj", "Scripts")


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


def main():
    model = os.environ.get("SOLVER_MODEL", "real")
    stages = [int(a) for a in sys.argv[1:]] or list(range(1, 8))
    for n in stages:
        secs = read_stage(n)
        total = 0
        print("STAGE %d  (%s)" % (n, model))
        for i, sec in enumerate(secs):
            f0 = sec["first"] if i == 0 else min(sec["first"], secs[i - 1]["check"] + rs.THUMBS_TIME * rs.SPEED)
            got, missed = rs.best_line(sec["objects"], f0, sec["check"], model=model, want_reach=True)
            count = sum(1 for o in sec["objects"] if o[2] == 0 and f0 <= o[0] <= sec["check"])
            total += got or 0
            ok = got is not None and total >= sec["quota"]
            print("  section %d: best clean line %s of %d rings, asks %d; running total %d, check needs %d -> %s (spare %d)"
                  % (i + 1, got, count, sec["asks"], total, sec["quota"], "PASS" if ok else "FAIL", total - sec["quota"]))
            if missed:
                print("    no clean line touches %d ring(s): %s" % (len(missed), ", ".join(
                    "frame %.0f angle %.0f" % m for m in missed[:12]) + (" ..." if len(missed) > 12 else "")))
        sys.stdout.flush()


if __name__ == "__main__":
    main()
