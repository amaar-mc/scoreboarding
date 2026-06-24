"""Tests for the scoreboarding CLI."""

from __future__ import annotations

import textwrap

import pytest

from scoreboarding.cli import _parse_program, run

CLASSIC_PROGRAM_TEXT = textwrap.dedent("""\
    # Classic CDC 6600 floating-point example
    FU Load1 load 2
    FU Mult1 mult 10
    FU Add1  add  2
    FU Div1  div  40

    LD   F6, R2
    LD   F2, R3
    MULT F0, F2, F4
    SUB  F8, F6, F2
    DIV  F10, F0, F6
    ADD  F6, F8, F2
""")


class TestParseProgramText:
    def test_parse_fus(self) -> None:
        fus, _ = _parse_program(CLASSIC_PROGRAM_TEXT)
        assert len(fus) == 4
        names = [fu.name for fu in fus]
        assert "Load1" in names
        assert "Mult1" in names

    def test_parse_instructions(self) -> None:
        _, instrs = _parse_program(CLASSIC_PROGRAM_TEXT)
        assert len(instrs) == 6
        assert instrs[0].op == "LD"
        assert instrs[0].dest == "F6"
        assert instrs[0].src1 == "R2"
        assert instrs[0].src2 == ""

    def test_parse_three_operand_instruction(self) -> None:
        text = "FU Add1 add 2\nADD F0, F1, F2"
        _, instrs = _parse_program(text)
        assert instrs[0].dest == "F0"
        assert instrs[0].src1 == "F1"
        assert instrs[0].src2 == "F2"

    def test_ignore_blank_lines_and_comments(self) -> None:
        text = "# comment\n\nFU Add1 add 2\n\nADD F0, R0, R1\n"
        fus, instrs = _parse_program(text)
        assert len(fus) == 1
        assert len(instrs) == 1

    def test_parse_fu_defaults_unpipelined(self) -> None:
        fus, _ = _parse_program("FU Add1 add 2\nADD F0, R0, R1")
        assert fus[0].pipelined is False

    def test_parse_fu_pipelined_flag(self) -> None:
        fus, _ = _parse_program("FU Mult1 mult 10 pipelined\nMULT F0, R0, R1")
        assert fus[0].pipelined is True

    def test_parse_fu_unpipelined_flag(self) -> None:
        fus, _ = _parse_program("FU Mult1 mult 10 unpipelined\nMULT F0, R0, R1")
        assert fus[0].pipelined is False

    def test_invalid_pipelined_flag_raises(self) -> None:
        with pytest.raises(ValueError, match="pipelined flag"):
            _parse_program("FU Mult1 mult 10 sometimes")

    def test_too_many_fu_tokens_raises(self) -> None:
        with pytest.raises(ValueError, match="FU declaration"):
            _parse_program("FU Mult1 mult 10 pipelined extra")

    def test_invalid_fu_declaration_raises(self) -> None:
        with pytest.raises(ValueError, match="FU declaration"):
            _parse_program("FU Add1 add")

    def test_non_integer_latency_raises(self) -> None:
        with pytest.raises(ValueError, match="latency"):
            _parse_program("FU Add1 add two")

    def test_instruction_no_space_raises(self) -> None:
        with pytest.raises(ValueError, match="Cannot parse"):
            _parse_program("FU Add1 add 2\nADD")

    def test_instruction_missing_source_raises(self) -> None:
        with pytest.raises(ValueError, match="source"):
            _parse_program("FU Add1 add 2\nADD F0")


class TestRunCLI:
    def test_run_with_file(self, tmp_path: pytest.TempPathFactory) -> None:
        prog_file = tmp_path / "prog.txt"  # type: ignore[operator]
        prog_file.write_text(CLASSIC_PROGRAM_TEXT)
        exit_code = run([str(prog_file)])
        assert exit_code == 0

    def test_run_missing_file(self) -> None:
        exit_code = run(["/nonexistent/path/prog.txt"])
        assert exit_code == 1

    def test_run_no_fus(self, tmp_path: pytest.TempPathFactory) -> None:
        prog_file = tmp_path / "prog.txt"  # type: ignore[operator]
        prog_file.write_text("ADD F0, R0, R1\n")
        exit_code = run([str(prog_file)])
        assert exit_code == 1

    def test_run_no_instructions(self, tmp_path: pytest.TempPathFactory) -> None:
        prog_file = tmp_path / "prog.txt"  # type: ignore[operator]
        prog_file.write_text("FU Add1 add 2\n")
        exit_code = run([str(prog_file)])
        assert exit_code == 1

    def test_run_with_snapshots_flag(self, tmp_path: pytest.TempPathFactory) -> None:
        prog_file = tmp_path / "prog.txt"  # type: ignore[operator]
        prog_file.write_text("FU Add1 add 2\nADD F0, R0, R1\n")
        exit_code = run(["--snapshots", str(prog_file)])
        assert exit_code == 0

    def test_run_unknown_fu_kind(self, tmp_path: pytest.TempPathFactory) -> None:
        prog_file = tmp_path / "prog.txt"  # type: ignore[operator]
        prog_file.write_text("FU Add1 add 2\nMULT F0, R0, R1\n")
        exit_code = run([str(prog_file)])
        assert exit_code == 1
