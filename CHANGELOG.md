# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-06-23

### Added
- Pipelined vs unpipelined functional units. `FunctionalUnit` now takes a required
  keyword `pipelined` flag. An unpipelined unit (the classic CDC 6600 behaviour)
  stays busy from Issue until Write Result, so a same-kind successor stalls at Issue
  until the occupant writes back. A pipelined unit releases its issue slot once the
  occupying instruction reads operands, letting a successor issue while the deep
  execute pipeline still carries the earlier result.
- CLI grammar extended: `FU <name> <kind> <latency> [pipelined|unpipelined]`. The
  fifth token is optional and defaults to `unpipelined`.
- Golden cycle-accurate tests for pipelined back-to-back issue, three-deep pipelined
  issue, the producer-disambiguation broadcast, and the unpipelined structural-stall
  contrast.

### Changed
- Execution timing is now tracked per instruction rather than on the shared
  Functional Unit Status row, so a pipelined unit can correctly hold several
  in-flight instructions at once. The Write Result broadcast wakes a waiting consumer
  only when the producer's destination matches the consumer's source register.
- All existing golden traces are unchanged: an all-unpipelined configuration is
  cycle-for-cycle identical to 0.1.0.

## [0.1.0] - 2026-06-17

### Added
- `FunctionalUnit`, `Instruction`, `Trace`, `InstructionResult`, `CycleSnapshot` data
  model in `src/scoreboarding/model.py`.
- Cycle-exact Scoreboarding engine in `src/scoreboarding/engine.py` implementing all
  four stages (Issue, Read Operands, Execute, Write Result) with structural, RAW, WAR,
  and WAW hazard detection.
- `render_trace()` timing-table renderer.
- `scoreboarding` CLI with `--snapshots` flag for per-cycle state dumps.
- 50 tests covering golden trace, in-order issue invariant, all four hazard types,
  simulation termination, and error handling.
- `examples/classic.txt` -- the classic CDC 6600 floating-point scheduling example.
- CI on Python 3.10, 3.11, 3.12, 3.13 via GitHub Actions.

[Unreleased]: https://github.com/amaar-mc/scoreboarding/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/amaar-mc/scoreboarding/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/amaar-mc/scoreboarding/releases/tag/v0.1.0
