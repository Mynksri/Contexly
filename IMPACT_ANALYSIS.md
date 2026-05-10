# Impact Analysis Guide

Contexly impact analysis helps you estimate downstream breakage before changing a function.

## Command

contexly impact [path] <function_name> [file_hint] [--depth N] [--dataflow]

## What It Shows

- Direct callers with confidence labels (HIGH, MED, LOW)
- Indirect impact up to selected hop depth
- Optional dataflow summary (configs, classes, state fields)
- Optional side-effects summary (API, database, file-write, telegram, blockchain)
- Final summary line:
  X files affected | Y high impact | Z potential breaks

## Flags

- --depth N
  Controls indirect traversal depth.
  Typical values:
  - 1: direct impact only
  - 2: direct + one transitive ring
  - 3: deeper multi-file propagation

- --dataflow
  Adds a dataflow/side-effects section for faster risk assessment.

## Examples

contexly impact . execute_trade
contexly impact . execute_trade trade_executor.py
contexly impact . run_coin_round --depth 3 --dataflow

## Suggested Workflow

1. Build or refresh index
   contexly tree .

2. Run impact preview before editing
   contexly impact . <function> --depth 2 --dataflow

3. Edit target function

4. Re-check impact and run query for changed behavior
   contexly impact . <function> --depth 2
   contexly query . "<behavior or bug>" 2 1

## Notes on Confidence

- HIGH: direct call-chain evidence from structured call graph
- MED: reverse call traces from skeleton call lines
- LOW: symbol mention fallback only

Treat LOW entries as "verify manually" candidates.

## Tree Requirement

Impact analysis runs on the indexed tree representation.
If a tree is missing, Contexly auto-builds it.
If a tree already exists, cached data is reused for speed.
Use --rebuild globally if you want a guaranteed fresh view.
