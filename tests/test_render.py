"""Tests for the trace rendering utility."""

from __future__ import annotations

from scoreboarding import FunctionalUnit, Instruction, run
from scoreboarding.model import Trace
from scoreboarding.render import render_trace


class TestRenderTrace:
    def test_empty_trace_returns_message(self) -> None:
        trace = Trace(results=[], snapshots=[], total_cycles=0)
        output = render_trace(trace)
        assert "empty" in output.lower()

    def test_output_contains_header_columns(self) -> None:
        fus = [FunctionalUnit(name="Add1", kind="add", latency=2, pipelined=False)]
        prog = [Instruction(op="ADD", dest="F0", src1="R0", src2="R1")]
        trace = run(prog, functional_units=fus)
        output = render_trace(trace)
        assert "Issue" in output
        assert "ReadOps" in output
        assert "ExecComp" in output
        assert "WriteResult" in output

    def test_output_contains_instruction_text(self) -> None:
        fus = [FunctionalUnit(name="Add1", kind="add", latency=2, pipelined=False)]
        prog = [Instruction(op="ADD", dest="F0", src1="R0", src2="R1")]
        trace = run(prog, functional_units=fus)
        output = render_trace(trace)
        assert "ADD" in output
        assert "F0" in output

    def test_output_contains_total_cycles(self) -> None:
        fus = [FunctionalUnit(name="Add1", kind="add", latency=2, pipelined=False)]
        prog = [Instruction(op="ADD", dest="F0", src1="R0", src2="R1")]
        trace = run(prog, functional_units=fus)
        output = render_trace(trace)
        assert "Total cycles:" in output
        assert str(trace.total_cycles) in output

    def test_single_source_instruction_no_trailing_comma(self) -> None:
        fus = [FunctionalUnit(name="Load1", kind="load", latency=2, pipelined=False)]
        prog = [Instruction(op="LD", dest="F6", src1="R2", src2="")]
        trace = run(prog, functional_units=fus)
        output = render_trace(trace)
        # Should not have a trailing ", " for the missing src2.
        assert "R2," not in output.split("LD")[1].split("\n")[0]

    def test_render_returns_string(self) -> None:
        fus = [FunctionalUnit(name="Add1", kind="add", latency=2, pipelined=False)]
        prog = [Instruction(op="ADD", dest="F0", src1="R0", src2="R1")]
        trace = run(prog, functional_units=fus)
        output = render_trace(trace)
        assert isinstance(output, str)
        assert len(output) > 0
