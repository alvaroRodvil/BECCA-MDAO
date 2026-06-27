"""
Capa Model del MDAO-UCAV.

Contiene el grupo OpenMDAO `UCAVModel` y la fábrica `build_problem(config)`
que construye un `om.Problem` listo para optimizar a partir de un `FullConfig`.
"""

from __future__ import annotations

from typing import Optional

import openmdao.api as om

from modules.geometry import GeometryModule
from modules.propulsion import PropulsionModule
from modules.aerodynamics import AerodynamicsModule
from modules.mission import MissionModule
from modules.weights import SecondaryWeightsModule
from modules.performance import PerformanceConstraintsModule
from modules.stability import StabilityControlModule
from modules.cost import CostEstimationModule

from core.config import FullConfig, default_config, isa_state  # noqa: F401 (re-export)


class UCAVModel(om.Group):
    """
    Grupo principal de la arquitectura MDAO.
    Ensambla las disciplinas y resuelve la convergencia del MTOW.
    """
    def setup(self):
        # --- 1. Grupo Cíclico (Convergencia de Masas) ---
        cycle = self.add_subsystem('cycle', om.Group(), promotes_inputs=['*'])

        cycle.add_subsystem('geom', GeometryModule(),
                            promotes_inputs=['wing_area', 'aspect_ratio', 'taper_ratio',
                                             'sweep_angle', 'v_ht', 'v_vt', 'l_h', 'l_v',
                                             't_c_ratio', 'fuselage_length',
                                             'fuselage_diameter'])
        cycle.add_subsystem('prop', PropulsionModule(),
                            promotes_inputs=['t_sl', 'tsfc_sl', 'rho', 't_atm', 'mach',
                                             'rho_combat', 'mach_combat'])
        cycle.add_subsystem('aero', AerodynamicsModule(),
                            promotes_inputs=['mach', 'v_cruise', 'rho', 't_atm', 'wing_area',
                                             'aspect_ratio', 'taper_ratio', 'sweep_angle', 't_c_ratio',
                                             'fuselage_length', 'fuselage_diameter'])
        cycle.add_subsystem('miss', MissionModule(),
                            promotes_inputs=['v_cruise', 'range_m', 'loiter_time_s',
                                             'w_weapons',
                                             't_combat', 'thrust_combat_frac', 'tsfc_combat_factor',
                                             'f_warmup', 'f_to', 'f_climb',
                                             'f_desc', 'f_land'])
        cycle.add_subsystem('weight', SecondaryWeightsModule(),
                            promotes_inputs=['wing_area', 'fuselage_length', 'fuselage_diameter',
                                             'n_ult', 'w_avionics', 'aspect_ratio', 'taper_ratio',
                                             'sweep_angle', 't_c_ratio'])

        cycle.add_subsystem('mtow_sum', om.ExecComp(
            'mtow_calc = oew_partial + w_engine + w_fuel + w_weapons',
            mtow_calc={'units': 'kg', 'lower': 1000.0},
            oew_partial={'units': 'kg'},
            w_engine={'units': 'kg'},
            w_fuel={'units': 'kg'},
            w_weapons={'val': 600.0, 'units': 'kg'}
        ), promotes_inputs=['w_weapons'])

        # --- Conexiones internas del ciclo ---
        cycle.connect('geom.mac', 'aero.mac')
        cycle.connect('geom.s_vtail', 'aero.s_vtail')
        cycle.connect('geom.s_vtail', 'weight.s_vtail')

        cycle.connect('prop.tsfc_avail', 'miss.tsfc_avail')
        cycle.connect('prop.t_avail', 'miss.t_avail')
        cycle.connect('prop.w_engine', 'mtow_sum.w_engine')

        cycle.connect('aero.L_D', 'miss.L_D')
        cycle.connect('aero.L_D_max', 'miss.L_D_max')
        cycle.connect('miss.w_fuel', 'mtow_sum.w_fuel')
        cycle.connect('weight.oew_partial', 'mtow_sum.oew_partial')

        cycle.connect('mtow_sum.mtow_calc', 'aero.mtow_guess')
        cycle.connect('mtow_sum.mtow_calc', 'miss.mtow_guess')
        cycle.connect('mtow_sum.mtow_calc', 'weight.mtow_guess')

        cycle.nonlinear_solver = om.NonlinearBlockGS(use_aitken=True)
        cycle.nonlinear_solver.options['iprint'] = 2
        cycle.nonlinear_solver.options['maxiter'] = 50
        cycle.linear_solver = om.DirectSolver()

        # --- 2. Módulos post-ciclo ---
        self.add_subsystem('perf', PerformanceConstraintsModule(),
                           promotes_inputs=['wing_area', 't_sl', 'aspect_ratio',
                                            'sweep_angle', 'rho_sl',
                                            'taper_ratio', 'cl_max_airfoil',
                                            'rho_combat', 'v_combat',
                                            'mach_combat', 'n_combat'])
        self.add_subsystem('stab', StabilityControlModule(),
                           promotes_inputs=['fuselage_length', 'fuselage_diameter',
                                            'wing_area', 'aspect_ratio',
                                            'taper_ratio', 'sweep_angle', 'mach',
                                            'v_ht', 'v_vt',
                                            'cl_alpha_t', 'eta_tail', 'w_avionics',
                                            'x_wing_frac', 'frac_fuel_fuse',
                                            'x_payload_offset_frac',
                                            'x_fuel_fuse_frac'])
        self.add_subsystem('cost', CostEstimationModule(),
                           promotes_inputs=['v_cruise', 'q_prod', 't_sl',
                                            'k_no_cockpit', 'k_no_life_support',
                                            'k_no_civil_cert', 'k_reduced_avionics',
                                            'k_simplified_struct'])

        # --- Volumen de combustible (Torenbeek §8.2 + Roskam Part IV §6.3) ---
        self.add_subsystem('fuel_vol', om.ExecComp([
            'margin_wing_tank = vol_wing_tank - (1.0 - frac_fuel_fuse) * w_fuel / rho_fuel',
            'margin_fuse_tank = vol_fuse_tank - frac_fuel_fuse * w_fuel / rho_fuel',
        ],
            rho_fuel={'val': 800.0, 'units': 'kg/m**3'},
            w_fuel={'val': 800.0, 'units': 'kg'},
            frac_fuel_fuse={'val': 0.30},
            vol_wing_tank={'val': 0.5, 'units': 'm**3'},
            vol_fuse_tank={'val': 2.0, 'units': 'm**3'},
            margin_wing_tank={'val': 0.0, 'units': 'm**3'},
            margin_fuse_tank={'val': 1.0, 'units': 'm**3'},
        ), promotes_inputs=['frac_fuel_fuse'])

        # Performance
        self.connect('cycle.mtow_sum.mtow_calc', 'perf.mtow_guess')
        self.connect('cycle.miss.w_fuel', 'perf.w_fuel')
        self.connect('cycle.aero.cd0', 'perf.cd0')
        self.connect('cycle.aero.e_oswald', 'perf.e_oswald')
        self.connect('cycle.aero.L_D', 'perf.L_D')
        self.connect('cycle.prop.t_avail_cruise', 'perf.t_avail_cruise')

        # Estabilidad
        self.connect('cycle.weight.w_fuse', 'stab.w_fuse')
        self.connect('cycle.weight.w_wing', 'stab.w_wing')
        self.connect('cycle.weight.w_vtail', 'stab.w_vtail')
        self.connect('cycle.weight.w_lg', 'stab.w_lg')
        self.connect('cycle.prop.w_engine', 'stab.w_engine')
        self.connect('cycle.miss.w_fuel', 'stab.w_fuel')
        self.connect('cycle.geom.mac', 'stab.mac')
        self.connect('cycle.geom.wingspan', 'stab.wingspan')
        self.connect('w_weapons', 'stab.w_payload')

        # Coste
        self.connect('cycle.weight.oew_partial', 'cost.oew_partial')
        self.connect('cycle.prop.w_engine', 'cost.w_engine')

        # Volumen de combustible
        self.connect('cycle.miss.w_fuel', 'fuel_vol.w_fuel')
        self.connect('cycle.geom.vol_wing_tank', 'fuel_vol.vol_wing_tank')
        self.connect('cycle.geom.vol_fuse_tank', 'fuel_vol.vol_fuse_tank')


# FÁBRICA DE PROBLEMA
def build_problem(config: Optional[FullConfig] = None,
                  recorder_path: Optional[str] = None) -> om.Problem:
    """
    Construye un `om.Problem` listo para `run_driver()` a partir de `config`.

    Si `config is None` usa `default_config()` (corrida nominal histórica).
    Si `recorder_path` se indica, adjunta un SqliteRecorder al driver.
    """
    if config is None:
        config = default_config()

    atm = config.mission.atmosphere()

    prob = om.Problem()
    prob.model = UCAVModel()

    prob.model.set_input_defaults('w_weapons', val=config.mission.payload_kg, units='kg')
    prob.model.set_input_defaults('mach_combat', val=config.mission.m_combat)

    # --- Driver ---
    prob.driver = om.ScipyOptimizeDriver()
    prob.driver.options['optimizer'] = config.opt.optimizer
    prob.driver.options['tol'] = config.opt.tol
    prob.driver.options['disp'] = config.opt.disp

    if recorder_path is not None:
        prob.driver.add_recorder(om.SqliteRecorder(recorder_path))
        prob.driver.recording_options['record_desvars'] = True
        prob.driver.recording_options['record_objectives'] = True
        prob.driver.recording_options['record_constraints'] = True

    # --- Objetivo ---
    prob.model.add_objective(config.opt.objective, ref=config.opt.objective_ref)

    # --- Variables de diseño ---
    for dv in config.design_vars:
        if not dv.enabled:
            continue
        kwargs = dict(lower=dv.lower, upper=dv.upper, ref=dv.ref)
        if dv.units is not None:
            kwargs['units'] = dv.units
        prob.model.add_design_var(dv.name, **kwargs)

    # --- Restricciones ---
    for c in config.constraints:
        if not c.enabled:
            continue
        kwargs = dict(ref=c.ref)
        if c.lower is not None:
            kwargs['lower'] = c.lower
        if c.upper is not None:
            kwargs['upper'] = c.upper
        prob.model.add_constraint(c.name, **kwargs)

    prob.setup()

    # Inicialización de parámetros
    m = config.mission
    ac = config.aircraft
    co = config.cost
    st = config.stability

    # Atmósfera de crucero
    prob.set_val('mach', m.m_cruise)
    prob.set_val('v_cruise', atm['v_cruise'])
    prob.set_val('rho', atm['rho_cruise'])
    prob.set_val('t_atm', atm['T_cruise'])
    # Atmósfera de combate
    prob.set_val('rho_combat', atm['rho_combat'])
    prob.set_val('mach_combat', m.m_combat)
    prob.set_val('v_combat', atm['v_combat'])
    prob.set_val('n_combat', m.n_combat)
    prob.set_val('rho_sl', ac.rho_sl)

    # Requisitos de misión
    prob.set_val('range_m', m.range_km * 1.0e3)
    prob.set_val('loiter_time_s', m.loiter_min * 60.0)
    prob.set_val('w_weapons', m.payload_kg)

    # Segmento de combate y fracciones de combustible
    prob.set_val('t_combat', m.t_combat_s)
    prob.set_val('thrust_combat_frac', m.thrust_combat_frac)
    prob.set_val('tsfc_combat_factor', m.tsfc_combat_factor)
    prob.set_val('f_warmup', m.f_warmup)
    prob.set_val('f_to', m.f_to)
    prob.set_val('f_climb', m.f_climb)
    prob.set_val('f_desc', m.f_desc)
    prob.set_val('f_land', m.f_land)

    # Parámetros fijos de la aeronave
    prob.set_val('w_avionics', ac.w_avionics_kg)
    prob.set_val('fuselage_length', ac.fuselage_length_m)
    prob.set_val('fuselage_diameter', ac.fuselage_diameter_m)
    prob.set_val('n_ult', ac.n_ult)
    prob.set_val('t_c_ratio', ac.t_c_ratio)
    prob.set_val('sweep_angle', ac.sweep_angle_deg)
    prob.set_val('cl_max_airfoil', ac.cl_max_airfoil)

    # Coste
    prob.set_val('q_prod', co.q_prod)
    prob.set_val('k_no_cockpit', co.k_no_cockpit)
    prob.set_val('k_no_life_support', co.k_no_life_support)
    prob.set_val('k_no_civil_cert', co.k_no_civil_cert)
    prob.set_val('k_reduced_avionics', co.k_reduced_avionics)
    prob.set_val('k_simplified_struct', co.k_simplified_struct)

    # Estabilidad / control
    prob.set_val('stab.cm_ac_wing', st.cm_ac_wing)
    prob.set_val('stab.cl_landing', st.cl_landing)
    prob.set_val('stab.cg_fwd_loading_margin', st.cg_fwd_loading_margin)
    prob.set_val('stab.rho_sl', ac.rho_sl)
    prob.set_val('stab.cl_max_to', st.cl_max_to)
    prob.set_val('stab.cl_to', st.cl_to)
    prob.set_val('stab.mg_cg_offset_frac_mac', st.mg_cg_offset_frac_mac)
    prob.set_val('stab.mg_ac_offset_frac_mac', st.mg_ac_offset_frac_mac)

    # Valores iniciales del optimizador
    prob.set_val('t_sl', config.opt.t_sl_init)
    prob.set_val('tsfc_sl', ac.tsfc_sl)
    prob.set_val('cycle.aero.mtow_guess', config.opt.mtow_init)
    prob.set_val('cycle.miss.mtow_guess', config.opt.mtow_init)
    prob.set_val('cycle.weight.mtow_guess', config.opt.mtow_init)

    _dv_init = {dv.name: (dv.lower + dv.upper) / 2.0
                for dv in config.design_vars if dv.enabled}
    for name, val in _dv_init.items():
        try:
            prob.set_val(name, val)
        except KeyError:
            pass

    return prob
