#!/usr/bin/env python
"""Import the special stage music into the Octave project as SoundWave assets.

    python native/gen_music_assets.py

Writes proj/Assets/Sounds/SW_SpecialStage_Intro.oct and SW_SpecialStage_Loop.oct from
the WAVs in external/audio/, in the same layout the editor's own importer writes
(Engine/Source/Engine/Assets/SoundWave.cpp, LoadStream), so nothing has to be clicked
through an import dialog and the assets can be regenerated when the WAVs change.

Stored as plain PCM: uncompressed, not streamed. That is the simple, exact choice on
Windows, where 23MB of audio in memory is nothing. The compress and stream flags exist
for the GameCube, which has neither the RAM nor, without them, the patience.
"""

import os
import struct
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "external", "audio")
OUT = os.path.join(HERE, "..", "proj", "Assets", "Sounds")

MAGIC = 0x4F435421
VERSION = 14                        # ASSET_VERSION_SOUND_STREAM: the stream flag is present
TYPE_SOUNDWAVE = 0x9A6A5AC0         # read from an asset the editor wrote

TRACKS = [
    # wav, asset name, uuid
    ("ss_intro.wav", "SW_SpecialStage_Intro", 0x51C0FFEE00300001),
    ("ss_loop.wav", "SW_SpecialStage_Loop", 0x51C0FFEE00300002),
]


def main():
    os.makedirs(OUT, exist_ok=True)
    for wav_name, asset, uuid in TRACKS:
        w = wave.open(os.path.join(SRC, wav_name), "rb")
        channels, width, rate, frames = (w.getnchannels(), w.getsampwidth(),
                                         w.getframerate(), w.getnframes())
        pcm = w.readframes(frames)
        w.close()

        name = asset.encode("ascii")
        d = struct.pack("<IIIB", MAGIC, VERSION, TYPE_SOUNDWAVE, 0)
        d += struct.pack("<Q", uuid) + struct.pack("<I", len(name)) + name
        d += struct.pack("<ff", 1.0, 1.0)            # volume, pitch multipliers
        d += struct.pack("<b", 0)                    # audio class
        d += struct.pack("<???", False, False, False)  # compress, compress internal, stream
        block = channels * width
        d += struct.pack("<IIIIII", channels, width * 8, rate, frames, block, rate * block)
        d += struct.pack("<?", False)                # not compressed: raw PCM follows
        d += struct.pack("<I", len(pcm)) + pcm

        with open(os.path.join(OUT, asset + ".oct"), "wb") as f:
            f.write(d)
        print("%-24s %d Hz, %d ch, %d-bit, %.2f s, %.1f MB"
              % (asset, rate, channels, width * 8, frames / float(rate), len(d) / 1048576.0))


if __name__ == "__main__":
    main()
