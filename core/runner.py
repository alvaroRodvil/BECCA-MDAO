"""
Orquestación de una corrida MDAO — capa Model (servicio principal).

`run_mdao(config)` es el único punto de entrada que necesita la GUI:
construye el problema, lo optimiza, extrae resultados e historial y devuelve
un `ResultsDTO`. Se ejecuta normalmente en un QThread desde el controlador.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
import warnings
from typing import IO, Optional

warnings.filterwarnings("ignore", message=".*nonlinear solver.*atomic.*")

from core.config import FullConfig, default_config
from core.model import build_problem
from core.results import ResultsDTO, extract_results, read_history


def _driver_status(run_result) -> tuple[bool, str]:
    """Extrae éxito + mensaje del valor devuelto por run_driver()."""
    success_attr = getattr(run_result, "success", None)
    if success_attr is not None:
        success = bool(success_attr)
    else:
        success = not bool(run_result)

    message = str(getattr(run_result, "exit_status", "")
                  or getattr(run_result, "message", "") or "")
    if not message:
        message = "Optimización convergida." if success else \
                  "El optimizador no convergió o devolvió una solución no factible."
    return success, message


def _generate_n2(prob) -> str:
    """Genera el HTML del N2 de OpenMDAO a un fichero temporal y devuelve su ruta."""
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from openmdao.visualization.n2_viewer.n2_viewer import n2
        fd, path = tempfile.mkstemp(suffix="_n2.html", prefix="mdao_n2_")
        os.close(fd)
        n2(prob, outfile=path, show_browser=False, embeddable=False)
        return path
    except Exception:
        return ""


def run_mdao(config: Optional[FullConfig] = None,
             record_history: bool = True,
             log_stream: Optional[IO[str]] = None) -> ResultsDTO:
    """
    Ejecuta el MDAO completo y devuelve un `ResultsDTO`.

    Parameters
    ----------
    config : FullConfig | None
        Configuración de entrada. None => corrida nominal (default_config()).
    record_history : bool
        Si True, registra el historial de iteraciones del driver.
    log_stream : file-like | None
        Si se indica, redirige el log del solver a este stream.
    """
    if config is None:
        config = default_config()

    recorder_path: Optional[str] = None
    if record_history:
        fd, recorder_path = tempfile.mkstemp(suffix=".sql", prefix="mdao_hist_")
        os.close(fd)

    prob = build_problem(config, recorder_path=recorder_path)

    try:
        if log_stream is not None:
            with contextlib.redirect_stdout(log_stream):
                run_result = prob.run_driver()
        else:
            run_result = prob.run_driver()
        success, message = _driver_status(run_result)

        dto = extract_results(prob, config, success=success, message=message)

        dto.n2_html_path = _generate_n2(prob)

        if recorder_path is not None:
            prob.cleanup()
            dto.history = read_history(recorder_path)

        return dto
    finally:
        if recorder_path is not None and os.path.exists(recorder_path):
            try:
                os.remove(recorder_path)
            except OSError:
                pass
