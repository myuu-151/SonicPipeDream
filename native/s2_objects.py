"""Read the original special stages' rings and bombs, and draw them as maps.

    python native/s2_objects.py [stage 1-7]      # no stage: a summary of all seven

Format and findings: docs/s2-special-stage-objects.md. Each map row is one track
frame of a segment; across is the angle round the pipe, $40 the floor's centre line.
    o ring   X bomb
"""

import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kosinski import decompress

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "docs", "reference", "Special stage object location lists.kos")

MARKS = {0xFF: "", 0xFE: "checkpoint", 0xFD: "emerald", 0xFC: "rings-to-go message"}


def stages():
    """[[(objects, end byte), ...] per stage]; an object is (frame, angle, is_bomb)."""
    d = decompress(open(SRC, "rb").read())
    offs = struct.unpack(">7H", d[:14])
    out = []
    for p in offs:
        segs = []
        while True:
            objs = []
            while d[p] < 0x80:
                objs.append((d[p] & 0x3F, d[p + 1], bool(d[p] & 0x40)))
                p += 2
            segs.append((objs, d[p]))
            p += 1
            if segs[-1][1] == 0xFD:           # the emerald: nothing is read after it
                break
        out.append(segs)
    return out


def draw(segs):
    for i, (objs, end) in enumerate(segs):
        print("seg %2d  %2d objects  %s" % (i, len(objs), MARKS.get(end, hex(end))))
        rows = {}
        for frame, angle, bomb in objs:
            rows.setdefault(frame, {})[angle] = "X" if bomb else "o"
        for frame in sorted(rows):
            line = [" "] * 64
            for angle, c in rows[frame].items():
                line[angle // 4] = c
            print("   %2d |%s|  %s" % (frame, "".join(line),
                                       " ".join("%02X" % a for a in sorted(rows[frame]))))


if __name__ == "__main__":
    all_stages = stages()
    if len(sys.argv) > 1:
        draw(all_stages[int(sys.argv[1]) - 1])
    else:
        for n, segs in enumerate(all_stages, 1):
            objs = [o for seg, _ in segs for o in seg]
            print("stage %d: %2d segments, %3d rings, %3d bombs" % (
                n, len(segs), sum(not o[2] for o in objs), sum(o[2] for o in objs)))
