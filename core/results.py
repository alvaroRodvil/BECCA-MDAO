"""
Resultados del MDAO — DTO consumido por la GUI (capa Model).

`ResultsDTO` empaqueta:
  - values     : dict {ruta_openmdao -> valor escalar}.
  - feasibility: estado de cada restricción (ok / activa / violada) + margen.
  - history    : series temporales del optimizador leídas del SqliteRecorder.
  - success / message: resultado del driver.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import openmdao.api as om

from core.config import FullConfig


RESULT_PATHS: list[str] = [
    # --- Objetivo y coste ---
    "cost.unit_cost_mUSD", "cost.rdte_mUSD", "cost.f_attritable_eff",
    # --- Variables de diseño / geometría base ---
    "wing_area", "t_sl", "v_ht", "aspect_ratio", "t_c_ratio",
    "x_wing_frac", "frac_fuel_fuse", "x_fuel_fuse_frac",
    "x_payload_offset_frac", "sweep_angle", "taper_ratio", "w_weapons",
    # --- Geometría derivada (ala / cola) ---
    "cycle.geom.wingspan", "cycle.geom.root_chord", "cycle.geom.tip_chord",
    "cycle.geom.mac", "cycle.geom.y_mac", "cycle.geom.x_le_mac",
    "cycle.geom.s_vtail", "cycle.geom.v_angle",
    "cycle.geom.vol_wing_tank", "cycle.geom.vol_fuse_tank",
    # --- Aerodinámica ---
    "cycle.aero.cd0", "cycle.aero.cd_induced", "cycle.aero.cd_wave",
    "cycle.aero.L_D", "cycle.aero.L_D_max", "cycle.aero.CL_cruise",
    "cycle.aero.M_dd", "cycle.aero.e_oswald",
    "cycle.aero.cd0_wing", "cycle.aero.cd0_fuse", "cycle.aero.cd0_vtail",
    "cycle.aero.cd0_misc", "cycle.aero.cd0_other",
    # --- Propulsión ---
    "cycle.prop.t_avail", "cycle.prop.t_avail_cruise",
    "cycle.prop.tsfc_avail", "cycle.prop.w_engine",
    # --- Misión / masas globales ---
    "cycle.miss.w_fuel", "cycle.mtow_sum.mtow_calc",
    "cost.oew_partial", "cost.w_engine",
    # --- Desglose de pesos ---
    "cycle.weight.w_wing", "cycle.weight.w_fuse", "cycle.weight.w_vtail",
    "cycle.weight.w_lg", "cycle.weight.oew_partial",
    "cycle.weight.w_systems", "cycle.weight.w_fuel_sys",
    "cycle.weight.w_flight_ctrl", "cycle.weight.w_hydraulics",
    "cycle.weight.w_electrical", "cycle.weight.w_ecs", "cycle.weight.w_apu",
    # --- Performance (restricciones) ---
    "perf.s_to", "perf.s_land", "perf.n_turn", "perf.roc", "perf.P_s",
    "perf.stall_margin",
    # --- Estabilidad / control ---
    "stab.sm_full", "stab.sm_empty", "stab.cg_fuel_offset",
    "stab.payload_cg_offset", "stab.cg_excursion_pct_mac",
    "stab.cg_full_pct_mac", "stab.cg_empty_pct_mac",
    "stab.cn_beta", "stab.cn_beta_vtail", "stab.cn_beta_fus",
    "stab.downwash_grad", "stab.cl_alpha_w", "stab.K_f",
    "stab.l_h_actual", "stab.v_ht_effective",
    "stab.cl_tail_required", "stab.cl_tail_rotation_req",
    "stab.v_stall_to", "stab.v_r",
    "stab.x_cg_full", "stab.x_cg_empty", "stab.x_cg_aft", "stab.x_np",
    "stab.x_fuel_fuse", "stab.sm_aft", "stab.cg_aft_pct_mac",
    # --- Volumen de combustible ---
    "fuel_vol.margin_wing_tank", "fuel_vol.margin_fuse_tank",
]


@dataclass
class ConstraintStatus:
    name: str
    label: str
    value: float
    lower: Optional[float]
    upper: Optional[float]
    status: str          # "ok" | "active" | "violated"
    margin: float
    ref: float = 1.0


@dataclass
class ResultsDTO:
    config: FullConfig
    values: dict = field(default_factory=dict)
    feasibility: list[ConstraintStatus] = field(default_factory=list)
    history: dict = field(default_factory=dict)
    success: bool = True
    message: str = ""
    n2_html_path: str = ""

    # --- Accesores cómodos ---
    def get(self, path: str, default: float = float("nan")) -> float:
        return self.values.get(path, default)

    @property
    def mtow(self) -> float:
        return self.get("cycle.mtow_sum.mtow_calc")

    @property
    def unit_cost(self) -> float:
        return self.get("cost.unit_cost_mUSD")

    @property
    def all_constraints_ok(self) -> bool:
        return all(c.status != "violated" for c in self.feasibility)


def _scalar(prob: om.Problem, path: str):
    try:
        return float(prob.get_val(path)[0])
    except Exception:
        return None


def extract_results(prob: om.Problem, config: FullConfig,
                    success: bool = True, message: str = "") -> ResultsDTO:
    """Lee del problema resuelto todos los valores de interés y el estado de
    las restricciones, y construye el DTO."""
    values: dict = {}
    for path in RESULT_PATHS:
        v = _scalar(prob, path)
        if v is not None:
            values[path] = v

    feasibility = _evaluate_feasibility(prob, config)
    return ResultsDTO(config=config, values=values, feasibility=feasibility,
                      success=success, message=message)


def _evaluate_feasibility(prob: om.Problem, config: FullConfig) -> list[ConstraintStatus]:
    """Clasifica cada restricción habilitada como ok / activa / violada."""
    out: list[ConstraintStatus] = []
    tol_active = 0.02
    for c in config.constraints:
        if not c.enabled:
            continue
        val = _scalar(prob, c.name)
        if val is None:
            continue

        status = "ok"
        scale = max(abs(c.ref), 1.0e-9)
        margin = float("inf")

        if c.lower is not None:
            d = (val - c.lower) / scale
            margin = min(margin, d)
            if val < c.lower - 1.0e-6 * scale:
                status = "violated"
            elif abs(d) <= tol_active and status != "violated":
                status = "active"
        if c.upper is not None:
            d = (c.upper - val) / scale
            margin = min(margin, d)
            if val > c.upper + 1.0e-6 * scale:
                status = "violated"
            elif abs(d) <= tol_active and status != "violated":
                status = "active"

        out.append(ConstraintStatus(
            name=c.name, label=c.label or c.name, value=val,
            lower=c.lower, upper=c.upper, status=status,
            margin=(0.0 if margin == float("inf") else margin),
            ref=scale,
        ))
    return out


def read_history(recorder_path: str) -> dict:
    """Lee el SqliteRecorder y devuelve las series por iteración del driver."""
    history = {"iterations": [], "objective": {}, "desvars": {}, "constraints": {}}
    try:
        cr = om.CaseReader(recorder_path)
        cases = cr.get_cases("driver", recurse=False)
    except Exception:
        return history

    def _append(bucket: dict, data: dict):
        for name, arr in data.items():
            try:
                bucket.setdefault(name, []).append(float(np.asarray(arr).ravel()[0]))
            except Exception:
                pass

    for i, case in enumerate(cases):
        history["iterations"].append(i)
        try:
            _append(history["objective"], case.get_objectives(scaled=False))
        except Exception:
            pass
        try:
            _append(history["desvars"], case.get_design_vars(scaled=False))
        except Exception:
            pass
        try:
            _append(history["constraints"], case.get_constraints(scaled=False))
        except Exception:
            pass

    return history
