"""
Input sets for LAMMPS, initially developed inside
pymatgen by Ryan Kingsbury & Guillaume Brunin.
"""

import logging
import warnings
import os
import numpy as np
from pymatgen.io.lammps.generators import LammpsInputSet, InputGenerator
from pymatgen.io.lammps.data import LammpsData, CombinedData
from pymatgen.core.structure import Structure
from pymatgen.io.lammps.inputs import LammpsInputFile
from typing import Literal, Sequence
from pathlib import Path
from monty.json import MSONable

from atomate2.lammps.sets.utils import LammpsInterchange

from dataclasses import dataclass, field

logger = logging.getLogger(__name__)
template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

_BASE_LAMMPS_SETTINGS = {'units': 'metal',
                         'atom_style': 'atomic',
                         'dimension': 3,
                         'boundary': 'p p p',
                         'pair_style': 'lj/cut 10.0',
                         'thermo': 100,
                         'start_temp': 300,
                         'end_temp': 300,
                         'start_pressure': 0,
                         'end_pressure': 0,
                         'timestep': 0.001,
                         'friction': 0.1,
                         'log_interval': 100,
                         'traj_interval': 100,
                         'ensemble': 'nvt',
                         'thermostat': 'nose-hoover',
                         'barostat': 'nose-hoover',
                         'nsteps': 1000,
                         'tol': 1e-6,
                         }

_STAGE_TO_KEYS = {'Initialization': ['units', 'atom_style', 'dimension', 'boundary', 'pair_style', 'bond_style', 'angle_style', 'dihedral_style', 'improper_style'],
                  'AtomDefinition': ['read_data', 'read_restart'],
                  'ForceField': ['include'],
                  'AdditionalData': ['read_data'],
                  'Velocities': ['velocity', 'neigh_modify'],
                  'Ensemble': ['fix'],
                  'Outputs': ['thermo', 'dump', 'dump_modify'],
                  'Actions': ['timestep', 'run']} 


class LammpsInputSettings(MSONable):
    """
    Settings object for LAMMPS input files. 
    Note: default settings are given in the _BASE_LAMMPS_SETTINGS object in 'metal' units for reference.
    
    Keys that can be passed as input to the SETTINGS object:
    atom_style : str 
        Atom style for the LAMMPS input file.
    dimension : int
        Dimension of the simulation.
    boundary : str
        Boundary conditions for the simulation. Defualts to PBCs in all directions.
    ensemble : MDEnsemble | str
        Ensemble for the simulation. Defaults to NVT.
    temperature : float | Sequence | np.ndarray | None
        Temperature for the simulation. Defaults to 300 K. If a sequence is provided, 
        the first value is the starting temperature and the last value is the final temperature, 
        with a linear interpolation during the simulation.
    pressure : float | Sequence | np.ndarray | None
        Pressure for the simulation. Defaults to 0 bar. If a sequence is provided, 
        the first value is the starting pressure and the last value is the final pressure, 
        with a linear interpolation during the simulation. A non-zero pressure requires a barostat.
        A 2D pressure input (e.g. [[0, 100, 0], [100, 100, 0]]) will be interpreted as anisotropic pressure, 
        with the first list being the starting pressure and the second list being the final pressure.
    units : str
        Units for the simulation. Defaults to metal.
    nsteps : int
        Number of steps for the simulation. Defaults to 1000.
    timestep : float
        Timestep for the simulation. Defaults to 0.001 (=ps in metal units).
    log_interval : int
        Interval for logging the simulation. Defaults to 100.
    traj_interval : int
        Interval for writing the trajectory. Defaults to 100.
    thermostat : Literal["langevin", "nose-hoover"]
        Thermostat for the simulation. Defaults to nose-hoover.
    barostat : Literal["berendsen", "nose-hoover"]
        Barostat for the simulation. Defaults to nose-hoover.
    friction : float
        Friction coefficient for the thermostat and barostat. Defaults to 100*timestep.
    tol : float
        Tolerance for minimization jobs, done under constant pressure. Defaults to 1e-6.
    """
    settings = {} #raw strings given as input by the user/maker
    input_settings = {} #formatted settings for the LAMMPS input i/o functions in pmg
    
    def __init__(self, settings : dict):  
              
        if settings.get('temperature', None):
            if isinstance(settings['temperature'], (int, float)):
                settings.update({'start_temp': settings['temperature'], 'end_temp': settings['temperature']})
            if isinstance(settings['temperature'], (list, np.ndarray)):
                settings.update({'start_temp': settings['temperature'][0], 'end_temp': settings['temperature'][-1]})
            settings.pop('temperature')
        
        if settings.get('pressure', None):
            if isinstance(settings['pressure'], (int, float)):
                settings.update({'start_pressure': settings['pressure'], 'end_pressure': settings['pressure']})
            if isinstance(settings['pressure'], (list, np.ndarray)):
                settings.update({'start_pressure': settings['pressure'][0], 'end_pressure': settings['pressure'][-1]})
            settings.pop('pressure')
        
        for k, v in _BASE_LAMMPS_SETTINGS.items():
            if k not in settings.keys():
                settings.update({k: v})
        
        if self.settings.get('friction', 0.1) < settings.get('timestep', 0.001)/10:
            warnings.warn("Friction coefficient is too low, setting equal to timestep.")
            settings.update({'friction': settings['timestep']})
        
        for k, v in settings.items():
            setattr(self, k, v)
        
        self.settings = settings
        self.input_settings = self.get_formatted_settings()
        
    def as_dict(self):
        return self.settings
    
    @classmethod
    def from_dict(cls, d):
        return cls(d)

    def get_formatted_settings(self) -> dict:
        
        updates = self.settings.copy()
        input_settings = {k: {} for k in _STAGE_TO_KEYS.keys()}
        for stage, stage_data in input_settings.items():
            if stage in ['Initialization', 'AtomDefinition', 'ForceField', 'AdditionalData', 'Actions']:
                stage_data.update({k: v for k, v in updates.items() if k in _STAGE_TO_KEYS[stage]})
                    
            if stage in ['Velocities']:
                if 'start_temp' in updates.keys():
                    stage_data.update({'velocity': f'all create {updates["start_temp"]} 42 mom yes rot yes dist gaussian'})
            
            if stage in ['Ensemble']:
                updates.update({k : _BASE_LAMMPS_SETTINGS[k] for k in ['start_temp', 'end_temp', 'friction', 'ensemble', 'start_pressure', 'end_pressure', 'thermostat', 'barostat'] if k not in updates.keys()})
                if 'fix' not in stage_data.keys():
                    pressure_symmetry = 'aniso' if isinstance(updates['start_pressure'], (list, np.ndarray)) or isinstance(updates['end_pressure'], (list, np.ndarray)) else 'iso'
                    if updates['ensemble'] == 'nve':
                        stage_data.update({'fix': f'1 all nve'})
                    if updates['ensemble'] == 'nvt':
                        if updates['thermostat'] == 'nose-hoover':
                            stage_data.update({'fix': f'1 all nvt temp {updates["start_temp"]} {updates["end_temp"]} {updates["friction"]}'})
                        if updates['thermostat'] == 'langevin':
                            stage_data.update({'fix': [f'1 all nve',
                                f'2 all langevin {updates["start_temp"]} {updates["end_temp"]} {updates["friction"]} 42']})
                    if updates['ensemble'] == 'npt':
                        if updates['barostat'] == 'nose-hoover':
                            stage_data.update({'fix': f'1 all npt temp {updates["start_temp"]} {updates["end_temp"]} {updates["friction"]} {pressure_symmetry} {updates["start_pressure"]} {updates["end_pressure"]} {updates["friction"]}'})
                        if updates['barostat'] == 'berendsen':
                            stage_data.update({'fix': [f'1 all nve',
                                f'2 all press/berendsen {pressure_symmetry} {updates["start_pressure"]} {updates["end_pressure"]} {updates["friction"]}']})
                        if updates['barostat'] == 'langevin':
                            stage_data.update({'fix': [f'1 all nve',
                                f'2 all press/langevin {pressure_symmetry} {updates["start_pressure"]} {updates["end_pressure"]} {updates["friction"]} temp {updates["start_temp"]} {updates["end_temp"]} 42']})
                    if updates['ensemble'] == 'nph':
                        stage_data.update({'fix': [f'1 all nve',
                            f'2 all nph {updates["start_temp"]} {updates["end_temp"]} {updates["friction"]} {pressure_symmetry} {updates["start_pressure"]} {updates["end_pressure"]} {updates["friction"]}']})
                    if updates['ensemble'] == 'minimize':
                        stage_data.update({'min_style': 'cg',
                            'fix': f'1 all box/relax {pressure_symmetry} {updates["start_pressure"]} vmax 0.001'})
                        
                
            if stage in ['Outputs']:
                if 'log_interval' in updates.keys():
                    stage_data.update({'thermo': updates['log_interval']})
                if 'traj_interval' in updates.keys():
                    stage_data.update({'dump': f'd1 all custom {updates["traj_interval"]} traj.dump id element x y z vx vy vz fx fy fz'})
            
            if stage == 'Actions':
                if 'nsteps' in updates.keys():
                    stage_data.update({'run': updates['nsteps']})
        
        if updates.get('ensemble', None) == 'minimize':
            input_settings.pop('Velocities')
            input_settings['Actions'] = {'minimize': f'{updates["tol"]} {updates["tol"]} {updates["nsteps"]} 100000',
                                         'write_restart': 'minimized.restart'}
            
        return input_settings
             
    @classmethod
    def apply_updates(cls, updates) -> "LammpsInputSettings":    
        
        updated_settings = cls.settings.copy()
        for k, v in updates.items():
            updated_settings.update({k: v})
        
        return LammpsInputSettings(updated_settings)
    
    def _validate_settings(self):
        """
        Validate the settings for the LAMMPS input file.
        """
        pass #implement this with ENUMS for the settings

@dataclass       
class BaseLammpsSetGenerator(InputGenerator):
    """
    Base class for generating LAMMPS input sets.
    
    Args:
        inputfile : LammpsInputFile | str | Path
            Premade input file for the LAMMPS simulation. Useful if the user wants to use a custom input file (to make use of Lammps' flexibility).
            Default format based on the md.template file in the templates directory.
        settings : dict | LammpsInputSettings
            Settings for the LAMMPS simulation. Default settings are given in the _BASE_LAMMPS_SETTINGS object in 'metal' units for reference.
        calc_type : str
            Type of calculation to be performed by LAMMPS.
        keep_stages : bool
            Whether to keep the stages of the input file or not. Default is True.
        override_updates : bool
            Whether to override the updates to the input file, i.e., keep the input file as is. Default is False.
    """
    inputfile : LammpsInputFile | str = field(default=None)
    settings : dict | LammpsInputSettings = field(default_factory={})
    calc_type : str = field(default="lammps")
    keep_stages : bool = field(default=True)
    override_updates : bool = field(default=False)
    
    def __init__(self,
                 inputfile : LammpsInputFile | str | Path = None,
                 settings : dict | LammpsInputSettings = {},
                 **kwargs):
        
        settings.update({k:v for k, v in kwargs.items() if k in _BASE_LAMMPS_SETTINGS.keys()})
        #print({k:v for k, v in kwargs.items() if k in _BASE_LAMMPS_SETTINGS.keys()})
        
        if isinstance(settings, dict):
            self.settings = LammpsInputSettings(settings) if settings else LammpsInputSettings(_BASE_LAMMPS_SETTINGS)
         
        if isinstance(inputfile, Path):
            self.inputfile = LammpsInputFile.from_file(inputfile, keep_stages=self.keep_stages)
        if isinstance(inputfile, str):
            self.inputfile = LammpsInputFile.from_str(inputfile, keep_stages=self.keep_stages)
        if inputfile is None:
            self.inputfile = LammpsInputFile.from_file(os.path.join(template_dir, "md.template"), keep_stages=self.keep_stages)
    
    def update_settings(self, updates : dict) -> "BaseLammpsSetGenerator":
        """
        Update the settings for the LAMMPS input file.
        Args:
            updates : dict
                Dictionary containing the settings to update.
        """
        present_settings = self.settings.settings
        for k, v in updates.items():
            present_settings.update({k: v})
        self.settings = LammpsInputSettings.apply_updates(present_settings)
        return self
                        
    def get_input_set(self, 
                      data : Structure | LammpsData | CombinedData | LammpsInterchange, 
                      force_field : str = None,
                      additional_data : LammpsData | CombinedData | None = None, 
                      **kwargs) -> LammpsInputSet:
        """
        Generate a LAMMPS input set.
        Args:
            structure : Structure | LammpsData
                Structure or LammpsData object for the simulation.
            **kwargs : dict
                Additional keyword arguments to pass to the InputSet from pmg.      
        """
        input_settings = self.settings.input_settings
        atom_style = input_settings.get('Initialization').get('atom_style', "full")
        species = ' '.join(set([s.symbol for s in data.species])) if isinstance(data, Structure) else ''

        if isinstance(data, Path):
            data = LammpsData.from_file(data, atom_style=atom_style)
        if isinstance(data, str):
            data = LammpsData.from_str(data, atom_style=atom_style)
        if isinstance(data, Structure):
            data = LammpsData.from_structure(data, atom_style=atom_style)
            warnings.warn("Structure provided, converting to LammpsData object.")
        if isinstance(data, LammpsInterchange):
            warnings.warn("Interchange is experimental and may not work as expected. Use with caution. Ensure FF units are consistent with LAMMPS.")
            #write unit convertor here
            data.to_lammps_datafile("interchange_data.lmp")
            data = LammpsData.from_file("interchange_data.lmp", atom_style=atom_style)
            #validate data here: ff coeffs style, atom_style, etc. have to be updated into the input_set_generator.settings'''
            
        if not data.force_field and not force_field:
            raise ValueError("Force field not specified!")
        
        if species:
            input_settings['Outputs'].update({"dump_modify": f"d1 sort id element {species}"})
        
        write_data = {}
        if additional_data:
            write_data.update({"extra.data": additional_data})
        else:
            self.inputfile.remove_stage(stage_name="AdditionalData")
        
        if force_field:
            write_data.update({"forcefield.lammps": force_field})
        else:
            self.inputfile.remove_stage(stage_name="ForceField") #implies FF is in the datafile
            
            
        if self.override_updates:
            return LammpsInputSet(
                inputfile=self.inputfile,
                data=data,
                calc_type=self.calc_type,
                additional_data=additional_data,
                **kwargs
            )
        
        if self.inputfile.contains_command(command='fix'):
            self.inputfile.remove_command(command='fix', stage_name="Ensemble", remove_empty_stages=False)
        
        
        for stage, stage_data in input_settings.items():
            for key, value in stage_data.items():
                if self.inputfile.contains_command(command=key, stage_name=stage) and key not in ['fix']:
                    self.inputfile.set_args(stage_name=stage, command=key, argument=str(value))                        
                else:
                    value = [value] if not isinstance(value, list) else value
                    for val in value:
                        self.inputfile.add_commands(stage_name=stage, commands={key: str(val)})
        '''try:
            fix_vals = self.inputfile.get_args(stage_name="Ensemble", command='fix')
            if isinstance(fix_vals, list):
                for i in range(len(fix_vals)):
                    for j in range(len(fix_vals) - 1, i, -1):
                        if fix_vals[i] == fix_vals[j]:
                            fix_vals.pop(j)
                self.inputfile.remove_command(command='fix', stage_name="Ensemble", remove_empty_stages=False)
                #remove duplicates if any
                for fix in fix_vals:
                    self.inputfile.add_commands(stage_name="Ensemble", commands={'fix': fix})
        except KeyError:
            logger.error("No fix command found in Ensemble stage!")
            raise KeyError'''
                            
        
        return LammpsInputSet(
            inputfile=self.inputfile,
            data=data,
            calc_type=self.calc_type,
            additional_data=write_data,
            **kwargs
        )
        
        
        
        
        
        
            
        
            
            
            
        
        
