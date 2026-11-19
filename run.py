"""Launcher used by PyInstaller and for `python run.py`."""

import sys

from autokey_pixel.main import main

if __name__ == "__main__":
    sys.exit(main())
