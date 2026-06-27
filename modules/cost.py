import openmdao.api as om

class CostEstimationModule(om.ExplicitComponent):
    """
    Módulo de Estimación de Costes — DAPCA IV (RAND Corp.) para UCAV.

    Referentes:
        - Hess & Romanoff, RAND R-3255-AF, 1987 (DAPCA IV original).
        - Raymer, "Aircraft Design", 6ª ed., cap. 18 (Tabla 18.1).
        - Roskam, "Airplane Design", Part VIII (cap. 4-6).

    Horas de trabajo DAPCA IV (calibradas en lb, KTAS):
        H_E  = 4.86  · W_e^0.777 · V^0.894 · Q^0.163
        H_T  = 5.99  · W_e^0.777 · V^0.696 · Q^0.263
        H_M  = 7.37  · W_e^0.820 · V^0.484 · Q^0.641
        H_Q  = 0.133 · H_M

    Costes directos (USD 2012, escalados a 2026 con infl = 1.38):
        C_D  = 91.3  · W_e^0.630 · V^1.300
        C_F  = 2498  · W_e^0.325 · V^0.822 · FTA^1.21
        C_M  = 22.1  · W_e^0.921 · V^0.621 · Q^0.799

    Factor Affordable Mass descompuesto:
        k_no_cockpit · k_no_life_support · k_no_civil_cert
        · k_reduced_avionics · k_simplified_struct
    """

    def setup(self):
        # --- Inputs ---
        self.add_input('oew_partial', val=1500.0, units='kg', desc='Peso en vacío sin motor')
        self.add_input('w_engine', val=200.0, units='kg', desc='Peso del motor')
        self.add_input('v_cruise', val=236.0, units='m/s', desc='Velocidad de diseño (≈ V_max para DAPCA IV)')
        self.add_input('t_sl', val=10000.0, units='N', desc='Empuje SL (para coste motor)')
        self.add_input('q_prod', val=100.0, desc='Cantidad de unidades a producir (Fleet size)')

        # Factor Affordable Mass descompuesto
        self.add_input('k_no_cockpit', val=0.95,
                       desc='Penalización sin cabina/asiento eyectable (-5%)')
        self.add_input('k_no_life_support', val=0.97,
                       desc='Penalización sin sistemas soporte de vida (-3%)')
        self.add_input('k_no_civil_cert', val=0.90,
                       desc='Penalización sin certificación civil tipo (-10%)')
        self.add_input('k_reduced_avionics', val=0.96,
                       desc='Penalización por aviónica MUM-T combat-grade (-4%)')
        self.add_input('k_simplified_struct', val=0.96,
                       desc='Penalización por estructura stealth combat (-4%)')

        # --- Outputs ---
        self.add_output('unit_cost_mUSD', val=0.0, desc='Coste unitario medio en M$ (2026)')
        self.add_output('rdte_mUSD', val=0.0, desc='Coste RDT&E total estimado (M$)')
        self.add_output('f_attritable_eff', val=0.0,
                        desc='Factor Affordable Mass efectivo (producto de sub-factores, diagnóstico)')

    def setup_partials(self):
        self.declare_partials('*', '*', method='cs')

    def compute(self, inputs, outputs):
        # 1. Conversión a unidades imperiales (DAPCA IV calibrado en lb, KTAS)
        w_empty_kg = inputs['oew_partial'] + inputs['w_engine']
        w_empty_lb = w_empty_kg * 2.20462
        v_kts = inputs['v_cruise'] * 1.94384
        Q = inputs['q_prod']

        FTA = 4.0
        N_eng = (Q + FTA) * 1.10

        # 2. Factor de inflación BLS CPI 2012→2026
        infl = 1.38

        # 3. Horas DAPCA IV — RAND R-3255-AF / Raymer ec. 18.4-18.6
        H_E = 4.86 * w_empty_lb**0.777 * v_kts**0.894 * Q**0.163
        H_T = 5.99 * w_empty_lb**0.777 * v_kts**0.696 * Q**0.263
        H_M = 7.37 * w_empty_lb**0.820 * v_kts**0.484 * Q**0.641
        H_Q = 0.133 * H_M

        # 4. Wrap rates (USD 2012 / Raymer Tabla 18.2) escalados a 2026
        R_E = 115.0 * infl
        R_T = 118.0 * infl
        R_M =  98.0 * infl
        R_Q = 108.0 * infl

        # 5. Costes directos DAPCA IV — Raymer Tabla 18.1
        C_D = 91.3   * w_empty_lb**0.630 * v_kts**1.300                * infl
        C_F = 2498.0 * w_empty_lb**0.325 * v_kts**0.822 * FTA**1.21    * infl
        C_M = 22.1   * w_empty_lb**0.921 * v_kts**0.621 * Q**0.799     * infl

        # 6. Coste del motor (correlación motores combat-grade pequeños)
        t_lb = inputs['t_sl'] * 0.224809
        C_engine_unit = 350.0 * t_lb * infl
        C_engine_total = C_engine_unit * N_eng

        # 7. Coste total (RDT&E + producción + motores)
        cost_total_usd = (H_E * R_E + H_T * R_T + H_M * R_M + H_Q * R_Q +
                          C_D + C_F + C_M + C_engine_total)

        # 8. Coste unitario medio (curva de aprendizaje implícita en exponentes de Q)
        avg_unit_cost_usd = cost_total_usd / Q

        # 9. Factor Affordable Mass descompuesto
        f_att = (inputs['k_no_cockpit'] *
                 inputs['k_no_life_support'] *
                 inputs['k_no_civil_cert'] *
                 inputs['k_reduced_avionics'] *
                 inputs['k_simplified_struct'])
        outputs['f_attritable_eff'] = f_att

        avg_unit_cost_usd_att = avg_unit_cost_usd * f_att
        outputs['unit_cost_mUSD'] = avg_unit_cost_usd_att / 1.0e6

        # 10. RDT&E — Raymer §18.4
        rdte_usd = H_E * R_E + H_T * R_T + C_D + C_F
        outputs['rdte_mUSD'] = rdte_usd / 1.0e6
