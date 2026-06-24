"""Cycle-exact Scoreboarding simulator engine.

Implements Thornton's Scoreboarding algorithm as used in the CDC 6600 (1964),
with four pipeline stages and three tracking tables.

Stage checks (per Thornton):

ISSUE
  Preconditions (checked in program order -- no instruction may issue while an
  earlier instruction is stalled):
  1. No structural hazard: the required functional unit is not busy.
  2. No WAW hazard: no currently-active instruction will write the same
     destination register.

READ OPERANDS
  An instruction that has been issued waits here until BOTH source operands are
  available. An operand is available when no earlier-issued instruction is still
  going to write it (qj/qk = None AND rj/rk = True).  This stage resolves RAW.

EXECUTE
  The instruction occupies its functional unit for exactly `latency` cycles
  starting the cycle after operands are read.

WRITE RESULT
  Precondition -- no WAR hazard: every earlier-issued instruction that reads
  the destination register as a source must have already completed its READ
  OPERANDS stage.  Once this holds, the result is written to the register file,
  RegisterResultStatus is cleared, and the functional unit is freed.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

from scoreboarding.model import (
    CycleSnapshot,
    FunctionalUnit,
    FunctionalUnitStatus,
    Instruction,
    InstructionResult,
    InstructionStatus,
    Trace,
)


@dataclass
class _SimInstruction:
    """Internal per-instruction mutable state."""

    instruction: Instruction
    program_index: int
    status: InstructionStatus = field(default_factory=InstructionStatus)
    fu_name: str = ""  # which FU was assigned at issue
    execute_start: int | None = None  # cycle execution began for THIS instruction


def _op_kind(op: str) -> str:
    """Map an operation name to its functional-unit kind.

    Recognises load/store, add/sub, mult/div, and falls back to op.lower().
    """
    op_upper = op.upper()
    if op_upper in ("LD", "LW", "LOAD", "ST", "SW", "STORE"):
        return "load"
    if op_upper in ("ADD", "ADDD", "ADDI", "ADDF"):
        return "add"
    if op_upper in ("SUB", "SUBD", "SUBI", "SUBF"):
        return "add"  # SUB shares the add/subtract unit by convention
    if op_upper in ("MULT", "MUL", "MULTD", "MULF"):
        return "mult"
    if op_upper in ("DIV", "DIVD", "DIVF"):
        return "div"
    return op.lower()


def run(
    program: list[Instruction],
    *,
    functional_units: list[FunctionalUnit],
    capture_snapshots: bool = False,
) -> Trace:
    """Simulate program using Thornton's Scoreboarding algorithm.

    Args:
        program: Instructions to execute, in program order.
        functional_units: Available functional units.
        capture_snapshots: When True, record a full CycleSnapshot each cycle.

    Returns:
        A Trace with per-instruction cycle stamps and optional snapshots.

    Raises:
        ValueError: If an instruction's operation has no matching functional unit.
    """
    if not program:
        return Trace(results=[], snapshots=[], total_cycles=0)

    # Validate that every instruction has a matching FU kind.
    fu_by_kind: dict[str, list[FunctionalUnit]] = {}
    for fu in functional_units:
        fu_by_kind.setdefault(fu.kind, []).append(fu)

    for instr in program:
        kind = _op_kind(instr.op)
        if kind not in fu_by_kind:
            raise ValueError(
                f"No functional unit of kind '{kind}' for operation '{instr.op}'"
            )

    # Build per-FU status table.
    fu_status: dict[str, FunctionalUnitStatus] = {
        fu.name: FunctionalUnitStatus() for fu in functional_units
    }
    fu_latency: dict[str, int] = {fu.name: fu.latency for fu in functional_units}
    fu_pipelined: dict[str, bool] = {fu.name: fu.pipelined for fu in functional_units}

    # Free-for-issue flag per FU. An unpipelined unit is occupied (False) from
    # Issue until Write Result. A pipelined unit becomes free again the cycle
    # after the occupying instruction reads operands and enters the execute
    # pipeline, so a same-kind successor may issue to it sooner.
    fu_free: dict[str, bool] = {fu.name: True for fu in functional_units}

    # Register-result-status table: maps register name -> FU name that will write it.
    # None means no pending write (register holds its committed value).
    register_result: dict[str, str | None] = {}

    # Internal instruction list.
    sim_instrs: list[_SimInstruction] = [
        _SimInstruction(instruction=instr, program_index=i)
        for i, instr in enumerate(program)
    ]

    # Index of the next instruction to issue (in-order issue pointer).
    next_to_issue: int = 0
    snapshots: list[CycleSnapshot] = []
    cycle = 0

    # Run until every instruction has a WriteResult.
    while not _all_done(sim_instrs):
        cycle += 1

        # Determine which instructions attempt write-result, read-operands,
        # and execute this cycle.  ISSUE is handled last because it depends on
        # the current-cycle FU state after potential WriteResults free units.

        # --- WRITE RESULT ---
        # For each issued instruction that has completed execution and not yet
        # written its result, check the WAR condition.
        for si in sim_instrs:
            if not _can_attempt_write(si):
                continue
            dest = si.instruction.dest
            # WAR check: every earlier-issued instruction that lists `dest` as a
            # source (fj or fk) must have already read its operands (rj/rk = False
            # means it already consumed that operand; the flag is True only while
            # waiting to read).
            war_blocked = False
            for other in sim_instrs:
                if other is si:
                    continue
                if other.status.issue is None:
                    continue
                if other.status.issue >= (si.status.issue or 0):
                    # Only earlier-issued instructions can cause WAR.
                    continue
                if other.status.read_operands is not None:
                    # Already read operands; no WAR from this instruction.
                    continue
                fu_other = fu_status.get(other.fu_name)
                if fu_other is None:
                    continue
                # Check if the other instruction is waiting to read dest.
                if fu_other.fj == dest and fu_other.rj:
                    war_blocked = True
                    break
                if fu_other.fk == dest and fu_other.rk:
                    war_blocked = True
                    break

            if war_blocked:
                continue

            # Write result.
            si.status.write_result = cycle

            # Clear register-result-status if this FU is still the producer.
            if register_result.get(dest) == si.fu_name:
                register_result[dest] = None

            # Update Qj/Qk of any waiting instruction that depended on this
            # instruction's result. The dependency is keyed by FU name in the
            # classic model, but a pipelined FU can hold several in-flight
            # instructions sharing one name, so we also require the waiting
            # instruction's source register to equal this instruction's
            # destination -- the actual producer-consumer link.
            for other in sim_instrs:
                if other.status.issue is None or other.status.read_operands is not None:
                    continue
                fu_other = fu_status.get(other.fu_name)
                if fu_other is None:
                    continue
                if fu_other.qj == si.fu_name and fu_other.fj == dest:
                    fu_other.qj = None
                    fu_other.rj = True
                if fu_other.qk == si.fu_name and fu_other.fk == dest:
                    fu_other.qk = None
                    fu_other.rk = True

            # Free the functional unit for issue. A pipelined unit was already
            # released for issue when this instruction read operands; only reset
            # the shared status row if it still belongs to this instruction (a
            # newer instruction may have reused a pipelined row already).
            fu_free[si.fu_name] = True
            if fu_status[si.fu_name].fi == dest and fu_status[si.fu_name].op == si.instruction.op:
                fu_status[si.fu_name].reset()

        # --- READ OPERANDS ---
        # An instruction reads operands when both sources are ready.
        for si in sim_instrs:
            if si.status.issue is None or si.status.read_operands is not None:
                continue
            fu_st = fu_status[si.fu_name]
            # Both operands available when qj=None,rj=True AND qk=None,rk=True.
            # For single-source instructions src2="" has rk=True and qk=None by
            # construction.
            if fu_st.qj is None and fu_st.rj and fu_st.qk is None and fu_st.rk:
                si.status.read_operands = cycle
                # Mark operands as consumed (rj=rk=False) so WAR tracking works.
                fu_st.rj = False
                fu_st.rk = False
                # A pipelined unit releases its issue slot now that this
                # instruction has read its operands and entered the execute
                # pipeline; a successor may issue to it next cycle.
                if fu_pipelined[si.fu_name]:
                    fu_free[si.fu_name] = True

        # --- EXECUTE COMPLETE ---
        # Mark execute_complete when the latency has elapsed since execute_start.
        for si in sim_instrs:
            if si.status.read_operands is None or si.status.execute_complete is not None:
                continue
            # Start executing the cycle after read-operands. Execution timing is
            # tracked per instruction (not on the shared FU row) so a pipelined
            # unit can hold several in-flight instructions correctly.
            if si.execute_start is None and si.status.read_operands < cycle:
                si.execute_start = si.status.read_operands + 1
                # Mirror onto the FU row for snapshots while the row is this
                # instruction's (unpipelined units keep it for their lifetime).
                fu_status[si.fu_name].execute_start = si.execute_start
            if si.execute_start is not None:
                elapsed = cycle - si.execute_start + 1
                if elapsed >= fu_latency[si.fu_name]:
                    si.status.execute_complete = cycle

        # --- ISSUE ---
        # In-order: attempt to issue the next unissued instruction.
        if next_to_issue < len(sim_instrs):
            si = sim_instrs[next_to_issue]
            instr = si.instruction
            kind = _op_kind(instr.op)

            # Find a free FU of the right kind. A unit is free for issue when its
            # fu_free flag is set: unpipelined units clear it from Issue until
            # Write Result; pipelined units clear it only until the occupying
            # instruction has read operands.
            candidate_fu: str | None = None
            for fu in functional_units:
                if fu.kind == kind and fu_free[fu.name]:
                    candidate_fu = fu.name
                    break

            if candidate_fu is not None:
                # Check WAW: no active instruction may write the same destination.
                waw_blocked = False
                for other in sim_instrs:
                    if other is si:
                        continue
                    if (
                        other.status.issue is not None
                        and other.status.write_result is None
                        and other.instruction.dest == instr.dest
                    ):
                        waw_blocked = True
                        break

                if not waw_blocked:
                    # Issue.
                    si.status.issue = cycle
                    si.fu_name = candidate_fu
                    next_to_issue += 1

                    # Occupy the issue slot. Released at read-operands (pipelined)
                    # or at write-result (unpipelined).
                    fu_free[candidate_fu] = False

                    fu_st = fu_status[candidate_fu]
                    fu_st.busy = True
                    fu_st.op = instr.op
                    fu_st.fi = instr.dest
                    fu_st.execute_start = None

                    # Source 1 (fj).
                    fu_st.fj = instr.src1
                    producing_fj = register_result.get(instr.src1)
                    if producing_fj is not None:
                        fu_st.qj = producing_fj
                        fu_st.rj = False
                    else:
                        fu_st.qj = None
                        fu_st.rj = True

                    # Source 2 (fk).
                    if instr.src2:
                        fu_st.fk = instr.src2
                        producing_fk = register_result.get(instr.src2)
                        if producing_fk is not None:
                            fu_st.qk = producing_fk
                            fu_st.rk = False
                        else:
                            fu_st.qk = None
                            fu_st.rk = True
                    else:
                        # No second source (e.g. single-operand load).
                        fu_st.fk = ""
                        fu_st.qk = None
                        fu_st.rk = True

                    # Mark this FU as the future producer of dest.
                    register_result[instr.dest] = candidate_fu

        # --- CAPTURE SNAPSHOT ---
        if capture_snapshots:
            snapshots.append(
                CycleSnapshot(
                    cycle=cycle,
                    instruction_status=[copy.deepcopy(s.status) for s in sim_instrs],
                    fu_status=copy.deepcopy(fu_status),
                    register_result=dict(register_result),
                )
            )

        # Safety valve: cap at a generous but finite cycle count.
        max_cycles = 10 + sum(fu_latency[fu.name] for fu in functional_units) * len(
            sim_instrs
        )
        if cycle > max_cycles:
            raise RuntimeError(
                f"Simulation did not terminate within {max_cycles} cycles -- "
                "possible deadlock in the program or functional unit configuration."
            )

    total = max(
        (s.status.write_result for s in sim_instrs if s.status.write_result is not None),
        default=0,
    )

    results = [
        InstructionResult(
            instruction=si.instruction,
            issue=si.status.issue or 0,
            read_operands=si.status.read_operands or 0,
            execute_complete=si.status.execute_complete or 0,
            write_result=si.status.write_result or 0,
        )
        for si in sim_instrs
    ]

    return Trace(results=results, snapshots=snapshots, total_cycles=total)


def _all_done(sim_instrs: list[_SimInstruction]) -> bool:
    """Return True when every instruction has completed WriteResult."""
    return all(si.status.write_result is not None for si in sim_instrs)


def _can_attempt_write(si: _SimInstruction) -> bool:
    """Return True when si is eligible to attempt WriteResult this cycle."""
    return (
        si.status.execute_complete is not None
        and si.status.write_result is None
    )
