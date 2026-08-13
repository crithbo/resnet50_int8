# ConvInt32Accumulate 53-stage exact-scope migration

- date: `2026-08-06`
- family owner: `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- upper task: `019fd276-14c5-7800-94db-87ebfb9ce632`
- unique mainline: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- status: `EXACT_STAGE_SCOPE_MIGRATED / HARDWARE_OR_SEMANTIC_CAPABILITY_BLOCKED`
- package release: `NONE`

## Current public identities

- rule:
  `CDA-COMPLETE-JSON-FAMILY-SET-SCOPE-FAMILY-OR-STAGE-PREDICATE-001`
- `.agents/rules/算子配置规则.md`:
  `dc5243226bacde799b368d37fb9eb656e6b7e3d33a0a2932ae72ab35415ae3e1`
- `.agents/rules/生成前必读索引.md`:
  `e3c7ed8a651d9b1d8b4d67e4ec29fe50c6441f8410cb60c9bd7f95359ccd4bf6`
- family-set schema:
  `bc4b0b40810e526cfa6b6bb8bce734850b85bb44c0100b5e43212b0aba5bfd18`
- family-set auditor:
  `3e72c6c8fb5921b427d6e41b048acb51b1f55df65011e4b1733cdc341f7ff5f1`
- lowering:
  `bf661e4eda2011025d9922708ab46a64f8d1b3c279527b88aa7d630bb3545432`

## Migration

Only
`artifacts/operator_config_validation/r5_complete_json_regeneration_v1/conv_int32_accumulate/family_set.json`
was semantically migrated.  It now declares:

- `family_scope.mode=PINNED_EXACT_STAGE_IDS`;
- the exact lowering SHA above;
- the previously proven ordered list of all 53
  `ConvInt32Accumulate` stage IDs;
- `target_hw_op_types=["ConvInt32Accumulate"]`, used only to verify the
  real lowering type of every declared ID.

The public audit reports:

- scope mode: `PINNED_EXACT_STAGE_IDS`;
- exact scope receipts: `53`;
- expected/covered: `53/53`;
- missing stage IDs: `0`;
- unexpected stage IDs: `0`;
- duplicate stage IDs: `0`;
- absent stage IDs: `0`;
- hardware type mismatches: `0`;
- lowering SHA mismatch: `0`;
- `legacy_scope_compatibility=false`;
- `migration_recommended=false`.

The family audit exit remains `1` only because the sole candidate is a
valid `BLOCKED` candidate (`contract_valid=true`, `blocked_valid=true`,
candidate errors `0`, completion blockers `1851`, candidate `pass=false`).
This is the intended family-release fail-closed result and is not a
scope error.  The family is not claimed COMPLETE.

## Validation

Bundled Python:
`C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`

1. Public family audit:
   `python tools/audit_complete_operator_json_family_set.py <family_set> --workspace-root . --output <public_family_set_audit>`
   - exit `1`, expected BLOCKED family release;
   - scope/type/SHA/coverage errors `0`;
   - sole error is the incomplete BLOCKED candidate release gate.
2. Family validator:
   `python tools/validate_conv53_complete_json_regeneration_v1.py --project-root .`
   - exit `0`, valid `true`, errors `0`.
3. Family tests:
   `python tests/test_conv53_complete_json_regeneration_v1.py`
   - exit `0`, `2/2 PASS`.
4. Public candidate + family tests:
   `python -m unittest tests.test_complete_operator_json_candidate tests.test_complete_operator_json_family_set`
   - exit `0`, `20/20 PASS`.
5. Forbidden package/runtime marker scan:
   - ZIP/PREPARE_AND_RUN/TEST_PACKAGE_MANIFEST/SERVER_RESULT_GATE count `0`.

## Current migrated identities

- `family_set.json`: bytes `2001`, SHA
  `fb70a87f95578bdf1f5d37c21b1cb557b21777b7531a657cdaaee2982f862d2a`
- `public_family_set_audit.json`: bytes `161678`, SHA
  `8d151dea0a6cf99932cebdcfb25b8b94a5c0ab0bbcd84ed51c9808bdb88b43a1`
- `report.json`: bytes `7283`, SHA
  `e408f8c9903c4e71ea546dd0add786dfc7a19c1a32237c7dcbd9dd00ed0a5059`

## Frozen-asset byte identity

The migration did not change any candidate or semantic evidence asset:

- `blocked_candidate_contract.json`:
  `c7bc3aa5a5f29565db0ac2c9798b69893bfe5b57538f179e4f8208cf741694a9`
- `blocked_candidate_blueprint.json`:
  `c08e0ed2adc85281ba5573b9f390b408fd5f7ae615905d2d19db6fa99d3b5134`
- `field_provenance_ledger.json`:
  `6f35e0cb513894a20d11a5b3b6d78a01cf0a916c418f600fcad0f38c9d633a22`
- `handler_capability.json`:
  `3a20562abbaa2ab9a6c6b01463125c8137249a1064e9355ee81dafe56d0a0f23`
- `current_test_diff.json`:
  `44715227ab5fc4e065cd6a518da811a3fa5a0766d83933827267a8ed8f3d7a11`
- `public_candidate_validation.json`:
  `3d166d4c274b19b3fdf66b74cc165c61c9d20927647799dba78f209124e7f390`
- `validation.json`:
  `5323239737a93bedffbd01f356861b0b1e3fe85ccf0356efbca0131b94b7133e`
- `negative_controls.json`:
  `38d6b400eb0456a8076b818daa14f3add4ca947ad5f83ce2c4498ad330a00954`

No candidate, ledger, handler capability, current-test diff, blocked status,
numeric/W3/golden, mapping, bitstream, execplan, SCA, server package, RTL,
plan, public rule or other-family asset was changed.

## Rule feedback

`RULE_CONFIRMATION`: the exact-stage scope rule correctly binds the proven
53-ID Conv set to the lowering SHA and independently rejects missing,
unexpected, duplicate, absent, wrong-type and SHA-drift cases.  No rule delta
is proposed.
