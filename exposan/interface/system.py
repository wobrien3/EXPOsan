# -*- coding: utf-8 -*-
'''
EXPOsan: Exposition of sanitation and resource recovery systems

This module is developed by:
    
    Yalin Li <mailto.yalin.li@gmail.com>
    
    Joy Zhang <joycheung1994@gmail.com>

This module is under the University of Illinois/NCSA Open Source License.
Please refer to https://github.com/QSD-Group/EXPOsan/blob/main/LICENSE.txt
for license details.
'''

import numpy as np, qsdsan as qs
from qsdsan import System
from exposan.bsm1 import bsm1 as bsm1_sys, A1, C1, RE as RWW, WAS
from exposan.interface._junction import ADMtoASM, ASMtoADM

thermo_asm1 = qs.get_thermo() # ASM1 components loaded by the bsm1 module

# Subsequent units should be using ADM1 components
cmps_adm1 = qs.processes.create_adm1_cmps()
thermo_adm1 = qs.get_thermo()
J1 = ASMtoADM('J1', upstream=WAS, thermo=thermo_adm1, isdynamic=True) # WAS is C1.outs[2]
AD1 = qs.sanunits.AnaerobicCSTR('AD1', ins=J1.outs[0], outs=('biogas', 'ad_eff'), isdynamic=True)
J2 = ADMtoASM('J2', upstream=AD1-1, thermo=thermo_asm1, isdynamic=True)

# Subsequent units should be using ASM1 components
qs.set_thermo(thermo_asm1)
RWW.disconnect_sink() # disconnect from A1 to avoid replacement warning
M1 = qs.sanunits.Mixer('M1', ins=[RWW, J2.outs[0]], isdynamic=True)
A1.ins[1] = M1.outs[0]

sys = System(path=(*bsm1_sys.units, J1, AD1, J2, M1))
sys.set_dynamic_tracker(A1, C1, J1, AD1, J2, M1)
sys.simulate(
    state_reset_hook='reset_cache',
    t_span=(0, 10),
    t_eval=np.arange(0, 10.5, 0.5),
    )


# p1 = Process('biomass_convert', 
#              reaction='X_BH + X_ND -> [?]X_pr + [?]X_li + [?]X_ch + [?]X_I',
#              ref_component='X_BH',
#              conserved_for=('COD', 'N', 'P', 'mass'))

# p1 = Process('biomass_convert', 
#               reaction='X_BH + [?]X_ND -> X_pr + [0.32]X_I',
#               ref_component='X_BH',
#               conserved_for=('N',))