from monty.serialization import loadfn
import os
import json

try:
    from openff.interchange import Interchange
except ImportError:

    class Interchange:  # type: ignore[no-redef]
        """Dummy class for failed imports of Interchange."""

        def model_validate(self, _: str) -> None:
            """Parse raw is the first method called on the Interchange object."""
            raise ImportError(
                "openff-interchange must be installed for OpenMM makers to"
                "to support OpenFF Interchange objects."
            )

settings_dir = os.path.dirname(os.path.abspath(__file__))
_BASE_LAMMPS_SETTINGS = loadfn(os.path.join(settings_dir,'BASE_LAMMPS_SETTINGS.json'))


class LammpsInterchange(Interchange):
    """
    A subclass of Interchange that adds a method to convert the object to a dictionary.
    """
    
    @classmethod
    def from_interchange(cls, interchange: Interchange) -> None:
        """
        Load an Interchange object.
        """
        
        return cls(topology=interchange.topology,
                  collections=interchange.collections,
                  box=interchange.box,
                  positions=interchange.positions,
                  velocities=interchange.velocities,
                  mdconfig=interchange.mdconfig
                  )
    
    def as_dict(self) -> dict:
        """
        Convert the Interchange object to a dictionary.
        """
        return json.loads(self.json())
    
    @classmethod
    def from_dict(cls, d: dict) -> "LammpsInterchange":
        """
        Load an Interchange object from a dictionary.
        """
        return cls(**d)

def update_settings(settings : dict = None, **kwargs) -> dict:
    """
    Update the settings for the LAMMPS input file. 
    """
    
    base_settings = _BASE_LAMMPS_SETTINGS.copy()

    if settings is None:
        settings = base_settings
    
    settings  = settings.copy()
    
    for k in base_settings.keys():
        if k not in settings.keys():
            if k not in kwargs.keys():
                settings.update({k: base_settings.get(k)})
            else:
                settings.update({k: kwargs.get(k)})
    
    return settings


def process_ensemble_conditions(settings : dict) -> dict:
    """
    Process the ensemble conditions for the LAMMPS input file.
    """
    ensemble = settings.get('ensemble', 'nve')
    for k in ["nve", "nvt", "npt"]:
        settings.update({f'{k}_flag': '#'})
        
    if ensemble == 'nvt':
        if settings.get('thermostat') == 'langevin':
            settings.update({'nve_flag': 'fix', 'thermseed': settings.get('seed', 0)})
            
        else: 
            settings.update({'thermostat': 'nvt temp'})
    
        
    if ensemble == 'npt':
        if settings.get('barostat') == 'berendsen':
            settings.update({'nve_flag': 'fix', 'barostat': 'press/berendsen'})
        else:
            settings.update({'barostat': 'npt temp'})
    
    if ensemble == 'nph':
        settings.update({'npt_flag': 'fix', 'barostat': 'nph'})
    
    settings.update({f'{ensemble}_flag': 'fix'}) if ensemble in ["nve", "nvt", "npt"] else None
    return settings