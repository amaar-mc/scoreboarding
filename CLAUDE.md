# CLAUDE.md -- scoreboarding

## Project

Pure-Python cycle-exact Thornton Scoreboarding (CDC 6600) simulator.
Companion to `tomasulo` (out-of-order with register renaming).

## Layout

```
src/scoreboarding/
  model.py      -- dataclasses: FunctionalUnit, Instruction, FunctionalUnitStatus,
                   InstructionStatus, InstructionResult, CycleSnapshot, Trace
  engine.py     -- the simulation engine (four stages, three tables)
  render.py     -- render_trace() timing-table formatter
  cli.py        -- scoreboarding CLI: run(argv) + main()
  __init__.py   -- public API re-exports
  py.typed      -- PEP 561 marker
tests/
  test_engine.py  -- golden trace + all hazard invariants (30 tests)
  test_cli.py     -- CLI parse + run tests (14 tests)
  test_render.py  -- render output tests (6 tests)
```

## Dev gates (must all pass)

```bash
uv run pytest -q
uv run ruff check .
uv run mypy src
uv build
uv run --with twine twine check dist/*
```

## Key constraints

- mypy strict: no `Any`, no missing annotations.
- No default parameter values in public API; use keyword-only args.
- No em dashes in source or docs (use -- or plain dashes).
- No TODO/FIXME in code.
- ruff: line-length=100, selectors E,F,I,UP,B,SIM,RUF.
- Zero runtime deps.

## Algorithm

Four stages: Issue (structural + WAW check), Read Operands (RAW wait),
Execute (latency countdown), Write Result (WAR check then broadcast).
See docs/architecture.md for the full description.

## PyPI

Not yet published (quota exhausted at initial release). `uv build && twine check dist/*`
to validate the distribution. Publish when quota resets.
