# RequantizeUint8 P1-B shared UINT8 quant-tail evidence input

Date: 2026-07-27  
Owner task: `019fa2bf-95cd-7502-82c8-6a48cf12d648`  
Mainline return target: `019fa2ca-72bc-7753-8d58-81e59bc76c88`

## Scope and stop gates

This task only reorganizes existing RequantizeUint8 / AverageRequantizeUint8
evidence into a machine-readable input for the QuantizeLinear-owned P0-A exact
UINT8 quant-tail. It does not emit an operator target JSON, mapping, bitstream,
execplan, SCA, server package, or dynamic probe.

- Frozen event-edge packages were not modified.
- No server root or server file was inspected, uploaded, or run.
- No functional RTL, `.agents/plan.md`, or `.agents/rules/**` file was changed.
- This record and its JSON contract do not count as E4 or E5 and do not
  authorize a formal target instance or candidate release.

## Required source receipts

| Input | Size | SHA256 |
|---|---:|---|
| `.agents/plan.md` | 23239 | `d42a3ac6208f4198fdcd17cc569a156fbc7906661618dca59e3d43147f887e35` |
| `.agents/task_records/20260727_ndpsim_resnet50_reuse_audit_and_replan.md` | 6913 | `dfd12a4e45c79ee51d104f939a7b8f07b7a5b4e94df62e54dfb395f9d5e9235f` |
| `contracts/operator_config/resnet50_ndpsim_reuse_gap_audit_v1.json` | 13275 | `ca3daf485f4098793e1c4544139c22e62119dbe5743e0db02e4e07d7c301c7c5` |
| `.agents/task_records/20260727_exact_uint8_quant_tail_capability_matrix.md` | 5545 | `cc8cc0f9e4a993d6de7c21f86a54a62d6eeb6cb75c453d73b343bf044f30a754` |
| `contracts/operator_config/exact_uint8_quant_tail_capability_v1.json` | 16165 | `ba966e2d78bb38e162fdc7cc2e31fd5418914423ae1eb9e694f8789df158cddb` |
| `.agents/rules/生成前必读索引.md` | 6200 | `6ae4c7fe09fcdb39a48357cfef645c272f67e7a81d09b5547ebd9a929e6ce1a4` |
| `.agents/rules/精确UINT8量化尾专项规则.md` | 5186 | `5593f9df3bbc5605e9b019b6cc53ee33b0edbeb203d657fdf974cb4b680c2df0` |
| `.agents/rules/RequantizeUint8算子配置规则.md` | 33778 | `d9ec14cc6975e9596f3fe56e762cd4797c8ba6c70fa235503f5954e97c6f863f` |
| `artifacts/operator_config_validation/r5-requant-family-classification-v1/report.json` | 146668 | `547245ecd125c94a0430a0ffe13f5949494f61119383524029b0e5a72f60e539` |
| `artifacts/operator_config_validation/r5-requant-node0001-two-stage-e2-v1/local_e2_report.json` | 230039 | `29b24ba2c0ca48348adb7e2c2b7a05508324474f506f0cabcadc1ded4f121990` |
| `artifacts/operator_config_validation/r5-requant-zero-point-shape-holdouts-v1/analysis.json` | 8865 | `9ab7c724266c7ae9f61bceaf3f2001be5a99bcd06564c989a444934fb08d9259` |
| `contracts/typed_config_parameter_contract.json` | 1619185 | `abbc87b0b13c92611a90fe1767b32b15fe9c49f23bee616ca2bb51219dd181bd` |
| `artifacts/reference_model/resnet50-v1-12-int8.onnx` | 25816052 | `c234f30975989788b4405f25253275aae247ab6dbdd34aaa69ab0a59ff76f6d0` |

The plan receipt differs from the earlier package-adaptation dispatch receipt
because the mainline was replanned. The current on-disk SHA above is the
read-time authority for this task. The machine contract separates mutable
control-plane read receipts from fail-closed semantic source receipts; a later
plan edit does not silently rewrite this historical receipt or invalidate the
numeric evidence.

The mandatory-read index, shared exact UINT8 quant-tail rule and Requant family
rule are active, fail-closed semantic receipts. The shared rule approves the
four P0-A fail-closed rules. The narrowed
`CDA-REQUANT-ROUND-MAGIC-001` only approves node0001 on its formal W3 input
domain as a conditional local E2; it does not close the shared FMA rounding
capability.

## RETURN_ANALYSIS

Status:
`P1B_REQUANT_EVIDENCE_READY_FOR_P0A_QUANT_TAIL`.

Closed evidence totals:

- 54/54 RequantizeUint8 stages reproduce W3 golden exactly with the standard
  order.
- 33 stages have `y_zero_point=0` and are numerically compatible with the
  current node0001 guard recipe.
- 21 stages have nonzero `y_zero_point` and all 21 contradict that guard recipe.
- Of the 21 nonzero stages, 16 have even and 5 have odd zero-point.
- Only `r5:hwop-0001-01` has a physical, config-bound local E2.
- Formal dynamic pass count remains zero.

Normative evidence equation:

`clip_uint8(rne(float32(int32_input) * float32(multiplier)) + int(y_zero_point))`

The zero-point is added after nearest-even rounding, in the integer domain.
Clamping the signed accumulator before scaling is not exact for arbitrary
nonzero zero-point. Adding odd zero-point inside the FP32 magic-round expression
can change tie parity.

P0-A dependency refinement:

- Shared decision is `NO_UNCONDITIONAL_PURE_CONFIG_PROVEN`.
- First hardware unknown is
  `CE_FMA_VS_SEQUENTIAL_ROUND`: `int32=400`,
  multiplier bits `0x3d828f5c`, `zp=0`; sequential FP32 multiply then RNE
  yields 26, while a one-round fused magic model yields 25.
- All 33 zp0 stages remain blocked for formal release by
  `B_QUANT_TAIL_FMA_ROUNDING_POINT` and
  `B_QUANT_TAIL_MAGIC_DOMAIN_BOUND`. All 33 also contain negative W3
  accumulators; their zp0 guard is a conditional numeric workaround, not a
  released shared signed-ingress route. This includes node0001 despite its
  physical local E2.
- The 21 nonzero stages split into 16 even-zp stages blocked by signed ingress,
  rounding and finite-domain gates, and 5 odd-zp stages blocked by those gates
  plus zero-point-after-RNE/tie parity.
- `CE_FP32_DIVISION_VS_RECIPROCAL_FMA` is a shared QuantizeLinear dependency,
  not a classifier for the 54 Requant multiplier paths. It prevents Requant
  evidence from being extrapolated into FP32 division closure.

Counterexample coverage:

- Signed-domain guard loss: one W3 counterexample is recorded for each of the
  21 nonzero-zero-point stages.
- Tie/parity: node0014, `y_zero_point=123`, has 32 W3 mismatches; the first
  exact sample is `scaled=4.5`, standard output 127, old magic output 128.
- Saturation: all W3 stages contain 24,128,384 lower-clip and 80 upper-clip
  occurrences. The nonzero-zero-point subset contains 80 upper-clip but zero
  lower-clip occurrences. The contract records this absence and does not label
  a synthetic input as W3 evidence.
- MatMul requant `r5:hwop-0075-01` has `y_zero_point=60`, exact standard W3
  replay, 8,272 guard mismatches, and a separate rank-2 layout gap. Its even
  zero-point explains only the lack of an observed odd-tie mismatch; it does
  not validate the signed-domain guard.

Problem classification:

| Class | Count/scope | Classification |
|---|---|---|
| Nonzero zero-point Requant | 21 | Numeric recipe gap first; physical materialization deferred |
| Other zero-point-zero Requant | 32 | Numeric recipe compatible; only per-shape physical materialization remains |
| node0001 | 1 | Numeric exact plus physical local E2; no dynamic/E4/E5 claim |
| MatMul output requant | 1 of the 21 | Numeric signed-domain gap plus independent rank-2 layout gap |
| AverageRequant/GAP tail | one composite consumer | zp0 numeric tail reusable conditionally; sum transport, address, accumulator state and lifetime remain physical/composite gaps |

Shape/layout, transaction and lifetime are independent of the numeric proof:
rank-4 HWC8 materialization for node0001 cannot authorize other shapes, rank-2
MatMul cannot inherit HWC8, forecast shard/stage counts are not emission
authority, and only node0001 has the stage0-D to stage1-A alias/barrier/SCA
lifetime proof.

The four zero-point-zero shape holdouts remain
`LOCAL_E2_PLANNING_ONLY`, lower priority than the shared quant-tail, with no
operator JSON produced.

## QUANT_TAIL_EVIDENCE_INPUT

QuantizeLinear owner may consume:

1. 54 exact INT32-input W3 oracles and their qparam identities.
2. The exact multiply -> nearest-even -> integer zero-point add -> UINT8
   saturation order.
3. Per-stage signed-domain, observed tie/parity, and saturation evidence.
4. node0001 as a zero-point-zero rank-4 physical E2 transport oracle.
5. MatMul `y_zero_point=60` as an explicit example of the numeric/layout split.

QuantizeLinear owner must not infer:

1. FP32 ingress closure from this INT32-ingress family evidence.
2. Generic nonzero-zero-point support from the node0001 guard.
3. Rank-2 layout or another rank-4 shape from node0001 HWC8.
4. Shape schedule, transaction count, address alias, or lifetime from numeric
   W3 exactness.
5. E4/E5, server release, or a formal target instance.

Machine-readable contract:

- `contracts/operator_config/requant_quant_tail_evidence_input_v1.json`
- file size: 301782 bytes
- file SHA256:
  `64aec997e9188ed69a0f0062dd9f66c5377d772fdc8b598dd1b8aa038a036f07`
- semantic self-hash:
  `0530d34ed53d09b785dd81afa119dfc286ba9f1cba596361ecc388b1d2e05d6b`

Generation receipt:

- `artifacts/operator_config_validation/r5-requant-quant-tail-evidence-input-v1/generation_receipt.json`
- file size: 4583 bytes
- file SHA256:
  `5f2219b69ec2372ce286a132d1fa6f07e8318798c2e5c0f1c3deed40125c9651`
- receipt self-hash:
  `665d356d52303f52b490590eea7b87f242d556dbaebecbd8c51b913430e03a53`

## RULE_DELTA_PROPOSAL

Proposal only; no rule file was changed.

1. `CDA-QUANT-TAIL-RNE-ADD-ZP-SATURATE-001`: exact UINT8 tails perform
   FP32 multiply, nearest-even rounding, integer zero-point addition, then
   UINT8 saturation, in that order.
2. `CDA-QUANT-TAIL-NUMERIC-PHYSICAL-SPLIT-001`: numeric recipe closure does
   not authorize shape/layout/transaction/lifetime materialization.
3. `CDA-QUANT-TAIL-INGRESS-TYPED-001`: INT32 and FP32 ingress variants require
   separate typed capability evidence.

The P0-A mapping adds no further family-local rule proposal. Mainline has now
approved `CDA-QUANT-TAIL-NUMERIC-ORDER-001`,
`CDA-QUANT-TAIL-ZP-AFTER-ROUND-001`,
`CDA-QUANT-TAIL-MAGIC-DOMAIN-001`, and
`CDA-QUANT-TAIL-CAPABILITY-MATRIX-001`; all four are bound through the active
shared-rule receipt.

## BLOCKER_DELTA

Close: none.

Keep:

- `B_REQUANT_NONZERO_ZP_SIGNED_DOMAIN`
- `B_REQUANT_MAGIC_ZP_TIE_PARITY`
- `B_REQUANT_MATMUL_2D_LAYOUT`
- `B_REQUANT_SHAPE_LIFETIME_MATERIALIZED_E2`
- `B_REQUANT_SERVER_E4_E5`

Add: none.

`B_REQUANT_SERVER_E4_E5` remains historically open, but it is not a
prerequisite for the P0-A numeric/typed quant-tail contract.

Dependency mapping, without duplicating P0-A ownership:

- `B_QUANT_TAIL_FMA_ROUNDING_POINT`
- `B_QUANT_TAIL_MAGIC_DOMAIN_BOUND`
- `B_QUANT_TAIL_EXACT_FP32_DIVISION`
- `B_QUANT_TAIL_SIGNED_INT32_INGRESS`
- `B_QUANT_TAIL_THREE_PE_TOPOLOGY`
- `B_QUANT_TAIL_TYPED_BINDING`
- `B_QUANT_TAIL_MAPPER_REGISTRATION`

The exact-FP32-division blocker is shared-contract-only for this family; the
other six map directly to Requant release cells.

## Validation

Command:

`.\.venv\Scripts\python.exe -m unittest tests.test_build_requant_quant_tail_evidence_input`

Result: 8/8 tests passed.

Validated fail-closed properties include exact 54/33/21/1 totals, per-stage
nonzero counterexamples, node0014 tie parity, nonzero saturation coverage
absence, MatMul `y_zero_point=60`, numeric/physical classification separation,
P0-A 33/16/5 dependency partition, the 26-vs-25 first hardware unknown,
FP32-division scoping, the three active rule identities, narrowed Requant magic
scope, mutable-plan provenance separation, on-disk deterministic equality,
self-hash verification, and all stop-gate booleans.

## Formal D / observer

Formal D: not run and not claimed in this task.  
Observer: not installed, modified, or run in this task.
