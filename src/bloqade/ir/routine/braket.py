from collections import OrderedDict
from dataclasses import dataclass
from typing import Optional, Tuple
from numbers import Real

from bloqade.ir.routine.base import RoutineBase
from bloqade.submission.braket import BraketBackend
from bloqade.task.batch import LocalBatch, RemoteBatch
from bloqade.task.braket_simulator import BraketEmulatorTask
from bloqade.task.braket import BraketTask


@dataclass(frozen=True)
class BraketServiceOptions(RoutineBase):
    def aquila(self) -> "BraketHardwareRoutine":
        backend = BraketBackend(
            device_arn="arn:aws:braket:us-east-1::device/qpu/quera/Aquila"
        )
        return BraketHardwareRoutine(source=self.source, backend=backend)

    def local_emulator(self):
        return BraketLocalEmulatorRoutine(source=self.source)


@dataclass(frozen=True)
class BraketHardwareRoutine(RoutineBase):
    backend: BraketBackend

    def compile(
        self,
        shots: int,
        args: Tuple[Real, ...] = (),
        name: Optional[str] = None,
    ) -> RemoteBatch:
        """
        Compile to a RemoteBatch, which contain
            Braket backend specific tasks.

        Args:
            shots (int): number of shots
            args (Tuple): additional arguments
            name (str): custom name of the batch

        Return:
            RemoteBatch

        """

        ## fall passes here ###
        from bloqade.codegen.common.assign_variables import AssignAnalogCircuit
        from bloqade.codegen.common.assignment_scan import AssignmentScan
        from bloqade.codegen.hardware.quera import QuEraCodeGen

        capabilities = self.backend.get_capabilities()

        circuit, params = self.parse_source()
        circuit = AssignAnalogCircuit(params.static_params).visit(circuit)

        tasks = OrderedDict()

        for task_number, batch_params in enumerate(params.batch_assignments(*args)):
            record_params = AssignmentScan(batch_params).emit(circuit)
            final_circuit = AssignAnalogCircuit(record_params).visit(circuit)
            task_ir, parallel_decoder = QuEraCodeGen(capabilities=capabilities).emit(
                shots, final_circuit
            )

            task_ir = task_ir.discretize(capabilities)
            tasks[task_number] = BraketTask(
                None,
                self.backend,
                task_ir,
                batch_params,
                parallel_decoder,
                None,
            )

        batch = RemoteBatch(source=self.source, tasks=tasks, name=name)

        return batch

    def submit(
        self,
        shots: int,
        args: Tuple[Real, ...] = (),
        name: Optional[str] = None,
        shuffle: bool = False,
        **kwargs,
    ) -> RemoteBatch:
        """
        Compile to a RemoteBatch, which contain
        Braket backend specific tasks, and submit to Braket.

        Note:
            This is async.

        Args:
            shots (int): number of shots
            args (Tuple): additional arguments
            name (str): custom name of the batch
            shuffle (bool): shuffle the order of jobs

        Return:
            RemoteBatch

        """

        batch = self.compile(shots, args, name)
        batch._submit(shuffle, **kwargs)
        return batch

    def run(
        self,
        shots: int,
        args: Tuple[Real, ...] = (),
        name: Optional[str] = None,
        shuffle: bool = False,
        **kwargs,
    ) -> RemoteBatch:
        """
        Compile to a RemoteBatch, which contain
        Braket backend specific tasks, submit to Braket,
        and wait until the results are coming back.

        Note:
            This is sync, and will wait until remote results
            finished.

        Args:
            shots (int): number of shots
            args (Tuple): additional arguments
            name (str): custom name of the batch
            shuffle (bool): shuffle the order of jobs

        Return:
            RemoteBatch

        """

        batch = self.submit(shots, args, name, shuffle, **kwargs)
        batch.pull()
        return batch

    def __call__(
        self,
        *args: Tuple[Real, ...],
        shots: int = 1,
        name: Optional[str] = None,
        shuffle: bool = False,
        **kwargs,
    ):
        """
        Compile to a RemoteBatch, which contain
        Braket backend specific tasks, submit to Braket,
        and wait until the results are coming back.

        Note:
            This is sync, and will wait until remote results
            finished.

        Args:
            shots (int): number of shots
            args: additional arguments for flatten variables.
            name (str): custom name of the batch
            shuffle (bool): shuffle the order of jobs

        Return:
            RemoteBatch

        """
        return self.run(shots, args, name, shuffle, **kwargs)


@dataclass(frozen=True)
class BraketLocalEmulatorRoutine(RoutineBase):
    def compile(
        self, shots: int, args: Tuple[Real, ...] = (), name: Optional[str] = None
    ) -> LocalBatch:
        """
        Compile to a LocalBatch, which contain tasks to run on local emulator.

        Args:
            shots (int): number of shots
            args: additional arguments for flatten variables.
            name (str): custom name for the batch

        Return:
            LocalBatch

        """
        ## fall passes here ###
        from bloqade.ir import ParallelRegister
        from bloqade.codegen.common.assign_variables import AssignAnalogCircuit
        from bloqade.codegen.hardware.quera import QuEraCodeGen
        from bloqade.codegen.common.assignment_scan import AssignmentScan
        from bloqade.submission.ir.braket import to_braket_task_ir

        circuit, params = self.parse_source()
        circuit = AssignAnalogCircuit(params.static_params).visit(circuit)

        if isinstance(circuit.register, ParallelRegister):
            raise TypeError(
                "Parallelization of atom arrangements is not supported for "
                "local emulation."
            )

        tasks = OrderedDict()

        for task_number, batch_params in enumerate(params.batch_assignments(*args)):
            record_params = AssignmentScan(batch_params).emit(circuit)
            final_circuit = AssignAnalogCircuit(record_params).visit(circuit)
            quera_task_ir, _ = QuEraCodeGen().emit(shots, final_circuit)

            task_ir = to_braket_task_ir(quera_task_ir)

            tasks[task_number] = BraketEmulatorTask(
                task_ir,
                batch_params,
                None,
            )

        batch = LocalBatch(source=self.source, tasks=tasks, name=name)

        return batch

    def run(
        self,
        shots: int,
        args: Tuple[Real, ...] = (),
        name: Optional[str] = None,
        multiprocessing: bool = False,
        num_workers: Optional[int] = None,
        **kwargs,
    ) -> LocalBatch:
        """
        Compile to a LocalBatch, and run.
        The LocalBatch contain tasks to run on local emulator.

        Note:
            This is sync, and will wait until remote results
            finished.

        Args:
            shots (int): number of shots
            args: additional arguments for flatten variables.
            multiprocessing (bool): enable multi-process
            num_workers (int): number of workers to run the emulator

        Return:
            LocalBatch

        """

        batch = self.compile(shots, args, name)
        batch._run(multiprocessing=multiprocessing, num_workers=num_workers, **kwargs)
        return batch
