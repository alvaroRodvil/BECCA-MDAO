"""
Dibujado matplotlib de las gráficas (capa View) — estilo SciencePlots + LaTeX.

La física la aportan `core.diagrams` y `core.studies`; aquí solo se estiliza con
`gui.plot_style`. Dos tipos de función de dibujo:

  - "instant":  fn(fig, dto, config)
  - "study":    fn(fig, study_result)   (tornado / Pareto, calculados aparte)

`CATEGORIES` agrupa las gráficas por familia para la navegación.
"""

from __future__ import annotations

import numpy as np

import math

from core import diagrams as dg
from core.config import FullConfig
from core.results import ResultsDTO
from gui import plot_style as ps
from gui.plot_style import (
    BLUE_PRIMARY, BLUE_DARK, BLUE_ACCENT, GREEN_OK,
    AMBER_ACTIVE, RED_VIOLATED, MUTED, CYCLE, CMAP_PS, INK,
)

ps.apply_theme()

DV_LATEX = {
    "wing_area": r"$S$ (sup. alar)",
    "t_sl": r"$T_{SL}$ (empuje)",
    "v_ht": r"$V_{HT}$ (cola)",
    "aspect_ratio": r"$AR$ (alargamiento)",
    "taper_ratio": r"$\lambda$ (taper)",
    "x_wing_frac": r"$x_w/L_f$ (pos. ala)",
    "frac_fuel_fuse": r"fracción fuel fuselaje",
    "x_fuel_fuse_frac": r"$x_{fuel}/L_f$",
    "x_payload_offset_frac": r"offset payload",
}


# CATEGORÍA 1 · Convergencia (objetivo + infactibilidad)
def plot_convergence(fig, dto: ResultsDTO, config: FullConfig):
    fig.clear()
    ax = fig.add_subplot(111)
    d = dg.convergence_detail(dto, config)
    obj = d["objective"]
    if not d["iterations"] or not obj:
        ps.placeholder(fig, "Sin historial de iteraciones.\nEjecuta una optimización.")
        return
    ax.plot(range(len(obj)), obj, "o-", color=BLUE_PRIMARY, ms=4, label=d["objective_label"])
    ax.set_ylabel(ps.bold_math(d["objective_label"]), color=BLUE_PRIMARY, fontweight="bold")
    ax.tick_params(axis="y", colors=BLUE_PRIMARY)
    ps.annotate(ax, len(obj) - 1, obj[-1], rf"{obj[-1]:.3f}")

    ax2 = ax.twinx()
    ax2.plot(range(len(d["infeas"])), d["infeas"], "s--", color=RED_VIOLATED,
             ms=3, lw=1.5, label="Infactibilidad máx.")
    ax2.set_ylabel("Infactibilidad (norm.)", color=RED_VIOLATED, fontweight="bold")
    ax2.tick_params(axis="y", colors=RED_VIOLATED)
    ax2.grid(False)

    ps.style_axes(ax, "Convergencia del optimizador", "Iteración", None)
    l1, lab1 = ax.get_legend_handles_labels()
    l2, lab2 = ax2.get_legend_handles_labels()
    ax.legend(l1 + l2, lab1 + lab2, loc="upper right")
    ps.footer(fig)


# CATEGORÍA 1 · Historial de variables de diseño
def plot_dv_history(fig, dto: ResultsDTO, config: FullConfig):  # noqa: ARG001
    fig.clear()
    ax = fig.add_subplot(111)
    d = dg.dv_history(dto)
    if not d["series"]:
        ps.placeholder(fig, "Sin historial de iteraciones.")
        return
    DV_PALETTE = [
        "#2563EB",  # azul
        "#DC2626",  # rojo
        "#16A34A",  # verde
        "#D97706",  # naranja
        "#7C3AED",  # violeta
        "#0891B2",  # cian
        "#DB2777",  # magenta
        "#65A30D",  # lima
        "#000000",  # negro
        "#9333EA",  # púrpura
    ]
    DV_DASHES = ["-", "--", "-.", ":"]
    for i, (name, arr) in enumerate(d["series"].items()):
        ax.plot(range(len(arr)), arr, DV_DASHES[(i // len(DV_PALETTE)) % len(DV_DASHES)],
                color=DV_PALETTE[i % len(DV_PALETTE)], lw=2.0,
                label=DV_LATEX.get(name, name.replace("_", r"\_")))
    ax.axhline(1.0, color=MUTED, ls=":", lw=1, alpha=0.6)
    ps.style_axes(ax, "Historial de variables de diseño (normalizado al óptimo)",
                  "Iteración", "Valor / valor óptimo", legend="upper right")
    ps.footer(fig)


# CATEGORÍA 1 · Tornado de sensibilidad   (study)
def plot_tornado(fig, result: dict):
    fig.clear()
    ax = fig.add_subplot(111)
    rows = result["rows"]
    for i, r in enumerate(rows):
        ax.barh(i, r["d_hi"], color=BLUE_PRIMARY, height=0.6, edgecolor="white",
                label=rf"+10{ps.pct()}" if i == 0 else None)
        ax.barh(i, r["d_lo"], color=AMBER_ACTIVE, height=0.6, edgecolor="white",
                label=rf"$-$10{ps.pct()}" if i == 0 else None)
    ax.set_yticks(np.arange(len(rows)))
    ax.set_yticklabels([r["label"] for r in rows], fontsize=9)
    ax.axvline(0, color=INK, lw=1)
    ax.grid(True, axis="x", alpha=0.3)
    ps.style_axes(ax, rf"Sensibilidad del objetivo ($\pm$10{ps.pct()})",
                  rf"$\Delta$ {result['objective_label']}  [{ps.pct()}]", None,
                  legend="lower right")
    ps.footer(fig)


# CATEGORÍA 1 · Frontera de Pareto   (study)
def plot_pareto(fig, result: dict):
    fig.clear()
    ax = fig.add_subplot(111)
    pts = result["points"]
    xs = [p["x"] for p in pts]
    cost = [p["cost"] for p in pts]
    mtow = [p["mtow"] for p in pts]
    feas = [p["feasible"] for p in pts]

    ax.plot(xs, cost, "-", color=BLUE_PRIMARY, lw=2, zorder=2)
    ax.scatter([x for x, f in zip(xs, feas) if f], [c for c, f in zip(cost, feas) if f],
               s=70, color=BLUE_PRIMARY, edgecolor="white", zorder=3, label="Factible")
    ax.scatter([x for x, f in zip(xs, feas) if not f], [c for c, f in zip(cost, feas) if not f],
               s=70, color=RED_VIOLATED, edgecolor="white", zorder=3, label="No factible")
    ax.axvline(result["design_x"], color=MUTED, ls=":", lw=1.2, label="Diseño nominal")
    ax.set_ylabel(r"Coste unitario  [M\$]", color=BLUE_PRIMARY, fontweight="bold")
    ax.tick_params(axis="y", colors=BLUE_PRIMARY)

    ax2 = ax.twinx()
    ax2.plot(xs, mtow, "s--", color=AMBER_ACTIVE, ms=4, lw=1.5, label="MTOW")
    ax2.set_ylabel("MTOW  [kg]", color=AMBER_ACTIVE, fontweight="bold")
    ax2.tick_params(axis="y", colors=AMBER_ACTIVE)
    ax2.grid(False)

    ps.style_axes(ax, "Frontera de Pareto — compromiso de misión",
                  rf"{result['param_label']}  [{result['unit']}]", None)
    l1, lab1 = ax.get_legend_handles_labels()
    l2, lab2 = ax2.get_legend_handles_labels()
    ax.legend(l1 + l2, lab1 + lab2, loc="upper left", fontsize=8)
    ps.footer(fig)


# CATEGORÍA 2 · Desglose de pesos
def plot_weight_breakdown(fig, dto: ResultsDTO, config: FullConfig):  # noqa: ARG001
    fig.clear()
    d = dg.weight_breakdown(dto)
    ax1, ax2 = fig.subplots(1, 2)

    groups = d["groups"]
    vals = list(groups.values())
    donut_cols = [BLUE_DARK, BLUE_ACCENT, AMBER_ACTIVE]
    wedges, _t, _a = ax1.pie(
        vals, autopct=lambda p: f"{p:.0f}{ps.pct()}", pctdistance=0.78,
        colors=donut_cols, startangle=90,
        wedgeprops=dict(width=0.42, edgecolor="white", linewidth=2),
        textprops=dict(color="white", fontsize=10))
    ax1.set_title("Desglose de pesos", fontweight="bold")
    ax1.text(0, 0, f"MTOW\n{d['mtow']:.0f} kg", ha="center", va="center",
             fontsize=11, color=BLUE_DARK)
    ax1.legend(wedges, [f"{k}: {v:.0f} kg" for k, v in groups.items()],
               loc="lower center", bbox_to_anchor=(0.5, 0.0), fontsize=8,
               frameon=False, ncol=len(groups))

    comp = d["components"]
    order = np.argsort(list(comp.values()))
    names = [list(comp.keys())[i] for i in order]
    cvals = [list(comp.values())[i] for i in order]
    ypos = np.arange(len(names))
    bars = ax2.barh(ypos, cvals, color=BLUE_PRIMARY, height=0.62, edgecolor="white")
    for b, v in zip(bars, cvals):
        ax2.text(b.get_width() + max(cvals) * 0.01, b.get_y() + b.get_height() / 2,
                 f"{v:.0f}", va="center", fontsize=8, color=INK)
    ax2.set_yticks(ypos)
    ax2.set_yticklabels(names, fontsize=9)
    ps.style_axes(ax2, "Componentes de OEW", "Masa  [kg]")
    ax2.set_xlim(0, max(cvals) * 1.18)
    ps.footer(fig)


# CATEGORÍA 2 · Polar de resistencia
def plot_drag_polar(fig, dto: ResultsDTO, config: FullConfig):
    fig.clear()
    ax = fig.add_subplot(111)
    d = dg.drag_polar(dto, config)
    cl, cd, cl_max = d["cl"], d["cd"], d["cl_max"]
    K, cd0 = d["K"], d["cd0"]

    # Tramo válido (sólido) hasta CL_max
    valid = cl <= cl_max
    ax.plot(cd[valid], cl[valid], color=BLUE_PRIMARY, lw=2.3,
            label=rf"Polar  ($K$ = {K:.3f})")
    ax.plot(cd[~valid], cl[~valid], color="#9AA4B2", lw=1.6, ls="--",
            label="Modelo no físico (post-stall)")
    cd_clmax = cd0 + K * cl_max**2
    ax.plot([cd_clmax], [cl_max], "o", ms=6, color="#9AA4B2", markeredgecolor="white")
    ax.annotate(rf"$C_{{L,max}}$ = {cl_max:.2f}", xy=(cd_clmax, cl_max), xytext=(10, -2),
                textcoords="offset points", fontsize=11, color="#5A6675")

    # Recta de CD0 (parásita), bien visible + etiqueta con valor dentro
    ax.axvline(cd0, color=RED_VIOLATED, ls="-", lw=1.6, alpha=0.85)
    ax.annotate(rf"$C_{{D0}}$ = {cd0:.4f}", xy=(cd0, cl_max * 0.92), xytext=(6, 0),
                textcoords="offset points", fontsize=11, color=RED_VIOLATED)

    # Punto de crucero (naranja) con flecha + etiqueta CLcruise con valor
    ax.plot([d["cd_cruise"]], [d["cl_cruise"]], "o", ms=10, color=AMBER_ACTIVE,
            markeredgecolor="white", markeredgewidth=1.2, zorder=6)
    ax.annotate(rf"$C_{{L,cruise}}$ = {d['cl_cruise']:.2f}", xy=(d["cd_cruise"], d["cl_cruise"]),
                xytext=(48, -18), textcoords="offset points", fontsize=11,
                color=AMBER_ACTIVE,
                arrowprops=dict(arrowstyle="->", color=AMBER_ACTIVE, lw=1.5))

    # Punto de L/D máx (verde) con flecha + etiqueta
    ax.plot([d["cd_ld_max"]], [d["cl_ld_max"]], "s", ms=10, color=GREEN_OK,
            markeredgecolor="white", markeredgewidth=1.2, zorder=6)
    ax.annotate(rf"$(L/D)_{{max}}$ = {d['ld_max']:.1f}", xy=(d["cd_ld_max"], d["cl_ld_max"]),
                xytext=(54, 6), textcoords="offset points", fontsize=11,
                color=GREEN_OK,
                arrowprops=dict(arrowstyle="->", color=GREEN_OK, lw=1.5))
    ax.plot([0, d["cd_ld_max"]], [0, d["cl_ld_max"]], "--", lw=1, color=GREEN_OK, alpha=0.6)

    # Ecuación justo encima del tramo válido de la curva (coordenadas de datos)
    i_txt = int(len(cl[valid]) * 0.65)
    cl_txt = cl[valid][i_txt]
    cd_txt = cd[valid][i_txt]
    ax.text(cd_txt, cl_txt + 0.055,
            rf"$C_D = {cd0:.4f} + {K:.3f}\,C_L^2$",
            fontsize=13, color=BLUE_PRIMARY, fontweight="bold",
            va="bottom",
            bbox=dict(boxstyle="round,pad=0.22", facecolor="white", alpha=0.92,
                      edgecolor=BLUE_PRIMARY, lw=0.6))

    ps.style_axes(ax, "Polar de resistencia", r"Resistencia  $C_D$",
                  r"Sustentación  $C_L$", legend="lower right")
    ax.set_xlim(left=0)
    ax.set_ylim(bottom=0)
    ps.footer(fig)


# CATEGORÍA 2 · Desglose de la resistencia parásita (CD0 buildup)
def plot_cd0_buildup(fig, dto: ResultsDTO, config: FullConfig):
    fig.clear()
    ax = fig.add_subplot(111)
    d = dg.cd0_buildup(dto, config)
    comps = d["components"]
    total = d["total"]
    names = list(comps.keys())
    vals = list(comps.values())
    order = np.argsort(vals)
    names = [names[i] for i in order]
    vals = [vals[i] for i in order]
    ypos = np.arange(len(names))
    base_cols = [BLUE_PRIMARY, BLUE_ACCENT, GREEN_OK, "#8B5CF6", "#0891B2"]
    misc_keys = {"Misceláneos"}
    bar_cols = [AMBER_ACTIVE if n in misc_keys else base_cols[i % len(base_cols)]
                for i, n in enumerate(names)]
    bars = ax.barh(ypos, vals, color=bar_cols, height=0.62, edgecolor="white")
    for b, v in zip(bars, vals):
        ax.text(b.get_width() + total * 0.01, b.get_y() + b.get_height() / 2,
                rf"{v:.4f}  ({v/total*100:.0f}{ps.pct()})", va="center",
                fontsize=8.5, color=INK)
    ax.set_yticks(ypos)
    ax.set_yticklabels(names, fontsize=9.5)
    ax.set_xlim(0, max(vals) * 1.28)
    ps.style_axes(ax, rf"Desglose de la resistencia parásita  ($C_{{D0}}$ = {total:.4f})",
                  r"Contribución a $C_{D0}$", None)
    ps.footer(fig)


# CATEGORÍA 2 · L/D vs Mach a varias altitudes
def plot_ld_mach(fig, dto: ResultsDTO, config: FullConfig):
    fig.clear()
    ax = fig.add_subplot(111)
    d = dg.ld_vs_mach(dto, config)
    md, ldd = d["design"]
    h_cruise = d["h_cruise"]
    cruise_color = BLUE_PRIMARY
    ld_peak = 0.0
    for i, (h, ld) in enumerate(sorted(d["curves"].items())):
        col = CYCLE[i % len(CYCLE)]
        if abs(h - h_cruise) < 1.0:
            cruise_color = col
        ax.plot(d["mach"], ld, color=col, lw=2.0, label=rf"$h$ = {h/1000:.0f} km")
        imax = int(np.argmax(ld))
        ax.plot(d["mach"][imax], ld[imax], "o", ms=5, color=col, markeredgecolor="white")
        ld_peak = max(ld_peak, float(np.max(ld)))

    # Línea de crucero
    ax.axvline(md, color=cruise_color, ls=":", lw=1.4)
    ax.annotate(rf"$M_{{cruise}}$ = {md:.2f}", xy=(md, ldd),
                xytext=(-92, -34), textcoords="offset points", fontsize=10,
                color=cruise_color, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                          edgecolor=cruise_color, lw=0.9),
                arrowprops=dict(arrowstyle="->", color=cruise_color, lw=1.3))

    ax.text(0.02, 0.05, rf"$(L/D)_{{max}}$ $\approx$ {ld_peak:.1f}",
            transform=ax.transAxes, fontsize=10, color=INK, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#F1F5F9",
                      edgecolor="#CBD5E1", lw=0.8))

    ax.set_xlim(0.30, 1.00)
    ax.set_ylim(0, ld_peak * 1.15)
    ps.style_axes(ax, r"Eficiencia aerodinámica  $L/D$ vs Mach", "Número de Mach",
                  r"$L/D$", legend="lower right")
    ps.footer(fig)


# CATEGORÍA 2 · Distribución de sustentación (Schrenk)
def plot_spanwise(fig, dto: ResultsDTO, config: FullConfig):
    fig.clear()
    ax = fig.add_subplot(111)
    d = dg.spanwise_lift(dto, config)
    eta = d["eta"]
    ax.plot(eta, d["ell"], "--", color=GREEN_OK, lw=2, label="Elíptica ideal")
    ax.plot(eta, d["trap"], ":", color=MUTED, lw=2, label="Ala trapezoidal")
    ax.plot(eta, d["schrenk"], color=BLUE_PRIMARY, lw=2.4, label="Schrenk (real)")
    ax.fill_between(eta, d["schrenk"], color=BLUE_PRIMARY, alpha=0.10)
    ps.style_axes(ax, "Distribución de sustentación (aprox. de Schrenk)",
                  r"Posición a lo largo de la envergadura  $y/(b/2)$",
                  r"Carga normalizada  $c \cdot c_l$", legend="upper right")
    ax.set_xlim(0, 1)
    ax.set_ylim(bottom=0)
    ps.footer(fig)


# CATEGORÍA 2 · Curva de momento de cabeceo (Cm vs CL)
def plot_cm_cl(fig, dto: ResultsDTO, config: FullConfig):
    fig.clear()
    ax = fig.add_subplot(111)
    d = dg.cm_cl(dto, config)
    cl = d["cl"]
    ax.plot(cl, d["cm_full"], color=BLUE_PRIMARY, lw=2.3,
            label=rf"CG full (SM={d['sm_full']:.1f}{ps.pct()})")
    ax.plot(cl, d["cm_empty"], color=AMBER_ACTIVE, lw=2.3,
            label=rf"CG empty (SM={d['sm_empty']:.1f}{ps.pct()})")
    ax.plot(cl, d["cm_aft"], color=RED_VIOLATED, lw=2.0, ls="--",
            label=rf"CG aft-crítico (SM={d['sm_aft']:.1f}{ps.pct()})")
    ax.axhline(0, color=MUTED, lw=0.9)
    ps.style_axes(ax, "Curva de momento de cabeceo  ($C_m$ vs $C_L$)",
                  r"Coef. de sustentación  $C_L$",
                  r"Coef. de momento  $C_m$", legend=(0.02, 0.7))
    ps.footer(fig)


# CATEGORÍA 2 · Diagrama V-n
def plot_vn(fig, dto: ResultsDTO, config: FullConfig):
    fig.clear()
    ax = fig.add_subplot(111)
    ax.set_facecolor("white")
    d = dg.vn_diagram(dto, config)
    v = d["v"]
    n_lp, n_ln = d["n_lim_pos"], d["n_lim_neg"]
    n_up, n_un = d["n_ult_pos"], d["n_ult_neg"]
    v_c, v_d = d["v_c"], d["v_d"]

    # Envolventes capadas por las parábolas de pérdida
    L_top = np.minimum(d["n_par_pos"], n_lp)        # límite, rama positiva
    U_top = np.minimum(d["n_par_pos"], n_up)        # última, rama positiva
    L_bot = np.maximum(d["n_par_neg"], n_ln)        # límite, rama negativa
    U_bot = np.maximum(d["n_par_neg"], n_un)        # última, rama negativa
    m_d = v <= v_d
    m_g = v <= v_c

    v_s = d["v_s"]
    m_stall = v < v_s
    m_oper = (v >= v_s) & m_g
    GRAY_F, GREEN_F, YELLOW_F = "#CBD2DA", "#86E29B", "#FCE38A"
    ORANGE_DMG = "#F6B26B"
    RED_FAIL   = "#F87171"
    Y_TOP = 12.0              
    Y_BOT = n_un - 2.0       

    fac_neg = abs(n_ln) / n_lp

    # ── Zona stall (gris): izquierda de Vs ───────────────────────────────────
    ax.fill_between(v, L_bot, L_top, where=m_stall, color=GRAY_F, alpha=0.75, lw=0,
                    label="Pérdida (no vuelo)")
    # ── Operación normal (verde): Vs → Vc, dentro de ±n_lim ─────────────────
    ax.fill_between(v, L_bot, L_top, where=m_oper, color=GREEN_F, alpha=0.55, lw=0)
    # ── Caution Range (amarillo): Vc → Vd, dentro de ±n_lim ─────────────────
    ax.fill_between(v, n_ln, n_lp, where=(v >= v_c) & m_d, color=YELLOW_F, alpha=0.60, lw=0)
    # ── Structural Damage (naranja): entre límite y última (Vs → Vd) ─────────
    ax.fill_between(v, L_top, U_top, where=m_d, color=ORANGE_DMG, alpha=0.60, lw=0)
    ax.fill_between(v, U_bot, L_bot, where=m_d, color=ORANGE_DMG, alpha=0.60, lw=0)

    # ── Structural Failure (rojo) ────────────────────────────────────────────
    n_ext_p = np.linspace(n_up, Y_TOP, 300)
    v_para_p = v_s * np.sqrt(n_ext_p)
    ax.fill_betweenx(n_ext_p, v_para_p, v_d,        # clip a v_d (sin solapamiento)
                     where=v_para_p <= v_d,
                     color=RED_FAIL, alpha=0.65, lw=0)

    n_ext_n = np.linspace(Y_BOT, n_un, 300)
    v_para_n = v_s * np.sqrt(np.abs(n_ext_n) / fac_neg)
    ax.fill_betweenx(n_ext_n, v_para_n, v_d,
                     where=v_para_n <= v_d,
                     color=RED_FAIL, alpha=0.65, lw=0)

    # Banda SF vertical (v > V_D) — misma alpha para color uniforme
    ax.fill_between(v, Y_BOT, Y_TOP, where=(v > v_d), color=RED_FAIL, alpha=0.65, lw=0)

    # Envolvente de carga LÍMITE (roja gruesa) y ÚLTIMA (roja oscura)
    ax.plot(v[m_d], L_top[m_d], color=RED_VIOLATED, lw=2.4)
    ax.plot(v[m_d], L_bot[m_d], color=RED_VIOLATED, lw=2.4)
    ax.plot([v_d, v_d], [n_ln, n_lp], color=RED_VIOLATED, lw=2.4,
            label="Carga límite")
    # Tramo capeado de la carga última (hasta v_A_ult)
    ax.plot(v[m_d], U_top[m_d], color="#7F1D1D", lw=2.0, ls="--")
    ax.plot(v[m_d], U_bot[m_d], color="#7F1D1D", lw=2.0, ls="--")
    ax.plot([v_d, v_d], [n_un, n_up], color="#7F1D1D", lw=2.0, ls="--",
            label=rf"Carga última (×{d['safety_factor']:.1f})")
    # Extensión de la parábola más allá de n_up/n_un (límite de SF)
    m_ext_p = (v_para_p <= d["v_max"]) & (v_para_p >= v_s * np.sqrt(n_up))
    ax.plot(v_para_p[m_ext_p], n_ext_p[m_ext_p], color="#7F1D1D", lw=2.0, ls="--")
    m_ext_n = (v_para_n <= d["v_max"]) & (v_para_n >= v_s * np.sqrt(abs(n_un) / fac_neg))
    ax.plot(v_para_n[m_ext_n], n_ext_n[m_ext_n], color="#7F1D1D", lw=2.0, ls="--")

    ax.axhline(0, color="black", lw=0.8)
    ax.axhline(1, color="black", ls=":", lw=1.1, alpha=0.7)
    ax.annotate("1 g", xy=(v_d * 0.98, 1), xytext=(0, 3), textcoords="offset points",
                fontsize=8, color="black", ha="right")

    # Velocidades características — líneas azules visibles con entradas en leyenda
    vel_info = [
        (v_s, r"$V_S$", "stall"),
        (d["v_a"], r"$V_A$", "maniobra"),
        (v_c,      r"$V_C$", "crucero máx."),
        (v_d,      r"$V_D$", "picado"),
    ]
    for j, (vx, lab, desc) in enumerate(vel_info):
        ax.axvline(vx, color=BLUE_PRIMARY, ls=":", lw=1.7,
                   ymin=0.04, ymax=0.90, label=f"{lab}: {desc}", alpha=0.85)
        ax.annotate(lab, xy=(vx, n_up + 0.1), xytext=(0, 6), textcoords="offset points",
                    fontsize=10, color=BLUE_PRIMARY, ha="center", fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.15", facecolor="white",
                              edgecolor=BLUE_PRIMARY, lw=0.6, alpha=0.95))

    # Etiquetas de zonas — "Normal Operating Range" en una línea, justo sobre la 1g
    ax.text((d["v_s"] + d["v_a"]) / 2, 1.10, "Normal Operating Range",
            ha="center", va="bottom", fontsize=8.5, color="#14532D", fontweight="bold")
    ax.text((v_c + v_d) / 2, 0.5, "Caution\nRange", ha="center", va="center",
            fontsize=8.5, color="#7C5E10", fontweight="bold")
    ax.text((d["v_a"] + v_d) / 2, (n_lp + n_up) / 2, "Structural Damage",
            ha="center", va="center", fontsize=8.5, color="#92400E", fontweight="bold")
    ax.text(d["v_max"] * 0.97, (n_up + n_un) / 2, "Structural Failure\n(Never exceed speed)",
            ha="right", va="center", fontsize=8.0, color="#7F1D1D", fontweight="bold",
            rotation=90)

    ax.set_xlim(0, d["v_max"])
    ax.set_ylim(Y_BOT, Y_TOP)
    ax.grid(False)
    # Valores de n_lim / n_ult: esquina inferior izquierda
    ax.text(0.02, 0.10,
            rf"$n_{{lim}}$ = +{n_lp:.1f} / {n_ln:.1f} g    ·    "
            rf"$n_{{ult}}$ = +{n_up:.1f} / {n_un:.1f} g",
            fontsize=8.8, color="#111827",
            transform=ax.transAxes,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                      edgecolor="#94A3B8", lw=0.8))
    ps.style_axes(ax, "Diagrama V-n (envolvente de vuelo estructural)",
                  "Velocidad equivalente EAS  [m/s]", r"Factor de carga  $n$  [g]",
                  legend=(0.02, 0.55), grid=False)
    ps.footer(fig)


# CATEGORÍA 2 · CG-travel (recorrido del centro de gravedad)
def plot_cg_travel(fig, dto: ResultsDTO, config: FullConfig):
    fig.clear()
    ax = fig.add_subplot(111)
    d = dg.cg_travel(dto, config)
    states = d["states"]
    cg = [s[1] for s in states]
    w = [s[2] for s in states]

    np_pct = d["np_pct"]
    lo_sm, hi_sm = d["band"]
    cg_lo, cg_hi = np_pct - hi_sm, np_pct - lo_sm
    pc = ps.pct()
    ax.axvspan(cg_lo, cg_hi, color=GREEN_OK, alpha=0.12,
               label=rf"CG admisible (SM {lo_sm:.0f}{pc} a {hi_sm:.0f}{pc})")
    ax.axvline(np_pct, color=RED_VIOLATED, lw=2, ls="--",
               label=rf"Punto neutro = {np_pct:.1f}{pc} MAC")
    ax.plot(cg, w, "-o", color=BLUE_PRIMARY, lw=2, ms=7, markeredgecolor="white",
            zorder=5, label="CG (recorrido)")
    for (lbl, c, wt) in states:
        ax.annotate(lbl, xy=(c, wt), xytext=(8, 0), textcoords="offset points",
                    fontsize=7.5, color=INK, va="center")

    in_band = d["sm_aft"] >= lo_sm - 0.05
    col = GREEN_OK if in_band else RED_VIOLATED
    ax.scatter([d["cg_aft"]], [min(w)], marker="D", s=70, color=col,
               edgecolor="white", zorder=6,
               label=rf"Aft-crítico: SM={d['sm_aft']:.1f}{pc}")

    ax.text(0.01, 0.70,
            rf"Excursión $\approx${d['excursion']:.1f}{pc} MAC"
            rf"  (sep. tanques {d['tank_sep_pct']:.0f}{pc})",
            transform=ax.transAxes, fontsize=10, color=BLUE_DARK,
            va="top",
            bbox=dict(boxstyle="round,pad=0.28", facecolor="white",
                      edgecolor=BLUE_DARK, lw=0.7, alpha=0.92))
    x_lo = min(np_pct - 3.0, min(cg) - 0.6, cg_lo - 0.6)
    x_hi = max(np_pct + 4.0, max(cg) + 0.6, d["cg_aft"] + 0.6, cg_hi + 0.6)
    ax.set_xlim(x_lo, x_hi)
    ps.style_axes(ax, "Recorrido del centro de gravedad",
                  rf"Posición del CG  [{pc} MAC]", "Peso  [kg]", legend="upper left")
    ps.footer(fig)


# CATEGORÍA 3 · Diagrama de restricciones T/W vs W/S
def plot_constraint_diagram(fig, dto: ResultsDTO, config: FullConfig):
    fig.clear()
    ax = fig.add_subplot(111)
    d = dg.constraint_diagram(dto, config)
    ws = d["ws_kg"]

    envelope = np.full_like(ws, -np.inf)
    for i, (label, tw) in enumerate(d["curves"].items()):
        tw = np.asarray(tw, dtype=float)
        ax.plot(ws, tw, lw=1.9, color=CYCLE[i % len(CYCLE)], label=label)
        envelope = np.maximum(envelope, np.nan_to_num(tw, nan=-np.inf))

    ws_land = min(d["vlines"].values()) if d["vlines"] else ws.max()
    vline_styles = [("#111827", ":"), ("#111827", "-.")]   # negros, distinto trazo
    for j, (label, xv) in enumerate(d["vlines"].items()):
        col, lstyle = vline_styles[j % len(vline_styles)]
        ax.axvline(xv, color=col, lw=1.7, ls=lstyle, label=label)

    finite = np.isfinite(envelope)
    ymax = max(1.2, (np.nanmax(envelope[finite]) * 1.25 if finite.any() else 1.2),
               d["design"][1] * 1.3)
    mask = finite & (ws <= ws_land)
    ax.fill_between(ws, envelope, ymax, where=mask, color=GREEN_OK, alpha=0.10,
                    label="Región factible")

    # Punto de diseño: círculo negro (el MDAO lo clava sobre la restricción activa)
    wsd, twd = d["design"]
    ax.plot([wsd], [twd], "o", ms=9, color="black", markeredgecolor="white",
            markeredgewidth=1.0, zorder=12, label="Diseño óptimo")
    ps.annotate(ax, wsd, twd, rf"{wsd:.0f} kg/m$^2$ $\cdot$ $T/W$={twd:.2f}", dx=8, dy=-24)

    ax.set_xlim(ws.min(), ws.max())
    ax.set_ylim(0, ymax)
    ps.style_axes(ax, r"Diagrama de restricciones ($T/W$ vs $W/S$)",
                  r"Carga alar  $W/S$  [kg/m$^2$]",
                  r"Empuje-peso  $T/W$ (SL estático)", legend="upper right")
    ps.footer(fig)


# CATEGORÍA 3 · Envolvente de vuelo con isolíneas de P_s
def plot_ps_envelope(fig, dto: ResultsDTO, config: FullConfig):
    fig.clear()
    ax = fig.add_subplot(111)
    d = dg.flight_envelope_ps(dto, config)
    M, H, PS = d["M"], d["H_km"], d["PS"]

    import matplotlib.patheffects as pe
    vmax = np.nanmax(np.abs(PS))
    levels = np.linspace(-vmax, vmax, 21)
    cf = ax.contourf(M, H, PS, levels=levels, cmap=CMAP_PS, extend="both")
    cs = ax.contour(M, H, PS, levels=[-40, -20, 20, 40, 60], colors="white",
                    linewidths=0.8, alpha=0.85)
    labels = ax.clabel(cs, fmt="%d", fontsize=8)
    for t in labels:                                   # halo negro → legibles
        t.set_path_effects([pe.withStroke(linewidth=2.2, foreground="black")])
    z = ax.contour(M, H, PS, levels=[0], colors=[INK], linewidths=2.2)
    zl = ax.clabel(z, fmt={0.0: r"$P_s=0$"}, fontsize=9)
    for t in zl:
        t.set_path_effects([pe.withStroke(linewidth=2.2, foreground="white")])

    md, hd = d["design"]
    mc, hc = d["combat"]
    ax.plot(md, hd, "o", ms=12, color=BLUE_DARK, markeredgecolor="white",
            markeredgewidth=1.5, zorder=8, label="Crucero")
    ax.plot(mc, hc, "o", ms=12, color=RED_VIOLATED, markeredgecolor="white",
            markeredgewidth=1.5, zorder=8, label="Combate")
    cb = fig.colorbar(cf, ax=ax, pad=0.02)
    cb.set_label(ps.bold_math(r"$P_s$  [m/s]"), fontsize=9, fontweight="bold")
    ps.style_axes(ax, r"Envolvente de vuelo · contornos de $P_s$  ($n=1$)",
                  "Número de Mach", "Altitud  [km]", legend="upper right", grid=False)
    ps.footer(fig)


# CATEGORÍA 3 · Empuje requerido vs disponible
def plot_thrust(fig, dto: ResultsDTO, config: FullConfig):
    fig.clear()
    ax = fig.add_subplot(111)
    d = dg.thrust_curves(dto, config)
    curves = sorted(d["curves"].items())
    a_sl = 340.3
    for i, (h, c) in enumerate(curves):
        col = CYCLE[i % len(CYCLE)]
        ax.plot(c["v"], c["TR"] / 1000.0, color=col, lw=2.1,
                label=rf"$T_R$  $h$={h/1000:.0f} km")
        ax.plot(c["v"], c["TA"] / 1000.0, color=col, lw=1.7, ls="--",
                label=rf"$T_A$  $h$={h/1000:.0f} km")
        ax.plot([c["v"][0]], [c["TR"][0] / 1000.0], "o", ms=4, color=col,
                markeredgecolor="white")

    ps.style_axes(ax, r"Empuje requerido ($T_R$) vs disponible ($T_A$)",
                  "Velocidad verdadera TAS  [m/s]", "Empuje  [kN]", legend="upper center")
    ax.set_title(ax.get_title(), pad=26, fontweight="bold")  # espacio entre eje sup. y título
    ax.set_ylim(bottom=0)
    v_min_stall = min(c["v"][0] for _, c in curves)
    ax.set_xlim(left=max(0, v_min_stall * 0.88))
    from matplotlib.ticker import FixedLocator
    secax = ax.secondary_xaxis("top", functions=(lambda v: v / a_sl, lambda M: M * a_sl))
    x_lo, x_hi = ax.get_xlim()
    m_lo, m_hi = x_lo / a_sl, x_hi / a_sl
    mach_ticks = [m for m in np.arange(0.0, 1.21, 0.2) if m_lo <= m <= m_hi]
    secax.xaxis.set_major_locator(FixedLocator(mach_ticks))
    secax.set_xlabel(ps.bold_math(r"Número de Mach  ($M = V/a_0$)"), fontsize=10,
                     labelpad=6)
    ps.footer(fig)


# CATEGORÍA 3 · Empuje por altitud (detalle: exceso/déficit de potencia)
def plot_thrust_detail(fig, dto: ResultsDTO, config: FullConfig):
    fig.clear()
    d = dg.thrust_curves(dto, config)
    curves = sorted(d["curves"].items())
    axes = fig.subplots(1, len(curves), sharey=True)
    if len(curves) == 1:
        axes = [axes]
    for ax, (h, c) in zip(axes, curves):
        v = c["v"]
        TR = c["TR"] / 1000.0
        TA = c["TA"] / 1000.0
        ax.plot(v, TR, color=BLUE_PRIMARY, lw=2.1, label=r"$T_R$ (requerido)")
        ax.plot(v, TA, color=RED_VIOLATED, lw=2.0, ls="--", label=r"$T_A$ (disponible)")
        # Exceso (verde) y déficit (rojo) de potencia
        ax.fill_between(v, TR, TA, where=(TA >= TR), color=GREEN_OK, alpha=0.18,
                        interpolate=True, label="Exceso de potencia")
        ax.fill_between(v, TR, TA, where=(TA < TR), color=RED_VIOLATED, alpha=0.14,
                        interpolate=True, label="Déficit de potencia")
        # Máximo exceso de empuje
        diff = TA - TR
        imax = int(np.argmax(diff))
        if diff[imax] > 0:
            ax.plot([v[imax]], [TA[imax]], "o", ms=7, color=GREEN_OK,
                    markeredgecolor="white", zorder=6)
            ps.annotate(ax, v[imax], TA[imax], "Máx exceso", dx=-4, dy=12,
                        color=GREEN_OK)
        imin = int(np.argmin(TR))
        ax.axvline(v[imin], color=MUTED, ls=":", lw=1.2)
        ax.annotate("min $T_R$ (máx autonomía)", xy=(v[imin], TR[imin]),
                    xytext=(10, -15), textcoords="offset points", fontsize=7.5,
                    color=MUTED, ha="left", va="top")
        ax.set_title(ps.bold_math(rf"$h$ = {h/1000:.0f} km"), fontsize=12,
                     fontweight="bold")
        ax.set_xlabel("TAS  [m/s]", fontweight="bold")
        ax.grid(True, alpha=0.3)
        ax.set_ylim(bottom=0)
    axes[0].set_ylabel("Empuje  [kN]", fontweight="bold")
    axes[-1].legend(loc="upper right", fontsize=8)
    fig.suptitle(ps.bold_math(r"Empuje $T_R$ vs $T_A$ (detalle por altitud)"),
                 fontweight="bold", fontsize=13)
    ps.footer(fig)


# CATEGORÍA 3 · Tasa de giro vs Mach
def plot_turn(fig, dto: ResultsDTO, config: FullConfig):
    fig.clear()
    ax = fig.add_subplot(111)
    d = dg.turn_rate(dto, config)
    m = d["mach"]
    ax.plot(m, d["omega_inst"], color=RED_VIOLATED, lw=2.4, label="Giro instantáneo")
    ax.plot(m, d["omega_sus"], color=BLUE_PRIMARY, lw=2.4, label="Giro sostenido")
    ax.fill_between(m, d["omega_sus"], color=BLUE_PRIMARY, alpha=0.10)

    omega_max = float(np.max(d["omega_inst"]))
    iva = int(np.argmax(d["omega_inst"]))
    ax.axvline(m[iva], color=MUTED, ls=":", lw=1.2)
    ax.text(m[iva] + 0.005, omega_max * 0.5,
            rf"$V_A$ = $M${m[iva]:.2f}  (veloc. de esquina)", 
            ha="left", va="center", fontsize=8.5, color=MUTED)
    ps.annotate(ax, m[iva], d["omega_inst"][iva],
                rf"$n_{{lim}}$={d['n_struct']:.1f}g", dx=8, dy=6,
                color=RED_VIOLATED)
    isus = int(np.argmax(d["omega_sus"]))
    ps.annotate(ax, m[isus], d["omega_sus"][isus],
                rf"Sostenido máx {d['omega_sus'][isus]:.1f}$^\circ$/s", dx=6, dy=-22)
    ps.style_axes(ax, rf"Tasa de giro vs Mach  ($h$ = {d['altitude_km']:.0f} km)",
                  "Número de Mach", r"Tasa de giro  [$^\circ$/s]", legend="upper left")
    ax.set_ylim(0, omega_max * 1.15)
    ps.footer(fig)


# CATEGORÍA 4 · Perfil de misión doble (altitud + peso vs distancia)
def plot_mission_double(fig, dto: ResultsDTO, config: FullConfig):
    fig.clear()
    ax1, ax2 = fig.subplots(2, 1, sharex=True, gridspec_kw={"height_ratios": [3, 2]})
    fig.set_layout_engine(None)
    fig.subplots_adjust(left=0.09, right=0.97, top=0.94, bottom=0.09, hspace=0.08)
    d = dg.mission_profile(dto, config)
    mw = dg.mission_weight(dto, config)
    pcol = dg.MISSION_PHASE_COLORS

    phs = d["phases"]
    x_obj0 = phs[3]["x0"]                 # inicio loiter
    x_obj1 = phs[6]["x1"]                 # fin ascenso de regreso a crucero
    h_top = d["h_cruise"] / 1000.0 * 1.15

    # --- Panel 1: altitud vs distancia recorrida ---
    seen = set()
    for (x0, h0, x1, h1, label) in d["segments"]:
        col = pcol.get(label, BLUE_PRIMARY)
        lab = label if label not in seen else None
        seen.add(label)
        ax1.plot([x0, x1], [h0 / 1000.0, h1 / 1000.0], lw=2.6, color=col, label=lab)
        ax1.fill_between([x0, x1], [h0 / 1000.0, h1 / 1000.0], 0, color=col, alpha=0.06)
    ax1.axhline(d["h_cruise"] / 1000.0, color=MUTED, ls=":", lw=1, alpha=0.6)
    for ax in (ax1, ax2):
        ax.axvspan(x_obj0, x_obj1, color="#FBBF24", alpha=0.10, lw=0)
        ax.axvline(x_obj0, color="#92400E", ls="--", lw=1.0, alpha=0.6)
        ax.axvline(x_obj1, color="#92400E", ls="--", lw=1.0, alpha=0.6)
    # Cota con doble flecha entre las dos líneas punteadas
    d_ops = d["d_loiter"] + d["d_combat"]
    y_cota = h_top * 1.03          # por encima de la altitud de crucero
    ax1.annotate("", xy=(x_obj1, y_cota), xytext=(x_obj0, y_cota),
                 arrowprops=dict(arrowstyle="<->", color="#92400E", lw=1.3))
    ax1.text((x_obj0 + x_obj1) / 2, y_cota,
             rf"{d_ops:.0f} km",
             ha="center", va="bottom", fontsize=7.5,
             color="#92400E", fontweight="bold")
    ax1.annotate("Operación sobre objetivo\n (no se aleja de base)",
                 xy=(x_obj1*1.15, h_top*1.08), ha="center", va="top",
                 fontsize=7.5, color="#92400E", fontweight="bold")
    ps.style_axes(ax1, "Perfil de misión", None,
                  "Altitud  [km]")
    ax1.legend(loc="lower center", ncol=5, fontsize=8.5)
    ax1.set_ylim(0, h_top*1.15)

    # Recuadro: alcance de misión vs distancia total recorrida
    ax1.text(0.015, 0.95,
             rf"Alcance de misión (ida+vuelta): {d['range_km']:.0f} km"
             "\n"
             rf"Distancia total recorrida: {d['total_km']:.0f} km"
             "\n"
             rf"(loiter {d['d_loiter']:.0f} km + combate {d['d_combat']:.0f} km"
             "\n"
             rf" + (taxi, ascenso y descenso) {d['d_ground']:.0f} km)",
             transform=ax1.transAxes, ha="left", va="top", fontsize=8.5,
             color=INK, bbox=dict(boxstyle="round,pad=0.35", facecolor="white",
                                  edgecolor="#CBD5E1", lw=0.8, alpha=0.95))

    # --- Panel 2: peso vs distancia, coloreado por fase (mismos colores) ---
    pts = mw["points"]
    w_floor = min(p[1] for p in pts) * 0.92
    for k in range(1, len(pts)):
        x0, w0, _ = pts[k - 1]
        x1, w1, ph = pts[k]
        col = pcol.get(ph, BLUE_DARK)
        ax2.plot([x0, x1], [w0, w1], lw=2.6, color=col)
        ax2.fill_between([x0, x1], [w0, w1], w_floor, color=col, alpha=0.07)
        if abs(x1 - x0) < 1e-6 and w1 < w0:        # caída discreta = soltado
            ax2.annotate("Soltado\narmas", xy=(x1, w0), xytext=(12, -8),
                         textcoords="offset points", fontsize=8, color=RED_VIOLATED,
                         arrowprops=dict(arrowstyle="->", color=RED_VIOLATED, lw=1.2))
    ax2.scatter([p[0] for p in pts], [p[1] for p in pts], s=22, color=INK,
                zorder=5, edgecolor="white")
    w_max = max(p[1] for p in pts)
    ax2.set_ylim(w_floor, w_max * 1.05)
    ps.style_axes(ax2, None, "Distancia recorrida  [km]", "Peso  [kg]")
    ps.footer(fig)


# CATEGORÍA 4 · Payload-Range
def plot_payload_range(fig, dto: ResultsDTO, config: FullConfig):
    fig.clear()
    ax = fig.add_subplot(111)
    d = dg.payload_range(dto, config)
    R, P = d["ranges_km"], d["payloads_kg"]
    A, B, C, D = 0, 1, 2, 3                          # índices vértices

    # Tres zonas sombreadas (estilo manual de actuaciones)
    ax.fill_between([R[A], R[B]], [P[A], P[B]], color="#E5E7EB", alpha=0.9, lw=0)
    ax.fill_between([R[B], R[C]], [P[B], P[C]], color="#DBEAFE", alpha=0.9, lw=0)
    ax.fill_between([R[C], R[D]], [P[C], P[D]], color="#FEE2E2", alpha=0.9, lw=0)

    ax.text((R[A] + R[B]) / 2, P[A] * 0.5, "Máxima\ncarga útil", ha="center",
            va="center", fontsize=9, color="#475569", fontweight="bold")
    ax.text((R[B] + R[C]) / 2, P[B] * 0.42, "Intercambio\ncombustible/carga",
            ha="center", va="center", fontsize=8.5, color="#1E40AF", fontweight="bold")
    ax.text((R[C] + R[D]) / 2, P[C] * 0.2, "Intercambio\ncarga/alcance",
            ha="center", va="center", fontsize=8.5, color="#B91C1C", fontweight="bold")

    # Línea principal + vértices A-B-C-D en círculos rojos
    ax.plot(R, P, "-", color=BLUE_DARK, lw=2.6, zorder=4)
    ax.plot(R, P, "o", color=RED_VIOLATED, ms=8, markeredgecolor="white",
            markeredgewidth=1.2, zorder=5)
    for x, y, lab in zip(R, P, d["labels"]):
        ax.annotate(lab, xy=(x, y), xytext=(6, 8), textcoords="offset points",
                    fontsize=10, color=RED_VIOLATED, fontweight="bold")

    ps.style_axes(ax, r"Diagrama Payload-Range", r"Alcance  [km]",
                  r"Payload  [kg]")
    ax.set_ylim(0, max(P) * 1.15)
    ax.set_xlim(left=0)
    ps.footer(fig)


# CATEGORÍA 4 · Payload-Radius (radio táctico)
def plot_payload_radius(fig, dto: ResultsDTO, config: FullConfig):
    fig.clear()
    ax = fig.add_subplot(111)
    d = dg.payload_radius(dto, config)
    ideal, tact, P = d["ideal_radius"], d["tactical_radius"], d["payloads_kg"]
    req = d["req_radius_km"]

    IDEAL_COLOR = "#D97706"       # naranja/ámbar para B', C', D'
    ax.plot(ideal, P, "--", color=MUTED, lw=1.8, label="Radio s/ loiter+combate (ref.)")
    ax.plot(tact, P, "-", color=BLUE_DARK, lw=2.6, label="Radio de combate (táctico)")
    ax.fill_between(tact, P, color=BLUE_PRIMARY, alpha=0.12)
    # Vértices tácticos (B, C, D) en rojo
    ax.plot(tact, P, "o", color=RED_VIOLATED, ms=7, markeredgecolor="white", zorder=5)
    for x, y, lab in zip(tact, P, d["labels"]):
        ax.annotate(lab, xy=(x, y), xytext=(6, 7), textcoords="offset points",
                    fontsize=9.5, color=RED_VIOLATED, fontweight="bold")
    # Vértices ideales B', C', D' (naranja) en la curva de radio ideal
    PRIME_LABELS = ["B'", "C'", "D'"]
    for x, y, lab in zip(ideal[1:], P[1:], PRIME_LABELS):
        ax.plot([x], [y], "o", ms=8, color=IDEAL_COLOR,
                markeredgecolor="white", markeredgewidth=1.0, zorder=6)
        ax.annotate(lab, xy=(x, y), xytext=(6, 7), textcoords="offset points",
                    fontsize=9.5, color=IDEAL_COLOR, fontweight="bold")

    ax.axvline(req, color=GREEN_OK, ls="-.", lw=1.8, alpha=0.85,
               label=rf"Radio requerido = {req:.0f} km")
    ax.annotate("B coincide con el\nradio requerido\n(restricción activa)",
                xy=(tact[1], P[1]), xytext=(-140, 22), textcoords="offset points",
                fontsize=8, color=GREEN_OK, fontweight="bold", ha="left",
                arrowprops=dict(arrowstyle="->", color=GREEN_OK, lw=1.2))

    ax.text(0.98, 0.06,
            rf"Coste de loiter+combate en B: $\Delta R\approx${d['d_pen_km']:.0f} km de radio",
            transform=ax.transAxes, ha="right", fontsize=8.5, color=MUTED,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor="#CBD5E1"))
    ps.style_axes(ax, "Diagrama Payload-Radius (radio de combate)",
                  "Radio de combate  [km]", "Payload  [kg]", legend="lower left")
    ax.set_ylim(0, max(P) * 1.15)
    ax.set_xlim(left=0)
    ps.footer(fig)


# CATEGORÍA 4 · Planta del ala
def plot_planform(fig, dto: ResultsDTO, config: FullConfig):
    """Esquema técnico paramétrico de la semiala (estilo Raymer/Roskam)."""
    fig.clear()
    ax = fig.add_subplot(111)
    d = dg.planform(dto, config)
    b2, c_r, c_t = d["b_2"], d["c_r"], d["c_t"]
    tan_le = d["tan_le"]
    BLACK = "#111827"
    GREEN_M, PURPLE_M = "#16A34A", "#7C3AED"

    poly_y = list(d["ys"]) + [d["ys"][0]]
    poly_x = list(d["xs"]) + [d["xs"][0]]
    ax.fill(d["ys"], d["xs"], color="#F1F5F9", zorder=1)
    ax.plot(poly_y, poly_x, color=BLACK, lw=2.4, zorder=4)

    # MAC (verde) y MGC (púrpura)
    ax.plot([d["y_mac"], d["y_mac"]], [d["x_mac"], d["x_mac"] + d["mac"]],
            color=GREEN_M, lw=3.0, zorder=6, label=rf"MAC = {d['mac']:.2f} m")
    ax.plot([d["y_mgc"], d["y_mgc"]], [d["x_mgc"], d["x_mgc"] + d["mgc"]],
            color=PURPLE_M, lw=3.0, zorder=6, label=rf"MGC = {d['mgc']:.2f} m")
    # Valores numéricos de los parámetros dimensionales en la leyenda
    ax.plot([], [], lw=0, label=rf"$c_r$ = {c_r:.2f} m")
    ax.plot([], [], lw=0, label=rf"$c_t$ = {c_t:.2f} m")
    ax.plot([], [], lw=0, label=rf"$b/2$ = {b2:.2f} m")
    ax.plot([], [], lw=0, label=rf"$\lambda$ = {c_t / c_r:.3f}")

    # Líneas auxiliares para yMAC y xMAC
    ax.plot([d["y_mac"], d["y_mac"]], [0, d["x_mac"]], color=GREEN_M, ls="--", lw=1.2, alpha=0.7)
    ax.plot([0, d["y_mac"]], [d["x_mac"], d["x_mac"]], color=GREEN_M, ls="--", lw=1.2, alpha=0.7)
    ax.annotate(r"$y_{MAC}$", xy=(d["y_mac"], d["x_mac"] / 2), xytext=(10, 0),
                textcoords="offset points", fontsize=14, color=GREEN_M, va="center")
    ax.annotate(r"$x_{MAC}$", xy=(d["y_mac"] / 2, d["x_mac"]), xytext=(0, -12),
                textcoords="offset points", fontsize=14, color=GREEN_M, ha="center", va="top")
    # MAC a la IZQUIERDA de la línea MAC
    ax.annotate("MAC", xy=(d["y_mac"], d["x_mac"] + d["mac"] / 2), xytext=(-10, 0),
                textcoords="offset points", fontsize=13, color=GREEN_M, fontweight="bold",
                ha="right")
    ax.annotate("MGC", xy=(d["y_mgc"], d["x_mgc"] + d["mgc"] / 2), xytext=(10, 0),
                textcoords="offset points", fontsize=13, color=PURPLE_M, fontweight="bold")

    # Cota cuerda raíz Cr (en Y=0) y de punta Ct (en Y=b/2)
    ax.annotate("", xy=(-0.04 * b2, c_r), xytext=(-0.04 * b2, 0),
                arrowprops=dict(arrowstyle="<->", color=BLACK, lw=1.4))
    ax.annotate(r"$c_r$", xy=(-0.04 * b2, c_r / 2), xytext=(-12, 0),
                textcoords="offset points", fontsize=13, color=BLACK, ha="right", va="center")
    ax.annotate("", xy=(b2 + 0.04 * b2, b2 * tan_le + c_t), xytext=(b2 + 0.04 * b2, b2 * tan_le),
                arrowprops=dict(arrowstyle="<->", color=BLACK, lw=1.4))
    ax.annotate(r"$c_t$", xy=(b2 + 0.04 * b2, b2 * tan_le + c_t / 2), xytext=(10, 0),
                textcoords="offset points", fontsize=13, color=BLACK, va="center")

    # Cota semienvergadura b/2
    te_max = max(c_r, b2 * tan_le + c_t)
    y_dim = te_max * 1.05
    ax.plot([0, b2], [y_dim, y_dim], color=BLACK, lw=0.9, ls="--", alpha=0.5)
    ax.annotate("", xy=(b2, y_dim), xytext=(0, y_dim),
                arrowprops=dict(arrowstyle="<->", color=BLACK, lw=1.6))
    ax.annotate(r"$b/2$", xy=(b2 / 2, y_dim), xytext=(0, 9),
                textcoords="offset points", fontsize=14, color=BLACK, ha="center",
                fontweight="bold")

    # Arco del ángulo de flecha del LE
    r_arc = 0.28 * b2
    ang = d["sweep_le_deg"]
    ang_rad = math.radians(ang)
    ax.plot([0, r_arc * 2.1], [0, 0], color=BLACK, ls="--", lw=1.0)
    # Línea en la dirección del LE
    le_end_y = r_arc * math.cos(ang_rad)
    le_end_x = r_arc * math.sin(ang_rad)
    ax.plot([0, le_end_y], [0, le_end_x], color=BLACK, ls="--", lw=1.0)
    theta_arr = np.linspace(0, ang_rad, 40)
    r_small = r_arc * 0.55
    ax.plot(r_small * np.cos(theta_arr), r_small * np.sin(theta_arr),
            color=BLACK, lw=1.6)
    # Etiqueta en el punto medio del arco
    mid_y = r_arc * 0.52 * math.cos(ang_rad / 2)
    mid_x = r_arc * 0.92 * math.sin(ang_rad / 2)
    ax.annotate(r"$\Lambda_{LE}$",
                xy=(mid_y, mid_x), xytext=(16, 8),
                textcoords="offset points", fontsize=14,
                color=BLACK)

    ax.plot([], [], lw=0, label=rf"$\Lambda_{{LE}}$ = {ang:.0f}°")

    ax.margins(y=0.15)                               # 15% de aire en eje Y
    ax.set_aspect("equal", adjustable="datalim")
    ax.invert_yaxis()                                # morro arriba
    ax.grid(False)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(top=False, right=False, which="both")
    ps.style_axes(ax, "Geometría en planta del semiala",
                  "Envergadura  y  [m]", "Estación longitudinal  x  [m]",
                  legend="lower left", grid=False)
    ps.footer(fig)


# ECUACIONES FUNDAMENTALES POR GRÁFICA (se muestran bajo el lienzo)
#   key -> {"equations": [(título, latex), ...], "note": "observación"}
CHART_INFO = {
    "weights": {"equations": [
        ("Cierre de masas (punto fijo)", r"$MTOW = OEW + W_{fuel} + W_{payload}$"),
        ("Ala — CER Fighter/Attack", r"$W_w = 0.0103\,K_{dw}(W_{dg}N_z)^{0.5}S^{0.622}AR^{0.785}(t/c)^{-0.4}(\cos\Lambda)^{-1}$"),
        ("Fuselaje — CER Fighter/Attack", r"$W_f = 0.499\,K_{dwf}\,W_{dg}^{0.35}N_z^{0.25}L^{0.5}D^{1.534}$"),
        ("Empenaje en V — CER", r"$W_{vt} = C_{VT}\,(N_z\,MTOW)^{0.414}\,S_{vt}^{0.896}$"),
        ("Tren de aterrizaje (fracción)", r"$W_{lg} = f_{lg}\,MTOW$"),
        ("Subsistemas (desglose)", r"$\sum W_{sys} = f_{sys}\,MTOW$"),
        ("Motor (calibración turbofan)", r"$W_{eng} = f_{eng}\,T_{SL}$"),
    ], "note": "El donut reparte el MTOW en OEW / combustible / payload. Las barras desglosan la OEW por componente. Cada barra es una CER: estructura (ala, fuselaje, cola en V) por las Statistical Group Weights Fighter/Attack de Raymer (cap. 15), y tren, subsistemas y motor por fracciones calibradas sobre referentes de la misma clase. Se aplica un factor de reducción composite sobre la estructura. La aviónica es un input fijo. La carga última $N_z$ se fija según el factor de seguridad estructural aplicable a aeronaves no tripuladas."},

    "polar": {"equations": [
        ("Polar parabólica", r"$C_D = C_{D0} + K\,C_L^2$"),
        ("Factor de resistencia inducida", r"$K = \dfrac{1}{\pi\,AR\,e}$"),
        ("Eficiencia máxima y su C_L", r"$(L/D)_{max} = \dfrac{1}{2\sqrt{K\,C_{D0}}}\quad\mathrm{en}\;\;C_L=\sqrt{C_{D0}/K}$"),
    ], "note": "La curva es la polar parabólica con el $C_{D0}$ (component buildup) y el $K$ (resistencia inducida) del diseño óptimo. $e$ es la eficiencia de Oswald que el modelo calcula internamente como función de $AR$ y flecha. El tramo gris discontinuo más allá de $C_{L,max}$ es el modelo parabólico extrapolado, ya no físico: la capa límite está separada (post-stall). El punto verde marca $(L/D)_{max}$, el naranja el crucero real y la recta roja vertical el $C_{D0}$."},

    "cd0_buildup": {"equations": [
        ("Component buildup (Raymer)", r"$C_{D0} = \dfrac{1}{S_{ref}}\sum_i C_{f,i}\,FF_i\,Q_i\,S_{wet,i}$"),
        ("Fricción turbulenta (Prandtl-Schlichting)", r"$C_f = \dfrac{0.455}{(\log_{10}Re)^{2.58}\,(1+0.144\,M^2)^{0.65}}$"),
        ("Factor de forma del ala", r"$FF = [\,1+2(t/c)+100(t/c)^4\,]\,(1.34\,M^{0.18}\cos^{0.28}\!\Lambda)$"),
    ], "note": "Cada barra es la contribución de un componente (ala, fuselaje, cola en V) a través de su área mojada $S_{wet}$, su coeficiente de fricción $C_f$ (Reynolds local con corrección de compresibilidad) y su factor de forma $FF$. Sobre el conjunto limpio se suman márgenes por misceláneos (tomas de aire, antenas, fugas), excrescencias y rugosidad, y la penalización del conducto en S furtivo. Demuestra el método analítico, no un $C_{D0}$ como parámetro libre."},

    "ld_mach": {"equations": [
        ("Eficiencia aerodinámica", r"$\dfrac{L}{D} = \dfrac{C_L}{C_D},\qquad C_L = \dfrac{W}{q\,S}$"),
        ("Resistencia con onda", r"$C_D = C_{D0} + K\,C_L^2 + C_{D,w}$"),
        ("Mach de divergencia (Korn-Mason)", r"$M_{dd} = \dfrac{\kappa_A}{\cos\Lambda} - \dfrac{t/c}{\cos^2\Lambda} - \dfrac{C_L}{10\cos^3\Lambda}$"),
        ("Resistencia de onda (Lock)", r"$C_{D,w} = 20\,(M - M_{cr})^4,\quad M_{cr} = M_{dd} - 0.108$"),
    ], "note": "Para cada altitud se barre el Mach: el $C_L=W/(qS)$ cambia con la velocidad y la densidad, y con él la resistencia. $\kappa_A$ depende del tipo de perfil empleado. $M_{dd}$ se capa físicamente a la unidad. La caída brusca de $L/D$ cerca del Mach de divergencia es la resistencia de onda (choque transónico). Volar por debajo la evita. A mayor altitud, mayor $C_L$ de crucero y antes aparece la onda."},

    "spanwise": {"equations": [
        ("Carga del ala trapezoidal", r"$c_{trap}(y) \propto c(y) = c_r + (c_t - c_r)\,\eta,\;\;\eta = y/(b/2)$"),
        ("Distribución elíptica ideal", r"$c_{elip}(y) = \dfrac{4S}{\pi b}\sqrt{1-(2y/b)^2}$"),
        ("Aproximación de Schrenk", r"$c\,c_l(y) = \frac{1}{2}\,[\,c_{trap}(y) + c_{elip}(y)\,]$"),
    ], "note": "Schrenk (azul) promedia la carga del ala trapezoidal real (verde, proporcional a la cuerda) con la elíptica ideal (la de mínima resistencia inducida). Las tres curvas se normalizan al área para comparar la forma. El pico de carga se desplaza hacia la punta al aumentar el estrechamiento $\lambda$, favoreciendo la entrada en pérdida por la punta (peligrosa: pérdida de control de alerón). El washout y el alivio en raíz se controlan aparte en el margen de pérdida del MDAO."},

    "cm_cl": {"equations": [
        ("Momento de cabeceo", r"$C_m = C_{m0} + \dfrac{\partial C_m}{\partial C_L}\,C_L$"),
        ("Pendiente = menos margen estático", r"$\dfrac{\partial C_m}{\partial C_L} = -SM$"),
    ], "note": "Cada recta es $C_m(C_L)$ para un estado de carga (full, empty y aft-crítico), con pendiente $-SM$ y ordenada $C_{m0}$ (perfil supercrítico). Con estabilidad relajada ($SM<0$) la pendiente es POSITIVA: una perturbación que aumente $C_L$ genera un momento que la amplifica, avión divergente, estabilizado por el control de vuelo (FBW). El aft-crítico tiene el $SM$ más negativo (pendiente más empinada). Es la firma gráfica de la estabilidad relajada."},

    "vn": {"equations": [
        ("Pérdida acelerada (parábolas)", r"$n = \left(\dfrac{V}{V_S}\right)^2$"),
        ("Velocidad de maniobra", r"$V_A = V_S\sqrt{n_{lim}}$"),
        ("Carga última (factor de seguridad)", r"$n_{ult} = SF\cdot n_{lim}$"),
        ("Velocidades de diseño", r"$V_D = M_{dd}\,a_0,\qquad V_C = V_D/1.25$"),
    ], "note": "Las parábolas izquierdas son el límite de pérdida $n=(V/V_S)^2$, que se capan en $n_{lim}$ (obtenido dividiendo la carga última entre el factor de seguridad). La rama negativa es más ancha porque el perfil con curvatura tiene $|C_{L,min}|<C_{L,max}$. $V_D$ se ata al Mach de divergencia $M_{dd}$ evaluado a nivel del mar (peor caso de presión dinámica) y $V_C=V_D/1.25$ (FAR 25.335). Zonas: verde operación normal, amarillo precaución, naranja daño, rojo fallo estructural."},

    "cg": {"equations": [
        ("CG por momentos", r"$x_{CG} = \frac{\sum_i m_i\,x_i}{\sum_i m_i}$"),
        ("Margen estático", r"$SM = \dfrac{x_{NP} - x_{CG}}{\bar c}$"),
        ("Punto neutro (ala + cola + fuselaje)", r"$\dfrac{x_{NP}}{\bar c} = \dfrac{x_{ac,w}}{\bar c} + \eta_t\dfrac{C_{L\alpha,t}}{C_{L\alpha,w}}V_H\!\left(1-\dfrac{d\epsilon}{d\alpha}\right) + \Delta x_{fus}$"),
    ], "note": "Cada punto del recorrido es el CG en %MAC calculado por suma de momentos. La banda verde es el rango admisible de $SM$ y la línea roja el punto neutro. El recorrido sigue la secuencia de vaciado estándar: tanque de FUSELAJE primero (conserva fuel en el ala, alivia la flexión en raíz). Como el tanque de fuselaje va adelantado esa secuencia retrasa el CG. El estado aft-crítico (fuselaje vacío, ala llena, armas soltadas) marca el $SM$ mínimo, restringido en el MDAO. $d\epsilon/d\\alpha$ se calcula por DATCOM y la contribución desestabilizadora del fuselaje por Multhopp. $SM<0$ implica estabilidad relajada, que exige FBW."},

    "constraint": {"equations": [
        ("Giro sostenido (T=D, L=nW)", r"$\dfrac{T}{W} = \dfrac{q\,C_{D0}}{W/S} + \dfrac{K\,n^2\,(W/S)}{q}$"),
        ("Ascenso (tasa RoC)", r"$\dfrac{T}{W} = \dfrac{RoC}{V} + \dfrac{q\,C_{D0}}{W/S} + \dfrac{K\,(W/S)}{q}$"),
        ("Crucero nivelado", r"$\dfrac{T}{W} = \dfrac{q\,C_{D0}}{W/S} + \dfrac{K\,(W/S)}{q}$"),
        ("Exceso de potencia en combate", r"$\dfrac{T}{W} = \dfrac{P_s}{V} + \dfrac{q\,C_{D0}}{W/S} + \dfrac{K\,n^2\,(W/S)}{q}$"),
        ("Despegue (carrera de aceleración)", r"$s_{GR} = \dfrac{V_{LOF}^2}{2\,a_{avg}},\quad V_{LOF}=1.1\,V_S$"),
        ("Aterrizaje (distancia total)", r"$s_{land} = s_{app} + s_{flare} + \dfrac{V_{TD}^2}{2\,a_{dec}}$"),
        ("Línea de pérdida (vertical)", r"$\left(\dfrac{W}{S}\right)_{stall} = \frac{1}{2}\rho\,V_{S,ref}^2\,C_{L,max}$"),
    ], "note": "Cada curva es el $T/W$ mínimo que cumple una restricción en función de la carga alar $W/S$. La envolvente es su máximo y define la frontera de la región factible (verde). El lapse de empuje del turbofan (caída con altitud y Mach) se incorpora en el denominador de todas las curvas de $T/W$. Las líneas verticales son límites de pérdida y aterrizaje independientes del $T/W$. El MDAO clava el óptimo sobre la restricción activa: el menor $W/S$ y $T/W$ compatibles, es decir el ala y el motor más pequeños posibles."},

    "ps_envelope": {"equations": [
        ("Potencia específica (Boyd EM)", r"$P_s = \dfrac{V\,(T - D)}{W}$"),
        ("Empuje con lapse (Mattingly)", r"$T = T_{SL}\,\sigma^{0.7}(1 - 0.49\sqrt{M})$"),
        ("Resistencia (vuelo nivelado n=1)", r"$D = q\,S\,(C_{D0} + K\,C_L^2 + C_{D,w}),\;\;C_L = \dfrac{W}{q\,S}$"),
    ], "note": "Para cada par (altitud, Mach) se evalúa $P_s=V(T-D)/W$ en vuelo nivelado ($n=1$), con la resistencia de onda Korn-Mason incluida. La isolínea $P_s=0$ (negra) es el techo sostenido a cada Mach: dentro hay margen para acelerar o subir, fuera el avión decelera. Se marcan los puntos de crucero y de combate. El mapa de color revela si el diseño tiene energía suficiente en ambos."},

    "thrust": {"equations": [
        ("Empuje requerido", r"$T_R = D = q\,S\,(C_{D0} + K\,C_L^2 + C_{D,w})$"),
        ("Empuje disponible (lapse)", r"$T_A = T_{SL}\,\sigma^{0.7}(1 - 0.49\sqrt{M})$"),
        ("Sustentación de crucero", r"$C_L = \dfrac{W}{q\,S},\qquad q = \frac{1}{2}\rho V^2$"),
    ], "note": "$T_R$ (curva sólida) es la resistencia total a vencer en vuelo nivelado. $T_A$ (discontinua) el empuje del turbofan tras el lapse. Su intersección a la derecha fija la velocidad máxima a cada altitud. El mínimo de $T_R$ marca la velocidad de máxima autonomía (mínimo consumo, vuelo a $(L/D)_{max}$). Al subir de altitud $T_A$ cae (menor $\sigma$) y la envolvente de baja velocidad se cierra porque sube $V_{stall}$. El eje superior traduce TAS a Mach."},

    "thrust_detail": {"equations": [
        ("Exceso de potencia", r"$\Delta T = T_A - T_R\;\;(>0\Rightarrow\mathrm{acelera/trepa})$"),
        ("Mínimo consumo (autonomía)", r"$V_{opt}:\;\min(T_R)\Rightarrow (L/D)_{max}$"),
    ], "note": "Cada panel es una altitud. La zona verde ($T_A>T_R$) es exceso de potencia disponible para trepar o acelerar. La roja ($T_A<T_R$) es déficit, vuelo imposible en régimen permanente. El punto verde marca el máximo exceso de empuje. La línea punteada señala la velocidad de mínimo $T_R$, donde el avión vuela a $(L/D)_{max}$: máxima autonomía y mínimo consumo. Al ganar altitud el exceso se reduce y la envolvente se estrecha."},

    "turn": {"equations": [
        ("Tasa de giro", r"$\omega = \dfrac{g\sqrt{n^2 - 1}}{V}$"),
        ("Factor de carga instantáneo", r"$n_{inst} = \min(n_{aero},\,n_{struct})$"),
        ("Límite aerodinámico", r"$n_{aero} = \dfrac{q\,C_{L,max}}{W/S}$"),
        ("Giro sostenido (T=D)", r"$n_{sus}^2 = \dfrac{(T_A - q S C_{D0})\,qS}{K\,W^2}$"),
    ], "note": "Giro instantáneo (rojo): máximo $n$ permitido por pérdida ($n_{aero}$) o por estructura ($n_{struct}=n_{ult}/SF$), sin restricción de empuje, solo sostenible unos segundos perdiendo energía. Giro sostenido (azul): el que permite el empuje con $T=D$, sin perder velocidad ni altitud. El pico de la curva instantánea es la velocidad de esquina $V_A$, donde $n_{aero}=n_{lim}$: el punto de máxima maniobrabilidad. Evaluado a la altitud de combate."},

    "mission": {"equations": [
        ("Crucero (Breguet, jet)", r"$\dfrac{W_{i+1}}{W_i} = \exp\!\left(-\dfrac{R\,g\,c}{V\,(L/D)}\right)$"),
        ("Loiter (autonomía)", r"$\dfrac{W_{i+1}}{W_i} = \exp\!\left(-\dfrac{E\,g\,c}{(L/D)_{max}}\right)$"),
        ("Combate (cálculo explícito)", r"$\Delta w_{comb} = T_{comb}\,c_{comb}\,t_{comb}$"),
        ("Soltado de armas (salto discreto)", r"$W^{+} = W^{-} - W_{payload}$"),
    ], "note": "El panel de peso baja fase a fase aplicando estas fracciones: warm-up, despegue, ascenso, crucero ida, loiter ISR, combate, soltado de armas (caída discreta), crucero de regreso y aterrizaje. El crucero usa el $L/D$ real del diseño. El loiter usa $(L/D)_{max}$. El combate se calcula con el empuje real a altitud con su lapse, no con una fracción arbitraria. El eje X es distancia RECORRIDA: el loiter y el combate orbitan sobre el objetivo sin alejarse, por eso el total supera el alcance ida+vuelta. Se añade una reserva táctica sobre el combustible quemado."},

    "payload_range": {"equations": [
        ("Alcance de Breguet", r"$R = \dfrac{V}{g\,c}\,\dfrac{L}{D}\,\ln\dfrac{W_0}{W_0 - W_f}$"),
        ("Combustible máximo (volumen)", r"$W_{f,max} = \rho_{fuel}\,(V_{ala} + V_{fus})$"),
        ("Combustible usable (con reserva)", r"$W_{f,usable} = W_f / (1 + f_{res})$"),
    ], "note": "Tres tramos: A→B vuela con payload máximo y combustible creciente hasta llenar tanques (MTOW limita). B→C cambia payload por combustible manteniendo MTOW constante. C→D es el ferry (sin payload, tanques llenos, máximo alcance). El combustible máximo $W_{f,max}$ lo fija la capacidad volumétrica real de los tanques (alar + saddle de fuselaje), no un valor libre. Se descuenta la reserva táctica antes de aplicar Breguet."},

    "payload_radius": {"equations": [
        ("Balance de combustible (cuadrática)", r"$A\,a^2 + B\,a + C = 0,\qquad a = e^{-kR}$"),
        ("Constante de Breguet", r"$k = \dfrac{g\,c}{V\,(L/D)}$"),
        ("Radio a partir de la raíz", r"$R = -\ln(a)/k$"),
        ("Radio requerido", r"$R_{req} = R_{mision}/2$"),
    ], "note": "A diferencia del payload-range (alcance de solo ida), el radio de combate exige ida + vuelta CON loiter y combate sobre el objetivo. Como el factor de crucero $a=e^{-kR}$ aparece en las dos piernas, el balance de combustible es una cuadrática en $a$, de la que se toma la raíz física ($0<a<1$) y $R=-\ln(a)/k$. La curva ideal (sin loiter ni combate) es la referencia: su separación con la táctica es el coste en radio de las operaciones ISR. En el vértice B el radio táctico coincide con el requerido, señal de restricción de misión activa en el óptimo."},

    "planform": {"equations": [
        ("Envergadura", r"$b = \sqrt{S\,AR}$"),
        ("Cuerda en la raíz", r"$c_r = \dfrac{2S}{b\,(1+\lambda)}$"),
        ("Cuerda en la punta", r"$c_t = \lambda\,c_r$"),
        ("Cuerda media aerodinámica (MAC)", r"$\bar c = \dfrac{2}{3}\,c_r\,\dfrac{1+\lambda+\lambda^2}{1+\lambda}$"),
        ("Posición spanwise de la MAC", r"$y_{MAC} = \dfrac{b}{6}\,\dfrac{1+2\lambda}{1+\lambda}$"),
        ("Flecha del borde de ataque", r"$\tan\Lambda_{LE} = \tan\Lambda_{c/4} + \dfrac{1-\lambda}{AR(1+\lambda)}$"),
        ("Retraso longitudinal de la MAC", r"$x_{MAC} = y_{MAC}\,\tan\Lambda_{LE}$"),
        ("Cuerda media geométrica (MGC)", r"$MGC = \dfrac{c_r + c_t}{2}$"),
    ], "note": "El contorno de la semiala se levanta de la geometría trapezoidal (Raymer 7.2–7.4): de $S$ y $AR$ sale la envergadura, y de $S$, $b$ y el estrechamiento $\lambda=c_t/c_r$ salen las cuerdas de raíz y punta. La MAC (verde) es la cuerda de referencia para el CG y el punto neutro, situado en $(y_{MAC},\,x_{MAC})$. La MGC (púrpura) es la media aritmética. La flecha $\Lambda_{LE}$ se obtiene de $\Lambda_{c/4}$ con la identidad trapezoidal y es la que usan el modelo de Oswald y la resistencia de onda."},

    "tornado": {"equations": [
        ("Sensibilidad relativa", r"$S_i = \dfrac{\Delta f / f}{\Delta x_i / x_i}$"),
        ("Perturbación aplicada", r"$x_i \rightarrow x_i\,(1 \pm 0.10)$"),
    ], "note": "Cada barra mide cuánto cambia el objetivo (coste unitario) al perturbar $\pm10\%$ una variable de diseño, recalculando el MDAO completo. Las variables se ordenan por impacto (las más influyentes arriba), de ahí la forma de tornado. Identifica las palancas de diseño dominantes y dónde conviene afinar requisitos o reducir incertidumbre. Azul = $+10\%$, ámbar = $-10\%$."},

    "convergence": {"equations": [
        ("Objetivo (coste unitario DAPCA IV)", r"$\min_x\; f(x) = c_{unit}$"),
        ("Infactibilidad máxima", r"$g_{viol} = \max_j\,\dfrac{\max(0,\;g_j - g_j^{lim})}{|g_{j,ref}|}$"),
    ], "note": "Eje izquierdo (azul): el objetivo $c_{unit}$ (coste unitario DAPCA IV), iteración a iteración. Eje derecho (rojo): la violación máxima de restricciones $g_{viol}$ normalizada por su escala. Ha convergido cuando el objetivo se estabiliza y $g_{viol}\\to0$ (todas las restricciones satisfechas). Picos transitorios de infactibilidad son normales mientras el optimizador explora el límite de la región factible."},
}


# ── Métrica del lienzo de ecuaciones (layout dos columnas: eqs izq, obs der) ──
_EQ_ROW_PX = 80      # altura por ecuación (título + fórmula apilados)
_NOTE_HDR_PX = 30    # cabecera "Observaciones:"
_NOTE_LINE_PX = 22   # cada línea de observación ajustada
_TOP_PX = 44         # margen superior (da aire a la primera ecuación)
_BOT_PX = 20         # margen inferior
_NOTE_WRAP = 62      # caracteres de ajuste para la columna derecha


def _wrap_math(text: str, width: int) -> list:
    """textwrap.wrap que nunca rompe dentro de un bloque $...$."""
    import re
    tokens = re.split(r'(\$[^$]+\$)', text)
    words = []
    for tok in tokens:
        if tok.startswith('$') and tok.endswith('$'):
            words.append(tok)           # bloque math: tratar como palabra indivisible
        else:
            words.extend(tok.split())   # texto plano: dividir en palabras normales
    lines, current = [], ''
    for word in words:
        if not current:
            current = word
        elif len(current) + 1 + len(word) <= width:
            current += ' ' + word
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def equations_canvas_height(key: str) -> int:
    """Altura en px del lienzo: máximo entre la columna de ecuaciones y la de
    observaciones, calculado en píxeles para mantener fuente constante."""
    info = CHART_INFO.get(key, {})
    n_eq = len(info.get("equations", []))
    left_h = _TOP_PX + n_eq * _EQ_ROW_PX + _BOT_PX

    note = info.get("note", "")
    if note:
        lines = _wrap_math(note, _NOTE_WRAP)
        right_h = _TOP_PX + _NOTE_HDR_PX + len(lines) * _NOTE_LINE_PX + _BOT_PX
    else:
        right_h = 0

    return int(max(120, left_h, right_h))


def draw_equations(fig, key):
    """Dos columnas: ecuaciones (izq, 0–0.48) y observaciones (der, 0.52–1.0).
    Título de ecuación arriba, fórmula indentada debajo. El lienzo crece con el
    contenido para mantener el tamaño de fuente constante."""
    fig.clear()
    info = CHART_INFO.get(key)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    if not info:
        ax.text(0.5, 0.5, "—", ha="center", va="center", color=MUTED,
                transform=ax.transAxes, fontsize=10)
        return

    from matplotlib.lines import Line2D

    TITLE_FS, EQ_FS, HDR_FS, NOTE_FS = 11.5, 14.0, 11.5, 10.5
    X_TITLE = 0.025    # margen izquierdo del título
    X_EQ    = 0.050    # sangría de la fórmula
    X_DIV   = 0.500    # línea divisoria central
    X_RIGHT = 0.530    # inicio columna derecha

    eqs  = info.get("equations", [])
    note = info.get("note")
    H    = float(equations_canvas_height(key))

    # ── Columna izquierda: ecuaciones ─────────────────────────────────
    y_px = float(_TOP_PX)
    for title, eq in eqs:
        y_title = 1.0 - (y_px + 15.0) / H
        y_eq    = 1.0 - (y_px + 54.0) / H
        ax.text(X_TITLE, y_title, title + ":", fontsize=TITLE_FS,
                fontweight="bold", color="black", va="center",
                transform=ax.transAxes)
        ax.text(X_EQ, y_eq, eq, fontsize=EQ_FS, color="black", va="center",
                transform=ax.transAxes)
        y_px += _EQ_ROW_PX

    # ── Línea divisoria + columna derecha: observaciones ──────────────
    if note:
        ax.add_line(Line2D([X_DIV, X_DIV], [0.03, 0.97],
                           transform=ax.transAxes, color="#CCCCCC",
                           lw=1.0, solid_capstyle="butt"))

        y_note = 1.0 - _TOP_PX / H
        ax.text(X_RIGHT, y_note, "Observaciones:", fontsize=HDR_FS,
                fontweight="bold", color="black", va="top",
                transform=ax.transAxes)

        y_note_px = _TOP_PX + _NOTE_HDR_PX
        for line in _wrap_math(note, _NOTE_WRAP):
            y = 1.0 - (y_note_px + _NOTE_LINE_PX * 0.5) / H
            ax.text(X_RIGHT, y, line, fontsize=NOTE_FS, style="italic",
                    color="#444444", va="center", transform=ax.transAxes)
            y_note_px += _NOTE_LINE_PX


def draw_xdsm(_fig):  # stub vacío — XDSM eliminado
    pass


# REGISTRO POR CATEGORÍAS  —  (clave, etiqueta, función, kind)
CATEGORIES = [
    ("1 · Validación del optimizador", [
        ("convergence", "Convergencia", plot_convergence, "instant"),
        ("dv_history", "Historial de variables de diseño", plot_dv_history, "instant"),
        ("tornado", "Análisis de sensibilidad", plot_tornado, "study:tornado"),
        ("pareto", "Frontera de Pareto", plot_pareto, "study:pareto"),
    ]),
    ("2 · Síntesis multidisciplinar", [
        ("weights", "Análisis de pesos", plot_weight_breakdown, "instant"),
        ("polar", "Polar de resistencia", plot_drag_polar, "instant"),
        ("cd0_buildup", "Desglose de resistencia parásita", plot_cd0_buildup, "instant"),
        ("ld_mach", "L/D vs Mach", plot_ld_mach, "instant"),
        ("spanwise", "Distribución de sustentación", plot_spanwise, "instant"),
        ("cm_cl", "Momento de cabeceo (Cm-CL)", plot_cm_cl, "instant"),
        ("vn", "Diagrama V-n", plot_vn, "instant"),
        ("cg", "Recorrido del CG", plot_cg_travel, "instant"),
    ]),
    ("3 · Rendimiento y combate", [
        ("constraint", "Diagrama de restricciones", plot_constraint_diagram, "instant"),
        ("ps_envelope", "Envolvente de vuelo - potencia específica Ps", plot_ps_envelope, "instant"),
        ("thrust", "Empuje requerido vs disponible", plot_thrust, "instant"),
        ("thrust_detail", "Empujes (detalle)", plot_thrust_detail, "instant"),
        ("turn", "Tasa de giro vs Mach", plot_turn, "instant"),
    ]),
    ("4 · Operación y misión", [
        ("mission", "Perfil de misión (altitud + peso)", plot_mission_double, "instant"),
        ("payload_range", "Payload-Range", plot_payload_range, "instant"),
        ("payload_radius", "Payload-Radius", plot_payload_radius, "instant"),
        ("planform", "Geometría del semiala", plot_planform, "instant"),
    ]),
]
