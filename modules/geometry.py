import openmdao.api as om
import numpy as np

class GeometryModule(om.ExplicitComponent):
    """
    Módulo de Geometría — UCAV (Loyal Wingman).
    Calcula dimensiones del ala principal y del empenaje en V,
    posición espanwise y longitudinal de la MAC, y volumen de tanques.
    """

    def setup(self):
        # --- Inputs (Variables de Diseño) ---
        self.add_input('wing_area', val=10.0, units='m**2', desc='Superficie alar de referencia')
        self.add_input('aspect_ratio', val=5.0, desc='Alargamiento')
        self.add_input('taper_ratio', val=0.3, desc='Estrechamiento')
        self.add_input('sweep_angle', val=35.0, units='deg', desc='Flecha en c/4')

        # Inputs para el V-Tail
        self.add_input('v_ht', val=0.5, desc='Coeficiente volumétrico horizontal')
        self.add_input('v_vt', val=0.06, desc='Coeficiente volumétrico vertical')
        self.add_input('l_h', val=4.5, units='m', desc='Brazo de momento de la cola horizontal')
        self.add_input('l_v', val=4.5, units='m', desc='Brazo de momento de la cola vertical')

        # Inputs para volumen de tanques (Torenbeek §8.2)
        self.add_input('t_c_ratio', val=0.065, desc='Espesor relativo del ala')
        self.add_input('fuselage_length', val=9.0, units='m', desc='Longitud del fuselaje')
        self.add_input('fuselage_diameter', val=1.4, units='m', desc='Diámetro del fuselaje')

        # --- Outputs ---
        self.add_output('wingspan', units='m')
        self.add_output('root_chord', units='m')
        self.add_output('tip_chord', units='m')
        self.add_output('mac', units='m', desc='Cuerda Aerodinámica Media')
        self.add_output('y_mac', units='m', desc='Posición spanwise de la MAC')
        self.add_output('x_le_mac', units='m', desc='Posición longitudinal del LE de la MAC respecto al LE raíz')

        self.add_output('s_vtail', units='m**2', desc='Área real total del V-tail')
        self.add_output('v_angle', units='rad', desc='Ángulo diedro del V-tail')

        self.add_output('vol_wing_tank', units='m**3',
                        desc='Volumen útil del tanque alar (Torenbeek §8.2.4)')
        self.add_output('vol_fuse_tank', units='m**3',
                        desc='Volumen útil del tanque de fuselaje (cilindro·K_pack)')

    def setup_partials(self):
        self.declare_partials('*', '*', method='cs')

    def compute(self, inputs, outputs):
        # 1. Geometría del Ala (planta trapezoidal)
        S = inputs['wing_area']
        AR = inputs['aspect_ratio']
        lam = inputs['taper_ratio']
        sweep_qc = inputs['sweep_angle'] * (np.pi / 180.0)

        b = (S * AR)**0.5
        c_root = (2.0 * S) / (b * (1.0 + lam))
        c_tip = c_root * lam
        mac = (2.0 / 3.0) * c_root * ((1.0 + lam + lam**2) / (1.0 + lam))

        # Posición espanwise de la MAC — Raymer §7.2:
        #   y_MAC = (b/6) · (1 + 2λ)/(1 + λ)
        y_mac = (b / 6.0) * (1.0 + 2.0 * lam) / (1.0 + lam)

        # Flecha en LE a partir de la flecha en c/4 — Raymer ec. 7.8:
        #   tan(Λ_LE) = tan(Λ_c/4) + (1 − λ)/(AR·(1+λ))
        tan_le = np.tan(sweep_qc) + (1.0 - lam) / (AR * (1.0 + lam))
        x_le_mac = y_mac * tan_le

        outputs['wingspan'] = b
        outputs['root_chord'] = c_root
        outputs['tip_chord'] = c_tip
        outputs['mac'] = mac
        outputs['y_mac'] = y_mac
        outputs['x_le_mac'] = x_le_mac

        # 2. Geometría del Empenaje en V (Método de Cola Equivalente)
        v_ht = inputs['v_ht']
        v_vt = inputs['v_vt']
        l_h = inputs['l_h']
        l_v = inputs['l_v']

        s_h = (v_ht * S * mac) / l_h
        s_v = (v_vt * S * b) / l_v

        K_VT = 1.10
        outputs['s_vtail'] = (s_h + s_v) * K_VT
        outputs['v_angle'] = np.arctan((s_v / s_h)**0.5)

        # 3. Volumen del tanque alar — Torenbeek §8.2.4
        #   V_wing = K_combined · (b/3) · (c_r² + c_r·c_t + c_t²) · (t/c)
        t_c = inputs['t_c_ratio']
        K_TANK_WING_COMBINED = 0.65 * 0.70
        V_tank_wing = (K_TANK_WING_COMBINED *
                       (b / 3.0) *
                       (c_root**2 + c_root * c_tip + c_tip**2) *
                       t_c)
        outputs['vol_wing_tank'] = V_tank_wing

        # 4. Volumen del tanque de fuselaje (saddle tank)
        #   V_tank_fuse = K_tank · (π/4) · D_f² · (L_FRAC · L_f)
        L_f = inputs['fuselage_length']
        d_f = inputs['fuselage_diameter']
        K_TANK_FUSE = 0.50
        L_TANK_FUSE_FRAC = 0.10
        V_tank_fuse = (K_TANK_FUSE *
                       (np.pi / 4.0) * d_f**2 *
                       (L_TANK_FUSE_FRAC * L_f))
        outputs['vol_fuse_tank'] = V_tank_fuse
