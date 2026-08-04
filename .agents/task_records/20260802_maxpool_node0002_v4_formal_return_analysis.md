# MaxPool node0002 v4 formal return analysis

Date: 2026-08-02

## Provenance and scope

- `analysis_owner_thread=019fbe9f-3f2d-7071-806c-1ae72ae96391`
- `return_target_thread=019fbec2-fe93-7e03-9314-cff6f222f33d`
- Analysis is receipt-only.
- `numeric_analysis_repeated=false`
- `W3_analysis_repeated=false`
- `config_mapper_bitstream_execplan_SCA_analysis_repeated=false`
- No package was generated.
- No server was inspected, uploaded to, or run.
- No plan, public rule, functional RTL, or other operator-family asset was
  modified.

Return:

`C:/Users/15383/xwechat_files/wxid_vwpfpfs4fgyk22_29b7/msg/file/2026-08/r5_n2_maxpool_native_reuse_v4_return.zip`

- bytes: `71129`
- SHA256:
  `350be6952bdb0135c9fd3c428494abf5461f9c7195cba662726923be3c1cbce6`
- Adjacent sidecar was not delivered. The user's transport attestation is
  applied only under
  `CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001`; no internal
  gate is relaxed.

Frozen source:

`artifacts/operator_config_validation/r5-server-test-packages/r5_n2_maxpool_native_reuse_v4.zip`

- bytes: `1496952`
- SHA256:
  `f2df61c2edd9459f872dc930312fa3cecb30d72ecd284760fbbc534d5f5dd6a0`
- source task record SHA256:
  `e40cf82bd0cd031d31f1d61a6d24c6ed4257a369c9b672889e1b3ac858467935`
- current source machine report SHA256:
  `ed08a5915497400c32dae152ae56071464313e6bb8aa9f3f7114e25c600bd2c9`
- The source task record's embedded old machine-report SHA `151db...` was
  not reused.

Control receipts:

- mutable plan SHA256:
  `11d8a61ae403ad223fe1ab35cd6250d24aafecc0b7c8dab4fc6770aa0d845c94`
- server rule at dispatch:
  `1e0b40589dddee3bf2b4d081936d37d9a25f78ea2ceb98bc08f2dcf813438589`
- server rule observed at analysis completion:
  `80851d9881a4701e19052e45240587499c6a286f1ffa30f76a7e77848091e14a`
- The rule drift was read-only. The final adjudication applies the stricter
  completion-observed rule.

## RETURN_ANALYSIS

- ZIP CRC, single root, path safety, duplicate and symlink gates pass.
- Return contains 21 files and 1,527,240 uncompressed bytes.
- `RETURN_MANIFEST.json` contains 20 records; every size/SHA matches.
- Manifest exact-set, allowlist subset, and required-missing reconciliation
  pass.
- Returned `package/TEST_PACKAGE_MANIFEST.json` is byte-identical to the
  frozen source manifest, SHA256
  `63f5b5dcc57b884ff34621374f47a004b23ec58d8bd80bd2135e7ceadb5db23d`.
- Package/install/run/return identity is exactly
  `r5_n2_maxpool_native_reuse_v4`.
- Package and installed preflights are valid; package tree is immutable;
  formal D targets were absent before runtime; server sources were not
  inspected.
- Observer source, package-local `+incdir`, compile macro, actual simulator
  argv, runtime enable, time-zero marker, returned observer, and signal trap
  all bind successfully.

Execution:

```text
compile_exit_status=0
simulation_exit_status=125
run_status_receipt=125
termination_signal=INT
natural_terminal=false
```

- Compilation/elaboration succeeds.
- Eleven matrices load; `Reg Started` and stage0 `INFO: slice start` appear.
- No `Simulation completed successfully!` or `INFO: slice completed after`
  appears.
- Host observer samples span 2,881 seconds.
- Simulation is interrupted at `33,712,835,625 ps`.
- Formal D: expected 4 segments, present 0, missing 4. Mismatch is not
  evaluable and must not be treated as zero.
- Result conjunction is false.

## LAST_PROVEN_GOOD

The last defensible end-to-end boundary is:

```text
compile/elaboration
→ 11 matrix preload
→ Reg Started
→ stage0 slice start
→ qualified MSE request/read-data
→ qualified GA pipeline0 capture
```

The last returned window is:

```text
active_cycles=26738688
clk_sg_edges=13459609
req=5
rdata=5
wdata=0
p0_capture=13369566
ga_output=0
finish=0
delta=131072
```

All 102 windows report positive delta only because repeated upstream
pipeline0 capture continues. Every downstream completion counter remains
zero.

## FIRST_DIVERGENCE

```text
QUALIFIED_GA_PIPELINE0_CAPTURE
→ GA_OUTBUFFER_WRITE_ABSENT
→ D_WRITE_DATA_ABSENT
→ SLICE_FINISH_ABSENT
```

The return does not expose a unique configuration or RTL leaf inside this
interval. No such leaf is claimed.

## HANG_ROOT_CAUSE

```text
UNRESOLVED_WITHIN_GA_PIPELINE0_CAPTURE_TO_GA_OUTBUFFER_WRITE
```

Execution is classified as a long-running hang pending root cause, not as a
slow successful run. The observer proves repeated pipeline0 capture but lacks
the internal boundary necessary to determine why no GA output is accepted.

Three package-diagnostic limitations are independent of the functional
interval:

1. The two-stage source contract expects ordered stages
   `op-native-maxpool-slice0`, then `op-native-maxpool-slice1`, but the
   canonical record does not bind this ordered list.
2. Observer output has three stage0 `EXEC_START` witnesses without a unique
   ordered-stage identity, no stage finish, no stage1 start, and no canonical
   candidate. The fallback
   `EVIDENCE_INSUFFICIENT` record correctly does not claim natural terminal,
   but is not a current-rule canonical stage record.
3. The INT finalizer demonstrably generated signal/status/gate/observer/
   manifest artifacts, but returned no outer-shell/finalizer exit receipt and
   no runner stderr receipt. The returned sim/run value `125` was initialized
   before the interrupted wait and is a sentinel, not proof of the final shell
   exit code.

No early-stage `COMP_FINISH` was misclassified as whole-task completion:
there is no `COMP_FINISH` at all, and `natural_terminal=false`.

## E3_E4_E5

- `E3=false`: signal interruption and no final expected-stage completion.
- `E4=false`: no natural terminal, 0/4 formal D, mismatch unevaluable, and
  server source identity unbound.
- `E5=false`: E4 is absent and no fresh independent passing rerun exists.

## BLOCKER_DELTA

- `B_GA_INT8_MAX_FLOW`:
  `KEEP_OPEN_DYNAMIC_STALL_CONFIRMED_AT_PIPELINE0_CAPTURE_TO_GA_OUTBUFFER_WRITE`
- `B_GA_INT8_MAX_NUMERIC`:
  `KEEP_OPEN_UNEVALUABLE_NO_FORMAL_D_OUTPUT`
- `B_MAXPOOL_SERVER_E4_E5`:
  `KEEP_OPEN_SIGNAL_NO_NATURAL_TERMINAL_D_0_OF_4`

Package diagnostic-contract findings:

- `PACKAGE_DIAGNOSTIC_DECISION_FINAL_STAGE_SCOPE_CONTRACT_MISSING`
- `PACKAGE_SIGNAL_FINALIZER_SHELL_EXIT_STATUS_UNRETURNED`
- `PACKAGE_PROGRESS_SUM_DOMINATED_BY_REPEATED_UPSTREAM_CAPTURE`

## RULE_DELTA_PROPOSAL

`NONE`

Current canonical-stage, signal-finalizer, event-qualification and result
conjunction rules already classify the observed gaps.

## SUCCESSOR_PROPOSAL_OR_NONE

`NONE`

This task was not authorized to generate a successor. A future action must be
assigned by the mainline after it selects whether to repair GA INT8 Max flow
or first narrow the capture-to-outbuffer interval.

## PACKAGE_RELEASE

- `new_package=false`
- `PACKAGE_RELEASE=NONE`
- v4 disposition:
  `RETURN_CONSUMED_FAIL_CLOSED_DO_NOT_RERUN`

## Machine evidence

- Analyzer:
  `tools/analyze_maxpool_node0002_v4_formal_return.py`
- Analyzer SHA256:
  `27a0055492a782962e191a60f04bb840f3be30da53c8620f707290164d68874c`
- Machine report:
  `artifacts/operator_config_validation/maxpool-node0002-native-reuse-v4-return-analysis/report.json`
- Machine report SHA256:
  `dfaa1dd1de98b52b561e722df65d4191999c4c91477d40ea6b3caca9e723f23d`
- Analyzer command exit: `0`
- Machine report: `analysis_valid=true`, `errors=[]`
