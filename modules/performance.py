import openmdao.api as om
import numpy as np

class PerformanceConstraintsModule(om.ExplicitComponent):
    """
    Módulo de Actuaciones — Análisis de Restricciones (TFG).

    Referentes:
        - Raymer, "Aircraft Design: A Conceptual Approach", 6ª ed., cap. 17.
        - Roskam, "Airplane Design", Part I cap. 3 (TO/Landing) y Part VII.
        - Anderson, "Aircraft Performance and Design", McGraw-Hill 1999.
        - Boyd, "Energy-Maneuverability Theory" (USAF, 1966).

    Calcula:
        - Distancia de despegue sobre obstáculo 15.2 m (Raymer ec. 17.103).
        - Distancia de aterrizaje (Roskam): aproximación + flare + ground roll.
        - Factor de carga máximo sostenido en giro a 160 m/s @ SL.
        - Tasa de ascenso (RoC) a 130 m/s @ SL.
        - Exceso de potencia específica P_s en condiciones de combate.
    """

    def setup(self):
        # --- Inputs: Variables de Diseño y Masas ---
        self.add_input('mtow_guess', val=3000.0, units='kg', desc='MTOW iterado')
        self.add_input('w_fuel', val=800.0, units='kg', desc='Combustible consumido')
        self.add_input('wing_area', val=10.0, units='m**2', desc='Superficie alar (S)')
        self.add_input('t_sl', val=10000.0, units='N', desc='Empuje a nivel del mar (T)')
        self.add_input('aspect_ratio', val=5.0, desc='Alargamiento (AR)')

        # --- Inputs: Aerodinámica y Atmósfera ---
        self.add_input('cd0', val=0.022, desc='Resistencia parásita')
        self.add_input('e_oswald', val=0.8, desc='Eficiencia de Oswald')
        self.add_input('rho_sl', val=1.225, units='kg/m**3', desc='Densidad a nivel del mar')

        # --- Inputs: Punto táctico de Combate ---
        self.add_input('rho_combat', val=0.413, units='kg/m**3',
                       desc='Densidad atmosférica a altitud de combate (10 km)')
        self.add_input('v_combat', val=254.0, units='m/s',
                       desc='Velocidad de evaluación P_s en combate (M=0.85 @ 10km)')
        self.add_input('mach_combat', val=0.85,
                       desc='Mach de combate (para lapse de empuje)')
        self.add_input('n_combat', val=2.5,
                       desc='Factor de carga sostenido en evaluación P_s')

        # --- Inputs: CL_max con coupling sweep — Roskam Part V §5.3.3 ---
        self.add_input('sweep_angle', val=35.0, units='deg',
                       desc='Flecha c/4. Reduce CL_max wing vía cos(Λ) (Roskam §5.3.3).')
        self.add_input('taper_ratio', val=0.30,
                       desc='Estrechamiento del ala (afecta concentración de Cl en punta)')
        self.add_input('cl_max_airfoil', val=1.85,
                       desc='Cl_max bidimensional del perfil (NACA 64A series CCA: 1.75-1.95)')
        self.add_input('delta_cl_to', val=0.30,
                       desc='ΔCL takeoff (plain flap 10° + droop). Roskam Part VI Tabla 7.3.')
        self.add_input('delta_cl_l', val=0.60,
                       desc='ΔCL landing (plain flap 30° full + droop). Roskam Part VI Tabla 7.3.')
        self.add_input('delta_cl_twist', val=0.15,
                       desc='Reducción CL pico tip por washout (~-3° twist). '
                            'Anderson §5.6.4 corrección Schrenk: 0.10-0.20 típico.')

        # --- Inputs: Crucero (margen T ≥ D) ---
        self.add_input('t_avail_cruise', val=3000.0, units='N',
                       desc='Empuje disponible a altitud + Mach de crucero (PropulsionModule)')
        self.add_input('L_D', val=10.0,
                       desc='Eficiencia aerodinámica en crucero L/D (AerodynamicsModule)')

        # --- Outputs ---
        self.add_output('s_to', units='m', desc='Distancia total de despegue sobre obstáculo 15.2 m')
        self.add_output('s_land', units='m', desc='Distancia total de aterrizaje sobre obstáculo 15.2 m')
        self.add_output('n_turn', desc='Factor de carga máximo sostenido en giro (g)')
        self.add_output('roc', units='m/s', desc='Tasa de ascenso a nivel del mar (RoC) @ V=130 m/s')
        self.add_output('P_s', units='m/s',
                        desc='Exceso de potencia específica en combate '
                             '(condiciones parametrizables rho_combat/v_combat/n_combat)')
        self.add_output('stall_margin',
                        desc='Margen de stall por carga spanwise (Anderson §5.6.3): '
                             'cl_max_airfoil - CL_max_wing·γ(λ). γ(λ)=1+0.4·(1-λ).')
        self.add_output('cruise_margin',
                        desc='T_avail_cr·(L/D)/W − 1 ≥ 0: garantiza vuelo nivelado '
                             'a altitud y Mach de crucero referenciado a MTOW.')

    def setup_partials(self):
        self.declare_partials('*', '*', method='cs')

    def compute(self, inputs, outputs):
        mtow = inputs['mtow_guess']
        w_fuel = inputs['w_fuel']
        S = inputs['wing_area']
        T = inputs['t_sl']
        AR = inputs['aspect_ratio']
        cd0 = inputs['cd0']
        e = inputs['e_oswald']
        rho0 = inputs['rho_sl']

        # CL_max con coupling sweep — Roskam Part V §5.3.3
        #   CL_max_clean_wing = cl_max_airfoil · cos(Λ_c/4)
        sweep_perf_rad = inputs['sweep_angle'] * np.pi / 180.0
        cl_max_clean_wing = inputs['cl_max_airfoil'] * np.cos(sweep_perf_rad)
        cl_to = cl_max_clean_wing + inputs['delta_cl_to']
        cl_l  = cl_max_clean_wing + inputs['delta_cl_l']

        g = 9.81
        W = mtow * g
        W_S = W / S
        T_W = T / W
        K = 1.0 / (np.pi * AR * e)

        A_SL = 340.3

        # 1. Despegue — Raymer §17.8 (ground roll + rotation + climb a 15.2 m)
        v_stall_to = (2.0 * W_S / (rho0 * cl_to))**0.5
        v_lof = 1.10 * v_stall_to
        v_2   = 1.15 * v_stall_to

        mu_eff = 0.04
        v_avg = v_lof / 2.0**0.5
        q_avg = 0.5 * rho0 * v_avg**2
        cl_ground = 0.1 * cl_to
        cd_ground = cd0 + K * cl_ground**2
        D_avg = q_avg * cd_ground * S
        L_avg = q_avg * cl_ground * S
        M_avg_to = v_avg / A_SL
        T_lapse_to = 1.0 - 0.49 * (M_avg_to + 1.0e-12)**0.5
        accel_to = g * (T_W * T_lapse_to - mu_eff) - g * (D_avg - mu_eff * L_avg) / W
        s_ground = v_lof**2 / (2.0 * accel_to)

        s_rotate = 3.0 * v_lof

        cl_2 = cl_to / 1.15**2
        cd_2 = cd0 + K * cl_2**2
        LD_2 = cl_2 / cd_2
        gamma_climb = T_W - 1.0 / LD_2
        gamma_safe = 0.5 * (gamma_climb + (gamma_climb**2 + 1.0e-6)**0.5) + 1.0e-3
        s_climb_obs = 15.2 / gamma_safe
        outputs['s_to'] = s_ground + s_rotate + s_climb_obs

        # 2. Aterrizaje — Roskam Part I §3.5 (approach + flare geométrico + ground roll)
        W_land = (mtow - w_fuel) * g
        WS_land = W_land / S
        v_stall_land = (2.0 * WS_land / (rho0 * cl_l))**0.5
        v_app = 1.30 * v_stall_land
        v_td  = 1.15 * v_stall_land

        # Flare geométrico — Roskam Part I §3.5.3
        #   R_flare = V_app² / [g·(n − 1)],   s_flare = R·sin(γ_app)
        gamma_app = 3.0 * np.pi / 180.0
        n_flare = 1.2
        R_flare = v_app**2 / (g * (n_flare - 1.0))
        h_flare = R_flare * (1.0 - np.cos(gamma_app))

        s_app = (15.2 - h_flare) / np.tan(gamma_app)
        s_flare = R_flare * np.sin(gamma_app)

        decel_land = 0.30 * g
        s_ground_land = v_td**2 / (2.0 * decel_land)
        outputs['s_land'] = s_app + s_flare + s_ground_land

        # 3. Giro sostenido a 160 m/s @ SL — Anderson ec. 6.107
        #   n² = (q / (K·W/S)) · [T·lapse/W − q·CD0/(W/S)]
        v_turn = 160.0
        q_turn = 0.5 * rho0 * v_turn**2
        M_turn = v_turn / A_SL
        T_lapse_turn = 1.0 - 0.49 * (M_turn + 1.0e-12)**0.5
        thrust_margin = T_W * T_lapse_turn - (q_turn * cd0 / W_S)
        val = (thrust_margin * q_turn) / (K * W_S)

        val_pos = 0.5 * (val + (val**2 + 1.0e-12)**0.5)
        outputs['n_turn'] = (val_pos + 1.0e-12)**0.5

        # 4. Tasa de ascenso a nivel del mar — Anderson ec. 5.30
        #   RoC = V·(T·lapse − D)/W  @ V_climb = 130 m/s
        v_climb = 130.0
        q_climb = 0.5 * rho0 * v_climb**2
        M_climb = v_climb / A_SL
        T_lapse_climb = 1.0 - 0.49 * (M_climb + 1.0e-12)**0.5
        drag_climb_ratio = (q_climb * cd0 / W_S) + (K * W_S / q_climb)
        outputs['roc'] = v_climb * (T_W * T_lapse_climb - drag_climb_ratio)

        # 4b. Margen de stall por carga spanwise — Anderson §5.6.3
        #   γ(λ) = 1 + 0.4·(1 − λ)
        #   stall_margin = cl_max_airfoil + ΔCL_twist − γ(λ)·CL_max_clean_wing
        lam = inputs['taper_ratio']
        gamma_taper = 1.0 + 0.4 * (1.0 - lam)
        outputs['stall_margin'] = (inputs['cl_max_airfoil']
                                   + inputs['delta_cl_twist']
                                   - gamma_taper * cl_max_clean_wing)

        # 5. Exceso de potencia específica — Boyd EM (USAF 1966)
        #   P_s = V·(T − D)/W  en condiciones de combate
        #   Lapse: T/T_SL = σ^0.7·(1 − 0.49·√M)  (Mattingly §2.4)
        rho_combat = inputs['rho_combat']
        v_combat   = inputs['v_combat']
        n_combat   = inputs['n_combat']
        M_combat   = inputs['mach_combat']

        q_combat = 0.5 * rho_combat * v_combat**2
        T_lapse_combat = ((rho_combat / rho0)**0.7
                          * (1.0 - 0.49 * (M_combat + 1.0e-12)**0.5))
        T_W_combat = T_W * T_lapse_combat
        D_W_combat = (q_combat * cd0 / W_S) + (K * n_combat**2 * W_S / q_combat)
        outputs['P_s'] = v_combat * (T_W_combat - D_W_combat)

        # 6. Margen de empuje en crucero
        outputs['cruise_margin'] = (inputs['t_avail_cruise'] * inputs['L_D'] / W) - 1.0
