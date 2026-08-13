# Conv native four-lane p25 formal return and p26 Memory_AG successor

Date: 2026-08-09  
Owner: native four-lane Conv performance branch  
Mainline return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`

## Formal p25 identity and internal receipt

- Formal return: `C:/Users/15383/Downloads/r5_n4_0cc_p25_pe7src13_r1786206206960470201_4177943_return.zip`
- Return bytes: `2016259`
- Return SHA256: `41f74570a7455c855a56ada6318e5cce6a47f6ba0d128acb4c61be41d05c572b`
- Execution identity: `r1786206206960470201_4177943`
- Exact source p25 bytes: `5882004`
- Exact source p25 SHA256: `d2c0e853391f012273e6d6bb2e07c6e3bcbee0d895db5b866c77526c580390e6`
- Source after formal consumption: `artifacts/operator_config_validation/r5-server-test-packages/tested/conv_native_four_lane/r5_n4_0cc_p25_pe7src13/r5_n4_0cc_p25_pe7src13.zip`
- Machine analysis: `outputs/conv_native_four_lane_0ccae916_p25_return_analysis/report.json`, bytes `10251`, SHA256 `17e1793cf787659c69b074304d3800c18b3fa094ae33030d98b6a64b01d8acbf`

The return passes transport identity, CRC, one safe root, exact manifest set, exact allowlist,
embedded source-manifest binding, unique per-execution basename, package/install/observer/path-budget
preflights, install-only runtime layout and NDP-root direct name+type exact-set. Production VCS compile
and elaboration exited zero; the c0 simulator started and its feature binding receipt is valid.

The run was externally interrupted with `INT` (`run_exit_status=125`) after qualified progress.
Therefore the absent natural terminal and absent formal D are not promoted to a functional,
configuration or numeric failure. p25 is c0 diagnostic-only with `formal_readback_count=0`; it does
not claim c0 slice finish, 27/27 natural terminals, 320/320 formal D, mismatch zero, E3, E4, E5 or
server performance.

## p25 public-chain adjudication

p25 emitted exactly one qualified `PUBLIC_PE7_SOURCE13_V2` row and two state rows. The qualified row
has `event_mask=0x7`, `src_id=13`, `src_is_pe7=1`, `pe7_valid=pe7_bp=1`,
`connect_valid=connect_bp=1`, `memory_valid=memory_bp=1`, `select_eq=port_eq=1`, and both Connect and
Memory-WR carry index `8`. The single event-mask record preserves all three simultaneous edge
classes. The two state rows are not counted as transactions.

Actual production identities collected after successful compile include:

- `IGA_Interconnect.sv` SHA256 `f46f68b1eb1edc2a4ff85ce6894b8f549727512f9d3e6527d6954d7bb352c82e`, authority match;
- `Stream_Engine_Connect.sv` SHA256 `0ca375c4af56f7f6fe9e7055a39ac7370d91e6048b2aa9f3ae0a4910deae5425`, authority match;
- `Memory_WR_Stream_Engine.sv` SHA256 `c97a5b4a3587384d5b57b2a5db288a44b2166584c236307c69d26bb04f389127`, authority match;
- `Memory_AG_Idx_Queue.sv` SHA256 `2f534813b8d73ff19961541b910c03b417f401d73ae98b2e446e728f384a7b3e`,
  differing from the package cloud receipt `b555ab22523540a9aa49d3eb51dee6eea9962086a71429028c69964de3819989`.

The Memory_AG difference is nonblocking provenance because production compile and simulation
passed. It makes the actual runtime Memory_AG handshake authoritative for the next causal decision.

```text
LPG = production compile/sim + actual IGA/Connect/Memory-WR identity
      + source13=PE7 + same-sample source13/Connect/Memory-WR qualified index8 accept
FD  = after Memory-WR input accepts index8, before actual Memory_AG all-match/queue-write
HANG_ROOT_CAUSE = ROOT_NOT_YET_UNIQUE_MEMORY_AG_INDEX8_MATCH_TO_QUEUE_WRITE
classification = PARTIAL_INTERRUPTED_AFTER_QUALIFIED_PE7_SOURCE13_TO_MEMORY_WR_ACCEPT
```

Remaining observational equivalents are: another Memory_AG input/mode/keep/same/gotten predicate
blocks all-match; all-match occurs but queue-write does not; or queue-write occurs but downstream
queue-read/WR-Memory-AG consumption is blocked. No config leaf or functional RTL fix is authorized.

Blocker delta:

- closed: actual IGA identity; actual PE7/source13→Connect edge; Connect→Memory-WR index8 acceptance;
- opened: p25 exact observer contains the already compiled `EPOCH_FLOW_V1` block but its runner did
  not enable `+RETURN_OBS_EPOCH_FLOW`;
- preserved: actual Memory_AG index8 match→queue-write, c0 slice finish, 27 natural terminals,
  formal 320D and E4/E5.

## p26 continuous-closure release

Disposition: `PACKAGE_READY_NOT_RUN / PERFORMANCE_DIAGNOSTIC_CANDIDATE`;
`candidate_release=false`.

- Pickup ZIP: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p26_memag.zip`
- ZIP bytes: `5881902`
- ZIP SHA256: `844360af973a6687fe9b0e202e169cfe176df42000859fbd88a15b559b3cce25`
- Command: `bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02`
- Expected return: `/home/panqs/ndp/simresult/r5_n4_0cc_p26_memag_r<epoch-ns>_<pid>_return.zip`

p26 is the highest-information narrow successor. It retains p25's exact observer SHA256
`e54a72e0f6e96f0ae26b33312881c71fb4927d4c4986da895ab18c026322daf1` and enables both:

- `+RETURN_OBS_SELECT_PORT +RETURN_OBS_SELECT_PORT_QUAL_LIMIT=128 +RETURN_OBS_SELECT_PORT_STATE_LIMIT=64`;
- `+RETURN_OBS_EPOCH_FLOW +RETURN_OBS_EPOCH_FLOW_LIMIT=256`.

The first ledger preserves the proven source13→Connect→Memory-WR boundary; the second exposes the
actual Memory_AG input valid/same/gotten/keep masks, all-match predicate, queue full/empty,
qualified queue-write/read, modes, keeps, indices, tags and source backpressure. Both features run
in the same c0 prefix and owner clock. The observer/XMR bytes already passed p25 production compile,
so package-local HDL is receipt reuse; the changed dual runtime binding is blocking-applicable and
passes its exact positive and missing-feature/wrong-limit/reordered/duplicate fail-closed controls.

Frozen from p25: 87/87 installed payload members byte-equal, both SCA files identity-normalized
equal, numeric/W3/workload/config/mapping/bitstream/execplan/golden/timeout, functional RTL, ISA,
hardware and active ndp-sim. No server/upload/run/lease action was performed.

## Exact p26 local gates

- Deterministic double build: PASS.
- Family audit: `pending_receipts/conv_native_four_lane/r5_n4_0cc_p26_memag/r5_n4_0cc_p26_memag.family_audit.json`,
  bytes `428221`, SHA256 `729605538e2959fa3b4cb2847e2d8cbac9eab4200d0342c31a382466681c15eb`, PASS/errors0.
- Runner harness: `pending_receipts/conv_native_four_lane/r5_n4_0cc_p26_memag/r5_n4_0cc_p26_memag.runtime_layout_harness.json`,
  bytes `9545`, SHA256 `c497eab6b102767e9e2c438b51b04d106ad6d3f080129b0d81b066d82b97bba2`;
  normal/preflight-fail/compile-fail/HUP/INT/TERM all reach the shared finalizer, publish the unique
  fixed-simresult return and preserve the NDP-root direct exact set.
- Shared runtime-layout validation: `pending_receipts/conv_native_four_lane/r5_n4_0cc_p26_memag/r5_n4_0cc_p26_memag.shared_runtime_layout.json`,
  bytes `24848`, SHA256 `e3ebb00c1ded5fd41b64c52fe3288b365145198b04a5e98ce1571e126968c102`,
  PASS/errors0, exact-final-ZIP invocation count one.
- Shadow build profile: `pending_receipts/conv_native_four_lane/r5_n4_0cc_p26_memag/r5_n4_0cc_p26_memag.build_profile.json`,
  bytes `12886`, SHA256 `5b5c95f711c9bcf28d6b01899920aec0580789fe9cabf4b3bc2c1230f9478821`,
  contract valid/errors0.
- Final ZIP audit: `pending_receipts/conv_native_four_lane/r5_n4_0cc_p26_memag/r5_n4_0cc_p26_memag.final_zip_audit.json`,
  bytes `4656`, SHA256 `424364faafa8b3273906b3020e4da09a9260914e54ea6f5eaa0a69da95a78cfe`,
  `PACKAGE_READY_NOT_RUN`.
- Current storage index: bytes `239713`, SHA256
  `e16922a1c8caf140ea9516c4f63e1991a6c6bd5de28f82c2df8348b7342d8887`, PASS. p25 is tested;
  p26 is the sole `conv_native_four_lane` pending ZIP; pending remains flat ZIP-only.

The frozen config occurrence inversion remains native `51,380,224` versus serialized
`205,520,896` (`4.0x` reduction), weight bytes `65,536` versus `262,144` (`4.0x`), activation per
producer `12,845,056` versus `51,380,224` (`4.0x`), and maximum useful lane utilization `100%`
versus `25%`. These are byte-identical config/occurrence receipts, not server E4/E5 or wall-clock
performance claims.

## Current rule receipts and feedback

- `.agents/agent.md`: `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f`
- `.agents/plan.md`: `4f04b3e207a5fd200b6bbc6e66b6c0a312d1e4f24317cd9266d31d2018aecc13`
- generation index: `db4160367cc7046a73910a5370c8b0629e3403fce31ebe6c0e986c6451b36a81`
- server package rule: `3d2c7098dcb06ccd1a0393a5f392d1df77ac8d5d47a2d0320af2f829e2f6bd9c`
- config rule: `dc5243226bacde799b368d37fb9eb656e6b7e3d33a0a2932ae72ab35415ae3e1`
- hardware semantics: `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055`
- INT8 SA rule: `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`
- UINT8 tail rule: `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e`
- convergence optimizer: `e52ab12c78edca3ada0eabf26a323b3da7a9fb6dc0bb07dab594793eee8e87ff`
- hardware entry: `0b271cd2ba4f16a0fd277d8f52f926be0ef51431ab9a995042363215afb9caa6`

`RULE_CONFIRMATION`:

- `CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001`
- `CDA-SERVER-DIAGNOSTIC-FEATURE-RUNTIME-ENABLE-END-TO-END-001`
- `CDA-SERVER-DIAGNOSTIC-EVENT-QUALIFICATION-001`
- `CDA-SERVER-DIAGNOSTIC-LOGGER-PARSER-EXACT-FORMAT-TRACE-001`
- `CDA-SERVER-DIAGNOSTIC-MULTICLASS-EDGE-NO-LOSS-001`
- `CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001`
- `CDA-SERVER-CLOUD-GITHUB-RTL-AUTHORITY-NONBLOCKING-DIFF-001`
- `CDA-SERVER-INSTALL-SUBTREE-RUNTIME-LAYOUT-001`
- `CDA-SERVER-NDP-ROOT-TOPLEVEL-NO-NEW-ENTRY-001`
- `CDA-SERVER-RETURN-FIXED-SIMRESULT-ATOMIC-PUBLISH-001`
- `CDA-SERVER-PACKAGE-STORAGE-ROTATION-001`
- `CDA-SERVER-RESULT-GATE-CONJUNCTION-001`

No non-synonymous public-rule gap was found. The p25 runtime-enablement escape is already covered by
the current end-to-end feature-binding rule, so no new rule is proposed. Any future rule delta would
apply only to a later fresh identity and does not retroactively hold p26.
