# Conv native-four-lane historical v1 formal RETURN and p5 successor

Date: 2026-08-05  
Owner: `019fc783-1146-7901-9e40-64d0ed8e052d`  
Unique mainline / structured return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`

## 1. Assignment and immutable inputs

This task analyzes the historical df23e4d native-four-lane v1 formal return without
modifying or rebuilding v1 or p4, and then closes the mandatory
RETURN-to-successor path under the current e1fb0f7 source baseline.

- Formal return:
  - path:
    `C:/Users/15383/xwechat_files/wxid_vwpfpfs4fgyk22_29b7/msg/file/2026-08/r5_conv_native_four_lane_df23e4d_perf_v1_return.zip`
  - bytes: `121996`
  - SHA-256:
    `8166c8dd85aece80714d051c7d88591f181e4bd35c5c74dc91aa90554867fd44`
- Exact historical source v1:
  - path:
    `artifacts/operator_config_validation/r5-server-test-packages/r5_conv_native_four_lane_df23e4d_perf_v1.zip`
  - bytes: `46027937`
  - SHA-256:
    `5cbf05cac96f887c6753d378c7f3f44daf04f60caa6016f1f41eab274cebd62f`
- Existing content-neutral delivery successor p4:
  - path:
    `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_df23e4d_p4.zip`
  - SHA-256:
    `c8d42f979b07468e869d077755f987c09c04d017cd1bc6ab50a71a8ee1d0204e`
- Current source baseline:
  `e1fb0f7bb2761d6c804867de0c5d2cb77554c48d`
- Current source-sync receipt:
  `artifacts/rtl_sync/trassic_master_e1fb0f7_20260804/report.json`
  SHA-256:
  `c2e57de1d1d05cc1fee3356cce772fbb3c76943cf04bb5366cbc0a4db6e3539c`

The adjacent external return sidecar was absent. The user explicitly waived only
that external transfer receipt. No internal ZIP, manifest, exact-set, source
package, compile, terminal, or formal-D gate was waived.

## 2. Historical v1 RETURN analysis

Machine report:

- `outputs/conv_native_four_lane_df23e4d_v1_return_analysis/report.json`
- bytes: `23104`
- SHA-256:
  `8857cd23f809f59c290eaa0a5216b9213ae3a37bc81d6472a6338c5a984c55dd`
- status: `HISTORICAL_V1_DYNAMIC_FAILURE_CONSUMABLE`
- `valid=true`, `errors=[]`

### 2.1 Package/install/return identity

- Return ZIP is path-safe, single-root, has 18 entries, and has no symlink member.
- Its 17 allowlisted payload records exactly match size and SHA receipts.
- Its returned package manifest is byte-equal to the frozen source-v1 package
  manifest, SHA-256
  `0fb4fc098d7d7faf46bd70907b9dbec2199437eaa0191d443999097d9da6049f`.
- Source v1 ZIP is path-safe, single-root, has 833 entries, and has no symlink
  member; all 832 manifest-described package files match.
- Package preflight is valid:
  - package files: `832`
  - formal readback targets: `320`
  - preloaded readback targets: `0`
- Installed workload preflight is valid:
  - installed workload files: `503`
  - preloaded readback targets: `0`

This is authoritative historical dynamic evidence. It is not an extraction-
contamination failure and is not invalidated by the later p4 package.

### 2.2 Actual production compile identity

The actual VCS compile completed with exit `0`. Independent compile-log parsing
and the returned post-compile receipt bind the simulation to the historical
df23e4d SA leaf set:

- `SA_PE_Float_CSA.v`:
  `72a156f4888af38fa562dbd09a37eed3a9f6a64dedf27d3aa556174d55c5c2f3`
- `SA_PE_Float_Control.v`:
  `00107da5137ada324407ba7dbf3e74d6e32428a42631aa23f44c5077ea7b7eeb`
- `SA_PE_Mul_Array.v`:
  `135306563de4407c7d1279c942a7d1ce4e347dd8d263e3fd4a7d63f0e8a2587a`
- `SA_ALU.v`:
  `c986ea2de79381afb220ccef83f28466ec3bdda39cd4d80255419bfa214fee06`

The receipt source is the actual VCS parse log followed by post-compile leaf
hashing. The current e1fb0f7 source identity is not substituted for this actual
historical compile receipt.

### 2.3 Dynamic result

- required runs: `27`
- returned runs: `1` (`c0`)
- compile exit: `0`
- run exit: `124`
- external signal: `NONE`
- natural terminals: `0/27`
- expected formal D: `320`
- returned formal D: `0`
- missing formal D: `320`
- mismatch byte count: `0`, which is vacuous because no D was returned
- joint result gate: `false`

Classification:

`LONG_RUNNING_HANG_PENDING_ROOT_CAUSE`

No E3, E4, E5, performance-pass, or release claim is made.

## 3. Progress localization

The c0 observer binding is valid. It returned `1207` canonical records:

- `1` `STILL_PROGRESSING`
- `905` `HEARTBEAT`
- `301` `LONG_RUNNING_HANG_AT_EXEC_TO_SLICE_FINISH`

Host observation elapsed `43142` seconds (`11:59:02`).

### LAST_PROVEN_GOOD

`package/install preflight -> actual VCS compile -> cfg start/finish -> exec start
-> first qualified window`

First qualified window, simulation cycle `0 -> 2097152`:

- config start/finish: `1/1`
- exec start/slice finish: `1/0`
- local request accepts: `128`
- local read-data accepts: `118`
- local write-data accepts: `0`
- bank-frame accepts: `52010`
- qualified total/delta: `52259/52259`

### FIRST_DIVERGENCE

`c0 exec_start -> slice_finish`

- first zero-delta window: `2097152 -> 2359296`
- first canonical hang: `2097152 -> 3145728`
- final returned snapshot: cycle `318242816`
- final counters remain:
  `req=128`, `rdata=118`, `wdata=0`, `bank=52010`,
  `qualified_total=52259`, `finish=0`
- final silent windows: `301`

The aggregate `128 - 118` difference is not called “ten outstanding reads”:
the historical observer does not prove a per-engine request/response pairing.

### HANG_ROOT_CAUSE

`UNRESOLVED_AFTER_EXHAUSTIVE_RETURN_AUDIT`

Excluded:

- package exact-set or extraction contamination
- package/install preflight failure
- compile failure
- observer disabled or unbound
- config never started or never finished
- execution never started
- external-signal interruption
- natural completion followed by return-collection loss

Remaining candidates:

- per-MSE request/read-data imbalance or response starvation
- `RD_Data_Channel` metadata/inbuffer/prepared-data blockage
- `Buffer_AG` / `Array_Request_Manager` queue or hold backpressure
- SA/buffer consumer starvation before output write
- MSE4 output request/write-data or finish-propagation blockage

## 4. p4 adjudication and current-RTL boundary

p4 is a content-neutral delivery/extraction successor, not a replacement for the
historical dynamic result:

- compared workload files: `503`
- byte-identical: `449`
- install-identity-only normalized JSON: `54`
- missing/extra/unexpected changed: `0/0/0`

p4 preserves the same coarse observer and therefore does not distinguish the
remaining hang candidates or erase the actual df23e4d run.

The current e1fb0f7 source baseline changes exactly four leaves relevant to the
bounded interval relative to df23e4d:

- `Array_Request_Manager.sv`:
  `d3f100b2a1415ff561791ccafd157b038c4d8e80a80bf18dcedb89c1fec7c4eb`
- `Buffer_AG_Idx_Queue.sv`:
  `b5fc30fa970a4ed38ebdfaf825946a80562ded91d72c600dd1ee89d14103b1ef`
- `RD_Data_Channel.sv`:
  `6c612cdd0eb907678a4825215553fd4a1b1b79869b1314fafba9b0e8c072f60e`
- `Neighbor_Out_AG.sv`:
  `05a6b1eadd2d5fb125a6a9e6b01b03dbbf9cd1bddc32423c01b5b6651cced41e`

Together with the four unchanged SA leaves above, these form the eight-leaf
post-compile identity required by the fresh diagnostic successor. Source hashes
are immutable expected identities; a future actual server compile receipt is
still mandatory.

## 5. Fresh e1fb0f7 p5 diagnostic successor

Fresh identity: `r5_n4_e1f_p5_c0diag`

- class: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`
- `candidate_release=false`
- evidence ceiling: `E2_LOCAL_ONLY`
- server action: none
- formal D: intentionally not included
- E3/E4/E5 claimed: `false/false/false`

The successor keeps all 28 c0 slices and every c0 causal workload byte. It drops
c1/c2, the 24 tail runs, and all 320 formal-D payloads because they cannot
participate before the observed c0 first divergence. It does not host-precompute,
replay, or replace any internal tensor.

p4-c0 relation:

- source and target c0 files: `89/89`
- byte-identical: `87`
- only identity-normalized files:
  `sca_cfg.json`, `sca_cfg_D.json`
- missing/extra/unexpected changed: `0/0/0`
- input consumers: `86`, all closed
- simulation D endpoints retained: `28`
- formal-D payload count: `0`

The package-local read-only observer records, per MSE/channel and relevant
consumer boundary, qualified request/read/write events, RD metadata/inbuffer/
prepared/buffer handoffs, `Buffer_AG`/ARM pressure, SA input/output/buffer
handoffs, and MSE4 output/finish propagation. It does not drive DUT control,
ready, backpressure, terminal, or timeout.

### 5.1 Final artifacts

- Source ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_e1f_p5_c0diag.zip`
  - bytes: `5811321`
  - SHA-256:
    `393428f1ac860d89daa56543a8e27521c79e0965d5eaa197c074d81219cc6cb8`
- Source sidecar:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_e1f_p5_c0diag.zip.sha256`
  - bytes: `90`
  - SHA-256:
    `7713ccebee5e7949565b7bfec71f201f54226d979a593cc8e92e0c6a8aaa0647`
- Build validation:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_e1f_p5_c0diag.validation.json`
  - SHA-256:
    `4700ae69597bb6874d8470012362a87b667b2170e57ed2d63e3237adf018e17d`
- Independent final-ZIP audit:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_e1f_p5_c0diag.final_zip_audit.json`
  - bytes: `72402`
  - SHA-256:
    `0bc5a3647a9ea5da8f7bac3a733f276267befababc02c4558a9eef3b17ce3ba9`

### 5.2 Final-ZIP gate

- status: `PACKAGE_READY_NOT_RUN`
- `valid=true`
- `errors=[]`
- `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`
- `current_match=true`
- deterministic dual build/replay:
  `393428f1ac860d89daa56543a8e27521c79e0965d5eaa197c074d81219cc6cb8`
- final ZIP contains `98` files including its manifest
- package-local observer bytes/SHA:
  `47647`,
  `06d25e2299125a7d7e2ff7d60c308776976a4ed5955f811b6fddaff2eb203389`

The independent audit passed:

- safe ZIP, manifest/exact-set, source sidecar, deterministic replay
- p4-c0 content-neutral causal-slice relation
- SCA/execplan/input-consumer closure and no preseeded/formal-D payload
- immutable expected e1fb0f7 eight-leaf identity
- package-local HDL focused syntax/scope/name-resolution
- `44` actual canonical consumer expressions, `20` equivalence classes,
  uncovered `0`; direct actual-consumer typo controls fail closed
- observer source/include/macro/runtime-return four-way binding
- feature enable/limit/time-0 marker/return-target end-to-end binding
- canonical decision ambiguity and required-field negatives
- user-root/path-budget/exact-set/runtime-target negatives
- real runner safe-stub natural and TERM shared-finalizer paths
- manifest-driven return allowlist and exact return ZIP/sidecar

The focused local frontend proves only the exact package-local observer
declarations/updates/consumers under the recorded external hierarchy/type/macro
stubs. Production VCS elaboration and the actual eight-leaf identity remain
pending the formal server return.

### 5.3 Server handoff

After extracting the source ZIP and entering its single root:

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy02
```

Expected formal return:

```text
r5_n4_e1f_p5_c0diag_return.zip
```

No upload, lease, or server run was performed by this owner.

## 6. BLOCKER_DELTA and release ceiling

Closed:

- historical v1 package/install/return identity ambiguity
- historical v1 actual compile-identity ambiguity
- historical v1 extraction-contamination hypothesis

Preserved:

- `B_CONV_NATIVE_FOUR_LANE_SERVER_NATURAL_TERMINAL`
- `B_CONV_NATIVE_FOUR_LANE_SERVER_FORMAL_D_320`
- `B_CONV_NATIVE_FOUR_LANE_SERVER_PRODUCTION_RTL_IDENTITY`

New bounded diagnostic boundary:

- `B_CONV_NATIVE_FOUR_LANE_C0_EXEC_TO_SLICE_FINISH_STALL`

`PACKAGE_RELEASE=PACKAGE_READY_NOT_RUN` applies only to the fresh diagnostic p5
source package. It is not a performance release candidate and does not replace
the serialized correctness baseline. The historical v1 result remains a
consumable dynamic failure; p4 replaces its delivery mechanics only.

## 7. Rule receipts and feedback

Post-generation current receipts:

- `.agents/agent.md`:
  `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f`
- `.agents/plan.md` mutable provenance:
  `710ae4ef66665a8dd475eeb07ccf0e3d840b05d184ee0a0ccced19dee9b7c692`
- `.agents/rules/生成前必读索引.md`:
  `93b66e7986beeaddb01f237710af6874bb4bbfcc4c6c6929563c5e98d8397eb2`
- `.agents/rules/服务器测试包生成规则.md`:
  `5f1369c4af431baaf74044a004a3383860a9d279561712616fb19e745465c7f9`
- `.agents/rules/NDP硬件字段语义.md`:
  `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055`
- `.agents/rules/INT8_SA点积专项规则.md`:
  `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`
- `.agents/rules/精确UINT8量化尾专项规则.md`:
  `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e`
- `NDP_copy01/README_HARDWARE_SIM_ENTRY.md`:
  `e82f51c73f658fa567d47c8ab277c1cfb2cdf6d7cd2b4debefb3d0543e2228ba`

`RULE_CONFIRMATION`

The current rules were sufficient and no non-synonymous delta was found:

- `CDA-SERVER-RESULT-GATE-CONJUNCTION-001`: compile success plus zero
  natural terminals and missing 320/320 D correctly fail the joint gate.
- `CDA-SERVER-RETURN-MANIFEST-ALLOWLIST-001` and
  `CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001`: the external
  sidecar waiver remains limited while internal exact-set/source binding passes.
- `CDA-SERVER-SIGNAL-SAFE-PARTIAL-COLLECTION-001` and
  `CDA-SERVER-TIMEOUT-MANUAL-INTERRUPT-HANG-FIRST-001`: exit 124 with signal
  `NONE` is kept as a long-running hang, not misreported as an RTL root cause.
- `CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001` and
  `CDA-SERVER-DIAGNOSTIC-TIME-TO-ROOT-CAUSE-OPTIMIZATION-001`: unresolved
  historical evidence produced a fresh c0-only, multi-boundary diagnostic
  successor instead of a proposal or timeout extension.
- `CDA-SERVER-PACKAGE-INTERNAL-PATH-LENGTH-BUDGET-001`: shortened p5 inner
  namespace and all path negatives pass before server use.
- `CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001` and
  `CDA-SERVER-HDL-SCOPE-NEGATIVE-MUST-TARGET-ACTUAL-CONSUMER-001`: the final
  observer exact bytes pass focused syntax/scope and every actual canonical
  consumer class has a direct fail-closed typo control.
- `CDA-SERVER-OBSERVER-BINDING-FOUR-WAY-001`,
  `CDA-SERVER-DIAGNOSTIC-FEATURE-RUNTIME-ENABLE-END-TO-END-001`, and
  `CDA-SERVER-DIAGNOSTIC-DECISION-CANONICAL-RECORD-001`: source/include/macro/
  runtime/return, feature parameters/marker, and a unique canonical result are
  all machine-closed with required negative controls.
- `CDA-SERVER-RUNNER-PREFLIGHT-TO-COMPILE-POSITIVE-CONTROL-001`,
  `CDA-SERVER-PACKAGE-BOOTSTRAP-IMMUTABILITY-001`, and
  `CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001`: fresh-extract safe-stub natural,
  TERM, bad-identity, immutable-package, deterministic-replay and final-current
  rule controls all pass.

Claim boundary: these confirmations cover historical v1 receipt adjudication and
local p5 delivery readiness only. They do not prove a current production compile,
natural terminal, formal D, E3, E4, E5, or performance success.
