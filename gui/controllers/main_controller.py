"""
Controlador principal (capa Controller del MVC).

Orquesta el flujo entre las vistas y el modelo:
  - aplica presets a la vista de Setup,
  - al pulsar "Ejecutar": lee y valida la FullConfig, lanza el MdaoWorker en
    un QThread, transmite el log en vivo y, al terminar, vuelca el ResultsDTO
    en las vistas de Run y Results.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Slot
from PySide6.QtWidgets import QMessageBox

from core.config import FullConfig, PRESETS, default_config
from core.results import ResultsDTO
from gui.worker import MdaoWorker


class MainController(QObject):
    def __init__(self, setup_view, run_view, results_view, plots_view, tabs):
        super().__init__()
        self.setup_view = setup_view
        self.run_view = run_view
        self.results_view = results_view
        self.plots_view = plots_view
        self.tabs = tabs

        self._base_config: FullConfig = default_config()
        self._thread: QThread | None = None
        self._worker: MdaoWorker | None = None
        self.last_dto: ResultsDTO | None = None

        # Carga inicial
        self.setup_view.load_config(self._base_config)

        # Señales
        self.setup_view.preset_selected.connect(self.on_preset_selected)
        self.setup_view.goto_run_requested.connect(self.on_goto_run)
        self.run_view.run_requested.connect(self.on_run_requested)
        self.run_view.goto_results_requested.connect(
            lambda: self.tabs.setCurrentWidget(self.results_view))
        self.results_view.goto_plots_requested.connect(
            lambda: self.tabs.setCurrentWidget(self.plots_view))

    # ----------------------------------------------------------- presets
    @Slot(str)
    def on_preset_selected(self, name: str):
        preset = PRESETS.get(name)
        if preset is not None:
            self._base_config = preset.copy()
            self.setup_view.load_config(self._base_config)

    # --------------------------------------------------------- navegación
    @Slot()
    def on_goto_run(self):
        """Paso 3 del asistente → muestra la pestaña de Ejecución (sin lanzar)."""
        self.tabs.setCurrentWidget(self.run_view)

    # ------------------------------------------------------------- run
    @Slot()
    def on_run_requested(self):
        if self._thread is not None:
            return  # ya hay una corrida en marcha

        cfg = self.setup_view.read_config(self._base_config)
        errors = self.setup_view.validate(cfg)
        if errors:
            QMessageBox.warning(self.run_view, "Configuración no válida",
                                "\n".join(errors))
            return

        self.run_view.set_running(True)
        self.tabs.setCurrentWidget(self.run_view)

        self._thread = QThread()
        self._worker = MdaoWorker(cfg)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.log.connect(self.run_view.append_log)
        self._worker.finished.connect(self.on_finished)
        self._worker.failed.connect(self.on_failed)

        self._thread.start()

    @Slot(object)
    def on_finished(self, dto: ResultsDTO):
        self.last_dto = dto
        self.run_view.set_running(False)
        self.run_view.plot_convergence(dto.history, dto.config.opt.objective_label)

        if dto.success and dto.all_constraints_ok:
            self.run_view.set_status("✔ Optimización convergida y factible.", ok=True)
        else:
            self.run_view.set_status(f"⚠ {dto.message}", ok=False)

        self.results_view.show_results(dto)
        self.plots_view.show_results(dto, dto.config)
        self.run_view.load_n2(dto.n2_html_path)
        self.run_view.set_results_ready(True)
        self._teardown_thread()

    @Slot(str)
    def on_failed(self, tb: str):
        self.run_view.set_running(False)
        self.run_view.append_log("\n[ERROR]\n" + tb)
        self.run_view.set_status("✖ La ejecución falló (ver log).", ok=False)
        QMessageBox.critical(self.run_view, "Error en la optimización", tb)
        self._teardown_thread()

    def _teardown_thread(self):
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
            self._thread = None
            self._worker = None
