#!/usr/bin/python3
"""Build the tray icon set from the white Claude mark in icons/claude.png.

claude.png is the source of truth; the warn/crit variants are tints of it with
the alpha channel preserved. Re-run after replacing claude.png or changing the
colours below.
"""

import os
import sys

import gi

gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf  # noqa: E402

ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")
SOURCE = os.path.join(ICON_DIR, "claude.png")

# The icon is the only pressure cue a tray item has — its text label cannot be
# coloured. Set both to (255, 255, 255) to keep the mark white at all times.
TINTS = {
    "claude-warn": (240, 180, 41),
    "claude-crit": (240, 82, 82),
}


def tint(pixbuf, rgb):
    """Recolour opaque pixels, keeping per-pixel alpha so edges stay smooth."""
    out = pixbuf.copy()
    pixels = bytearray(out.get_pixels())
    stride, channels = out.get_rowstride(), out.get_n_channels()
    if channels != 4:
        raise SystemExit(f"{SOURCE}: expected RGBA, got {channels} channels")

    for y in range(out.get_height()):
        row = y * stride
        for x in range(out.get_width()):
            off = row + x * channels
            if pixels[off + 3]:
                pixels[off], pixels[off + 1], pixels[off + 2] = rgb

    return GdkPixbuf.Pixbuf.new_from_bytes(
        __import__("gi").repository.GLib.Bytes.new(bytes(pixels)),
        out.get_colorspace(), True, 8,
        out.get_width(), out.get_height(), stride,
    )


def main():
    if not os.path.exists(SOURCE):
        sys.exit(f"missing {SOURCE}")

    src = GdkPixbuf.Pixbuf.new_from_file(SOURCE)
    if not src.get_has_alpha():
        src = src.add_alpha(False, 0, 0, 0)
    print(f"source {SOURCE}: {src.get_width()}x{src.get_height()}")

    for name, rgb in TINTS.items():
        path = os.path.join(ICON_DIR, f"{name}.png")
        tint(src, rgb).savev(path, "png", [], [])
        print("wrote", path)


if __name__ == "__main__":
    main()
