"""
Genera el XDSM (eXtended Design Structure Matrix) del MDAO-UCAV.

Arquitectura:
  - Optimizer (ScipyOptimize / SLSQP)
  - MDA loop (NonlinearBlockGS): Geometry → Propulsion → Aero → Mission → Weights → MTOW_sum
  - Post-ciclo: Performance, Stability, Cost, FuelVol

Correcciones aplicadas respecto a la versión anterior:
  1. Eliminado mda→geom y mda→prop (geom/prop no usan MTOW como entrada).
  2. Eliminado opt→miss (range_m, loiter_time_s son parámetros fijos, no DVs).
  3. opt→aero: sustituido sweep (fijo) por taper (DV real).
  4. opt→weight: eliminado n_ult (fijo), añadido taper (DV).
  5. opt→cost: sustituido v_cruise (fijo) por t_sl (DV real).
  6. opt→perf: añadidos AR y taper (promovidos y usados por perf).
  7. opt→stab: añadidos todos los DVs de CG (x_wing_frac, frac_fuel_fuse,
     x_fuel_fuse_frac, x_payload_offset_frac); eliminado v_vt (fijo).
  8. Añadido opt→fvol: frac_fuel_fuse (DV promovido a fuel_vol).
  9. Añadido prop→perf: T_avail,cr (conexión cycle.prop.t_avail_cruise→perf).
 10. aero→perf: añadido L/D (conexión cycle.aero.L_D→perf).
 11. Añadido aero→opt: g_M_dd (Constraint cycle.aero.M_dd).
 12. Añadido geom→opt: g_b (Constraint cycle.geom.wingspan).
 13. Etiquetas de restricciones detalladas y alineadas con config.py.

Uso:
    python docs/xdsm_ucav.py
    # Genera xdsm_ucav.pdf (y xdsm_ucav.tex) en el directorio actual
"""

from pyxdsm.XDSM import (
    XDSM,
    OPT,    # Optimizer — óvalo azul
    SOLVER, # Solver MDA — óvalo naranja
    FUNC,   # Función/módulo — rectángulo
    LEFT,
    RIGHT,
)

# ── Crear diagrama ────────────────────────────────────────────────────────────
x = XDSM(use_sfmath=True)

# ── 1. Sistemas (diagonal) ────────────────────────────────────────────────────
x.add_system("opt",    OPT,    r"\text{Optimizer}")
x.add_system("mda",   SOLVER, (r"\text{MDA}", r"\text{NonlinearBGS}"))
x.add_system("geom",  FUNC,   (r"\text{Geometry}",))
x.add_system("prop",  FUNC,   (r"\text{Propulsion}",))
x.add_system("aero",  FUNC,   (r"\text{Aerodynamics}",))
x.add_system("miss",  FUNC,   (r"\text{Mission}",))
x.add_system("weight",FUNC,   (r"\text{Weights}",))
x.add_system("mtow",  FUNC,   (r"\text{MTOW}", r"\text{Sum}"))
x.add_system("perf",  FUNC,   (r"\text{Performance}",))
x.add_system("stab",  FUNC,   (r"\text{Stability}",))
x.add_system("cost",  FUNC,   (r"\text{Cost}",))
x.add_system("fvol",  FUNC,   (r"\text{Fuel}", r"\text{Volume}"))

# ── 2. Conexiones del solver MDA ──────────────────────────────────────────────

x.connect("mda", "aero",   r"\text{MTOW}^{(k)}")
x.connect("mda", "miss",   r"\text{MTOW}^{(k)}")
x.connect("mda", "weight", r"\text{MTOW}^{(k)}")


x.connect("mtow", "mda", r"\text{MTOW}^{(k+1)}")

# ── 3. Variables de diseño (Optimizer → módulos que las usan) ─────────────────

x.add_input("opt", (r"x^{(0)}", r"\text{DVs init}"))


x.connect("opt", "geom",   (r"\text{wing\_area}", r"\text{AR, taper, }v_{HT}"))


x.connect("opt", "prop",   r"t_{sl}")


x.connect("opt", "aero",   (r"\text{wing\_area}", r"\text{AR, taper}"))


x.connect("opt", "weight", (r"\text{wing\_area}", r"\text{AR, taper}"))


x.connect("opt", "perf",   (r"\text{wing\_area}", r"t_{sl}", r"\text{AR, taper}"))


x.connect("opt", "stab",   (r"\text{wing\_area}", r"\text{AR, taper, }v_{HT}",
                              r"x_w,\,f_{ff},\,x_{ff},\,x_{pl}"))
x.connect("opt", "cost",   r"t_{sl}")


x.connect("opt", "fvol",   r"f_{ff}")


x.connect("geom", "aero",   (r"\text{mac}", r"S_{vtail}"))
x.connect("geom", "weight", r"S_{vtail}")
x.connect("geom", "stab",   (r"\text{mac}", r"b"))
x.connect("geom", "fvol",   (r"V_{wing}", r"V_{fuse}"))


x.connect("prop", "miss",   (r"\text{tsfc}", r"T_{avail}"))
x.connect("prop", "mtow",   r"W_{eng}")
x.connect("prop", "stab",   r"W_{eng}")
x.connect("prop", "cost",   r"W_{eng}")
x.connect("prop", "perf",   r"T_{avail,cr}")   


x.connect("aero", "miss",   (r"L/D", r"(L/D)_{max}"))
x.connect("aero", "perf",   (r"C_{D0}", r"e", r"L/D"))   

x.connect("miss", "mtow",   r"W_{fuel}")
x.connect("miss", "stab",   r"W_{fuel}")
x.connect("miss", "perf",   r"W_{fuel}")
x.connect("miss", "fvol",   r"W_{fuel}")


x.connect("weight", "mtow",  r"W_{OEW}")
x.connect("weight", "stab",  (r"W_{fuse}", r"W_{wing}", r"W_{vtail}", r"W_{lg}"))
x.connect("weight", "cost",  r"W_{OEW}")


x.connect("mtow", "aero",   r"MTOW")
x.connect("mtow", "miss",   r"MTOW")
x.connect("mtow", "weight", r"MTOW")
x.connect("mtow", "perf",   r"MTOW")
x.connect("mtow", "stab",   r"MTOW")

# ── 5. Salidas hacia el Optimizer (objetivo y restricciones) ──────────────────
# Objetivo
x.connect("cost", "opt", r"C_{ac}\;(\text{obj})")

# Restricciones perf:
x.connect("perf", "opt", (r"g_{s_{TO}},\,g_{s_{land}}",
                           r"g_{n_{turn}},\,g_{RoC}",
                           r"g_{P_s},\,g_{stall},\,g_{cr}"))

# Restricciones stab:
x.connect("stab", "opt", (r"g_{SM_{full/empty/aft}}",
                           r"g_{\delta CG},\,g_{pl}",
                           r"g_{C_{n\beta}},\,g_{C_L^{tail}}"))

# Restricciones aero:
x.connect("aero", "opt", r"g_{M_{dd}}")

# Restricciones geom: 
x.connect("geom", "opt", r"g_b")

# Restricciones fvol:
x.connect("fvol", "opt", (r"g_{V_w}", r"g_{V_f}"))

# ── 6. Outputs finales ────────────────────────────────────────────────────────
x.add_output("opt",    r"x^*\;\text{(DVs óptimos)}", side=LEFT)
x.add_output("mtow",   r"MTOW^*",                    side=RIGHT)
x.add_output("perf",   r"\text{Perf. constraints}",  side=RIGHT)
x.add_output("stab",   r"\text{Stab. constraints}",  side=RIGHT)
x.add_output("cost",   r"C_{ac}^*",                  side=RIGHT)

# ── 7. Generar PDF ────────────────────────────────────────────────────────────
x.write("xdsm_ucav", cleanup=True)
print("✓  XDSM generado: xdsm_ucav.pdf")
