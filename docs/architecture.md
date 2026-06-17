# Architecture: Thornton's Scoreboarding Algorithm

## Overview

Scoreboarding is the dynamic instruction scheduling technique implemented in the
CDC 6600 (1964), designed by James Thornton. It allows instructions to execute
out of order while preserving correctness -- without register renaming.

The central insight is to replace the simple stall-on-hazard pipeline with a central
scoreboard that tracks every in-flight instruction across three tables and enforces
hazard conditions per stage.

## The Three Tables

### 1. Instruction Status

Records the cycle at which each instruction completed each of the four stages:

| Field             | Type      | Description                              |
|---|---|---|
| issue             | int/None  | Cycle when instruction was issued        |
| read_operands     | int/None  | Cycle when both source registers were read |
| execute_complete  | int/None  | Cycle when execution finished            |
| write_result      | int/None  | Cycle when result was written            |

### 2. Functional Unit Status

One row per physical functional unit:

| Field          | Type       | Description                                                  |
|---|---|---|
| busy           | bool       | Whether the unit is currently occupied                       |
| op             | str        | Operation being performed                                    |
| fi             | str        | Destination register                                         |
| fj, fk         | str        | Source register names                                        |
| qj, qk         | str/None   | Name of FU that will produce fj/fk (None = already ready)   |
| rj, rk         | bool       | True when fj/fk are ready to read (not yet consumed)        |
| execute_start  | int/None   | Cycle when execution began (None until operands read)        |

### 3. Register Result Status

Maps each register name to the name of the functional unit that will next write it,
or `None` if no pending write exists (the register holds its committed value).

## The Four Pipeline Stages

### Stage 1: ISSUE (in order)

An instruction may issue to a functional unit in the current cycle only if:

1. **No structural hazard**: the required functional unit (`kind` matching `op`) is
   not currently busy (its `busy` flag is False).
2. **No WAW hazard**: no currently-active instruction (issued but not yet at
   WriteResult) is writing the same destination register.

If either condition fails, the instruction stalls, and no later instruction may issue
(in-order issue constraint).

On a successful issue:
- The FU is marked busy; `op`, `fi`, `fj`, `fk` are recorded.
- For each source register, if `RegisterResultStatus[src]` is non-None, set
  `qj`/`qk` to that FU name and `rj`/`rk` to False. Otherwise set `qj`/`qk` to
  None and `rj`/`rk` to True (operand immediately available).
- `RegisterResultStatus[dest]` is set to this FU name.

### Stage 2: READ OPERANDS

An issued instruction reads both source operands when both are available. The
operand for source j (or k) is available when:
- `qj` (or `qk`) is None -- no pending write to that source.
- `rj` (or `rk`) is True -- the operand has not yet been consumed.

Once both conditions hold, the instruction records `read_operands = current_cycle`.
The `rj` and `rk` flags are then set to False (operands consumed), and execution
starts the following cycle.

This stage resolves **RAW (read-after-write)** hazards: an instruction naturally waits
here until the producing instruction has written and cleared the Qj/Qk pointer.

### Stage 3: EXECUTE

The instruction occupies its functional unit for exactly `latency` cycles starting the
cycle after `read_operands`. `execute_complete` is recorded when the full latency has
elapsed.

### Stage 4: WRITE RESULT

Before writing its result, the instruction checks for a **WAR (write-after-read)**
hazard: no earlier-issued instruction may still be waiting to read a source register
that equals this instruction's destination.

Concretely, for every other instruction j that:
- was issued before this instruction (earlier issue cycle), AND
- has not yet completed ReadOperands (its `rj` or `rk` flag is still True for this
  instruction's destination register),

the WriteResult is stalled until those reads complete.

Once the WAR check passes:
- `write_result = current_cycle` is recorded.
- `RegisterResultStatus[dest]` is cleared to None (if this FU is still the listed
  producer).
- The `Qj`/`Qk` fields of any other instruction that listed this FU as a producer
  are cleared (set to None), and their `Rj`/`Rk` flags are set to True.
- The functional unit is freed (all fields reset to idle).

## Hazard Summary

| Hazard | Stage where enforced | Effect |
|---|---|---|
| Structural | Issue | Stalls Issue until FU is free |
| WAW | Issue | Stalls Issue until conflicting write completes |
| RAW | Read Operands | Stalls ReadOperands until producing FU writes |
| WAR | Write Result | Stalls WriteResult until all earlier readers have read |

## Contrast with Tomasulo's Algorithm

| Property | Scoreboarding | Tomasulo (see `tomasulo` package) |
|---|---|---|
| Issue order | In order (program order) | In order (program order) |
| Execution order | Out of order | Out of order |
| Register renaming | No | Yes (via reservation station tags) |
| WAW resolution | Stall Issue | Eliminated by renaming |
| WAR resolution | Stall Write Result | Eliminated by renaming |
| RAW resolution | Stall Read Operands | Stall in reservation station |
| Result broadcast | No bus -- scoreboard polls | Common Data Bus (CDB) broadcast |
| Multiple FUs of same kind | Allowed | Allowed |
| Precise exceptions | Yes (in-order commit) | Requires reorder buffer |

Scoreboarding is simpler to implement but wastes cycles on WAW and WAR hazards that
Tomasulo eliminates through renaming. Tomasulo's CDB approach also removes the polling
overhead of the scoreboard.

## Implementation Notes

The engine (`src/scoreboarding/engine.py`) processes all four stages within each cycle
in a specific order to model the within-cycle interactions correctly:

1. WriteResult (may free an FU that the same-cycle Issue check will see as free).
2. Read Operands (operands become available from this cycle's WriteResult).
3. Execute Complete (tracks latency from the previous cycle's ReadOperands).
4. Issue (uses the FU availability state after WriteResult).

This ordering ensures that a WriteResult in cycle N and an Issue in cycle N of the same
FU is possible -- matching the CDC 6600's microarchitectural behavior.
