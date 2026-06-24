"""Tests for the Scoreboarding simulation engine.

Golden trace derivation (hand-computed)
----------------------------------------
Program and functional units:

    FU Load1 load  latency=2
    FU Mult1 mult  latency=10
    FU Add1  add   latency=2
    FU Div1  div   latency=40

    [0] LD   F6, R2       -- Load unit, dest=F6
    [1] LD   F2, R3       -- Load unit, dest=F2
    [2] MULT F0, F2, F4   -- Mult unit, src1=F2 (RAW from [1])
    [3] SUB  F8, F6, F2   -- Add unit,  src1=F6 (RAW from [0]), src2=F2 (RAW from [1])
    [4] DIV  F10, F0, F6  -- Div unit,  src1=F0 (RAW from [2]), src2=F6 (WAR: [5] writes F6)
    [5] ADD  F6, F8, F2   -- Add unit,  dest=F6 (WAR: [4] reads F6; structural: Add1 busy by [3])

Step-by-step trace:

Cycle 1:
  ISSUE [0] LD F6: Load1 free, no WAW. Assign Load1, rj=True (R2 ready), rk=True (no src2).
  RegisterResult[F6] = Load1.

Cycle 2:
  READ OPS [0] LD F6: qj=None, rj=True, qk=None, rk=True => reads at cycle 2.
    rj=rk=False (consumed). execute_start = 3.
  ISSUE [1] LD F2: Load1 still busy (LD F6 has not written result yet). Structural stall.

Cycles 2-4:
  LD F6 executes: execute_start=3, latency=2, execComp = 3+2-1 = 4.
  ISSUE [1] LD F2: blocked every cycle -- Load1 busy until LD F6 writes result.

Cycle 4:
  EXEC COMPLETE [0] LD F6: execComp=4.

Cycle 5:
  WRITE RESULT [0] LD F6: WAR check -- any earlier instruction (none) reads F6 with rj/rk=True? No.
    WriteResult[0]=5. RegisterResult[F6]=None. Load1 freed.
  ISSUE [1] LD F2: Load1 now free (freed this cycle). No WAW (F2 not written by active insn).
    Assign Load1, rj=True (R3 ready), rk=True (no src2).
    RegisterResult[F2] = Load1.

Cycle 6:
  READ OPS [1] LD F2: qj=None, rj=True => reads at cycle 6. execute_start=7.
  ISSUE [2] MULT F0: Mult1 free, no WAW on F0.
    src1=F2 -- RegisterResult[F2]=Load1 => qj=Load1, rj=False (not ready).
    src2=F4 -- not in RegisterResult => qk=None, rk=True.
    RegisterResult[F0] = Mult1.

Cycle 7:
  ISSUE [3] SUB F8: Add1 free, no WAW on F8.
    src1=F6 -- RegisterResult[F6]=None => qj=None, rj=True (F6 written at cycle 5).
    src2=F2 -- RegisterResult[F2]=Load1 => qk=Load1, rk=False.
    RegisterResult[F8] = Add1.

Cycle 8:
  EXEC COMPLETE [1] LD F2: execute_start=7, latency=2, execComp = 7+2-1 = 8.
  ISSUE [4] DIV F10: Div1 free, no WAW on F10.
    src1=F0 -- RegisterResult[F0]=Mult1 => qj=Mult1, rj=False.
    src2=F6 -- RegisterResult[F6]=None => qk=None, rk=True.
    RegisterResult[F10] = Div1.

Cycle 9:
  WRITE RESULT [1] LD F2: WAR check -- does any earlier instruction (none are earlier than [1])
    read F2 with rj/rk=True? No earlier instructions. WriteResult[1]=9.
    RegisterResult[F2]=None. Update qj/qk for dependents:
      [2] MULT: qj==Load1 => qj=None, rj=True.
      [3] SUB:  qk==Load1 => qk=None, rk=True.
    Load1 freed.
  READ OPS [2] MULT F0: qj=None, rj=True AND qk=None, rk=True => reads at cycle 9. execute_start=10.
  READ OPS [3] SUB F8: qj=None, rj=True AND qk=None, rk=True => reads at cycle 9. execute_start=10.
  ISSUE [5] ADD F6 (attempt): Add1 is busy (SUB F8 still executing). Structural stall.

Cycles 10-11:
  [3] SUB executes: execute_start=10, latency=2, execComp = 10+2-1 = 11.

Cycle 11:
  EXEC COMPLETE [3] SUB F8: execComp=11.

Cycle 12:
  WRITE RESULT [3] SUB F8: WAR check -- any earlier instruction reads F8 with rj/rk=True?
    [0],[1] are done. [2] MULT reads F2,F4 (not F8). No WAR. WriteResult[3]=12.
    RegisterResult[F8]=None. Add1 freed.
  ISSUE [5] ADD F6: Add1 now free (freed this cycle).
    WAW check: is any active instruction writing F6? No (LD F6 [0] is done).
    src1=F8 -- RegisterResult[F8]=None (just cleared) => qj=None, rj=True.
    src2=F2 -- RegisterResult[F2]=None => qk=None, rk=True.
    RegisterResult[F6] = Add1.

Cycle 13:
  READ OPS [5] ADD F6: qj=None, rj=True AND qk=None, rk=True => reads at cycle 13. execute_start=14.

Cycles 14-15:
  [5] ADD executes: latency=2, execComp = 14+2-1 = 15.

Cycle 15:
  EXEC COMPLETE [5] ADD F6: execComp=15.

Cycles 16-20:
  WRITE RESULT [5] ADD F6 (attempts): WAR check -- does any earlier instruction read F6 with
    rj/rk=True? [4] DIV reads F6 as src2. [4] issued at cycle 8, earlier than [5] at cycle 12.
    [4] DIV fu_status.rk = True (F6 ready from the start, qk=None, rk=True -- but rk was set
    True at issue because RegisterResult[F6]=None at issue time. It has NOT yet read operands.)
    So rk=True means DIV is still waiting for F6 (even though F6 is ready; DIV is blocked on F0).
    WAR blocks ADD F6 write until DIV reads F6.

Cycle 19:
  EXEC COMPLETE [2] MULT F0: execute_start=10, latency=10, execComp = 10+10-1 = 19.

Cycle 20:
  WRITE RESULT [2] MULT F0: WAR check -- earlier instructions reading F0? None use F0 as source.
    WriteResult[2]=20. RegisterResult[F0]=None.
    Update [4] DIV: qj==Mult1 => qj=None, rj=True. Mult1 freed.
  READ OPS [4] DIV F10: qj=None, rj=True AND qk=None, rk=True => reads at cycle 20.
    execute_start=21.

Cycle 21:
  WRITE RESULT [5] ADD F6: WAR check -- [4] DIV read F6 at cycle 20 (rk was cleared).
    No more earlier instructions with rj/rk=True on F6. WriteResult[5]=21. Add1 freed.
    RegisterResult[F6]=None.

Cycles 21-60:
  [4] DIV executes: execute_start=21, latency=40, execComp = 21+40-1 = 60.

Cycle 60:
  EXEC COMPLETE [4] DIV F10: execComp=60.

Cycle 61:
  WRITE RESULT [4] DIV F10: no WAR. WriteResult[4]=61. RegisterResult[F10]=None. Div1 freed.

Final timing table:
  [0] LD   F6: issue=1, ro=2,  ec=4,  wr=5
  [1] LD   F2: issue=5, ro=6,  ec=8,  wr=9
  [2] MULT F0: issue=6, ro=9,  ec=19, wr=20
  [3] SUB  F8: issue=7, ro=9,  ec=11, wr=12
  [4] DIV F10: issue=8, ro=20, ec=60, wr=61
  [5] ADD  F6: issue=12,ro=13, ec=15, wr=21

  Total cycles: 61

Hazards demonstrated:
- Structural stall: [1] LD F2 waits at cycle 2-4 because Load1 is busy (LD F6).
- RAW: [2] MULT waits until cycle 9 (LD F2 writes F2 at cycle 9) to read operands.
- RAW: [3] SUB waits until cycle 9 (LD F2 writes F2 at cycle 9) to read operands.
- WAR: [5] ADD writes F6 but [4] DIV reads F6; ADD WriteResult stalls until cycle 21
        (after DIV reads F6 at cycle 20).
- WAW: Tested separately -- two instructions writing same dest stalls Issue.
"""

from __future__ import annotations

import pytest

from scoreboarding import FunctionalUnit, Instruction, run

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _classic_fus() -> list[FunctionalUnit]:
    """Four FUs matching the classic CDC 6600 floating-point example."""
    return [
        FunctionalUnit(name="Load1", kind="load", latency=2, pipelined=False),
        FunctionalUnit(name="Mult1", kind="mult", latency=10, pipelined=False),
        FunctionalUnit(name="Add1", kind="add", latency=2, pipelined=False),
        FunctionalUnit(name="Div1", kind="div", latency=40, pipelined=False),
    ]


def _classic_program() -> list[Instruction]:
    """Six-instruction program used to derive the golden trace above."""
    return [
        Instruction(op="LD", dest="F6", src1="R2", src2=""),
        Instruction(op="LD", dest="F2", src1="R3", src2=""),
        Instruction(op="MULT", dest="F0", src1="F2", src2="F4"),
        Instruction(op="SUB", dest="F8", src1="F6", src2="F2"),
        Instruction(op="DIV", dest="F10", src1="F0", src2="F6"),
        Instruction(op="ADD", dest="F6", src1="F8", src2="F2"),
    ]


# ---------------------------------------------------------------------------
# Golden trace tests
# ---------------------------------------------------------------------------


class TestGoldenTrace:
    """Verify the hand-derived cycle stamps against the simulator."""

    def test_ld_f6(self) -> None:
        trace = run(_classic_program(), functional_units=_classic_fus())
        r = trace.results[0]
        assert r.issue == 1
        assert r.read_operands == 2
        assert r.execute_complete == 4
        assert r.write_result == 5

    def test_ld_f2(self) -> None:
        trace = run(_classic_program(), functional_units=_classic_fus())
        r = trace.results[1]
        assert r.issue == 5
        assert r.read_operands == 6
        assert r.execute_complete == 8
        assert r.write_result == 9

    def test_mult_f0(self) -> None:
        trace = run(_classic_program(), functional_units=_classic_fus())
        r = trace.results[2]
        assert r.issue == 6
        assert r.read_operands == 9
        assert r.execute_complete == 19
        assert r.write_result == 20

    def test_sub_f8(self) -> None:
        trace = run(_classic_program(), functional_units=_classic_fus())
        r = trace.results[3]
        assert r.issue == 7
        assert r.read_operands == 9
        assert r.execute_complete == 11
        assert r.write_result == 12

    def test_div_f10(self) -> None:
        trace = run(_classic_program(), functional_units=_classic_fus())
        r = trace.results[4]
        assert r.issue == 8
        assert r.read_operands == 20
        assert r.execute_complete == 60
        assert r.write_result == 61

    def test_add_f6(self) -> None:
        trace = run(_classic_program(), functional_units=_classic_fus())
        r = trace.results[5]
        assert r.issue == 12
        assert r.read_operands == 13
        assert r.execute_complete == 15
        assert r.write_result == 21

    def test_total_cycles(self) -> None:
        trace = run(_classic_program(), functional_units=_classic_fus())
        assert trace.total_cycles == 61

    def test_result_count(self) -> None:
        trace = run(_classic_program(), functional_units=_classic_fus())
        assert len(trace.results) == 6


# ---------------------------------------------------------------------------
# Invariant: in-order issue
# ---------------------------------------------------------------------------


class TestInOrderIssue:
    """Issue cycles must be non-decreasing in program order."""

    def test_classic_program_issues_in_order(self) -> None:
        trace = run(_classic_program(), functional_units=_classic_fus())
        issue_cycles = [r.issue for r in trace.results]
        for i in range(len(issue_cycles) - 1):
            assert issue_cycles[i] <= issue_cycles[i + 1], (
                f"Out-of-order issue: instr {i} issued at {issue_cycles[i]} "
                f"but instr {i+1} issued at {issue_cycles[i+1]}"
            )

    def test_single_fu_type_issues_in_order(self) -> None:
        """With a single Add FU, three ADD instructions must issue strictly in order."""
        fus = [FunctionalUnit(name="Add1", kind="add", latency=3, pipelined=False)]
        prog = [
            Instruction(op="ADD", dest="F0", src1="R0", src2="R1"),
            Instruction(op="ADD", dest="F2", src1="R2", src2="R3"),
            Instruction(op="ADD", dest="F4", src1="R4", src2="R5"),
        ]
        trace = run(prog, functional_units=fus)
        issue_cycles = [r.issue for r in trace.results]
        assert issue_cycles[0] < issue_cycles[1] < issue_cycles[2]


# ---------------------------------------------------------------------------
# Structural stall
# ---------------------------------------------------------------------------


class TestStructuralStall:
    """A second instruction of the same FU kind stalls until the first completes WriteResult."""

    def test_two_loads_one_unit(self) -> None:
        """With one Load FU, LD F2 cannot issue until LD F6 finishes WriteResult."""
        fus = [FunctionalUnit(name="Load1", kind="load", latency=2, pipelined=False)]
        prog = [
            Instruction(op="LD", dest="F6", src1="R1", src2=""),
            Instruction(op="LD", dest="F2", src1="R2", src2=""),
        ]
        trace = run(prog, functional_units=fus)
        r0, r1 = trace.results
        # LD F6 issues at 1, writes result at 5.
        assert r0.issue == 1
        assert r0.write_result == 5
        # LD F2 can only issue once Load1 is free, which happens at cycle 5.
        assert r1.issue == 5
        assert r1.issue > r0.issue  # structural stall confirmed

    def test_classic_ld_f2_structural_stall(self) -> None:
        """In the classic program, LD F2 is stalled from cycle 2 to 5."""
        trace = run(_classic_program(), functional_units=_classic_fus())
        r0, r1 = trace.results[0], trace.results[1]
        # LD F6 writes at 5, LD F2 issues at 5 -- stalled 4 cycles.
        assert r0.write_result == 5
        assert r1.issue == 5


# ---------------------------------------------------------------------------
# Pipelined vs unpipelined functional units
# ---------------------------------------------------------------------------


class TestPipelinedFunctionalUnits:
    """A pipelined unit frees its issue slot at ReadOperands, not WriteResult.

    Back-to-back independent ops of the same kind on a single physical unit::

        FU Mult1 mult latency=4 (pipelined or unpipelined)
        [0] MULT F0, R0, R1
        [1] MULT F2, R2, R3

    Pipelined hand-derivation::

        C1  ISSUE [0]      Mult1 free -> occupy. RegResult[F0]=Mult1.
        C2  READ OPS [0]   reads at 2, execute_start=3, pipelined -> Mult1 free.
            ISSUE [1]      Mult1 free (released this cycle) -> issue at 2.
        C3  READ OPS [1]   reads at 3, execute_start=4.
        C6  EXEC COMP [0]  3+4-1 = 6.
        C7  WRITE [0]=7.   EXEC COMP [1] 4+4-1 = 7.
        C8  WRITE [1]=8.

        [0]: issue=1 ro=2 ec=6 wr=7
        [1]: issue=2 ro=3 ec=7 wr=8   total=8

    Unpipelined, [1] cannot issue until [0] writes back at cycle 7::

        [1]: issue=7 ro=8 ec=12 wr=13  total=13
    """

    def _two_independent_mults(self) -> list[Instruction]:
        return [
            Instruction(op="MULT", dest="F0", src1="R0", src2="R1"),
            Instruction(op="MULT", dest="F2", src1="R2", src2="R3"),
        ]

    def test_pipelined_back_to_back_issue(self) -> None:
        fus = [FunctionalUnit(name="Mult1", kind="mult", latency=4, pipelined=True)]
        trace = run(self._two_independent_mults(), functional_units=fus)
        r0, r1 = trace.results
        assert (r0.issue, r0.read_operands, r0.execute_complete, r0.write_result) == (1, 2, 6, 7)
        assert (r1.issue, r1.read_operands, r1.execute_complete, r1.write_result) == (2, 3, 7, 8)
        assert trace.total_cycles == 8

    def test_unpipelined_back_to_back_structural_stall(self) -> None:
        fus = [FunctionalUnit(name="Mult1", kind="mult", latency=4, pipelined=False)]
        trace = run(self._two_independent_mults(), functional_units=fus)
        r0, r1 = trace.results
        assert (r0.issue, r0.read_operands, r0.execute_complete, r0.write_result) == (1, 2, 6, 7)
        # Second MULT stalls at Issue until the first writes back (cycle 7).
        assert (r1.issue, r1.read_operands, r1.execute_complete, r1.write_result) == (7, 8, 12, 13)
        assert trace.total_cycles == 13

    def test_pipelined_issues_earlier_than_unpipelined(self) -> None:
        prog = self._two_independent_mults()
        pip = run(
            prog,
            functional_units=[FunctionalUnit(name="M", kind="mult", latency=4, pipelined=True)],
        )
        unp = run(
            prog,
            functional_units=[FunctionalUnit(name="M", kind="mult", latency=4, pipelined=False)],
        )
        assert pip.results[1].issue < unp.results[1].issue
        assert pip.total_cycles < unp.total_cycles

    def test_pipelined_three_deep_loads(self) -> None:
        """Three independent loads on one pipelined Load unit issue one per cycle."""
        fus = [FunctionalUnit(name="Load1", kind="load", latency=2, pipelined=True)]
        prog = [
            Instruction(op="LD", dest="F0", src1="R0", src2=""),
            Instruction(op="LD", dest="F2", src1="R1", src2=""),
            Instruction(op="LD", dest="F4", src1="R2", src2=""),
        ]
        trace = run(prog, functional_units=fus)
        r0, r1, r2 = trace.results
        assert (r0.issue, r0.read_operands, r0.execute_complete, r0.write_result) == (1, 2, 4, 5)
        assert (r1.issue, r1.read_operands, r1.execute_complete, r1.write_result) == (2, 3, 5, 6)
        assert (r2.issue, r2.read_operands, r2.execute_complete, r2.write_result) == (3, 4, 6, 7)
        assert trace.total_cycles == 7

    def test_pipelined_raw_disambiguation_by_destination(self) -> None:
        """Two in-flight ops share a pipelined FU name; a RAW dependent must
        wake on the correct producer, not whichever finishes first.

        Mult1 (pipelined) holds [0] producing F0 and [1] producing F2. ADD reads
        F2 (from [1]), so it must read operands at cycle 8 (when [1] writes), not
        cycle 7 (when [0] writes F0).
        """
        fus = [
            FunctionalUnit(name="Mult1", kind="mult", latency=4, pipelined=True),
            FunctionalUnit(name="Add1", kind="add", latency=2, pipelined=False),
        ]
        prog = [
            Instruction(op="MULT", dest="F0", src1="R0", src2="R1"),
            Instruction(op="MULT", dest="F2", src1="R2", src2="R3"),
            Instruction(op="ADD", dest="F4", src1="F2", src2="R5"),
        ]
        trace = run(prog, functional_units=fus)
        r_m0, r_m1, r_add = trace.results
        assert r_m0.write_result == 7
        assert r_m1.write_result == 8
        # ADD reads F2 the cycle [1] writes it (8), not the cycle [0] writes F0 (7).
        assert r_add.read_operands == 8
        assert (r_add.execute_complete, r_add.write_result) == (10, 11)

    def test_pipelined_relaxes_classic_load_contention(self) -> None:
        """Pipelining only relaxes the structural stall; with no same-kind
        contention the classic golden trace is unchanged, but the pipelined Load
        unit lets LD F2 issue at cycle 2 instead of 5."""
        prog = _classic_program()
        unp = run(prog, functional_units=_classic_fus())
        pip = run(
            prog,
            functional_units=[
                FunctionalUnit(name="Load1", kind="load", latency=2, pipelined=True),
                FunctionalUnit(name="Mult1", kind="mult", latency=10, pipelined=True),
                FunctionalUnit(name="Add1", kind="add", latency=2, pipelined=True),
                FunctionalUnit(name="Div1", kind="div", latency=40, pipelined=True),
            ],
        )
        # Unpipelined Load1 stays busy until LD F6 writes back (cycle 5).
        assert unp.results[1].issue == 5
        # Pipelined Load1 is released once LD F6 reads operands (cycle 2), and
        # Issue runs after Read Operands within the cycle, so LD F2 issues at 2.
        assert pip.results[1].issue == 2


# ---------------------------------------------------------------------------
# WAW hazard stalls Issue
# ---------------------------------------------------------------------------


class TestWAWHazard:
    """A WAW hazard (two instructions writing the same register) must stall Issue."""

    def test_waw_stalls_second_mult(self) -> None:
        """Two MULT instructions writing F0 with separate Mult FUs -- second stalls for WAW."""
        fus = [
            FunctionalUnit(name="Mult1", kind="mult", latency=5, pipelined=False),
            FunctionalUnit(name="Mult2", kind="mult", latency=5, pipelined=False),
        ]
        prog = [
            # Both write F0 -- WAW hazard.
            Instruction(op="MULT", dest="F0", src1="R1", src2="R2"),
            Instruction(op="MULT", dest="F0", src1="R3", src2="R4"),
        ]
        trace = run(prog, functional_units=fus)
        r0, r1 = trace.results
        # First issues at cycle 1.
        assert r0.issue == 1
        # Second must not issue until the first has written its result (WAW).
        assert r1.issue > r0.issue
        assert r1.issue >= r0.write_result

    def test_waw_with_one_mult_fu(self) -> None:
        """With one Mult FU, both structural and WAW block the second instruction."""
        fus = [FunctionalUnit(name="Mult1", kind="mult", latency=4, pipelined=False)]
        prog = [
            Instruction(op="MULT", dest="F0", src1="R0", src2="R1"),
            Instruction(op="MULT", dest="F0", src1="R2", src2="R3"),
        ]
        trace = run(prog, functional_units=fus)
        r0, r1 = trace.results
        assert r0.issue == 1
        # Blocked by structural AND WAW -- must issue after r0.write_result.
        assert r1.issue >= r0.write_result

    def test_different_dest_no_waw_stall(self) -> None:
        """Two MULTs to different destinations must NOT stall due to WAW."""
        fus = [
            FunctionalUnit(name="Mult1", kind="mult", latency=5, pipelined=False),
            FunctionalUnit(name="Mult2", kind="mult", latency=5, pipelined=False),
        ]
        prog = [
            Instruction(op="MULT", dest="F0", src1="R1", src2="R2"),
            Instruction(op="MULT", dest="F2", src1="R3", src2="R4"),
        ]
        trace = run(prog, functional_units=fus)
        r0, r1 = trace.results
        # Both can issue in cycle 1 and 2 (different FUs, different dests).
        assert r0.issue == 1
        assert r1.issue == 2


# ---------------------------------------------------------------------------
# RAW hazard delays ReadOperands
# ---------------------------------------------------------------------------


class TestRAWHazard:
    """RAW hazards delay the ReadOperands stage."""

    def test_raw_delays_read_operands(self) -> None:
        """ADD reads F0 only after MULT writes F0."""
        fus = [
            FunctionalUnit(name="Mult1", kind="mult", latency=5, pipelined=False),
            FunctionalUnit(name="Add1", kind="add", latency=2, pipelined=False),
        ]
        prog = [
            Instruction(op="MULT", dest="F0", src1="R1", src2="R2"),
            Instruction(op="ADD", dest="F4", src1="F0", src2="R3"),
        ]
        trace = run(prog, functional_units=fus)
        r_mult, r_add = trace.results
        # ADD must read operands no earlier than the cycle after MULT writes result.
        assert r_add.read_operands >= r_mult.write_result

    def test_classic_mult_raw_from_ld_f2(self) -> None:
        """MULT F0 reads F2 at cycle 9, which is exactly when LD F2 writes result."""
        trace = run(_classic_program(), functional_units=_classic_fus())
        r_ld_f2 = trace.results[1]
        r_mult = trace.results[2]
        # MULT reads operands the same cycle LD F2 writes (cycle 9).
        assert r_mult.read_operands == r_ld_f2.write_result

    def test_no_raw_both_read_immediately(self) -> None:
        """When no RAW exists, ReadOperands follows immediately after Issue."""
        fus = [FunctionalUnit(name="Add1", kind="add", latency=2, pipelined=False)]
        prog = [Instruction(op="ADD", dest="F0", src1="R0", src2="R1")]
        trace = run(prog, functional_units=fus)
        r = trace.results[0]
        # Issue at 1, ReadOps at 2 (next cycle, both sources ready).
        assert r.issue == 1
        assert r.read_operands == r.issue + 1


# ---------------------------------------------------------------------------
# WAR hazard delays WriteResult
# ---------------------------------------------------------------------------


class TestWARHazard:
    """WAR hazards must delay WriteResult, not Issue or ReadOperands."""

    def test_war_delays_write_result(self) -> None:
        """ADD F6 must wait for DIV to read F6 before writing its result.

        Program:
          MULT F0, R1, R2    -- produces F0 (latency=10)
          DIV  F10, F0, F6   -- reads F0 (RAW: stalled until MULT writes) and reads F6
          ADD  F6, R3, R4    -- writes F6 (WAR against DIV which still needs to read F6)

        The RAW on F0 forces DIV to delay ReadOperands until cycle 13.
        ADD F6 has no RAW hazards so it executes quickly (execComp=6).
        WAR blocks ADD F6 WriteResult (which would otherwise be cycle 7) until
        DIV has consumed F6 at cycle 13. ADD F6 WriteResult = 14.
        """
        fus = [
            FunctionalUnit(name="Mult1", kind="mult", latency=10, pipelined=False),
            FunctionalUnit(name="Div1", kind="div", latency=5, pipelined=False),
            FunctionalUnit(name="Add1", kind="add", latency=2, pipelined=False),
        ]
        prog = [
            Instruction(op="MULT", dest="F0", src1="R1", src2="R2"),
            Instruction(op="DIV", dest="F10", src1="F0", src2="F6"),
            Instruction(op="ADD", dest="F6", src1="R3", src2="R4"),
        ]
        trace = run(prog, functional_units=fus)
        r_mult, r_div, r_add = trace.results
        # ADD completes execution well before DIV reads F6.
        assert r_add.execute_complete < r_div.read_operands
        # ADD WriteResult cannot precede DIV ReadOperands (WAR).
        assert r_add.write_result >= r_div.read_operands
        # Exact cycle numbers derived from the algorithm:
        assert r_mult.write_result == 13
        assert r_div.read_operands == 13
        assert r_add.execute_complete == 6
        assert r_add.write_result == 14

    def test_classic_add_f6_war_stall(self) -> None:
        """In the classic program, ADD F6 is WAR-blocked by DIV F10 reading F6."""
        trace = run(_classic_program(), functional_units=_classic_fus())
        r_div = trace.results[4]
        r_add = trace.results[5]
        # ADD F6 execComp=15, but DIV reads F6 at 20 -- WAR stall for 6 cycles.
        assert r_add.execute_complete == 15
        assert r_div.read_operands == 20
        assert r_add.write_result == 21  # one cycle after DIV reads F6

    def test_no_war_when_no_earlier_reader(self) -> None:
        """If no earlier instruction reads the destination, WriteResult is immediate."""
        fus = [FunctionalUnit(name="Add1", kind="add", latency=2, pipelined=False)]
        prog = [Instruction(op="ADD", dest="F0", src1="R0", src2="R1")]
        trace = run(prog, functional_units=fus)
        r = trace.results[0]
        # execComp = issue+1+latency-1 = 1+1+2-1 = 3 ... ReadOps=2, execStart=3, execComp=4.
        assert r.write_result == r.execute_complete + 1


# ---------------------------------------------------------------------------
# Simulation termination
# ---------------------------------------------------------------------------


class TestTermination:
    """Simulation must always terminate for valid inputs."""

    def test_empty_program(self) -> None:
        fus = [FunctionalUnit(name="Add1", kind="add", latency=2, pipelined=False)]
        trace = run([], functional_units=fus)
        assert trace.results == []
        assert trace.total_cycles == 0

    def test_single_instruction(self) -> None:
        fus = [FunctionalUnit(name="Add1", kind="add", latency=3, pipelined=False)]
        prog = [Instruction(op="ADD", dest="F0", src1="R0", src2="R1")]
        trace = run(prog, functional_units=fus)
        assert len(trace.results) == 1
        r = trace.results[0]
        assert r.write_result is not None
        assert r.write_result > 0

    def test_classic_program_terminates(self) -> None:
        trace = run(_classic_program(), functional_units=_classic_fus())
        assert trace.total_cycles > 0
        for r in trace.results:
            assert r.issue > 0
            assert r.read_operands > 0
            assert r.execute_complete > 0
            assert r.write_result > 0

    def test_stage_ordering_within_each_instruction(self) -> None:
        """Every instruction must satisfy: issue <= ro <= ec <= wr."""
        trace = run(_classic_program(), functional_units=_classic_fus())
        for r in trace.results:
            assert r.issue <= r.read_operands, (
                f"{r.instruction.op} {r.instruction.dest}: issue > read_operands"
            )
            assert r.read_operands <= r.execute_complete, (
                f"{r.instruction.op} {r.instruction.dest}: read_operands > execute_complete"
            )
            assert r.execute_complete <= r.write_result, (
                f"{r.instruction.op} {r.instruction.dest}: execute_complete > write_result"
            )


# ---------------------------------------------------------------------------
# Snapshot capture
# ---------------------------------------------------------------------------


class TestSnapshots:
    """capture_snapshots=True must produce one snapshot per cycle."""

    def test_snapshot_count(self) -> None:
        fus = [FunctionalUnit(name="Add1", kind="add", latency=2, pipelined=False)]
        prog = [Instruction(op="ADD", dest="F0", src1="R0", src2="R1")]
        trace = run(prog, functional_units=fus, capture_snapshots=True)
        assert len(trace.snapshots) == trace.total_cycles

    def test_snapshots_disabled_by_default(self) -> None:
        fus = [FunctionalUnit(name="Add1", kind="add", latency=2, pipelined=False)]
        prog = [Instruction(op="ADD", dest="F0", src1="R0", src2="R1")]
        trace = run(prog, functional_units=fus)
        assert trace.snapshots == []


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrors:
    """Invalid inputs must raise ValueError with descriptive messages."""

    def test_unknown_fu_kind_raises(self) -> None:
        fus = [FunctionalUnit(name="Add1", kind="add", latency=2, pipelined=False)]
        prog = [Instruction(op="MULT", dest="F0", src1="R0", src2="R1")]
        with pytest.raises(ValueError, match="mult"):
            run(prog, functional_units=fus)

    def test_fu_latency_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="latency"):
            FunctionalUnit(name="Add1", kind="add", latency=0, pipelined=False)

    def test_fu_latency_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="latency"):
            FunctionalUnit(name="Add1", kind="add", latency=-3, pipelined=False)
