# Conv node0004 v23 return and v24 compile-fix successor

## Scope

- owner: `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- numeric/W3/qparam/tail/workload/config/golden: frozen
- functional RTL, public rules and `.agents/plan.md`: unchanged
- server upload/run/lease: none

## v23 formal return

- return ZIP bytes: `29867`
- return ZIP SHA256:
  `e8efef64b095f5d6cc2b5e4d734b6d1a94a14741d3b608dfc008ef6894905842`
- adjacent sidecar: absent and content-neutral under
  `CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001`
- source v23 ZIP SHA256:
  `9ec61dda9d1d1729b1896b94e86c92747fbec4b2077a7d779a75d186329e2a27`

CRC, root, path safety, duplicate, symlink, return allowlist exact-set and all
ten returned size/SHA receipts passed. Package/install/observer preflight and
runtime-D-absent passed. Actual compile argv carried the package-local
`+incdir` and observer enable macro.

The return lacks both `RETURN_MANIFEST.json` and a returned source package
manifest receipt. The existing allowlist is internally exact but does not
satisfy the current formal return identity contract.

## First divergence

- compile exit: `2`
- run exit: `125`
- simulation started: false
- time-zero markers/progress/formal D: absent
- E3/E4/E5: false/false/false

This is not a runtime hang.

- return LPG:
  `PACKAGE_INSTALL_AND_OBSERVER_STATIC_PREFLIGHT_PASS`
- return FD:
  `VCS_PARSE_PACKAGE_LOCAL_OBSERVER_UNDECLARED_IDENTIFIER`
- file:
  `r5_n4_hw_v23_final_release_diag/tb_probe/native_return_observer.svh`
- VCS line: `3926`
- leaf SHA256:
  `3ecc3f0e0f276a5d4cfa9ca8267cedcad2a0b1198929217f99046595524e8723`
- token: `return_obs_buf45_wr_edge_count`

`FINAL_RELEASE_BOUNDARY_V1` used that identifier once, but it had no
declaration, reset or update. VCS therefore stopped before elaboration and
simulation.

No new Conv dataflow evidence was produced. The frozen semantic boundary
remains:

- `SA_ALU_RESULT_ACCEPT_AND_OUTBUFFER_WRITE`
- `SA_ALU_RESULT_WRITE_TO_FINAL_RESULT_RELEASE_AND_PE_OUTPUT_VALID`

The old occupancy blocker, `WAIT_RTL_FIX` and
`delta=4*initial+1*alu-1*out` remain `INVALIDATED_NOT_RTL_BUG`.

## Package-audit escape root cause

This was not caused by failing to read the rules. The index, server rule,
INT8-SA rule and hardware README were read before generation and completely
reread after v23 generation; their recorded SHA values match current.

The escape was validator noncompliance with the intent of
`CDA-SERVER-STRICT-LOCAL-AUDIT-MINIMAL-RUNTIME-PREFLIGHT-001`, which explicitly
says locally discoverable syntax errors must not reach the server.

The old checks were insufficient:

- the generator emitted a use but no declaration/update and had no
  declaration/use assertion;
- the final validator required the bad token to be present but did not resolve
  its declaration;
- the XMR guard only checked generated-instance index constancy;
- the runner positive control used a safe make/simulator stub, so it proved
  runner reachability and EXIT/TERM collection, not HDL syntax/elaboration;
- unit tests only checked token presence and package freeze.

No HDL parser, compiler or linter was invoked by the old final audit.

The v23 claims are corrected:

- withdrawn: final-audit PASS as sufficient readiness, observer compile
  compatibility and `PACKAGE_READY_NOT_RUN`;
- preserved: ZIP identity, deterministic build, frozen workload/config,
  package/observer SHA, XMR constant-index guard, safe runner reachability,
  feature binding under the stub, and EXIT/TERM collection;
- v23 status:
  `QUARANTINED_PACKAGE_LOCAL_OBSERVER_COMPILE_FAILURE`.

Machine report:

- `outputs/conv_node0004_v23_return_analysis/package_audit_escape_root_cause.json`
- SHA256:
  `9ccd411e32ba74ee086fb327adb6f9b1c4c1a73aa6996673a6e50154381fc636`

## v24 fixes

The fresh package remains `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`.

1. It declares, resets and updates
   `return_obs_fr_buffer5_write_edges` on a qualified Buffer5 write-enable
   rising edge and binds the existing final-release boundary to that counter.
2. It creates and validates `RETURN_MANIFEST.json`, returns the exact source
   package manifest as `evidence/returned_package_manifest.json`, and binds
   both to the allowlist/exact-set.

No numeric, configuration, functional RTL, timeout or backpressure semantics
changed.

## New syntax/scope acceptance gate

`tools/validate_node0004_v24_observer_scope.py` runs:

- exact final observer declaration/use closure;
- Icarus Verilog 12.0 focused SystemVerilog compile for the corrected subset;
- deletion-of-declaration negative: frontend exit `2`;
- misspelled-use negative: frontend exit `1`;
- deletion-of-update negative: validator exit `1`.

The positive focused compile exits `0`. Safe compile stub evidence is explicitly
excluded from this HDL gate.

## v24 validation

- deterministic double build: PASS
- return analyzer: exit `0`
- Python syntax checks: exit `0`
- observer syntax/scope validator: exit `0`
- runner control: exit `0`
- safe compile-stub runner: expected exit `74`
- TERM finalizer runner: expected exit `143`
- final ZIP validator: exit `0`
- unit tests: `4/4 PASS`, exit `0`
- `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`
- errors: `0`
- all final ZIP, observer, return-manifest, feature and canonical negatives:
  fail closed

Post-generation full reread:

- index:
  `f768a870d19699c87b66b735a759d3212db6ad51aace30e3a6305b2521a708c8`
- server rule:
  `7a5383b7881b71043bb99d997c92524cb8c25df304179b53f364219fd7c1b141`
- INT8-SA:
  `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`
- hardware README:
  `4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7`
- mutable plan provenance after generation:
  `1fcefd012f3771003954cd8a64c9856c4fc557a502618d1dac95485bd7a6df7c`

## Package release

- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v24_final_release_diag_compilefix.zip`
- bytes: `5828936`
- SHA256:
  `3701226c52de41a6982dd0ac9a111ade26c26ed088eee53d62fcc038cd5980fc`
- sidecar bytes: `113`
- sidecar SHA256:
  `9c670a475772307d5cd13d595a14dd6d17e7e7e6c33ccaeb3181a8491561207a`
- status: `PACKAGE_READY_NOT_RUN`
- command:
  `bash r5_n4_hw_v24_final_release_diag_compilefix/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy`
- expected return:
  `r5_n4_hw_v24_final_release_diag_compilefix_return.zip`

## Blocker delta

Closed by v24:

- `B_CONV_NODE0004_V23_PACKAGE_OBSERVER_UNDECLARED_IDENTIFIER`
- `B_CONV_NODE0004_RETURN_MANIFEST_IDENTITY_RECEIPT_MISSING`

Still open:

- `B_CONV_NODE0004_SA_FINAL_RESULT_RELEASE_PATH_UNOBSERVED`
- `B_CONV_NODE0004_DYNAMIC_TERMINAL_AND_FORMAL_D`

## Rule delta proposal

Proposed ID:
`CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001`.

The exact final observer bytes must pass syntax and scope/name-resolution in a
compatible frontend. If full production VCS dependencies are unavailable,
require a focused compatible frontend for the changed SV subset plus a machine
declaration/use closure over the exact final observer. Safe compile stubs,
token-presence checks and XMR constant-index scans cannot substitute. Deleting
a declaration, misspelling a use, and deleting required state update must each
fail closed.

## Machine assets

- return report:
  `outputs/conv_node0004_v23_return_analysis/report.json`
  SHA256 `e832e674b07c19abc5a78dfb8ed4eba5349676297690a794cd6c31e7607328b1`
- successor report:
  `outputs/conv_node0004_v23_return_analysis/successor_release.json`
  bytes `6936`, SHA256
  `1f888c9767350286b0e1a934f16f740a12e695d730a090bddcccee4b564a8155`
- contract:
  `contracts/operator_config/node0004_v23_return_v24_compilefix_successor_v1.json`
  bytes `3686`, SHA256
  `c59d4f72ebbb563e20df4a6f641e13a4cbcf0e4aec06efa1b8c9a37ed0b42885`
- final audit SHA256:
  `426387ccc918b64e7ac91f608b41e42b79b9a53aeaaf3fcf0390c6c783107407`
- observer syntax/scope report SHA256:
  `f4e522940d3806441b5c723bbd7f9be09fe4172a88007c0edcb2eeb741cb642c`
- runner controls SHA256:
  `7a24c253b634979122dc23f274953c78fe0e0a836566f6934323e4671059beaf`
