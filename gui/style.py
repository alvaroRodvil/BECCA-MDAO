"""
Stylesheet global (QSS) y constantes de paleta para la GUI del MDAO-UCAV.

Paleta principal:
  - Blanco / gris muy claro para fondos
  - Azul primario (#1E6FD9) y azul oscuro (#0D47A1) para acentos
  - Grises medios para texto secundario y bordes

Todo el look-and-feel se define aquí. Las vistas solo organizan widgets.
"""

from __future__ import annotations

import os as _os

_ASSETS = _os.path.join(_os.path.dirname(__file__), "assets").replace("\\", "/")
_ARROW_UP   = f"{_ASSETS}/arrow_up.svg"
_ARROW_DOWN = f"{_ASSETS}/arrow_down.svg"

# ──────────────────────────────── Paleta ────────────────────────────────
# Backgrounds
BG_WINDOW = "#F0F2F5"
BG_CARD = "#FFFFFF"
BG_HEADER = "#0D47A1"

# Borders
BORDER_CARD = "#DDE1E8"
BORDER_INPUT = "#C4CAD4"

# Blues
BLUE_PRIMARY = "#1E6FD9"
BLUE_DARK = "#0D47A1"
BLUE_ACCENT = "#3B82F6"
BLUE_LIGHT = "#E8F0FE"

# Text
TEXT_PRIMARY = "#1E293B"
TEXT_SECONDARY = "#64748B"
TEXT_ON_DARK = "#E2E8F0"
TEXT_WHITE = "#FFFFFF"

# Status
GREEN_OK = "#16A34A"
AMBER_ACTIVE = "#D97706"
RED_VIOLATED = "#DC2626"

# Table
TABLE_HEADER_BG = "#0D47A1"
TABLE_HEADER_FG = "#FFFFFF"
TABLE_ALT_ROW = "#F8FAFC"

# Console
CONSOLE_BG = "#1E293B"
CONSOLE_FG = "#E2E8F0"

# ──────────────────────────────── Font ──────────────────────────────────
FONT_FAMILY = "'.AppleSystemUIFont', 'Helvetica Neue', 'Arial'"
FONT_SIZE = "13px"

# ──────────────────────────────── QSS ───────────────────────────────────
GLOBAL_QSS = f"""
/* ── Base ────────────────────────────────────────────────────────── */
QMainWindow, QWidget#centralWidget {{
    background-color: {BG_WINDOW};
}}

QWidget {{
    font-family: {FONT_FAMILY};
    font-size: {FONT_SIZE};
    color: {TEXT_PRIMARY};
}}

/* ── Tab Widget ──────────────────────────────────────────────────── */
QTabWidget::pane {{
    border: none;
    background: {BG_WINDOW};
}}

QTabBar {{
    background: {BG_CARD};
    border-bottom: 2px solid {BORDER_CARD};
}}

QTabBar::tab {{
    background: transparent;
    color: {TEXT_SECONDARY};
    padding: 10px 24px;
    margin: 0px 2px;
    font-size: 13px;
    font-weight: 600;
    border-bottom: 3px solid transparent;
    min-width: 140px;
}}

QTabBar::tab:selected {{
    color: {BLUE_PRIMARY};
    border-bottom: 3px solid {BLUE_PRIMARY};
    background: {BG_CARD};
}}

QTabBar::tab:hover:!selected {{
    color: {TEXT_PRIMARY};
    border-bottom: 3px solid {BORDER_CARD};
}}

/* ── Group Box (Card) ────────────────────────────────────────────── */
QGroupBox {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER_CARD};
    border-radius: 10px;
    margin-top: 0px;
    padding: 42px 16px 14px 16px;
    font-weight: 700;
    font-size: 13px;
    color: {BLUE_DARK};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 14px 16px 0px 16px;
    background-color: transparent;
    border: none;
    color: {BLUE_DARK};
    font-weight: 800;
    font-size: 20px;
    left: 0px;
}}

/* ── Inputs ──────────────────────────────────────────────────────── */
QDoubleSpinBox, QSpinBox {{
    background: {BG_CARD};
    border: 1px solid {BORDER_INPUT};
    border-radius: 6px;
    padding: 5px 8px;
    min-height: 24px;
    min-width: 110px;
    color: {TEXT_PRIMARY};
    font-weight: 500;
}}

QDoubleSpinBox:focus, QSpinBox:focus {{
    border: 2px solid {BLUE_PRIMARY};
}}

QDoubleSpinBox::up-button, QDoubleSpinBox::down-button,
QSpinBox::up-button, QSpinBox::down-button {{
    width: 20px;
    border: none;
    border-left: 1px solid {BORDER_INPUT};
    background: {TABLE_ALT_ROW};
    subcontrol-origin: border;
}}

QDoubleSpinBox::up-button, QSpinBox::up-button {{
    subcontrol-position: top right;
    border-bottom: 1px solid {BORDER_INPUT};
    border-top-right-radius: 5px;
}}

QDoubleSpinBox::down-button, QSpinBox::down-button {{
    subcontrol-position: bottom right;
    border-bottom-right-radius: 5px;
}}

QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover,
QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
    background: {BLUE_LIGHT};
}}

QDoubleSpinBox::up-arrow, QSpinBox::up-arrow {{
    image: url("{_ARROW_UP}");
    width: 8px;
    height: 5px;
}}

QDoubleSpinBox::down-arrow, QSpinBox::down-arrow {{
    image: url("{_ARROW_DOWN}");
    width: 8px;
    height: 5px;
}}

QComboBox {{
    background: {BG_CARD};
    border: 1px solid {BORDER_INPUT};
    border-radius: 6px;
    padding: 6px 10px;
    min-height: 26px;
    color: {TEXT_PRIMARY};
    font-weight: 500;
}}

QComboBox:focus {{
    border: 2px solid {BLUE_PRIMARY};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox QAbstractItemView {{
    background: {BG_CARD};
    border: 1px solid {BORDER_CARD};
    border-radius: 6px;
    selection-background-color: {BLUE_LIGHT};
    selection-color: {BLUE_PRIMARY};
    padding: 4px;
}}

/* ── Tables ──────────────────────────────────────────────────────── */
QTableWidget {{
    background-color: {BG_CARD};
    alternate-background-color: {TABLE_ALT_ROW};
    border: none;
    border-radius: 0px;
    gridline-color: {BORDER_CARD};
    selection-background-color: {BLUE_LIGHT};
    selection-color: {TEXT_PRIMARY};
    font-size: 12px;
}}

QTableWidget::item {{
    padding: 6px 10px;
    border: none;
}}

QHeaderView::section {{
    background-color: {TABLE_HEADER_BG};
    color: {TABLE_HEADER_FG};
    font-weight: 700;
    font-size: 12px;
    padding: 8px 10px;
    border: none;
    border-right: 1px solid rgba(255,255,255,0.15);
}}

QHeaderView::section:first {{
    border-top-left-radius: 8px;
}}

QHeaderView::section:last {{
    border-top-right-radius: 8px;
    border-right: none;
}}

/* ── Buttons ─────────────────────────────────────────────────────── */
QPushButton {{
    background-color: {BLUE_PRIMARY};
    color: {TEXT_WHITE};
    border: none;
    border-radius: 6px;
    padding: 9px 22px;
    font-weight: 700;
    font-size: 13px;
    min-height: 28px;
}}

QPushButton:hover {{
    background-color: {BLUE_ACCENT};
}}

QPushButton:pressed {{
    background-color: {BLUE_DARK};
}}

QPushButton:disabled {{
    background-color: {BORDER_INPUT};
    color: {TEXT_SECONDARY};
}}

/* ── Progress bar ────────────────────────────────────────────────── */
QProgressBar {{
    background: {BORDER_CARD};
    border: none;
    border-radius: 6px;
    min-height: 12px;
    max-height: 12px;
    text-align: center;
    color: transparent;
    font-size: 1px;
}}

QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {BLUE_PRIMARY}, stop:1 {BLUE_ACCENT});
    border-radius: 6px;
}}

/* ── Plain text (log console) ────────────────────────────────────── */
QPlainTextEdit#logConsole {{
    background-color: {CONSOLE_BG};
    color: {CONSOLE_FG};
    border: 1px solid {BORDER_CARD};
    border-radius: 8px;
    padding: 10px;
    font-family: 'Menlo', 'Cascadia Code', 'Consolas', monospace;
    font-size: 11px;
    selection-background-color: {BLUE_PRIMARY};
    selection-color: {TEXT_WHITE};
}}

/* ── Scroll area ─────────────────────────────────────────────────── */
QScrollArea {{
    background: transparent;
    border: none;
}}

QScrollArea > QWidget > QWidget {{
    background: transparent;
}}

/* ── Scrollbar ───────────────────────────────────────────────────── */
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 4px 2px;
}}

QScrollBar::handle:vertical {{
    background: {BORDER_INPUT};
    border-radius: 4px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background: {TEXT_SECONDARY};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
    margin: 2px 4px;
}}

QScrollBar::handle:horizontal {{
    background: {BORDER_INPUT};
    border-radius: 4px;
    min-width: 30px;
}}

QScrollBar::handle:horizontal:hover {{
    background: {TEXT_SECONDARY};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

/* ── Splitter ────────────────────────────────────────────────────── */
QSplitter::handle {{
    background: {BORDER_CARD};
    width: 2px;
    margin: 4px 6px;
    border-radius: 1px;
}}

/* ── Form labels ─────────────────────────────────────────────────── */
QLabel {{
    color: {TEXT_PRIMARY};
    background: transparent;
}}

/* ── Tooltip ─────────────────────────────────────────────────────── */
QToolTip {{
    background-color: {TEXT_PRIMARY};
    color: {TEXT_WHITE};
    border: none;
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 12px;
}}
"""
