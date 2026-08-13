# Conv native-four-lane p5 formal RETURN analysis and p6 ARM-interface successor

Date: 2026-08-05  
Owner: `019fc783-1146-7901-9e40-64d0ed8e052d`  
Unique mainline / return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`

## Scope and frozen boundaries

- Consumed only the exact p5 diagnostic package/return and current disk RTL/rules.
- Did not rerun all-53 Conv/W3, local E2, or performance inversion.
- Did not modify `.agents/plan.md`, public/special rules, functional RTL, the
  serialized Conv baseline, or another operator family.
- Did not upload, run a production server simulation, or acquire a lease.
- p5 and p6 are diagnostic-only and contain no formal 320D payload. Absence of
  320D records is therefore neither a formal-D pass nor a formal-D failure.

## Exact input identities

- Formal p5 return:
  `C:/Users/15383/xwechat_files/wxid_vwpfpfs4fgyk22_29b7/msg/file/2026-08/r5_n4_e1f_p5_c0diag_return.zip`
  - bytes: `41417`
  - SHA256:
    `bcebec2837fdf3398d2786bf7c75dc6bf5b4c6012d136911e9d998844232aeb0`
  - adjacent sidecar absent; only the external transport receipt is waived.
- Exact p5 source:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_e1f_p5_c0diag.zip`
  - bytes: `5811321`
  - SHA256:
    `393428f1ac860d89daa56543a8e27521c79e0965d5eaa197c074d81219cc6cb8`
- p5 return analyzer:
  `tools/analyze_conv_native_four_lane_e1fb0f7_p5_return.py`
  - SHA256:
    `1f99bd49067aedaed3dbe45099c1b76fe95833e2615e70603d8a7c58deadc9eb`
- Machine analysis:
  `outputs/conv_native_four_lane_e1fb0f7_p5_return_analysis/report.json`
  - bytes: `9871`
  - SHA256:
    `56cff23a6d5f5f78cacb8e09b1f452a0dab8f52f9d49183be91479657f32aabf`
  - status: `RETURN_ANALYSIS_COMPLETE`
  - classification: `P5_PRODUCTION_COMPILE_FAILURE_CONSUMABLE`

## p5 internal receipt

The outer ZIP is safe, has one declared root and 13 files, and its exact set
equals the return-manifest records plus the return manifest and allowlist.
Every declared byte count/SHA matches.

- `RETURN_MANIFEST.json` SHA256:
  `54f50fe1c57d44b828e1c89d9ada06055ab6eaf4c0909613e9fc93aa1e8b2e9e`
- `RETURN_ALLOWLIST.json` SHA256:
  `3aaa06d459540a40996e20fce9b1c61ee874b78b232ea63c6cab6525f8a8b831`
- returned canonical source `package_manifest.json` SHA256:
  `d7d24452e561abd4b097dd348c790e0e5df687f82f2d9e28ac0dbb25641f67a2`
- The returned canonical source manifest is byte-equal to the manifest inside
  the exact p5 source ZIP.
- Package preflight, install preflight and observer precompile guard all report
  `valid=true`.
- Actual compile invocation includes both
  `+define+NATIVE_RETURN_OBSERVER_ENABLE` and the p5 `tb_probe` include path.

## LPG / FD / HANG_ROOT_CAUSE

LPG:

1. exact outer return and exact source package;
2. exact internal set/hashes and source-manifest binding;
3. valid package/install/observer guards;
4. production VCS invoked with the package observer enabled;
5. VCS parsed the observer and entered elaboration.

FD:

`tb_probe/native_return_observer.svh:350`, production VCS cross-module
reference resolution of private token `buf2arm_valid_hold`.

Observed execution:

- compile exit: `2`
- run exit: `125`
- signal: `NONE`
- VCS XMRE count: `10`; all ten name the same line/token, then the default
  maximum error count is reached.
- no c0 simulation/feature-binding/natural-terminal records exist;
  `canonical_record_count=0`.

`HANG_ROOT_CAUSE =
NOT_REACHED_SIMULATION_PACKAGE_OBSERVER_PRIVATE_XMR_FAILURE`

This is the root cause of the p5 attempt terminating before simulation, not a
root-cause adjudication of the older c0 `exec_start -> slice_finish` stall.

## Actual compile identity and claim ceiling

No `evidence/production_rtl_identity.json` exists because compilation did not
complete. The `/home/panqs/ndp/NDP_copy02` path in the compile argv is only
path provenance and is not an RTL byte-identity receipt.

The expected/current local identity remains e1fb0f7:

- commit: `e1fb0f7bb2761d6c804867de0c5d2cb77554c48d`
- current `Array_Request_Manager.sv` immutable Git blob SHA256:
  `d3f100b2a1415ff561791ccafd157b038c4d8e80a80bf18dcedb89c1fec7c4eb`

It must not be promoted to the actual production compile identity.

Preserved blockers:

- `B_CONV_NATIVE4_C0_EXEC_TO_SLICE_FINISH_UNDIAGNOSED`
- `B_CONV_NATIVE4_NATURAL_TERMINAL_UNPROVEN`
- `B_CONV_NATIVE4_FORMAL_320D_NOT_IN_P5_OR_P6_SCOPE`
- `B_CONV_NATIVE4_ACTUAL_PRODUCTION_RTL_IDENTITY_UNAVAILABLE`

Closed/delta:

- p5 extraction, exact-set, preflight and actual compiler-invocation delivery
  gates are closed.
- p5 exposed
  `B_P5_OBSERVER_PRIVATE_XMR_PRODUCTION_RESOLUTION`, which p6 removes from the
  package observer without changing functional RTL.

No E3/E4/E5, performance-server pass, c0 natural terminal, or formal-D claim is
made.

## Fresh p6 successor

Identity: `r5_n4_e1f_p6_armif`  
Class: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`  
`candidate_release=false`, `PACKAGE_READY_NOT_RUN`

Single diagnostic change:

- `n4d_arm_hold_mon` no longer reads the private
  `buf2arm_valid_hold` register.
- It is the raw interface-derived hold-set pressure witness
  `buf2arm_rvalid & !array2arm_bp_post`.
- This raw level remains excluded from monotonic qualified progress totals.

All p5 non-manifest members are exact except:

- five fresh-identity normalizations:
  `PREPARE_AND_RUN.sh`,
  `TEST_PACKAGE_MANIFEST.json`,
  package runtime,
  `sca_cfg.json`, and `sca_cfg_D.json`;
- the diagnostic README;
- the one package observer replacement above.

There are no missing or extra p5 workload members. The retained c0
config/bitstream/execplan/payload semantics are unchanged; no functional or
numeric change exists.

Package:

- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_e1f_p6_armif.zip`
  - bytes: `5811422`
  - SHA256:
    `05fc4f385d544195ad3cbc68256525d70775cc490d4a42ff784e9b9f7c5d34c1`
- sidecar:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_e1f_p6_armif.zip.sha256`
  - SHA256:
    `73647f626160cdf1c418a8f579680bbf883dcbfe16de6faa11bc2bcd0d8e183c`
- package observer:
  - bytes: `48247`
  - SHA256:
    `a00c76b17aec6b9b257356cc8b254a571e2958c708630e93a9827691de24e3b3`
- build receipt:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_e1f_p6_armif.validation.json`
  - SHA256:
    `e858db298c1e896d637ec2a6c5f08ff114d38a1769f0e3e0b74ce1a42bca6584`
- final audit:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_e1f_p6_armif.final_zip_audit.json`
  - bytes: `72635`
  - SHA256:
    `d961e4196abbe217c60ecc27f00af1e89be35156c3203318e7ebc0b13e581670`

Tools:

- builder:
  `tools/build_conv_native_four_lane_e1fb0f7_p6_armif_package.py`
  - SHA256:
    `f76e1a97e60dc4be0f7ea70676046b40f80aebcc6a3f0b225709d4e162db24be`
- independent validator:
  `tools/validate_conv_native_four_lane_e1fb0f7_p6_armif_package.py`
  - SHA256:
    `ef31fad1e56aa21721927dc9d8be0ea02647d859d360920e6de6e88066ea6041`

## p6 local/final gates

All final audit gates pass:

- deterministic dual build and deterministic ZIP replay;
- safe ZIP, exact package-directory match and exact sidecar;
- exact p5 content relation;
- package-manifest exact set;
- config/SCA actual-consumer closure: 86 input consumers, none missing;
- no preloaded formal D; 28 simulation D endpoints retained;
- immutable eight-leaf e1fb0f7 expected identity;
- focused exact-observer Icarus syntax/scope and actual-consumer closure;
- per-equivalence-class HDL negative controls fail closed;
- runtime positive/negative controls;
- runner/observer/feature/canonical/return-allowlist controls;
- safe local runner/finalizer natural, signal-143, and wrong-observer-SHA
  controls;
- package tree remains immutable and no Python bootstrap artifacts appear;
- path budget: `209/240` projected absolute characters;
- ZIP: 98 files, 45,739,194 uncompressed bytes;
- `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`.

The safe local runner controls do not invoke production VCS or DUT simulation.

## Server handoff

Upload only the p6 ZIP and verify its adjacent sidecar. Extract into a fresh
directory, enter the extracted package root, then run exactly once:

```bash
bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02
```

Expected formal return:

- `/home/panqs/ndp/NDP_copy02/r5_n4_e1f_p6_armif_return.zip`
- `/home/panqs/ndp/NDP_copy02/r5_n4_e1f_p6_armif_return.zip.sha256`

p6 is c0 diagnostic-only. Its formal return must be used to adjudicate actual
production compile identity and the retained per-MSE/RD/Buffer_AG/ARM/SA/MSE4
`exec_start -> slice_finish` boundary. It cannot itself establish 320/320 D.

## Current-rule receipt and feedback

Post-generation current disk receipts:

- `.agents/agent.md`:
  `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f`
- `.agents/plan.md` mutable provenance:
  `85764e5f232499ab8d67268c4a29cecb396e0bbb058358ea519ea88b1f518817`
- generation index:
  `93b66e7986beeaddb01f237710af6874bb4bbfcc4c6c6929563c5e98d8397eb2`
- server-package rule:
  `5f1369c4af431baaf74044a004a3383860a9d279561712616fb19e745465c7f9`

`RULE_CONFIRMATION`:

The current server-package rule correctly keeps production-only
compile/elaboration evidence below simulation/320D claims, permits a fresh
package-local observer successor without functional RTL changes, and requires
the returned actual compile identity plus natural-terminal/formal-D evidence
before E3/E4/E5. No evidence-backed non-synonymous public rule delta is proven.

