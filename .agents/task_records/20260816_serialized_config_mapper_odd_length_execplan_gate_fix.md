# Serialized config mapper odd-length execplan gate fix

- date: 2026-08-16
- source family: `family.conv.serialized`, owner epoch 2, registry epoch 6
- classification: existing config-length semantics implementation escape
- public rule delta: none

## Adjudication

The native planner and the existing checked-in config-length contract agree that
`Load_Config.config_length` counts meaningful 64-bit words. A 128-bit transport
row carries two 64-bit words, except that an odd final word is paired with an
all-zero high-half transport pad. The former shared validator incorrectly
counted every 128-bit row as two meaningful words and therefore rejected the
serialized mapper candidate's valid 71-word payload as 72 words.

## Fix

`OperatorConfigExecPlanValidator` now derives the programmed length from the
hash-bound `modules_dump_64b.bin`, independently reconstructs the exact 128-bit
transport, and accepts odd length only when the final high half is all zero.
It fails closed on nonzero padding, undercount, overcount, missing 64-bit
identity, or 64/128 identity drift.

## Validation

- focused validator regression: 12/12 PASS
- validator plus execplan-evidence regression: 16/16 PASS
- Python compile: PASS
- serialized A baseline: 70 meaningful words / 35 transport rows / PASS
- serialized B candidate: 71 meaningful words / 36 transport rows with zero
  high-half padding / PASS

Machine report:
`outputs/serialized_config_mapper_odd_length_gate_v1/report.json`

No family package was built or published. No managed storage, server, RTL,
functional config, numeric, workload, golden, plan or owner-registry action was
performed. The serialized family must rerun all remaining current-disk gates
before it may release a fresh targeted successor.
