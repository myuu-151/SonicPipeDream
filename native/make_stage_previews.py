"""Photograph each stage for the stage-select screen.

    python native/make_stage_previews.py            (needs Pillow; Windows)

    -> external/ui/menu/parts/preview_stage<n>.png  one picture a stage, 165 x 143

This is the one script here that RUNS THE GAME. A stage's preview ought to be the stage --
its own pipe colours under its own sky -- and the truest way to get that is to start it and
take a photograph. It launches the Windows build seven times with S2_STAGE=<n> and S2_NOMENU
set, waits for Sonic to be a little way in, grabs the window, and crops out the HUD.

The mockup's preview is 165 x 143 (parts/preview_picture.png), so these are cut to that
shape and size, from the middle of the window below the HUD.
"""

import os
import subprocess
import sys
import time

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
PARTS = os.path.abspath(os.path.join(HERE, "..", "external", "ui", "menu", "parts"))
PROJ = os.path.abspath(os.path.join(HERE, "..", "proj", "Sonic2Special3D.octp"))

ENGINE = os.environ.get("OCTAVE_ROOT", r"C:\Users\NoSig\Documents\octave-libogc")
EXE = os.path.join(ENGINE, "Standalone", "Build", "Windows", "x64", "Release", "Octave.exe")

SIZE = (165, 143)                   # the mockup's preview picture
SETTLE = 9.0                        # seconds before the photograph: past START, into the rings
HUD_TOP = 0.30                      # the top of the window is the HUD; crop below it


def grab_window(title="Sonic2Special3D"):
    """A picture of the game's window, without giving it focus and without catching
    whatever else is on screen.

    Not ImageGrab: that photographs the SCREEN at the window's coordinates, so anything
    sitting on top of the game lands in the picture -- one of these came back showing another
    application's notification. PrintWindow asks the window to draw itself instead.
    """
    import ctypes
    from ctypes import wintypes
    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    hwnd = user32.FindWindowW(None, title)
    if not hwnd:
        return None

    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w, h = rect.right - rect.left, rect.bottom - rect.top

    dc = user32.GetWindowDC(hwnd)
    mem = gdi32.CreateCompatibleDC(dc)
    bmp = gdi32.CreateCompatibleBitmap(dc, w, h)
    gdi32.SelectObject(mem, bmp)
    PW_RENDERFULLCONTENT = 2
    user32.PrintWindow(hwnd, mem, PW_RENDERFULLCONTENT)

    class BMI(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", ctypes.c_long),
                    ("biHeight", ctypes.c_long), ("biPlanes", wintypes.WORD),
                    ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", ctypes.c_long),
                    ("biYPelsPerMeter", ctypes.c_long), ("biClrUsed", wintypes.DWORD),
                    ("biClrImportant", wintypes.DWORD)]

    info = BMI()
    info.biSize = ctypes.sizeof(BMI)
    info.biWidth, info.biHeight = w, -h        # negative: top-down rows
    info.biPlanes, info.biBitCount = 1, 32
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(info), 0)

    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mem)
    user32.ReleaseDC(hwnd, dc)
    return Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB")


def shoot(stage):
    env = dict(os.environ, S2_STAGE=str(stage), S2_NOMENU="1")
    # The working directory MUST be the engine root: the runtime loads its shaders from the
    # relative path Engine/Shaders/GLSL/bin, and started anywhere else it dies without a word.
    game = subprocess.Popen([EXE, "-project", PROJ], env=env, cwd=ENGINE)
    try:
        time.sleep(SETTLE)
        if game.poll() is not None:
            raise RuntimeError("the game exited (%s) before stage %d could be photographed"
                               % (game.returncode, stage))
        shot = grab_window()
        if shot is None:
            raise RuntimeError("no window for stage %d" % stage)
    finally:
        game.terminate()
        game.wait(timeout=10)

    # below the HUD, centred, cut to the preview's shape
    w, h = shot.size
    top = int(h * HUD_TOP)
    usable = (w, h - top)
    want = SIZE[0] / float(SIZE[1])
    cw, ch = (int(usable[1] * want), usable[1]) if usable[0] / float(usable[1]) > want \
        else (usable[0], int(usable[0] / want))
    left = (w - cw) // 2
    return shot.crop((left, top, left + cw, top + ch)).resize(SIZE, Image.LANCZOS)


def main():
    if not os.path.exists(EXE):
        sys.exit("no Windows build at %s (build Standalone Release first)" % EXE)
    for stage in range(1, 8):
        out = os.path.join(PARTS, "preview_stage%d.png" % stage)
        shoot(stage).convert("RGBA").save(out)
        print("wrote %s" % os.path.basename(out))


if __name__ == "__main__":
    main()
