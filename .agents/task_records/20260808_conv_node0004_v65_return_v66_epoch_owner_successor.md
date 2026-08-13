# Conv node0004 v65 return → v66 epoch-owner successor

## Scope

- Owner: `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- Return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- Serialized Conv correctness route only.
- Numeric/W3/qparams/tail/workload/config/golden/timeout/backpressure and functional RTL were frozen.
- No server upload, run, lease, ISA, hardware, public-rule, or plan mutation.

## Formal v65 return

- Return: `C:/Users/15383/Downloads/r5_n4_hw_v65_branchcatch_diag_r1786123560502887410_3800700_return.zip`
- Bytes/SHA256: `126114` / `55aa22054535bfe032b62639c36f67cf058b09e84752fe3eeef13a0d186dacd3`
- Source: `r5_n4_hw_v65_branchcatch_diag.zip`
- Source SHA256: `b78e3c7257a34e23fab6cf046922a488c8e1f17356d6dfa6df11234e882a3816`
- Execution: `r1786123560502887410_3800700`
- CRC, one-root safe paths, exact-set, allowlist, per-file receipts, source/reset/install/collector identity: PASS.
- Compile/run/signal: `0/0/NONE`; simulation started.
- Natural terminal: false.
- Formal D expected/present/missing/mismatch: `320/0/320/0`.
- E3/E4/E5: `true/false/false`.

The unique per-execution return basename is a valid collector identity, not a source-package mismatch.

## Qualified adjudication

- LAST_PROVEN_GOOD: `THIRD_DESCRIPTOR_TERMINAL_AND_DESC18_PREPARED18_RECOVER_TO_DELTA0`
- FIRST_DIVERGENCE: `AFTER_THIRD_DESCRIPTOR_TERMINAL_ADDRESS_BRANCH_HAS_NO_COMPLETE_NEW_THREE_INPUT_TUPLE_WHILE_BUFFER_BRANCH_ACCEPTS_TWO_UNMATCHED_GROUPS`

Final qualified snapshot:

- descriptor terminal/descriptor/prepared/delta: `3/18/20/2`
- Memory_AG raw/same/gotten/masked/match/queue-empty: `1/1/7/0/0/1`
- Buffer push/pop: `27/23`
- row/column/Buffer queue/prepared store full: all asserted

The v65 evidence proves the coarse branch boundary but does not reveal the source epoch of each of the three Memory_AG inputs. Shared-LC partial capture, physical LC terminal/keep stop, same/gotten suppression, and Buffer next-epoch early accept therefore remain observationally equivalent. The current `same/gotten` behavior matches the source masking mechanism and is not by itself a proven RTL defect.

Blocker is refined to `B_CONV_NODE0004_MSE4_PER_INPUT_EPOCH_OWNERSHIP_UNOBSERVED`. The historical outbuffer occupancy diagnosis remains `INVALIDATED_NOT_RTL_BUG`.

## v66 continuous-closure successor

- ID: `r5_n4_hw_v66_epoch_owner_diag`
- Classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`
- Candidate release: false
- ZIP bytes/SHA256: `5169182` / `b0f4a0d83a82ccd1b039247da09318a1d9121ae08a9857f268a8568538050d1e`
- Command: `bash r5_n4_hw_v66_epoch_owner_diag/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x`
- Expected return: `/home/panqs/ndp/simresult/r5_n4_hw_v66_epoch_owner_diag_r<epoch-ns>_<pid>_return.zip`

The only new functional surface is a bounded, qualified, same-clock observer that records per-input mode/keep/index/tag and correlates it with physical LC6/8/17/18, Memory_AG raw/same/gotten/masked/match, descriptor/prepared, and Buffer push/pop/full state. Stable levels are not counted as progress.

## Local release evidence

- Deterministic double build: PASS.
- Focused compatible HDL syntax/scope: PASS.
- Declaration deletion and actual-consumer typo negatives: fail closed.
- Candidate×observation matrix: complete for all four remaining causes.
- Predicate trace: stable-level repetition emits no additional progress.
- Family runner/install-only validation: PASS.
- Shared runtime-layout validation: PASS, errors `0`.
- 86/86 SCA matrix/bitstream opens: PASS.
- Normal, preflight-fail, compile-fail, HUP, INT, TERM finalizers: PASS.
- Early runner error visibility and return-collision preservation: PASS.
- Return/result collector contract: PASS.
- Final ZIP current-rule self-audit: PASS, errors `0`.

Machine report: `outputs/conv_node0004_v65_return_v66_successor/release_report.json`.

## Storage rotation

- v65 was moved intact to `tested/conv_serialized_node0004/r5_n4_hw_v65_branchcatch_diag`.
- The only serialized-Conv pending ZIP is
  `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_hw_v66_epoch_owner_diag.zip`.
- Post-rotation storage audit: PASS.
- Storage receipt:
  `outputs/conv_node0004_v65_return_v66_successor/storage_receipt.json`.

## Rule feedback

`RULE_CONFIRMATION=CURRENT_RULES_SUFFICIENT`. Existing no-sidecar transport, hang-first, time-to-root-cause, qualified-observability, install-only layout, focused HDL/actual-consumer negative, finalizer, fixed-result and continuous-closure rules were sufficient. No non-synonymous rule delta is proposed.
