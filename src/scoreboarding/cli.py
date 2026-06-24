"""Command-line interface for the scoreboarding simulator.

Program text format
-------------------
Lines starting with '#' or blank lines are ignored.

Functional unit declarations (must come before instructions)::

    FU <name> <kind> <latency> [pipelined|unpipelined]

The optional fifth token controls the execute pipeline. It defaults to
``unpipelined`` (the classic CDC 6600 scoreboard): the unit stays busy from
Issue until Write Result, so a same-kind successor cannot issue to it until the
occupying instruction writes back. A ``pipelined`` unit frees its issue slot once
the occupying instruction reads operands, shortening the structural stall.

Example::

    FU Load1 load 2
    FU Mult1 mult 10 pipelined
    FU Add1  add  2
    FU Div1  div  40 unpipelined

Instruction lines::

    <op> <dest>, <src1>, <src2>
    <op> <dest>, <src1>          # single-source (loads etc.)

Example::

    LD  F6, R2
    MULT F0, F2, F4
    ADD  F6, F8, F2

Usage::

    scoreboarding program.txt
    scoreboarding --snapshots program.txt
"""

from __future__ import annotations

import argparse
import sys

from scoreboarding.engine import run as engine_run
from scoreboarding.model import FunctionalUnit, Instruction
from scoreboarding.render import render_trace


def _parse_program(text: str) -> tuple[list[FunctionalUnit], list[Instruction]]:
    """Parse program text into functional units and instructions.

    Args:
        text: Full program text with FU declarations followed by instructions.

    Returns:
        A tuple of (functional_units, instructions).

    Raises:
        ValueError: If a line cannot be parsed.
    """
    functional_units: list[FunctionalUnit] = []
    instructions: list[Instruction] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line.upper().startswith("FU "):
            parts = line.split()
            if len(parts) not in (4, 5):
                raise ValueError(
                    "FU declaration must be "
                    "'FU <name> <kind> <latency> [pipelined|unpipelined]', "
                    f"got: {line!r}"
                )
            try:
                latency = int(parts[3])
            except ValueError:
                raise ValueError(
                    f"FU latency must be an integer, got: {parts[3]!r}"
                ) from None
            if len(parts) == 5:
                flag = parts[4].lower()
                if flag not in ("pipelined", "unpipelined"):
                    raise ValueError(
                        "FU pipelined flag must be 'pipelined' or 'unpipelined', "
                        f"got: {parts[4]!r}"
                    )
                pipelined = flag == "pipelined"
            else:
                pipelined = False
            functional_units.append(
                FunctionalUnit(
                    name=parts[1],
                    kind=parts[2].lower(),
                    latency=latency,
                    pipelined=pipelined,
                )
            )
            continue

        # Instruction line: "OP DEST, SRC1" or "OP DEST, SRC1, SRC2"
        # Split op from the rest.
        space_idx = line.find(" ")
        if space_idx == -1:
            raise ValueError(f"Cannot parse instruction line: {line!r}")
        op = line[:space_idx].strip()
        rest = line[space_idx:].strip()

        # Split operands by comma.
        operands = [p.strip() for p in rest.split(",")]
        if len(operands) < 2:
            raise ValueError(
                f"Instruction must have dest and at least one source: {line!r}"
            )
        dest = operands[0]
        src1 = operands[1]
        src2 = operands[2] if len(operands) >= 3 else ""
        instructions.append(Instruction(op=op, dest=dest, src1=src1, src2=src2))

    return functional_units, instructions


def run(argv: list[str]) -> int:
    """Entry point for the CLI, accepting an explicit argv list.

    Args:
        argv: Command-line arguments (excluding the program name).

    Returns:
        Exit code (0 = success, non-zero = error).
    """
    parser = argparse.ArgumentParser(
        prog="scoreboarding",
        description=(
            "Cycle-exact Thornton Scoreboarding (CDC 6600) simulator. "
            "Reads a program file and prints the pipeline timing table."
        ),
    )
    parser.add_argument(
        "program",
        metavar="FILE",
        help="Path to program text file (or '-' to read from stdin).",
    )
    parser.add_argument(
        "--snapshots",
        action="store_true",
        default=False,
        help="Print per-cycle state snapshots after the timing table.",
    )
    args = parser.parse_args(argv)

    try:
        if args.program == "-":
            text = sys.stdin.read()
        else:
            with open(args.program) as fh:
                text = fh.read()
    except OSError as exc:
        print(f"scoreboarding: error reading file: {exc}", file=sys.stderr)
        return 1

    try:
        functional_units, instructions = _parse_program(text)
    except ValueError as exc:
        print(f"scoreboarding: parse error: {exc}", file=sys.stderr)
        return 1

    if not functional_units:
        print(
            "scoreboarding: no functional units declared"
            " -- add 'FU <name> <kind> <latency>' lines.",
            file=sys.stderr,
        )
        return 1

    if not instructions:
        print("scoreboarding: no instructions found.", file=sys.stderr)
        return 1

    try:
        trace = engine_run(
            instructions,
            functional_units=functional_units,
            capture_snapshots=args.snapshots,
        )
    except (ValueError, RuntimeError) as exc:
        print(f"scoreboarding: simulation error: {exc}", file=sys.stderr)
        return 1

    print(render_trace(trace))

    if args.snapshots and trace.snapshots:
        print()
        for snap in trace.snapshots:
            print(f"-- Cycle {snap.cycle} --")
            for i, ist in enumerate(snap.instruction_status):
                issue_s = str(ist.issue) if ist.issue is not None else "-"
                ro_s = str(ist.read_operands) if ist.read_operands is not None else "-"
                ec_s = str(ist.execute_complete) if ist.execute_complete is not None else "-"
                wr_s = str(ist.write_result) if ist.write_result is not None else "-"
                print(f"  [{i}] Issue={issue_s} RO={ro_s} EC={ec_s} WR={wr_s}")

    return 0


def main() -> None:
    """Entry point installed as the 'scoreboarding' console script."""
    sys.exit(run(sys.argv[1:]))
