"""
Worker que ejecuta el MDAO en un hilo aparte (QThread).

La optimización (run_mdao) bloquearía la interfaz si corriese en el hilo de UI.
Se mueve a un QThread y se comunica con la vista mediante señales:

    log      -> texto del solver/optimizador en vivo
    finished -> ResultsDTO cuando termina con éxito
    failed   -> traza de error si lanza excepción
"""

from __future__ import annotations

import traceback

from PySide6.QtCore import QObject, Signal

from core.config import FullConfig
from core.runner import run_mdao


class _SignalStream:
    """Objeto file-like cuyo write() reemite el texto por una señal Qt.

    run_mdao redirige stdout aquí, de modo que el iprint del solver OpenMDAO
    aparece en la GUI conforme se genera."""

    def __init__(self, emit_fn):
        self._emit = emit_fn

    def write(self, text: str):
        if text:
            self._emit(text)
        return len(text)

    def flush(self):
        pass


class MdaoWorker(QObject):
    log = Signal(str)
    finished = Signal(object)   # ResultsDTO
    failed = Signal(str)

    def __init__(self, config: FullConfig):
        super().__init__()
        self._config = config

    def run(self):
        """Slot a conectar con QThread.started."""
        try:
            stream = _SignalStream(self.log.emit)
            dto = run_mdao(self._config, record_history=True, log_stream=stream)
            self.finished.emit(dto)
        except Exception:
            self.failed.emit(traceback.format_exc())
