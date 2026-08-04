# QLinearAdd node0007 v24 mainline release acceptance

## Scope and provenance

- mainline thread: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- owner thread: `019fa2c0-b647-7a91-93bf-d21a173487e3`
- superseded plan SHA256:
  `f403d52bb4cd049c1dec193057007be6108d8764625f42d8eb098378c8f8493d`
- no server upload/run/lease
- no functional RTL or public/specialized rule modification

## Current rule receipts

- `.agents/agent.md`:
  `d9fe95839c2c92a83083d956392a66876c1007fbb7922522c6a8920babab6721`
- `.agents/rules/生成前必读索引.md`:
  `db339fb8f47105b76deef85cdd43cfc85af6358a0c8155571fde54c2006f26c5`
- `.agents/rules/服务器测试包生成规则.md`:
  `5761987d07f425a316bd845e390405c0c64d78c9a371b9cce22cc491c8f25f48`
- `.agents/rules/QLinearAdd算子配置规则.md`:
  `aecf9d98136a23a73b3cd5ce8c8ec52f3070a763937373703e6376e3910e730f`
- `.agents/rules/精确UINT8量化尾专项规则.md`:
  `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e`

## Frozen release identity

- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_bctrl_v24.zip`
- bytes: `38032104`
- SHA256:
  `71e14695c3025340987dba2fc0ffedd23e8e61d9bcb6eaec704de74c8e6928da`
- sidecar:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_bctrl_v24.zip.sha256`
- sidecar bytes: `91`
- sidecar file SHA256:
  `93ad51474ee5e566249ae3b3aab8f4f1baa1f80f5e360a663558f20948936300`
- sidecar content binds the exact ZIP SHA and basename.
- package status:
  `PACKAGE_READY_NOT_RUN / DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX /
  E2_LOCAL_ONLY`
- candidate release: `false`
- command:
  `bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX`
- expected return:
  `r5_qadd_n7_bctrl_v24_return.zip`

## Mainline mechanical audit

- ZIP listing has one root, `135` entries and no duplicate names.
- exact package manifest reports `node-0007`, `hwop-0007-00`,
  `install_name=r5_qadd_n7_bctrl_v24`, `PACKAGE_READY_NOT_RUN`,
  `candidate_release=false`, `functional_rtl_modified=false`,
  `configuration_modified=false`, `host_precomputed_internal_tensor=false`,
  and zero server RTL entries.
- exact package-local HDL members:
  `tb_probe/native_return_observer.svh` and
  `tb_probe/qlinearadd_node0007_first_request_observer_tail_v9.svh`.
- final audit:
  `artifacts/operator_config_validation/r5-qlinearadd-node0007-b-dequant-control-rulefix-v24/final_zip_self_audit.json`
- final audit bytes/SHA256:
  `18388 /
  9d2603782314be5eb1fe8d4be43c45ecb783c3d9b1897abd135bb978be353a96`
- `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`, errors=`0`.
- package-local HDL gate is true; compatible frontend preprocess and focused
  compile exit `0`; both identifier namespaces have unresolved count `0`.
- deletion of a declaration, misspelling of a consumer use, and deletion of
  a qualified update all fail closed.
- safe compile-stub reaches compile and exits `86`; stderr is exactly empty;
  required finalizer artifacts are complete.
- safe compile-failure `RETURN_MANIFEST.required_missing` has exactly `28`
  entries and every entry is a formal-D target; no simulator log, actual argv
  or observer receipt is missing.
- safe EXIT and TERM controls exit `125`, have empty stderr, and collect the
  expected return/canonical/feature receipts.

## Adjudication

- v22 remains quarantined for the missing package-local HDL gate and
  compile-stub finalizer diagnostics.
- v23 remains quarantined because compile-failure return placeholders were
  incomplete.
- v24 is the only runnable QLinearAdd identity and is admitted to the current
  server queue.
- `B_QADD_V22_FINAL_ZIP_HDL_GATE_MISSING`,
  `B_QADD_V22_COMPILE_STUB_FINALIZER_STDERR_DIAGNOSTICS`, and
  `B_QADD_V23_COMPILE_STUB_RETURN_REQUIRED_PLACEHOLDERS_ABSENT` are closed.
- `B_QADD_V20_PACKAGE_LOCAL_FP32_OBSERVER_EVENT_STORM_SUSPECT` and
  `B_QADD_NODE0007_FP32_DUAL_INGRESS_FIRST_ACCEPT_UNRESOLVED` remain open.
- a successful B-only control is local diagnostic evidence only; the final
  six-stage plus 28-D end-to-end E4/E5 gate remains mandatory.

## Rule feedback

The mainline accepts the owner's evidence-backed `RULE_CONFIRMATION`.
`CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001` and
`CDA-SERVER-RUNNER-PREFLIGHT-TO-COMPILE-POSITIVE-CONTROL-001` detected the
two escape classes and are sufficient for this closure. No synonymous public
rule is added.
