# GAP node0071 v15 feature-enable rule refresh

Date: 2026-08-01

Mainline: `019fa2ca-72bc-7753-8d58-81e59bc76c88`

## Rule-drift adjudication

Current server rule:

- SHA256:
  `fb400d016a1328e0de1d576f76af5905f93e77c86361321af39513f329a43025`
- new applicable ID:
  `CDA-SERVER-DIAGNOSTIC-FEATURE-RUNTIME-ENABLE-END-TO-END-001`

The new rule is applicable to the Buffer-to-GA accumulator-state feature.
v14 already had the correct real simulator enable/limit behavior and four
feature-oriented external negative controls, but its final ZIP manifest:

- bound the prior server-rule SHA;
- did not list the new formal rule ID;
- did not declare the complete feature name, time-0 marker, returned binding
  receipt, record schema and allowlist-target contract.

Those are package machine-contract changes. Therefore a content-neutral
external receipt cannot repair v14. v14 is quarantined without modifying its
bytes.

## Fresh successor

- identity: `r5_n71_gap_v15_feature_enable_rule`
- claim: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`
- status: `PACKAGE_READY_NOT_RUN`
- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v15_feature_enable_rule.zip`
- bytes: `1798008`
- SHA256:
  `97a7366812210840ad67af40b3be3d90f7d7d44b997a29de41d366d877d97811`
- sidecar SHA256:
  `770dd792ef4d045d5a05e9cdc55dea095a7e65f1fccdf2566decaef43b587557`

The final manifest now binds the current server rule and formal new ID, and
declares:

- feature: `buffer_to_ga_accumulator_state`;
- real argv: `+RETURN_OBS_ACCUM_STATE`;
- limit: `+RETURN_OBS_ACCUM_LIMIT=512`;
- time-0 marker tokens: `accum_state=1`, `accum_limit=512`;
- returned binding:
  `buffer_to_ga_accum_state_enabled=true`,
  `buffer_to_ga_accum_limit=512`;
- record schema: `BUFFER_TO_GA_COUNTS`, `BUFFER_TO_GA_STATE`;
- return targets: actual simulator argv, observer binding and observer log.

The final-ZIP validator directly removes the enable, tampers the limit,
removes the time-0 marker contract and removes the feature return target.
All four controls fail closed.

## Final audit

- audit:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v15_feature_enable_rule.final_zip_rule_self_audit.json`
- audit SHA256:
  `7839caa9b65c7a53257b221f2cda2c38cc1102e8060b8d71f369aa4a0ef350dd`
- `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`
- errors: `0`

All required validators exit 0 at the audit layer. Fresh-extract package
preflight and bash syntax pass. The real-runner safe compile-stub positive
control reaches make and exits the unique expected 86. Wrong identity exits 5
before compile. Bootstrap immutability, manifest exact-set, runtime-D absent,
minimal runtime preflight, observer four-way, canonical decision, gated-domain
counter, result conjunction, return allowlist, transport receipt and the new
feature-enable rule all pass.

Runner-chain report:

- path:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v15_feature_enable_rule.runner_chain_validation.json`
- SHA256:
  `91ed88ad4fd00bc42cd773a6a141f361acf1edb2e34c9f80140a09e8265ce77a`

## Frozen boundary

The observer remains byte-identical to v14, SHA256
`c6ae0bbd7f2cbe40c5ba47608b8ffb2c4123f58c5ce7ebe9e92f3dce8fb87c59`.
All 73 numeric files remain byte-identical. No numeric analysis, sum/tail,
workload, config semantics or golden was repeated or rebuilt. No functional
RTL was modified and no server action occurred.

Only these source-v14 paths changed:

- `PREPARE_AND_RUN.sh`
- `README.md`
- `TEST_PACKAGE_MANIFEST.json`
- `workload/sca_cfg.json`
- `workload/sca_cfg_D.json`

Runner feature enable/limit behavior is unchanged; its feature-specific
returned receipt now also reports the effective limit. SCA changes are fresh
namespace only.

## PACKAGE_RELEASE

The only runnable GAP identity is
`r5_n71_gap_v15_feature_enable_rule`.

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

Expected return ZIP:
`r5_n71_gap_v15_feature_enable_rule_return.zip`. The runner generates a
server-local sidecar; under the user-attested transport rule it need not be
returned.

Machine receipt:
`artifacts/operator_config_validation/r5-gap-node0071-v15-feature-enable-rule-refresh/receipt.json`.

