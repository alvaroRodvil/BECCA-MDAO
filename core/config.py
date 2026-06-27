"""
Configuración del MDAO-UCAV — capa de entrada de datos (MVC: parte del Model).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Optional

import numpy as np


# Atmósfera estándar internacional (ISA) — hasta 20 km
# Devuelve (ρ [kg/m³], T [K], a [m/s]) en función de h [m].
def isa_state(h):
    if h <= 11000.0:
        T = 288.15 - 0.0065 * h
        p = 101325.0 * (T / 288.15) ** 5.2561
    else:
        T = 216.65
        p = 22632.0 * np.exp(-0.0001577 * (h - 11000.0))
    rho = p / (287.0 * T)
    a = (1.4 * 287.0 * T) ** 0.5
    return float(rho), float(T), float(a)


# REQUISITOS DE MISIÓN + ENVELOPE TÁCTICO
@dataclass
class MissionConfig:
    # --- Envelope táctico ---
    h_cruise_m: float = 13000.0
    m_cruise: float = 0.80
    h_combat_m: float = 10000.0
    m_combat: float = 0.85
    n_combat: float = 3.0

    # --- Requisitos de misión ---
    range_km: float = 4300.0
    payload_kg: float = 600.0
    loiter_min: float = 60.0

    # --- Segmento de combate ---
    t_combat_s: float = 300.0
    thrust_combat_frac: float = 0.90
    tsfc_combat_factor: float = 2.5

    # --- Fracciones de combustible históricas (Raymer Tabla 6.2) ---
    f_warmup: float = 0.985
    f_to: float = 0.97
    f_climb: float = 0.985
    f_desc: float = 0.99
    f_land: float = 0.995

    def atmosphere(self) -> dict:
        rho_cr, T_cr, a_cr = isa_state(self.h_cruise_m)
        rho_co, T_co, a_co = isa_state(self.h_combat_m)
        return {
            "rho_cruise": rho_cr, "T_cruise": T_cr, "a_cruise": a_cr,
            "v_cruise": self.m_cruise * a_cr,
            "rho_combat": rho_co, "T_combat": T_co, "a_combat": a_co,
            "v_combat": self.m_combat * a_co,
        }


# PARÁMETROS FIJOS DE LA AERONAVE
@dataclass
class AircraftParams:
    t_c_ratio: float = 0.065
    sweep_angle_deg: float = 35.0
    fuselage_length_m: float = 9.0
    fuselage_diameter_m: float = 1.5
    n_ult: float = 10.0
    w_avionics_kg: float = 250.0
    cl_max_airfoil: float = 1.85
    rho_sl: float = 1.225
    tsfc_sl: float = 1.35e-5


# PARÁMETROS ECONÓMICOS Y FACTOR AFFORDABLE MASS
@dataclass
class CostParams:
    q_prod: float = 100.0
    k_no_cockpit: float = 0.95
    k_no_life_support: float = 0.97
    k_no_civil_cert: float = 0.90
    k_reduced_avionics: float = 0.96
    k_simplified_struct: float = 0.96


# PARÁMETROS DE ESTABILIDAD/CONTROL
@dataclass
class StabilityParams:
    cm_ac_wing: float = -0.10
    cl_landing: float = 1.3
    cg_fwd_loading_margin: float = 0.10
    cl_max_to: float = 1.6
    cl_to: float = 0.7
    mg_cg_offset_frac_mac: float = 0.12
    mg_ac_offset_frac_mac: float = 0.10


# VARIABLES DE DISEÑO Y RESTRICCIONES
@dataclass
class DesignVar:
    """Una variable de diseño del optimizador. `enabled=False` => parámetro fijo."""
    name: str
    lower: float
    upper: float
    ref: float
    units: Optional[str] = None
    enabled: bool = True
    label: str = ""


@dataclass
class Constraint:
    """Una restricción del optimizador (lower y/o upper). `enabled=False` la desactiva."""
    name: str
    lower: Optional[float] = None
    upper: Optional[float] = None
    ref: float = 1.0
    enabled: bool = True
    label: str = ""


@dataclass
class OptConfig:
    optimizer: str = "SLSQP"
    tol: float = 1e-6
    disp: bool = True
    objective: str = "cost.unit_cost_mUSD"
    objective_ref: float = 10.0
    objective_label: str = r"Coste unitario [M\$]"
    mtow_init: float = 3200.0
    t_sl_init: float = 15000.0


def _default_design_vars() -> list[DesignVar]:
    return [
        DesignVar("wing_area", 9.0, 16.0, 10.0, units="m**2",
                  label="Superficie alar S [m²]"),
        DesignVar("t_sl", 8000.0, 20000.0, 16000.0, units="N",
                  label="Empuje SL [N]"),
        DesignVar("v_ht", 0.20, 0.70, 0.45,
                  label="Coef. volumétrico cola V_HT"),
        DesignVar("aspect_ratio", 3.0, 4.5, 3.5,
                  label="Alargamiento AR"),
        DesignVar("taper_ratio", 0.20, 0.35, 0.25,
                  label="Estrechamiento λ"),
        DesignVar("x_wing_frac", 0.40, 0.58, 0.50,
                  label="Posición ala x_w/L_f"),
        DesignVar("frac_fuel_fuse", 0.0, 0.80, 0.40,
                  label="Fracción fuel en fuselaje"),
        DesignVar("x_fuel_fuse_frac", 0.45, 0.68, 0.55,
                  label="Centro tanque fuselaje x/L_f"),
        DesignVar("x_payload_offset_frac", 0.0, 0.15, 0.08,
                  label="Offset bahía armas / L_f"),
    ]


def _default_constraints() -> list[Constraint]:
    return [
        Constraint("perf.s_to", upper=900.0, ref=900.0,
                   label="Distancia despegue [m]"),
        Constraint("perf.s_land", upper=900.0, ref=900.0,
                   label="Distancia aterrizaje [m]"),
        Constraint("perf.n_turn", lower=3.5, ref=3.5,
                   label="Giro sostenido n [g]"),
        Constraint("perf.roc", lower=15.0, ref=30.0,
                   label="Tasa de ascenso RoC [m/s]"),
        Constraint("perf.P_s", lower=-10.0, ref=25.0,
                   label="Exceso potencia P_s [m/s]"),
        Constraint("stab.sm_full", lower=-0.03, upper=0.02, ref=0.03,
                   label="Margen estático (full)"),
        Constraint("stab.sm_empty", lower=-0.03, upper=0.02, ref=0.03,
                   label="Margen estático (empty)"),
        Constraint("stab.sm_aft", lower=-0.03, ref=0.03,
                   label="Margen estático (aft-crítico)"),
        Constraint("stab.cg_excursion_pct_mac", lower=-0.03, upper=0.03, ref=0.03,
                   label="Excursión CG / MAC"),
        Constraint("stab.payload_cg_offset", lower=-0.20, upper=0.20, ref=0.1,
                   label="Offset payload-CG [m]"),
        Constraint("stab.cn_beta", lower=0.08, ref=0.10,
                   label="Estabilidad direccional Cn_β"),
        Constraint("cycle.aero.M_dd", lower=0.78, ref=0.80,
                   label="Mach divergencia M_dd"),
        Constraint("perf.stall_margin", lower=0.05, ref=0.10,
                   label="Margen de entrada en pérdida"),
        Constraint("stab.cl_tail_required", lower=-0.8, upper=0.8, ref=0.5,
                   label="CL cola (trim aterrizaje)"),
        Constraint("stab.cl_tail_rotation_req", lower=-0.8, upper=0.8, ref=0.5,
                   label="CL cola (rotación despegue)"),
        Constraint("fuel_vol.margin_wing_tank", lower=0.0, ref=0.5,
                   label="Margen tanque alar [m³]"),
        Constraint("fuel_vol.margin_fuse_tank", lower=0.0, ref=1.0,
                   label="Margen tanque fuselaje [m³]"),
        Constraint("cycle.geom.wingspan", upper=8.0, ref=7.5,
                   label="Envergadura b [m]"),
    ]


# CONFIGURACIÓN COMPLETA
@dataclass
class FullConfig:
    mission: MissionConfig = field(default_factory=MissionConfig)
    aircraft: AircraftParams = field(default_factory=AircraftParams)
    cost: CostParams = field(default_factory=CostParams)
    stability: StabilityParams = field(default_factory=StabilityParams)
    design_vars: list[DesignVar] = field(default_factory=_default_design_vars)
    constraints: list[Constraint] = field(default_factory=_default_constraints)
    opt: OptConfig = field(default_factory=OptConfig)

    def copy(self) -> "FullConfig":
        """Copia profunda (para que la GUI no mute la configuración base)."""
        return FullConfig(
            mission=replace(self.mission),
            aircraft=replace(self.aircraft),
            cost=replace(self.cost),
            stability=replace(self.stability),
            design_vars=[replace(dv) for dv in self.design_vars],
            constraints=[replace(c) for c in self.constraints],
            opt=replace(self.opt),
        )


def default_config() -> FullConfig:
    """Configuración nominal — CCA tier-2."""
    cfg = _preset(
        13000.0, 0.80, 8000.0, 0.85, 2.0, 4300.0, 600.0, 60.0,
        mtow_init=3200.0,
        n_turn_lower=3.0,
        roc_lower=15.0,
        ps_lower=-10.0,
    )
    cfg.constraints.append(
        Constraint("perf.cruise_margin", lower=0.0, ref=0.10,
                   label="Margen crucero nivelado T/D − 1")
    )
    return cfg


# PRESETS DE REFERENCIA
def _preset(h_cr, m_cr, h_co, m_co, n_co, range_km, payload, loiter_min, *,
            t_sl_pub=None,
            t_sl_lower=None,
            t_sl_upper=None,
            mtow_init=3200.0,
            wingspan_upper=None,
            fuselage_length=None,
            fuselage_diameter=None,
            tsfc_sl=None,
            s_to_enabled=True,
            roc_lower=None,
            ps_lower=None,
            n_turn_lower=None,
            ) -> FullConfig:
    cfg = FullConfig()
    cfg.mission = MissionConfig(
        h_cruise_m=h_cr, m_cruise=m_cr,
        h_combat_m=h_co, m_combat=m_co, n_combat=n_co,
        range_km=range_km, payload_kg=payload, loiter_min=loiter_min,
    )
    cfg.opt.mtow_init = mtow_init

    if fuselage_length is not None:
        cfg.aircraft.fuselage_length_m = fuselage_length
    if fuselage_diameter is not None:
        cfg.aircraft.fuselage_diameter_m = fuselage_diameter
    if tsfc_sl is not None:
        cfg.aircraft.tsfc_sl = tsfc_sl
    if t_sl_pub is not None:
        cfg.opt.t_sl_init = float(t_sl_pub)

    for dv in cfg.design_vars:
        if dv.name == "t_sl" and t_sl_pub is not None:
            dv.lower = float(t_sl_lower)
            dv.upper = float(t_sl_upper)
            dv.ref   = float(t_sl_pub)

    for c in cfg.constraints:
        if c.name == "perf.n_turn":
            if n_turn_lower is not None:
                c.lower = c.ref = float(n_turn_lower)
        if c.name == "cycle.geom.wingspan" and wingspan_upper is not None:
            c.upper = float(wingspan_upper)
        if c.name == "perf.s_to":
            c.enabled = s_to_enabled
        if c.name == "perf.roc" and roc_lower is not None:
            c.lower = float(roc_lower)
            c.ref   = max(c.ref, float(roc_lower))
        if c.name == "perf.P_s" and ps_lower is not None:
            c.lower = float(ps_lower)

    return cfg


PRESETS: dict[str, FullConfig] = {
    "Nominal (CCA tier-2)": default_config(),

    # ── XQ-58A Valkyrie (Kratos Defense) ─────────────────────────────────────
    "XQ-58A Valkyrie": _preset(
        13000.0, 0.72, 9000.0, 0.85, 1.5, 5556.0, 544.0, 60.0,
        t_sl_pub       = 8_900.0,
        t_sl_lower     = 8_000.0,
        t_sl_upper     = 11_000.0,
        mtow_init      = 2_722.0,
        wingspan_upper = 8.2,
        fuselage_diameter = 1.4,
        tsfc_sl        = 1.33e-5,
        s_to_enabled   = False,
        n_turn_lower   = 2.0,
        roc_lower      = 8.0,
        ps_lower       = -50.0,
    ),

    # ── MQ-28A Ghost Bat (Boeing Australia) ──────────────────────────────────
    "MQ-28A Ghost Bat": _preset(
        14000.0, 0.78, 10000.0, 0.85, 2.5, 3700.0, 1400.0, 60.0,
        mtow_init      = 4_500.0,
        wingspan_upper = 7.3,
        fuselage_length= 11.7,
        fuselage_diameter = 1.4,
        n_turn_lower   = 3.0,
        ps_lower       = -35.0,
    ),

    # ── YFQ-44A Fury (Anduril Industries) ────────────────────────────────────
    "YFQ-44A Fury": _preset(
        14000.0, 0.85, 9000.0, 0.95, 3.0, 3200.0, 300.0, 60.0,
        t_sl_pub       = 17_800.0,
        t_sl_lower     = 14_000.0,
        t_sl_upper     = 21_000.0,
        mtow_init      = 2200.0,
        wingspan_upper = 6.4,
        fuselage_length= 7.5,
        fuselage_diameter = 1.4,
        tsfc_sl        = 1.30e-5,
        n_turn_lower   = 4.5,
        ps_lower       = -40.0,
    ),
}
