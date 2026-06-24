"""scoreboarding -- pure-Python Thornton Scoreboarding (CDC 6600) simulator.

Public API::

    from scoreboarding import FunctionalUnit, Instruction, run, render_trace, Trace

Example::

    from scoreboarding import FunctionalUnit, Instruction, run, render_trace

    fus = [
        FunctionalUnit(name="Load1", kind="load", latency=2, pipelined=False),
        FunctionalUnit(name="Mult1", kind="mult", latency=10, pipelined=False),
        FunctionalUnit(name="Add1",  kind="add",  latency=2, pipelined=False),
        FunctionalUnit(name="Div1",  kind="div",  latency=40, pipelined=False),
    ]
    program = [
        Instruction(op="LD",   dest="F6",  src1="R2",  src2=""),
        Instruction(op="LD",   dest="F2",  src1="R3",  src2=""),
        Instruction(op="MULT", dest="F0",  src1="F2",  src2="F4"),
        Instruction(op="SUB",  dest="F8",  src1="F6",  src2="F2"),
        Instruction(op="DIV",  dest="F10", src1="F0",  src2="F6"),
        Instruction(op="ADD",  dest="F6",  src1="F8",  src2="F2"),
    ]
    trace = run(program, functional_units=fus)
    print(render_trace(trace))
"""

from scoreboarding.engine import run
from scoreboarding.model import (
    CycleSnapshot,
    FunctionalUnit,
    FunctionalUnitStatus,
    Instruction,
    InstructionResult,
    InstructionStatus,
    Trace,
)
from scoreboarding.render import render_trace

__all__ = [
    "CycleSnapshot",
    "FunctionalUnit",
    "FunctionalUnitStatus",
    "Instruction",
    "InstructionResult",
    "InstructionStatus",
    "Trace",
    "render_trace",
    "run",
]
