"""Flow for MP absorption calculations."""

from dataclasses import dataclass, field
from pathlib import Path

from jobflow import Flow, Maker
from pymatgen.core.structure import Structure

from atomate2.vasp.jobs.absorption import IPAMaker, RPAMaker
from atomate2.vasp.jobs.base import BaseVaspMaker
from atomate2.vasp.jobs.mp import MP24StaticMaker, MPMetaGGARelaxMaker


@dataclass
class MPAbsorptionMaker(Maker):
    """
    MP Absorption workflow.

    Default WF:
        1. PBEsol pre-relaxation
        2. r2SCAN relax (for double relaxation)
        3. PBE Static Calculation
        4. NSCF Optics Calculation

    Parameters
    ----------
    name : str
        Name of the flows produced by this maker.
    relax_maker (optional) : .BaseVaspMaker | None
        Maker to generate the first relaxation.
    static_maker : .BaseVaspMaker
        Maker to generate a static calculation.
    bs_maker : .BaseVaspMaker
        Maker to generate the bandstructure calculation(s)
    bandstructure_type : str #probs need to remove
        The type of band structure to generate. Options are "line", "uniform" or "both".
    """

    name: str = "MP Absorption maker"
    relax_maker: BaseVaspMaker | None = field(default_factory=MPMetaGGARelaxMaker)

    static_maker: BaseVaspMaker = field(
        default_factory=lambda: MP24StaticMaker(
            copy_vasp_kwargs={"additional_vasp_files": ("WAVECAR", "CHGCAR")}
        )
    )
    ipa_maker: BaseVaspMaker = field(default_factory=IPAMaker)
    rpa_maker: BaseVaspMaker = field(default_factory=RPAMaker)

    def make(self, structure: Structure, prev_dir: str | Path | None = None) -> Flow:
        """
        Create an MP-compatible absorption flow.

        Parameters
        ----------
        structure : Structure
            A pymatgen structure object.
        prev_dir : str or Path or None
            A previous VASP calculation directory to copy output files from.

        Returns
        -------
        Flow
            An MP-compatible absorption flow.
        """
        jobs = []
        dir_name = prev_dir
        if self.relax_maker:
            relax_job = self.relax_maker.make(structure, prev_dir=prev_dir)
            structure = relax_job.output.structure
            dir_name = relax_job.output.dir_name
            jobs += [relax_job]

        # Manually chain Static -> Optics (IPA) -> RPA to avoid Flow ownership issues
        static_job = self.static_maker.make(structure, prev_dir=dir_name)
        jobs.append(static_job)

        ipa_job = self.ipa_maker.make(
            structure=static_job.output.structure, prev_dir=static_job.output.dir_name
        )
        jobs.append(ipa_job)

        rpa_job = self.rpa_maker.make(
            structure=ipa_job.output.structure, prev_dir=ipa_job.output.dir_name
        )
        jobs.append(rpa_job)

        return Flow(jobs=jobs, output=rpa_job.output, name=self.name)
