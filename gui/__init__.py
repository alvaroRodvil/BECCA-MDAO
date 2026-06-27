"""
Capa View + Controller (PySide6) del MDAO-UCAV — patrón MVC.

La GUI consume exclusivamente el paquete `core/` (capa Model). Estructura:

    gui/app.py                  → punto de entrada (QApplication + MainWindow)
    gui/worker.py               → MdaoWorker (corre run_mdao en un QThread)
    gui/widgets/mpl_canvas.py   → lienzo matplotlib reutilizable
    gui/views/                  → ventanas y pestañas (Setup, Run, Results)
    gui/controllers/            → orquestación config <-> vistas <-> worker

Lanzar con:  python -m gui.app
"""

import os
import re
import threading
import warnings

os.environ.setdefault("QT_API", "pyside6")

# Silencia los WARNING de Qt WebEngine sobre rutas de recursos/locales que no se
# pasan al proceso renderer (Qt las resuelve por defecto, no son errores).
_WEBENGINE_NOISE = re.compile(
    rb"web_engine_library_info\.cpp|"
    rb"--webengine-(?:resources|locales)-path not passed"
)


def _filter_stderr_fd() -> None:
    try:
        real_stderr_fd = os.dup(2)          
        read_fd, write_fd = os.pipe()
    except OSError:
        return

    os.dup2(write_fd, 2)                  
    os.close(write_fd)

    def _pump() -> None:
        with os.fdopen(read_fd, "rb", buffering=0) as reader:
            for line in reader:
                if not _WEBENGINE_NOISE.search(line):
                    os.write(real_stderr_fd, line)

    threading.Thread(target=_pump, name="stderr-webengine-filter",
                     daemon=True).start()


_filter_stderr_fd()

# Silencia avisos de terceros que no indican ningún problema real:
warnings.filterwarnings("ignore", category=UserWarning,
                        message=".*gridspecs with layoutgrids.*")
warnings.filterwarnings("ignore", message=".*nonlinear solver.*atomic.*",
                        module="openmdao.*")
