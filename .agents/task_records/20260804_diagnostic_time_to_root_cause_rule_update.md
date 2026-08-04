# Diagnostic time-to-root-cause rule update

Date: 2026-08-04

Mainline: `019fbec2-fe93-7e03-9314-cff6f222f33d`

## User correction

The user clarified that a diagnostic successor should locate the root cause as
quickly as possible and may discard unnecessary simulation work.  The previous
wording “最窄诊断包 / 最小观测” could be read as:

- one new signal or one leaf per server run;
- preserving every frozen stage/payload even when it cannot affect the current
  first divergence;
- optimizing ZIP/probe size instead of information gained per server wall-clock.

That interpretation is rejected.

## Formal adjudication

The stable objective is now:

```text
minimize time-to-root-cause
subject to exact reproduction of the causal execution slice
and fail-closed provenance / E4-E5 claim boundaries
```

A diagnostic successor must combine all low-cost qualified observations that
can distinguish the remaining candidates in one run.  It must also audit and,
where legal, remove stages, slices, payload, formal readback and observers that
do not participate in reproducing or distinguishing the current
`LAST_PROVEN_GOOD → FIRST_DIVERGENCE`.

Internal tensors may not be synthesized or replayed by the host.  If there is
no legal graph-external input, verified hardware checkpoint or approved
diagnostic stimulus, the package must retain the shortest cumulative hardware
prefix.  Pruning must not change pre-divergence config, addresses, request
ordering, backpressure, timing, barriers or lifetime.

New public rule:

- `CDA-SERVER-DIAGNOSTIC-TIME-TO-ROOT-CAUSE-OPTIMIZATION-001`

## Changed public files

| path | previous SHA256 | current SHA256 |
|---|---|---|
| `.agents/agent.md` | `d9fe95839c2c92a83083d956392a66876c1007fbb7922522c6a8920babab6721` | `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f` |
| `.agents/rules/生成前必读索引.md` | `db339fb8f47105b76deef85cdd43cfc85af6358a0c8155571fde54c2006f26c5` | `5146225e549942c4e25780ac4fc0120d7cac1ef355879284450dad2e48df237b` |
| `.agents/rules/服务器测试包生成规则.md` | `5761987d07f425a316bd845e390405c0c64d78c9a371b9cce22cc491c8f25f48` | `0916c655b0581cd99836d8cc1561a3f41b15b25e861692d596a4789c039b090e` |

The server rule now requires:

1. a candidate-by-observation discrimination matrix;
2. one-run aggregation of bounded low-cost qualified events;
3. an explicit causal execution slice;
4. a `diagnostic_execution_reduction` keep/drop exact-set with provenance and
   expected runtime reduction;
5. fail-closed controls for deletion of a required prefix/boundary or mutation
   of boundary provenance;
6. a full-chain E4/E5 run after the diagnostic/fix path.

## GAP v33 confirmation

The GAP owner consumed the correction while building the v32 successor.
`r5_n71_gap_v33_buffer_ag_idx_pair_diag` combines COL-LC0, both MSE0 queue
inputs, tag/index/match-mask, all-matched, enqueue/dequeue and the direct
consumer in one bounded feature (`<=256` qualified events).

Its execution-reduction audit found:

- no legal typed checkpoint before the first divergence;
- `sum_s1` is already the first stage;
- later stages never start during the observed hang.

Therefore deleting later-stage assets would not reduce dynamic runtime and
could weaken provenance.  The package correctly records `drop=[]` with an
evidence-based non-prunable reason.  This is compliant with the new rule:
pruning is required when it saves causal execution, not when it only makes the
archive smaller.

GAP v33 machine report:

- `artifacts/operator_config_validation/r5-gap-node0071-v32-return-v33-successor/report.json`
- SHA256=`0c37f937316dfc09215f632a2d700b8607de665028d9b75d2057b88dc43d7676`

## Boundaries

No functional RTL, numeric, workload, config, golden or existing package bytes
were modified by the mainline rule update.  Operator owners still cannot edit
public rules or the mainline plan.  Upload and server execution remain
separately authorized actions.
