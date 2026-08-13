# Conv node0004 v36 return → v37 WR drain diagnostic successor

- owner: `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- route: serialized node0004 correctness only
- numeric/workload/config/golden repeated: `false`
- functional RTL / public rules / plan modified by owner: `false`
- server upload/run/lease: `false`

## Input and rule receipts

- v36 return: `r5_n4_hw_v36_b5rd_diag_return.zip`, bytes `102854`, SHA256 `f98d448113aafb78c80cbab6cd002e8b783325082a79ae98cf265ffebc38bca5`
- frozen v36 source: bytes `5845330`, SHA256 `08a7d79c50896c18665d551c32522fc39f0f90f4802a8797caa024f4ac474bc2`
- `.agents/agent.md`: `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f`
- generation-time mutable plan receipt: `ae72cd46d134c51eba8455da120d07e9a82dfe1aa29f1bd438e592d556de042e`
- post-generation mutable plan drift is content-neutral and is recorded by the final audit
- generation index: `93b66e7986beeaddb01f237710af6874bb4bbfcc4c6c6929563c5e98d8397eb2`
- server rule: `14b7e5fa45e5985f9c8bc849acf0a9e768ab4617f3c249addaeb7b5d291a47d1`
- common rule: `8eb7a4c6759a5517e7218f6aab9e9ebb89052f898b790e5b6f4adfab622e6497`
- NDP fields: `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055`
- INT8-SA: `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`
- hardware README: `e82f51c73f658fa567d47c8ab277c1cfb2cdf6d7cd2b4debefb3d0543e2228ba`
- current local/user server baseline: `e1fb0f7bb2761d6c804867de0c5d2cb77554c48d`; actual compile identity remains a return-time E3/E4/E5 requirement.

## RETURN_ANALYSIS

All CRC/root/path/identity/RETURN_MANIFEST/exact-set/allowlist/per-file receipts, source binding, package/install preflights, runtime-D-absent, observer feature binding, compile and canonical-decision gates passed. Compile/run were `0/0`, signal was `NONE`, and the diagnostic `$finish` was observed. The DUT did not naturally terminate. Formal D remained `present=0, missing=320, mismatch=0`; the joint gate and E3/E4/E5 are false.

v35 observer defects are dynamically closed:

- qualified `buf_match` rises: `35`;
- `ROWLC4_BUFAG_BOUNDARY_V1` and `B5RD_BOUNDARY_V1` each have exactly one canonical `DIAG_DECISION`;
- no decision snapshot depends on the disabled parent feature.

The five v36 candidates are all excluded by qualified evidence:

- selected Buffer5 request accept: `35`;
- cluster request accept: `35`;
- Buffer5 bank read accept: `35`;
- RD Buffer AG pop: `35`;
- a single `rvalid` rise is evidence-dominated by the 35 qualified downstream pops, so it is a sustained burst level rather than one transaction per cycle.

`LAST_PROVEN_GOOD=BUFFER5_SELECTED_READ_REQUEST_ACCEPTED_THROUGH_CLUSTER_MRM_BANK_AND_RETURNED_TO_MSE_WITH_35_QUALIFIED_RD_BUFFER_POPS`.

`FIRST_DIVERGENCE=WR_DATA_CHANNEL_PREPARED_FIFO_REACHES_COUNT32_BACKPRESSURE_WITH_NO_OBSERVED_PREPARED_TO_OUTPUT_DRAIN_CAUSE`.

The canonical terminal state has prepared count `32`, prepared valid `1`, prepared backpressure `0`, WR ready `0`, and the two-entry RD buffer full again. The exact remaining cause is not unique in v36 because DWRITE and DataHub features were compiled but not runtime-enabled.

## BLOCKER_DELTA

Closed:

- `B_CONV_NODE0004_V35_ROWLC4_OBSERVER_EVENT_AND_SNAPSHOT_BINDING`
- `B_CONV_NODE0004_BUFFER5_READ_REQUEST_READY_AND_RETURN_PATH_UNOBSERVED`

Opened:

- `B_CONV_NODE0004_WR_DATA_PREPARED_TO_OUTPUT_AND_DATAHUB_DRAIN_UNOBSERVED`

Preserved:

- natural terminal
- formal D 320

The historical `B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED` remains `INVALIDATED_NOT_RTL_BUG`; it was not reopened.

## v37 successor

The unique successor is `r5_n4_hw_v37_wrdrain_diag`, classification `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`, `candidate_release=false`.

It enables the already compiled qualified `MSE4_DESCRIPTOR`, `DWRITE_PATH`, and `DATAHUB_DRAIN` features. One new `WRDRAIN_BOUNDARY_V1` canonical snapshot records descriptor count/size, mask dependency, prepared state, output selector/valid/backpressure and memory write valid/ready. It is state-only and is not added to canonical progress. The candidate × observation matrix covers descriptor starvation, masked-write old-data dependency, output selector/slot blocking, MSE write-data ready backpressure, and DataHub arbiter/bank drain in one run.

No legal checkpoint exists for the accumulated prepared-count state, so the frozen c0 prefix is retained. No host replay or internal tensor fabrication is used.

## Validation

- builder and deterministic double build: exit `0`, equal `true`
- runner safe compile/EXIT finalizer: outer validator exit `0`, controlled runner exit `74`
- TERM finalizer: controlled runner exit `143`, partial return retained
- focused Icarus positive compile: exit `0`
- focused negatives: missing gate declaration exit `4`; typo XMR exit `1`; missing task owner exit `1`
- each newly enabled feature: delete enable, limit, time0 marker, and returned target all fail closed
- path negatives: overdeep, repeated identity, and stale shortened reference all fail closed
- final ZIP audit: `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`, `errors=[]`

## PACKAGE_RELEASE

- state: `PACKAGE_READY_NOT_RUN`
- ZIP: `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v37_wrdrain_diag.zip`
- bytes: `5847340`
- SHA256: `cd37675c41c3920c292bdb7ff342443222f96a412fe66d7d4d1319540549dbe0`
- sidecar bytes: `96`
- sidecar SHA256: `d397ce9bda137a9edd5126b14b6705777010b170f61ea9f7e120b98f1d18070a`
- command: `bash r5_n4_hw_v37_wrdrain_diag/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy`
- expected return: `r5_n4_hw_v37_wrdrain_diag_return.zip`

## RULE_CONFIRMATION

No rule delta is proposed. The current time-to-root-cause optimization, runtime feature binding, package-local focused HDL scope, path budget, runner controls, and final-ZIP self-audit rules were sufficient and executable. Their positive and negative controls directly governed this release.

## Machine evidence

- return report: `outputs/conv_node0004_v36_return_analysis/report.json`
- release report: `outputs/conv_node0004_v36_return_analysis/v37_successor_release.json`
- build report: `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v37_wrdrain_diag.validation.json`
- runner report: `outputs/conv_node0004_v37_package_validation/runner_controls.json`
- observer scope report: `outputs/conv_node0004_v37_package_validation/observer_scope.json`
- final audit: `outputs/conv_node0004_v37_package_validation/final_zip_audit.json`
