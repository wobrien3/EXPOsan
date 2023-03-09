# -*- coding: utf-8 -*-
'''
EXPOsan: Exposition of sanitation and resource recovery systems

This module is developed by:
    
    Joy Zhang <joycheung1994@gmail.com>

This module is under the University of Illinois/NCSA Open Source License.
Please refer to https://github.com/QSD-Group/EXPOsan/blob/main/LICENSE.txt
for license details.
'''

import numpy as np, qsdsan as qs
from qsdsan import (
    processes as pc, 
    WasteStream, System, TEA, LCA, PowerUtility,
    ImpactItem as IItm, 
    StreamImpactItem as SIItm,
    )
from exposan.metab import (
    _impact_item_loaded,
    load_lca_data,
    flex_rhos_adm1
    )
from exposan.metab.units import *
from exposan.metab.equipment import *

__all__ = ('get_fug_ch4', 'get_NG_eq', 'add_strm_iitm',
           'kWh', 'MJ', 'add_TEA_LCA',
           )

#%%
C_mw = 12.0107
N_mw = 14.0067

default_inf_concs = {
    'S_su':3.0,
    'S_aa':0.6,
    'S_fa':0.4,
    'S_va':0.4,
    'S_bu':0.4,
    'S_pro':0.4,
    'S_ac':0.4,
    'S_h2':5e-9,
    'S_ch4':5e-6,
    'S_IC':0.04*C_mw,
    'S_IN':0.01*N_mw,
    'S_I':0.02,
    'X_c':0.1,
    'X_ch':0.3,
    'X_pr':0.5,
    'X_li':0.25,
    'X_aa':1e-3,
    'X_fa':1e-3,
    'X_c4':1e-3,
    'X_pro':1e-3, 
    'X_ac':1e-3, 
    'X_h2':1e-3, 
    'X_I':0.025, 
    'S_cat':0.04, 
    'S_an':0.02
    }

C0_bulk = np.array([
    1.204e-02, 5.323e-03, 9.959e-02, 1.084e-02, 1.411e-02, 1.664e-02,
    4.592e-02, 2.409e-07, 7.665e-02, 5.693e-01, 1.830e-01, 3.212e-02,
    2.424e-01, 2.948e-02, 4.766e-02, 2.603e-02, 4.708e+00, 1.239e+00,
    4.838e-01, 1.423e+00, 8.978e-01, 2.959e+00, 1.467e+00, 4.924e-02,
    4.000e-02, 2.000e-02, 9.900e+02
    ])

if not _impact_item_loaded: load_lca_data()
bg_offset_CFs = IItm.get_item('biogas_offset').CFs
NaOCl_item = IItm.get_item('NaOCl')
citric_acid_item = IItm.get_item('citric_acid')

def get_fug_ch4(ws):
    '''Returns kg/hr fugitive CH4.'''
    cmps = ws.components
    return ws.imass['S_ch4']*cmps.S_ch4.i_mass

def get_NG_eq(bg):
    '''Returns m3/hr natural gas equivalent.'''
    cmps = bg.components
    KJ_per_kg = cmps.i_mass/cmps.chem_MW*cmps.LHV
    return -sum(bg.mass*KJ_per_kg)*1e-3/39

def add_fugch4_iitm(ws):
    SIItm(ID=f'{ws.ID}_fugitive_ch4', linked_stream=ws, 
          flow_getter=get_fug_ch4,
          GWP100=28, MIR=0.0143794871794872)

def add_ngoffset_iitm(ws):
    SIItm(ID=f'{ws.ID}_NG_offset', linked_stream=ws, functional_unit='m3',
          flow_getter=get_NG_eq, # m3/hr natural-gas-equivalent
          **bg_offset_CFs)
    
def add_chemicals_iitm(u):
    SIItm(linked_stream=u.NaOCl, **NaOCl_item.CFs)
    SIItm(linked_stream=u.citric_acid, **citric_acid_item.CFs)

def add_strm_iitm(sys):
    for ws in sys.products:
        if ws.phase == 'l': add_fugch4_iitm(ws)
        elif ws.phase == 'g': add_ngoffset_iitm(ws)
    for u in sys.units:
        if isinstance(u, DegassingMembrane): add_chemicals_iitm(u)

# Operation items
kWh = lambda lca: lca.system.power_utility.rate*lca.lifetime_hr
def MJ(lca):
    sys = lca.system
    duties = [hu.duty for hu in sys.heat_utilities]
    MJ_per_hr = sum(d for d in duties if d > 0)*1e-3
    return MJ_per_hr*lca.lifetime_hr
    
def add_TEA_LCA(sys, irr, lt):
    TEA(sys, discount_rate=irr, lifetime=lt, simulate_system=False, CEPCI=708)   
    LCA(
        sys, lifetime=lt, simulate_system=False,
        electricity = kWh,
        heat_onsite = MJ
        )

#%% Systems
# electricity_price = 0.0913
reactor_classes = {
    'UASB': UASB,
    'FB': METAB_FluidizedBed,
    'PB': METAB_PackedBed
    }

def set_init_concs(unit):
    isa = isinstance
    if isa(unit, UASB):
        C0 = C0_bulk.copy()
    elif isa(unit, METAB_FluidizedBed):
        C0 = np.tile(C0_bulk, unit.n_layer+1)
    else:
        C0 = np.tile(C0_bulk, (unit.n_layer+1)*unit.n_cstr)
    unit._concs = C0

def create_system(n_stages=1, reactor_type='UASB', gas_extraction='P', 
                  lifetime=30, discount_rate=0.1, 
                  Q=5, inf_concs={}, tot_HRT=12,
                  flowsheet=None):
    
    Reactor = reactor_classes[reactor_type]
    sys_ID = f'{reactor_type}{n_stages}{gas_extraction}'
    
    flowsheet = flowsheet or qs.Flowsheet(sys_ID)
    qs.main_flowsheet.set_flowsheet(flowsheet)
    
    pc.create_adm1_cmps()
    adm1 = pc.ADM1(flex_rate_function=flex_rhos_adm1)
    inf_concs = inf_concs or default_inf_concs.copy()
    inf = WasteStream('inf')
    inf.set_flow_by_concentration(Q, concentrations=inf_concs, 
                                  units=('m3/d', 'kg/m3'))   
    eff = WasteStream('eff')
    eff_dg = WasteStream('eff_dg')
    bge = WasteStream('bge', phase='g')
    add_fugch4_iitm(eff)
    
    IST = IronSpongeTreatment(ID='IST')
    GH = DoubleMembraneGasHolder(ID='GH')
    
    if n_stages == 1:
        bg = WasteStream('bg', phase='g')
        add_ngoffset_iitm(bg)
        R1 = Reactor('R1', ins=inf, outs=(bg, eff), V_liq=Q*tot_HRT, 
                     V_gas=Q*tot_HRT*0.1, T=273.15+35, model=adm1, 
                     equipment=[IST, GH],
                     F_BM_default=1, lifetime=lifetime)
        set_init_concs(R1)
        sys = System(sys_ID, path=(R1,), )
        sys.set_dynamic_tracker(R1, eff, bg)
    else:
        bg1 = WasteStream('bg1', phase='g')
        bg2 = WasteStream('bg2', phase='g')
        add_ngoffset_iitm(bg1)
        add_ngoffset_iitm(bg2)
        if gas_extraction == 'M':
            bgs = WasteStream('bgs', phase='g')
            add_ngoffset_iitm(bgs)
            R1 = Reactor('R1', ins=[inf, ''], outs=(bg1, '', ''), split=[400, 1],
                         V_liq=Q*tot_HRT/12, V_gas=Q*tot_HRT/12*0.1, 
                         T=273.15+35, pH_ctrl=5.8, model=adm1, 
                         F_BM_default=1, lifetime=lifetime)
            DMs = DegassingMembrane('DMs', ins=R1-1, outs=(bgs, 1-R1), F_BM_default=1)
            add_chemicals_iitm(DMs)
            R2 = Reactor('R2', ins=R1-2, outs=(bg2, eff), V_liq=Q*tot_HRT*11/12, 
                         V_gas=Q*tot_HRT*11/12*0.1, T=273.15+22, pH_ctrl=7.2, 
                         model=adm1, equipment=[IST, GH],
                         F_BM_default=1, lifetime=lifetime)
            sys = System(sys_ID, path=(R1, DMs, R2))
            sys.set_dynamic_tracker(R1, R2, eff, bg1, bgs, bg2)
        else:
            if gas_extraction == 'P': fixed_headspace_P = False
            else: fixed_headspace_P = True
            R1 = Reactor('R1', ins=inf, outs=(bg1, ''), V_liq=Q*tot_HRT/12, 
                         V_gas=Q*tot_HRT/12*0.1, T=273.15+35, pH_ctrl=5.8, 
                         model=adm1, fixed_headspace_P=fixed_headspace_P, headspace_P=0.1,
                         F_BM_default=1, lifetime=lifetime)
            R2 = Reactor('R2', ins=R1-1, outs=(bg2, eff), V_liq=Q*tot_HRT*11/12, 
                         V_gas=Q*tot_HRT*11/12*0.1, T=273.15+22, pH_ctrl=7.2, 
                         model=adm1, equipment=[IST, GH],
                         F_BM_default=1, lifetime=lifetime)
            sys = System(sys_ID, path=(R1, R2))
            sys.set_dynamic_tracker(R1, R2, eff, bg1, bg2)
        
        set_init_concs(R1)
        set_init_concs(R2)
    
    add_TEA_LCA(sys, discount_rate, lifetime)
    
    DMe = DegassingMembrane('DMe', ins=eff, outs=(bge, eff_dg), F_BM_default=1)
    add_chemicals_iitm(DMe)
    add_fugch4_iitm(eff_dg)
    add_ngoffset_iitm(bge)
    
    sys_dg = System(f'{sys_ID}_edg', path=(sys, DMe))
    add_TEA_LCA(sys_dg, discount_rate, lifetime)
    return sys, sys_dg
    