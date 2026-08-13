# 2026-08-05 Conv native-four-lane p6 cloud-nonblocking adjudication and p7 successor

## Scope and ownership

- owner: `019fc783-1146-7901-9e40-64d0ed8e052d`
- unique mainline/return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- operator family: frozen Conv node0004 native-four-lane performance diagnostic
- serialized Conv baseline, functional RTL, `.agents/plan.md`, public rules and
  other operator families were not modified
- no server upload, execution or lease was performed

## Current rule and mutable provenance receipts

- `.agents/agent.md`
  - SHA256 `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f`
- `.agents/plan.md` (mutable provenance only)
  - SHA256 `0d1c5577f71d565c7ee4fa6a43054db458de53b41f45813ed2bb3b98be30e126`
- `.agents/rules/生成前必读索引.md`
  - SHA256 `93b66e7986beeaddb01f237710af6874bb4bbfcc4c6c6929563c5e98d8397eb2`
- `.agents/rules/服务器测试包生成规则.md`
  - SHA256 `61753f6866f49aca142545394451cd73c4e634a5aa160b066e020b7c9067cedd`
- `.agents/rules/算子配置规则.md`
  - SHA256 `d4069167000ae5e0076401afbc6c8db20965965ef4f5da30914f40297f59cba0`

## Cloud authority and p6 supersession

Authenticated GitHub compare/blob inspection and the exact local immutable Git
object independently bind:

- repository: `xlsjdjdk/Trassic2.0_RTL`
- branch: `master`
- approved cloud head:
  `0ccae916ef61904a64d6cf8ec1d1931b45e428d8`
- local provenance base:
  `e1fb0f7bb2761d6c804867de0c5d2cb77554c48d`
- diff: 12 commits, 11 files, +497/-30

The targeted causal-cone audit proves that the three p6 production SHA
differences are exactly the three changed compiled leaves:

- `Array_Request_Manager.sv`
  - cloud bytes 14630
  - cloud SHA256
    `026019ed9643b3b7d83bc0888c4f5b89fc4776015524df1c69bacbab5315e557`
- `Buffer_AG_Idx_Queue.sv`
  - cloud bytes 9977
  - cloud SHA256
    `7bbf229f60fb91fe89fd78d8e2df8716cd4de2be3fc578c5270c570ea33c7bca`
- `RD_Data_Channel.sv`
  - cloud bytes 27591
  - cloud SHA256
    `449ce3bb75535b7fb9d7d00f5f940e35165ac47929d29b1c654c4755b3c4fcaa`

The remaining five required production leaves are byte-equal between e1fb0f7
and 0ccae916.  Therefore all eight leaves actually compiled in the formal p6
return equal the exact approved 0ccae916 Git blobs.  The p6 production compile
also had exit 0 and XMRE count 0 with the byte-equal public-interface observer.
This reclassifies the old p6 stop:

- superseded:
  `TERMINAL_NO_PACKAGE_SERVER_RTL_IDENTITY_MISMATCH`
- current:
  `SUCCESSOR_REQUIRED_CLOUD_RTL_NONBLOCKING`

p6 is not reused as a dynamic c0 result: its old runner stopped before the
first simulator invocation.

## Targeted causal-cone result

Only the current native-four-lane c0 causal cone was revalidated:

- direct changed observer owners: Array Request Manager, Buffer AG queue and
  RD Data Channel
- indirect dynamic changes: row-LC FIFO/backpressure, Buffer Manager wiring,
  request depths, and SA-Inport pingpong acceptance
- p6 public observer leaves remain declared at exact 0ccae916
- exact source predicates confirm:
  - row-LC FIFO depth 128 with `valid=!empty`, `bp_pre=!full`
  - Buffer AG depth 32
  - RD channel depth 128
  - request OOO/queue/tag depths 128
  - SA pingpong change requires enable, valid, last, range and acceptance
- low-cost metadata/exact-predicate traces cover empty, first, penultimate,
  final, one-after, push+pop, and invalid/valid pingpong boundaries
- no DUT, numeric, W3, golden or local E2 rerun was performed

Evidence:

- tool:
  `tools/audit_conv_native_four_lane_0ccae916_cloud_causal_cone.py`
  - SHA256 `21e0020c10d530ac44e3d97b0dece6b216b600055b59095129be7c19c077a3c7`
- report:
  `outputs/conv_native_four_lane_0ccae916_cloud_causal_cone/report.json`
  - SHA256 `b441a8c6cf71466d01c86436d02e8611bb54e521b39e70df2699540ecfe4c9e2`
  - valid `true`
  - status `SUCCESSOR_REQUIRED_CLOUD_RTL_NONBLOCKING`

Static evidence does not claim c0 terminal behavior.  The affected queue,
request and pingpong changes make a fresh production simulation necessary.

## Fresh p7 successor

Identity: `r5_n4_0cc_p7`

The p7 source is the exact p6 ZIP:

- `r5_n4_e1f_p6_armif.zip`
- SHA256
  `05fc4f385d544195ad3cbc68256525d70775cc490d4a42ff784e9b9f7c5d34c1`

The p7 member relation is exact:

- source files 97, target files 97
- missing `[]`, extra `[]`
- changed members:
  - `PREPARE_AND_RUN.sh`
  - `README.md`
  - `TEST_PACKAGE_MANIFEST.json`
  - `package_tools/node0004_assumed_hardware_server_runtime.py`
  - `provenance/current_local_rtl_binding.json`
  - `workload/runtime/runs/c0/sca_cfg.json`
  - `workload/runtime/runs/c0/sca_cfg_D.json`
- observer is byte-equal to p6
- all workload/config/bitstream/execplan payload bytes are unchanged
- the SCA pair changes only the fresh install identity
- no functional RTL and no formal 320D payload are carried

Runtime/runner change:

- after successful compile, actual leaf paths/bytes/SHA are always collected
  and returned
- local and cloud expected identities are both recorded
- any actual/local or actual/cloud SHA difference is nonblocking for simulator
  launch
- incomplete identity collection is also returned as an incomplete receipt;
  it may make the final result partial but cannot suppress simulator launch
- package-local observer/manifest/preflight failures remain fail-closed before
  compile

Build and validator:

- builder:
  `tools/build_conv_native_four_lane_0ccae916_p7_cloudnb_package.py`
  - SHA256 `d54ad08fe4a4c0a6fe9057a891092b49904ba6400693847db0b596f4a4c6bac6`
- validator:
  `tools/validate_conv_native_four_lane_0ccae916_p7_cloudnb_package.py`
  - SHA256 `d1c237aef74c3fb9ec0965f0579616eb63bae536cac89438301a62d838bffa1a`
- deterministic dual build: PASS
- build receipt:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_0cc_p7.validation.json`
  - SHA256 `016ba5501dc21e3ebed93e1aa1613779a1e753abc5733a855b71f6aa4a226638`
- final ZIP audit:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_0cc_p7.final_zip_audit.json`
  - SHA256 `18356e21652076085bca87e90f7f70e40a2bc26b7f81d21528a7f12b8b216cb6`
  - valid `true`
  - status `PACKAGE_READY_NOT_RUN`

## Release-gate matrix

The single final `release_gate_matrix` is valid:

- core package/bootstrap/path: PASS
- changed runner compile→simulator→finalizer: PASS
- changed return/result joint gate: PASS
- cloud RTL causal cone: PASS
- package-local HDL: PASS by byte-equal receipt reuse plus p6 production VCS
  compile against the exact eight 0ccae916 leaf bytes
- materialized config: not applicable, byte-equal receipt reuse
- diagnostic predicate trace: not applicable, observer/parser/canonical bytes
  unchanged
- numeric/W3/golden: record-only, not repeated

The safe runner positive control uses the exact eight 0ccae916 immutable Git
blobs.  Three leaf SHA differ from local e1fb0f7, yet the exact final runner
reaches the simulator stub, natural finalizer and exact return sidecar.  Signal
finalization also returns, and a wrong observer SHA fails before compile.
Neither production VCS nor DUT simulation was invoked locally.

## Deliverable

- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_0cc_p7.zip`
  - bytes 5812109
  - SHA256
    `4ff473247a7356af3e6b960430b559e90113b774e27478dbcd41151d8507f8a4`
- sidecar:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_0cc_p7.zip.sha256`
  - SHA256
    `d40aec8235183a6450e3a2d1fa5092c66f7ea8a2d32fc9b715d1413c22831ad3`
- manifest SHA256:
  `05c8fbf822b737bb6c76793b284392ce7e629bddf5cf1d8201d0880f767b9114`
- runner SHA256:
  `8dd96fe8545c0575df4bbca30b1843422e15fd4c2e6e4adf6a83d9f1144621f4`
- runtime SHA256:
  `343882a45fd03ed3d5fb022d518e9e0cb6c216af9698f7ea0915205c4da95fa5`
- observer SHA256:
  `a00c76b17aec6b9b257356cc8b254a571e2958c708630e93a9827691de24e3b3`

After transferring the ZIP and adjacent sidecar, extract into a fresh directory
and run from the extracted package root:

```bash
bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02
```

Expected return at the server root:

- `/home/panqs/ndp/NDP_copy02/r5_n4_0cc_p7_return.zip`
- `/home/panqs/ndp/NDP_copy02/r5_n4_0cc_p7_return.zip.sha256`

The formal return must provide actual compiled leaf identity, successful
simulator invocation, c0 natural/canonical terminal or bounded partial
diagnostic evidence, and exact finalizer/allowlist receipts.  It contains no
formal 320D payload, so p7 alone cannot establish performance, E3, E4 or E5.

## Rule feedback

`RULE_CONFIRMATION`

- `CDA-SERVER-CLOUD-GITHUB-RTL-AUTHORITY-NONBLOCKING-DIFF-001` is necessary:
  the p6 compile was compatible with the exact approved cloud RTL, and the old
  local-SHA equality gate alone suppressed the only needed dynamic result.
- impact-applicability correctly limited fresh work to runner/result/cloud
  causal-cone gates and reused byte-equal observer/config/numeric receipts.
- package-local observer and precompile integrity negatives remain fail-closed.
- no non-synonymous `RULE_DELTA_PROPOSAL` is required.

