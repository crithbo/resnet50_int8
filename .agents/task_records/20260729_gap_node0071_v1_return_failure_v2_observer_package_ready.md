# GAP node0071 v1 formal return adjudication and v2 observer package record

- date: `2026-07-29`
- owner family: `QLinearGlobalAveragePool / node0071`
- unique mainline:
  `019fa2ca-72bc-7753-8d58-81e59bc76c88`
- local claim: `CONFIG_ONLY_CORRECTNESS_BASELINE`
- v1 return status: `ADJUDICATED_COMPILE_FAILURE`
- replacement package status: `PACKAGE_READY_NOT_RUN`
- functional RTL modified: `false`
- server inspected/uploaded/run: `false`
- lease acquired: `false`
- GAP numeric analysis repeated: `false`
- accepted sum/tail/local-E2 reuse consumed: `true`

## Control-plane and rule receipt

- server-package rule SHA256:
  `153b0f03210f8e4f98b6b39a7ca7a40b11c788085ba3775826e42beb171167a2`
- common operator-config rule SHA256:
  `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171`
- generation index SHA256:
  `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f`
- GAP family rule SHA256:
  `b194d525fb7c1647b3fdaabd51d88dc4bc9b874ce7a910d4fdd1ca125b56fd96`
- hardware simulator entry receipt SHA256:
  `4318f5a9065352402064620dc05747376a78d16c42dc27fe38ee73b0dc81fb04`
- mutable plan SHA256 at final materialization:
  `638b175804560a502516b15eb98bae1a00c08ee6d7f0fb3031d722b3c4197dfc`
- plan role: mutable provenance only; not a persistent semantic gate

## RETURN_ANALYSIS

Formal return identity:

- return ZIP:
  `C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7\msg\file\2026-07\r5_node0071_gap_hw_v1_return.zip`
- bytes: `23237`
- SHA256:
  `f084ccbae33a1e998ed99047da4d8f98d22ed85895b7ed4457ac090449843205`
- supplied sidecar: `false`
- return-sidecar blocker: `RETURN_SIDECAR_NOT_PROVIDED`
- ZIP CRC and unsafe-path checks: pass
- exact returned file count: `11`
- `RETURN_MANIFEST` exact allowlist, file-size and SHA checks: pass

The returned `PACKAGE_MANIFEST.json`, `SCA`, and `SCA_D` are byte-equal to the
bound source package:

- source ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_node0071_gap_hw_v1.zip`
- source ZIP SHA256:
  `bb5818c4071eacd220c669941169e181b51018d0591d85d51b01f0a7bd732b74`
- source ZIP bytes: `1766963`

Installed preflight proves that package validation passed, all 48 formal
readback targets were absent before simulation, the installed file count was
75, preload count was 25, formal readback count was 48, and repeat count was
8.

Execution result:

- compile exit: `2`
- simulation exit: `125` (`not started`)
- runner exit: `2`
- natural completion: `false`
- terminal observed: `false`
- formal dynamic readbacks produced: `0`
- missing formal readbacks: `48`
  (`16 sum_int32 + 16 scaled_fp32 + 16 final_uint8`)
- mismatch bytes: `0`, which cannot satisfy PASS because the exact readback
  set is absent
- returned gate status: `NODE0071_GAP_SERVER_FAILURE`
- conjunction result: `false`

The fail-closed gate therefore behaved correctly under
`CDA-SERVER-RESULT-GATE-CONJUNCTION-001`; no partial or empty readback result
was promoted to PASS.

The first divergence is compile-log line 2394:
`Error-[SFCOR] Source file cannot be opened`. Lines 2395-2396 identify the
missing relative include `native_return_observer.svh`; lines 2398-2399 bind it
to the target testbench include at reported TB line 5854. The exact v1 source
ZIP contains zero observer entries and its compile command provides no
package-local observer include directory. Simulation never began, so this
return is neither supporting nor contradicting dynamic GAP numeric/config
behavior and cannot support E3/E4/E5.

Machine adjudication:

- analyzer:
  `resnet50_pipeline/gap_node0071_return_analysis.py`
- analyzer SHA256:
  `89f1ac836b45c0e9a77d232dcc949227bbac357d5fb60ea0a6f3782f291edd00`
- CLI:
  `tools/analyze_gap_node0071_hw_v1_return.py`
- CLI SHA256:
  `b1deb45c6e0eda7023505dd56f05455194e3d3c55b9e19ac95afb3cf7e9876a1`
- report:
  `artifacts/operator_config_validation/r5-gap-node0071-hw-v1-return-analysis/report.json`
- report SHA256:
  `251971737d9a9cf09c361d87bd66cc0479f21e653ce81faa7fa7c839b3cef5f2`

## BYPASS_ANNOTATION

1. `bypass_reason`: preserve the accepted node0071 config-only numeric
   producer and repair only the package-local observer include binding proven
   missing by the formal return.
2. `contradicted_or_missing_native_path`: v1 ships no observer and passes no
   package-local include path although the target TB unconditionally includes
   `native_return_observer.svh`. Server TB/RTL edits, transout, repair_v9,
   RTL_CONTROL and CONFIG_SEMANTICS repair routes remain frozen.
3. `exact_equivalence_scope`: v2 is equivalent only to the exact bound v1
   node0071 numeric/config/bitstream/execplan/SCA semantics. It changes the
   fresh install namespace and observer transport only; it does not generalize
   GAP, AverageRequant or Quantize capability.
4. `materialized_configuration_mechanism`: a fresh identity ships the frozen
   read-only observer under package-local `tb_probe/`, verifies its SHA and
   elaboration-constant XMR paths immediately before compile, passes
   `+incdir+<package_root>/tb_probe` through `VCS_EXTRA_OPTS`, and returns the
   precompile receipt through the exact allowlist.
5. `performance_and_resource_cost`: the package adds a 111824-byte observer,
   one precompile static check and one returned receipt. It adds no compute
   stage, scratch allocation or numerical pass; compile/elaboration overhead
   is not yet measured.
6. `unresolved_production_blocker`: v2 has not run; v1 sidecar is absent; final
   server/Trassic2.0_RTL identity is unbound; dynamic terminal/readbacks,
   E4/E5, performance/resource closure and the Dequant consumer endpoint
   section remain open.
7. `claim_boundary`: the accepted local result remains only
   `CONFIG_ONLY_CORRECTNESS_BASELINE`; v2 is only
   `PACKAGE_READY_NOT_RUN`, not a dynamic, production, performance, E3, E4 or
   E5 result.

## BLOCKER_DELTA

Closed:

- v1 return identity, strict allowlist and source-package binding adjudicated;
- fail-closed gate behavior confirmed;
- first divergence localized to package-local observer include binding;
- evidence-based legality of a package-only fresh-identity repair established;
- deterministic v2 package materialized without changing numeric payloads;
- GAP producer endpoint identities refreshed without changing its
  storage/base/offset/coverage/visibility/lifetime semantics.

Added or still open:

- `RETURN_SIDECAR_NOT_PROVIDED` for the v1 formal return;
- v2 compile/simulation/natural-terminal result;
- exact 48-file dynamic formal readback set and zero-mismatch conjunction;
- final server and Trassic2.0_RTL source identity binding;
- E4/E5 and production performance/resource closure;
- `B_GAP_NODE0071_TO_NODE0072_DEQUANT_CONSUMER_SECTION_MISSING`;
- integrated node0071-D to node0072-A first-read/release E2.

The failed v1 package is no longer counted as a pending runnable candidate; v2
replaces the same GAP package slot. Under the prior mainline baseline, the
global `PACKAGE_READY_NOT_RUN` count therefore remains 2 rather than
incrementing.

## RULE_DELTA_PROPOSAL

No public rule delta is proposed. The existing package-local observer
transport, elaboration-constant XMR check, runtime readback-target absence,
conjunctive PASS gate and return-manifest allowlist rules fully cover the
observed failure and the v2 remedy.

## PACKAGE_RELEASE

Failed evidence identity, preserved read-only:

- identity: `r5_node0071_gap_hw_v1`
- ZIP SHA256:
  `bb5818c4071eacd220c669941169e181b51018d0591d85d51b01f0a7bd732b74`
- state: `ADJUDICATED_COMPILE_FAILURE`
- rebuild or modification: `false`

Fresh replacement:

- install/package identity: `r5_n71_gap_v2_obs`
- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v2_obs.zip`
- ZIP bytes: `1777110`
- ZIP SHA256:
  `c3fe06f6e0110b41936b69ae264a24b2dc2d76779efc589c4fe34378b6891b8f`
- sidecar:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v2_obs.zip.sha256`
- validation:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v2_obs.validation.json`
- validation SHA256:
  `f5f34434ce0f89ac0a64f6eeb9bdeac51dcf101375f3bda0519959bac3b39f5c`
- status: `PACKAGE_READY_NOT_RUN`
- actual upload/compile/run count: `0 / 0 / 0`
- functional RTL changes: `false`
- server RTL entries: `0`
- server file writes required: `false`
- source numeric payload tree preserved: `116 files`, byte-equal
- source sum/tail numerical execution repeated: `false`
- package preload/formal-readback counts: `25 / 48`
- runtime readback targets in ZIP: `0`
- result gate fail-closed: `true`
- return collector exact allowlist only: `true`
- independent builds and ZIPs byte-identical: `true`
- fresh-extract runtime preflight tree mutation: none
- sole future server command:
  `bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX`

No package was uploaded or run in this task.

## GAP to Dequant shared endpoint continuation

Only the GAP-owned producer section of
`contracts/operator_config/resnet50_node0071_node0072_shared_endpoint_v1.json`
was refreshed with the v1 formal-return failure and v2 replacement-package
identities. The accepted physical endpoint remains unchanged:

- storage ID:
  `r5:activation:node-0071:D:tensor-ab32f279540568c3:batch-slice-sharded-16x2048-v1`
- active-slice base:
  `D_base(slice)=0x000a2000+(slice_id<<25)`
- offset: `0`
- coverage: `2048 B/slice`, `32768 B` across 16 active slices
- occurrence:
  `addr=base+32*occurrence`, `0<=occurrence<64`
- producer visibility and lifetime/release requirements: unchanged

Final endpoint identities:

- canonical manifest SHA256:
  `9a832711eccd406d32ce802268889ecd67a9944a841d8cd8445af206ec93c2b0`
- GAP owner-section content SHA256:
  `2113dd0f538757efc1cd48e313806d03f1ca133d4f40f021ba84d3ce94945473`
- validation report SHA256:
  `4e44e487a7a3ee35d257313a4fbd1c6f69a913ab2f7d1061f1ed0dbcfb6b5ead`
- Dequant consumer section: missing
- integrated endpoint closed: `false`
- endpoint-level package generated: `false`
- existing package rebuilt or modified for endpoint work: `false`

The complete ONNX local config-only E2 count remains `3/78`. No GAP sum,
tail, complete-node or endpoint numerical analysis was rerun.
