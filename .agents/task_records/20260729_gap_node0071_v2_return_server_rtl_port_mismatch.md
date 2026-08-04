# GAP node0071 v2 formal return: server RTL port-interface mismatch

- date: `2026-07-29`
- owner family: `QLinearGlobalAveragePool / node0071`
- unique mainline:
  `019fa2ca-72bc-7753-8d58-81e59bc76c88`
- local claim retained: `CONFIG_ONLY_CORRECTNESS_BASELINE`
- formal return status:
  `COMPILE_FAILED_SERVER_RTL_PORT_INTERFACE_MISMATCH`
- source package status: `ADJUDICATED_COMPILE_FAILURE`
- next package generated: `false`
- functional RTL modified: `false`
- server inspected outside returned evidence: `false`
- uploaded/run/lease: `false / false / false`
- GAP numeric analysis repeated: `false`
- accepted numeric/package reuse assets consumed: `true`

## Control-plane and rule receipt

- server-package rule SHA256:
  `153b0f03210f8e4f98b6b39a7ca7a40b11c788085ba3775826e42beb171167a2`
- common operator-config rule SHA256:
  `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171`
- generation index SHA256:
  `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f`
- GAP family rule SHA256:
  `b194d525fb7c1647b3fdaabd51d88dc4bc9b874ce7a910d4fdd1ca125b56fd96`
- mutable plan SHA256 at analysis start:
  `2946e5080678e3f2f95fa9f834b3ed6f6888914cb4feb9ebef0bde1b563434df`
- mutable plan SHA256 at report materialization:
  `f74f45eb990f9c8874c0a7cf1251ce931bd770d1fb1d76b32fe33629d55f782b`
- plan role: mutable provenance only; not a persistent semantic gate

## RETURN_ANALYSIS

Formal return:

- path:
  `C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7\msg\file\2026-07\r5_n71_gap_v2_obs_return.zip`
- bytes: `25437`
- SHA256:
  `6855ed551940a460dc06414a007f48d88a4abe5a4275e8ae268246e2527ec558`
- supplied return sidecar: `false`
- sidecar blocker: `RETURN_SIDECAR_NOT_PROVIDED`
- CRC, unsafe/duplicate path and exact-set checks: pass
- actual file count: `12`
- `RETURN_MANIFEST` allowlist-only, size and per-file SHA checks: pass
- return manifest status: `incomplete`

Bound source:

- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v2_obs.zip`
- ZIP bytes: `1777110`
- ZIP SHA256:
  `c3fe06f6e0110b41936b69ae264a24b2dc2d76779efc589c4fe34378b6891b8f`
- sidecar SHA256:
  `d4008551f3e19c1e5960cc3a44a1986b7363deec08246004e6e4391fa152d84f`
- sidecar content:
  `c3fe06f6e0110b41936b69ae264a24b2dc2d76779efc589c4fe34378b6891b8f  r5_n71_gap_v2_obs.zip`
- source ZIP CRC: pass
- returned `PACKAGE_MANIFEST`, SCA and SCA_D byte-equal to source: true

Package/install preflight:

- package preflight valid: `true`
- installed preflight valid: `true`
- installed file count: `75`
- preload/readback/repeat counts: `25 / 48 / 8`
- source ZIP runtime readback-target count: `0`
- post-install, pre-simulation runtime readback targets absent: `true`
- server source files inspected by package: `false`

Observer transport:

- package-local observer SHA256:
  `47f0d66728f47c92f9f93f8cf87b47a0ff8567d587c3a099e2d03f610af09f49`
- precompile readable/hash/identity receipt: pass
- XMR elaboration-constant gate: pass
- checked generated references: `198`
- runtime-indexed generated references: `0`
- compiler parsed the package-local observer at compile-log line `2394`
- v1 missing-include blocker: closed

Execution and conjunctive result gate:

- compile exit: `2`
- simulation exit: `125` (`not started`)
- runner exit: `2`
- simulation started: `false`
- natural terminal: `false`
- SCA/SCA_D loader echoes: `false / false`
- preload count exact: `false`
- formal dump count exact: `false`
- dynamic formal readbacks: `0`
- missing: `48`
  (`16 sum_int32 + 16 scaled_fp32 + 16 final_uint8`)
- mismatch bytes: `0`, which does not pass because the formal exact-set is
  absent
- gate conjunction `all_terms_true`: `false`
- returned gate status: `NODE0071_GAP_SERVER_FAILURE`

The fail-closed gate behaved correctly. No missing, preseeded or stale output
was called PASS, and this return supplies no E3/E4/E5 evidence.

Machine artifacts:

- analyzer:
  `resnet50_pipeline/gap_node0071_v2_return_analysis.py`
- analyzer SHA256:
  `ebd213bc398c08c09af30c9c08c976c7de83977bfb25d4da79469b9ea942e750`
- CLI:
  `tools/analyze_gap_node0071_v2_return.py`
- CLI SHA256:
  `aafac134c3a18c08d96f77b0978b38d833b844527170939bb41474af9c1e6b7e`
- test:
  `tests/test_gap_node0071_v2_return_analysis.py`
- test SHA256:
  `2e7ae63fd3852a79ae69141837405c58999a693c54c5a4030e72e6cce824edbe`
- report:
  `artifacts/operator_config_validation/r5-gap-node0071-v2-return-analysis/report.json`
- report SHA256:
  `a5caeecab039aa039680b8981ae5aa0be269a4a1417d6263ba3ba2373f9b15f0`
- test result: `5 tests`, all passed

## FIRST_DIVERGENCE

The v1 package-local include failure is no longer present. The first fatal
divergence in the new evidence is:

- classification:
  `SERVER_RTL_PORT_INTERFACE_MISMATCH_BEFORE_SIMULATION`
- compile-log error line: `2451`
- returned RTL location line: `2452`
- reported location: `SA_PE_ALU/SA_ALU.v:124`
- undefined-port evidence line: `2453`
- instance: `SA_PE_Mul_Array u_SA_PE_Mul_Array`
- undefined port: `slice_rst`
- compile summary: `1 error` at line `2461`

The returned log proves that `SA_ALU` connects `slice_rst` when instantiating
`SA_PE_Mul_Array`, while the compiled module definition does not expose that
port. This is a server RTL interface failure observed before simulation, not a
GAP config, observer transport, sum-stage or exact-tail numerical divergence.
No server file beyond the returned ZIP was read or inspected.

## BLOCKER_DELTA

Closed:

- v2 source ZIP, sidecar, manifest, SCA and SCA_D identity binding;
- source/install runtime-readback target absence;
- package-local observer readability, hash and compile include transport;
- XMR elaboration-constant gate;
- v1 `native_return_observer.svh` missing-include blocker;
- v2 return exact-set and fail-closed gate adjudication.

New:

- `B_GAP_NODE0071_SERVER_RTL_SA_PE_MUL_ARRAY_SLICE_RST_INTERFACE_MISMATCH`

Still open:

- `RETURN_SIDECAR_NOT_PROVIDED` for this v2 return;
- successful compile and simulation start;
- natural terminal and SCA/SCA_D loader echoes;
- exact 25 preloads and 48 formal dumps;
- complete 48-file dynamic readback set with missing=0 and mismatch=0;
- final server/Trassic2.0_RTL identity binding;
- E4/E5, performance and production resource closure;
- Dequant consumer endpoint and integrated node0071-D to node0072-A E2.

The GAP package slot is no longer `PACKAGE_READY_NOT_RUN`; it is an
adjudicated compile failure. Any mainline global pending-package count should
therefore decrement by one unless another concurrent package replaces it.
The complete local config-only ONNX E2 count remains `3/78`.

## RULE_DELTA_PROPOSAL

No public rule delta is proposed. Existing rules already require:

- compile success before dynamic evidence;
- conjunctive terminal/readback PASS;
- no inference from zero readbacks after a pre-simulation compile failure;
- server-source failures to remain separate from config/numeric failures.

Changing the observed `slice_rst` interface would require functional RTL
authority and an exact server-source identity, neither of which is authorized
in this task.

## PACKAGE_RELEASE

- analyzed source identity: `r5_n71_gap_v2_obs`
- source ZIP SHA256:
  `c3fe06f6e0110b41936b69ae264a24b2dc2d76779efc589c4fe34378b6891b8f`
- final state: `ADJUDICATED_COMPILE_FAILURE`
- preserve source and return evidence read-only: `true`
- package-side legal fix confirmed: `false`
- fresh next package authorized: `false`
- next identity generated: `false`
- existing ZIP rebuilt or modified: `false`
- uploaded/run: `false / false`

No package is released at `PACKAGE_READY_NOT_RUN` from this return.

## Claim and reuse boundary

- GAP numerical analysis repeated: `false`
- frozen six-stage sum retested: `false`
- frozen exact UINT8 tail retested: `false`
- accepted node0071 local-E2 assets consumed as immutable reuse: `true`
- v2 package/manifest/observer assets consumed for identity adjudication:
  `true`
- host-precomputed dynamic or final tensor replayed: `false`
- retained claim: `CONFIG_ONLY_CORRECTNESS_BASELINE` local E2 only
- production/E3/E4/E5 claim: `false`
