# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/amaar-mc/scoreboarding/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/amaar-mc/scoreboarding/releases/tag/v0.1.0
