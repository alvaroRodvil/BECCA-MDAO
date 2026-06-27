import openmdao.api as om
import numpy as np


class SecondaryWeightsModule(om.ExplicitComponent):
    """
    Módulo de Estimación de Pesos — UCAV tipo CCA (~3200 kg).
    Ecuaciones empíricas CER de Raymer, "Aircraft Design", Cap. 15
    (Statistical Group Weights Method), categorías Fighter/Attack.

    Subsistemas: desglose explícito por fracción de MTOW calibrado sobre
    referentes F-16 / F-35 / X-47B / MQ-28A. Total ≈ 9.6 % MTOW.
    """

    def setup(self):
        # --- Inputs ---
        self.add_input('mtow_guess', val=3200.0, units='kg',
                       desc='MTOW iterado por el solver')
        self.add_input('s_vtail', val=3.5, units='m**2',
                       desc='Área real del V-Tail (viene de Geometry)')
        self.add_input('wing_area', val=10.0, units='m**2',
                       desc='Superficie alar (viene de Geometry)')
        self.add_input('fuselage_length', val=9.0, units='m',
                       desc='Longitud del fuselaje')
        self.add_input('fuselage_diameter', val=1.4, units='m',
                       desc='Diámetro equivalente del fuselaje')
        self.add_input('n_ult', val=10.0,
                       desc='Factor de carga último (n_limit=8g × SF=1.25, '
                            'MIL-STD-1530D para aeronaves no tripuladas)')
        self.add_input('w_avionics', val=250.0, units='kg',
                       desc='Peso de aviónica MUM-T (CCA tier-2 calibrado YFQ-44A)')

        # --- Inputs de geometría alar ---
        self.add_input('aspect_ratio', val=5.0, desc='Alargamiento')
        self.add_input('taper_ratio', val=0.3, desc='Estrechamiento')
        self.add_input('sweep_angle', val=35.0, units='deg',
                       desc='Ángulo de flecha en c/4')
        self.add_input('t_c_ratio', val=0.065, desc='Espesor relativo (X-47B grade)')

        # --- Outputs ---
        self.add_output('w_wing', units='kg', desc='Peso del ala principal')
        self.add_output('w_fuse', units='kg', desc='Peso del fuselaje (estructura primaria)')
        self.add_output('w_vtail', units='kg', desc='Peso del empenaje en V')
        self.add_output('w_lg', units='kg', desc='Peso del tren de aterrizaje')

        # Subsistemas auxiliares
        self.add_output('w_fuel_sys', units='kg', desc='Sistema de combustible')
        self.add_output('w_flight_ctrl', units='kg', desc='Flight controls (FBW)')
        self.add_output('w_hydraulics', units='kg', desc='Sistema hidráulico')
        self.add_output('w_electrical', units='kg', desc='Sistema eléctrico')
        self.add_output('w_ecs', units='kg', desc='Environmental Control System')
        self.add_output('w_apu', units='kg', desc='APU auxiliar')
        self.add_output('w_systems', units='kg', desc='Suma de subsistemas auxiliares')

        self.add_output('oew_partial', units='kg',
                        desc='Peso Operativo en Vacío (sin motor)')

    def setup_partials(self):
        self.declare_partials('*', '*', method='cs')

    def compute(self, inputs, outputs):
        mtow      = inputs['mtow_guess']
        s_vtail   = inputs['s_vtail']
        s_wing    = inputs['wing_area']
        l_fuse    = inputs['fuselage_length']
        d_fuse    = inputs['fuselage_diameter']
        n_ult     = inputs['n_ult']
        ar        = inputs['aspect_ratio']
        lam       = inputs['taper_ratio']
        t_c       = inputs['t_c_ratio']
        sweep_rad = inputs['sweep_angle'] * np.pi / 180.0

        # Constantes de conversión SI ↔ Imperial
        LB_PER_KG  = 2.20462
        FT_PER_M   = 3.28084
        FT2_PER_M2 = 10.7639
        KG_PER_LB  = 1.0 / LB_PER_KG

        mtow_lb    = mtow * LB_PER_KG
        l_fuse_ft  = l_fuse * FT_PER_M
        d_fuse_ft  = d_fuse * FT_PER_M
        s_wing_ft2 = s_wing * FT2_PER_M2

        # 1. Tren de aterrizaje — fracción empírica MTOW (Raymer Tabla 6.2 / Gundlach)
        outputs['w_lg'] = 0.040 * mtow

        # 2. Fuselaje — CER Fighter/Attack (Raymer cap. 15)
        #   W_F [lb] = 0.499 · K_dwf · W_dg^0.35 · N_z^0.25 · L^0.5 · D^0.849 · W^0.685
        K_DWF = 0.774
        F_COMP_FUSE = 0.85

        w_fuse_lb = (0.499 * K_DWF
                     * mtow_lb**0.35
                     * n_ult**0.25
                     * l_fuse_ft**0.5
                     * d_fuse_ft**0.849
                     * d_fuse_ft**0.685)

        outputs['w_fuse'] = w_fuse_lb * F_COMP_FUSE * KG_PER_LB

        # 3. Ala — CER Fighter/Attack wing weight (Raymer cap. 15)
        #   W_w [lb] = 0.0103 · K_dw · K_vs · (W_dg·N_z)^0.5 · S_w^0.622
        #              · AR^0.785 · (t/c)^-0.4 · (1+λ)^0.05 · cos(Λ)^-1 · S_csw^0.04
        K_DW = 0.768
        K_VS = 1.0
        F_COMP_WING = 0.85
        s_csw_ft2 = 0.10 * s_wing_ft2

        w_wing_lb = (0.0103 * K_DW * K_VS
                     * (mtow_lb * n_ult)**0.5
                     * s_wing_ft2**0.622
                     * ar**0.785
                     * t_c**(-0.4)
                     * (1.0 + lam)**0.05
                     * np.cos(sweep_rad)**(-1.0)
                     * s_csw_ft2**0.04)

        outputs['w_wing'] = w_wing_lb * F_COMP_WING * KG_PER_LB

        # 4. Empenaje en V — CER GA horizontal-tail (Raymer cap. 15), constante SI
        #   C_VT = 0.04417 · q^0.168 · (100·t/c)^-0.12 · (AR/cos²Λ)^0.043 · λ^-0.02 · f_comp
        C_VT = 0.192
        outputs['w_vtail'] = C_VT * (n_ult * mtow)**0.414 * s_vtail**0.896

        # 5. Subsistemas auxiliares — fracciones de MTOW (Raymer Tabla 15.2 / Gundlach cap. 6)
        K_FUEL_SYS    = 0.012
        K_FLIGHT_CTRL = 0.025
        K_HYDRAULICS  = 0.013
        K_ELECTRICAL  = 0.028
        K_ECS         = 0.012
        K_APU         = 0.006

        outputs['w_fuel_sys']    = K_FUEL_SYS    * mtow
        outputs['w_flight_ctrl'] = K_FLIGHT_CTRL * mtow
        outputs['w_hydraulics']  = K_HYDRAULICS  * mtow
        outputs['w_electrical']  = K_ELECTRICAL  * mtow
        outputs['w_ecs']         = K_ECS         * mtow
        outputs['w_apu']         = K_APU         * mtow

        outputs['w_systems'] = (outputs['w_fuel_sys']
                                + outputs['w_flight_ctrl']
                                + outputs['w_hydraulics']
                                + outputs['w_electrical']
                                + outputs['w_ecs']
                                + outputs['w_apu'])

        # 6. OEW parcial (sin motor)
        w_structural = outputs['w_wing'] + outputs['w_fuse'] + outputs['w_vtail']
        outputs['oew_partial'] = (w_structural
                                  + outputs['w_lg']
                                  + outputs['w_systems']
                                  + inputs['w_avionics'])
