"""
Tema de gráficas estilo publicación científica (SciencePlots + LaTeX).

Usa el estilo `science` de SciencePlots con `text.usetex=True`, de modo que el
texto y las ecuaciones se renderizan con LaTeX (fuente Computer Modron serif),
el estándar de artículos científicos.

  - apply_theme():   aplica el estilo (idempotente).
  - warmup_latex():  fuerza el primer render de LaTeX (caché) para que la
                     primera gráfica de la GUI no sufra el retardo inicial. Si
                     LaTeX no estuviera disponible, cae a 'no-latex' (mathtext).
  - style_axes / footer / annotate / design_star / placeholder: utilidades.

TODO el texto que llegue a matplotlib debe ser LaTeX-seguro: matemáticas entre
$...$, y `%`/`$` escapados (\%, \$). Hay helpers `pct()` y un alias `MATH`.
"""

from __future__ import annotations

import re

import matplotlib as mpl
import matplotlib.style as mstyle
from matplotlib.colors import LinearSegmentedColormap

import scienceplots  
from gui.style import (
    BLUE_PRIMARY, BLUE_DARK, BLUE_ACCENT, BLUE_LIGHT,
    GREEN_OK, AMBER_ACTIVE, RED_VIOLATED,
)

__all__ = [
    "BLUE_PRIMARY", "BLUE_DARK", "BLUE_ACCENT", "BLUE_LIGHT", "GREEN_OK",
    "AMBER_ACTIVE", "RED_VIOLATED", "INK", "MUTED", "GRID", "CYCLE",
    "CMAP_BLUE", "CMAP_PS", "USETEX", "apply_theme", "warmup_latex",
    "pct", "style_axes", "footer", "annotate", "design_star", "placeholder",
]

# ───────────────────────── Paleta de gráficas ─────────────────────────
INK = "#0F1F33"
MUTED = "#5A6675"
GRID = "#D9DEE7"

CYCLE = [
    BLUE_PRIMARY, AMBER_ACTIVE, GREEN_OK, "#8B5CF6",
    RED_VIOLATED, "#0EA5E9", BLUE_DARK, "#EC4899",
]
FILL_FEASIBLE = GREEN_OK

CMAP_BLUE = LinearSegmentedColormap.from_list(
    "becca_blue", ["#EAF2FE", BLUE_ACCENT, BLUE_DARK])
CMAP_PS = LinearSegmentedColormap.from_list(
    "becca_ps", ["#B91C1C", "#FCA5A5", "#F8FAFC", "#93C5FD", BLUE_DARK])

BLACK = "#000000"
USETEX = False
_APPLIED = False


def apply_theme(force: bool = False):
    """Aplica SciencePlots 'no-latex' (mathtext Computer Modern) + paleta BECCA.

    Rápido (sin subproceso LaTeX) y con ejes/títulos/texto en negro y gruesos."""
    global _APPLIED
    if _APPLIED and not force:
        return
    try:
        mstyle.use(["science", "no-latex"])
    except Exception:
        pass

    mpl.rcParams.update({
        # --- Tipografía estilo LaTeX vía mathtext (Computer Modern) ---
        "text.usetex": False,
        "mathtext.fontset": "cm",
        "font.family": "serif",
        "font.serif": ["CMU Serif", "DejaVu Serif", "Times New Roman"],
        "font.size": 12,

        # --- Texto/ejes en NEGRO ---
        "text.color": BLACK,
        "axes.labelcolor": BLACK,
        "axes.titlecolor": BLACK,
        "axes.edgecolor": BLACK,
        "xtick.color": BLACK,
        "ytick.color": BLACK,
        "xtick.labelcolor": BLACK,
        "ytick.labelcolor": BLACK,

        # --- Tamaños y pesos ---
        "axes.titlesize": 14,
        "axes.titleweight": "bold",
        "axes.labelsize": 12,
        "axes.labelweight": "bold",
        "xtick.labelsize": 10.5,
        "ytick.labelsize": 10.5,
        "legend.fontsize": 9.8,
        "legend.frameon": True,
        "legend.framealpha": 0.95,
        "legend.edgecolor": "0.6",

        # --- Líneas/ejes más gruesos (no finos) ---
        "axes.linewidth": 1.4,
        "xtick.major.width": 1.3,
        "ytick.major.width": 1.3,
        "xtick.minor.width": 0.9,
        "ytick.minor.width": 0.9,
        "xtick.major.size": 5.0,
        "ytick.major.size": 5.0,
        "xtick.minor.size": 2.8,
        "ytick.minor.size": 2.8,
        "lines.linewidth": 2.1,

        # --- Rejilla suave + color de series ---
        "axes.prop_cycle": mpl.cycler(color=CYCLE),
        "axes.grid": True,
        "grid.color": GRID,
        "grid.alpha": 0.45,
        "grid.linewidth": 0.7,

        # --- Lienzo ---
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
        "figure.dpi": 110,
        "savefig.dpi": 220,
        "savefig.bbox": "tight",

        # --- Márgenes (constrained layout + título) ---
        "figure.constrained_layout.h_pad": 0.30,
        "figure.constrained_layout.w_pad": 0.30,
        "axes.titlepad": 10,
    })
    _APPLIED = True


def warmup_latex():
    """Prepara el render (caché de fuentes mathtext). Muy rápido: no usa LaTeX.

    Se conserva el nombre por compatibilidad con app.py."""
    apply_theme()
    import io
    from matplotlib.figure import Figure
    try:
        fig = Figure(figsize=(1, 1))
        ax = fig.add_subplot(111)
        ax.set_title(r"$C_L \geq 0$  áéíóú")
        ax.set_xlabel(r"$T/W$")
        fig.savefig(io.BytesIO(), format="png")
    except Exception:
        pass


def pct() -> str:
    r"""'%' (sin usetex, mathtext no requiere escaparlo fuera de modo math)."""
    return "%"


def bold_math(s: str) -> str:
    r"""Envuelve cada segmento matemático ($...$) en \boldsymbol{} para negrita
    cursiva (bold-italic), que es el estilo estándar en títulos y ejes."""
    if not s:
        return s
    return re.sub(r"\$(.+?)\$", lambda m: r"$\boldsymbol{" + m.group(1) + r"}$", s)


def style_axes(ax, title=None, xlabel=None, ylabel=None, legend=None,
               legend_ncol=1, grid=True):
    if title is not None:
        ax.set_title(bold_math(title), fontweight="bold")
    if xlabel is not None:
        ax.set_xlabel(bold_math(xlabel), fontweight="bold")
    if ylabel is not None:
        ax.set_ylabel(bold_math(ylabel), fontweight="bold")
    if grid:
        ax.grid(True, alpha=0.30)
    else:
        ax.grid(False)
    if legend:
        ax.legend(loc=legend, ncol=legend_ncol)


def footer(fig, text="BECCA $\\cdot$ MDAO"):
    fig.text(0.995, 0.005, text, ha="right", va="bottom",
             fontsize=7.5, color="#9AA4B2")


def annotate(ax, x, y, text, dx=8, dy=8, color=None):
    color = color or BLUE_DARK
    ax.annotate(text, xy=(x, y), xytext=(dx, dy), textcoords="offset points",
                fontsize=8.6, color=color,
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                          edgecolor=color, lw=0.7, alpha=0.92))


def design_star(ax, x, y, label="Diseño óptimo", color=None):
    color = color or BLUE_DARK
    ax.plot([x], [y], marker="*", ms=18, color=color, markeredgecolor="white",
            markeredgewidth=1.3, zorder=12, label=label, linestyle="none")


def placeholder(fig, text, color=MUTED):
    fig.clear()
    ax = fig.add_subplot(111)
    ax.axis("off")
    prev = mpl.rcParams["text.usetex"]
    mpl.rcParams["text.usetex"] = False
    ax.text(0.5, 0.5, text, ha="center", va="center", fontsize=12,
            color=color, transform=ax.transAxes, wrap=True)
    mpl.rcParams["text.usetex"] = prev
    return ax
