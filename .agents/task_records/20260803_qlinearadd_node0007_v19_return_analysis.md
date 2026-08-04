# QLinearAdd node0007 v19 formal return analysis

- analysis owner thread: `019fa2c0-b647-7a91-93bf-d21a173487e3`
- return target thread: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- numeric/W3/qparam/tail/workload/config/golden repeated: `false`
- functional RTL modified: `false`
- server action: `false`

## Bound identities

- return transport: `C:/Users/15383/xwechat_files/wxid_vwpfpfs4fgyk22_29b7/msg/file/2026-08/r5_qadd_n7_fp32_ingress_diag_v19_return.zip`
- return bytes/SHA256: `45494` / `548bb94b570f80878d6b45305b69a4f6a51df7e1ea9157a1788c123b35ca610c`
- adjacent sidecar: absent; accepted only under `CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001`
- frozen source: `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_fp32_ingress_diag_v19.zip`
- source bytes/SHA256: `38038498` / `f32abc4b2b91bf5e854ab113aa98fd1f7925e68a3bd8958f2454762a524709ba`
- machine report: `artifacts/operator_config_validation/r5-qlinearadd-node0007-fp32-ingress-v19-return-analysis/report.json`
- machine report bytes/SHA256: `3968` / `f53a0bd48f60a1f2dfc373183f6af594798011c0dde2d79a884d15bdb555e8f2`

The ZIP CRC, exact root, safe paths, duplicate/symlink absence, RETURN_MANIFEST
per-file size/SHA exact-set, source return allowlist, package/install identity and
returned source-manifest byte binding all pass.

## Formal execution verdict

- compile exit: `2`
- simulation/runner exit: `125`
- simulation started: `false`
- signal: `NONE`
- natural terminal: `false`
- formal D expected/present/missing: `28/0/28`
- mismatch bytes: `0`, explicitly unevaluable because every formal D is absent
- SERVER_RESULT_GATE/E3/E4/E5: `false/false/false/false`

VCS parsed the package-local QAdd observer through line 239 and then rejected
line 240 of `qlinearadd_node0007_fp32_ingress_observer_tail_v19.svh`:
`return_obs_ga_operand_capture_mon` was consumed but never declared. Therefore:

- `LAST_PROVEN_GOOD=VCS_PARSED_QADD_FP32_INGRESS_OBSERVER_THROUGH_LINE_239`
- `FIRST_DIVERGENCE=OBSERVER_V19_LINE_240_UNDECLARED_RETURN_OBS_GA_OPERAND_CAPTURE_MON`
- `HANG_ROOT_CAUSE=NOT_APPLICABLE_COMPILE_FAILED_BEFORE_SIMULATION`
- v19 status: `QUARANTINED_OBSERVER_COMPILE_IDENTIFIER_UNDECLARED`

The returned canonical `PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE` at the missing
feature time-zero marker is a correct fail-closed consequence of compilation
failure, not a functional QAdd diagnosis.

## Root-cause and successor boundary

The active RTL leaf
`NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/GA_PE_Inbuffer.sv`
(SHA256 `25fa4dd2c6fe8301bc3651d660df72059ea2787c0c26a2841a1d4e439586b518`)
defines qualified `ga_pe_inbuffer_enable`. The minimal successor declares the
missing monitor and binds physical GA columns 0 and 2 to this leaf, then includes
the unchanged v19 observer tail. No workload, config, mapping, bitstream,
execplan, SCA, qparam, tail, golden, timeout, or functional RTL may change.

- opened: `B_QADD_V19_OBSERVER_GA_OPERAND_CAPTURE_MON_UNDECLARED`
- remains open: `B_QADD_NODE0007_FP32_DUAL_INGRESS_FIRST_ACCEPT_UNRESOLVED`
- rule delta proposal: `NONE_CURRENT_RULES_SUFFICIENT`
