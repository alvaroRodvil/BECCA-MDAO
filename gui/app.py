"""
Punto de entrada de la GUI del MDAO-UCAV.

Ejecutar con:
    python -m gui.app
"""

from __future__ import annotations

import sys

import gui  

from PySide6.QtCore import QLocale
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from gui import plot_style as ps
from gui.style import GLOBAL_QSS
from gui.views.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("MDAO-UCAV")

    QLocale.setDefault(QLocale(QLocale.Language.English, QLocale.Country.UnitedStates))

    font = QFont("Helvetica Neue", 11)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    app.setFont(font)
    app.setStyleSheet(GLOBAL_QSS)

    ps.apply_theme()
    ps.warmup_latex()

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()