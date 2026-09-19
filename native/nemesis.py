"""Nemesis decompressor (Sega Mega Drive), enough to read the special stage
layouts. Output is a stream of nibbles, 64 per 'tile', so 32 bytes a tile."""
import sys

def decompress(data):
    header = (data[0] << 8) | data[1]
    xor_mode = bool(header & 0x8000)
    total_nibbles = (header & 0x7FFF) * 64
    pos = 2

    # code table: (code, length) -> (nibble, run)
    table = {}
    nibble = 0
    b = data[pos]; pos += 1
    while b != 0xFF:
        if b & 0x80:
            nibble = b & 0x0F
            b = data[pos]; pos += 1
        length = b & 0x0F
        run = ((b >> 4) & 0x07) + 1
        code = data[pos]; pos += 1
        table[(code, length)] = (nibble, run)
        b = data[pos]; pos += 1

    bits = []
    for byte in data[pos:]:
        for k in range(7, -1, -1):
            bits.append((byte >> k) & 1)

    out = []
    i = 0
    while len(out) < total_nibbles:
        code, length = 0, 0
        while True:
            code = (code << 1) | bits[i]; i += 1; length += 1
            if length == 6 and code == 0x3F:          # inline: 3 bits run, 4 bits nibble
                run = (bits[i] << 2 | bits[i + 1] << 1 | bits[i + 2]) + 1
                nib = bits[i + 3] << 3 | bits[i + 4] << 2 | bits[i + 5] << 1 | bits[i + 6]
                i += 7
                break
            if (code, length) in table:
                nib, run = table[(code, length)]
                break
            assert length < 9, "no code matched"
        out += [nib] * run
    out = out[:total_nibbles]

    raw = bytearray((out[k] << 4) | out[k + 1] for k in range(0, len(out), 2))
    if xor_mode:
        for k in range(4, len(raw)):
            raw[k] ^= raw[k - 4]
    return bytes(raw)

if __name__ == "__main__":
    raw = decompress(open(sys.argv[1], "rb").read())
    open(sys.argv[2], "wb").write(raw)
    print("decompressed %d bytes" % len(raw))
