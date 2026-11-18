#!/usr/bin/env python3
"""make.fun news-image entry.

Copies the checked-in image (entry.png, beside this file) to the output path.
Standard library only. No network.
"""

import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, "entry.png")

DEFAULT_OUTPUT = "/output/entry.png"


def main():
    dest = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_OUTPUT

    parent = os.path.dirname(dest)
    if parent:
        os.makedirs(parent, exist_ok=True)

    shutil.copyfile(SOURCE, dest)

    print(dest)
    print(os.path.getsize(dest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
