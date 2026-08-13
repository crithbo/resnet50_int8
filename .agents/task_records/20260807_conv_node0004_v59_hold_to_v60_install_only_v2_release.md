# Conv serialized node0004 v59 HOLD → v60 install-only V2

## Disposition

- `PACKAGE_READY_NOT_RUN`
- Fresh identity: `r5_n4_hw_v60_install_only`
- Classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`
- Candidate release: `false`
- Server action: none

The unique pickup ZIP is:

`artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_hw_v60_install_only.zip`

It is 5,154,474 bytes with SHA256
`cb3342e90510e4cd1e66afb9a19977cc5eae725abccf987346757d3d34937ec8`.

The held v59 predecessor remains archived at:

`artifacts/operator_config_validation/r5-server-test-packages/superseded/conv_serialized_node0004/r5_n4_hw_v59_install_subtree/r5_n4_hw_v59_install_subtree.zip`

It is 5,153,755 bytes with SHA256
`e5023a50e827ae3d4b0fc6bb9ac327c9aa38d9e72db068cc4fd567f8e76a216d`.
It was never run and cannot return to pending.

## Runtime-layout correction

Only `$server_root/install` must pre-exist as a real, non-symlink directory.
The exact runner safely and idempotently creates absent
`install/cfg_pkg` and `install/codex_runs`, then creates fresh
cfg/package/attempt leaves below them. No user `mkdir` is required.

The isolated exact-runner harness began all positive scenarios with both
creatable parents absent. After execution they were real directories, while
the NDP-root direct name/type exact-set remained unchanged.

- normal: exit 0; safe compile and simulation stubs reached;
- preflight failure: exit 5; compile not started; partial return published;
- compile failure: exit 42; simulation not started; partial return published;
- HUP/INT/TERM: exits 129/130/143; partial returns published;
- exact SCA/TB-cwd check: 86/86 matrix and bitstream inputs opened;
- missing matrix, missing bitstream, and wrong SCA prefix: fail closed before
  an SCA-open receipt.

The exact embedded shared helper is byte-equal to current
`tools/server_package_runtime_layout.py`, SHA256
`7969ca56e13a7e0a0a83bdfd48d1409d28eef2ae0fd63ad08f0ec5c39e2d848a`.
The shared V2 regression receipt remains 14/14 PASS, profile SHA256
`e698b79c98355cbfd58710bc03c648e27c4feb5d649ad47f6d094843c02052a3`,
covering file/symlink collision, path escape, nonfresh leaf, unknown
overwrite/delete, new root direct entry and the p14 regression.

## Frozen boundary

No numeric/W3/qparam/tail/workload/config/golden/observer/timeout/backpressure,
functional RTL, ISA, hardware or active `ndp-sim` semantics were changed.
Among the 112 common v59/v60 package members, 105 frozen members are
byte-equal. SCA and SCA_D differ only by the mechanical package identity
replacement `r5_n4_hw_v59_install_subtree` →
`r5_n4_hw_v60_install_only`.

## Exact validation receipts

- Family validator:
  `artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/conv_serialized_node0004/r5_n4_hw_v60_install_only/r5_n4_hw_v60_install_only.family_validation.json`,
  SHA256
  `92344d5db463575f3e6fb1b8c53fbdef80d806841dbbce028157d9ed4623d697`,
  `valid=true`, errors=0.
- Shared runtime-layout validator:
  `artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/conv_serialized_node0004/r5_n4_hw_v60_install_only/r5_n4_hw_v60_install_only.shared_validation.json`,
  SHA256
  `7c7acfd60d5e5e476aa73279d5eacb18ef73d6312201082b673290eb2586c68b`,
  `pass=true`, errors=0. The shared exact-final-ZIP gate was invoked once.
- Final ZIP audit:
  `artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/conv_serialized_node0004/r5_n4_hw_v60_install_only/r5_n4_hw_v60_install_only.final_audit.json`,
  SHA256
  `5ff96a98295f32a36fd3957a9fb839936b97c6807bfcf932f803378570e1c188`,
  `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`, errors=0.
- Shadow build profile:
  `artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/conv_serialized_node0004/r5_n4_hw_v60_install_only/r5_n4_hw_v60_install_only.shadow_profile.json`,
  SHA256
  `fc69df5ea318f0d97f4d80a316a061d8fc2638354884da7f92639fd4ef23c2f9`,
  7 blocking, 2 not-applicable and 1 record-only gates.
- Storage index:
  `artifacts/operator_config_validation/r5-server-test-packages/PACKAGE_STORAGE_INDEX.json`,
  132,898 bytes, SHA256
  `e6a553a8e8addbff5378de8e7b9e4ee2e2cc7b5384d45662ba02e67fbff41401`.
  This family has exactly one pending package, v60; flat pending contains ZIPs
  only.
- Machine report:
  `outputs/conv_node0004_v59_install_only_successor/report.json`.

Current post-generation reads:

- agent:
  `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f`;
- plan mutable provenance:
  `43fe7b8c5b7d5d8daf1631f1d01cca1450ef13d7a4891722ebc509061e166e70`;
- generation index:
  `68c13cbd1461ca2a506174678d22cfdbfdc5aced25ad80150d4e4cacece7f2be`;
- server rule:
  `16f7773796dccf4f27a5e412bb200f7b4190ffb87742d3dd2e466866a7f77dde`;
- convergence optimizer:
  `f51525f8db7d8b8e79e57ea194c7d9f6624a320e5754df4dfd164ddc5e50687b`;
- INT8-SA rule:
  `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`.

## Server handoff

After extracting the pickup ZIP, run:

```bash
bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02
```

Expected fixed results:

- `/home/panqs/ndp/simresult/r5_n4_hw_v60_install_only_return.zip`
- `/home/panqs/ndp/simresult/r5_n4_hw_v60_install_only_return.zip.sha256`

## Blocker delta and rule feedback

Closed:
`B_CONV_NODE0004_SHARED_LAYOUT_PARENT_PRECONDITION_TOO_STRICT`.

Still open until a formal server return:
`B_CONV_NODE0004_DYNAMIC_NATURAL_TERMINAL_AND_FORMAL_320D`.

`RULE_CONFIRMATION`: current
`CDA-SERVER-INSTALL-SUBTREE-RUNTIME-LAYOUT-001`,
`CDA-SERVER-NDP-ROOT-TOPLEVEL-NO-NEW-ENTRY-001`,
`CDA-SERVER-RETURN-FIXED-SIMRESULT-ATOMIC-PUBLISH-001`,
`CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001` and
`CDA-SERVER-PACKAGE-STORAGE-ROTATION-001` are sufficient. No non-synonymous
public rule delta is required.

Claim boundary: local package/bootstrap/path/runtime-layout/SCA-open,
finalizer and storage correctness only. No production compile, DUT
simulation, natural terminal, formal 320D, E4 or E5 claim.

Provenance owner=`019fa2c1-17df-7122-bcbd-a727aaf173f5`;
return target=`019fbec2-fe93-7e03-9314-cff6f222f33d`.
