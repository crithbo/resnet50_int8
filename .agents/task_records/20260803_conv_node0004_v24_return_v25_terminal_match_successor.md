# Conv node0004 v24 return → v25 terminal-match successor

- owner: `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- mainline target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`
- package status: `PACKAGE_READY_NOT_RUN`
- numeric analysis repeated: `false`
- workload rebuilt: `false`
- configuration rebuilt: `false`
- functional RTL modified: `false`
- server action: `false`

## Current receipts

- `.agents/agent.md`: `aae402d48b82d026c5512c8a6a5d4c9ff9db4bcc6a94576cd618c168f3fd188e`
- `.agents/plan.md`: `24ca593e1be4ae1c16b70ba60762f3c096559ac0904932010a9e75b9a5088dbe` (mutable provenance)
- `.agents/rules/生成前必读索引.md`: `d9e66e5a1dc4ba1658aac7f851227bb162b76601cd497eeea558a88a2e900422`
- `.agents/rules/服务器测试包生成规则.md`: `559ce2660cfe34d567ab45f6c2573f7d0ad2ad3f3d751337432616ce9a9690b2`
- `.agents/rules/INT8_SA点积专项规则.md`: `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`
- `NDP_copy01/README_HARDWARE_SIM_ENTRY.md`: `4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7`

The post-generation server-rule drift is content-neutral for the exact v25
bytes. The current rule narrows the package-local HDL closure to states that
were added/modified or are necessary to the current decision. The v25 focused
frontend and semantic closure cover exactly that scope; no full observer state
inventory or local full-design elaboration is claimed.

## v24 return adjudication

The formal return ZIP is
`r5_n4_hw_v24_final_release_diag_compilefix_return.zip`, bytes `93748`, SHA-256
`e403d08c5ea0b6dd252f72d4378e78b8f15c68165153d304dde7c1834fde0999`.
The absent adjacent sidecar is content-neutral under the user-attested
transport rule. CRC, root/path safety, exact allowlist, per-file receipts,
source/package/install/observer identity and actual compile/runtime binding all
pass.

VCS compile/elaboration and run returned zero, and simulation started. The
observer diagnostic `$finish` is not a natural DUT terminal. Formal D is
`present=0`, `missing=320`, `mismatch=0`; therefore the conjunction gate fails
and E3/E4/E5 remain false.

Qualified evidence establishes:

- A/B/C accepts `16/16/8`;
- `2048` ALU accepts with outbuffer updates;
- `256` raw input-terminal rising edges;
- zero qualified terminal match/out, terminal ALU write, PE output,
  SA group output and Buffer5 write;
- the first progress window recorded `182` qualified events, followed by four
  full `262144`-cycle zero-delta windows.

`LAST_PROVEN_GOOD` remains the accepted mainline boundary
`SA_ALU_RESULT_ACCEPT_AND_OUTBUFFER_WRITE`; v24 refines it to
`SA_NONTERMINAL_OPERAND_ACCEPT_AND_ALU_OUTBUFFER_UPDATE`.
`FIRST_DIVERGENCE` is now
`RAW_INPUT_TERMINAL_TO_QUALIFIED_TRANSOUT_MATCH_OR_OUT`.

The old outbuffer occupancy blocker and its `+1` per ALU write equation remain
`INVALIDATED_NOT_RTL_BUG`. v24 cannot uniquely distinguish terminal
valid/same/gotten/mask misalignment, accepted last-index mismatch, or later tag
loss because it did not observe the necessary per-port qualified boundary.

## Package audit escape correction

The v23 compile escape was an undeclared
`return_obs_buf45_wr_edge_count` use at
`r5_n4_hw_v23_final_release_diag/tb_probe/native_return_observer.svh:3926`.
Rules were read before and after generation; this was not a rule-read omission.
The generator emitted a consumer without declaration/reset/update, while the
old validator checked token presence and XMR constant indices but invoked no
HDL frontend. The safe compile stub only proved runner reachability and
EXIT/TERM finalization.

The v23 compile-ready claim is withdrawn; its ZIP identity, frozen semantics,
runner reachability and finalizer results remain valid. The missing executable
gate is now published as
`CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001`, so no
synonymous rule delta is proposed.

Machine report:
`outputs/conv_node0004_v24_return_analysis/package_audit_escape_root_cause_current.json`,
bytes `4219`, SHA-256
`4c1ed6ffb60181758e38d58477722dd44820571fc8a2accab67032fd399e1703`.

## v25 successor

The successor preserves the frozen numeric inputs, W3, qparams, tail, workload,
configuration, bitstream, execplan, SCA, golden and functional RTL. It extends
the already-enabled final-release feature only with low-cost, bounded,
qualified observations of:

- per-port raw and masked valid/last/index, same and gotten;
- simultaneous A/B terminal accept;
- `transout_last_index`, diff, ignore, matched and out;
- the previously established downstream release witnesses.

The exact package is:

- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v25_terminal_match_diag.zip`
- bytes: `5829810`
- SHA-256:
  `e4aaf762a3b434a78dfc4af276b48405f84b6dbaee1dad224282ac7b14fb1eab`
- sidecar SHA-256:
  `0f6167ef48ff6006f8aac4e416a8e492409a6d3730b076762d4253c9883cad7d`
- command:
  `bash r5_n4_hw_v25_terminal_match_diag/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy`
- expected return:
  `r5_n4_hw_v25_terminal_match_diag_return.zip`

Deterministic double build is equal. Final ZIP current-rule self-audit passes
with `errors=0`. Focused Icarus syntax/scope positive exits `0`; deletion of a
required declaration exits `4`, misspelled consumer exits `1`, and deletion of
the qualified update is rejected by semantic closure with validator exit `1`.
Runner safe compile and TERM finalizer controls return `74` and `143`; all
package identity/include/macro/runtime/return-contract negatives fail closed.

## Artifacts

- v24 analysis:
  `outputs/conv_node0004_v24_return_analysis/report.json`, bytes `16521`,
  SHA-256 `1953686423c807e3211bf878b07dfd6549254b4c62f4ea9827b3796f9d9cd2d8`
- focused HDL scope:
  `outputs/conv_node0004_v24_return_analysis/v25_observer_scope.json`, bytes
  `7773`, SHA-256
  `f854df72cff2ba714d66c93a439da7df8b01c62e80e089fb61a14f4fcfecd5d8`
- runner controls:
  `outputs/conv_node0004_v24_return_analysis/v25_runner_controls.json`, bytes
  `7753`, SHA-256
  `c62c3b4545d34518369c6d4bcbe2c49151c5fca6944c7c67bd7e34782a036bdd`
- final ZIP audit:
  `outputs/conv_node0004_v24_return_analysis/v25_final_zip_self_audit.json`,
  bytes `6210`, SHA-256
  `0def133614d48293264ea43101a94e100392a64297f3f67863c4de90a7256bfe`
- structured release:
  `outputs/conv_node0004_v24_return_analysis/successor_release.json`, bytes
  `7875`, SHA-256
  `17bffbf7254175a6843181081af9a675475335481a38f677db4a195f10454c06`
- targeted unit test:
  `tests/test_node0004_v25_terminal_match_diag.py`, bytes `2195`, SHA-256
  `09f1414c4ea3db2efa38b9cb70ff7d34d0c89109728dded42a388ad3ae6aa3f7`;
  `python -B -m unittest tests.test_node0004_v25_terminal_match_diag` exits
  `0` (`3/3 PASS`).

