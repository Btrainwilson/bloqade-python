from bloqade.builder.start import ProgramStart
from bloqade.builder.coupling import LevelCoupling
from bloqade.builder.field import Field, Rabi
from bloqade.builder.pragmas import (
    Assignable,
    BatchAssignable,
    Parallelizable,
    Flattenable,
)
from bloqade.builder.backend import BackendRoute


class PulseRoute(ProgramStart, LevelCoupling, Field, Rabi):
    pass


class PragmaRoute(
    Assignable, BatchAssignable, Parallelizable, Flattenable, BackendRoute
):
    pass


class WaveformRoute(PulseRoute, PragmaRoute):
    pass
