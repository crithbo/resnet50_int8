# Conv native-four-lane p14 → p15 install-only V2 release

## Disposition

- `PACKAGE_READY_NOT_RUN`
- Fresh identity: `r5_n4_0cc_p15_installonly`
- Candidate release: `false`
- Server action: none
- The tested p14 package was not rerun, overwritten, or rebuilt in place.

The exact pending pickup ZIP is
`artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p15_installonly.zip`,
45,918,261 bytes, SHA256
`e323e3394124c9b8b655037ac916cc3e3510360cb0097f1f91f60bfb9508c9b8`.

## Source and frozen boundary

The only source package was the formally consumed tested p14 ZIP:

- identity: `r5_n4_0cc_p14_install`
- bytes: 45,911,951
- SHA256: `e920803ffddbb90dc93470c0b711bfc8bf046ae819012ad89461f36ab9be5427`
- formal classification:
  `PACKAGE_LOCAL_PREFLIGHT_CONTRACT_TOO_STRICT`
- compile/simulation at the p14 failure: not started

Exactly nine package members changed: runner/README/layout contract/pointer/
manifest/publisher/runtime/shared-helper plus the mechanical SCA_D output
prefix. All other package members are byte-equal. The family audit reports
zero frozen mismatches. Workload/config/mapping/bitstream/execplan/SCA input,
numeric/W3/golden, observer/timeout, functional RTL/ISA/hardware and active
`ndp-sim` semantics remain frozen.

## Install-only V2 closure

The exact runner now requires only `$server_root/install` to pre-exist as a
real, non-symlink directory. It safely and idempotently creates absent
`install/cfg_pkg` and `install/codex_runs`, then creates fresh cfg/package/
attempt leaves. No user `mkdir` is required.

The isolated exact-runner harness began each positive scenario with both
creatable parents absent. The parents were real directories afterward and the
NDP root direct name/type exact-set was unchanged. Results:

- normal: exit 0, compile stub and simulator stub reached;
- preflight fail: exit 5, compile/simulation not started, partial return
  published;
- compile fail: exit 42, simulation not started, partial return published;
- HUP/INT/TERM: exits 129/130/143, partial returns published;
- missing `install`: exit 12, compile/simulation not started, partial return
  published.

The current public helper regression passed locally (7/7); the merged shared
contract receipt remains 14/14 PASS with compiled profile SHA256
`e698b79c98355cbfd58710bc03c648e27c4feb5d649ad47f6d094843c02052a3`.
This covers file/symlink collisions, path escape, nonfresh leaves, unknown
overwrite/delete, new root direct entries and the p14 regression.

## Exact receipts

- Family final audit:
  `outputs/conv_native_four_lane_0ccae916_p15_install_only/r5_n4_0cc_p15_installonly.final_zip_audit.json`,
  156,372 bytes, SHA256
  `3801c02f1b2aec2c657f85a7e3c8f7a68d95008d348bc33bceafa9b9eabd049f`,
  `valid=true`.
- Shared runtime-layout report:
  `outputs/conv_native_four_lane_0ccae916_p15_install_only/r5_n4_0cc_p15_installonly.shared_runtime_layout.json`,
  17,490 bytes, SHA256
  `7034ae2023ee813cddcf648115be92d5fbdf4941cac4ad48092e6beeabc4dfbc`,
  `pass=true`, `errors=0`.
- The exact final ZIP invoked the shared validator once.
- Runtime-layout harness:
  `outputs/conv_native_four_lane_0ccae916_p15_install_only/r5_n4_0cc_p15_installonly.runtime_layout_harness.json`,
  9,344 bytes, SHA256
  `5c3d6eec979126a0d86cc69ebda5b29931d440a87bd4e3529de133c27827c2fa`.
- Shadow build profile:
  `outputs/conv_native_four_lane_0ccae916_p15_install_only/r5_n4_0cc_p15_installonly.build_profile.json`,
  8,111 bytes, SHA256
  `6557345b16862a523af8d318ec47834b7e51a1c5761865ae526d69d3cc68aa0c`.
  It matches 7 blocking, 2 not-applicable and 1 record-only dispositions.
- Storage index after atomic rotation:
  `artifacts/operator_config_validation/r5-server-test-packages/PACKAGE_STORAGE_INDEX.json`,
  128,833 bytes, SHA256
  `8ccc7cb8dc0dcfab69e7c7eba6fcb24dfe229e31cea45515afc49bdccaa17cb5`,
  `pass=true`. This family has exactly one pending identity, p15; p14 remains
  tested.

Current generation receipts remained exact at final read:

- server package rule:
  `16f7773796dccf4f27a5e412bb200f7b4190ffb87742d3dd2e466866a7f77dde`;
- generation index:
  `68c13cbd1461ca2a506174678d22cfdbfdc5aced25ad80150d4e4cacece7f2be`;
- convergence optimizer rule:
  `f51525f8db7d8b8e79e57ea194c7d9f6624a320e5754df4dfd164ddc5e50687b`;
- shared helper:
  `7969ca56e13a7e0a0a83bdfd48d1409d28eef2ae0fd63ad08f0ec5c39e2d848a`;
- shared validator:
  `66f779d9d472dabaf9a3d2f2b09b472d6bb6ea575865e223a8e80c11818813a5`;
- layout schema:
  `529864182fc57bd3af47fc31dcb5697420b8f656303270e0b0ee862379faf79d`;
- harness schema:
  `9f77cd5921ff3b4e0f692425aaa27c6f6f7a18466c414e7bcc89a00b56ec67c3`;
- build registry:
  `7af29e7d01684db24334365e9e92f0dd0370331c253b2bfb8e58ccf265f93274`;
- two-Conv dispatch contract:
  `896c2b5a97409c14bf6596c51823cf9ba4ddfa6fc2e8614d7f48e899b298168b`.

## Server handoff

After extracting the single pickup ZIP, run:

```bash
bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02
```

Expected fixed results:

- `/home/panqs/ndp/simresult/r5_n4_0cc_p15_installonly_return.zip`
- `/home/panqs/ndp/simresult/r5_n4_0cc_p15_installonly_return.zip.sha256`

## Claim boundary and rule feedback

This release proves local package/bootstrap/path/runtime-layout/SCA-path,
early/shared-finalizer and storage behavior only. It does not claim production
compile, DUT simulation, natural terminal, formal 320D, numeric correctness,
performance, E3, E4 or E5.

`RULE_CONFIRMATION`: the current
`CDA-SERVER-INSTALL-SUBTREE-RUNTIME-LAYOUT-001` V2 semantics are sufficient.
The p14 over-strict-parent counterexample is closed without a public-rule
delta.
