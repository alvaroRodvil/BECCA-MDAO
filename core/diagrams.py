"""
Datos para las gráficas aeronáuticas (capa Model).

Funciones puras que, a partir de un `ResultsDTO` + `FullConfig`, devuelven
arrays/dicts listos para dibujar. Toda la física vive aquí; el dibujado
matplotlib vive en gui/plots.py.

Orden de secciones:
  1 · Validación del optimizador
  2 · Síntesis multidisciplinar
  3 · Rendimiento y combate
  4 · Operación y misión
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from core.config import FullConfig, isa_state
from core.results import ResultsDTO

G = 9.81
RHO_SL = 1.225
A_SL = 340.3
RHO_FUEL = 800.0
KAPPA_KORN = 0.95
DELTA_CL_TO = 0.30
DELTA_CL_L = 0.60


def _cbound(config: FullConfig, name: str, which: str = "lower") -> Optional[float]:
    for c in config.constraints:
        if c.name == name and c.enabled:
            return c.lower if which == "lower" else c.upper
    return None


def perf_params(dto: ResultsDTO, config: FullConfig) -> dict:
    """Parámetros aerodinámicos del diseño óptimo usados por las gráficas."""
    AR = dto.get("aspect_ratio")
    e = dto.get("cycle.aero.e_oswald")
    cd0 = dto.get("cycle.aero.cd0")
    K = 1.0 / (math.pi * AR * e)

    sweep_rad = math.radians(config.aircraft.sweep_angle_deg)
    cl_max_clean = config.aircraft.cl_max_airfoil * math.cos(sweep_rad)
    cl_to = cl_max_clean + DELTA_CL_TO
    cl_l = cl_max_clean + DELTA_CL_L

    atm = config.mission.atmosphere()
    return {
        "AR": AR, "e": e, "cd0": cd0, "K": K,
        "cl_max_clean": cl_max_clean, "cl_to": cl_to, "cl_l": cl_l,
        "mtow": dto.get("cycle.mtow_sum.mtow_calc"),
        "w_fuel": dto.get("cycle.miss.w_fuel"),
        "S": dto.get("wing_area"),
        "t_sl": dto.get("t_sl"),
        "rho_combat": atm["rho_combat"], "v_combat": atm["v_combat"],
        "m_combat": config.mission.m_combat, "n_combat": config.mission.n_combat,
    }


# 1 · VALIDACIÓN DEL OPTIMIZADOR
def dv_history(dto: ResultsDTO) -> dict:
    """Evolución normalizada de cada variable de diseño por iteración."""
    hist = dto.history.get("desvars", {})
    iters = dto.history.get("iterations", [])
    series = {}
    for name, arr in hist.items():
        a = np.asarray(arr, dtype=float)
        ref = a[-1] if len(a) and abs(a[-1]) > 1e-12 else (np.nanmax(np.abs(a)) or 1.0)
        series[name] = a / ref
    return {"iterations": iters, "series": series}


def convergence_detail(dto: ResultsDTO, config: FullConfig) -> dict:
    """Objetivo + máxima infactibilidad de restricciones por iteración."""
    hist = dto.history
    iters = hist.get("iterations", [])
    obj = hist.get("objective", {})
    obj_name, obj_series = (next(iter(obj.items())) if obj else ("obj", []))
    cons = hist.get("constraints", {})

    bounds = {c.name: (c.lower, c.upper, max(abs(c.ref), 1e-9))
              for c in config.constraints if c.enabled}
    n = len(iters)
    infeas = []
    for k in range(n):
        worst = 0.0
        for name, series in cons.items():
            if name not in bounds or k >= len(series):
                continue
            lo, hi, scale = bounds[name]
            val = series[k]
            v = 0.0
            if lo is not None:
                v = max(v, (lo - val) / scale)
            if hi is not None:
                v = max(v, (val - hi) / scale)
            worst = max(worst, v)
        infeas.append(worst)
    return {"iterations": iters, "objective": list(obj_series),
            "objective_label": config.opt.objective_label, "infeas": infeas}


# 2 · SÍNTESIS MULTIDISCIPLINAR
def weight_breakdown(dto: ResultsDTO) -> dict:
    oew = dto.get("cost.oew_partial") + dto.get("cost.w_engine")
    w_wing = dto.get("cycle.weight.w_wing")
    w_fuse = dto.get("cycle.weight.w_fuse")
    w_vtail = dto.get("cycle.weight.w_vtail")
    w_lg = dto.get("cycle.weight.w_lg")
    w_sys = dto.get("cycle.weight.w_systems")
    w_eng = dto.get("cycle.prop.w_engine")
    w_avi = (dto.get("cost.oew_partial") - w_wing - w_fuse - w_vtail - w_lg - w_sys)

    groups = {
        "OEW (vacío)": oew,
        "Fuel Weight": dto.get("cycle.miss.w_fuel"),
        "Payload": dto.get("w_weapons"),
    }
    components = {
        "Ala": w_wing,
        "Fuselaje": w_fuse,
        "Cola V": w_vtail,
        "Tren": w_lg,
        "Subsistemas": w_sys,
        "Motor": w_eng,
        "Aviónica": w_avi,
    }
    return {"groups": groups, "components": components,
            "mtow": dto.get("cycle.mtow_sum.mtow_calc")}


def drag_polar(dto: ResultsDTO, config: FullConfig) -> dict:
    p = perf_params(dto, config)
    cd0, K = p["cd0"], p["K"]
    cl_max = p["cl_max_clean"]
    cl_top = max(1.2, cl_max * 1.12)
    cl = np.linspace(0.0, cl_top, 220)
    cd = cd0 + K * cl**2
    cl_ld_max = math.sqrt(cd0 / K)
    return {
        "cl": cl, "cd": cd, "cd0": cd0, "K": K, "cl_max": cl_max,
        "cl_cruise": dto.get("cycle.aero.CL_cruise"),
        "cd_cruise": cd0 + K * dto.get("cycle.aero.CL_cruise")**2,
        "cl_ld_max": cl_ld_max,
        "cd_ld_max": cd0 + K * cl_ld_max**2,
        "ld_max": dto.get("cycle.aero.L_D_max"),
    }


def cd0_buildup(dto: ResultsDTO, config: FullConfig) -> dict:
    """Contribución de cada componente al CD0 (Component Buildup, Raymer)."""
    comps = {
        "Ala": dto.get("cycle.aero.cd0_wing"),
        "Fuselaje": dto.get("cycle.aero.cd0_fuse"),
        "Cola en V": dto.get("cycle.aero.cd0_vtail"),
        "Misceláneos": dto.get("cycle.aero.cd0_misc"),
        "Excrec. + S-duct": dto.get("cycle.aero.cd0_other"),
    }
    return {"components": comps, "total": dto.get("cycle.aero.cd0"),
            "sweep_deg": config.aircraft.sweep_angle_deg,
            "t_c": config.aircraft.t_c_ratio}


def _cd_wave(M, CL, sweep_rad, t_c):
    cos_s = math.cos(sweep_rad)
    m_dd = (KAPPA_KORN / cos_s) - (t_c / cos_s**2) - (CL / (10.0 * cos_s**3))
    m_dd = min(m_dd, 0.95)
    m_cr = m_dd - (0.1 / 80.0)**(1.0 / 3.0)
    dM = M - m_cr
    return 20.0 * dM**4 if dM > 0 else 0.0


def ld_vs_mach(dto: ResultsDTO, config: FullConfig, altitudes_m=None) -> dict:
    """L/D(M) para varias altitudes usando CD0/K del óptimo + onda Korn-Mason."""
    p = perf_params(dto, config)
    cd0, K = p["cd0"], p["K"]
    sweep_rad = math.radians(config.aircraft.sweep_angle_deg)
    t_c = config.aircraft.t_c_ratio
    W = p["mtow"] * G
    S = p["S"]
    if altitudes_m is None:
        altitudes_m = sorted({8000.0, config.mission.h_cruise_m, 16000.0})

    mach = np.linspace(0.30, 1.00, 180)
    curves = {}
    for h in altitudes_m:
        rho, T, a = isa_state(h)
        ld = []
        for M in mach:
            V = M * a
            q = 0.5 * rho * V**2
            CL = W / (q * S)
            cdw = _cd_wave(M, CL, sweep_rad, t_c)
            cd = cd0 + K * CL**2 + cdw
            ld.append(CL / cd)
        curves[h] = np.array(ld)

    return {
        "mach": mach, "curves": curves,
        "design": (config.mission.m_cruise, dto.get("cycle.aero.L_D")),
        "h_cruise": config.mission.h_cruise_m,
    }


def spanwise_lift(dto: ResultsDTO, config: FullConfig, n=120) -> dict:
    """Aproximación de Schrenk: media entre carga trapezoidal y elíptica ideal."""
    b = dto.get("cycle.geom.wingspan")
    c_root = dto.get("cycle.geom.root_chord")
    c_tip = dto.get("cycle.geom.tip_chord")
    semi = b / 2.0

    eta = np.linspace(0.0, 1.0, n)
    c_local = c_root + (c_tip - c_root) * eta
    load_trap = c_local / np.trapezoid(c_local, eta)
    ell = np.sqrt(np.clip(1.0 - eta**2, 0.0, None))
    load_ell = ell / np.trapezoid(ell, eta)
    load_schrenk = 0.5 * (load_trap + load_ell)
    load_schrenk /= np.trapezoid(load_schrenk, eta)

    return {
        "eta": eta, "trap": load_trap, "ell": load_ell, "schrenk": load_schrenk,
        "semi": semi, "sweep_deg": config.aircraft.sweep_angle_deg,
    }


def cm_cl(dto: ResultsDTO, config: FullConfig) -> dict:
    """Cm(CL) en torno al CG. Pendiente dCm/dCL = −SM."""
    cl_max = perf_params(dto, config)["cl_max_clean"]
    cl = np.linspace(0.0, cl_max, 60)
    cm0 = config.stability.cm_ac_wing
    sm_full = dto.get("stab.sm_full")
    sm_empty = dto.get("stab.sm_empty")
    sm_aft = dto.get("stab.sm_aft")
    return {
        "cl": cl,
        "cm_full": cm0 - sm_full * cl,
        "cm_empty": cm0 - sm_empty * cl,
        "cm_aft": cm0 - sm_aft * cl,
        "cm0": cm0,
        "sm_full": sm_full * 100.0, "sm_empty": sm_empty * 100.0,
        "sm_aft": sm_aft * 100.0,
    }


def vn_diagram(dto: ResultsDTO, config: FullConfig,
               safety_factor: float = 1.5) -> dict:
    """Diagrama V-n con carga límite y última, zonas de operación y stall asimétrico.

    Velocidades en EAS. V_D atado a M_dd a nivel del mar; V_C = V_D/1.25 (FAR 25.335)."""
    p = perf_params(dto, config)
    W_S = p["mtow"] * G / p["S"]
    cl_max = p["cl_max_clean"]

    n_ult_pos = config.aircraft.n_ult
    n_lim_pos = n_ult_pos / safety_factor
    n_lim_neg = -0.4 * n_lim_pos
    n_ult_neg = safety_factor * n_lim_neg

    v_s = math.sqrt(2.0 * W_S / (RHO_SL * cl_max))
    v_a = v_s * math.sqrt(n_lim_pos)
    v_s_neg = v_s * math.sqrt(n_lim_pos / abs(n_lim_neg))

    m_dd = dto.get("cycle.aero.M_dd")
    v_d = m_dd * A_SL
    v_c = v_d / 1.25

    v_max = 1.06 * v_d
    v = np.linspace(0.0, v_max, 400)
    n_par_pos = 0.5 * RHO_SL * v**2 * cl_max / W_S
    n_par_neg = -0.5 * RHO_SL * (v / v_s_neg * v_s)**2 * cl_max / W_S

    return {
        "v": v, "n_par_pos": n_par_pos, "n_par_neg": n_par_neg,
        "n_lim_pos": n_lim_pos, "n_lim_neg": n_lim_neg,
        "n_ult_pos": n_ult_pos, "n_ult_neg": n_ult_neg,
        "v_s": v_s, "v_s_neg": v_s_neg, "v_a": v_a, "v_c": v_c, "v_d": v_d,
        "v_max": v_max, "m_dd": m_dd, "safety_factor": safety_factor,
    }


def cg_travel(dto: ResultsDTO, config: FullConfig) -> dict:
    """Recorrido del CG (%MAC) con secuencia de vaciado: fuselaje primero.

    El estado aft-crítico (fuselaje vacío + ala llena + armamento soltado)
    marca el SM mínimo de la misión, restringido en el MDAO (stab.sm_aft)."""
    L_f = config.aircraft.fuselage_length_m
    mac = dto.get("cycle.geom.mac")
    x_wing = dto.get("x_wing_frac") * L_f
    f_fuse = dto.get("frac_fuel_fuse")
    x_ffuse = dto.get("stab.x_fuel_fuse")
    x_payload = (dto.get("x_wing_frac") - dto.get("x_payload_offset_frac")) * L_f

    w_oew = dto.get("cost.oew_partial") + dto.get("cost.w_engine")
    x_cg_empty = dto.get("stab.x_cg_empty")
    w_fuel = dto.get("cycle.miss.w_fuel")
    w_pay = dto.get("w_weapons")
    W_wing0 = (1.0 - f_fuse) * w_fuel
    W_fuse0 = f_fuse * w_fuel
    reserve = 0.15 / 1.15

    x_le_mac_abs = (dto.get("stab.x_cg_full")
                    - dto.get("stab.cg_full_pct_mac") * mac)

    def cg_and_w(ww, wf, has_pay):
        M = (w_oew * x_cg_empty + ww * x_wing + wf * x_ffuse
             + (w_pay * x_payload if has_pay else 0.0))
        W = w_oew + ww + wf + (w_pay if has_pay else 0.0)
        return (M / W - x_le_mac_abs) / mac * 100.0, W

    seq = [
        ("MTOW", W_wing0, W_fuse0, True),
        ("Crucero ida", W_wing0, 0.40 * W_fuse0, True),
        ("Loiter", W_wing0, 0.10 * W_fuse0, True),
        ("Soltado de armas", W_wing0, 0.0, False),          # ← aft-crítico
        ("Crucero regreso", 0.45 * W_wing0, 0.0, False),
        ("Reserva", reserve * W_wing0, 0.0, False),
    ]
    states = [(lbl, *cg_and_w(ww, wf, hp)) for (lbl, ww, wf, hp) in seq]

    np_pct = (dto.get("stab.x_np") - x_le_mac_abs) / mac * 100.0
    band = (-3.0, 2.0)
    for c in config.constraints:
        if c.name == "stab.sm_empty" and c.enabled:
            band = ((c.lower or -0.03) * 100.0, (c.upper or 0.02) * 100.0)

    cgs = [s[1] for s in states]
    cg_aft = dto.get("stab.cg_aft_pct_mac") * 100.0
    sm_aft = dto.get("stab.sm_aft") * 100.0
    return {
        "states": states,
        "excursion": max(cgs) - min(cgs),
        "cg_aft": cg_aft, "sm_aft": sm_aft,
        "np_pct": np_pct, "band": band,
        "tank_sep_pct": abs(x_wing - x_ffuse) / mac * 100.0,
        "burn_order": "fuselaje primero (alivio de flexión del ala)",
    }


# 3 · RENDIMIENTO Y COMBATE
def _s_takeoff(W_S, T_W, p):
    """Distancia de despegue [m] (port de performance.py)."""
    cl_to, cd0, K = p["cl_to"], p["cd0"], p["K"]
    v_stall = math.sqrt(2.0 * W_S / (RHO_SL * cl_to))
    v_lof = 1.10 * v_stall
    mu = 0.04
    v_avg = v_lof / math.sqrt(2.0)
    q_avg = 0.5 * RHO_SL * v_avg**2
    cl_g = 0.1 * cl_to
    cd_g = cd0 + K * cl_g**2
    M_avg = v_avg / A_SL
    lapse = 1.0 - 0.49 * math.sqrt(M_avg)
    accel = G * (T_W * lapse - mu) - G * q_avg * (cd_g - mu * cl_g) / W_S
    if accel <= 0:
        return 1.0e9
    s_ground = v_lof**2 / (2.0 * accel)
    s_rot = 3.0 * v_lof
    cl_2 = cl_to / 1.15**2
    cd_2 = cd0 + K * cl_2**2
    gamma = T_W - cd_2 / cl_2
    gamma_safe = 0.5 * (gamma + math.sqrt(gamma**2 + 1.0e-6)) + 1.0e-3
    return s_ground + s_rot + 15.2 / gamma_safe


def _tw_takeoff_required(W_S, p, s_limit):
    """T/W mínimo para cumplir s_to ≤ s_limit a un W/S dado (bisección)."""
    lo, hi = 0.05, 2.5
    if _s_takeoff(W_S, hi, p) > s_limit:
        return float("nan")
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        if _s_takeoff(W_S, mid, p) > s_limit:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _s_landing(W_S_land, p):
    """Distancia de aterrizaje [m] a un W/S de aterrizaje dado."""
    cl_l = p["cl_l"]
    v_stall = math.sqrt(2.0 * W_S_land / (RHO_SL * cl_l))
    v_app = 1.30 * v_stall
    v_td = 1.15 * v_stall
    gamma_app = math.radians(3.0)
    R = v_app**2 / (G * 0.2)
    h_flare = R * (1.0 - math.cos(gamma_app))
    s_app = (15.2 - h_flare) / math.tan(gamma_app)
    s_flare = R * math.sin(gamma_app)
    s_ground = v_td**2 / (2.0 * 0.30 * G)
    return s_app + s_flare + s_ground


def constraint_diagram(dto: ResultsDTO, config: FullConfig) -> dict:
    """Diagrama T/W requerido vs W/S (kg/m²) para cada restricción + punto diseño."""
    p = perf_params(dto, config)
    g = G

    ws_design_kg = p["mtow"] / p["S"]
    tw_design = p["t_sl"] / (p["mtow"] * g)

    ws_kg = np.linspace(max(60.0, 0.45 * ws_design_kg),
                        2.0 * ws_design_kg, 260)
    ws_N = ws_kg * g

    cd0, K = p["cd0"], p["K"]
    curves: dict[str, np.ndarray] = {}

    # --- Giro sostenido (n ≥ n_req @ 160 m/s SL) ---
    n_req = _cbound(config, "perf.n_turn", "lower") or 4.0
    v_t = 160.0
    q_t = 0.5 * RHO_SL * v_t**2
    lapse_t = 1.0 - 0.49 * math.sqrt(v_t / A_SL)
    curves[rf"Giro sostenido $n\geq{n_req:g}$g"] = (
        (q_t * cd0 / ws_N + K * n_req**2 * ws_N / q_t) / lapse_t)

    # --- Ascenso (RoC ≥ req @ 130 m/s SL) ---
    roc_req = _cbound(config, "perf.roc", "lower") or 15.0
    v_c = 130.0
    q_c = 0.5 * RHO_SL * v_c**2
    lapse_c = 1.0 - 0.49 * math.sqrt(v_c / A_SL)
    curves[rf"Ascenso $RoC\geq{roc_req:g}$ m/s"] = (
        (roc_req / v_c + q_c * cd0 / ws_N + K * ws_N / q_c) / lapse_c)

    # --- Exceso de potencia P_s (combate) ---
    ps_req = _cbound(config, "perf.P_s", "lower")
    if ps_req is not None:
        rho_co, v_co, n_co = p["rho_combat"], p["v_combat"], p["n_combat"]
        q_co = 0.5 * rho_co * v_co**2
        lapse_co = (rho_co / RHO_SL)**0.7 * (1.0 - 0.49 * math.sqrt(p["m_combat"]))
        D_W = q_co * cd0 / ws_N + K * n_co**2 * ws_N / q_co
        curves[rf"$P_s\geq{ps_req:g}$ m/s (combate)"] = (ps_req / v_co + D_W) / lapse_co

    # --- Despegue (s_to ≤ límite) ---
    s_to_lim = _cbound(config, "perf.s_to", "upper")
    if s_to_lim is not None:
        tw_to = np.array([_tw_takeoff_required(w, p, s_to_lim) for w in ws_N])
        curves[rf"Despegue $s\leq{s_to_lim:g}$ m"] = tw_to

    # --- Crucero nivelado — Raymer §5.3, Mattingly §2.2 ---
    #   T_SL/W_TO = [q·CD0/(W_TO/S) + K·β²·(W_TO/S)/q] / α
    m = config.mission
    beta_cr = m.f_warmup * m.f_to * m.f_climb
    atm = config.mission.atmosphere()
    rho_cr, v_cr, M_cr = atm["rho_cruise"], atm["v_cruise"], config.mission.m_cruise
    q_cr = 0.5 * rho_cr * v_cr**2
    lapse_cr = (rho_cr / RHO_SL)**0.7 * (1.0 - 0.49 * math.sqrt(M_cr))
    curves[rf"Crucero nivelado ($\beta$={beta_cr:.3f})"] = (
        (q_cr * cd0 / ws_N + K * beta_cr**2 * ws_N / q_cr) / lapse_cr)

    
    vlines: dict[str, float] = {}

    V_APP_MAX = 80.0
    V_STALL_REF = V_APP_MAX / 1.30
    ws_stall_N = 0.5 * RHO_SL * V_STALL_REF**2 * p["cl_l"]
    vlines[rf"Pérdida ($V_S\leq{V_STALL_REF:.0f}$ m/s)"] = ws_stall_N / g
    s_land_lim = _cbound(config, "perf.s_land", "upper")
    if s_land_lim is not None:
        lo, hi = 50.0, 4000.0
        for _ in range(50):
            mid = 0.5 * (lo + hi)
            if _s_landing(mid, p) > s_land_lim:
                hi = mid
            else:
                lo = mid
        ws_land_N = 0.5 * (lo + hi)
        frac_land = max(0.3, (p["mtow"] - p["w_fuel"]) / p["mtow"])
        vlines[rf"Aterrizaje $s\leq{s_land_lim:g}$ m"] = (ws_land_N / frac_land) / g

    return {
        "ws_kg": ws_kg,
        "curves": curves,
        "vlines": vlines,
        "design": (ws_design_kg, tw_design),
    }


def flight_envelope_ps(dto: ResultsDTO, config: FullConfig,
                       n_h=200, n_m=200) -> dict:
    """Exceso de potencia específica P_s(h, M) en vuelo nivelado (n=1)."""
    p = perf_params(dto, config)
    cd0, K = p["cd0"], p["K"]
    sweep_rad = math.radians(config.aircraft.sweep_angle_deg)
    t_c = config.aircraft.t_c_ratio
    W = p["mtow"] * G
    S = p["S"]
    t_sl = p["t_sl"]

    h_arr = np.linspace(0.0, 18000.0, n_h)
    m_arr = np.linspace(0.15, 0.95, n_m)
    PS = np.full((n_h, n_m), np.nan)

    for i, h in enumerate(h_arr):
        rho, T, a = isa_state(h)
        sigma = rho / RHO_SL
        for j, M in enumerate(m_arr):
            V = M * a
            q = 0.5 * rho * V**2
            CL = W / (q * S)
            if CL > 1.4:
                continue
            cdw = _cd_wave(M, CL, sweep_rad, t_c)
            D = q * S * (cd0 + K * CL**2 + cdw)
            T_av = t_sl * sigma**0.7 * (1.0 - 0.49 * math.sqrt(M))
            PS[i, j] = V * (T_av - D) / W

    MM, HH = np.meshgrid(m_arr, h_arr / 1000.0)
    return {
        "M": MM, "H_km": HH, "PS": PS,
        "design": (config.mission.m_cruise, config.mission.h_cruise_m / 1000.0),
        "combat": (config.mission.m_combat, config.mission.h_combat_m / 1000.0),
    }


def thrust_curves(dto: ResultsDTO, config: FullConfig, altitudes_m=None) -> dict:
    p = perf_params(dto, config)
    cd0, K = p["cd0"], p["K"]
    sweep_rad = math.radians(config.aircraft.sweep_angle_deg)
    t_c = config.aircraft.t_c_ratio
    W = p["mtow"] * G
    S = p["S"]
    t_sl = p["t_sl"]
    if altitudes_m is None:
        altitudes_m = sorted(set([0.0, config.mission.h_combat_m,
                                  config.mission.h_cruise_m]))

    cl_max = p["cl_max_clean"]
    out = {}
    for h in altitudes_m:
        rho, T, a = isa_state(h)
        sigma = rho / RHO_SL
        v_stall = math.sqrt(2.0 * (W / S) / (rho * cl_max))
        v = np.linspace(v_stall, 0.98 * a, 200)
        q = 0.5 * rho * v**2
        CL = W / (q * S)
        M = v / a
        cdw = np.array([_cd_wave(mi, cli, sweep_rad, t_c) for mi, cli in zip(M, CL)])
        TR = q * S * (cd0 + K * CL**2 + cdw)
        TA = t_sl * sigma**0.7 * (1.0 - 0.49 * np.sqrt(M))
        out[h] = {"v": v, "TR": TR, "TA": TA, "a": a, "v_stall": v_stall}
    return {"curves": out, "t_sl": t_sl}


def turn_rate(dto: ResultsDTO, config: FullConfig, altitude_m=None) -> dict:
    p = perf_params(dto, config)
    cd0, K = p["cd0"], p["K"]
    W = p["mtow"] * G
    S = p["S"]
    t_sl = p["t_sl"]
    cl_max = p["cl_max_clean"]
    n_struct = config.aircraft.n_ult / 1.5
    if altitude_m is None:
        altitude_m = config.mission.h_combat_m
    rho, T, a = isa_state(altitude_m)
    sigma = rho / RHO_SL

    mach = np.linspace(0.2, 0.92, 160)
    v = mach * a
    q = 0.5 * rho * v**2

    # Instantáneo: limitado por CL_max y por estructura
    n_lift = q * cl_max * S / W
    n_inst = np.minimum(n_lift, n_struct)

    # Sostenido: T_disp = D(n) → límite por empuje
    T_av = t_sl * sigma**0.7 * (1.0 - 0.49 * np.sqrt(mach))
    n2 = (T_av - q * S * cd0) * (q * S) / (K * W**2)
    n_sus_thrust = np.sqrt(np.clip(n2, 0.0, None))
    n_sus = np.minimum(n_sus_thrust, n_inst)

    def omega(n):
        nn = np.clip(n, 1.0, None)
        return np.degrees(G * np.sqrt(nn**2 - 1.0) / v)

    return {
        "mach": mach, "v": v,
        "omega_sus": omega(n_sus), "omega_inst": omega(n_inst),
        "n_sus": n_sus, "n_inst": n_inst, "n_struct": n_struct,
        "altitude_km": altitude_m / 1000.0,
    }


# 4 · OPERACIÓN Y MISIÓN
def _breguet_range_km(W0, fuel_usable, LD, V, tsfc):
    if W0 <= 0 or fuel_usable <= 0 or LD <= 0:
        return 0.0
    W1 = W0 - fuel_usable
    if W1 <= 0:
        return 0.0
    R = (V * LD / (G * tsfc)) * math.log(W0 / W1)
    return R / 1000.0


def payload_range(dto: ResultsDTO, config: FullConfig) -> dict:
    """Diagrama payload-range clásico (3 tramos) + punto de diseño."""
    oew = dto.get("cost.oew_partial") + dto.get("cost.w_engine")
    mtow = dto.get("cycle.mtow_sum.mtow_calc")
    payload_max = dto.get("w_weapons")
    LD = dto.get("cycle.aero.L_D")
    tsfc = dto.get("cycle.prop.tsfc_avail")
    V = config.mission.atmosphere()["v_cruise"]
    fuel_max = (dto.get("cycle.geom.vol_wing_tank")
                + dto.get("cycle.geom.vol_fuse_tank")) * RHO_FUEL

    def usable(fuel):
        return fuel / 1.15

    # Punto A: payload máximo, fuel limitado por MTOW
    fuel1 = min(fuel_max, max(0.0, mtow - oew - payload_max))
    W0_1 = oew + payload_max + fuel1
    R1 = _breguet_range_km(W0_1, usable(fuel1), LD, V, tsfc)

    # Punto B: MTOW con tanques llenos → payload reducido
    payload2 = max(0.0, mtow - oew - fuel_max)
    R2 = _breguet_range_km(mtow, usable(fuel_max), LD, V, tsfc)

    # Punto C: ferry (sin payload, tanques llenos)
    W0_3 = oew + fuel_max
    R3 = _breguet_range_km(W0_3, usable(fuel_max), LD, V, tsfc)

    ranges = [0.0, R1, max(R1, R2), max(R1, R2, R3)]
    payloads = [payload_max, payload_max, payload2, 0.0]

    return {
        "ranges_km": ranges,
        "payloads_kg": payloads,
        "design": (config.mission.range_km, config.mission.payload_kg),
        "fuel_max_kg": fuel_max,
        "labels": ["A", "B", "C", "D"],
    }


def _combat_radius_km(P, F, oew, ld_cr, v, tsfc, f_wtc, f_dl, f_loiter, dc) -> float:
    """Radio de combate [km] resolviendo el balance de combustible ida-vuelta.

    Secuencia de masas (W0 = OEW + P + F):
        w1 = W0·f_wtc               (warmup+despegue+ascenso)
        w2 = w1·a                   (crucero IDA)
        w3 = w2·f_loiter            (loiter ISR)
        w4 = w3 − Δc               (combate)
        w5 = w4 − P                (soltado de armas)
        w6 = w5·a                  (crucero REGRESO)
        w7 = w6·f_dl               (descenso+aterrizaje)
    Condición de aterrizaje: w7 = OEW + reserva (cuadrática en a)."""
    if F <= 1.0e-6 or ld_cr <= 0 or tsfc <= 0:
        return 0.0
    k = G * tsfc / (v * ld_cr)
    W0 = oew + P + F
    reserve = 0.15 * F / 1.15
    A = f_dl * f_wtc * f_loiter * W0
    B = -f_dl * (dc + P)
    C = -(oew + reserve)
    disc = B * B - 4.0 * A * C
    if disc < 0.0 or A <= 0.0:
        return 0.0
    a = (-B + math.sqrt(disc)) / (2.0 * A)
    if a <= 0.0 or a >= 1.0:
        return 0.0
    return (-math.log(a) / k) / 1000.0


def payload_radius(dto: ResultsDTO, config: FullConfig) -> dict:
    """Diagrama Payload-Radius (radio de combate) con balance de misión real.

    Calcula radio táctico (con loiter + combate) e ideal (sin loiter ni combate)
    para los mismos vértices que payload-range."""
    m = config.mission
    oew = dto.get("cost.oew_partial") + dto.get("cost.w_engine")
    mtow = dto.get("cycle.mtow_sum.mtow_calc")
    payload_max = dto.get("w_weapons")
    LD_cr = dto.get("cycle.aero.L_D")
    LD_lo = dto.get("cycle.aero.L_D_max")
    tsfc = dto.get("cycle.prop.tsfc_avail")
    t_avail = dto.get("cycle.prop.t_avail")
    V = m.atmosphere()["v_cruise"]
    E = m.loiter_min * 60.0
    fuel_max = (dto.get("cycle.geom.vol_wing_tank")
                + dto.get("cycle.geom.vol_fuse_tank")) * RHO_FUEL

    f_wtc = m.f_warmup * m.f_to * m.f_climb
    f_dl = m.f_desc * m.f_land
    f_loiter = math.exp(-(E * tsfc * G) / LD_lo)
    dc = m.thrust_combat_frac * t_avail * (m.tsfc_combat_factor * tsfc) * m.t_combat_s

    fuel_B = min(fuel_max, max(0.0, mtow - oew - payload_max))
    payload_C = max(0.0, mtow - oew - fuel_max)
    points = [
        (payload_max, 0.0),
        (payload_max, fuel_B),
        (payload_C, fuel_max),
        (0.0, fuel_max),
    ]

    def radius(P, F, tactical):
        fl = f_loiter if tactical else 1.0
        cc = dc if tactical else 0.0
        return _combat_radius_km(P, F, oew, LD_cr, V, tsfc, f_wtc, f_dl, fl, cc)

    tactical_radius = [radius(P, F, True) for P, F in points]
    ideal_radius = [radius(P, F, False) for P, F in points]
    payloads = [P for P, _ in points]

    req_radius = m.range_km / 2.0
    d_pen = ideal_radius[1] - tactical_radius[1]

    return {
        "ideal_radius": ideal_radius, "tactical_radius": tactical_radius,
        "payloads_kg": payloads, "d_pen_km": d_pen,
        "req_radius_km": req_radius,
        "design": (req_radius, m.payload_kg),
        "labels": ["A", "B", "C", "D"],
    }


def _mission_phases(dto: ResultsDTO, config: FullConfig) -> dict:
    """Secuencia física de fases de misión compartida por los paneles de altitud y peso.

    El eje X es distancia recorrida (trayectoria). Las masas replican
    exactamente la secuencia de mission.py (w1..w7)."""
    m = config.mission
    g = G
    h_cr, h_co = m.h_cruise_m, m.h_combat_m
    atm = m.atmosphere()
    V_cr, V_co = atm["v_cruise"], atm["v_combat"]
    rho_cr = atm["rho_cruise"]

    mtow = dto.get("cycle.mtow_sum.mtow_calc")
    LD_cr = dto.get("cycle.aero.L_D")
    LD_lo = dto.get("cycle.aero.L_D_max")
    tsfc = dto.get("cycle.prop.tsfc_avail")
    t_avail = dto.get("cycle.prop.t_avail")
    R = m.range_km * 1.0e3
    E = m.loiter_min * 60.0
    w_weap = m.payload_kg

    f_cruise = math.exp(-((R / 2.0) * tsfc * g) / (V_cr * LD_cr))
    f_loiter = math.exp(-(E * tsfc * g) / LD_lo)
    w_fuel_combat = (m.thrust_combat_frac * t_avail
                     * (m.tsfc_combat_factor * tsfc) * m.t_combat_s)

    # Velocidad y distancia de loiter (a (L/D)_max)
    cd0 = dto.get("cycle.aero.cd0")
    AR = dto.get("aspect_ratio")
    e_osw = dto.get("cycle.aero.e_oswald")
    S = dto.get("wing_area")
    w_loiter = mtow * m.f_warmup * m.f_to * m.f_climb * f_cruise
    try:
        K = 1.0 / (math.pi * AR * e_osw)
        cl_opt = math.sqrt(cd0 / K)
        v_loiter = math.sqrt(2.0 * w_loiter * g / (rho_cr * S * cl_opt))
    except (ValueError, ZeroDivisionError):
        v_loiter = V_cr
    d_loiter = v_loiter * E / 1.0e3
    d_combat = V_co * m.t_combat_s / 1.0e3
    d_cruise = R / 2.0 / 1.0e3

    # Distancias de ascenso/descenso — estimación geométrica
    def d_climb(dh):  return abs(dh) / math.tan(math.radians(7.0)) / 1.0e3
    def d_desc(dh):   return abs(dh) / math.tan(math.radians(4.0)) / 1.0e3
    D_GROUND = 4.0

    # Construcción de fases con x acumulado, altitud y masa
    phases = []
    x = 0.0
    w = mtow

    def add(name, dx, h0, h1, w_end, drop=0.0):
        nonlocal x, w
        ph = {"name": name, "x0": x, "x1": x + dx, "h0": h0, "h1": h1,
              "w0": w, "w1": w_end, "drop": drop}
        x += dx
        w = w_end - drop
        phases.append(ph)

    add("Warmup + taxi",        D_GROUND,            0.0,  0.0,  mtow * m.f_warmup)
    add("Despegue + ascenso",   d_climb(h_cr),       0.0,  h_cr, w * m.f_to * m.f_climb)
    add("Crucero ida",          d_cruise,            h_cr, h_cr, w * f_cruise)
    add("Loiter ISR",           d_loiter,            h_cr, h_cr, w * f_loiter)
    add("Descenso a combate",   d_desc(h_cr - h_co), h_cr, h_co, w)
    add("Combate + soltado",    d_combat,            h_co, h_co, w - w_fuel_combat, drop=w_weap)
    add("Ascenso regreso",      d_climb(h_cr - h_co), h_co, h_cr, w)
    add("Crucero regreso",      d_cruise,            h_cr, h_cr, w * f_cruise)
    add("Descenso + aterrizaje", d_desc(h_cr),       h_cr, 0.0,  w * m.f_desc * m.f_land)
    add("Taxi + shutdown",      D_GROUND,            0.0,  0.0,  w)

    x_objective = phases[3]["x0"]
    d_ground = x - (2.0 * d_cruise + d_loiter + d_combat)
    return {
        "phases": phases, "h_cruise": h_cr, "h_combat": h_co,
        "range_km": m.range_km, "total_km": x,
        "x_objective": x_objective, "d_loiter": d_loiter, "d_combat": d_combat,
        "d_ground": d_ground, "v_loiter": v_loiter, "payload_kg": w_weap,
    }


def mission_profile(dto: ResultsDTO, config: FullConfig) -> dict:
    """Perfil altitud vs distancia recorrida, derivado de fases físicas reales."""
    mp = _mission_phases(dto, config)
    segs = [(p["x0"], p["h0"], p["x1"], p["h1"], p["name"]) for p in mp["phases"]]
    mp["segments"] = segs
    return mp


# Colores por fase (compartidos por ambos paneles del perfil de misión)
MISSION_PHASE_COLORS = {
    "Warmup + taxi": "#94A3B8",
    "Despegue + ascenso": "#0EA5E9",
    "Crucero ida": "#1E6FD9",
    "Loiter ISR": "#16A34A",
    "Descenso a combate": "#D97706",
    "Combate + soltado": "#DC2626",
    "Ascenso regreso": "#D97706",
    "Crucero regreso": "#1E6FD9",
    "Descenso + aterrizaje": "#EC4899",
    "Taxi + shutdown": "#94A3B8",
}


def mission_weight(dto: ResultsDTO, config: FullConfig) -> dict:
    """Peso del avión vs distancia recorrida, alineado con `mission_profile`."""
    mp = _mission_phases(dto, config)
    phases = mp["phases"]

    pts = [(phases[0]["x0"], phases[0]["w0"], phases[0]["name"])]
    for i, p in enumerate(phases):
        pts.append((p["x1"], p["w1"], p["name"]))
        if p["drop"] > 0.0:
            nxt = phases[i + 1]["name"] if i + 1 < len(phases) else p["name"]
            pts.append((p["x1"], p["w1"] - p["drop"], nxt))
    return {"points": pts, "payload_kg": mp["payload_kg"],
            "range_km": mp["range_km"], "total_km": mp["total_km"]}


def planform(dto: ResultsDTO, config: FullConfig) -> dict:
    """Geometría paramétrica de la semiala derecha con MAC y MGC.

    Sistema: Y = envergadura, X = estación longitudinal (LE raíz = 0)."""
    b = dto.get("cycle.geom.wingspan")
    c_r = dto.get("cycle.geom.root_chord")
    c_t = dto.get("cycle.geom.tip_chord")
    AR = dto.get("aspect_ratio")
    lam = c_t / c_r
    sweep_c4 = math.radians(config.aircraft.sweep_angle_deg)
    b_2 = b / 2.0

    tan_le = math.tan(sweep_c4) + (1.0 - lam) / (AR * (1.0 + lam))
    sweep_le_deg = math.degrees(math.atan(tan_le))

    mac = (2.0 / 3.0) * c_r * (1.0 + lam + lam**2) / (1.0 + lam)
    y_mac = (b_2 / 3.0) * (1.0 + 2.0 * lam) / (1.0 + lam)
    x_mac = y_mac * tan_le
    mgc = (c_r + c_t) / 2.0
    y_mgc = b_2 / 2.0
    x_mgc = y_mgc * tan_le

    tip_le_x = b_2 * tan_le
    xs = [0.0, tip_le_x, tip_le_x + c_t, c_r]
    ys = [0.0, b_2, b_2, 0.0]

    return {
        "xs": xs, "ys": ys, "b_2": b_2, "b": b, "c_r": c_r, "c_t": c_t,
        "lam": lam, "sweep_le_deg": sweep_le_deg, "tan_le": tan_le,
        "mac": mac, "y_mac": y_mac, "x_mac": x_mac,
        "mgc": mgc, "y_mgc": y_mgc, "x_mgc": x_mgc,
    }
