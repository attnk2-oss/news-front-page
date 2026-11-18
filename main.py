#!/usr/bin/env python3
"""Ship the rendered front page into the sandbox's output directory.

The sandbox has no network, a read-only /bot holding this repository, and a
writable /output. This program writes the image to /output/entry.png.

The drawing happens ahead of time in tools/render.py, on a machine that has
Pillow. The sandbox does not, so this program only copies the committed PNG.
Standard library only, and the bytes written are the bytes in the repository,
which makes the output identical on every run.

Usage:
    python3 main.py [OUTPUT_PATH]

OUTPUT_PATH defaults to /output/entry.png.
"""
import os
import struct
import sys

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
IEND = b"\x00\x00\x00\x00IEND\xaeB`\x82"
DEFAULT_OUTPUT = "/output/entry.png"
EXPECTED_SIZE = (1024, 1024)
MAX_BYTES = 1048576


def _check_png(blob, source):
    """Fail loudly rather than ship a broken or oversized entry."""
    if not blob.startswith(PNG_SIGNATURE):
        raise SystemExit("%s is not a PNG" % source)
    if len(blob) < 33 or blob[12:16] != b"IHDR":
        raise SystemExit("%s has no IHDR chunk" % source)
    width, height = struct.unpack(">II", blob[16:24])
    if (width, height) != EXPECTED_SIZE:
        raise SystemExit("%s is %dx%d, expected 1024x1024" % (source, width, height))
    if not blob.rstrip().endswith(IEND):
        raise SystemExit("%s is truncated: no IEND chunk" % source)
    if len(blob) > MAX_BYTES:
        raise SystemExit("%s is %d bytes, over the 1 MiB limit" % (source, len(blob)))


def main(argv):
    output = argv[1] if len(argv) > 1 else DEFAULT_OUTPUT

    here = os.path.dirname(os.path.abspath(__file__))
    source = os.path.join(here, "entry.png")
    with open(source, "rb") as fh:
        blob = fh.read()
    _check_png(blob, source)

    parent = os.path.dirname(os.path.abspath(output))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(output, "wb") as fh:
        fh.write(blob)

    print("wrote %s (%d bytes)" % (output, len(blob)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
