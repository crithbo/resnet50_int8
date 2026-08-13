# RequantizeUint8 complete-JSON regeneration v1

Date: 2026-08-06  
Family owner task: `019fa2bf-95cd-7502-82c8-6a48cf12d648`  
Upstream task: `019fd276-14c5-7800-94db-87ebfb9ce632`  
Unique mainline return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`

## Result

`HARDWARE_OR_SEMANTIC_CAPABILITY_BLOCKED`

All 54 `RequantizeUint8` lowering stages are inventoried exactly once. The
inventory contains 54 exact materialized-consumer signatures and 17 capability
reuse signatures. Qparam classes are 33 zero-point-zero, 16 even nonzero
zero-point and 5 odd nonzero zero-point stages.

No strict target hardware JSON was materialized. The target requirement ledger
contains 944 unresolved required leaves and the native-reference applicability
ledger records 27,864 unresolved reference leaves. This is a fail-closed
capability result, not a target-config failure and not a `COMPLETE` result.

The fresh shared candidate gate result after the BLOCKED adjudication driver
refresh is:

```text
candidate_count=54
contract_valid=54/54
blocked_valid=54/54
pass=true=0/54
candidate_errors=0
completion_blockers=4046
per_candidate_blockers=74..78
```

Completion blocker categories:

| Category | Count |
|---|---:|
| uncovered handler-dependent leaf | 1,888 |
| unknown source-absent target field | 890 |
| unresolved candidate leaf | 890 |
| unsupported handler axis | 324 |
| unresolved composition boundary | 54 |

The family-set auditor proves expected/covered=`54/54`,
missing/unexpected=`[]`, and no `no_config_stages` exception. Its `pass=false`
and 54 errors are the expected one-per-stage non-`COMPLETE` fail-closed
findings. They are not coverage, identity, schema, ledger, or candidate
contract errors.

## Capability boundary

The pinned native quant reference is
`ndp-sim/jsons/quant_from_buffer_int32MN_uint8MN.json` at
`uSFrances/ndp-sim@ec12424516ae0304228dd2321d4e604fe225e04e`, blob
`959e759e81eea358f52680c091f2dfa1535f564d`. It is grade C for these
targets: same quant hardware neighborhood, but different numeric order, dtype,
layout and physical schedule. The native handler documents itself as a
placeholder, only rewrites limited rank-3 shape fields, and the native remapper
test excludes this op type from the registry.

The first capability break is therefore `shape`. The dependent unsupported
axes are `qparam`, `layout`, `address`, and `cross_stage_schedule`; dtype is
also not established by the handler. Every target's two-stage
`fp32_scaled_scratch` composition boundary remains unresolved.

The existing 54-stage W3 evidence was consumed without rerunning numerical
analysis. The established numerical gates remain:

- zero-point-zero: exact rounding point and finite-domain proof;
- even nonzero zero-point: the zero-point-zero gates plus signed INT32 ingress;
- odd nonzero zero-point: all preceding gates plus zero-point-after-RNE/tie
  parity.

## Current-test comparison

The frozen node0001 guard-only event-edge diagnostics were read-only comparison
evidence and were not used as generation authority. The current plan records
`NO_CURRENT_RELEASE`. There is no proven current configuration defect that
explains the historical card point.

The last trustworthy node0001 boundary remains 64/64 bit-exact BST data and
coefficient addresses. The first unresolved dynamic boundary remains
coefficient SRAM output through ALU/postprocess/normal outbuffer to MSE4.
Observer occurrence, package transport, production RTL identity, natural
terminal and formal D are dynamic-only/non-configuration evidence and were not
relabelled as JSON defects.

## Current receipts

| Path | SHA-256 |
|---|---|
| `.agents/agent.md` | `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f` |
| `.agents/plan.md` (generation-time mutable provenance) | `325be21aec6d57880c08a4e5f50d9effb83a8ad5e0e9c6bb579b175dc0e4e021` |
| `.agents/plan.md` (final-handoff mutable provenance) | `add16cbf259314ffc04948c4b268766f677d629901e148d970e37a8d99fdf4b0` |
| `.agents/rules/生成前必读索引.md` | `d3a82e82199eb005d0d477b7cc740d11c42cf5fa3bef4ac2b2573cc5bad26bb6` |
| `.agents/rules/算子配置规则.md` | `52939b59f079721a9a8438e3d5297f42118eadb1f2c2a238e20bcca73a30a820` |
| `.agents/rules/RequantizeUint8算子配置规则.md` | `5fcd1c9d2f6fa6dd193e369412c46c16b7bd087b570cc607aa0d0f06ba4c7555` |
| `.agents/rules/精确UINT8量化尾专项规则.md` | `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e` |
| `.agents/rules/最小双Stage生命周期规则.md` | `821b8b04b0e33d0a93e06a3a1bca8307b417bcb63f109cf12414891e9a0bc171` |
| `.agents/rules/NDP硬件字段语义.md` | `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055` |
| `contracts/operator_config/complete_json_generation_contract_v1.json` | `de2825cae9f892482cd8eb74a60ea9b409a7f8186516b7ac5a6c04344b10c746` |
| `tools/validate_complete_operator_json_candidate.py` | `4e30018656afd41f3f7d89f2d56070986e2465fac59d41483ae40fbf8f4ec62f` |
| `tools/audit_complete_operator_json_family_set.py` | `baa932a47a73e03746d1700015176cdeb21ac8c1c2b12d96929d0a1e9553fe82` |

## Validation

Commands and results:

```powershell
C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe tools/build_requant_complete_json_regeneration_v1.py
# exit 0

C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe tools/validate_requant_complete_json_regeneration_v1.py
# exit 0; errors=[]; stage_count=54; ledger_stage_count=54

C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_requant_complete_json_regeneration_v1 tests.test_complete_operator_json_candidate tests.test_complete_operator_json_family_set
# exit 0; 18/18 PASS
```

The family negative controls all fail closed. The artifact-root forbidden
output scan found zero ZIP, `PREPARE_AND_RUN.sh`,
`TEST_PACKAGE_MANIFEST.json`, or `SERVER_RESULT_GATE.json`.

## Machine artifacts

| Artifact | SHA-256 |
|---|---|
| `report.json` | `7273bb78fd231a8364e47de3299455cdb9a46d48da2ced43dff19e6339e50a5a` |
| `family_set.json` | `a1040358e84a80444d4d58a91751cfa0329732aeb349ad8231e7b238060debcb` |
| `validation/public_gate/summary.json` | `619cbd569955bbf0a2485817d324813bb557bd8bbdd35b7037d38e61900ee560` |
| `validation/public_gate/family_set_audit.json` | `97044b9ebcfe3cf7e9b35c90a8bef6a617cb216b940dfdc7ca097a6e35bfa7e4` |
| `validation/family_validator.json` | `d23a8cb3fc01800ab95e9f46d5e6906412c232ffbe87e583958af949687831b2` |
| `tools/build_requant_complete_json_regeneration_v1.py` | `9934dfa073d9b9ecb28a18a7d93c493c4e6b108f37c90b9cf22a39c4e16216f5` |
| `tools/validate_requant_complete_json_regeneration_v1.py` | `f45bffcb88041f7ebe97f311247e26a54b9362d1b3a0ca162da07b7d469da8e4` |
| `tests/test_requant_complete_json_regeneration_v1.py` | `b647a136758da214da9b6f8a8365a209c4b3562806d9af038abadbaa04f2f304` |

Artifact root:
`artifacts/operator_config_validation/r5_complete_json_regeneration_v1/requantize_uint8/`

## Structured deltas

`BLOCKER_DELTA`:

- close: none;
- add: `B_REQUANT_COMPLETE_JSON_NATIVE_HANDLER_CAPABILITY`,
  `B_REQUANT_COMPLETE_JSON_ADDRESS_SCHEDULE_OWNERSHIP`;
- keep: existing exact-tail rounding/domain/signed-ingress/topology/typed-binding/
  mapper-registration, Requant shape-lifetime E2, guard dynamic data path, and
  server E4/E5 blockers.

`RULE_DELTA_PROPOSAL`: none. The refreshed public driver now correctly
distinguishes legitimate completion blockers from structural errors. This
family confirms the current rule semantics without a non-synonymous delta.

`PACKAGE_RELEASE=NONE`.

Claim boundary: local complete-JSON capability analysis only. No strict target
JSON, mapping, bitstream, execplan, SCA, server package, server action, E4, or
E5 was produced or claimed.

The mutable plan changed after the final artifact build. This is recorded as
provenance drift only; no hard rule, schema, policy, public driver, lowering
bundle, candidate result, family coverage, or blocker classification changed.
