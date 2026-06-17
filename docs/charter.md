# Project Charter: scoreboarding

## Purpose

`scoreboarding` provides a cycle-exact, pure-Python implementation of Thornton's
Scoreboarding algorithm (as used in the CDC 6600, 1964) for computer architecture
education. It is the in-order companion to the `tomasulo` package.

## Goals

1. Correctness above all -- every cycle stamp must be derivable by hand from the
   algorithm's rules. The test suite documents the derivation.
2. Zero runtime dependencies -- install anywhere Python 3.10+ is available.
3. Pedagogical clarity -- the source code mirrors the three-table description from
   Thornton's original paper, with comments explaining each stage check.
4. Tested release quality -- mypy strict, ruff clean, 50+ unit tests.

## Non-goals

- Register renaming (that is Tomasulo; see `tomasulo` package).
- GUI or interactive visualizations.
- Simulating real ISAs (MIPS, x86, RISC-V) -- the model is intentionally abstract.
- Superscalar issue or multi-issue per cycle.

## Scope

The public API is `FunctionalUnit`, `Instruction`, `run()`, `render_trace()`, and
the `scoreboarding` CLI. The engine (`engine.py`) implements exactly the four-stage
scoreboard algorithm with the three classic tables.

## Relationship to sibling projects

- `tomasulo` -- out-of-order with register renaming and a Common Data Bus.
- `spikegen` -- unrelated (spike-train generation for neuroscience).
