# -*- coding: utf-8 -*-
"""
Created on Tue Oct 25 10:50:54 2022

@author: ereznic2
"""
import os
import pandas as pd
import numpy as np
import time

def run_RODeO(atb_year,site_location,turbine_model,wind_size_mw,solar_size_mw,electrolyzer_size_mw,\
              energy_to_electrolyzer,hybrid_plant,electrolyzer_capex_kw,useful_life,time_between_replacement,\
              grid_connected_rodeo,gams_locations_rodeo_version,output_dir):

     # Renewable generation profile
     system_rating_mw = wind_size_mw + solar_size_mw
     # Renewable output profile needs to be same length as number of time periods in RODeO.
     # Ideally it would be 8760 but if for some reason a couple hours less, this is a simple fix
     while len(energy_to_electrolyzer)<8760:
         energy_to_electrolyzer.append(energy_to_electrolyzer[-1])
         
     electrical_generation_timeseries = np.zeros_like(energy_to_electrolyzer)
     electrical_generation_timeseries[:] = energy_to_electrolyzer[:]
     # Put electrolyzer input into MW
     electrical_generation_timeseries = electrical_generation_timeseries/1000
     # Normalize renewable profile to 1. In my experience (Evan) this helps RODeO run more smoothly but might not be necessary. Should experiment with it.
     electrical_generation_timeseries = electrical_generation_timeseries/system_rating_mw
     # Get renewable generation profile into a format that works for RODeO
     electrical_generation_timeseries_df = pd.DataFrame(electrical_generation_timeseries).reset_index().rename(columns = {'index':'Interval',0:1})
     electrical_generation_timeseries_df['Interval'] = electrical_generation_timeseries_df['Interval']+1
     electrical_generation_timeseries_df = electrical_generation_timeseries_df.set_index('Interval')
     
     # Fill in renewable profile for RODeO with zeros for years 2-20 (because for some reason it neesd this)
     extra_zeroes = np.zeros_like(energy_to_electrolyzer)
     for j in range(19):
         #j=0
         extra_zeroes_df = pd.DataFrame(extra_zeroes,columns = [j+2]).reset_index().rename(columns = {'index':'Interval',0:j+2})
         extra_zeroes_df['Interval'] = extra_zeroes_df['Interval']+1
         extra_zeroes_df = extra_zeroes_df.set_index('Interval')
         electrical_generation_timeseries_df = electrical_generation_timeseries_df.join(extra_zeroes_df)
         # normalized_demand_df = normalized_demand_df.join(extra_zeroes_df)

     # Write the renewable generation profile to a .csv file in the RODeO repository, assuming RODeO is installed in the same folder as HOPP
     ren_profile_name = 'ren_profile_'+str(atb_year) + '_'+site_location.replace(' ','_') + '_'+ turbine_model
     electrical_generation_timeseries_df.to_csv("examples/H2_Analysis/RODeO_files/Data_files/TXT_files/Ren_profile/" + ren_profile_name + '.csv',sep = ',')
     
     # Storage costs as a function of location
     if site_location == 'Site 1':
         h2_storage_cost_USDperkg =25
         balancing_area = 'p65'
         hybrid_fixed_om_cost_kw = 103
     elif site_location == 'Site 2':
         h2_storage_cost_USDperkg = 540
         balancing_area ='p124'
         hybrid_fixed_om_cost_kw = 83
     elif site_location == 'Site 3':
         h2_storage_cost_USDperkg = 54
         balancing_area = 'p128'
         hybrid_fixed_om_cost_kw = 103
     elif site_location == 'Site 4':
         h2_storage_cost_USDperkg = 54
         balancing_area = 'p9'
         hybrid_fixed_om_cost_kw = 83
     
     # Format renewable system cost for RODeO
     hybrid_installed_cost = hybrid_plant.grid.total_installed_cost
     hybrid_installed_cost_perMW = hybrid_installed_cost/system_rating_mw  
     
     #Capital costs provide by Hydrogen Production Cost From PEM Electrolysis - 2019 (HFTO Program Record)
     mechanical_bop_cost = 36  #[$/kW] for a compressor
     electrical_bop_cost = 82  #[$/kW] for a rectifier

     # Installed capital cost
     stack_installation_factor = 12/100  #[%] for stack cost 
     elec_installation_factor = 12/100   #[%] and electrical BOP 
     #mechanical BOP install cost = 0%

     # Indirect capital cost as a percentage of installed capital cost
     site_prep = 2/100   #[%]
     engineering_design = 10/100 #[%]
     project_contingency = 15/100 #[%]
     permitting = 15/100     #[%]
     land = 250000   #[$]

     stack_replacment_cost = 15/100  #[% of installed capital cost]
     fixed_OM = 0.24     #[$/kg H2]


     total_direct_electrolyzer_cost_kw = (electrolyzer_capex_kw * (1+stack_installation_factor)) \
         + mechanical_bop_cost + (electrical_bop_cost*(1+elec_installation_factor))

     # Assign CapEx for electrolyzer from capacity based installed CapEx
     electrolyzer_total_installed_capex = total_direct_electrolyzer_cost_kw*electrolyzer_size_mw*1000

     # Add indirect capital costs
     electrolyzer_total_capital_cost = electrolyzer_total_installed_capex+((site_prep+engineering_design+project_contingency+permitting)\
         *electrolyzer_total_installed_capex) + land
         
     electrolyzer_capex_kw = electrolyzer_total_capital_cost/1000/1000
     
     # O&M costs
     # https://www.sciencedirect.com/science/article/pii/S2542435121003068
     fixed_OM = 12.8 #[$/kWh-y]
     property_tax_insurance = 1.5/100    #[% of Cap/y]
     variable_OM = 1.30  #[$/MWh]

     elec_cf = sum(energy_to_electrolyzer)/(electrolyzer_size_mw*1000*8760)

     # Amortized refurbishment expense [$/MWh]
     amortized_refurbish_cost = (total_direct_electrolyzer_cost_kw*stack_replacment_cost)\
             *max(((useful_life*8760*elec_cf)/time_between_replacement-1),0)/useful_life/8760/elec_cf*1000

     total_variable_OM = variable_OM+amortized_refurbish_cost
     
     # Define electrolyzer capex, fixed opex, and energy consumption (if not pulling from external data)
     electrolyzer_capex_USD_per_MW = electrolyzer_capex_kw*1000#1542000 # Eventually get from input loop
     electrolyzer_fixed_opex_USD_per_MW_year = fixed_OM*1000
     electrolyzer_energy_kWh_per_kg = 55.5 # Eventually get from input loop
     
     # Define dealination conversion factors
     desal_energy_conversion_factor_kWh_per_m3_water = 4 # kWh per m3-H2O
     m3_water_per_kg_h2 = 0.01 # m3-H2O per kg-H2
     
     # Calculate desalination energy requirement per kg of produced hydrogen
     desal_energy_kWh_per_kg_H2 = m3_water_per_kg_h2*desal_energy_conversion_factor_kWh_per_m3_water
     
     # Calculate desal capex and opex per MW of electrolysis power
     desal_capex_USD_per_MW_of_electrolysis = 32894*(997/3600*1000/electrolyzer_energy_kWh_per_kg*m3_water_per_kg_h2)
     desal_opex_USD_per_MW_of_EC_per_year = 4841*(997/3600*1000/electrolyzer_energy_kWh_per_kg*m3_water_per_kg_h2)
     
     # Incorporate desal cost and efficiency into electrolyzer capex, opex, and energy consumption
     electrolysis_desal_total_capex_per_MW = electrolyzer_capex_USD_per_MW + desal_capex_USD_per_MW_of_electrolysis
     electrolysis_desal_total_opex_per_MW_per_year = electrolyzer_fixed_opex_USD_per_MW_year + desal_opex_USD_per_MW_of_EC_per_year
     electrolysis_desal_total_energy_consumption = electrolyzer_energy_kWh_per_kg + desal_energy_kWh_per_kg_H2
     
     # Convert electrolysis energy consumption into LHV efficiency
     hydrogen_LHV = 120000 #kJ/kg
     eta_LHV = hydrogen_LHV/3600/electrolysis_desal_total_energy_consumption
     
     # Grid connection switfch
     if grid_connected_rodeo == True:
         grid_string = 'gridconnected'
         grid_imports = 1
     else:
         grid_string = 'offgrid'
         grid_imports = 0
         
     # Financial parameters
     inflation_rate = 2.5/100
     equity_percentage = 40/100
     bonus_depreciation = 0/100
     
     # Set hydrogen break even price guess value
     # Could in the future replace with H2OPP or H2A estimates 
     lcoh_guessvalue =50
     # Placeholder for if not doing optimization; may want to move this elsewhere or higher level
     h2_storage_duration = 10
     optimize_storage_duration = 1
     
     # Set up batch file
     dir0 = "..\\RODeO\\"
     dir1 = 'examples\\H2_Analysis\\RODeO_files\\Data_files\\TXT_files\\'
     dirout = output_dir
     
    # txt1 = '"C:\\GAMS\\win64\\24.8\\gams.exe" ..\\RODeO\\Storage_dispatch_SCS license=C:\\GAMS\\win64\\24.8\\gamslice.txt'
     txt1 = gams_locations_rodeo_version[0]
     scenario_name = 'steel_'+str(atb_year)+'_'+ site_location.replace(' ','-') +'_'+turbine_model+'_'+grid_string
     
     scenario_inst = ' --file_name_instance='+scenario_name
     #scenario_name = ' --file_name_instance='+Scenario1
     # demand_prof = ' --product_consumed_inst=' + dem_profile_name
     demand_prof = ' --product_consumed_inst=Product_consumption_flat_hourly_ones'
     load_prof = ' --load_prof_instance=Additional_load_none_hourly'
     ren_prof = ' --ren_prof_instance=Ren_profile\\'+ren_profile_name
     ren_cap = ' --Renewable_MW_instance=1'#+str(system_rating_mw)#'1'
     energy_price = ' --energy_purchase_price_inst=Elec_prices\\Elec_purch_price_WS_MWh_MC95by35_'+str(balancing_area)+'_'+str(atb_year)
     #energy_price = ' --energy_purchase_price_inst=Netload_'+str(i1)+' --energy_sale_price_inst=Netload_'+str(i1)
     #max_input_entry = ' --Max_input_prof_inst=Max_input_cap_'+str(i1)
     capacity_values = ' --input_cap_instance=1'#+str(system_rating_mw)#+str(storage_power_increment)#+' --output_cap_instance='+str(storage_power_increment)
     efficiency = ' --input_efficiency_inst='+str(round(eta_LHV,4))#'0.611'#+str(round(math.sqrt(RTE[i1-1]),6))#+' --output_efficiency_inst='+str(round(math.sqrt(RTE[i1-1]),6))

     wacc_instance = ' --wacc_instance=0.07'                    
     equity_perc_inst = ' --perc_equity_instance=' + str(round(equity_percentage,4))
     ror_inst = ' --ror_instance=0.489'
     roe_inst = ' --roe_instance=0.104'
     debt_interest_inst = ' --debt_interest_instance=0.0481'
     cftr_inst = ' --cftr_instance=0.27'
     inflation_inst = ' --inflation_inst=' + str(round(inflation_rate,3))
     bonus_dep_frac_inst = ' --bonus_deprec_instance=' + str(round(bonus_depreciation,1))
     
     storage_init_inst = ' --storage_init_instance=0.5'
     storage_final_inst = ' --storage_final_instance=0.5'
     max_storage_dur_inst= ' --max_stor_disch_inst=1000'
     
     storage_cap = ' --storage_cap_instance='+str(h2_storage_duration)#'1000'#+str(stor_dur[i1-1])
     storage_opt = ' --opt_storage_cap ='+str(optimize_storage_duration)
     out_dir = ' --outdir='+dirout
     in_dir = ' --indir='+dir1
     #out_dir = ' --outdir=C:\\Users\\ereznic2\\Documents\\Projects\\SCS_CRADA\\RODeO\\Projects\\SCS\\Output_GSA_test'
     #in_dir = ' --indir=C:\\Users\\ereznic2\\Documents\\Projects\\SCS_CRADA\\RODeO\\Projects\\SCS\\Data_files\\TXT_files'
     product_price_inst = ' --Product_price_instance='+str(lcoh_guessvalue)
     device_ren_inst = ' --devices_ren_instance=1'
     input_cap_inst = ' --input_cap_instance=1'#+str(system_rating_mw)#1'
     allow_import_inst = ' --allow_import_instance='+str(grid_imports)
     input_LSL_inst = ' --input_LSL_instance=0'
     ren_capcost = ' --renew_cap_cost_inst='+str(round(hybrid_installed_cost_perMW))#'1230000'
     input_capcost= ' --input_cap_cost_inst='+str(round(electrolysis_desal_total_capex_per_MW))#'1542000'
     prodstor_capcost = ' --ProdStor_cap_cost_inst='+str(round(h2_storage_cost_USDperkg))#'26'
     ren_fom = ' --renew_FOM_cost_inst='+str(1000*hybrid_fixed_om_cost_kw)
     input_fom = ' --input_FOM_cost_inst='+str(round(electrolysis_desal_total_opex_per_MW_per_year))#'34926.3'
     ren_vom = ' --renew_VOM_cost_inst=0'
     input_vom = ' --input_VOM_cost_inst='+str(round(total_variable_OM,2))
     
     # Create batch file
     batch_string = txt1+scenario_inst+demand_prof+ren_prof+load_prof+energy_price+capacity_values+efficiency+storage_cap+storage_opt+ren_cap+out_dir+in_dir\
                  + product_price_inst+device_ren_inst+input_cap_inst+allow_import_inst+input_LSL_inst+ren_capcost+input_capcost+prodstor_capcost+ren_fom+input_fom+ren_vom+input_vom\
                  + wacc_instance+equity_perc_inst+ror_inst+roe_inst+debt_interest_inst+cftr_inst+inflation_inst+bonus_dep_frac_inst\
                  + storage_init_inst+storage_final_inst  +max_storage_dur_inst                               
         
     dir_batch = 'examples\\H2_Analysis\\RODeO_files\\Batch_files\\'
     with open(os.path.join(dir_batch, 'Output_batch_'+scenario_name + '.bat'), 'w') as OPATH:
         OPATH.writelines([batch_string,'\n','pause']) # Remove '\n' and 'pause' if not trouble shooting
         #OPATH.writelines([batch_string]) # Remove '\n' and 'pause' if not trouble shooting
                  
                  
     # summary_file_path = dirout + '\\Storage_dispatch_summary_'+scenario_name + '.csv'
     # inputs_file_path = dirout + '\\Storage_dispatch_inputs_'+scenario_name + '.csv'
     # results_file_path = dirout + '\\Storage_dispatch_results_'+scenario_name + '.csv'
     
     # # Delete currently existing scenario so that RODeO can replace it
     # if os.path.exists(summary_file_path):
     #     os.remove(summary_file_path)
         
     # if os.path.exists(inputs_file_path):
     #     os.remove(inputs_file_path)
         
     # if os.path.exists(results_file_path):
     #     os.remove(results_file_path)
     
     # Run batch file
     os.startfile(r'examples\\H2_Analysis\\RODeO_files\\Batch_files\\Output_batch_'+scenario_name + '.bat')
     
     # start_time = time.time()
     
     # # Make sure GAMS has finished and printed results before continuing
     # while os.path.exists(summary_file_path)==False:
     #     time_delta = time.time() - start_time
     #     print('Waiting for RODeO... Elapsed time: ' + str(round(time_delta))+' s')
     #     time.sleep(20)
         
     # # Make sure the inputs file has been written too
     # while os.path.exists(inputs_file_path)==False:
     #     time_delta = time.time() - start_time
     #     print('Waiting for RODeO... Elapsed time: ' + str(round(time_delta))+' s')
     #     time.sleep(5)
     
     # # Make sure the results file has been written too
     # while os.path.exists(results_file_path)==False:
     #     time_delta = time.time() - start_time
     #     print('Waiting for RODeO... Elapsed time: ' + str(round(time_delta))+' s')
     #     time.sleep(5)
     
     # # Is this really the best way to do this? Probably not, but until we figure out
     # # how to use the Python API for GAMS, this is the quickest and easiest way to do it
     # end_time = time.time()
     # print('RoDeO finished! Total elapsed time: ' + str(round(end_time-start_time))+' s')
     
     return(scenario_name)