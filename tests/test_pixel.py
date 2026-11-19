from datetime import datetime

from autokey_pixel.core.pixel import PixelSample


def test_sample_formatting():
    s = PixelSample(1284, 562, 212, 48, 37, datetime(2026, 1, 1, 14, 32, 7))
    assert s.hex == "#D43025"
    assert s.rgb == "(212, 48, 37)"
    assert s.summary() == "#D43025  (1284, 562)  14:32:07"
