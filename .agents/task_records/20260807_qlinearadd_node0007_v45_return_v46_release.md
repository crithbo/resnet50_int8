# QLinearAdd node0007 v45 RETURN → v46 release

Date: 2026-08-07

## Provenance

- analysis_owner_thread: `019fa2c0-b647-7a91-93bf-d21a173487e3`
- return_target_thread: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- numeric/workload/config/golden repeated: `false`
- server action: `false`

## RETURN_ANALYSIS

- v45 return SHA256: `3e0404ee7a88429859fc19bc275866d070a1a11c16faf9a21162be08a3f322f3`
- CRC/root/exact-set/per-file receipts: PASS
- package/install preflight: PASS
- compile exit: `0`
- simulation exit: `125`
- signal: `HUP`
- natural terminal: `false`
- ordered stages: start `1`, finish `0`
- formal D: expected `28`, present `0`, missing `28`,
  mismatch_evaluable=`false`
- E3/E4/E5: `false/false/false`

The host sampler covered about 80.48 minutes. Its last about 43.48 minutes
repeated one unchanged `DEEP_MSE4_INDEX` level at sim time 16129418000.
That level is not qualified progress. Because raw sim/observer logs were not
returned, the functional root cause remains bounded but not unique.

Machine report:
`artifacts/operator_config_validation/r5-qlinearadd-node0007-v45-return-analysis/report.json`  
SHA256: `5c328798685eee873eada6074cc4f2ee96679d90413e9670bd8819f80f4879c2`

## FIRST_DIVERGENCE

`op_a_dequant EXEC_START → first proven qualified progress/COMP_FINISH`,
terminated by external HUP.

The deterministic package-side defect is separate: v45 retained stale split-C
return source paths for compile/sim/observer and 28 final D files. It also
required receipts it never generated. Therefore v45 could not prove a full
result even if the DUT later completed.

## PACKAGE_RELEASE

- state: `PACKAGE_READY_NOT_RUN`
- identity: `r5_qadd_n7_fullchain_returnfix_v46`
- pickup:
  `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_qadd_n7_fullchain_returnfix_v46.zip`
- bytes: `38060000`
- SHA256: `58f5204886fef6015501dedc7e4443936c8ba118be248d12c102b46bf5afa3c5`
- command:
  `bash r5_qadd_n7_fullchain_returnfix_v46/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x`
- fixed return:
  `/home/panqs/ndp/simresult/r5_qadd_n7_fullchain_returnfix_v46_return.zip`

The six-stage config/workload/numeric/W3/qparams/tail/golden/observer, 8-hour
timeout and functional RTL are frozen. Only identity, return source paths,
source/package receipt and low-rate process/log liveness changed.

## Validation

- deterministic double build: PASS
- family validator: PASS
- shared exact-ZIP runtime validator: PASS
- generated heredoc syntax: PASS
- same-shell HUP/INT/TERM unit: PASS
- return-path and missing-receipt negatives: all fail closed
- package-local HDL: byte-equal receipt reuse
- FINAL_ZIP_RULE_SELF_AUDIT_PASS: `true`
- errors: `0`

Release report:
`artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/qlinearadd_node0007/r5_qadd_n7_fullchain_returnfix_v46/r5_qadd_n7_fullchain_returnfix_v46.release_report.json`  
SHA256: `3ea625b27aa733d462f1544ed0baa50048001a3bccc2a108a4760a853d8ddca3`

## BLOCKER_DELTA

- CLOSED: `B_QADD_V45_RETURN_ALLOWLIST_SOURCE_PATH_DRIFT`
- OPEN: full-chain natural terminal, exact UINT8 28D, and the bounded first
  stage qualified-progress interval.

## RULE_CONFIRMATION

Current partial-return, continuous-closure, install-only, fixed-simresult,
NDP-root direct-set, generated-heredoc and storage rules are confirmed. No
new synonymous rule is proposed.
