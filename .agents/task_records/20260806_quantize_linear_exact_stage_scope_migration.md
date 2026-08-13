# QuantizeLinear exact-stage family-scope migration

- Delegation source: `019fd276-14c5-7800-94db-87ebfb9ce632`
- Unique mainline return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- Analysis owner: `019fa2c0-572b-7f21-ac5a-96e773dde534`
- Family: `quantize_linear`
- Status: `HARDWARE_OR_SEMANTIC_CAPABILITY_BLOCKED`
- Package release: `NONE`

## Scope-only result

`family_set.json` was migrated from `LEGACY_HW_OP_TYPE_SELECTOR` to
`PINNED_EXACT_STAGE_IDS`. The current lowering bundle was inspected directly
before writing the manifest:

| Exact stage ID | Occurrences | `hw_op_type` | `onnx_op_type` | Node |
| --- | ---: | --- | --- | --- |
| `hwop-0000-00` | 1 | `QuantizeLinear` | `QuantizeLinear` | `node-0000` |
| `hwop-0074-00` | 1 | `QuantizeLinear` | `QuantizeLinear` | `node-0074` |

The manifest binds
`contracts/resnet50_r5_lowering_bundle.json` SHA256
`bf661e4eda2011025d9922708ab46a64f8d1b3c279527b88aa7d630bb3545432`
and exact expected IDs `[hwop-0000-00, hwop-0074-00]`.
`target_hw_op_types=["QuantizeLinear"]` is retained only as a per-ID type
check; it does not select or enlarge the expected stage set.

## Current receipts

| Path | Bytes | SHA256 | Role |
| --- | ---: | --- | --- |
| `.agents/agent.md` | 13,174 | `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f` | active agent boundary |
| `.agents/plan.md` | 19,809 | `db3394a1f902bc7426fa791ae0574464e9f972678ea7980bcadad2efb1f42102` | mutable read receipt only |
| `.agents/rules/生成前必读索引.md` | 12,285 | `e3c7ed8a651d9b1d8b4d67e4ec29fe50c6441f8410cb60c9bd7f95359ccd4bf6` | active routing |
| `.agents/rules/算子配置规则.md` | 37,680 | `dc5243226bacde799b368d37fb9eb656e6b7e3d33a0a2932ae72ab35415ae3e1` | includes exact-stage family scope rule |
| `.agents/rules/精确UINT8量化尾专项规则.md` | 9,310 | `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e` | Quantize tail boundary |
| `schemas/operator_config_complete_json_family_set_v1.schema.json` | 2,719 | `bc4b0b40810e526cfa6b6bb8bce734850b85bb44c0100b5e43212b0aba5bfd18` | current schema |
| `tools/audit_complete_operator_json_family_set.py` | 13,363 | `3e72c6c8fb5921b427d6e41b048acb51b1f55df65011e4b1733cdc341f7ff5f1` | current auditor |

The applicable public rule is
`CDA-COMPLETE-JSON-FAMILY-SET-SCOPE-FAMILY-OR-STAGE-PREDICATE-001`.

## Materialized receipts

| Path | Bytes | SHA256 |
| --- | ---: | --- |
| `artifacts/operator_config_validation/r5_complete_json_regeneration_v1/quantize_linear/family_set.json` | 1,176 | `1a3f29cbd37daef174416a62c217fd609e581bfa49b41d138532ad5f55917408` |
| `artifacts/operator_config_validation/r5_complete_json_regeneration_v1/quantize_linear/family_set_audit_report.json` | 176,122 | `c395ae9d7766501bf603f879f3aab6d2970ae10fdca1dfe4fd2722e7d527c994` |
| `artifacts/operator_config_validation/r5_complete_json_regeneration_v1/quantize_linear/exact_stage_scope_migration_report.json` | 11,152 | `4d1d846deb446b5218051ce6adad34ca32398a4853d2acb55c6c7c75f998e3c7` |

The pre-migration `family_set.json` identity was 761 bytes,
SHA256 `eb3244499e5ffedc7913e111f453132a85014744833d148a42b33e1e5f8297f1`.

## Fresh audit

Command:

```powershell
& 'C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tools/audit_complete_operator_json_family_set.py artifacts/operator_config_validation/r5_complete_json_regeneration_v1/quantize_linear/family_set.json --output artifacts/operator_config_validation/r5_complete_json_regeneration_v1/quantize_linear/family_set_audit_report.json
```

Exit code: `1`, expected fail closed.

- `scope_mode=PINNED_EXACT_STAGE_IDS`
- expected/covered = `2/2`
- missing = `[]`
- unexpected = `[]`
- duplicate = `[]`
- scope errors = `0`
- both exact scope receipts are present and bind `QuantizeLinear`
- both candidates remain `contract_valid=true`, `blocked_valid=true`,
  `pass=false`, `errors=[]`
- each candidate retains 1,043 completion blockers
- overall family pass remains `false` solely because the two legal BLOCKED
  candidates do not pass the COMPLETE gate

The family auditor therefore reports two family-gate messages saying that the
candidate contracts did not pass complete-JSON validation. They are not scope
errors and do not invalidate either BLOCKED contract.

Public regression:

```powershell
& 'C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_complete_operator_json_candidate tests.test_complete_operator_json_family_set
```

Exit code: `0`; `20/20 PASS`.

The first attempt through an unqualified `python` command found no executable
on `PATH` and produced no authoritative audit. The command above uses the
workspace-bundled runtime and is the only audit result claimed here.

## Frozen assertions

The migration changed no candidate semantic asset. Pre/post hashes are
identical for:

- both candidate contracts:
  `282dac0cf3e478ebc6215da9c2fe7de4912dc7d2389b1e59c6e4417cd100d322`,
  `834f42c123ed7c713d7eed5496c60b6111afb1af8145463e7b9c000e7f2d19b5`;
- both field ledgers:
  `47ff99636706f6cbadc538626fddb2c4980326ccb62a5e4aa329fb53029f2b16`,
  `f65acfb69bdaf1bc7590ae3e731265144f230f25cf6ec46e21c61e31916f2e93`;
- both BLOCKED reports:
  `a568a4946e5f7cf00674281164c78c9e64331ce5613bece1dee61e18270ec2ce`,
  `751697764374ba23d6d77348ad9075ed71158a147f7d30fc74e52aa7c77f5823`;
- both per-stage current diffs:
  `426cc3443379fe11168eb7a95cb4b71ce054efd20b6fd1ddb2633351c98f3a8d`,
  `ca2a1c55ab76a719b870a371dd42412dcbd14a92717aa1a3ba6ebb1fa6b9cf47`;
- family current diff:
  `ee4db6bbb362c1ee7a40f018a8d5885ba204553fea5818440eb52279c6253ffa`.

The frozen node0074 instance-level `APPROVED_EQUIVALENT` paired elimination is
also unchanged:

- contract SHA256
  `7f9dbfa7d92a70c310c04275ee7c1f90dfa763de975d68bf663d3f20cbc073db`;
- evidence report SHA256
  `213ff272db06229451f2ccd5ca53c5533698dcfc8c28b14bf2cc189fe60ea8f8`;
- shared endpoint contract SHA256
  `04e3e6e7c5b27878cb021b653c1f6ec0df16b9a5530fdd11452bfe6eb2fcf89c`.

This remains an instance-level execution-path elimination. The generic
node0074 exact-binary32 division capability blocker remains open.

## Analysis and write boundary

- Numeric analysis repeated: `false`
- W3/golden repeated: `false`
- Dequant/View primitive tests repeated: `false`
- Existing reuse assets consumed: `true`, identity receipts only
- Mapping/bitstream/execplan/SCA generated or modified: `false`
- ZIP/server package generated or modified: `false`
- Server inspected/uploaded/run or lease acquired: `false`
- Functional RTL modified: `false`
- Plan/public rules/other family modified: `false`

## Rule feedback

`RULE_CONFIRMATION`: no non-synonymous rule delta is required. Current
`PINNED_EXACT_STAGE_IDS` semantics correctly close family scope at 2/2 while
leaving both capability-blocked candidates fail closed.

## Claim boundary

This record proves only the static QuantizeLinear family-set scope migration
and fresh local shared-auditor result. It does not produce or authorize target
JSON, mapping, bitstream, execplan, SCA, package, server execution, natural
terminal, formal D, or E3-E5 evidence.
