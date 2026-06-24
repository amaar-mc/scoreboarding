"""Data model for the Scoreboarding simulator.

Three tables track simulation state:
- InstructionStatus: per-instruction cycle stamps for each stage.
- FunctionalUnitStatus: per-FU state (busy, operands, ready flags, etc.).
- RegisterResultStatus: which FU will produce each register's next value.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FunctionalUnit:
    """Declares one physical functional unit available to the processor.

    Args:
        name: Unique identifier, e.g. "Add1", "Mult1", "Load1".
        kind: Operation class this unit handles, e.g. "add", "mult", "load", "div".
        latency: Number of cycles the execute stage occupies (>= 1).
        pipelined: Whether the unit's execute stage is pipelined. An unpipelined
            unit (False) is a structural hazard for its whole lifetime: it stays
            busy from Issue until Write Result, so a same-kind successor cannot
            issue to it until the occupying instruction writes back -- the classic
            CDC 6600 scoreboard behaviour. A pipelined unit (True) accepts a new
            instruction once the occupying instruction has read its operands and
            entered the execute pipeline, so the structural stall is shorter while
            the deep execute pipeline still holds the in-flight result.
    """

    name: str
    kind: str
    latency: int
    pipelined: bool

    def __post_init__(self) -> None:
        if self.latency < 1:
            raise ValueError(
                f"FunctionalUnit '{self.name}': latency must be >= 1, got {self.latency}"
            )


@dataclass
class Instruction:
    """One instruction in the program.

    For single-source instructions (e.g. loads), pass the base register as
    src1 and an empty string "" as src2.

    Args:
        op: Operation name, e.g. "LD", "MULT", "ADD", "SUB", "DIV".
        dest: Destination register, e.g. "F6".
        src1: First source register (or base register for loads).
        src2: Second source register; pass "" if not applicable.
    """

    op: str
    dest: str
    src1: str
    src2: str


@dataclass
class InstructionStatus:
    """Cycle stamps for one instruction's four pipeline stages.

    A value of None means the stage has not yet occurred.
    """

    issue: int | None = None
    read_operands: int | None = None
    execute_complete: int | None = None
    write_result: int | None = None


@dataclass
class FunctionalUnitStatus:
    """Runtime state of one functional unit (the FU status table).

    Fields mirror those in Thornton's original scoreboard description:
    - busy: whether the unit is currently occupied.
    - op: operation being performed.
    - fi: destination register name.
    - fj, fk: source register names.
    - qj, qk: names of FUs that will produce fj/fk (None = already available).
    - rj, rk: True when fj/fk are ready to read (operand available and not yet consumed).
    - execute_start: cycle when execution started (None until started).
    """

    busy: bool = False
    op: str = ""
    fi: str = ""
    fj: str = ""
    fk: str = ""
    qj: str | None = None
    qk: str | None = None
    rj: bool = False
    rk: bool = False
    execute_start: int | None = None

    def reset(self) -> None:
        """Return this FU to the idle state."""
        self.busy = False
        self.op = ""
        self.fi = ""
        self.fj = ""
        self.fk = ""
        self.qj = None
        self.qk = None
        self.rj = False
        self.rk = False
        self.execute_start = None


@dataclass
class CycleSnapshot:
    """Full simulator state at the end of one cycle.

    Useful for step-by-step educational replay.
    """

    cycle: int
    instruction_status: list[InstructionStatus]
    fu_status: dict[str, FunctionalUnitStatus]
    register_result: dict[str, str | None]


@dataclass
class InstructionResult:
    """Final cycle stamps for one instruction after simulation completes."""

    instruction: Instruction
    issue: int
    read_operands: int
    execute_complete: int
    write_result: int


@dataclass
class Trace:
    """Full simulation output.

    Attributes:
        results: Per-instruction cycle stamps in program order.
        snapshots: Optional per-cycle state snapshots (populated when
                   capture_snapshots=True in run()).
        total_cycles: Cycle number of the final WriteResult.
    """

    results: list[InstructionResult]
    snapshots: list[CycleSnapshot] = field(default_factory=list)
    total_cycles: int = 0
