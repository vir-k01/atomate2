"""Jobs for MP absorption calculations."""

from dataclasses import dataclass, field

from pymatgen.io.vasp.sets import MPAbsorptionSet, VaspInputGenerator

from atomate2.vasp.jobs.base import BaseVaspMaker


@dataclass
class IPAMaker(BaseVaspMaker):
    """Maker for IPA calculation."""

    name: str = "IPA maker"
    input_set_generator: VaspInputGenerator = field(
        default_factory=lambda: MPAbsorptionSet(mode="IPA")
    )
    copy_vasp_kwargs: dict = field(
        default_factory=lambda: {"additional_vasp_files": ("WAVECAR", "CHGCAR")}
    )


@dataclass
class RPAMaker(BaseVaspMaker):
    """Maker for RPA calculation."""

    name: str = "RPA maker"
    input_set_generator: VaspInputGenerator = field(
        default_factory=lambda: MPAbsorptionSet(mode="RPA")
    )
    copy_vasp_kwargs: dict = field(
        default_factory=lambda: {"additional_vasp_files": ("WAVECAR", "WAVEDER")}
    )
