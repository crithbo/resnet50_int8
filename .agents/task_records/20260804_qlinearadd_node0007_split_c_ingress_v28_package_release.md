# QLinearAdd node0007 split-C ingress v28 package release

- owner: `019fa2c0-b647-7a91-93bf-d21a173487e3`
- return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- status: `PACKAGE_READY_NOT_RUN`
- claim: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`
- ZIP: `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_split_c_ingress_v28.zip`
- ZIP bytes/SHA: `26163932 / f552f2a24ae62b1e4e11c1a69ddff6663ffa2ea4fa177b923d0298c15a739f50`
- sidecar SHA: `b1cb6e2377df01cb4f966e8bddf7533ea20f669ff21c0396a427bdbcbb43bfb2`
- command: `bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy02`
- expected return: `r5_qadd_n7_split_c_ingress_v28_return.zip`
- final audit: `artifacts/operator_config_validation/r5-qlinearadd-node0007-split-c-ingress-v28-server-package/final_zip_self_audit.json`
- final audit SHA: `6cdc70fecb3473c8fbfb35dfcc6ba802a695ac50a010a15a2dcf3a8fa4b8bca2`
- HDL scope report SHA: `c1004b9913322c289a980a4f7e465283f44dc6e21515f859848e57a7c11aba98`
- FINAL_ZIP_RULE_SELF_AUDIT_PASS: true; errors: 0
- safe compile stub / EXIT / TERM / wrong identity exits: `86 / 125 / 125 / 5`
- all observer, feature, stage, parser and HDL negatives fail closed.

The package preserves the exact split-C workload and configuration semantics
(only install-namespace rebinding is performed), keeps the 8h timeout, and adds
low-rate source-clock-qualified MSE0+MSE1, Buffer0+2 and dual-GA-ingress
observation. It does not claim stage completion or numeric correctness.

The first generated v27 identity is quarantined because its SCA namespace
retained the v26 install identity and the true runner failed before compile.
v28 is the sole runnable successor.
