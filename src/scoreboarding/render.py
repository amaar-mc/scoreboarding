"""Render a Trace as a human-readable timing table."""

from __future__ import annotations

from scoreboarding.model import InstructionResult, Trace


def _result_to_row(r: InstructionResult) -> tuple[str, str, str, str, str]:
    """Convert one InstructionResult to a tuple of string columns."""
    src2_part = f", {r.instruction.src2}" if r.instruction.src2 else ""
    instr_str = f"{r.instruction.op} {r.instruction.dest}, {r.instruction.src1}{src2_part}"
    return (
        instr_str,
        str(r.issue),
        str(r.read_operands),
        str(r.execute_complete),
        str(r.write_result),
    )


def render_trace(trace: Trace) -> str:
    """Return a formatted timing table for the given Trace.

    Each row shows one instruction and the four pipeline-stage cycle numbers:
    Issue, ReadOperands, ExecuteComplete, WriteResult.

    Args:
        trace: The simulation output from run().

    Returns:
        A multi-line string suitable for printing to a terminal.
    """
    if not trace.results:
        return "(empty program)"

    header_instr = "Instruction"
    header_issue = "Issue"
    header_ro = "ReadOps"
    header_ec = "ExecComp"
    header_wr = "WriteResult"

    rows = [_result_to_row(r) for r in trace.results]

    col0_w = max(len(header_instr), *(len(row[0]) for row in rows))
    col1_w = max(len(header_issue), *(len(row[1]) for row in rows))
    col2_w = max(len(header_ro), *(len(row[2]) for row in rows))
    col3_w = max(len(header_ec), *(len(row[3]) for row in rows))
    col4_w = max(len(header_wr), *(len(row[4]) for row in rows))

    sep = (
        "+"
        + "-" * (col0_w + 2)
        + "+"
        + "-" * (col1_w + 2)
        + "+"
        + "-" * (col2_w + 2)
        + "+"
        + "-" * (col3_w + 2)
        + "+"
        + "-" * (col4_w + 2)
        + "+"
    )

    def fmt_row(c0: str, c1: str, c2: str, c3: str, c4: str) -> str:
        return (
            f"| {c0:<{col0_w}} "
            f"| {c1:>{col1_w}} "
            f"| {c2:>{col2_w}} "
            f"| {c3:>{col3_w}} "
            f"| {c4:>{col4_w}} |"
        )

    lines = [
        sep,
        fmt_row(header_instr, header_issue, header_ro, header_ec, header_wr),
        sep,
    ]
    for row in rows:
        lines.append(fmt_row(row[0], row[1], row[2], row[3], row[4]))
    lines.append(sep)
    lines.append(f"Total cycles: {trace.total_cycles}")

    return "\n".join(lines)
