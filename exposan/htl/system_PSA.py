#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
EXPOsan: Exposition of sanitation and resource recovery systems

This module is developed by:
    Jianan Feng <jiananf2@illinois.edu>
    Yalin Li <mailto.yalin.li@gmail.com>
    
This module is under the University of Illinois/NCSA Open Source License.
Please refer to https://github.com/QSD-Group/EXPOsan/blob/main/LICENSE.txt
for license details.

References:

(1) Jones, S. B.; Zhu, Y.; Anderson, D. B.; Hallen, R. T.; Elliott, D. C.; 
    Schmidt, A. J.; Albrecht, K. O.; Hart, T. R.; Butcher, M. G.; Drennan, C.; 
    Snowden-Swan, L. J.; Davis, R.; Kinchin, C. 
    Process Design and Economics for the Conversion of Algal Biomass to
    Hydrocarbons: Whole Algae Hydrothermal Liquefaction and Upgrading;
    PNNL--23227, 1126336; 2014; https://doi.org/10.2172/1126336.
    
(2) Knorr, D.; Lukas, J.; Schoen, P. Production of Advanced Biofuels via
    Liquefaction - Hydrothermal Liquefaction Reactor Design: April 5, 2013;
    NREL/SR-5100-60462, 1111191; 2013; p NREL/SR-5100-60462, 1111191.
    https://doi.org/10.2172/1111191.
'''

import os, qsdsan as qs
import exposan.htl._sanunits as su
from qsdsan import sanunits as qsu
from biosteam.units import IsenthalpicValve
from exposan.htl._process_settings import load_process_settings
from exposan.htl._components import create_components
from exposan.htl._TEA import *
from qsdsan import PowerUtility
from biosteam import HeatUtility
from qsdsan.utils import auom, DictAttrSetter
import numpy as np
import pandas as pd

_m3perh_to_MGD = auom('m3/h').conversion_factor('MGD')

_kg_to_g = auom('kg').conversion_factor('g')

_MJ_to_MMBTU = auom('MJ').conversion_factor('MMBTU')

# __all__ = ('create_system',)

# def create_system():

load_process_settings()
cmps = create_components()

# Construction here, StreamImpactItem after TEA
folder = os.path.dirname(__file__)
qs.ImpactIndicator.load_from_file(os.path.join(folder, 'data/impact_indicators.csv'))
qs.ImpactItem.load_from_file(os.path.join(folder, 'data/impact_items.xlsx'))

# results_diesel = []
# results_sludge = []
# for a in (5,10,20,40,80):

raw_wastewater = qs.Stream('raw_wastewater', H2O=100, units='MGD', T=25+273.15)
# Jones baseline: 1276.6 MGD, 1.066e-4 $/kg ww
# set H2O equal to the total raw wastewater into the WWTP

# =============================================================================
# pretreatment (Area 000)
# =============================================================================

# results_diesel = []
# results_sludge = []
# for a in (0,0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1):
#     for b in (0,0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1):
#         if a + b <= 1:
            
WWTP = su.WWTP('S000', ins=raw_wastewater, outs=('sludge','treated_water'),
                    ww_2_dry_sludge=0.94,
                    # how much metric ton/day sludge can be produced by 1 MGD of ww
                    sludge_moisture=0.99, sludge_dw_ash=0.257, 
                    sludge_afdw_lipid=0.204, sludge_afdw_protein=0.463, operation_hours=7920)

SluC = su.HTL_sludge_centrifuge('A000', ins=WWTP-0,
                            outs=('supernatant','compressed_sludge'),
                            init_with='Stream',
                            solids=('Sludge_lipid','Sludge_protein',
                                    'Sludge_carbo','Sludge_ash'),
                            sludge_moisture=0.8)

# =============================================================================
# HTL (Area 100)
# =============================================================================

P1 = su.HTLpump('A100', ins=SluC-1, outs='press_sludge', P=3049.7*6894.76,
              init_with='Stream')
# Jones 2014: 3049.7 psia

H1 = su.HTLHX('A110', ins=P1-0, outs='heated_sludge', T=351+273.15,
                   U=0.0795, init_with='Stream', rigorous=True)
# feed T is low, thus high viscosity and low U (case B in Knorr 2013)
# U: 3, 14, 15 BTU/hr/ft2/F as minimum, baseline, and maximum
# U: 0.0170348, 0.0794957, 0.085174 kW/m2/K
# H1: SS PNNL 2020: 50 (17-76) Btu/hr/ft2/F ~ U = 0.284 (0.096-0.4313) kW/m2/K
# but not in other pumps (low viscosity, don't need U to enforce total heat transfer efficiency)
# unit conversion: https://www.unitsconverters.com/en/Btu(It)/Hmft2mdegf-To-W/M2mk/Utu-4404-4398

HTL = su.HTL('A120', ins=H1-0, outs=('biochar','HTL_aqueous',
             'biocrude','offgas_HTL'))
HTL_hx = HTL.heat_exchanger
HTL_drum = HTL.kodrum

# =============================================================================
# CHG (Area 200)
# =============================================================================

H2SO4_Tank = su.HTL_storage_tank('T200', ins='H2SO4', outs=('H2SO4_out'),
                             init_with='WasteStream', tau=24, vessel_material='Stainless steel')
H2SO4_Tank.ins[0].price = 0.00658 # based on 93% H2SO4 and fresh water (dilute to 5%) price found in Davis 2020$/kg

SP1 = su.HTLsplitter('S200',ins=H2SO4_Tank-0, outs=('H2SO4_P','H2SO4_N'),
                     init_with='Stream')
# must put after AcidEx and MemDis in path during simulation to ensure input
# not empty

AcidEx = su.AcidExtraction('A200', ins=(HTL-0, SP1-0),
                           outs=('residual','extracted'))

# AcidEx.outs[0].price = -0.055 # SS 2021 SOT PNNL report page 24 Table 9
# not include residual for TEA and LCA for now

# baseline:
M1 = su.HTLmixer('A210', ins=(HTL-1, AcidEx-1), outs=('mixture'))

# if remove AcidEx:
# M1 = su.HTLmixer('A210', ins=(HTL-1, ''), outs=('mixture'))

StruPre = su.StruvitePrecipitation('A220', ins=(M1-0,'MgCl2','NH4Cl','MgO'),
                                   outs=('struvite','CHG_feed'))
StruPre.ins[1].price = 0.5452
StruPre.ins[2].price = 0.13
StruPre.ins[3].price = 0.2
StruPre.outs[0].price = 0.661

CHG = su.CHG('A230', ins=(StruPre-1, '7.8%_Ru/C'), outs=('CHG_out', '7.8%_Ru/C_out'))
CHG_pump = CHG.pump
CHG_heating = CHG.heat_ex_heating
CHG_cooling = CHG.heat_ex_cooling
CHG.ins[1].price = 134.53

V1 = IsenthalpicValve('A240', ins=CHG-0, outs='depressed_cooled_CHG', P=50*6894.76, vle=True)

F1 = su.HTLflash('A250', ins=V1-0, outs=('CHG_fuel_gas','N_riched_aqueous'),
                 T=60+273.15, P=50*6894.76)

MemDis = su.MembraneDistillation('A260', ins=(F1-1, SP1-1, 'NaOH', 'Membrane_in'),
                                  outs=('ammonium_sulfate','MemDis_ww', 'Membrane_out','solution'), init_with='WasteStream')
MemDis.ins[2].price = 0.5256
MemDis.outs[0].price = 0.3236

# =============================================================================
# HT (Area 300)
# =============================================================================

P2 = su.HTLpump('A300', ins=HTL-2, outs='press_biocrude', P=1530.0*6894.76,
              init_with='Stream')
# Jones 2014: 1530.0 psia

# Tin = 174 C (345 F) based on Jones PNNL report. However, the reaction
# releases a lot of heat and increase the temperature of effluent to 402 C
# (755.5 F).

RSP1 = qsu.ReversedSplitter('S300', ins='H2', outs=('HT_H2','HC_H2'),
                            init_with='WasteStream')
# reversed splitter, write before HT and HC, simulate after HT and HC
RSP1.ins[0].price = 1.61

HT = su.HT_PSA('A310', ins=(P2-0, RSP1-0, 'CoMo_alumina_HT'), outs=('HTout', 'CoMo_alumina_HT_out'))
HT_compressor = HT.compressor
HT_hx_H2 = HT.heat_exchanger_H2
HT_hx_oil = HT.heat_exchanger_oil
HT.ins[2].price = 38.79

V2 = IsenthalpicValve('A320', ins=HT-0, outs='depressed_HT', P=717.4*6894.76, vle=True)

H2 = su.HTLHX('A330', ins=V2-0, outs='cooled_HT', T=60+273.15,
                    init_with='Stream', rigorous=True)

F2 = su.HTLflash('A340', ins=H2-0, outs=('HT_fuel_gas','HT_aqueous'), T=43+273.15,
                 P=717.4*6894.76) # outflow P

V3 = IsenthalpicValve('A350', ins=F2-1, outs='depressed_flash_effluent', P=55*6894.76, vle=True)

SP2 = qsu.Splitter('S310', ins=V3-0, outs=('HT_ww','HT_oil'),
                    split={'H2O':1}, init_with='Stream')
# separate water and oil based on gravity

H3 = su.HTLHX('A360', ins=SP2-1, outs='heated_oil', T=104+273.15, rigorous=True)
# temperature: Jones stream #334 (we remove the first distillation column)

D1 = su.HTLdistillation('A370', ins=H3-0,
                        outs=('HT_light','HT_heavy'),
                        LHK=('C4H10','TWOMBUTAN'), P=50*6894.76, # outflow P
                        y_top=188/253, x_bot=53/162, k=2, is_divided=True)

D2 = su.HTLdistillation('A380', ins=D1-1,
                        outs=('HT_Gasoline','HT_other_oil'),
                        LHK=('C10H22','C4BENZ'), P=25*6894.76, # outflow P
                        y_top=116/122, x_bot=114/732, k=2, is_divided=True)

D3 = su.HTLdistillation('A390', ins=D2-1,
                        outs=('HT_Diesel','HT_heavy_oil'),
                        LHK=('C19H40','C21H44'),P=18.7*6894.76, # outflow P
                        y_top=2421/2448, x_bot=158/2448, k=2, is_divided=True)

# =============================================================================
# HC (Area 400)
# =============================================================================

P3 = su.HTLpump('A400', ins=D3-1, outs='press_heavy_oil', P=1034.7*6894.76,
              init_with='Stream')
# Jones 2014: 1034.7 psia

# Tin = 394 C (741.2 F) based on Jones PNNL report. However, the reaction
# releases a lot of heat and increase the temperature of effluent to 451 C
# (844.6 F).

HC = su.HC('A410', ins=(P3-0, RSP1-1, 'CoMo_alumina_HC'), outs=('HC_out', 'CoMo_alumina_HC_out'))
HC_compressor = HC.compressor
HC_hx_H2 = HC.heat_exchanger_H2
HC_hx_oil = HC.heat_exchanger_oil
HC.ins[2].price = 38.79

H4 = su.HTLHX('A420', ins=HC-0, outs='cooled_HC', T=60+273.15,
                    init_with='Stream', rigorous=True)

V4 = IsenthalpicValve('A430', ins=H4-0, outs='cooled_depressed_HC', P=30*6894.76, vle=True)


F3 = su.HTLflash('A440', ins=V4-0, outs=('HC_fuel_gas','HC_aqueous'), T=60.2+273,
                 P=30*6894.76) # outflow P

D4 = su.HTLdistillation('A450', ins=F3-1, outs=('HC_Gasoline','HC_Diesel'),
                        LHK=('C9H20','C10H22'), P=20*6894.76, # outflow P
                        y_top=360/546, x_bot=7/708, k=2, is_divided=True)

# =============================================================================
# CHP, storage, and disposal (Area 500)
# =============================================================================

GasolineMixer = qsu.Mixer('S500', ins=(D2-0, D4-0), outs='mixed_gasoline',
                          init_with='Stream', rigorous=True)

DieselMixer = qsu.Mixer('S510', ins=(D3-0, D4-1), outs='mixed_diesel',
                        init_with='Stream', rigorous=True)

H5 = su.HTLHX('A500', ins=GasolineMixer-0, outs='cooled_gasoline',
                    T=60+273.15, init_with='Stream', rigorous=True)

H6 = su.HTLHX('A510', ins=DieselMixer-0, outs='cooled_diesel',
                    T=60+273.15, init_with='Stream', rigorous=True)

PC1 = su.PhaseChanger('S520', ins=H5-0, outs='cooled_gasoline_liquid')

PC2 = su.PhaseChanger('S530', ins=H6-0, outs='cooled_diesel_liquid')

PC3 = su.PhaseChanger('S540', ins=CHG-1, outs='CHG_catalyst_out', phase='s')

PC4 = su.PhaseChanger('S550', ins=HT-1, outs='HT_catalyst_out', phase='s')

PC5 = su.PhaseChanger('S560', ins=HC-1, outs='HC_catalyst_out', phase='s')

GasolineTank = su.HTL_storage_tank('T500', ins=PC1-0, outs=('gasoline'),
                                tau=3*24, init_with='Stream', vessel_material='Carbon steel')
# store for 3 days based on Jones 2014

DieselTank = su.HTL_storage_tank('T510', ins=PC2-0, outs=('diesel'),
                              tau=3*24, init_with='Stream', vessel_material='Carbon steel')
# store for 3 days based on Jones 2014

FuelMixer = su.FuelMixer('S570', ins=(GasolineTank-0, DieselTank-0),
                         outs='fuel', target='diesel')
# integrate gasoline and diesel based on their LHV for MFSP calculation

GasMixer = qsu.Mixer('S580', ins=(HTL-3, F1-0, F2-0, D1-0, F3-0),
                      outs=('fuel_gas'), init_with='Stream')

WWmixer = su.WWmixer('S590', ins=(SluC-0, MemDis-1, SP2-0),
                    outs='wastewater', init_with='Stream')
# effluent of WWmixer goes back to WWTP

# =============================================================================
# facilities
# =============================================================================

HXN = su.HTLHXN('HXN')

CHP = su.HTLCHP('CHP', ins=(GasMixer-0, 'natural_gas', 'air'),
              outs=('emission','solid_ash'), init_with='WasteStream', supplement_power_utility=False)

CHP.ins[1].price = 0.1685

RO_item = qs.StreamImpactItem(ID='RO_item',
                              linked_stream=MemDis.ins[3],
                              Acidification=0.53533,
                              Ecotoxicity=0.90848,
                              Eutrophication=0.0028322,
                              GlobalWarming=2.2663,
                              OzoneDepletion=0.00000025541,
                              PhotochemicalOxidation=0.0089068,
                              Carcinogenics=0.034791,
                              NonCarcinogenics=31.8,
                              RespiratoryEffects=0.0028778)
                              
H2SO4_item = qs.StreamImpactItem(ID='H2SO4_item',
                                 linked_stream=H2SO4_Tank.ins[0],
                                 Acidification=0.019678922,
                                 Ecotoxicity=0.069909345,
                                 Eutrophication=4.05E-06,
                                 GlobalWarming=0.008205666,
                                 OzoneDepletion=8.94E-10,
                                 PhotochemicalOxidation=5.04E-05,
                                 Carcinogenics=1.74E-03,
                                 NonCarcinogenics=1.68237815,
                                 RespiratoryEffects=9.41E-05)

MgCl2_item = qs.StreamImpactItem(ID='MgCl2_item',
                                 linked_stream=StruPre.ins[1],
                                 Acidification=0.77016,
                                 Ecotoxicity=0.97878,
                                 Eutrophication=0.00039767,
                                 GlobalWarming=2.8779,
                                 OzoneDepletion=4.94E-08,
                                 PhotochemicalOxidation=0.0072306,
                                 Carcinogenics=0.0050938,
                                 NonCarcinogenics=8.6916,
                                 RespiratoryEffects=0.004385)

H2_item = qs.StreamImpactItem(ID='H2_item',
                              linked_stream=RSP1.ins[0],
                              Acidification=0.81014,
                              Ecotoxicity=0.42747,
                              Eutrophication=0.0029415,
                              GlobalWarming=1.5624,
                              OzoneDepletion=1.80E-06,
                              PhotochemicalOxidation=0.0052545,
                              Carcinogenics=0.0026274,
                              NonCarcinogenics=8.5687,
                              RespiratoryEffects=0.0036698)

MgO_item = qs.StreamImpactItem(ID='MgO_item',
                               linked_stream=StruPre.ins[3],
                               Acidification=0.12584,
                               Ecotoxicity=2.7949,
                               Eutrophication=0.00063607,
                               GlobalWarming=1.1606,
                               OzoneDepletion=1.54E-08,
                               PhotochemicalOxidation=0.0017137,
                               Carcinogenics=0.018607,
                               NonCarcinogenics=461.54,
                               RespiratoryEffects=0.0008755)

NaOH_item = qs.StreamImpactItem(ID='NaOH_item',
                                linked_stream=MemDis.ins[2],
                                Acidification=0.33656,
                                Ecotoxicity=0.77272,
                                Eutrophication=0.00032908,
                                GlobalWarming=1.2514,
                                OzoneDepletion=7.89E-07,
                                PhotochemicalOxidation=0.0033971,
                                Carcinogenics=0.0070044,
                                NonCarcinogenics=13.228,
                                RespiratoryEffects=0.0024543)

NH4Cl_item = qs.StreamImpactItem(ID='NH4Cl_item',
                                 linked_stream=StruPre.ins[2],
                                 Acidification=0.34682,
                                 Ecotoxicity=0.90305, 
                                 Eutrophication=0.0047381,
                                 GlobalWarming=1.525,
                                 OzoneDepletion=9.22E-08,
                                 PhotochemicalOxidation=0.0030017,
                                 Carcinogenics=0.010029,
                                 NonCarcinogenics=14.85,
                                 RespiratoryEffects=0.0018387)

struvite_item = qs.StreamImpactItem(ID='struvite_item',
                                    linked_stream=StruPre.outs[0],
                                    Acidification=-0.122829597,
                                    Ecotoxicity=-0.269606396,
                                    Eutrophication=-0.000174952,
                                    GlobalWarming=-0.420850152,
                                    OzoneDepletion=-2.29549E-08,
                                    PhotochemicalOxidation=-0.001044087,
                                    Carcinogenics=-0.002983018,
                                    NonCarcinogenics=-4.496533528,
                                    RespiratoryEffects=-0.00061764)

NH42SO4_item = qs.StreamImpactItem(ID='NH42SO4_item',
                                   linked_stream=MemDis.outs[0],
                                   Acidification=-0.72917,
                                   Ecotoxicity=-3.4746,
                                   Eutrophication=-0.0024633,
                                   GlobalWarming=-1.2499,
                                   OzoneDepletion=-6.12E-08,
                                   PhotochemicalOxidation=-0.0044519,
                                   Carcinogenics=-0.036742,
                                   NonCarcinogenics=-62.932,
                                   RespiratoryEffects=-0.0031315)

natural_gas_item = qs.StreamImpactItem(ID='natural_gas_item',
                                       linked_stream=CHP.ins[1],
                                       Acidification=0.083822558,
                                       Ecotoxicity=0.063446198,
                                       Eutrophication=7.25E-05,
                                       GlobalWarming=1.584234288,
                                       OzoneDepletion=1.23383E-07,
                                       PhotochemicalOxidation=0.000973731,
                                       Carcinogenics=0.000666424,
                                       NonCarcinogenics=3.63204,
                                       RespiratoryEffects=0.000350917)

CHG_catalyst_item = qs.StreamImpactItem(ID='CHG_catalyst_item',
                                        linked_stream=PC3.outs[0],
                                        Acidification=991.6544196,
                                        Ecotoxicity=15371.08292,
                                        Eutrophication=0.45019348,
                                        GlobalWarming=484.7862509,
                                        OzoneDepletion=2.23437E-05,
                                        PhotochemicalOxidation=6.735405072,
                                        Carcinogenics=1.616793132,
                                        NonCarcinogenics=27306.37232,
                                        RespiratoryEffects=3.517184526)

HT_catalyst_item = qs.StreamImpactItem(ID='HT_catalyst_item',
                                       linked_stream=PC4.outs[0],
                                       Acidification=4.056401283,
                                       Ecotoxicity=50.26926274,
                                       Eutrophication=0.005759274,
                                       GlobalWarming=6.375878231,
                                       OzoneDepletion=1.39248E-06,
                                       PhotochemicalOxidation=0.029648759,
                                       Carcinogenics=0.287516945,
                                       NonCarcinogenics=369.791688,
                                       RespiratoryEffects=0.020809293)

HC_catalyst_item = qs.StreamImpactItem(ID='HC_catalyst_item',
                                       linked_stream=PC5.outs[0],
                                       Acidification=4.056401283,
                                       Ecotoxicity=50.26926274,
                                       Eutrophication=0.005759274,
                                       GlobalWarming=6.375878231,
                                       OzoneDepletion=1.39248E-06,
                                       PhotochemicalOxidation=0.029648759,
                                       Carcinogenics=0.287516945,
                                       NonCarcinogenics=369.791688,
                                       RespiratoryEffects=0.020809293)

dct = globals()
for unit_alias in (
        'WWTP', 'SluC', 'P1', 'H1', 'HTL', 'HTL_hx', 'HTL_drum', 'H2SO4_Tank', 'AcidEx',
        'M1', 'StruPre', 'CHG', 'CHG_pump', 'CHG_heating', 'CHG_cooling', 'V1', 'F1', 'MemDis', 'SP1',
        'P2', 'HT', 'HT_compressor', 'HT_hx_H2', 'HT_hx_oil', 'V2', 'H2', 'F2', 'V3', 'SP2', 'H3', 'D1', 'D2', 'D3', 'P3',
        'HC', 'HC_compressor', 'HC_hx_H2', 'HC_hx_oil', 'H4', 'V4', 'F3', 'D4', 'GasolineMixer', 'DieselMixer',
        'H5', 'H6', 'PC1', 'PC2', 'PC3', 'PC4', 'PC5', 'GasolineTank', 'DieselTank', 'FuelMixer',
        'GasMixer', 'WWmixer', 'RSP1', 'HXN', 'CHP'):
    dct[unit_alias].register_alias(unit_alias)
# so that qs.main_flowsheet.H1 works as well

sys_PSA = qs.System('sys_PSA', path=(WWTP, SluC, P1, H1, HTL, H2SO4_Tank,
                             AcidEx,
                             M1, StruPre, CHG, V1, F1, MemDis, SP1,
                             P2, HT, V2, H2, F2, V3, SP2, H3, D1, D2, D3, P3,
                             HC, H4, V4, F3, D4, GasolineMixer, DieselMixer,
                             H5, H6, PC1, PC2, PC3, PC4, PC5, GasolineTank, DieselTank, FuelMixer,
                             GasMixer, WWmixer, RSP1), facilities=(HXN, CHP,))

sys_PSA.operating_hours = WWTP.operation_hours # 7920 hr Jones

lca_diesel = qs.LCA(system=sys_PSA, lifetime=30, lifetime_unit='yr',
                    Electricity=lambda:(sys_PSA.get_electricity_consumption()-sys_PSA.get_electricity_production())*30,
                    Cooling=lambda:sys_PSA.get_cooling_duty()/1000*30)

diesel_item = qs.StreamImpactItem(ID='diesel_item',
                                  linked_stream=FuelMixer.outs[0],
                                  Acidification=-0.25164,
                                  Ecotoxicity=-0.18748,
                                  Eutrophication=-0.0010547,
                                  GlobalWarming=-0.47694,
                                  OzoneDepletion=-6.42E-07,
                                  PhotochemicalOxidation=-0.0019456,
                                  Carcinogenics=-0.00069252,
                                  NonCarcinogenics=-2.9281,
                                  RespiratoryEffects=-0.0011096)

lca_sludge = qs.LCA(system=sys_PSA, lifetime=30, lifetime_unit='yr',
              Electricity=lambda:(sys_PSA.get_electricity_consumption()-sys_PSA.get_electricity_production())*30,
              Cooling=lambda:sys_PSA.get_cooling_duty()/1000*30)

tea = create_tea(sys_PSA)

# return sys_PSA
#%%
from qsdsan import Model

model = Model(sys_PSA)

from chaospy import distributions as shape

param = model.parameter

# =============================================================================
# WWTP
# =============================================================================
dist = shape.Uniform(0.846,1.034)
@param(name='ww_2_dry_sludge',
        element=WWTP,
        kind='coupled',
        units='ton/d/MGD',
        baseline=0.94,
        distribution=dist)
def set_ww_2_dry_sludge(i):
    WWTP.ww_2_dry_sludge=i

dist = shape.Uniform(0.97,0.995)
@param(name='sludge_moisture',
        element=WWTP,
        kind='coupled',
        units='-',
        baseline=0.99,
        distribution=dist)
def set_WWTP_sludge_moisture(i):
    WWTP.sludge_moisture=i

dist = shape.Triangle(0.174,0.257,0.414)
@param(name='sludge_dw_ash',
        element=WWTP,
        kind='coupled',
        units='-',
        baseline=0.257,
        distribution=dist)
def set_sludge_dw_ash(i):
    WWTP.sludge_dw_ash=i

dist = shape.Triangle(0.08,0.204,0.308)
@param(name='sludge_afdw_lipid',
        element=WWTP,
        kind='coupled',
        units='-',
        baseline=0.204,
        distribution=dist)
def set_sludge_afdw_lipid(i):
    WWTP.sludge_afdw_lipid=i

dist = shape.Triangle(0.38,0.463,0.51)
@param(name='sludge_afdw_protein',
        element=WWTP,
        kind='coupled',
        units='-',
        baseline=0.463,
        distribution=dist)
def set_sludge_afdw_protein(i):
    WWTP.sludge_afdw_protein=i

dist = shape.Uniform(0.675,0.825)
@param(name='lipid_2_C',
        element=WWTP,
        kind='coupled',
        units='-',
        baseline=0.75,
        distribution=dist)
def set_lipid_2_C(i):
    WWTP.lipid_2_C=i

dist = shape.Uniform(0.4905,0.5995)
@param(name='protein_2_C',
        element=WWTP,
        kind='coupled',
        units='-',
        baseline=0.545,
        distribution=dist)
def set_protein_2_C(i):
    WWTP.protein_2_C=i

dist = shape.Uniform(0.36,0.44)
@param(name='carbo_2_C',
        element=WWTP,
        kind='coupled',
        units='-',
        baseline=0.4,
        distribution=dist)
def set_carbo_2_C(i):
    WWTP.carbo_2_C=i

dist = shape.Triangle(0.1348,0.1427,0.1647)
@param(name='C_2_H',
        element=WWTP,
        kind='coupled',
        units='-',
        baseline=0.1427,
        distribution=dist)
def set_C_2_H(i):
    WWTP.C_2_H=i

dist = shape.Uniform(0.1431,0.1749)
@param(name='protein_2_N',
        element=WWTP,
        kind='coupled',
        units='-',
        baseline=0.159,
        distribution=dist)
def set_protein_2_N(i):
    WWTP.protein_2_N=i
    
dist = shape.Triangle(0.1944,0.3927,0.5556)
@param(name='N_2_P',
        element=WWTP,
        kind='coupled',
        units='-',
        baseline=0.3927,
        distribution=dist)
def set_N_2_P(i):
    WWTP.N_2_P=i

dist = shape.Triangle(7392,7920,8448)
@param(name='operation_hour',
        element=WWTP,
        kind='coupled',
        units='hr/yr',
        baseline=7920,
        distribution=dist)
def set_operation_hour(i):
    WWTP.operation_hours=sys_PSA.operating_hours=i

# =============================================================================
# HTL
# =============================================================================
dist = shape.Triangle(0.017035,0.0795,0.085174)
@param(name='enforced heating transfer coefficient',
        element=H1,
        kind='coupled',
        units='kW/m2/K',
        baseline=0.0795,
        distribution=dist)
def set_U(i):
    H1.U=i

dist = shape.Triangle(0.692,0.846,1)
@param(name='lipid_2_biocrude',
        element=HTL,
        kind='coupled',
        units='-',
        baseline=0.846,
        distribution=dist)
def set_lipid_2_biocrude(i):
    HTL.lipid_2_biocrude=i

dist = shape.Normal(0.445,0.030)
@param(name='protein_2_biocrude',
        element=HTL,
        kind='coupled',
        units='-',
        baseline=0.445,
        distribution=dist)
def set_protein_2_biocrude(i):
    HTL.protein_2_biocrude=i

dist = shape.Normal(0.205,0.050)
@param(name='carbo_2_biocrude',
        element=HTL,
        kind='coupled',
        units='-',
        baseline=0.205,
        distribution=dist)
def set_carbo_2_biocrude(i):
    HTL.carbo_2_biocrude=i

dist = shape.Normal(0.074,0.020)
@param(name='protein_2_gas',
        element=HTL,
        kind='coupled',
        units='-',
        baseline=0.074,
        distribution=dist)
def set_protein_2_gas(i):
    HTL.protein_2_gas=i

dist = shape.Normal(0.418,0.030)
@param(name='carbo_2_gas',
        element=HTL,
        kind='coupled',
        units='-',
        baseline=0.418,
        distribution=dist)
def set_carbo_2_gas(i):
    HTL.carbo_2_gas=i
    
dist = shape.Normal(-8.370,0.939)
@param(name='biocrude_C_slope',
        element=HTL,
        kind='coupled',
        units='-',
        baseline=-8.370,
        distribution=dist)
def set_biocrude_C_slope(i):
    HTL.biocrude_C_slope=i
    
dist = shape.Normal(68.55,0.367)
@param(name='biocrude_C_intercept',
        element=HTL,
        kind='coupled',
        units='-',
        baseline=68.55,
        distribution=dist)
def set_biocrude_C_intercept(i):
    HTL.biocrude_C_intercept=i
    
dist = shape.Normal(0.133,0.005)
@param(name='biocrude_N_slope',
        element=HTL,
        kind='coupled',
        units='-',
        baseline=0.133,
        distribution=dist)
def set_biocrude_N_slope(i):
    HTL.biocrude_N_slope=i
    
dist = shape.Normal(-2.610,0.352)
@param(name='biocrude_H_slope',
        element=HTL,
        kind='coupled',
        units='-',
        baseline=-2.610,
        distribution=dist)
def set_biocrude_H_slope(i):
    HTL.biocrude_H_slope=i

dist = shape.Normal(8.200,0.138)
@param(name='biocrude_H_intercept',
        element=HTL,
        kind='coupled',
        units='-',
        baseline=8.200,
        distribution=dist)
def set_biocrude_H_intercept(i):
    HTL.biocrude_H_intercept=i
    
dist = shape.Normal(478,18.878)
@param(name='HTLaqueous_C_slope',
        element=HTL,
        kind='coupled',
        units='-',
        baseline=478,
        distribution=dist)
def set_HTLaqueous_C_slope(i):
    HTL.HTLaqueous_C_slope=i
    
dist = shape.Triangle(0.715,0.764,0.813)
@param(name='TOC_TC',
        element=HTL,
        kind='coupled',
        units='-',
        baseline=0.764,
        distribution=dist)
def set_TOC_TC(i):
    HTL.TOC_TC=i

dist = shape.Normal(1.750,0.122)
@param(name='biochar_C_slope',
        element=HTL,
        kind='coupled',
        units='-',
        baseline=1.750,
        distribution=dist)
def set_biochar_C_slope(i):
    HTL.biochar_C_slope=i

dist = shape.Triangle(0.035,0.063,0.102)
@param(name='biocrude_moisture_content',
        element=HTL,
        kind='coupled',
        units='-',
        baseline=0.063,
        distribution=dist)
def set_biocrude_moisture_content(i):
    HTL.biocrude_moisture_content=i

dist = shape.Uniform(0.84,0.88)
@param(name='biochar_P_recovery_ratio',
        element=HTL,
        kind='coupled',
        units='-',
        baseline=0.86,
        distribution=dist)
def set_biochar_P_recovery_ratio(i):
    HTL.biochar_P_recovery_ratio=i

# =============================================================================
# AcidEx
# =============================================================================
dist = shape.Uniform(4,10)
@param(name='acid_vol',
        element=AcidEx,
        kind='coupled',
        units='-',
        baseline=7,
        distribution=dist)
def set_acid_vol(i):
    AcidEx.acid_vol=i

dist = shape.Uniform(0.7,0.9)
@param(name='P_acid_recovery_ratio',
        element=AcidEx,
        kind='coupled',
        units='-',
        baseline=0.8,
        distribution=dist)
def set_P_recovery_ratio(i):
    AcidEx.P_acid_recovery_ratio=i

# =============================================================================
# StruPre
# =============================================================================
dist = shape.Uniform(8.5,9.5)
@param(name='target_pH',
        element=StruPre,
        kind='coupled',
        units='-',
        baseline=9,
        distribution=dist)
def set_StruPre_target_pH(i):
    StruPre.target_pH=i
    
dist = shape.Triangle(0.7,0.828,0.95)
@param(name='P_pre_recovery_ratio',
        element=StruPre,
        kind='coupled',
        units='-',
        baseline=0.828,
        distribution=dist)
def set_P_pre_recovery_ratio(i):
    StruPre.P_pre_recovery_ratio=i

# =============================================================================
# CHG
# =============================================================================
dist = shape.Triangle(2.86,3.562,3.99)
@param(name='WHSV',
        element=CHG,
        kind='coupled',
        units='kg/hr/kg',
        baseline=3.562,
        distribution=dist)
def set_CHG_WHSV(i):
    CHG.WHSV=i

dist = shape.Triangle(3960,7920,15840)
@param(name='catalyst_lifetime',
        element=CHG,
        kind='coupled',
        units='hr',
        baseline=7920,
        distribution=dist)
def set_CHG_catalyst_lifetime(i):
    CHG.catalyst_lifetime=i

dist = shape.Triangle(0.1893,0.5981,0.7798)
@param(name='gas_C_2_total_C',
        element=CHG,
        kind='coupled',
        units='-',
        baseline=0.5981,
        distribution=dist)
def set_gas_C_2_total_C(i):
    CHG.gas_C_2_total_C=i

# =============================================================================
# MemDis
# =============================================================================
dist = shape.Uniform(7.91,8.41)
@param(name='influent_pH',
        element=MemDis,
        kind='coupled',
        units='-',
        baseline=8.16,
        distribution=dist)
def set_influent_pH(i):
    MemDis.influent_pH=i

dist = shape.Uniform(10,11.8)
@param(name='target_pH',
        element=MemDis,
        kind='coupled',
        units='-',
        baseline=10,
        distribution=dist)
def set_MemDis_target_pH(i):
    MemDis.target_pH=i

dist = shape.Uniform(0.00075,0.000917)
@param(name='m2_2_m3',
        element=MemDis,
        kind='coupled',
        units='-',
        baseline=1/1200,
        distribution=dist)
def set_m2_2_m3(i):
    MemDis.m2_2_m3=i

dist = shape.Uniform(0.0000205,0.0000251)
@param(name='Dm',
        element=MemDis,
        kind='coupled',
        units='m2/s',
        baseline=0.0000228,
        distribution=dist)
def set_Dm(i):
    MemDis.Dm=i

dist = shape.Uniform(0.81,0.99)
@param(name='porosity',
        element=MemDis,
        kind='coupled',
        units='-',
        baseline=0.9,
        distribution=dist)
def set_porosity(i):
    MemDis.porosity=i

dist = shape.Uniform(0.000063,0.000077)
@param(name='thickness',
        element=MemDis,
        kind='coupled',
        units='m',
        baseline=0.00007,
        distribution=dist)
def set_thickness(i):
    MemDis.thickness=i

dist = shape.Uniform(1.08,1.32)
@param(name='tortuosity',
        element=MemDis,
        kind='coupled',
        units='-',
        baseline=1.2,
        distribution=dist)
def set_tortuosity(i):
    MemDis.tortuosity=i

dist = shape.Uniform(0.0000158,0.0000193)
@param(name='Ka',
        element=MemDis,
        kind='coupled',
        units='-',
        baseline=0.0000175,
        distribution=dist)
def set_Ka(i):
    MemDis.Ka=i

dist = shape.Uniform(5.409,6.611)
@param(name='capacity',
        element=MemDis,
        kind='coupled',
        units='-',
        baseline=6.01,
        distribution=dist)
def set_capacity(i):
    MemDis.capacity=i

# =============================================================================
# HT
# =============================================================================
dist = shape.Uniform(0.5625,0.6875)
@param(name='WHSV',
        element=HT,
        kind='coupled',
        units='kg/hr/kg',
        baseline=0.625,
        distribution=dist)
def set_HT_WHSV(i):
    HT.WHSV=i

dist = shape.Triangle(7920,15840,39600)
@param(name='catalyst_lifetime',
        element=HT,
        kind='coupled',
        units='hr',
        baseline=15840,
        distribution=dist)
def set_HT_catalyst_lifetime(i):
    HT.catalyst_lifetime=i

dist = shape.Uniform(0.0414,0.0506)
@param(name='hydrogen_rxned_to_biocrude',
        element=HT,
        kind='coupled',
        units='-',
        baseline=0.046,
        distribution=dist)
def set_HT_hydrogen_rxned_to_biocrude(i):
    HT.hydrogen_rxned_to_biocrude=i

dist = shape.Uniform(0.8,0.9)
@param(name='PSA_efficiency',
        element=HT,
        kind='coupled',
        units='-',
        baseline=0.9,
        distribution=dist)
def set_PSA_efficiency(i):
    HT.PSA_efficiency=i

dist = shape.Uniform(2.4,3.6)
@param(name='hydrogen_excess',
        element=HT,
        kind='coupled',
        units='-',
        baseline=3,
        distribution=dist)
def set_HT_hydrogen_excess(i):
    HT.hydrogen_excess=i

dist = shape.Uniform(0.7875,0.9625)
@param(name='hydrocarbon_ratio',
        element=HT,
        kind='coupled',
        units='-',
        baseline=0.875,
        distribution=dist)
def set_HT_hydrocarbon_ratio(i):
    HT.hydrocarbon_ratio=i

# =============================================================================
# HC
# =============================================================================
dist = shape.Uniform(0.5625,0.6875)
@param(name='WHSV',
        element=HC,
        kind='coupled',
        units='kg/hr/kg',
        baseline=0.625,
        distribution=dist)
def set_HC_WHSV(i):
    HC.WHSV=i

dist = shape.Uniform(35640,43560)
@param(name='catalyst_lifetime',
        element=HC,
        kind='coupled',
        units='hr',
        baseline=39600,
        distribution=dist)
def set_HC_catalyst_lifetime(i):
    HC.catalyst_lifetime=i

dist = shape.Uniform(0.010125,0.012375)
@param(name='hydrogen_rxned_to_heavy_oil',
        element=HC,
        kind='coupled',
        units='-',
        baseline=0.01125,
        distribution=dist)
def set_HC_hydrogen_rxned_to_heavy_oil(i):
    HC.hydrogen_rxned_to_heavy_oil=i

dist = shape.Uniform(4.4448,6.6672)
@param(name='hydrogen_excess',
        element=HC,
        kind='coupled',
        units='-',
        baseline=5.556,
        distribution=dist)
def set_HC_hydrogen_excess(i):
    HC.hydrogen_excess=i

dist = shape.Uniform(0.9,1)
@param(name='hydrocarbon_ratio',
        element=HC,
        kind='coupled',
        units='-',
        baseline=1,
        distribution=dist)
def set_HC_hydrocarbon_ratio(i):
    HC.hydrocarbon_ratio=i

# =============================================================================
# TEA
# =============================================================================

dist = shape.Triangle(0.6,1,1.4)
@param(name='HTL_CAPEX_factor',
        element='TEA',
        kind='isolated',
        units='-',
        baseline=1,
        distribution=dist)
def set_HTL_CAPEX_factor(i):
    HTL.CAPEX_factor=i
    
dist = shape.Triangle(0.6,1,1.4)
@param(name='CHG_CAPEX_factor',
        element='TEA',
        kind='isolated',
        units='-',
        baseline=1,
        distribution=dist)
def set_CHG_CAPEX_factor(i):
    CHG.CAPEX_factor=i

dist = shape.Triangle(0.6,1,1.4)
@param(name='HT_CAPEX_factor',
        element='TEA',
        kind='isolated',
        units='-',
        baseline=1,
        distribution=dist)
def set_HT_CAPEX_factor(i):
    HT.CAPEX_factor=i

dist = shape.Uniform(980,1470)
@param(name='unit_CAPEX',
        element='TEA',
        kind='isolated',
        units='-',
        baseline=1225,
        distribution=dist)
def set_unit_CAPEX(i):
    CHP.unit_CAPEX=i

dist = shape.Triangle(0,0.1,0.2)
@param(name='IRR',
        element='TEA',
        kind='isolated',
        units='-',
        baseline=0.1,
        distribution=dist)
def set_IRR(i):
    tea.IRR=i

dist = shape.Triangle(0.005994,0.00658,0.014497)
@param(name='5% H2SO4 price',
        element='TEA',
        kind='isolated',
        units='$/kg',
        baseline=0.00658,
        distribution=dist)
def set_H2SO4_price(i):
    H2SO4_Tank.ins[0].price=i

dist = shape.Triangle(0.525,0.5452,0.57)
@param(name='MgCl2 price',
        element='TEA',
        kind='isolated',
        units='$/kg',
        baseline=0.5452,
        distribution=dist)
def set_MgCl2_price(i):
    StruPre.ins[1].price=i

dist = shape.Uniform(0.12,0.14)
@param(name='NH4Cl price',
        element='TEA',
        kind='isolated',
        units='$/kg',
        baseline=0.13,
        distribution=dist)
def set_NH4Cl_price(i):
    StruPre.ins[2].price=i

dist = shape.Uniform(0.1,0.3)
@param(name='MgO price',
        element='TEA',
        kind='isolated',
        units='$/kg',
        baseline=0.2,
        distribution=dist)
def set_MgO_price(i):
    StruPre.ins[3].price=i

dist = shape.Triangle(0.419,0.661,1.213)
@param(name='struvite price',
        element='TEA',
        kind='isolated',
        units='$/kg',
        baseline=0.661,
        distribution=dist)
def set_struvite_price(i):
    StruPre.outs[0].price=i        
        
dist = shape.Uniform(1.450,1.772)
@param(name='H2 price',
        element='TEA',
        kind='isolated',
        units='$/kg',
        baseline=1.611,
        distribution=dist)
def set_H2_price(i):
    RSP1.ins[0].price=i

dist = shape.Uniform(0.473,0.578)
@param(name='NaOH price',
        element='TEA',
        kind='isolated',
        units='$/kg',
        baseline=0.5256,
        distribution=dist)
def set_NaOH_price(i):
    MemDis.ins[2].price=i

dist = shape.Triangle(0.1636,0.3236,0.463)
@param(name='ammonium sulfate price',
        element='TEA',
        kind='isolated',
        units='$/kg',
        baseline=0.3236,
        distribution=dist)
def set_ammonium_sulfate_price(i):
    MemDis.outs[0].price=i

dist = shape.Uniform(83.96,102.62)
@param(name='membrane price',
        element='TEA',
        kind='isolated',
        units='$/kg',
        baseline=93.29,
        distribution=dist)
def set_membrane_price(i):
    MemDis.membrane_price=i

dist = shape.Triangle(67.27,134.53,269.07)
@param(name='CHG catalyst price',
        element='TEA',
        kind='isolated',
        units='$/kg',
        baseline=134.53,
        distribution=dist)
def set_catalyst_price(i):
    CHG.ins[1].price=i

dist = shape.Triangle(0.121,0.1685,0.3608)
@param(name='CH4 price',
        element='TEA',
        kind='isolated',
        units='$/kg',
        baseline=0.1685,
        distribution=dist)
def set_CH4_price(i):
    CHP.ins[1].price=i

dist = shape.Uniform(34.91,42.67)
@param(name='HT & HC catalyst price',
        element='TEA',
        kind='isolated',
        units='$/kg',
        baseline=38.79,
        distribution=dist)
def set_HT_HC_catalyst_price(i):
    HT.ins[2].price=HC.ins[2].price=i
    
dist = shape.Triangle(0.7085,0.9388,1.4493)
@param(name='gasoline price',
        element='TEA',
        kind='isolated',
        units='$/kg',
        baseline=0.9388,
        distribution=dist)
def set_gasoline_price(i):
    FuelMixer.gasoline_price=i
    
dist = shape.Triangle(0.7458,0.9722,1.6579)
@param(name='diesel price',
        element='TEA',
        kind='isolated',
        units='$/kg',
        baseline=0.9722,
        distribution=dist)
def set_diesel_price(i):
    FuelMixer.diesel_price=i
    
# dist = shape.Uniform(-0.0605,-0.0495)
# @param(name='residual disposal',
#         element='TEA',
#         kind='isolated',
#         units='$/kg',
#         baseline=-0.055,
#         distribution=dist)
# def set_residual_disposal(i):
#     AcidEx.outs[0].price=i
# not include residual for TEA and LCA for now

dist = shape.Triangle(0.0667,0.06879,0.07180)
@param(name='electricity price',
        element='TEA',
        kind='isolated',
        units='$/kg',
        baseline=0.06879,
        distribution=dist)
def set_electrivity_price(i):
    PowerUtility.price=i

# =============================================================================
# LCA (unifrom ± 10%)
# =============================================================================
# don't get joint distribution for multiple times, since the baselines for LCA will change.
for item in qs.ImpactItem.get_all_items().keys():
    for CF in qs.ImpactIndicator.get_all_indicators().keys():
        abs_small = 0.9*qs.ImpactItem.get_item(item).CFs[CF]
        abs_large = 1.1*qs.ImpactItem.get_item(item).CFs[CF]
        dist = shape.Uniform(min(abs_small,abs_large),max(abs_small,abs_large))
        @param(name=f'{item}_{CF}',
               setter=DictAttrSetter(qs.ImpactItem.get_item(item), 'CFs', CF),
               element='LCA',
               kind='isolated',
               units=qs.ImpactIndicator.get_indicator(CF).unit,
               baseline=qs.ImpactItem.get_item(item).CFs[CF],
               distribution=dist)
        def set_LCA(i):
            qs.ImpactItem.get_item(item).CFs[CF]=i

# =============================================================================
# metrics
# =============================================================================

metric = model.metric

@metric(name='sludge_C',units='kg/hr',element='Sankey')
def get_sludge_C():
    return WWTP.sludge_C

@metric(name='sludge_N',units='kg/hr',element='Sankey')
def get_sludge_N():
    return WWTP.sludge_N

@metric(name='sludge_P',units='kg/hr',element='Sankey')
def get_sludge_P():
    return WWTP.sludge_P

@metric(name='sludge_E',units='GJ/hr',element='Sankey')
def get_sludge_E():
    return (WWTP.outs[0].F_mass-WWTP.outs[0].imass['H2O'])*WWTP.sludge_HHV/1000

@metric(name='HTLaqueous_C',units='kg/hr',element='Sankey')
def get_HTLaqueous_C():
    return HTL.HTLaqueous_C

@metric(name='HTLaqueous_N',units='kg/hr',element='Sankey')
def get_HTLaqueous_N():
    return HTL.HTLaqueous_N

@metric(name='HTLaqueous_P',units='kg/hr',element='Sankey')
def get_HTLaqueous_P():
    return HTL.HTLaqueous_P

@metric(name='biocrude_C',units='kg/hr',element='Sankey')
def get_biocrude_C():
    return HTL.biocrude_C

@metric(name='biocrude_N',units='kg/hr',element='Sankey')
def get_biocrude_N():
    return HTL.biocrude_N

@metric(name='biocrude_E',units='GJ/hr',element='Sankey')
def get_biocrude_E():
    return HTL.biocrude_HHV*HTL.outs[2].imass['Biocrude']/1000

@metric(name='offgas_C',units='kg/hr',element='Sankey')
def get_offgas_C():
    return HTL.offgas_C

@metric(name='offgas_E',units='GJ/hr',element='Sankey')
def get_offgas_E():
    return HTL.outs[3].HHV/1000000

@metric(name='biochar_C',units='kg/hr',element='Sankey')
def get_biochar_C():
    return HTL.biochar_C

@metric(name='biochar_P',units='kg/hr',element='Sankey')
def get_biochar_P():
    return HTL.biochar_P

@metric(name='HT_gasoline_C',units='kg/hr',element='Sankey')
def get_HT_gasoline_C():
    carbon = 0
    for name in cmps:
        carbon += D2.outs[0].imass[str(name)]*cmps[str(name)].i_C
    return carbon

@metric(name='HT_gasoline_N',units='kg/hr',element='Sankey')
def get_HT_gasoline_N():
    nitrogen = 0
    for name in cmps:
        nitrogen += D2.outs[0].imass[str(name)]*cmps[str(name)].i_N
    return nitrogen

@metric(name='HT_gasoline_E',units='GJ/hr',element='Sankey')
def get_HT_gasoline_E():
    return D2.outs[0].HHV/1000000

@metric(name='HT_diesel_C',units='kg/hr',element='Sankey')
def get_HT_diesel_C():
    carbon = 0
    for name in cmps:
        carbon += D3.outs[0].imass[str(name)]*cmps[str(name)].i_C
    return carbon

@metric(name='HT_diesel_E',units='GJ/hr',element='Sankey')
def get_HT_diesel_E():
    return D3.outs[0].HHV/1000000

@metric(name='HT_heavy_oil_C',units='kg/hr',element='Sankey')
def get_HT_heavy_oil_C():
    carbon = 0
    for name in cmps:
        carbon += D3.outs[1].imass[str(name)]*cmps[str(name)].i_C
    return carbon

@metric(name='HT_heavy_oil_E',units='GJ/hr',element='Sankey')
def get_HT_heavy_oil_E():
    return D3.outs[1].HHV/1000000

@metric(name='HT_gas_C',units='kg/hr',element='Sankey')
def get_HT_gas_C():
    carbon = 0
    for name in cmps:
        carbon += F2.outs[0].imass[str(name)]*cmps[str(name)].i_C
        carbon += D1.outs[0].imass[str(name)]*cmps[str(name)].i_C
    return carbon

@metric(name='HT_gas_N',units='kg/hr',element='Sankey')
def get_HT_gas_N():
    nitrogen = 0
    for name in cmps:
        nitrogen += F2.outs[0].imass[str(name)]*cmps[str(name)].i_N
        nitrogen += D1.outs[0].imass[str(name)]*cmps[str(name)].i_N
    return nitrogen

@metric(name='HT_gas_E',units='GJ/hr',element='Sankey')
def get_HT_gas_E():
    return (F2.outs[0].HHV+D1.outs[0].HHV)/1000000

@metric(name='HT_ww_C',units='kg/hr',element='Sankey')
def get_HT_ww_C():
    carbon = 0
    for name in cmps:
        carbon += D2.outs[0].imass[str(name)]*cmps[str(name)].i_C
        carbon += D3.outs[0].imass[str(name)]*cmps[str(name)].i_C
        carbon += D3.outs[1].imass[str(name)]*cmps[str(name)].i_C
        carbon += F2.outs[0].imass[str(name)]*cmps[str(name)].i_C
        carbon += D1.outs[0].imass[str(name)]*cmps[str(name)].i_C
    return HTL.biocrude_C - carbon

@metric(name='HT_ww_N',units='kg/hr',element='Sankey')
def get_HT_ww_N():
    nitrogen = 0
    for name in cmps:
        nitrogen += D2.outs[0].imass[str(name)]*cmps[str(name)].i_N
        nitrogen += D3.outs[0].imass[str(name)]*cmps[str(name)].i_N
        nitrogen += D3.outs[1].imass[str(name)]*cmps[str(name)].i_N
        nitrogen += F2.outs[0].imass[str(name)]*cmps[str(name)].i_N
        nitrogen += D1.outs[0].imass[str(name)]*cmps[str(name)].i_N
    return HTL.biocrude_N - nitrogen

@metric(name='HC_gasoline_C',units='kg/hr',element='Sankey')
def get_HC_gasoline_C():
    carbon = 0
    for name in cmps:
        carbon += D4.outs[0].imass[str(name)]*cmps[str(name)].i_C
    return carbon

@metric(name='HC_gasoline_E',units='GJ/hr',element='Sankey')
def get_HC_gasoline_E():
    return D4.outs[0].HHV/1000000

@metric(name='HC_diesel_C',units='kg/hr',element='Sankey')
def get_HC_diesel_C():
    carbon = 0
    for name in cmps:
        carbon += D4.outs[1].imass[str(name)]*cmps[str(name)].i_C
    return carbon

@metric(name='HC_diesel_E',units='GJ/hr',element='Sankey')
def get_HC_diesel_E():
    return D4.outs[1].HHV/1000000

@metric(name='HC_gas_C',units='kg/hr',element='Sankey')
def get_HC_gas_C():
    carbon = 0
    for name in cmps:
        carbon += F3.outs[0].imass[str(name)]*cmps[str(name)].i_C
    return carbon

@metric(name='HC_gas_E',units='GJ/hr',element='Sankey')
def get_HC_gas_E():
    return F3.outs[0].HHV/1000000

@metric(name='HT_H2_E',units='GJ/hr',element='Sankey')
def get_HT_H2_E():
    return HT.ins[1].HHV/HT.hydrogen_excess/1000000

@metric(name='HC_H2_E',units='GJ/hr',element='Sankey')
def get_HC_H2_E():
    return HC.ins[1].HHV/HC.hydrogen_excess/1000000

@metric(name='extracted_P',units='kg/hr',element='Sankey')
def get_extracted_P():
    return AcidEx.outs[1].imass['P']

@metric(name='residual_P',units='kg/hr',element='Sankey')
def get_residual_P():
    return HTL.biochar_P-AcidEx.outs[1].imass['P']

@metric(name='residual_C',units='kg/hr',element='Sankey')
def get_residual_C():
    return HTL.biochar_C

@metric(name='struvite_N',units='kg/hr',element='Sankey')
def get_struvite_N():
    return StruPre.struvite_N

@metric(name='struvite_P',units='kg/hr',element='Sankey')
def get_struvite_P():
    return StruPre.struvite_P

@metric(name='CHG_feed_C',units='kg/hr',element='Sankey')
def get_CHG_feed_C():
    return StruPre.outs[1].imass['C']

@metric(name='CHG_feed_N',units='kg/hr',element='Sankey')
def get_CHG_feed_N():
    return StruPre.outs[1].imass['N']

@metric(name='CHG_feed_P',units='kg/hr',element='Sankey')
def get_CHG_feed_P():
    return StruPre.outs[1].imass['P']

@metric(name='CHG_out_C',units='kg/hr',element='Sankey')
def get_CHG_out_C():
    return CHG.CHGout_C

@metric(name='CHG_out_N',units='kg/hr',element='Sankey')
def get_CHG_out_N():
    return CHG.CHGout_N

@metric(name='CHG_out_P',units='kg/hr',element='Sankey')
def get_CHG_out_P():
    return CHG.CHGout_P

@metric(name='CHG_gas_C',units='kg/hr',element='Sankey')
def get_CHG_gas_C():
    carbon = 0
    for name in cmps:
        carbon += F1.outs[0].imass[str(name)]*cmps[str(name)].i_C
    return carbon

@metric(name='CHG_gas_E',units='GJ/hr',element='Sankey')
def get_CHG_gas_E():
    return F1.outs[0].HHV/1000000

@metric(name='ammoniumsulfate_N',units='kg/hr',element='Sankey')
def get_ammoniumsulfate_N():
    return MemDis.outs[0].F_mass*14.0067*2/132.14

@metric(name='MemDis_ww_C',units='kg/hr',element='Sankey')
def get_MemDis_ww_C():
    return MemDis.outs[1].imass['C']

@metric(name='MemDis_ww_N',units='kg/hr',element='Sankey')
def get_MemDis_ww_N():
    return MemDis.outs[1].imass['N']

@metric(name='MemDis_ww_P',units='kg/hr',element='Sankey')
def get_MemDis_ww_P():
    return MemDis.outs[1].imass['P']

@metric(name='MFSP',units='$/gal diesel',element='TEA')
def get_MFSP():
    return tea.solve_price(FuelMixer.outs[0])*FuelMixer.diesel_gal_2_kg

@metric(name='GWP_diesel',units='g CO2/MMBTU diesel',element='LCA')
def get_LCA_diesel():
    return lca_diesel.get_total_impacts()['GlobalWarming']/FuelMixer.outs[0].F_mass/sys_PSA.operating_hours/lca_diesel.lifetime*_kg_to_g/45.5/_MJ_to_MMBTU
# diesel: 45.5 MJ/kg

@metric(name='GWP_sludge',units='kg CO2/ton dry sludge',element='LCA')
def get_LCA_sludge():
    return lca_sludge.get_total_impacts()['GlobalWarming']/raw_wastewater.F_vol/_m3perh_to_MGD/WWTP.ww_2_dry_sludge/(sys_PSA.operating_hours/24)/lca_sludge.lifetime

#%%
np.random.seed(3221)
samples = model.sample(N=1000, rule='L')
model.load_samples(samples)
model.evaluate()
model.table
#%%
def organize_results(model, path):
    idx = len(model.parameters)
    parameters = model.table.iloc[:, :idx]
    results = model.table.iloc[:, idx:]
    percentiles = results.quantile([0, 0.05, 0.25, 0.5, 0.75, 0.95, 1])
    with pd.ExcelWriter(path) as writer:
        parameters.to_excel(writer, sheet_name='Parameters')
        results.to_excel(writer, sheet_name='Results')
        percentiles.to_excel(writer, sheet_name='Percentiles')
organize_results(model, 'example_model.xlsx')
#%%
fig, ax = qs.stats.plot_uncertainties(model)
fig
#%%
fig, ax = qs.stats.plot_uncertainties(model, x_axis=model.metrics[0], y_axis=model.metrics[1],
                                      kind='kde-kde', center_kws={'fill': True})
fig
#%%
r_df, p_df = qs.stats.get_correlations(model, kind='Spearman', nan_policy='omit')
fig, ax = qs.stats.plot_correlations(r_df)
fig