import pytest
import os
from jobflow import run_locally
import pandas as pd

from atomate2.lammps.jobs.core import (
    LammpsNVTMaker,
    LammpsNPTMaker,
    MinimizationMaker,
)
from atomate2.lammps.sets.core import LammpsNVTSet
from atomate2.lammps.schemas.task import LammpsTaskDocument
from atomate2.lammps.schemas.task import StoreTrajectoryOption

def test_nvt_maker(si_structure, tmp_path, test_si_force_field, mock_lammps):
    ref_paths = {'nvt_test': 'nvt_test'}
    
    fake_run_lammps_kwargs = {}
    
    mock_lammps(ref_paths, fake_run_lammps_kwargs=fake_run_lammps_kwargs)
    
    generator = LammpsNVTSet(temperature=[300, 1000], nsteps=100000, timestep=0.001, friction=0.1, log_interval=500)
    maker = LammpsNVTMaker(force_field=test_si_force_field, input_set_generator=generator, task_document_kwargs={'store_trajectory': StoreTrajectoryOption.PARTIAL})
    maker.name = 'nvt_test'
    
    assert maker.input_set_generator.settings.settings['ensemble'] == 'nvt'
    
    supercell = si_structure.make_supercell([5, 5, 5])
    job = maker.make(supercell)
    
    os.chdir(tmp_path)
    responses = run_locally(job, create_folders=True, ensure_success=True)
    os.chdir(os.getcwd())
    output = responses[job.uuid][1].output
    
    assert isinstance(output, LammpsTaskDocument)
    assert output.structure.volume == pytest.approx(supercell.volume)
    assert len(list(output.dump_files.keys())) == 1
    dump_key = list(output.dump_files.keys())[0]
    assert dump_key.endswith('.dump')
    assert isinstance(output.dump_files[dump_key], str)
    
def test_npt_maker(si_structure, tmp_path, test_si_force_field, mock_lammps):
    
    ref_paths = {'npt_test': 'npt_test'}
    
    fake_run_lammps_kwargs = {}
    
    mock_lammps(ref_paths, fake_run_lammps_kwargs=fake_run_lammps_kwargs)
    
    maker = LammpsNPTMaker(force_field=test_si_force_field)
    maker.name = 'npt_test'
    job = maker.make(si_structure.make_supercell([5, 5, 5]))

    os.chdir(tmp_path)
    responses = run_locally(job, create_folders=True, ensure_success=True)
    os.chdir(os.getcwd())
    output = responses[job.uuid][1].output
    
    assert isinstance(output, LammpsTaskDocument)
    assert len(output.dump_files.keys()) == 1
    dump_key = list(output.dump_files.keys())[0]
    assert dump_key.endswith('.dump')
    assert isinstance(output.dump_files[dump_key], str)
            
def test_minimization_maker(si_structure, tmp_path, test_si_force_field, mock_lammps):
    
    ref_paths = {'min_test': 'min_test'}
    
    fake_run_lammps_kwargs = {}
    
    mock_lammps(ref_paths, fake_run_lammps_kwargs=fake_run_lammps_kwargs)
    
    maker = MinimizationMaker(force_field=test_si_force_field)
    maker.name = 'min_test'
    supercell = si_structure.make_supercell([5, 5, 5])
    job = maker.make(supercell)
    
    os.chdir(tmp_path)
    responses = run_locally(job, create_folders=True, ensure_success=True)
    os.chdir(os.getcwd())
    output = responses[job.uuid][1].output
    
    assert isinstance(output, LammpsTaskDocument)
    assert len(output.dump_files.keys()) == 1
    dump_key = list(output.dump_files.keys())[0]
    assert dump_key.endswith('.dump')
    assert isinstance(output.dump_files[dump_key], str)