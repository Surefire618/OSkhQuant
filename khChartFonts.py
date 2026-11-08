"""Shared Matplotlib fonts for Windows, macOS and Linux charts."""

import matplotlib
from matplotlib import font_manager


CHART_FONT_CANDIDATES = (
    "PingFang SC", "Heiti SC", "STHeiti", "Arial Unicode MS",
    "Microsoft YaHei", "SimHei",
    "Noto Sans CJK SC", "Noto Sans SC", "Source Han Sans SC", "Source Han Sans CN",
    "WenQuanYi Micro Hei", "WenQuanYi Zen Hei", "Noto Sans CJK JP",
    "Droid Sans Fallback", "DejaVu Sans",
)


def configure_chart_fonts() -> None:
    """Use installed fonts, with Chinese-capable families before the Latin fallback."""
    available = {font.name for font in font_manager.fontManager.ttflist}
    families = [name for name in CHART_FONT_CANDIDATES if name in available]
    matplotlib.rcParams["font.family"] = "sans-serif"
    matplotlib.rcParams["font.sans-serif"] = families or ["DejaVu Sans"]
    matplotlib.rcParams["axes.unicode_minus"] = False
