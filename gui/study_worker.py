"""
Worker genérico para estudios paramétricos caros (tornado, Pareto).

Ejecuta una función `fn(progress_cb) -> result` en un QThread y emite progreso.
"""

from __future__ import annotations

import traceback
from typing import Callable

from PySide6.QtCore import QObject, Signal


class StudyWorker(QObject):
    progress = Signal(int, int)     # (hechos, total)
    finished = Signal(object)       # resultado del estudio
    failed = Signal(str)

    def __init__(self, fn: Callable):
        super().__init__()
        self._fn = fn

    def run(self):
        try:
            result = self._fn(lambda i, n: self.progress.emit(int(i), int(n)))
            self.finished.emit(result)
        except Exception:
            self.failed.emit(traceback.format_exc())
