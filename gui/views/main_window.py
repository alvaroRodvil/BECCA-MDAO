"""Ventana principal: header + pestañas Setup / Ejecución / Resultados."""

from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QCloseEvent
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QButtonGroup,
)

from gui.style import BG_HEADER, TEXT_WHITE, BLUE_ACCENT


_NAV_QSS = """
QPushButton {
    background: transparent; color: rgba(255,255,255,0.75);
    border: none; border-radius: 0px; padding: 0px 18px;
    font-size: 13px; font-weight: 700;
    border-bottom: 3px solid transparent;
}
QPushButton:hover { color: #FFFFFF; }
QPushButton:checked { color: #FFFFFF; border-bottom: 3px solid #FFFFFF; }
"""
from gui.views.setup_view import SetupView
from gui.views.run_view import RunView
from gui.views.results_view import ResultsView
from gui.views.plots_view import PlotsView
from gui.controllers.main_controller import MainController


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BECCA (Baseline Environment for Conceptual Computation and Analysis) - MDAO")
        self.resize(1400, 900)

        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header banner ──
        header = QWidget()
        header.setFixedHeight(64)
        header.setStyleSheet(
            f"background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"stop:0 {BG_HEADER}, stop:1 {BLUE_ACCENT});"
            f"border: none;"
        )
        hlay = QHBoxLayout(header)
        hlay.setContentsMargins(16, 0, 24, 0)

        # ── Navegación (pestañas en horizontal, esquina superior izquierda) ──
        self.tabs = QTabWidget()
        self.tabs.tabBar().hide()              # se navega desde la cabecera

        self.setup_view = SetupView()
        self.run_view = RunView()
        self.results_view = ResultsView()
        self.plots_view = PlotsView()

        self.tabs.addTab(self.setup_view,   "Configuración")
        self.tabs.addTab(self.run_view,     "Ejecución")
        self.tabs.addTab(self.results_view, "Resultados")
        self.tabs.addTab(self.plots_view,   "Gráficas")

        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)
        self.nav_buttons = []
        for i, name in enumerate(["Configuración", "Ejecución", "Resultados", "Gráficas"]):
            b = QPushButton(name)
            b.setCheckable(True)
            b.setMinimumHeight(64)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(_NAV_QSS)
            b.clicked.connect(lambda _=False, idx=i: self.tabs.setCurrentIndex(idx))
            self._nav_group.addButton(b)
            self.nav_buttons.append(b)
            hlay.addWidget(b)
        self.nav_buttons[0].setChecked(True)
        self.tabs.currentChanged.connect(self._sync_nav)

        hlay.addStretch(1)

        # ── Marca a la derecha (junto a la versión) ──
        title = QLabel("BECCA - MDAO")
        title.setFont(QFont("Helvetica Neue", 16, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {TEXT_WHITE}; background: transparent;")
        hlay.addWidget(title)
        version_lbl = QLabel("v1.0")
        version_lbl.setFont(QFont("Helvetica Neue", 10))
        version_lbl.setStyleSheet("color: rgba(255,255,255,0.6); background: transparent;")
        hlay.addWidget(version_lbl)

        root.addWidget(header)
        root.addWidget(self.tabs, 1)

        self.controller = MainController(
            self.setup_view, self.run_view, self.results_view,
            self.plots_view, self.tabs)

    def _sync_nav(self, idx):
        if 0 <= idx < len(self.nav_buttons):
            self.nav_buttons[idx].setChecked(True)

    def closeEvent(self, event: QCloseEvent) -> None:
        root = Path(__file__).parent.parent.parent
        for d in root.glob("*_out"):
            if d.is_dir():
                shutil.rmtree(d, ignore_errors=True)
        super().closeEvent(event)
