import openmdao.api as om
import numpy as np

class AerodynamicsModule(om.ExplicitComponent):
    """
    Módulo de Aerodinámica — UCAV Affordable Mass (Loyal Wingman).
    Polar de resistencia completa — Raymer (Component Buildup):
        C_D = C_{D0} + k·C_L² + C_{D,wave}
    Corrección transónica de Korn-Mason para M_dd y resistencia de onda.
    """

    def setup(self):
        # --- Inputs: Condiciones de Vuelo ---
        self.add_input('mach', val=0.80, desc='Número de Mach de crucero')
        self.add_input('v_cruise', val=236.0, units='m/s', desc='Velocidad real (TAS)')
        self.add_input('rho', val=0.266, units='kg/m**3', desc='Densidad del aire a altitud')
        self.add_input('t_atm', val=216.65, units='K', desc='Temperatura exterior a altitud')
        self.add_input('mtow_guess', val=3000.0, units='kg', desc='MTOW (para calcular C_L)')

        # --- Inputs: Parámetros Geométricos ---
        self.add_input('wing_area', val=10.0, units='m**2', desc='Superficie alar (S_ref)')
        self.add_input('mac', val=1.5, units='m', desc='Cuerda aerodinámica media')
        self.add_input('aspect_ratio', val=5.0, desc='Alargamiento (AR)')
        self.add_input('taper_ratio', val=0.30,
                       desc='Estrechamiento λ (para derivar Λ_LE en Oswald, Raymer ec. 7.8)')
        self.add_input('sweep_angle', val=35.0, units='deg', desc='Ángulo de flecha en c/4')
        self.add_input('t_c_ratio', val=0.065, desc='Espesor relativo del ala (X-47B grade)')
        self.add_input('s_vtail', val=3.5, units='m**2', desc='Área del empenaje en V')

        self.add_input('fuselage_length', val=9.0, units='m', desc='Longitud del fuselaje')
        self.add_input('fuselage_diameter', val=1.4, units='m', desc='Diámetro equivalente')

        # --- Outputs ---
        self.add_output('cd0', desc='Coeficiente de resistencia parásita total')
        self.add_output('cd_induced', desc='Coeficiente de resistencia inducida')
        self.add_output('cd_wave', desc='Coeficiente de resistencia de onda (transónico)')
        self.add_output('L_D', desc='Eficiencia aerodinámica L/D en crucero')
        self.add_output('L_D_max', desc='Eficiencia L/D máxima teórica (sin onda)')
        self.add_output('CL_cruise', desc='Coeficiente de sustentación en crucero')
        self.add_output('M_dd', desc='Mach de divergencia de resistencia (Korn-Mason)')
        self.add_output('e_oswald',
                        desc='Eficiencia Oswald computada via Raymer ec. 12.49 '
                             '(función de AR y sweep). Output, NO parámetro libre.')
        # Desglose del CD0 por componente (Component Buildup, Raymer)
        self.add_output('cd0_wing', desc='Contribución del ala al CD0')
        self.add_output('cd0_fuse', desc='Contribución del fuselaje al CD0')
        self.add_output('cd0_vtail', desc='Contribución del empenaje en V al CD0')
        self.add_output('cd0_misc', desc='Misceláneos (tomas, antenas, fugas) al CD0')
        self.add_output('cd0_other',
                        desc='Excrescencias + rugosidad + S-duct stealth al CD0')

    def setup_partials(self):
        self.declare_partials('*', '*', method='cs')

    def compute(self, inputs, outputs):
        M = inputs['mach']
        V = inputs['v_cruise']
        rho = inputs['rho']
        T_atm = inputs['t_atm']
        W = inputs['mtow_guess'] * 9.81

        S_ref = inputs['wing_area']
        mac = inputs['mac']
        AR = inputs['aspect_ratio']
        lam = inputs['taper_ratio']
        sweep_rad = inputs['sweep_angle'] * (np.pi / 180.0)
        t_c = inputs['t_c_ratio']
        s_vt = inputs['s_vtail']

        l_f = inputs['fuselage_length']
        d_f = inputs['fuselage_diameter']

        # Eficiencia de Oswald — Raymer ec. 12.49 (Λ_LE)
        #   e = 4.61·(1 − 0.045·AR^0.68)·cos(Λ_LE)^0.15 − 3.1
        #   tan(Λ_LE) = tan(Λ_c/4) + (1 − λ)/(AR·(1 + λ))   [Raymer ec. 7.8]
        tan_le = np.tan(sweep_rad) + (1.0 - lam) / (AR * (1.0 + lam))
        sweep_le = np.arctan(tan_le)
        e = 4.61 * (1.0 - 0.045 * AR**0.68) * np.cos(sweep_le)**0.15 - 3.1
        outputs['e_oswald'] = e

        # 1. Viscosidad dinámica del aire — Ley de Sutherland
        mu_0 = 1.716e-5
        T_0 = 273.15
        S_mu = 111.0
        mu = mu_0 * ((T_atm / T_0)**1.5) * ((T_0 + S_mu) / (T_atm + S_mu))

        # 2. Número de Reynolds y Fricción turbulenta — Prandtl-Schlichting
        Re_wing = (rho * V * mac) / mu
        cf_wing = 0.455 / ((np.log10(Re_wing)**2.58) * (1.0 + 0.144 * M**2)**0.65)

        Re_fuse = (rho * V * l_f) / mu
        cf_fuse = 0.455 / ((np.log10(Re_fuse)**2.58) * (1.0 + 0.144 * M**2)**0.65)

        mac_vt = (s_vt / 1.5)**0.5
        Re_vt = (rho * V * mac_vt) / mu
        cf_vt = 0.455 / ((np.log10(Re_vt)**2.58) * (1.0 + 0.144 * M**2)**0.65)

        # 3. Factores de Forma (FF)
        ff_wing = (1.0 + (0.6 / 0.3) * t_c + 100.0 * (t_c**4)) * \
                  (1.34 * M**0.18 * (np.cos(sweep_rad)**0.28))

        f_ratio = l_f / d_f
        ff_fuse = 1.0 + 60.0 / (f_ratio**3) + f_ratio / 400.0

        t_c_vt = 0.09
        ff_vt = (1.0 + (0.6 / 0.3) * t_c_vt + 100.0 * (t_c_vt**4)) * (1.34 * M**0.18)

        # 4. Áreas Mojadas (S_wet)
        s_wet_wing = 2.0 * S_ref * (1.0 + 0.2 * t_c)
        s_wet_fuse = np.pi * d_f * l_f * 0.75
        s_wet_vt = 2.0 * s_vt * (1.0 + 0.2 * t_c_vt)

        # 5. CD0 por componente (Component Buildup, Raymer)
        cd0_wing = cf_wing * ff_wing * 1.00 * (s_wet_wing / S_ref)
        cd0_fuse = cf_fuse * ff_fuse * 1.00 * (s_wet_fuse / S_ref)
        cd0_vt = cf_vt * ff_vt * 1.04 * (s_wet_vt / S_ref)

        cd0_clean = cd0_wing + cd0_fuse + cd0_vt
        cd0_misc = 0.05 * cd0_clean
        cd0_excrescence = (cd0_clean + cd0_misc) * 1.03
        F_SDUCT_CD0 = 1.02
        cd0_total = cd0_excrescence * F_SDUCT_CD0
        outputs['cd0'] = cd0_total

        outputs['cd0_wing'] = cd0_wing
        outputs['cd0_fuse'] = cd0_fuse
        outputs['cd0_vtail'] = cd0_vt
        outputs['cd0_misc'] = cd0_misc
        outputs['cd0_other'] = cd0_total - cd0_clean - cd0_misc

        # 6. Sustentación en crucero
        q_dyn = 0.5 * rho * V**2
        CL = W / (q_dyn * S_ref)
        outputs['CL_cruise'] = CL

        # 7. Resistencia Inducida — C_Di = k · C_L²
        k_ind = 1.0 / (np.pi * AR * e)
        cd_i = k_ind * CL**2
        outputs['cd_induced'] = cd_i

        # 8. Resistencia de onda — Modelo de Korn-Mason
        # M_dd = κ_A/cos(Λ) − (t/c)/cos²(Λ) − C_L/(10·cos³(Λ))
        kappa_A = 0.95
        cos_s = np.cos(sweep_rad)
        M_dd_korn = (kappa_A / cos_s) - (t_c / cos_s**2) - (CL / (10.0 * cos_s**3))

        M_DD_PHYS_MAX = 0.95
        diff = M_dd_korn - M_DD_PHYS_MAX
        M_dd = 0.5 * (M_dd_korn + M_DD_PHYS_MAX - (diff**2 + 1.0e-10)**0.5)
        outputs['M_dd'] = M_dd

        # Mach crítico: M_cr = M_dd − (0.1/80)^(1/3)
        M_cr = M_dd - (0.1 / 80.0)**(1.0 / 3.0)

        # CD_wave = 20 · (M − M_cr)^4  (Lock)
        dM = M - M_cr
        dM_pos = 0.5 * (dM + (dM**2 + 1.0e-10)**0.5)
        cd_wave = 20.0 * dM_pos**4
        outputs['cd_wave'] = cd_wave

        # 9. Polar total y eficiencia aerodinámica
        cd_total = cd0_total + cd_i + cd_wave
        outputs['L_D'] = CL / cd_total

        # L/D máximo teórico (sin onda): 1 / (2·√(k·CD0))
        outputs['L_D_max'] = 1.0 / (2.0 * (k_ind * cd0_total)**0.5)
