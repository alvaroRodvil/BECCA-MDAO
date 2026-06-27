import openmdao.api as om
import numpy as np

class MissionModule(om.ExplicitComponent):
    """
    Módulo de Misión Táctica — UCAV Affordable Mass (Loyal Wingman).

    Referentes:
        - Raymer, "Aircraft Design", 6ª ed., cap. 6 (mission sizing).
        - Roskam, "Airplane Design", Part I, cap. 2 (mission fuel fractions).
        - Anderson, "Aircraft Performance and Design", cap. 7 (Breguet).
        - Mattingly, "Aircraft Engine Design", AIAA 2002 (TSFC en combate).

    Perfil de misión:
        warm-up/taxi → despegue → ascenso → crucero ida →
        loiter ISR → combate (cálculo explícito) → soltado de armas →
        crucero regreso → descenso → aterrizaje.
    """

    def setup(self):
        # --- Inputs: Aerodinámica y Propulsión ---
        self.add_input('mtow_guess', val=3000.0, units='kg', desc='MTOW iterado')
        self.add_input('v_cruise', val=236.0, units='m/s', desc='Velocidad de crucero (M=0.80 @ 13km)')
        self.add_input('tsfc_avail', val=2.2e-5, units='kg/(N*s)', desc='Consumo específico (crucero/loiter)')
        self.add_input('L_D', val=12.0, desc='Eficiencia aerodinámica en crucero (real)')
        self.add_input('L_D_max', val=14.0, desc='Eficiencia aerodinámica máxima (loiter)')
        self.add_input('t_avail', val=4000.0, units='N',
                       desc='Empuje disponible a altitud+Mach de COMBATE (lapse Mattingly σ^0.7·(1−0.49√M))')

        # --- Inputs: Perfil de Misión ---
        self.add_input('range_m', val=4300e3, units='m', desc='Alcance total (ida y vuelta)')
        self.add_input('loiter_time_s', val=3600.0, units='s', desc='Tiempo de reconocimiento (Ej: 1 hora)')
        self.add_input('w_weapons', val=600.0, units='kg', desc='Masa de armamento a liberar (Payload Drop)')

        # --- Inputs: Segmento de Combate ---
        self.add_input('t_combat', val=300.0, units='s',
                       desc='Duración del segmento de combate (5 min típico)')
        self.add_input('thrust_combat_frac', val=0.90,
                       desc='Fracción de T_SL usada en combate (~0.9 régimen MIL sin AB)')
        self.add_input('tsfc_combat_factor', val=2.5,
                       desc='Ratio TSFC_combat / TSFC_cruise (Mattingly: 2-3 sin AB, 4-5 con AB)')

        # --- Inputs: Fracciones Fijas — Raymer Tabla 6.2 ---
        self.add_input('f_warmup', val=0.985, desc='Warm-up / taxi (Raymer Tabla 6.2, jet militar)')
        self.add_input('f_to', val=0.97, desc='Despegue (Raymer Tabla 6.2)')
        self.add_input('f_climb', val=0.985, desc='Ascenso a altitud de crucero (Raymer Tabla 6.2)')
        self.add_input('f_desc', val=0.99, desc='Descenso (Raymer Tabla 6.2)')
        self.add_input('f_land', val=0.995, desc='Aterrizaje (Raymer Tabla 6.2)')

        # --- Outputs ---
        self.add_output('w_fuel', units='kg', desc='Combustible total requerido (con reserva)')

    def setup_partials(self):
        self.declare_partials('*', '*', method='cs')

    def compute(self, inputs, outputs):
        mtow = inputs['mtow_guess']
        R = inputs['range_m']
        V = inputs['v_cruise']
        LD_cruise = inputs['L_D']
        LD_loiter = inputs['L_D_max']
        tsfc = inputs['tsfc_avail']
        E = inputs['loiter_time_s']
        w_weap = inputs['w_weapons']
        g = 9.81

        # 1. Breguet para Crucero — Raymer ec. 6.13, Anderson ec. 7.21
        #   f_cruise = exp(−(R/2)·c·g / (V·L/D))
        exp_cruise = ((R / 2.0) * tsfc * g) / (V * LD_cruise)
        f_cruise = np.exp(-exp_cruise)

        # 2. Breguet de Autonomía para Loiter a (L/D)_max — Anderson ec. 7.30
        #   f_loiter = exp(−(E·c·g) / (L/D)_max)
        exp_loiter = (E * tsfc * g) / LD_loiter
        f_loiter = np.exp(-exp_loiter)

        # 3. Combate — cálculo explícito con lapse altitud+Mach (Mattingly §2.4)
        #   Δw_combat [kg] = T_combat [N] · TSFC_combat [kg/(N·s)] · t_combat [s]
        T_combat = inputs['thrust_combat_frac'] * inputs['t_avail']
        tsfc_combat = inputs['tsfc_combat_factor'] * tsfc
        w_fuel_combat = T_combat * tsfc_combat * inputs['t_combat']

        # --- Cálculo secuencial de masas ---
        w1 = mtow * inputs['f_warmup'] * inputs['f_to'] * inputs['f_climb']
        w2 = w1 * f_cruise
        w3 = w2 * f_loiter
        w4 = w3 - w_fuel_combat
        w5 = w4 - w_weap
        w6 = w5 * f_cruise
        w7 = w6 * inputs['f_desc'] * inputs['f_land']

        w_fuel_burned = (mtow - w7) - w_weap

        # Reserva táctica del 15% — MIL-STD-3013 / Roskam Part I §2.3
        outputs['w_fuel'] = w_fuel_burned * 1.15
