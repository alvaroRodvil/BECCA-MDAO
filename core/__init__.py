"""
Núcleo desacoplado del framework MDAO-UCAV (capa Model del patrón MVC).

Este paquete separa la lógica del MDAO de su presentación:

    config.py   → dataclasses con TODOS los parámetros de entrada (requisitos
                  de misión, parámetros fijos, variables de diseño y bounds,
                  restricciones, ajustes del optimizador) + presets.
    model.py    → UCAVModel (grupo OpenMDAO) + build_problem(config).
    results.py  → ResultsDTO + extracción de outputs e historial de iteraciones.
    runner.py   → run_mdao(config) — orquesta build → run → extract.

La GUI (PySide6, patrón MVC) consume exclusivamente este paquete; nunca
toca OpenMDAO directamente. Los scripts clásicos (main.py, sensitivity.py,
compare_AC.py) también pueden apoyarse aquí.
"""

from core.config import (
    FullConfig,
    MissionConfig,
    AircraftParams,
    CostParams,
    StabilityParams,
    DesignVar,
    Constraint,
    OptConfig,
    isa_state,
    default_config,
    PRESETS,
)

__all__ = [
    "FullConfig",
    "MissionConfig",
    "AircraftParams",
    "CostParams",
    "StabilityParams",
    "DesignVar",
    "Constraint",
    "OptConfig",
    "isa_state",
    "default_config",
    "PRESETS",
]
