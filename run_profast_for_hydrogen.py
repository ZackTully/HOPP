# -*- coding: utf-8 -*-
"""
Created on Tue Oct 25 12:31:28 2022

@author: ereznic2
"""
# Specify file path to PyFAST
import sys
#sys.path.insert(1,'../PyFAST/')
import numpy as np
import pandas as pd
import ProFAST

import LCA_single_scenario_ProFAST

sys.path.append('../ProFAST/')

pf = ProFAST.ProFAST()


def run_profast_for_hydrogen(site_location,electrolyzer_size_mw,H2_Results,\
                            electrolyzer_system_capex_kw,time_between_replacement,electrolyzer_energy_kWh_per_kg,hydrogen_storage_capacity_kg,hydrogen_storage_cost_USDprkg,\
                            capex_desal,opex_desal,plant_life,water_cost,wind_size_mw,solar_size_mw,hybrid_plant,revised_renewable_cost,wind_om_cost_kw,grid_connected_hopp,\
                            grid_connection_scenario, atb_year, site_name, policy_option):

    # plant_life=useful_life
    # electrolyzer_system_capex_kw = electrolyzer_capex_kw
    
    # Estimate average efficiency and water consumption
    electrolyzer_efficiency_while_running = []
    water_consumption_while_running = []
    hydrogen_production_while_running = []
    for j in range(len(H2_Results['electrolyzer_total_efficiency'])):
        if H2_Results['hydrogen_hourly_production'][j] > 0:
            electrolyzer_efficiency_while_running.append(H2_Results['electrolyzer_total_efficiency'][j])
            water_consumption_while_running.append(H2_Results['water_hourly_usage'][j])
            hydrogen_production_while_running.append(H2_Results['hydrogen_hourly_production'][j])
    
    #electrolyzer_design_efficiency_HHV = np.max(electrolyzer_efficiency_while_running) # Should ideally be user input
    electrolyzer_average_efficiency_HHV = np.mean(electrolyzer_efficiency_while_running)
    water_consumption_avg_kgprhr = np.mean(water_consumption_while_running)
    
    water_consumption_avg_kgH2O_prkgH2 = water_consumption_avg_kgprhr/np.mean(hydrogen_production_while_running)
    
    water_consumption_avg_galH2O_prkgH2 = water_consumption_avg_kgH2O_prkgH2/3.79
    
    # Calculate average electricity consumption from average efficiency
    h2_HHV = 141.88
    elec_avg_consumption_kWhprkg = h2_HHV*1000/3600/electrolyzer_average_efficiency_HHV
    
    # Design point electricity consumption
    elec_consumption_kWhprkg_design = electrolyzer_energy_kWh_per_kg

    # Calculate electrolyzer production capacity
    electrolysis_plant_capacity_kgperday=   electrolyzer_size_mw/elec_consumption_kWhprkg_design*1000*24
    #electrolysis_plant_capacity_kgperday = electrolyzer_size_mw*electrolyzer_design_efficiency_HHV/h2_HHV*3600*24
    
    # Installed capital cost
    electrolyzer_installation_factor = 12/100  #[%] for stack cost 
    
    # Indirect capital cost as a percentage of installed capital cost
    site_prep = 2/100   #[%]
    engineering_design = 10/100 #[%]
    project_contingency = 15/100 #[%]
    permitting = 15/100     #[%]
    land_cost = 250000   #[$]
    
    stack_replacement_cost = 15/100  #[% of installed capital cost]
    fixed_OM = 0.24     #[$/kg H2]    
    
    # Calculate electrolyzer installation cost
    total_direct_electrolyzer_cost_kw = (electrolyzer_system_capex_kw * (1+electrolyzer_installation_factor)) \
    
    electrolyzer_total_installed_capex = total_direct_electrolyzer_cost_kw*electrolyzer_size_mw*1000
    
    electrolyzer_indirect_cost = electrolyzer_total_installed_capex*(site_prep+engineering_design+project_contingency+permitting)
    
    #electrolyzer_installation_cost = electrolyzer_system_capex_kw*stack_installation_factor*electrolyzer_size_mw\
    #                               + electrolyzer_indirect_cost                             
    
    compressor_capex_USDprkWe_of_electrolysis = 39
    
    # Renewables system size
    system_rating_mw = wind_size_mw + solar_size_mw
     
    # Calculate capital costs
    capex_electrolyzer_overnight = electrolyzer_total_installed_capex + electrolyzer_indirect_cost
    capex_storage_installed = hydrogen_storage_capacity_kg*hydrogen_storage_cost_USDprkg
    capex_compressor_installed = compressor_capex_USDprkWe_of_electrolysis*electrolyzer_size_mw*1000
    #capex_hybrid_installed = hybrid_plant.grid.total_installed_cost
    capex_hybrid_installed = revised_renewable_cost
    
    # Fixed and variable costs
    fixed_OM = 12.8 #[$/kW-y]
    fixed_cost_electrolysis_total = fixed_OM*electrolyzer_size_mw*1000
    property_tax_insurance = 1.5/100    #[% of Cap/y]
    variable_OM = 1.30  #[$/MWh]
    
    electrolysis_total_EI_policy_grid,electrolysis_total_EI_policy_offgrid\
          = LCA_single_scenario_ProFAST.hydrogen_LCA_singlescenario_ProFAST(grid_connection_scenario,atb_year,site_name,policy_option,hydrogen_production_while_running,electrolyzer_energy_kWh_per_kg)
    if grid_connection_scenario == 'grid-only':
        # If grid connected, conservatively assume electrolyzer runs with high CF
        # Or just take this straight from H2_Results if that works
        elec_cf = 0.97
        Ren_PTC = 0
        electrolysis_total_EI_policy = electrolysis_total_EI_policy_grid
    elif grid_connection_scenario == 'off-grid':
        # If not grid connected, max CF will be relative to total renewable energy in
        elec_cf = H2_Results['cap_factor']
        electrolysis_total_EI_policy = electrolysis_total_EI_policy_offgrid
        if policy_option == 'no policy':
            Ren_PTC = 0
        elif policy_option == 'max':
            Ren_PTC = 0.03072
        elif policy_option == 'base':
            Ren_PTC = 0.0051              
    elif grid_connection_scenario == 'hybrid-grid':
         elec_cf = H2_Results['cap_factor']
         ren_frac = elec_cf/0.97 
         electrolysis_total_EI_policy = ren_frac * electrolysis_total_EI_policy_offgrid + (1 - ren_frac) * electrolysis_total_EI_policy_grid
         if policy_option == 'no policy':
             Ren_PTC = 0
         elif policy_option == 'max':
             Ren_PTC = ren_frac * 0.03072  
         elif policy_option == 'base':
             Ren_PTC = ren_frac * 0.0051   

    # Amortized refurbishment expense [$/MWh]
    amortized_refurbish_cost = (total_direct_electrolyzer_cost_kw*stack_replacement_cost)\
            *max(((plant_life*8760*elec_cf)/time_between_replacement-1),0)/plant_life/8760/elec_cf*1000

    total_variable_OM = variable_OM+amortized_refurbish_cost
    
    total_variable_OM_perkg = total_variable_OM*elec_avg_consumption_kWhprkg/1000
    
    fixed_cost_renewables = wind_om_cost_kw*system_rating_mw*1000    
    
    H2_PTC_duration = 10 # years
    Ren_PTC_duration = 10 # years
    
    if policy_option == 'no policy':
        H2_PTC = 0 # $/kg H2
        Ren_PTC = 0 # $/kWh
        
    elif policy_option == 'max':
           
        if electrolysis_total_EI_policy <= 0.45: # kg CO2e/kg H2
            H2_PTC = 3 # $/kg H2
        elif electrolysis_total_EI_policy > 0.45 and electrolysis_total_EI_policy <= 1.5: # kg CO2e/kg H2
            H2_PTC = 1 # $/kg H2
        elif electrolysis_total_EI_policy > 1.5 and electrolysis_total_EI_policy <= 2.5: # kg CO2e/kg H2     
            H2_PTC = 0.75 # $/kg H2
        elif electrolysis_total_EI_policy > 2.5 and electrolysis_total_EI_policy <= 4: # kg CO2e/kg H2    
            H2_PTC = 0.6 # $/kg H2 
        elif electrolysis_total_EI_policy > 4:
            H2_PTC = 0
                                
    elif policy_option == 'base':
            
        if electrolysis_total_EI_policy <= 0.45: # kg CO2e/kg H2
            H2_PTC = 0.6 # $/kg H2
        elif electrolysis_total_EI_policy > 0.45 and electrolysis_total_EI_policy <= 1.5: # kg CO2e/kg H2
            H2_PTC = 0.2 # $/kg H2
        elif electrolysis_total_EI_policy > 1.5 and electrolysis_total_EI_policy <= 2.5: # kg CO2e/kg H2     
            H2_PTC = 0.15 # $/kg H2
        elif electrolysis_total_EI_policy > 2.5 and electrolysis_total_EI_policy <= 4: # kg CO2e/kg H2    
            H2_PTC = 0.12 # $/kg H2    
        elif electrolysis_total_EI_policy > 4:
            H2_PTC = 0
        
    # Reassign PTC values to zero for atb year 2035
    if atb_year == 2035: # need to clarify with Matt when exactly the H2 PTC would end 
        H2_PTC = 0
        Ren_PTC = 0        

    Ren_PTC_perkgH2 = Ren_PTC * elec_consumption_kWhprkg_design 

    # Set up ProFAST
    pf = ProFAST.ProFAST('blank')
    
    # Fill these in - can have most of them as 0 also
    gen_inflation = 0.00
    pf.set_params('commodity',{"name":'Hydrogen',"unit":"kg","initial price":100,"escalation":gen_inflation})
    pf.set_params('capacity',electrolysis_plant_capacity_kgperday) #units/day
    pf.set_params('maintenance',{"value":0,"escalation":gen_inflation})
    pf.set_params('analysis start year',2022)
    pf.set_params('operating life',plant_life)
    pf.set_params('installation months',36)
    pf.set_params('installation cost',{"value":0,"depr type":"Straight line","depr period":4,"depreciable":False})
    pf.set_params('non depr assets',land_cost)
    pf.set_params('end of proj sale non depr assets',land_cost*(1+gen_inflation)**plant_life)
    pf.set_params('demand rampup',0)
    pf.set_params('long term utilization',H2_Results['cap_factor'])
    pf.set_params('credit card fees',0)
    pf.set_params('sales tax',0) 
    pf.set_params('license and permit',{'value':00,'escalation':gen_inflation})
    pf.set_params('rent',{'value':0,'escalation':gen_inflation})
    pf.set_params('property tax and insurance percent',property_tax_insurance)
    pf.set_params('admin expense percent',0)
    pf.set_params('total income tax rate',0.27)
    pf.set_params('capital gains tax rate',0.15)
    pf.set_params('sell undepreciated cap',True)
    pf.set_params('tax losses monetized',True)
    pf.set_params('operating incentives taxable',True)
    pf.set_params('general inflation rate',gen_inflation)
    pf.set_params('leverage after tax nominal discount rate',0.0824)
    pf.set_params('debt equity ratio of initial financing',1.38)
    pf.set_params('debt type','Revolving debt')
    pf.set_params('debt interest rate',0.0489)
    pf.set_params('cash onhand percent',1)
    
    #----------------------------------- Add capital items to ProFAST ----------------
    pf.add_capital_item(name="Electrolysis system",cost=capex_electrolyzer_overnight,depr_type="MACRS",depr_period=5,refurb=[0])
    pf.add_capital_item(name="Compression",cost=capex_compressor_installed,depr_type="MACRS",depr_period=5,refurb=[0])
    pf.add_capital_item(name="Hydrogen Storage",cost=capex_storage_installed,depr_type="MACRS",depr_period=5,refurb=[0])
    pf.add_capital_item(name ="Desalination",cost = capex_desal,depr_type="MACRS",depr_period=5,refurb=[0])
    pf.add_capital_item(name = "Renewable Plant",cost = capex_hybrid_installed,depr_type = "MACRS",depr_period = 5,refurb = [0])
    
    total_capex = capex_electrolyzer_overnight+capex_compressor_installed+capex_storage_installed+capex_desal+capex_hybrid_installed

    capex_fraction = {'Electrolyzer':capex_electrolyzer_overnight/total_capex,
                      'Compression':capex_compressor_installed/total_capex,
                      'Hydrogen Storage':capex_storage_installed/total_capex,
                      'Desalination':capex_desal/total_capex,
                      'Renewable Plant':capex_hybrid_installed/total_capex}
    
    #-------------------------------------- Add fixed costs--------------------------------
    pf.add_fixed_cost(name="Electrolyzer Fixed O&M Cost",usage=1.0,unit='$/year',cost=fixed_cost_electrolysis_total,escalation=gen_inflation)
    pf.add_fixed_cost(name="Desalination Fixed O&M Cost",usage=1.0,unit='$/year',cost=opex_desal,escalation=gen_inflation)
    pf.add_fixed_cost(name="Renewable Plant Fixed O&M Cost",usage=1.0,unit='$/year',cost=fixed_cost_renewables,escalation=gen_inflation)
    
    #---------------------- Add feedstocks, note the various cost options-------------------
    #pf.add_feedstock(name='Electricity',usage=elec_avg_consumption_kWhprkg,unit='kWh',cost=lcoe/100,escalation=gen_inflation)
    pf.add_feedstock(name='Water',usage=water_consumption_avg_galH2O_prkgH2,unit='gallon-water',cost=water_cost,escalation=gen_inflation)
    pf.add_feedstock(name='Var O&M',usage=1.0,unit='$/kg',cost=total_variable_OM_perkg,escalation=gen_inflation)
    
    #---------------------- Add various tax credit incentives -------------------
    pf.add_incentive(name ='Renewable PTC credit', value=Ren_PTC_perkgH2, decay = 0, sunset_years = Ren_PTC_duration, tax_credit = True)
    pf.add_incentive(name ='Hydrogen PTC credit', value=H2_PTC, decay = 0, sunset_years = H2_PTC_duration, tax_credit = True)
        
    sol = pf.solve_price()
    
    summary = pf.summary_vals
    
    price_breakdown = pf.get_cost_breakdown()
    
    # Calculate financial expense associated with equipment
    cap_expense = price_breakdown.loc[price_breakdown['Name']=='Repayment of debt','NPV'].tolist()[0]\
        + price_breakdown.loc[price_breakdown['Name']=='Interest expense','NPV'].tolist()[0]\
        + price_breakdown.loc[price_breakdown['Name']=='Dividends paid','NPV'].tolist()[0]\
        - price_breakdown.loc[price_breakdown['Name']=='Inflow of debt','NPV'].tolist()[0]\
        - price_breakdown.loc[price_breakdown['Name']=='Inflow of equity','NPV'].tolist()[0]    
        
    # Calculate remaining financial expenses
    remaining_financial = price_breakdown.loc[price_breakdown['Name']=='Non-depreciable assets','NPV'].tolist()[0]\
        + price_breakdown.loc[price_breakdown['Name']=='Cash on hand reserve','NPV'].tolist()[0]\
        + price_breakdown.loc[price_breakdown['Name']=='Property insurance','NPV'].tolist()[0]\
        - price_breakdown.loc[price_breakdown['Name']=='Sale of non-depreciable assets','NPV'].tolist()[0]\
        - price_breakdown.loc[price_breakdown['Name']=='Cash on hand recovery','NPV'].tolist()[0]
    
    # Calculate LCOH breakdown and assign capital expense to equipment costs
    price_breakdown_electrolyzer = price_breakdown.loc[price_breakdown['Name']=='Electrolysis system','NPV'].tolist()[0] + cap_expense*capex_fraction['Electrolyzer']
    price_breakdown_compression = price_breakdown.loc[price_breakdown['Name']=='Compression','NPV'].tolist()[0] + cap_expense*capex_fraction['Compression']
    price_breakdown_storage = price_breakdown.loc[price_breakdown['Name']=='Hydrogen Storage','NPV'].tolist()[0]+cap_expense*capex_fraction['Hydrogen Storage']
    price_breakdown_desalination = price_breakdown.loc[price_breakdown['Name']=='Desalination','NPV'].tolist()[0] + cap_expense*capex_fraction['Desalination']
    price_breakdown_renewables = price_breakdown.loc[price_breakdown['Name']=='Renewable Plant','NPV'].tolist()[0] + cap_expense*capex_fraction['Renewable Plant']
    price_breakdown_electrolysis_FOM = price_breakdown.loc[price_breakdown['Name']=='Electrolyzer Fixed O&M Cost','NPV'].tolist()[0]
    price_breakdown_electrolysis_VOM = price_breakdown.loc[price_breakdown['Name']=='Var O&M','NPV'].tolist()[0]
    price_breakdown_desalination_FOM = price_breakdown.loc[price_breakdown['Name']=='Desalination Fixed O&M Cost','NPV'].tolist()[0]
    price_breakdown_renewables_FOM = price_breakdown.loc[price_breakdown['Name']=='Renewable Plant Fixed O&M Cost','NPV'].tolist()[0]    
    price_breakdown_taxes = price_breakdown.loc[price_breakdown['Name']=='Income taxes payable','NPV'].tolist()[0]\
        - price_breakdown.loc[price_breakdown['Name'] == 'Monetized tax losses','NPV'].tolist()[0]\
            
    if gen_inflation > 0:
        price_breakdown_taxes = price_breakdown_taxes + price_breakdown.loc[price_breakdown['Name']=='Capital gains taxes payable','NPV'].tolist()[0]

    price_breakdown_water = price_breakdown.loc[price_breakdown['Name']=='Water','NPV'].tolist()[0]
       
    # price_breakdown_financial = price_breakdown.loc[price_breakdown['Name']=='Non-depreciable assets','NPV'].tolist()[0]\
    #     + price_breakdown.loc[price_breakdown['Name']=='Cash on hand reserve','NPV'].tolist()[0]\
    #     + price_breakdown.loc[price_breakdown['Name']=='Property insurance','NPV'].tolist()[0]\
    #     + price_breakdown.loc[price_breakdown['Name']=='Repayment of debt','NPV'].tolist()[0]\
    #     + price_breakdown.loc[price_breakdown['Name']=='Interest expense','NPV'].tolist()[0]\
    #     + price_breakdown.loc[price_breakdown['Name']=='Dividends paid','NPV'].tolist()[0]\
    #     - price_breakdown.loc[price_breakdown['Name']=='Sale of non-depreciable assets','NPV'].tolist()[0]\
    #     - price_breakdown.loc[price_breakdown['Name']=='Cash on hand recovery','NPV'].tolist()[0]\
    #     - price_breakdown.loc[price_breakdown['Name']=='Inflow of debt','NPV'].tolist()[0]\
    #     - price_breakdown.loc[price_breakdown['Name']=='Inflow of equity','NPV'].tolist()[0]
        
    lcoh_check = price_breakdown_electrolyzer+price_breakdown_compression+price_breakdown_storage+price_breakdown_electrolysis_FOM\
        + price_breakdown_desalination+price_breakdown_desalination_FOM+ price_breakdown_electrolysis_VOM\
            +price_breakdown_renewables+price_breakdown_renewables_FOM+price_breakdown_taxes+price_breakdown_water+remaining_financial
        
    lcoh_breakdown = {'LCOH: Compression & storage ($/kg)':price_breakdown_storage+price_breakdown_compression,\
                      'LCOH: Electrolyzer CAPEX ($/kg)':price_breakdown_electrolyzer,'LCOH: Desalination CAPEX ($/kg)':price_breakdown_desalination,\
                      'LCOH: Electrolyzer FOM ($/kg)':price_breakdown_electrolysis_FOM,'LCOH: Electrolyzer VOM ($/kg)':price_breakdown_electrolysis_VOM,\
                      'LCOH: Desalination FOM ($/kg)':price_breakdown_desalination_FOM,'LCOH: Renewable plant ($/kg)':price_breakdown_renewables,\
                      'LCOH: Renewable FOM ($/kg)':price_breakdown_renewables_FOM,'LCOH: Taxes ($/kg)':price_breakdown_taxes,'LCOH: Water consumption ($/kg)':price_breakdown_water,\
                      'LCOH: Finances ($/kg)':remaining_financial,'LCOH: total ($/kg)':lcoh_check}
    

    return(sol,summary,lcoh_breakdown,capex_electrolyzer_overnight/system_rating_mw/1000)