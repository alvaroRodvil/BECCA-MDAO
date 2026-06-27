"""
Barra de margen para restricciones (capa View, widget reutilizable).

Dibuja, para una `ConstraintStatus`, una barra horizontal con un MARCADOR de
posición que indica cuánto margen queda respecto al/los límite(s):

  · Restricción de DOS límites [lo, hi]:  la barra representa el rango admisible
    completo; el marcador cae en (valor−lo)/(hi−lo) y se pintan bandas rojas en
    los extremos (zona "activa", a 2·ref del límite). El usuario ve si el valor
    está centrado (holgado) o pegado a un borde (a punto de saturar).

  · Restricción de UN límite (≥ lo  ó  ≤ hi):  barra direccional. El límite se
    ancla en un extremo (rojo) y el relleno crece hacia la zona segura según el
    margen normalizado por `ref` (con mapeo √ para que los márgenes pequeños
    sigan siendo visibles). El marcador queda al final del relleno.

El color del marcador/relleno sigue el semáforo del estado: verde (holgada),
ámbar (activa) o rojo (violada). El dibujado es testable porque la lógica de
posición vive en `_geometry`, independiente de Qt.
"""

from __future__ import annotations

import math

from PySide6.QtCore import Qt, QRectF, QSize
from PySide6.QtGui import QPainter, QColor, QBrush, QPen
from PySide6.QtWidgets import QWidget

from core.results import ConstraintStatus
from gui.style import GREEN_OK, RED_VIOLATED

# Banda "activa" en unidades de ref (coincide con tol_active de results.py)
_ACTIVE_TOL = 0.02
_FULL_MARGIN = 1.0

_STATUS_COLOR = {
    "ok": GREEN_OK,
    "active": "#1E6FD9",    # azul primario (activa = buena señal)
    "violated": RED_VIOLATED,
}
_TRACK_BG = "#E8EDF3"
_ACTIVE_BAND = "#BFDBFE"        # azul claro para la zona próxima al límite


class MarginBar(QWidget):
    """Barra de margen con marcador para una restricción."""

    def __init__(self, cs: ConstraintStatus, parent=None):
        super().__init__(parent)
        self._cs = cs
        self.setMinimumWidth(120)
        self.setMinimumHeight(26)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setToolTip(self._tooltip())

    def sizeHint(self) -> QSize:  # noqa: N802 (Qt API)
        return QSize(180, 26)

    # ------------------------------------------------------------------
    def _geometry(self) -> dict:
        """Calcula posición del marcador y bandas (independiente de Qt).

        Devuelve fracciones en [0, 1] sobre el ancho útil de la barra:
          · 'two_sided': bool
          · 'marker'   : posición del marcador
          · 'fill0'/'fill1': extremos del relleno (one-sided)
          · 'band_lo'/'band_hi': anchura de banda activa en cada extremo
        """
        cs = self._cs
        ref = max(abs(cs.ref), 1e-9)
        two_sided = cs.lower is not None and cs.upper is not None

        if two_sided:
            lo, hi = cs.lower, cs.upper
            span = max(hi - lo, 1e-12)
            marker = (cs.value - lo) / span
            band = min(max(_ACTIVE_TOL * ref / span, 0.04), 0.30)
            return {"two_sided": True, "marker": _clamp(marker),
                    "band_lo": band, "band_hi": band}

        frac = math.sqrt(_clamp(cs.margin / _FULL_MARGIN))   # √ realza lo pequeño
        band = math.sqrt(_ACTIVE_TOL / _FULL_MARGIN)         # ancho de zona activa
        lower_only = cs.lower is not None
        if lower_only:                       # ≥ lo : límite a la izquierda
            return {"two_sided": False, "from_left": True,
                    "fill0": 0.0, "fill1": frac, "marker": frac, "band": band}
        else:                                # ≤ hi : límite a la derecha
            return {"two_sided": False, "from_left": False,
                    "fill0": 1.0 - frac, "fill1": 1.0, "marker": 1.0 - frac,
                    "band": band}

    def _tooltip(self) -> str:
        cs = self._cs
        lim = []
        if cs.lower is not None:
            lim.append(f"≥ {cs.lower:g}")
        if cs.upper is not None:
            lim.append(f"≤ {cs.upper:g}")
        return (f"{cs.label}\nValor: {cs.value:.4g}\nLímites: {'  '.join(lim)}\n"
                f"Margen: {cs.margin:+.3f} ref")

    # ------------------------------------------------------------------
    def paintEvent(self, event):  # noqa: N802 (Qt API)
        g = self._geometry()
        color = QColor(_STATUS_COLOR.get(self._cs.status, GREEN_OK))

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w = self.width()
        h = self.height()
        bar_h = 10
        pad = 10
        track_w = max(w - 2 * pad, 1)
        y = (h - bar_h) / 2.0
        radius = bar_h / 2.0

        def fx(frac: float) -> float:
            return pad + _clamp(frac) * track_w

        # --- Pista de fondo ---
        track = QRectF(pad, y, track_w, bar_h)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(_TRACK_BG)))
        p.drawRoundedRect(track, radius, radius)

        if g["two_sided"]:
            # Bandas rojas (zona activa) en ambos extremos
            band_color = QColor(_ACTIVE_BAND)
            p.setBrush(QBrush(band_color))
            blo = g["band_lo"] * track_w
            bhi = g["band_hi"] * track_w
            p.drawRoundedRect(QRectF(pad, y, blo, bar_h), radius, radius)
            p.drawRoundedRect(QRectF(pad + track_w - bhi, y, bhi, bar_h),
                              radius, radius)
        else:
            # Relleno de la zona segura (one-sided), con el color del estado
            fill = QColor(color)
            fill.setAlpha(70)
            x0 = fx(g["fill0"])
            x1 = fx(g["fill1"])
            p.setBrush(QBrush(fill))
            p.drawRoundedRect(QRectF(min(x0, x1), y, abs(x1 - x0), bar_h),
                              radius, radius)
            # Banda roja junto al límite
            p.setBrush(QBrush(QColor(_ACTIVE_BAND)))
            bw = g["band"] * track_w
            if g["from_left"]:
                p.drawRoundedRect(QRectF(pad, y, bw, bar_h), radius, radius)
            else:
                p.drawRoundedRect(QRectF(pad + track_w - bw, y, bw, bar_h),
                                  radius, radius)

        # --- Marcador (círculo) ---
        mx = fx(g["marker"])
        mr = 6.0
        p.setPen(QPen(QColor("#FFFFFF"), 1.6))
        p.setBrush(QBrush(color))
        p.drawEllipse(QRectF(mx - mr, h / 2.0 - mr, 2 * mr, 2 * mr))
        p.end()


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    if v != v:        # NaN
        return lo
    return max(lo, min(hi, v))
