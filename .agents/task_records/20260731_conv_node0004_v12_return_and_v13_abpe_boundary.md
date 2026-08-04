# Conv node0004 v12 formal return adjudication and v13 ABPE boundary package

## Scope

- Owner: Conv/SA.
- Mainline: `019fa2ca-72bc-7753-8d58-81e59bc76c88`.
- No plan, public-rule, functional-RTL, server, or other-family mutation.
- `numeric_analysis_repeated=false`.
- `node0004_workload_rebuilt=false`.
- Frozen v12 workload/package consumed read-only.

## Current receipts

- `.agents/plan.md` (mutable provenance):
  `e4beaa39dfd5bd3c247d546dc2fc431758e1038cbef806e7b5a8f5b49e09ac6a`.
- `.agents/rules/生成前必读索引.md`:
  `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f`.
- `.agents/rules/服务器测试包生成规则.md`:
  `7672b44bbcb7e130792d6b288188caa2509dc72b1ea3962bf44ffb82588009aa`.
- `.agents/rules/INT8_SA点积专项规则.md`:
  `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`.
- `NDP_copy01/README_HARDWARE_SIM_ENTRY.md`:
  `4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7`.

Final ZIP generation后已重新完整读取以上四个活动入口；全部
current-match。

## Return identity and envelope

- Return:
  `r5_n4_hw_v12_hangloc_returngate_return.zip`,
  76005 bytes,
  SHA256
  `4c6913a037b3211fbacb1c6c81bad29ea854b71787969ca6becff40450045efb`.
- Adjacent sidecar file SHA256:
  `afa15d897aa05d32e118fef7d2c4aa16847acc463ce63bc23fb519668ba3f769`;
  declared name/hash exactly match.
- Frozen source package:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v12_hangloc_returngate.zip`,
  SHA256
  `80d489798af019b00bba7ee7a7b6060de9f4cf77c2b6e57b11955995803e2e6d`.
- ZIP CRC, single root, 14-entry exact set, allowlist byte size and SHA all
  pass.
- Package/install/observer preflight pass. Observer source SHA is
  `ec7241e77c548b8f793cbb45e8d8500ea65c402563ec27c0ac72f9f9eb2655a9`;
  package-local source, compile include/macro, runtime and return binding pass.

## Dynamic result

- Compile exit 0; run exit 0; signal `NONE`.
- Simulation did start and advanced to 4,084,490,625 ps.
- It did not reach natural Conv terminal. Observer intentionally stopped the
  run after the bounded stall decision.
- Qualified progress was 144 in window 1 and remained exactly 144 through
  windows 2--5; the final four 262144-cycle windows each had `delta=0`.
- Final qualified counters:
  `req0=32, req1=32, req3=28, rdata0=12, rdata1=12, rdata3=24,
  d_req=4, d_wdata=0`.
- Buffer edge witnesses:
  `Buffer4 write=2, Buffer4 read=1, Buffer5 write=0, Buffer5 read=1`.
  Raw continuously asserted levels were not counted as progress.
- The unique canonical decision is
  `LONG_RUNNING_HANG_AT_BUFFER4_READ_WITNESS_TO_BUFFER5_WRITE_WITNESS`.
- Formal D readback is absent. `missing=all, mismatch=0` is not numeric PASS.

## First divergence and source closure

The last good boundary is c0 `Start_Comp`, qualified A/B/C requests/read data,
and one Buffer4 read edge. The first bad boundary is before the first
qualified Buffer5 write and before any visible SA group result.

The v12 return is insufficient to identify one functional/configuration root
cause inside that interval:

1. A one-sided ping-pong mismatch is excluded. The final JSON disables both
   memory-stream and SA-inport ping-pong. Active RTL keeps the MSE buffer
   selector at source 0 when disabled
   (`WR_Buffer_AG.sv:197-213`, `Stream_Engine_Connect.sv:219-232`) and keeps
   the SA selector at source 0 unless the independently enabled terminal
   condition toggles it (`SA_Inport_Connect.sv:75-87`).
2. Buffer5 read-request level is not a write barrier. Buffer5 write enables
   require a valid SA array output; the final selected SA output tag has no
   valid lane. Therefore Buffer5 no-write is a consequence, not yet the root.
3. The SA control matches A/B only after both masked operand-valid bits are
   present (`SA_PE_Control_Block.sv:112-122`) and independently backpressures
   the missing operand (`SA_PE_Control_Block.sv:288-298`). The v12 observer
   does not expose those masked bits or the following ALU/outbuffer
   handshakes.
4. All 28 slice MSE summaries are identical, excluding a single-slice random
   failure.

Formal root cause is therefore
`UNRESOLVED_AFTER_EXHAUSTIVE_AUDIT`, with one missing composite boundary:

`Buffer0/2 group accept -> per-PE masked A/B -> ALU accept ->
PE outbuffer accept -> SA group output`.

## v13 narrow successor

Generated:

- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v13_abpe_boundary.zip`
- ZIP SHA256:
  `a9e941dbb108f3672d05005ce04e02314dbfb87b410626a0233f1e07c830e5c9`
- ZIP bytes: 5,812,500.
- Sidecar SHA256:
  `b506e51d597bfd83ad9d8ecfa5906d72b813502cf1bbcb73093597257ac2765c`.
- Classification:
  `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`.
- `candidate_release=false`, `server_rtl_entries=0`.

v13 preserves the frozen JSON, bitstream, execplan, SCA, input and golden
bytes. It enables the existing finite MSE0 trace and emits exactly one
`ABPE_BOUNDARY_V1` record with qualified A/B/C group-accept, ALU-accept,
PE-outbuffer-accept and SA-group-output-accept counts plus per-PE masked-valid
snapshots. These probes do not enter the canonical progress sum.

## Commands and exits

1. Formal return analyzer:

   `python tools/analyze_node0004_v12_hangloc_return.py ...`

   Exit 0. Analyzer SHA256:
   `0da634dd3545f5dfceddd12d00530d1fc395446ab368cba2116a8bfd9425768b`.
   Report SHA256:
   `2a806e13e52a6025a948fc6073679182a1eed7a8a1f035f9e07cafa603a9c09f`.

2. v13 builder:

   `python tools/build_node0004_v12_abpe_boundary_package_v13.py`

   Exit 0. Repeated-build tree and ZIP identities are equal.

3. Final-ZIP independent self-audit:

   `python tools/validate_node0004_v13_final_zip_rule_self_audit.py
   --project-root . --zip ... --sidecar ... --python ... --builder ...
   --output ...`

   Exit 0;
   `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`;
   `errors=0`;
   all common and ABPE negative controls fail closed.

The four ABPE negative controls independently remove the ABPE record,
runtime ABPE binding, finite deep binding, or inject an ABPE level into the
progress expression. Each fails closed.

## Evidence boundary

- E3: false (diagnostic stop, no natural terminal/formal D).
- E4: false.
- E5: false.
- `RULE_DELTA_PROPOSAL=NONE`.
- `PACKAGE_RELEASE=r5_n4_hw_v13_abpe_boundary.zip`,
  `PACKAGE_READY_NOT_RUN`.
