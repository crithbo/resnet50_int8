# GAP node0071 v20 current-rule revalidation

Date: 2026-08-02  
Owner task: `019fa366-cb1f-7ae2-880c-f527be0680cd`  
Unique mainline: `019fbec2-fe93-7e03-9314-cff6f222f33d`

## Adjudication

`PACKAGE_RELEASE=PACKAGE_READY_NOT_RUN`

The frozen package and sidecar were not modified:

- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v20_bp_pre_factor_stage_scope_runnerfix.zip`
- ZIP SHA256:
  `a82ac187b46dac4f26a8545bf14bebf5bc5481308791be062ce581a30429bbe3`
- sidecar SHA256:
  `ed5def149aa25f92d656c094898f08d8b65256ddc78bda5c4363449a3485bb2f`

No v21 was generated.  No real server action, numeric/config/workload/golden
re-execution, public-rule edit, plan edit or RTL edit occurred.

## Rule drift

- old server rule:
  `1e0b40589dddee3bf2b4d081936d37d9a25f78ea2ceb98bc08f2dcf813438589`
- current server rule:
  `80851d9881a4701e19052e45240587499c6a286f1ffa30f76a7e77848091e14a`
- current bytes: `42892`
- affected existing rule:
  `CDA-SERVER-RUNNER-PREFLIGHT-TO-COMPILE-POSITIVE-CONTROL-001`
- content-neutral after external dynamic revalidation: `true`
- current-rule compliant: `true`

The normal EXIT path is proven:

- safe compile stub reached `make`;
- expected stub exit is `86`;
- finalizer generated a return ZIP;
- positive stderr is empty;
- an injected `package_manifest: unbound variable` regression fails closed.

The frozen runner declares a shared signal-finalizer path:

```bash
trap 'finalize $?' EXIT
trap 'signal_name=HUP; simulation_status=125; finalize 125' HUP
trap 'signal_name=INT; simulation_status=125; finalize 125' INT
trap 'signal_name=TERM; simulation_status=125; finalize 125' TERM
```

The original report and 34 negatives did not contain a signal-stub execution,
so static common-function text alone was initially insufficient.  Under the
supplemental authorization, the exact frozen v20 ZIP was fresh-extracted and
its real `PREPARE_AND_RUN.sh` was run with local safe compile/simulator stubs.
After the safe sim stub started, the harness delivered `TERM`.

Dynamic result:

- runner exit: `125`
- signal receipt: `TERM`
- compile status: `0`
- simulation/runner status: `125/125`
- runner stderr: empty
- harness stderr: empty
- finalizer epochs: exactly `1`
- partial return/sidecar generated: `true`
- partial return CRC/root/exact-set/allowlist/file receipts/package identity:
  all exact
- all 48 absent formal readbacks: explicitly listed as `required_missing`
- canonical decision: `PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE`
- canonical natural terminal: `false`
- result gate: `NODE0071_GAP_SERVER_FAILURE`
- result gate all terms: `false`
- fresh package tree before/after:
  `1e2d5385b43639bd48ab9bfbcee674ab3617e9fc66eb5cc59d120bc5b85edc6b`

This closes the added clause as:

`SAFE_SIGNAL_STUB_SHARED_FINALIZER_PATH_PROVEN`

The earlier functional leaf remains unchanged:

`rd_data_chl_data_ready==0 OR nse2mse_req_barrier==1`

## External receipt

- path:
  `artifacts/operator_config_validation/r5-gap-node0071-v18-bp-pre-factor-observability/v20_current_rule_revalidation.json`
- SHA256:
  `aa6b997195d514c37d04f51daf1050ea6d101630ef547de962c4b31e8952b97c`
- bytes: `6051`
- status: `RULE_DRIFT_CONTENT_NEUTRAL_REVALIDATION_PASS`

Signal-stub receipt:

- path:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v20_bp_pre_factor_stage_scope_runnerfix.signal_stub_revalidation.json`
- SHA256:
  `5ea6e42d76b1e5a2da5d9ca1ca73d97cdb838d7cd3d699b1e9f5ba156e530d8c`
- status: `PASS`

The updated external receipt status is
`RULE_DRIFT_CONTENT_NEUTRAL_REVALIDATION_PASS`.

`RULE_DELTA_PROPOSAL=NONE`: the merged current rule already states the missing
acceptance requirement.
