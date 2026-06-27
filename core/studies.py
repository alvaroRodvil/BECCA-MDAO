"""
Estudios paramétricos del MDAO (capa Model).

  - tornado_sensitivity: sensibilidad local del objetivo a perturbaciones ±10 %
    de variables de diseño y parámetros clave alrededor del óptimo.
  - pareto_front: barrido de un requisito de misión re-optimizando en cada punto.

Ambos aceptan un callback `progress(i, n)` para alimentar una barra en la GUI.
"""

from __future__ import annotations

import contextlib
import io
from typing import Callable, Optional

import numpy as np

from core.config import FullConfig
from core.model import build_problem
from core.results import ResultsDTO
from core.runner import run_mdao


def _silent_run(prob):
    """run_model() suprimiendo el iprint del solver NLBGS."""
    with contextlib.redirect_stdout(io.StringIO()):
        prob.run_model()


# Entradas a perturbar en el análisis tornado
TORNADO_INPUTS = [
    (r"$S$ $\cdot$ superficie alar", "wing_area"),
    (r"$T_{SL}$ $\cdot$ empuje", "t_sl"),
    (r"$AR$ $\cdot$ alargamiento", "aspect_ratio"),
    (r"$\lambda$ $\cdot$ estrechamiento", "taper_ratio"),
    (r"$V_{HT}$ $\cdot$ cola", "v_ht"),
    (r"TSFC $\cdot$ consumo motor", "tsfc_sl"),
    (r"$n_{ult}$ $\cdot$ factor estructural", "n_ult"),
    (r"Peso aviónica", "w_avionics"),
    (r"Longitud fuselaje", "fuselage_length"),
    (r"Alcance requerido", "range_m"),
    (r"Payload", "w_weapons"),
    (r"$Q$ $\cdot$ tamaño de flota", "q_prod"),
]


def tornado_sensitivity(dto: ResultsDTO, config: FullConfig,
                        perturb: float = 0.10,
                        progress: Optional[Callable[[int, int], None]] = None) -> dict:
    """Sensibilidad del objetivo a ±`perturb` en cada entrada, alrededor del óptimo."""
    prob = build_problem(config)
    for dv in config.design_vars:
        if dv.enabled:
            v = dto.get(dv.name)
            if v == v:
                prob.set_val(dv.name, v)
    _silent_run(prob)
    obj = config.opt.objective
    obj0 = float(prob.get_val(obj)[0])

    rows = []
    n = len(TORNADO_INPUTS)
    for i, (label, name) in enumerate(TORNADO_INPUTS):
        try:
            base = float(np.asarray(prob.get_val(name)).flatten()[0])
        except Exception:
            if progress:
                progress(i + 1, n)
            continue
        if base == 0.0:
            if progress:
                progress(i + 1, n)
            continue
        prob.set_val(name, base * (1.0 + perturb))
        _silent_run(prob)
        hi = float(prob.get_val(obj)[0])
        prob.set_val(name, base * (1.0 - perturb))
        _silent_run(prob)
        lo = float(prob.get_val(obj)[0])
        prob.set_val(name, base)
        _silent_run(prob)
        rows.append({
            "label": label,
            "d_hi": (hi - obj0) / obj0 * 100.0,
            "d_lo": (lo - obj0) / obj0 * 100.0,
        })
        if progress:
            progress(i + 1, n)

    rows.sort(key=lambda r: abs(r["d_hi"]) + abs(r["d_lo"]))
    return {
        "obj0": obj0,
        "objective_label": config.opt.objective_label,
        "perturb": perturb,
        "rows": rows,
    }


# Requisitos barríbles en el análisis Pareto
PARETO_PARAMS = {
    "range_km": ("Alcance", "km", 1.0),
    "payload_kg": ("Carga útil", "kg", 1.0),
    "n_combat": ("Factor de carga combate", "g", 1.0),
    "loiter_min": ("Loiter", "min", 1.0),
}


def pareto_front(config: FullConfig, param: str = "range_km",
                 values=None, n_points: int = 8,
                 progress: Optional[Callable[[int, int], None]] = None) -> dict:
    """Re-optimiza barriendo un requisito de misión → frontera coste/MTOW."""
    base = getattr(config.mission, param)
    if values is None:
        values = list(np.linspace(0.7 * base, 1.4 * base, n_points))

    points = []
    n = len(values)
    for i, v in enumerate(values):
        cfg = config.copy()
        setattr(cfg.mission, param, float(v))
        dto = run_mdao(cfg, record_history=False, log_stream=io.StringIO())
        points.append({
            "x": float(v),
            "cost": dto.unit_cost,
            "mtow": dto.mtow,
            "feasible": bool(dto.success and dto.all_constraints_ok),
        })
        if progress:
            progress(i + 1, n)

    label, unit, _ = PARETO_PARAMS.get(param, (param, "", 1.0))
    return {"param": param, "param_label": label, "unit": unit,
            "points": points,
            "design_x": getattr(config.mission, param)}
