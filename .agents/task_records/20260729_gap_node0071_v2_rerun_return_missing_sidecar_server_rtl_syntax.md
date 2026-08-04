# GAP node0071 v2 rerun formal return adjudication

- date: `2026-07-29`
- unique mainline:
  `019fa2ca-72bc-7753-8d58-81e59bc76c88`
- status:
  `FORMAL_CLAIM_FAILED_MISSING_SIDECAR_AND_COMPILE_FAILED_SERVER_RTL_SYNTAX`
- local claim retained: `CONFIG_ONLY_CORRECTNESS_BASELINE`
- package rebuilt or modified: `false`
- GAP sum/tail numeric analysis repeated: `false`
- server files outside return inspected: `false`
- uploaded/run by this task: `false / false`

## Rule and control receipts

- server-package rule SHA256:
  `153b0f03210f8e4f98b6b39a7ca7a40b11c788085ba3775826e42beb171167a2`
- operator-config rule SHA256:
  `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171`
- generation index SHA256:
  `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f`
- GAP rule SHA256:
  `b194d525fb7c1647b3fdaabd51d88dc4bc9b874ce7a910d4fdd1ca125b56fd96`
- mutable plan SHA256 at analysis:
  `fbe18d59d34ed9e7ba99b2a70fc147ff69a5de3731803aa81102d8af2f534ec2`
- plan role: mutable provenance only; not a semantic gate

## RETURN_ANALYSIS

The physical filename suffix `(1)` was ignored for identity purposes. Identity
was bound from the ZIP content SHA, embedded return manifest and exact source
package:

- physical return:
  `C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7\msg\file\2026-07\r5_n71_gap_v2_obs_return(1).zip`
- logical return identity: `r5_n71_gap_v2_obs_return`
- bytes: `22749`
- SHA256:
  `59285a790d7f092dfa9db35c21a9ab1ea811e1d810b186bb91fc2ecc19161066`
- exact same-name sidecar:
  `r5_n71_gap_v2_obs_return(1).zip.sha256`
- exact sidecar present: `false`
- formal receipt blocker: `RETURN_SIDECAR_NOT_PROVIDED`
- formal receipt claim pass: `false`
- ZIP CRC/path safety/exact-set: pass
- ZIP file count: `12`
- strict manifest allowlist, sizes and per-file SHA: pass
- return manifest status: `incomplete`

Bound source:

- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v2_obs.zip`
- bytes: `1777110`
- SHA256:
  `c3fe06f6e0110b41936b69ae264a24b2dc2d76779efc589c4fe34378b6891b8f`
- source sidecar SHA256:
  `d4008551f3e19c1e5960cc3a44a1986b7363deec08246004e6e4391fa152d84f`
- returned manifest/SCA/SCA_D byte-equal to source: `true`
- source ZIP CRC: pass
- runtime readback targets in source ZIP: `0`

Package/install preflight:

- package preflight: pass
- installed preflight: pass
- installed file count: `75`
- preload/readback/repeat counts: `25 / 48 / 8`
- runtime readback targets absent before simulation: `true`
- observer precompile SHA/XMR receipt: pass
- server source files inspected by package: `false`

Execution:

- compile exit: `2`
- runner exit: `2`
- simulation exit: `125`
- simulation started: `false`
- natural terminal: `false`
- SCA/SCA_D loader echo: `false / false`
- preload exact: `false`
- formal dump exact: `false`
- dynamic formal readbacks: `0`
- missing: `48`
  (`16 sum_int32 + 16 scaled_fp32 + 16 final_uint8`)
- mismatch bytes: `0`
- gate conjunction `all_terms_true`: `false`
- returned status: `NODE0071_GAP_SERVER_FAILURE`

Zero mismatch does not satisfy PASS because compile failed, simulation never
started, terminal is absent and the entire formal readback exact-set is
missing.

## FIRST_DIVERGENCE

Ordered evidence:

1. formal claim first blocker:
   `RETURN_SIDECAR_NOT_PROVIDED`;
2. dynamic execution first divergence:
   `SERVER_RTL_SYNTAX_ERROR_BEFORE_TESTBENCH_AND_SIMULATION`.

Compile-log details:

- fatal error line: `1781`
- returned source-location line: `1783`
- returned source: `SA_PE_Float_Control.v`
- reported source line: `51`
- token evidence line: `1784`
- reported token: `)`
- compile summary line: `1789`, `1 error`
- testbench reached: `false`
- observer include parsed by compiler: `false`
- simulation started: `false`

This is a server RTL source syntax failure before testbench parsing, not a GAP
configuration, sum/tail numeric, workload or package-observer divergence. The
returned evidence does not reach the previously reported `slice_rst` interface
location and therefore cannot independently confirm that external repair.

## Evidence-level adjudication

- E3: `false`
- E4: `false`
- E5: `false`

The exact sidecar is absent and compilation fails before testbench and
simulation. No dynamic or production claim is allowed.

## BLOCKER_DELTA

Closed:

- content/manifest/source-SHA binding despite the physical `(1)` suffix;
- return CRC, exact allowlist and package/install preflight adjudication;
- conjunctive result-gate adjudication;
- proof that the failure occurs before simulation and formal readback.

New:

- `RETURN_SIDECAR_NOT_PROVIDED`;
- `B_GAP_NODE0071_SERVER_RTL_SA_PE_FLOAT_CONTROL_LINE51_SYNTAX`.

Still open:

- successful server compile and testbench parsing;
- simulation, natural terminal and loader/dump exact counts;
- 48-file formal readback exact-set with missing=0 and mismatch=0;
- final server/Trassic2.0_RTL identity binding;
- E4/E5 and production timing/resource closure;
- GAP-to-Dequant integrated endpoint.

The complete local config-only ONNX E2 count remains `3/78`.

## RULE_DELTA_PROPOSAL

No public rule delta is proposed. Existing sidecar receipt, compile-before-
dynamic-evidence and conjunctive result-gate rules fully cover the return.

## PACKAGE_RELEASE

- analyzed source identity: `r5_n71_gap_v2_obs`
- source ZIP SHA256:
  `c3fe06f6e0110b41936b69ae264a24b2dc2d76779efc589c4fe34378b6891b8f`
- current return result:
  `RERUN_FAILED_SERVER_RTL_SYNTAX_AND_MISSING_RETURN_SIDECAR`
- package-side legal fix confirmed: `false`
- fresh next package authorized: `false`
- new package generated: `false`
- workload rebuilt: `false`
- existing package modified: `false`
- server upload/run performed by this task: `false`

No package is released from this return. The original v2 ZIP remains
byte-identical and may only be reconsidered after the external server syntax
failure is resolved; a subsequent formal return must include its exact
sidecar.

## Machine artifacts and current disk SHA

- analyzer:
  `resnet50_pipeline/gap_node0071_v2_rerun_return_analysis.py`
- analyzer SHA256:
  `58bb83d6210fe4e0407bc36aaf0706829a744daea7f4cec20cc608f2840648df`
- CLI:
  `tools/analyze_gap_node0071_v2_rerun_return.py`
- CLI SHA256:
  `f5c803cecad7bbe89044545a746d266cdaae0e38f4ae5079062e2e568d0c0967`
- test:
  `tests/test_gap_node0071_v2_rerun_return_analysis.py`
- test SHA256:
  `8543d78ae0a356cb463fe91f880273eb28cdc722632fd17a829cb90cc599d2ba`
- report:
  `artifacts/operator_config_validation/r5-gap-node0071-v2-rerun-return-analysis/report.json`
- report SHA256:
  `c81b30838f0aea8308735b5826e406644e262812c61169ee1f6d65f637e67de4`
- tests: `6`, all passed

Accepted node0071 local-E2/package assets were consumed as immutable reuse.
No numerical analysis, workload materialization, server inspection, upload or
execution was performed.
