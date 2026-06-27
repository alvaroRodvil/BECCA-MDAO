"""Lienzo matplotlib reutilizable embebido en Qt (sin pyplot)."""

from __future__ import annotations

import matplotlib
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT
from matplotlib.figure import Figure

from PySide6.QtWidgets import QWidget, QVBoxLayout

# ── Estilo matplotlib coherente con la paleta de la GUI ──
_MPL_RC = {
    "figure.facecolor": "#FFFFFF",
    "axes.facecolor": "#FAFBFC",
    "axes.edgecolor": "#DDE1E8",
    "axes.labelcolor": "#1E293B",
    "axes.titlepad": 12,
    "axes.grid": True,
    "grid.color": "#E8EBF0",
    "grid.alpha": 0.6,
    "grid.linestyle": "--",
    "grid.linewidth": 0.6,
    "xtick.color": "#64748B",
    "ytick.color": "#64748B",
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica Neue", "Arial", "Segoe UI"],
    "font.size": 10,
    "lines.linewidth": 2.0,
    "lines.markersize": 5,
    "savefig.dpi": 400,        # resolución de exportación PNG (calidad imprenta)
    "savefig.bbox": "tight",   # recorta márgenes en blanco al guardar
}

matplotlib.rcParams.update(_MPL_RC)


class MplCanvas(FigureCanvasQTAgg):
    """Canvas con una figura propia. Usar `self.fig` / `self.ax`."""

    def __init__(self, figsize=(5.0, 4.0), dpi=100):
        self.fig = Figure(figsize=figsize, dpi=dpi, layout="constrained")
        super().__init__(self.fig)
        self.ax = self.fig.add_subplot(111)

    def reset(self):
        """Limpia la figura y devuelve un único Axes nuevo."""
        self.fig.clear()
        self.ax = self.fig.add_subplot(111)
        return self.ax


class MplWidget(QWidget):
    """Canvas + barra de navegación matplotlib, listo para meter en un layout."""

    def __init__(self, figsize=(5.0, 4.0), toolbar=True, parent=None):
        super().__init__(parent)
        self.canvas = MplCanvas(figsize=figsize)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        if toolbar:
            layout.addWidget(NavigationToolbar2QT(self.canvas, self))
        layout.addWidget(self.canvas)

    @property
    def fig(self):
        return self.canvas.fig

    @property
    def ax(self):
        return self.canvas.ax

    def reset(self):
        return self.canvas.reset()

    def draw(self):
        self.canvas.draw_idle()
