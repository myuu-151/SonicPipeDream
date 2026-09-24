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
    ("stage1.wav", "SW_SpecialStage_Stage1", 0x51C0FFEE00300003),      # stage 1's own (SpecialStageMusic.lua)
    ("stage2_open.wav", "SW_SpecialStage_Stage2Intro", 0x51C0FFEE00300004),  # stage 2's: this once,
    ("stage2_loop.wav", "SW_SpecialStage_Stage2Loop", 0x51C0FFEE00300005),   # then this for ever
    ("ssr_intro.wav", "SW_SpecialStage_SSRIntro", 0x51C0FFEE00300006),        # stage 3's: once,
    ("ssr_loop.wav", "SW_SpecialStage_SSRLoop", 0x51C0FFEE00300007),          # then this
    ("stage4_intro.wav", "SW_SpecialStage_Stage4Intro", 0x51C0FFEE00300008),  # the stage 4 track (stage 5 plays it)
    ("stage4_loop.wav", "SW_SpecialStage_Stage4Loop", 0x51C0FFEE00300009),
    ("stage5full.wav", "SW_SpecialStage_Stage5", 0x51C0FFEE0030000A),         # the stage 5 track, whole (stage 6)
    ("stage7_intro.wav", "SW_SpecialStage_Stage7Intro", 0x51C0FFEE0030000B),
    ("stage7_loop.wav", "SW_SpecialStage_Stage7Loop", 0x51C0FFEE0030000C),
    ("menuintro.wav", "SW_SpecialStage_MenuIntro", 0x51C0FFEE0030000D),        # the menus': once,
    ("menuloop.wav", "SW_SpecialStage_MenuLoop", 0x51C0FFEE0030000E),          # then this
]


# The effects. OGG as well as WAV, so these are read with soundfile (pip install soundfile),
# which the two music tracks above do not need.
EFFECTS = [
    ("Ring.wav", "SW_Ring", 0x51C0FFEE00300010),
    ("LoseRings.ogg", "SW_LoseRings", 0x51C0FFEE00300011),
    ("Jump.ogg", "SW_Jump", 0x51C0FFEE00300012),
    ("Checkpoint.wav", "SW_Checkpoint", 0x51C0FFEE00300013),
    ("Get_Emerald.wav", "SW_GetEmerald", 0x51C0FFEE00300014),
    ("Continue.ogg", "SW_Continue", 0x51C0FFEE00300015),
    ("SE_Goalring.wav", "SW_Goalring", 0x51C0FFEE00300016),
    ("SE_Item_Appear.wav", "SW_ItemAppear", 0x51C0FFEE00300017),
    ("SE_Rainbow.wav", "SW_Rainbow", 0x51C0FFEE00300018),
    ("Fail.wav", "SW_Fail", 0x51C0FFEE00300019),
    ("Explosion2.wav", "SW_Explosion", 0x51C0FFEE0030001A),
    ("Exit_SS.wav", "SW_ExitStage", 0x51C0FFEE0030001B),
    ("MenuButton.ogg", "SW_MenuMove", 0x51C0FFEE0030001C),      # the menus: the highlight moving,
    ("Select.ogg", "SW_MenuSelect", 0x51C0FFEE0030001E),        # a menu going on to the next (and pausing),
    ("SpecialWarp.ogg", "SW_MenuWarp", 0x51C0FFEE0030001D),     # and a stage chosen (and left),
    ("back.wav", "SW_MenuBack", 0x51C0FFEE0030001F),            # and B, back out of a menu
]


NORMALISE = {"SW_GetEmerald": 0.97}     # asset -> the peak to bring it up to (the file peaks at 0.51)


def write(asset, uuid, channels, width, rate, frames, pcm):
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


def main():
    os.makedirs(OUT, exist_ok=True)
    for wav_name, asset, uuid in TRACKS:
        w = wave.open(os.path.join(SRC, wav_name), "rb")
        channels, width, rate, frames = (w.getnchannels(), w.getsampwidth(),
                                         w.getframerate(), w.getnframes())
        pcm = w.readframes(frames)
        w.close()
        write(asset, uuid, channels, width, rate, frames, pcm)

    import soundfile
    for file_name, asset, uuid in EFFECTS:
        data, rate = soundfile.read(os.path.join(SRC, file_name), dtype="int16", always_2d=True)
        if asset in NORMALISE:
            # a quiet file, already played at full volume in the game: bring its peak up here
            import numpy
            gain = NORMALISE[asset] * 32767.0 / max(1, int(numpy.abs(data.astype(numpy.int32)).max()))
            data = numpy.clip(data.astype(numpy.float64) * gain, -32768, 32767).astype(numpy.int16)
        write(asset, uuid, data.shape[1], 2, rate, data.shape[0], data.tobytes())


if __name__ == "__main__":
    main()
