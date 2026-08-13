# Conv native-four-lane p11f HOLD → p12 root-top-level gate replacement

Date: 2026-08-06  
Owner: `019fc783-1146-7901-9e40-64d0ed8e052d`  
Mainline return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`

## Adjudication

`r5_n4_0cc_p11f_pubord` is not releasable under current
`CDA-SERVER-NDP-ROOT-TOPLEVEL-NO-NEW-ENTRY-001`.

Read-only inspection of the exact p11f ZIP
`3198b62bf609f213f9355f8ddaa45df90dd05ea61443fe859247d0b9f3cd0acf`
proved that its exact final runner:

- creates `/home/panqs/ndp/simresult` before any NDP-root direct-child
  snapshot;
- has no pre/post direct-child name-and-type exact-set receipt;
- has no pre/post exact-set hashes;
- has no root-drift exit conjunction.

Therefore byte-neutral receipt supplementation was impossible. The p11f
status is:

`PACKAGE_HELD_NDP_ROOT_TOPLEVEL_GATE_REQUIRED`

It was never run and was rotated to `superseded`, preserving its exact
ZIP bytes.

## Fresh runner-only replacement

Package identity: `r5_n4_0cc_p12_rootgate`  
Workload install namespace: `r5_n4_0cc_p11f_pubord`

The separate workload namespace deliberately preserves every SCA path and
all frozen materialized workload bytes. The only changed package surfaces
are the outer identity/metadata, exact runner, fixed-return publisher, and
new root exact-set helper.

Frozen and byte-equal to p11f:

- `workload/runtime/**`
- `diagnostics/**`
- `tb_probe/**`
- numeric/golden/config/address data
- observer and diagnostic predicates
- compile/simulation timeout and progress tokens
- functional RTL

Frozen comparison: 92/92 selected files equal; no frozen mismatch, no
removal, and the only new nonmetadata member is
`package_tools/ndp_root_toplevel_exact_set_gate.py`.

## Root top-level contract

The p12 exact production runner now:

1. resolves the supplied server root read-only;
2. captures sorted direct-child names and `lstat` types before its first
   write;
3. declares no runtime write target or required pre-existing parent inside
   the NDP root;
4. keeps work and fixed return publication under the nonconfigurable server
   path `/home/panqs/ndp/simresult`;
5. captures the same direct-child set in the shared EXIT/HUP/INT/TERM
   finalizer;
6. writes pre/post receipt SHA, exact-set SHA, root path and the
   `ndp_root_toplevel_unchanged` conjunction into the formal return;
7. returns nonzero on any add/delete/rename/type drift without deleting the
   unknown entry.

## Local final-ZIP evidence

Final audit:

`artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/conv_native_four_lane/r5_n4_0cc_p12_rootgate/r5_n4_0cc_p12_rootgate.final_zip_audit.json`

SHA-256:

`2f5a513ffd871ab76908b65d787d4f2685739df45e6c7777ca6ff7e2fbd6fcdc`

Results:

- package exact-set/preflight: PASS
- deterministic double build: PASS
- production fixed result literal/nonconfigurability: PASS
- pre snapshot before first write: PASS
- post snapshot before atomic publication: PASS
- normal: exit `0`, root unchanged, return published
- compile-fail: exit `42`, root unchanged, return published
- HUP: exit `129`, root unchanged, return published
- INT: exit `130`, root unchanged, return published
- TERM: exit `143`, root unchanged, return published
- new root-level directory: exit `23`,
  `ndp_root_toplevel_unchanged=false`
- new root-level file: exit `23`,
  `ndp_root_toplevel_unchanged=false`
- declared pre-existing parent missing: fail closed
- tampered pre-snapshot receipt: fail closed
- removed drift exit conjunction mutation: rejected
- return duplicate under supplied server root: absent in every scenario

The local harness used an isolated path mapping only in disposable copies.
The production runner remains hard-coded to the server
`/home/panqs/ndp/simresult`; the local workspace did not create or map that
server path.

## Release and storage identity

Status: `PACKAGE_READY_NOT_RUN`

Unique pickup ZIP:

`artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p12_rootgate.zip`

Bytes: `45,883,980`  
SHA-256:
`ab8f13aaa2e66f01bd9c5461f8131b9cf0f89fb1706feb5fcd6aac0f15957646`

Server command:

```bash
bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02
```

Expected server return:

```text
/home/panqs/ndp/simresult/r5_n4_0cc_p12_rootgate_return.zip
/home/panqs/ndp/simresult/r5_n4_0cc_p12_rootgate_return.zip.sha256
```

Storage index SHA-256:

`776ee4d187ac8715574f5591598ed3ef8b553334bc73dc965f8ad352886c0cf2`

The native-four-lane family has exactly one pending package. `pending/`
remains ZIP-only.

## Current rule receipts

- `.agents/rules/生成前必读索引.md`: bytes `14,875`,
  SHA-256
  `1253c18b0008f3a06d509ae15ddaf2c4cd1e95c88f7cd73ec48adaafc7249500`
- `.agents/rules/服务器测试包生成规则.md`: bytes `93,382`,
  SHA-256
  `b1a29b114c57a89dadd56dbb293aeba545cd3acfb3200cadc15058126f359724`
- `.agents/plan.md` mutable provenance: SHA-256
  `43fe7b8c5b7d5d8daf1631f1d01cca1450ef13d7a4891722ebc509061e166e70`
- `NDP_copy01/README_HARDWARE_SIM_ENTRY.md`: SHA-256
  `0b271cd2ba4f16a0fd277d8f52f926be0ef51431ab9a995042363215afb9caa6`

## Claim boundary

This round is a runner/package release-gate replacement only. It did not
run a DUT and does not promote natural terminal, formal 320D, E3, E4, E5,
numeric correctness, or performance. The p11f c0 diagnostic objective and
all prior native-four-lane blockers remain dynamic until a formal server
return is consumed.

## Rule feedback

`RULE_CONFIRMATION`

- `CDA-SERVER-NDP-ROOT-TOPLEVEL-NO-NEW-ENTRY-001` was necessary and
  sufficient to catch the p11f audit escape and to define the p12
  pre/post/negative-control gates.
- `CDA-SERVER-RETURN-FIXED-SIMRESULT-ATOMIC-PUBLISH-001` remained compatible:
  all normal/failure/signal paths produced the unique fixed return outside
  the supplied NDP root.
- `CDA-SERVER-PACKAGE-STORAGE-ROTATION-001` correctly moved the unrun held
  p11f package to `superseded` and published only the p12 ZIP in `pending/`.
- `CDA-SERVER-LOCAL-RELEASE-GATE-IMPACT-APPLICABILITY-001` correctly limited
  blocking revalidation to runner/return/package identity while reusing
  byte-equality receipts for unchanged HDL/config/numeric surfaces.

No non-synonymous `RULE_DELTA_PROPOSAL` is required.
