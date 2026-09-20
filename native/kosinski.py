"""Kosinski decompressor, for the special stage's ring and bomb lists.

    python native/kosinski.py "docs/reference/Special stage object location lists.kos" objects.bin

The format: a 16-bit little-endian descriptor field read a bit at a time, low bit
first, refilled the moment it runs out. 1 = a literal byte; 00 = a short copy (two
count bits, one offset byte); 01 = a long copy (13-bit offset, 3-bit count, or a
whole count byte: 0 ends the stream, 1 is a no-op).
"""

import sys


def decompress(src):
    out = bytearray()
    pos = 2
    desc = src[0] | (src[1] << 8)
    bits = 16

    def getbit():
        nonlocal desc, bits, pos
        b = desc & 1
        desc >>= 1
        bits -= 1
        if bits == 0:
            desc = src[pos] | (src[pos + 1] << 8)
            pos += 2
            bits = 16
        return b

    while True:
        if getbit():
            out.append(src[pos])
            pos += 1
            continue
        if getbit():
            lo, hi = src[pos], src[pos + 1]
            pos += 2
            off = ((hi & 0xF8) << 5 | lo) - 0x2000
            cnt = hi & 7
            if cnt:
                cnt += 2
            else:
                cnt = src[pos]
                pos += 1
                if cnt == 0:
                    break
                if cnt == 1:
                    continue
                cnt += 1
        else:
            cnt = (getbit() << 1 | getbit()) + 2
            off = src[pos] - 0x100
            pos += 1
        for _ in range(cnt):
            out.append(out[len(out) + off])
    return bytes(out)


if __name__ == "__main__":
    data = decompress(open(sys.argv[1], "rb").read())
    open(sys.argv[2], "wb").write(data)
    print(len(data), "bytes")
