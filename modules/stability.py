import openmdao.api as om
import numpy as np

class StabilityControlModule(om.ExplicitComponent):
    """
    Módulo de Estabilidad y Control — UCAV (Loyal Wingman).

    Referentes:
        - Raymer, "Aircraft Design: A Conceptual Approach", 6ª ed., cap. 12, 16.
        - Roskam, "Airplane Design", Parts V y VI.
        - Nelson, "Flight Stability and Automatic Control", 2ª ed., cap. 2.
        - Etkin & Reid, "Dynamics of Flight", 3ª ed., cap. 2-3.

    Ecuaciones aplicadas:
        - Cl_α_w  : Polhamus (Raymer ec. 12.6) con compresibilidad Prandtl-Glauert.
        - dε/dα   : DATCOM (Raymer ec. 16.23).
        - K_f     : Multhopp evaluado en x_c4_root/L_f (Raymer Fig. 16.14).
        - NP      : Raymer ec. 16.21 + Munk fuselaje (Raymer ec. 16.22).
        - Cn_β    : Roskam Part VI §10.3.
        - Trim    : equilibrio longitudinal en aproximación (Raymer §16.4.5).
        - Rotación: equilibrio de momentos sobre tren principal (Raymer §16.4.5).
    """

    def setup(self):
        # --- Inputs: Masas ---
        self.add_input('w_fuse', val=400.0, units='kg')
        self.add_input('w_wing', val=300.0, units='kg')
        self.add_input('w_vtail', val=50.0, units='kg')
        self.add_input('w_lg', val=100.0, units='kg')
        self.add_input('w_engine', val=280.0, units='kg')
        self.add_input('w_avionics', val=250.0, units='kg',
                       desc='Peso aviónica MUM-T (CCA tier-2)')
        self.add_input('w_fuel', val=900.0, units='kg', desc='Combustible de misión')
        self.add_input('w_payload', val=600.0, units='kg', desc='Armamento en bodega')

        # --- Inputs: Geometría plana del ala ---
        self.add_input('fuselage_length', val=9.0, units='m', desc='Longitud L_f')
        self.add_input('fuselage_diameter', val=1.4, units='m',
                       desc='Anchura efectiva del fuselaje w_f (Munk)')
        self.add_input('mac', val=1.5, units='m', desc='Cuerda Aerodinámica Media')
        self.add_input('wing_area', val=10.0, units='m**2', desc='Superficie alar S_w')
        self.add_input('wingspan', val=7.0, units='m', desc='Envergadura b')
        self.add_input('aspect_ratio', val=5.0, desc='Alargamiento AR')
        self.add_input('taper_ratio', val=0.3, desc='Estrechamiento λ')
        self.add_input('sweep_angle', val=35.0, units='deg', desc='Flecha en c/4')
        self.add_input('mach', val=0.8, desc='Mach de crucero (para Polhamus β)')
        self.add_input('v_ht', val=0.5, desc='Coef. Volumétrico Horizontal Equivalente (diseño)')
        self.add_input('v_vt', val=0.06, desc='Coef. Volumétrico Vertical Equivalente (diseño)')
        self.add_input('x_tail_frac', val=0.92,
                       desc='Posición longitudinal V-tail (fracción de L_f)')

        # --- Inputs: Parámetros aerodinámicos ---
        self.add_input('cl_alpha_t', val=4.0, desc='Pendiente sustentación cola horizontal (1/rad)')
        self.add_input('cl_alpha_v', val=3.5, desc='Pendiente sustentación cola vertical (1/rad)')
        self.add_input('eta_tail', val=0.9, desc='Eficiencia dinámica cola horizontal')
        self.add_input('eta_vtail', val=0.85, desc='Eficiencia dinámica cola vertical')
        self.add_input('dsigma_dbeta', val=0.10,
                       desc='Gradiente de sidewash dσ/dβ (Roskam Part VI ec. 10.49)')

        # --- Inputs: Autoridad de control ---
        self.add_input('cm_ac_wing', val=-0.10,
                       desc='Momento de cabeceo del ala alrededor del a.c. '
                            '(perfil supercrítico ≈ -0.10, Roskam Part VI Tabla 5.1)')
        self.add_input('cl_landing', val=1.3,
                       desc='CL de aproximación a baja velocidad (~1.2·V_stall, '
                            'CCA sin flap; Raymer §16.4.5)')
        self.add_input('cg_fwd_loading_margin', val=0.10,
                       desc='Margen forward sobre el CG estático más adelantado '
                            '(fracción MAC), Raymer Fig. 16.16.')

        # --- Inputs: Rotación en despegue (Raymer §16.4.5) ---
        self.add_input('rho_sl', val=1.225, units='kg/m**3',
                       desc='Densidad atmosférica a nivel del mar (para V_stall_TO)')
        self.add_input('cl_max_to', val=1.6,
                       desc='CL máximo en configuración despegue '
                            '(Roskam Part VI Tabla 5.1, fighter clean)')
        self.add_input('cl_to', val=0.7,
                       desc='CL ground roll a V_R durante rotación '
                            '(Roskam Part VI §10.3.3)')
        self.add_input('mg_cg_offset_frac_mac', val=0.12,
                       desc='Brazo (x_mg − x_cg_fwd)/c̄ — tip-back margin. '
                            'Fighter típico (Raymer §11.5).')
        self.add_input('mg_ac_offset_frac_mac', val=0.10,
                       desc='Brazo (x_mg − x_ac_w)/c̄ — posición geométrica del '
                            'tren principal respecto al centro aerodinámico del ala.')

        # --- Inputs: Variables de diseño y configuración ---
        self.add_input('x_wing_frac', val=0.52,
                       desc='Posición longitudinal del centroide alar (fracción L_f)')
        self.add_input('x_payload_offset_frac', val=0.10,
                       desc='Offset bodega delante del centroide alar (frac L_f)')
        self.add_input('frac_fuel_fuse', val=0.30,
                       desc='Fracción de combustible en tanque fuselaje (0-1)')
        self.add_input('x_fuel_fuse_frac', val=0.60,
                       desc='Posición longitudinal del centro de volumen del tanque '
                            'saddle de fuselaje (frac L_f).')

        # --- Outputs longitudinales ---
        self.add_output('x_cg_full', units='m')
        self.add_output('x_cg_empty', units='m')
        self.add_output('x_cg_aft', units='m',
                        desc='CG en estado aft-crítico: tanque fuselaje vacío, '
                             'tanque ala lleno, armamento soltado.')
        self.add_output('x_np', units='m', desc='NP total (ala+cola+fuselaje)')
        self.add_output('x_np_wingtail', units='m', desc='NP sin fuselaje (diagnóstico)')
        self.add_output('sm_full', desc='Margen Estático full (fracción MAC)')
        self.add_output('sm_empty', desc='Margen Estático empty (fracción MAC)')
        self.add_output('sm_aft', desc='Margen Estático en el estado aft-crítico.')
        self.add_output('cg_aft_pct_mac', desc='CG aft-crítico en %MAC')
        self.add_output('cg_full_pct_mac', desc='CG full en %MAC')
        self.add_output('cg_empty_pct_mac', desc='CG empty en %MAC')
        self.add_output('x_fuel_fuse', units='m',
                        desc='Centro de volumen del tanque de combustible del fuselaje')
        self.add_output('cg_fuel_offset', units='m',
                        desc='Offset x_fuel_fuse - x_cg_empty.')
        self.add_output('payload_cg_offset', units='m',
                        desc='Offset x_payload - x_cg_empty (Raymer §15.5.4).')
        self.add_output('cg_excursion_pct_mac',
                        desc='Excursión normalizada (x_cg_empty - x_cg_full) / MAC. '
                             'Criterio Raymer §16.3 para fighter relaxed-stability: ≤ 3% MAC.')

        # --- Outputs aerodinámicos (Polhamus, DATCOM, Multhopp) ---
        self.add_output('cl_alpha_w', desc='Cl_α_w (Polhamus + compresibilidad, 1/rad)')
        self.add_output('downwash_grad', desc='dε/dα (DATCOM)')
        self.add_output('K_f', desc='Coef. Multhopp evaluado en x_c4_root/L_f')
        self.add_output('l_h_actual', units='m',
                        desc='Brazo de cola geométrico real (no el de diseño)')
        self.add_output('v_ht_effective', desc='V_H efectivo (con l_h_actual)')

        # --- Outputs lateral-direccionales ---
        self.add_output('cn_beta', desc='Cn_β total (1/rad)')
        self.add_output('cn_beta_vtail', desc='Contribución V-tail a Cn_β')
        self.add_output('cn_beta_fus', desc='Contribución fuselaje a Cn_β')

        # --- Outputs de autoridad de control ---
        self.add_output('cl_tail_required', val=-0.3,
                        desc='CL requerida en la cola para trimar en aproximación '
                             'a baja velocidad (Raymer §16.4.5).')
        self.add_output('cl_tail_rotation_req', val=-0.5,
                        desc='CL requerida en la cola para rotación en despegue '
                             'a V_R (Raymer §16.4.5).')
        self.add_output('v_stall_to', val=50.0, units='m/s',
                        desc='Velocidad de stall en despegue (diagnóstico)')
        self.add_output('v_r', val=55.0, units='m/s',
                        desc='Velocidad de rotación V_R = 1.1·V_stall_TO')

    def setup_partials(self):
        self.declare_partials('*', '*', method='cs')

    def compute(self, inputs, outputs):
        # 0. Extracción de inputs
        L_f = inputs['fuselage_length']
        w_f = inputs['fuselage_diameter']
        mac = inputs['mac']
        S_w = inputs['wing_area']
        b   = inputs['wingspan']
        AR  = inputs['aspect_ratio']
        lam = inputs['taper_ratio']
        Lambda_c4 = inputs['sweep_angle'] * np.pi / 180.0
        M   = inputs['mach']
        v_ht_design = inputs['v_ht']
        v_vt_design = inputs['v_vt']
        cl_a_t = inputs['cl_alpha_t']
        cl_a_v = inputs['cl_alpha_v']

        # 1. Estaciones de masa — Raymer Tabla 10.1
        x_w_frac  = inputs['x_wing_frac']
        pay_off   = inputs['x_payload_offset_frac']
        f_fuse    = inputs['frac_fuel_fuse']
        x_tail_fr = inputs['x_tail_frac']

        x_avi     = 0.10 * L_f
        x_fuse    = 0.50 * L_f
        x_wing    = x_w_frac * L_f
        x_eng     = 0.70 * L_f
        x_tail    = x_tail_fr * L_f
        x_payload = (x_w_frac - pay_off) * L_f
        x_lg      = (x_w_frac + 0.05) * L_f
        x_fuel_wing = x_wing
        x_fuel_fuse = inputs['x_fuel_fuse_frac'] * L_f

        # 2. Centro de gravedad — Raymer ec. 10.1
        w_empty_state = (inputs['w_avionics'] + inputs['w_fuse'] + inputs['w_wing'] +
                         inputs['w_lg'] + inputs['w_engine'] + inputs['w_vtail'])
        w_full_state = w_empty_state + inputs['w_fuel'] + inputs['w_payload']

        moment_empty = (inputs['w_avionics']*x_avi + inputs['w_fuse']*x_fuse +
                        inputs['w_wing']*x_wing + inputs['w_lg']*x_lg +
                        inputs['w_engine']*x_eng + inputs['w_vtail']*x_tail)
        w_fuel = inputs['w_fuel']
        moment_fuel = w_fuel * ((1.0 - f_fuse) * x_fuel_wing + f_fuse * x_fuel_fuse)
        moment_full = moment_empty + moment_fuel + inputs['w_payload']*x_payload

        x_cg_empty = moment_empty / w_empty_state
        x_cg_full  = moment_full  / w_full_state
        outputs['x_cg_empty'] = x_cg_empty
        outputs['x_cg_full']  = x_cg_full

        # Estado aft-crítico (fuselaje vacío + ala llena + armamento soltado)
        w_fuel_wing   = (1.0 - f_fuse) * w_fuel
        w_aft_state   = w_empty_state + w_fuel_wing
        moment_aft    = moment_empty + w_fuel_wing * x_fuel_wing
        x_cg_aft      = moment_aft / w_aft_state
        outputs['x_cg_aft'] = x_cg_aft

        outputs['x_fuel_fuse'] = x_fuel_fuse
        outputs['cg_fuel_offset'] = x_fuel_fuse - x_cg_empty
        outputs['payload_cg_offset'] = x_payload - x_cg_empty
        outputs['cg_excursion_pct_mac'] = (x_cg_empty - x_cg_full) / mac

        # 3. Reconstrucción geométrica del ala — identidades trapezoidales (Raymer §7.4)
        #   c_root = MAC · 1.5·(1+λ)/(1+λ+λ²)
        #   y_MAC  = (b/6)·(1+2λ)/(1+λ)
        #   tan(Λ_LE) = tan(Λ_c/4) + (1−λ)/(AR·(1+λ))
        c_root = mac * 1.5 * (1.0 + lam) / (1.0 + lam + lam*lam)
        y_mac  = (b / 6.0) * (1.0 + 2.0*lam) / (1.0 + lam)
        tan_LE = np.tan(Lambda_c4) + (1.0 - lam) / (AR * (1.0 + lam))

        x_LE_MAC  = x_wing - 0.5 * mac
        x_LE_root = x_LE_MAC - y_mac * tan_LE
        x_c4_root = x_LE_root + 0.25 * c_root
        x_c4_root_frac = x_c4_root / L_f

        # 4. Cl_α_w — Polhamus con compresibilidad (Raymer ec. 12.6)
        #   Cl_α = 2π·AR / (2 + √(4 + (AR·β/η)²·(1 + tan²Λ_c/2/β²)))
        beta = np.sqrt(np.maximum(1.0 - M*M, 1.0e-6))
        tan_Lambda_c2 = np.tan(Lambda_c4) - (4.0/AR) * (0.25 * (1.0 - lam)/(1.0 + lam))
        cl_alpha_w = (2.0 * np.pi * AR) / (
            2.0 + np.sqrt(4.0 + (AR*beta)**2 * (1.0 + tan_Lambda_c2**2 / (beta*beta)))
        )
        outputs['cl_alpha_w'] = cl_alpha_w

        # 5. Downwash dε/dα — DATCOM (Raymer ec. 16.23)
        #   dε/dα = 4.44·[K_A · K_λ · K_H · √cos(Λ_c/4)]^1.19
        x_ac_wing = x_wing - 0.25 * mac
        l_h_actual = x_tail - x_ac_wing
        h_h = 0.0

        K_A = 1.0/AR - 1.0/(1.0 + AR**1.7)
        K_lam = (10.0 - 3.0*lam) / 7.0
        K_H = (1.0 - h_h/b) / (2.0 * l_h_actual / b)**(1.0/3.0)
        factor_dw = K_A * K_lam * K_H * np.sqrt(np.cos(Lambda_c4))
        deps_da = 4.44 * factor_dw**1.19
        outputs['downwash_grad'] = deps_da

        # 6. V_H efectivo con brazo geométrico real
        l_h_design = 4.5
        v_ht_eff = v_ht_design * (l_h_actual / l_h_design)
        v_vt_eff = v_vt_design * (l_h_actual / l_h_design)
        outputs['l_h_actual'] = l_h_actual
        outputs['v_ht_effective'] = v_ht_eff

        # 7. Punto Neutro — Raymer ec. 16.21 + Munk fuselaje (Raymer ec. 16.22)
        #   x_np/c̄ = x_ac_w/c̄ + η_t·(Cl_α_t/Cl_α_w)·V_H_eff·(1 − dε/dα)
        #           + Δx_np_fus/c̄   con  Δx_np_fus = −K_f·w_f²·L_f / (Cl_α_w·S_w)
        tail_contrib = mac * v_ht_eff * inputs['eta_tail'] * \
                       (cl_a_t / cl_alpha_w) * (1.0 - deps_da)
        x_np_wt = x_ac_wing + tail_contrib
        outputs['x_np_wingtail'] = x_np_wt

        # K_f de Multhopp en x_c4_root/L_f (Raymer Fig. 16.14)
        #   K_f = 1.5·exp(−6·x_c4r/L_f)
        K_f = 1.5 * np.exp(-6.0 * x_c4_root_frac)
        outputs['K_f'] = K_f

        dCm_da_fus = K_f * w_f**2 * L_f / (mac * S_w)
        delta_x_np_fus = -mac * dCm_da_fus / cl_alpha_w

        x_np = x_np_wt + delta_x_np_fus
        outputs['x_np'] = x_np

        # 8. Márgenes estáticos — Raymer ec. 16.19
        outputs['sm_full']  = (x_np - x_cg_full)  / mac
        outputs['sm_empty'] = (x_np - x_cg_empty) / mac
        outputs['sm_aft']   = (x_np - x_cg_aft)   / mac

        # 9. CG en %MAC — Raymer §16.3
        outputs['cg_full_pct_mac']  = (x_cg_full  - x_LE_MAC) / mac
        outputs['cg_empty_pct_mac'] = (x_cg_empty - x_LE_MAC) / mac
        outputs['cg_aft_pct_mac']   = (x_cg_aft   - x_LE_MAC) / mac

        # 10. Estabilidad direccional Cn_β — Roskam Part VI §10.3
        cn_b_vt = (inputs['eta_vtail'] * v_vt_eff * cl_a_v *
                   (1.0 + inputs['dsigma_dbeta']))
        outputs['cn_beta_vtail'] = cn_b_vt

        K_N = 0.5
        V_fus = (np.pi / 4.0) * w_f**2 * L_f
        cn_b_fus = -K_N * V_fus / (S_w * b)
        outputs['cn_beta_fus'] = cn_b_fus

        outputs['cn_beta'] = cn_b_vt + cn_b_fus

        # 11. Autoridad de control — Trim a baja velocidad (Raymer §16.4.5)
        #   Equilibrio longitudinal (Cm_cg = 0) en aproximación:
        #   Cm_ac_wing + CL_landing·(x_cg_fwd − x_ac_w)/c̄ − V_HT_eff·η_t·CL_tail_req = 0
        cm_ac_w = inputs['cm_ac_wing']
        cl_land = inputs['cl_landing']

        cg_margin = inputs['cg_fwd_loading_margin']
        x_cg_fwd_static = np.minimum(x_cg_full, x_cg_empty)
        x_cg_fwd_design = x_cg_fwd_static - cg_margin * mac
        dx_cg_ac = (x_cg_fwd_design - x_ac_wing) / mac

        cl_tail_req = (cm_ac_w + cl_land * dx_cg_ac) / \
                      (v_ht_eff * inputs['eta_tail'])
        outputs['cl_tail_required'] = cl_tail_req

        # 12. Autoridad de control — Rotación en despegue (Raymer §16.4.5)
        #   Equilibrio de momentos sobre el tren principal:
        #   CL_t_rot = [Cm_ac_w + CL_TO·δ_ac_mg − (W·g/(q_R·S))·δ_cg_mg_eff]
        #              / (V_HT_eff · η_t)
        rho_sl = inputs['rho_sl']
        cl_max_to = inputs['cl_max_to']
        cl_to = inputs['cl_to']
        delta_mg_cg_static = inputs['mg_cg_offset_frac_mac']
        delta_mg_ac = inputs['mg_ac_offset_frac_mac']
        g = 9.81

        delta_mg_cg = delta_mg_cg_static + cg_margin

        v_stall_to = np.sqrt(2.0 * w_full_state * g /
                             (rho_sl * S_w * cl_max_to))
        v_r = 1.1 * v_stall_to
        q_r = 0.5 * rho_sl * v_r * v_r
        outputs['v_stall_to'] = v_stall_to
        outputs['v_r'] = v_r

        weight_per_qS = (w_full_state * g) / (q_r * S_w)

        numer_rot = (cm_ac_w
                     + cl_to * delta_mg_ac
                     - weight_per_qS * delta_mg_cg)
        cl_tail_rot_req = numer_rot / (v_ht_eff * inputs['eta_tail'])
        outputs['cl_tail_rotation_req'] = cl_tail_rot_req
