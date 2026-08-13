# Requant Conv53 lane-phase serialization isolated proof

## Scope and stop gates

- Family: `RequantizeUint8 / AverageRequant`
- Mainline return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- Authorization: B-only, existing-primitive slow-composite field proof.
- No target strict JSON, handler mutation, backend, mapping, bitstream,
  execplan, SCA, package, ZIP, upload, server run, lease, RTL/ISA change, or
  active ndp-sim change was performed.
- The prior 5PE numeric proof was consumed and was not recomputed.

## Mandatory-read receipts

| Path | SHA256 |
|---|---|
| `.agents/agent.md` | `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f` |
| `.agents/plan.md` at task start (mutable provenance) | `de7a956c8466b58004d14ffd66475c9cde8937e2cdb91184ce2b5d047160a6da` |
| `.agents/plan.md` at receipt write (mutable provenance) | `d1aeb4b3f99b998cd60b9e5e1bdc5a29592d340ade49f62e46d10fcdf1f00a7a` |
| `.agents/rules/生成前必读索引.md` | `3c0c9d5e836e2ea9cb7d697252fe2f46dfd5cce8facfdbd332d8bbd3d0fe48cc` |
| `.agents/rules/算子配置规则.md` | `dc5243226bacde799b368d37fb9eb656e6b7e3d33a0a2932ae72ab35415ae3e1` |
| `.agents/rules/RequantizeUint8算子配置规则.md` | `d2caeb55222f5b47585d890875e4d8f3f5c17d17a6849a93af4366e9f3447f99` |
| `.agents/rules/精确UINT8量化尾专项规则.md` | `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e` |
| `.agents/rules/最小双Stage生命周期规则.md` | `821b8b04b0e33d0a93e06a3a1bca8307b417bcb63f109cf12414891e9a0bc171` |

The plan drifted while this family task was running. It is recorded only as
mutable provenance; no plan or rule file was edited by this task.

## Isolated-worktree receipts

The proof tool creates fresh local Git clones with `--local --no-hardlinks`
under a temporary directory, checks that each clone is clean, performs all
field/source-equation checks there, then removes the temporary clones.

- isolated ndp-sim HEAD: `ec12424516ae0304228dd2321d4e604fe225e04e`
- isolated Trassic2.0_RTL HEAD:
  `0ccae916ef61904a64d6cf8ec1d1931b45e428d8`
- both isolated clone status counts: `0`
- active ndp-sim/RTL writes: `0`

Pinned native source anchors:

| Path | Git blob | SHA256 |
|---|---|---|
| `ndp-sim/jsons/decode_max_fp32N_fp32N.json` | `4cd761a7b8a68f6de47987f3076f05aa944951f3` | `ab73710698892ed8e1062e4b5ac66fe310f99609dac89ea96ce8fa6e4bd3a1c2` |
| `ndp-sim/jsons/prefill_mul_fp32MN_fp32M_fp32MN.json` | `9916da4c6d051c702d9ada15aeb604eedb367c18` | `db66d5e8da6146eb743fe1006a6248daf040ba937d713a99f961c591325a272f` |

The report also records blob/SHA receipts for each RTL equation source.

## Result

Status:
`PROVEN_AT_EXISTING_HARDWARE_FIELD_EQUATION_LEVEL`.

The existing fields can express the missing Conv53 multiplier supply without a
dynamic lane mux by changing the slow composite to channel-temporal scalar
transport:

1. For channel `c`, read exactly four bytes at `B_base + 4*c`.
2. Use buffer column `0`, `buf_spatial_stride=[0,1,2,3]`, and
   `buf_spatial_size=4`, placing the exact FP32 payload in buffer2 bank0.
3. Set buffer2 and GA inport1 masks to lane0 only.
4. Route GA inport1 lane0 to PE00 inport1.
5. Use the already-proven PE00 keep mechanism to retain `B[c]` across that
   channel's serialized occurrence loop, then clear/reload bank0 for `c+1`.

This is a composition of two current native mechanisms:

- `decode_max_fp32N_fp32N.json` proves scalar 4-byte
  memory-to-bank0-to-GA-lane0 temporal transport.
- `prefill_mul_fp32MN_fp32M_fp32MN.json` proves the
  B/buffer2/GA-inport1/PE00-keep route.

The composition is checked against current RTL equations and is not claimed as
an exact native JSON replay.

Coverage is 53/53 Conv stages. Channel-count classes are:

- C=64: 7
- C=128: 8
- C=256: 16
- C=512: 11
- C=1024: 7
- C=2048: 4

All LC/index/stride/address capacity checks pass. For every stage,
`(4*c) mod 16` is one of `{0,4,8,12}`, so no 4-byte multiplier transaction
crosses a 16-byte memory beat.

The historical node0001 counterexample remains explicit: the original 8-wide
fields route channel1 `0x3925d60c` to PE10 rather than PE00. The slow-composite
proof does not reinterpret or waive that failure; it avoids it by issuing each
channel as a separate lane0 scalar transaction. No one-round FMA, approximate
tail, or magic-wrap shortcut is used.

## Validation

Tool:

- `tools/prove_requant_lane_phase_serialization_isolated_v1.py`
- SHA256:
  `b108f2dd80eb1fb68d0c5682972d92a28e770fd1f338319d6f9689b051284040`

Tests:

- `tests/test_requant_lane_phase_serialization_isolated_v1.py`
- SHA256:
  `09a991060d147ef458d7c96f0d665bb3336a65047a0ab73829b542e63f84c3b2`

Commands and results:

1. Fresh isolated proof:
   `python.exe tools/prove_requant_lane_phase_serialization_isolated_v1.py --output artifacts/operator_config_validation/requant_lane_phase_serialization_isolated_v1/report.json`
   — exit `0`, `pass=true`, structural errors `0`, Conv coverage `53/53`.
2. Unit/negative controls:
   `python.exe -m unittest tests.test_requant_lane_phase_serialization_isolated_v1 -v`
   — exit `0`, `2/2 PASS`.
3. Negative controls fail closed when the scalar template
   `buf_spatial_size` is changed from `4` to `16`, and when channel count is
   changed to `2^17`.

Machine report:

- `artifacts/operator_config_validation/requant_lane_phase_serialization_isolated_v1/report.json`
- SHA256:
  `1fa2ad8e55be5e4d67e11b2001386dd8a92dafef61da6bb9883d8ea9a68c75ba`

## Structured deltas

### RETURN_ANALYSIS

- Field expressibility: proven for all 53 Conv Requant stages.
- Mechanism: eight scalar channel phases per former 8-wide channel group,
  transported to `PE00.inport1`; end-to-end performance was not measured.
- Claim level: source-equation/field capability only.
- Target strict/backend/dynamic status: not entered.

### BLOCKER_DELTA

Close only at field-equation level:

- `B_REQUANT_CONV53_MULTIPLIER_LANES_1_TO_7_NOT_SERIALIZED_TO_PE00_INPUT1`

Open replacement gates:

- `B_REQUANT_CONV53_SCALAR_PHASE_STRICT_MATERIALIZATION_AND_BACKEND_BINDING`
- `B_REQUANT_CONV53_SCALAR_PHASE_DYNAMIC_EXECUTION`

Unchanged:

- sequential multiply-to-RNE exact tail;
- integer zero-point and saturation tail;
- magic-wrap counterexample domain;
- all target strict/backend/package/server gates.

### RULE_DELTA_PROPOSAL

`NONE_NON_SYNONYMOUS`. Current rule already requires exact per-occurrence
multiplier supply and fail-closed physical proof; this result satisfies one
narrow proof obligation without requiring a semantic rule change.

### PACKAGE_RELEASE

`NONE`.
