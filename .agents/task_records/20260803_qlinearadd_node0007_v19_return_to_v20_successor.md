# QLinearAdd node0007 v19 return to v20 successor closure

- analysis owner thread: `019fa2c0-b647-7a91-93bf-d21a173487e3`
- return target thread: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- package release: `PACKAGE_READY_NOT_RUN`
- package class: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`
- candidate release: `false`
- evidence: `E2_LOCAL_ONLY`

## RETURN_ANALYSIS

The formal v19 return passed CRC/root/path/duplicate/symlink,
RETURN_MANIFEST exact-set/size/SHA, allowlist, package/install identity and
returned-source-manifest byte binding. The absent adjacent sidecar was accepted
only as user-attested transport; it did not relax any internal gate.

VCS failed before simulation:

- compile/simulation/runner: `2/125/125`
- signal/natural terminal: `NONE/false`
- formal D expected/present/missing: `28/0/28`
- mismatch bytes: `0`, unevaluable
- SERVER_RESULT_GATE/E3/E4/E5: all `false`
- `LAST_PROVEN_GOOD=VCS_PARSED_QADD_FP32_INGRESS_OBSERVER_THROUGH_LINE_239`
- `FIRST_DIVERGENCE=OBSERVER_V19_LINE_240_UNDECLARED_RETURN_OBS_GA_OPERAND_CAPTURE_MON`
- `HANG_ROOT_CAUSE=NOT_APPLICABLE_COMPILE_FAILED_BEFORE_SIMULATION`

The v19 package is quarantined. Its functional diagnostic did not execute, so
`B_QADD_NODE0007_FP32_DUAL_INGRESS_FIRST_ACCEPT_UNRESOLVED` remains open.

Formal analysis report:

- path: `artifacts/operator_config_validation/r5-qlinearadd-node0007-fp32-ingress-v19-return-analysis/report.json`
- bytes/SHA256: `3968` / `f53a0bd48f60a1f2dfc373183f6af594798011c0dde2d79a884d15bdb555e8f2`
- analysis task record SHA256: `d40aa8b1e0922a8b6e5fcc29499df99dae77263b08d5775901cd0bfb8841f910`

## Minimal successor

v20 declares `return_obs_ga_operand_capture_mon` and binds its two operands to
the active qualified RTL leaf
`GA_PE_Inbuffer.ga_pe_inbuffer_enable` at physical GA columns 0 and 2. It then
includes the byte-identical v19 observer tail. No functional RTL, workload,
config, mapping, bitstream, execplan, SCA, qparam, exact tail, golden or timeout
changed.

- install/package identity: `r5_qadd_n7_fp32_ingress_compilefix_v20`
- ZIP: `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_fp32_ingress_compilefix_v20.zip`
- ZIP bytes/SHA256: `38041268` / `13aabd82d62eb1fa25145919c08aa3402de648ac42e401f21e3199f91d53da51`
- sidecar bytes/SHA256: `109` / `f713c5c98a30af1aedef08981cc2db5786ff201ee795a88ff67e0f35aa404e5f`
- command: `bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX`
- expected return: `r5_qadd_n7_fp32_ingress_compilefix_v20_return.zip`

## Final ZIP audit

Post-generation current receipts:

- index: `f768a870d19699c87b66b735a759d3212db6ad51aace30e3a6305b2521a708c8`
- server: `7a5383b7881b71043bb99d997c92524cb8c25df304179b53f364219fd7c1b141`
- QLinearAdd: `aecf9d98136a23a73b3cd5ce8c8ec52f3070a763937373703e6376e3910e730f`
- exact UINT8 tail: `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e`

Two deterministic builds produced the same tree and ZIP SHA. The final ZIP
audit has `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`, `errors=0`. The real runner
reached the safe compile stub (exit 86); EXIT and TERM finalizer controls both
created an allowlisted return (exit 125); wrong identity failed before compile
(exit 5). Deleting source include/incdir/macro/feature/time0/return/stage or the
new declaration/GA0/GA2 binding each failed closed (exit 1).

- build receipt: `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_fp32_ingress_compilefix_v20.validation.json`
- build receipt bytes/SHA256: `1416` / `b92b44a17f9966e0f9b1734dbaac3a2b12e0836c33681088bb535fd25f9bc8e0`
- audit: `artifacts/operator_config_validation/r5-qlinearadd-node0007-fp32-ingress-compilefix-v20/final_zip_self_audit.json`
- audit bytes/SHA256: `8530` / `cf3af55ab29010c0f09070170fc95cdb0a1a96f1239ad2d39d81b898af9bc702`
- release machine report: `artifacts/operator_config_validation/r5-qlinearadd-node0007-fp32-ingress-compilefix-v20/release_report.json`
- release report bytes/SHA256: `5068` / `a2d51437558c2da9d2cccc385b9dd9a93357cd903b042450c632c50370e4f6dd`

The first validator pass exited 1 only because three validator negative
mutations deleted a first duplicate token rather than all bindings. The
validator was corrected and rerun; package ZIP and sidecar bytes never changed.

## BLOCKER_DELTA / RULE_DELTA_PROPOSAL

- closed locally: `B_QADD_V19_OBSERVER_GA_OPERAND_CAPTURE_MON_UNDECLARED`
- remains open pending the v20 dynamic return:
  `B_QADD_NODE0007_FP32_DUAL_INGRESS_FIRST_ACCEPT_UNRESOLVED`
- rule delta proposal: `NONE_CURRENT_RULES_SUFFICIENT`
