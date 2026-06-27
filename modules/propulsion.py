import openmdao.api as om

class PropulsionModule(om.ExplicitComponent):
    """
    Módulo de Propulsión — UCAV Affordable Mass (Loyal Wingman).
    Modelo de lapso de empuje y consumo calibrado para turbofanes
    de la familia Williams FJ33 / FJ44-4M (XQ-58A Valkyrie, YFQ-44A Fury).

    Características de la familia:
      - BPR ≈ 3.3 – 4.1
      - T/T_SL = σ^0.7  (Mattingly §2.4)
      - TSFC ≈ 0.45 – 0.50 lb/(lbf·hr)  ≡  1.27e-5 – 1.42e-5 kg/(N·s)
    """

    def setup(self):
        # --- Inputs de Diseño del Motor ---
        self.add_input('t_sl', val=10000.0, units='N', desc='Empuje máximo a nivel del mar (T_sl)')
        self.add_input('tsfc_sl', val=1.35e-5, units='kg/(N*s)',
                       desc='Consumo específico a nivel del mar y M=0 (calibrado FJ33/FJ44-4M)')

        # --- Inputs Atmosféricos: Crucero ---
        self.add_input('rho', val=0.266, units='kg/m**3',
                       desc='Densidad del aire a altitud de CRUCERO (TSFC y Breguet)')
        self.add_input('t_atm', val=216.65, units='K',
                       desc='Temperatura ambiente a altitud de CRUCERO')
        self.add_input('mach', val=0.80, desc='Mach de CRUCERO')

        # --- Inputs Atmosféricos: Combate ---
        self.add_input('rho_combat', val=0.413, units='kg/m**3',
                       desc='Densidad del aire a altitud de COMBATE')
        self.add_input('mach_combat', val=0.85, desc='Mach de COMBATE')

        # --- Outputs ---
        self.add_output('t_avail', units='N',
                        desc='Empuje disponible a altitud de COMBATE (lapse Mattingly)')
        self.add_output('t_avail_cruise', units='N',
                        desc='Empuje disponible a altitud de CRUCERO (diagnóstico)')
        self.add_output('tsfc_avail', units='kg/(N*s)',
                        desc='Consumo específico a altitud de CRUCERO (Breguet)')
        self.add_output('w_engine', units='kg', desc='Peso del motor turbofan instalado')

    def setup_partials(self):
        self.declare_partials('*', '*', method='cs')

    def compute(self, inputs, outputs):
        t_sl = inputs['t_sl']
        tsfc_sl = inputs['tsfc_sl']
        rho = inputs['rho']
        t_atm = inputs['t_atm']
        M = inputs['mach']

        rho_co = inputs['rho_combat']
        M_co = inputs['mach_combat']

        rho_sl = 1.225
        t_sl_atm = 288.15

        # 1. Relaciones atmosféricas
        sigma_cr = rho    / rho_sl
        sigma_co = rho_co / rho_sl
        theta_cr = t_atm  / t_sl_atm

        # 2. Empuje disponible — Mattingly §2.4 (turbofan high-BPR)
        #   T(M, h) / T_SL_static = σ^0.7 · (1 − 0.49·√M)
        T_LAPSE_CO = 1.0 - 0.49 * (M_co + 1.0e-12)**0.5
        T_LAPSE_CR = 1.0 - 0.49 * (M    + 1.0e-12)**0.5
        outputs['t_avail']        = t_sl * (sigma_co ** 0.7) * T_LAPSE_CO
        outputs['t_avail_cruise'] = t_sl * (sigma_cr ** 0.7) * T_LAPSE_CR

        # 3. Variación del TSFC con temperatura — Raymer §3.3 / Mattingly §3.5
        #   TSFC ≈ TSFC_SL · √θ,   con factor de instalación S-duct (+10%)
        F_INST_TSFC = 1.10
        outputs['tsfc_avail'] = (tsfc_sl * (theta_cr ** 0.5)) * F_INST_TSFC

        # 4. Peso del motor turbofan instalado — calibrado FJ33 / FJ44-4M
        #   W_bare/T_SL ≈ 0.018 kg/N  (motor enterrado, f_inst = 1.0)
        outputs['w_engine'] = 0.018 * t_sl
