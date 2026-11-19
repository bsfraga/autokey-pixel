"""Entry point."""

from __future__ import annotations

import sys

from .core import win32


def main() -> int:
    # Must happen before Qt (or any DPI-aware library) is imported/initialised,
    # otherwise cursor coordinates and pixel colors are wrong on scaled displays.
    win32.set_dpi_awareness()

    from PySide6.QtWidgets import QApplication  # noqa: PLC0415

    from .ui.main_window import MainWindow  # noqa: PLC0415

    app = QApplication(sys.argv)
    app.setApplicationName("AutoKey Pixel")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
