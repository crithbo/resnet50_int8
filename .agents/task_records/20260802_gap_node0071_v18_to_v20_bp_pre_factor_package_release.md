# GAP node0071 v18→v20 bp-pre factor diagnostic package release

Date: 2026-08-02  
Owner task: `019fa366-cb1f-7ae2-880c-f527be0680cd`  
Unique mainline: `019fbec2-fe93-7e03-9314-cff6f222f33d`

## Outcome

`PACKAGE_RELEASE=PACKAGE_READY_NOT_RUN`

The only runnable identity from this task is:

- install/package identity:
  `r5_n71_gap_v20_bp_pre_factor_stage_scope_runnerfix`
- class: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`
- candidate release: `false`
- evidence boundary: `E2_LOCAL_ONLY`
- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v20_bp_pre_factor_stage_scope_runnerfix.zip`
- bytes: `1810686`
- ZIP SHA256:
  `a82ac187b46dac4f26a8545bf14bebf5bc5481308791be062ce581a30429bbe3`
- sidecar:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v20_bp_pre_factor_stage_scope_runnerfix.zip.sha256`
- sidecar SHA256:
  `ed5def149aa25f92d656c094898f08d8b65256ddc78bda5c4363449a3485bb2f`
- one command:
  `bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX`
- expected return:
  `r5_n71_gap_v20_bp_pre_factor_stage_scope_runnerfix_return.zip`

No upload, server run or lease was performed.

## Why v18 and v19 are not runnable

The requested v18 identity was built and preserved byte-for-byte as ZIP SHA
`00ca26f5ad7d30507ed7889d5f19f1a1072c948475e1280198a43b98324916c7`,
but it is quarantined.  The post-generation server-rule delta was material:
the frozen GAP workload has the ordered stage list
`sum_s1,sum_s2,sum_s3,sum_s4,sum_s5,sum_s6,tail_mul,tail_round`, while the
v18 canonical parser did not bind the expected list or final-stage scope.

Fresh v19 added that package-local canonical contract and was preserved as ZIP
SHA
`68c9bd007d8dea02a13aefc7ac9ddda3623b1afb83ad9fdb97552940579ce098`,
but is also quarantined.  Its safe compile-stub reached `make`, yet the EXIT
trap finalizer referenced function-local `package_manifest` under `set -u`.
The first divergence was:

`EXIT_TRAP_FINALIZER_PACKAGE_MANIFEST_UNBOUND_VARIABLE`

The expected stub exit `86` had masked this finalizer diagnostic in the older
positive gate.  Fresh v20 changes only the package identity/manifest/README,
SCA namespace and runner finalizer expression to:

`$package_root/TEST_PACKAGE_MANIFEST.json`

The v19 observer and canonical parser are unchanged in v20.

## Frozen reuse receipts

- frozen numeric/workload files: `73`
- numeric/workload tree byte equality: `true`
- v19→v20 frozen non-allowed files: `120`
- v19→v20 frozen non-allowed tree byte equality: `true`
- v19→v20 changed path exact allowlist:
  `PREPARE_AND_RUN.sh`, `README.md`, `TEST_PACKAGE_MANIFEST.json`,
  `workload/sca_cfg.json`, `workload/sca_cfg_D.json`
- two deterministic v20 builds: `true`
- repeat ZIP SHA:
  `a82ac187b46dac4f26a8545bf14bebf5bc5481308791be062ce581a30429bbe3`
- numeric analysis repeated: `false`
- sum/tail/workload executed: `false`
- config semantics rebuilt: `false`
- golden rebuilt: `false`
- functional RTL modified: `false`

The package remains a read-only diagnostic.  The original leaf disjunction is
unchanged:

`rd_data_chl_data_ready==0 OR nse2mse_req_barrier==1`

Stable levels and factor transitions do not count as canonical monotonic
progress, and a zero conjunction output does not assign a leaf cause.

## Current rule receipts

- agent:
  `5a4660df1e771b75045c45f75e08b7eba771542750b91ab18af6ab0434043de0`
- plan, mutable provenance only:
  `11d8a61ae403ad223fe1ab35cd6250d24aafecc0b7c8dab4fc6770aa0d845c94`
- generation index:
  `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f`
- server package rules:
  `1e0b40589dddee3bf2b4d081936d37d9a25f78ea2ceb98bc08f2dcf813438589`
- common operator rules:
  `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171`
- NDP field semantics:
  `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055`
- GAP int32_mac:
  `4c3a88b8c6967812b0b64a550bb92a45117106f34996102335dc26fa1a211f8b`
- GAP dynamic/probe:
  `db377ee2eb7ecc381a44a169a875ccecf2c46711399a4bdabcaef4ba164653d1`
- exact UINT8 tail:
  `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e`
- hardware simulation entry:
  `4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7`

## Final-ZIP audit and controls

Final audit:

- report:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v20_bp_pre_factor_stage_scope_runnerfix.final_zip_rule_self_audit.json`
- SHA256:
  `61864f8adc6567fecc795c68afc59bb86b4076efe7095110065d9f3449283e97`
- `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`
- `errors=0`
- ZIP CRC, exact-set, manifest current-match, runtime-D-absent and return
  allowlist: all `true`
- nine audit command exit codes:
  `0,0,0,0,0,0,0,0,0`

Runner-chain report:

- path:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v20_bp_pre_factor_stage_scope_runnerfix.runner_chain_validation.json`
- SHA256:
  `bd7104e113e5fe8be97c9743fa7d6f915b96a796abad513075ba151043f7fd5e`
- safe compile-stub exit: `86`
- safe compile-stub reached: `true`
- positive stderr empty: `true`
- finalizer return ZIP created: `true`
- wrong identity exit: `5`
- wrong identity reached compile: `false`
- all runner negatives fail closed: `true`

Feature/stage-scope report:

- path:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v20_bp_pre_factor_stage_scope_runnerfix.feature_validation.json`
- SHA256:
  `5291b649c7e64848291c22f7ee312ff433b446300aa11ef2e3d2c6cb80608800`
- status: `PASS`
- negative controls: `34`
- all negatives fail closed: `true`
- canonical self-test: `true`

Machine report:

- path:
  `artifacts/operator_config_validation/r5-gap-node0071-v18-bp-pre-factor-observability/report.json`
- SHA256:
  `f0ca61b8bdfd4bb20a2784592bdb180e246d09cceaaba6c0e40dbe20e2ca6005`

## BLOCKER_DELTA

Closed locally:

- MSE0/MSE3 bp-pre conjunction factors are package-local, read-only and
  end-to-end bound.
- The canonical decision binds the expected eight-stage order and rejects an
  early-stage terminal.
- EXIT/signal finalization uses a globally visible manifest path and is covered
  by a safe-stub positive and regression negative.

Still open:

- The readiness-versus-barrier leaf cause remains unresolved until v20 is run
  and returned.
- No dynamic server result, E3, E4 or E5 is claimed.

## RULE_DELTA_PROPOSAL

Propose
`CDA-SERVER-RUNNER-POSITIVE-CONTROL-TRAP-FINALIZER-SCOPE-001`:
a positive runner control must execute EXIT/signal finalization after the safe
compile/simulator stub, require expected finalizer artifacts, and reject any
shell diagnostic such as `unbound variable`.  Stub exit code or make
reachability alone is insufficient.

## BYPASS_ANNOTATION

No new config-only bypass was introduced.  The equivalence scope is limited to
package-local diagnostic observability and result adjudication.  Its
materialization is a read-only observer, manifest-bound canonical parser and
runner finalizer.  The cost is at most 512 factor-edge records plus low-rate
summaries, with no timeout or DUT-backpressure change.  The production blocker
is the missing server run/return needed to distinguish readiness from barrier.
The claim boundary is
`DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX / E2_LOCAL_ONLY`.
