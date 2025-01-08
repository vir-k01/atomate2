from atomate2.lammps.sets.core import LammpsNVTSet, LammpsNPTSet, LammpsMinimizeSet

def test_LammpsNVTSet():
    nvt = LammpsNVTSet(timestep=0.005, thermostat='langevin')
    assert nvt.ensemble.value == 'nvt'
    assert nvt.settings.settings['thermostat'] == 'langevin'
    assert nvt.settings.settings['timestep'] == 0.005
    
def test_minimize_set():
    mini = LammpsMinimizeSet()
    assert mini.settings.settings['ensemble'] == 'minimize'