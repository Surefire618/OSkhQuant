"""Chinese labels and annotations must render with the configured chart font."""

import warnings

import matplotlib
from matplotlib import font_manager
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.ft2font import FT2Font
import pytest

from khChartFonts import configure_chart_fonts


def test_chinese_chart_labels_and_annotation_render_without_missing_glyphs():
    with matplotlib.rc_context():
        configure_chart_fonts()
        families = matplotlib.rcParams["font.sans-serif"]
        path = font_manager.findfont(font_manager.FontProperties(family=families))
        charmap = FT2Font(path).get_charmap()
        text = "中文收益率成交量"
        if not all(ord(char) in charmap for char in text):
            pytest.skip("Install a Chinese font such as fonts-noto-cjk to exercise glyph rendering")
        figure = Figure()
        canvas = FigureCanvasAgg(figure)
        axes = figure.subplots()
        axes.plot([-1, 1], [-1, 1])
        axes.set_title(text)
        axes.annotate("成交量", (0, 0), fontfamily=families)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            canvas.draw()
        assert not [item for item in caught if "Glyph" in str(item.message) and "missing" in str(item.message)]


def test_absent_platform_fonts_do_not_override_installed_chinese_font(monkeypatch):
    from types import SimpleNamespace

    with matplotlib.rc_context():
        monkeypatch.setattr(font_manager.fontManager, "ttflist", [
            SimpleNamespace(name="DejaVu Sans"), SimpleNamespace(name="Noto Sans CJK SC"),
        ])
        configure_chart_fonts()
        assert matplotlib.rcParams["font.sans-serif"][0] == "Noto Sans CJK SC"
