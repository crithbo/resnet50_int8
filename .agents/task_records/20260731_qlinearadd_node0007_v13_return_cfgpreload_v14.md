# QLinearAdd node0007 v13 return / v14 config preload closure

Date: 2026-07-31  
Owner: QLinearAdd family  
Mainline: `019fa2ca-72bc-7753-8d58-81e59bc76c88`

## Current immutable rule receipts

- `.agents/rules/生成前必读索引.md`
  `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f`
- `.agents/rules/服务器测试包生成规则.md`
  `507ca9090c20c081baaf9604e318c58b9984fba8765d39fdf53b7cce90e6be8d`
- `.agents/rules/QLinearAdd算子配置规则.md`
  `c38935c63469a165ffe6b79c9e3d08de47bbbd9b9e0613cbc16253c138e4b76b`
- `.agents/plan.md` is mutable provenance only.

## RETURN_ANALYSIS

- Source v13 ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_obsrate_v13.zip`
  SHA256 `fe65a96ad6365872f2f004f6702b197f33fc6b5fcd4397df716714f443b28858`.
- Return ZIP SHA256
  `0970b61bac55fe8f615255a824b48a55002e6540d6f92960399753071afc653c`,
  bytes `150923`.
- Direct adjacent return sidecar is absent. Formal external receipt therefore
  fails closed; ZIP-contained diagnostic evidence remains independently
  consumable.
- CRC, safe path/root, exact return-manifest set, member hashes/sizes,
  package allowlist, package/install preflight and runtime-D absence pass.
- Compile `0`; simulation `125`; signal `INT`; no natural terminal.
- Formal D: expected `28`, observed `0`, missing `28`, mismatch bytes `0`.
  Missing-all is not a numeric pass. E3/E4/E5 all fail.
- Simulation wall time `3346.760915609 s` (55.78 min); package total
  `3452.099042648 s`.

## FIRST_DIVERGENCE / HANG_ROOT_CAUSE

- 31 paired, shared-rate-gate `FIRST_REQUEST_CHAIN` and
  `FIRST_REQUEST_CLOCK` samples were returned.
- `clk_sg_edges` increases from `131072` to `4063232`, but every qualified
  LC/MSE/AG/request counter remains zero from active cycle `262144` through
  `8126464`.
- Flat interval is `7864320` cycles with `stall_window=1048576`; therefore
  this is a proved hang, not a merely unfinished run.
- Last good: compile/elaboration, configuration/execution command acceptance,
  actual `slice_start_run`, and alive observer clock.
- First bad: physical LC2/4/6/13/18 enable bitmap remains zero, so LC4 outer
  handshake never occurs.
- Deterministic cause: v13 `sca_cfg.json` preloads 85 exec/tensor objects but
  omits all six config bitstreams addressed by the six `Load_Config` commands.
  The payload files are present, and decoded addresses are
  `0x00D2B000`, `0x00D2B400`, `0x00D2B800`, `0x00D2BC00`,
  `0x00D2C000`, `0x00D2C400`, using
  `base_addr = ddr_config_addr << 10`.
- Active `IGA_LC_Config.sv` enables LC only on
  `iga_lc_configure_inport_valid && iga_lc_configure_inport_enable`.
  The missing DRAM preloads therefore exactly explain the observed
  `slice_start=1, lc_enable=0`.
- v13 status:
  `QUARANTINED_MISSING_SCA_CONFIG_PRELOADS`.

Machine report:
`artifacts/operator_config_validation/r5-qlinearadd-node0007-observer-rate-v13-return-analysis/report.json`,
SHA256 `1c00d2af8dd27f1c270506a0dbc17f82cdf5c312718365e50595f1bd64d2e6af`.

## PACKAGE_RELEASE

- Unique successor:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_cfgpreload_v14.zip`
- bytes `38033509`
- SHA256 `78f1aa16b2853173c5b263acb2f1a3b42516a08cc7bb2fd5342f3fd55b918282`
- Sidecar:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_cfgpreload_v14.zip.sha256`
  SHA256 `c0903628ebaff73892dc6678041834f401f6b0365e7aa20e0f786614fea87f07`.
- Status `PACKAGE_READY_NOT_RUN`.
- Claim `CONFIG_ONLY_CORRECTNESS_BASELINE`.
- Fix scope: six package-local SCA config preload objects only. Frozen final
  JSON, mapping, bitstream bytes, execplan, SCA_D, tensors, golden, W3 and six
  qparams are unchanged.
- Unique server command:
  `bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX`
- Expected return:
  `r5_qadd_n7_cfgpreload_v14_return.zip` and directly adjacent
  `r5_qadd_n7_cfgpreload_v14_return.zip.sha256`.

Final ZIP audit:

- `python tools/validate_qlinearadd_node0007_config_preload_v14.py` -> `0`
- `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`, `errors=0`
- real runner to safe compile stub -> `86` (positive control)
- wrong package identity -> `5`, before compile
- each of six deleted config preloads -> `1`
- wrong config base/hash/length -> `1`
- all observer/clock/canonical negative controls fail closed
- report:
  `artifacts/operator_config_validation/r5-qlinearadd-node0007-config-preload-v14/report.json`
  SHA256 `c48eb562df62afbcb65dfd0b9b51e52f038b8b6e5070a15b3a865831d34f315a`.
- directed tests:
  `python -m unittest tests.test_qlinearadd_node0007_obsrate_v13_return_analysis tests.test_qlinearadd_node0007_config_preload_v14 -v`
  -> `7/7`, exit `0`.

## BLOCKER_DELTA

- Closed:
  `QADD_NODE0007_EXEC_START_TO_FIRST_REQUEST_ROOT_CAUSE_UNRESOLVED`.
- Closed locally:
  `QADD_NODE0007_SCA_CONFIG_PRELOAD_MATERIALIZATION_OMISSION`.
- Open external:
  `QADD_NODE0007_V14_SERVER_DYNAMIC_RESULT_PENDING`.
  E3/E4/E5 remain false until a formally receipted v14 return satisfies the
  complete result conjunction.

## RULE_DELTA_PROPOSAL

Propose a fail-closed package rule: every final execplan `Load_Config` command
must have exactly one SCA preload object whose base is
`ddr_config_addr << 10`, whose payload hash/line count matches the packaged
bitstream, and whose config length matches the command. Payload presence
without address-bound SCA materialization must fail final-ZIP audit.

`numeric_analysis_repeated=false`; `workload_analysis_repeated=false`;
`config_numeric_analysis_repeated=false`; `consumed_reuse_assets=true`;
`functional_rtl_modified=false`; `server_action=false`.
