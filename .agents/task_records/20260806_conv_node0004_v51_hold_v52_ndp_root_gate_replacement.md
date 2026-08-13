# Conv node0004 v51 HOLD → v52 NDP-root gate replacement

- Owner: `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- Mainline target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- Result: `PACKAGE_READY_NOT_RUN`
- Classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`

## Adjudication

The exact v51 runner did not create an obvious new entry under the supplied
NDP root, but it did not capture the required direct-child name/type exact-set
before the first write, did not capture it again in the shared finalizer, and
did not return or fail closed on the comparison.  Therefore v51 could not be
made current by a content-neutral receipt.  It is now superseded.

v52 is a fresh runner-only identity.  Numeric/W3/qparams/tail/workload,
identity-normalized config/golden, observer, timeout/backpressure and
functional RTL remain frozen.  No server action was performed.

## Current receipts

- `.agents/agent.md`: `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f`
- `.agents/plan.md` mutable provenance: `43fe7b8c5b7d5d8daf1631f1d01cca1450ef13d7a4891722ebc509061e166e70`
- generation index: `1253c18b0008f3a06d509ae15ddaf2c4cd1e95c88f7cd73ec48adaafc7249500`
- server package rule: `b1a29b114c57a89dadd56dbb293aeba545cd3acfb3200cadc15058126f359724`
- common operator rule: `dc5243226bacde799b368d37fb9eb656e6b7e3d33a0a2932ae72ab35415ae3e1`
- NDP field rule: `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055`
- INT8-SA rule: `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`
- hardware entry README: `0b271cd2ba4f16a0fd277d8f52f926be0ef51431ab9a995042363215afb9caa6`

## Gate controls

The exact final runner was fresh-extracted and locally mapped only for the
isolated harness result root.  The production runner remains fixed to server
`/home/panqs/ndp/simresult`; this path was neither created nor mapped locally.

- normal: `0`
- compile failure: `73`
- HUP: `129`
- INT: `130`
- TERM: `143`
- new root directory: `96`, fail closed
- new root file: `96`, fail closed
- declared existing parent missing: `96`, fail closed
- comparison result removed from the final status: validator `1`, fail closed

The pre-snapshot is taken before the runner's first write.  All five normal
and abnormal exits use one finalizer to take the post-snapshot, compare the
sorted direct-child name/type set, return the receipts, and block on drift.

## Package release

- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_hw_v52_ndproot_gate.zip`
- bytes: `5146252`
- SHA256: `b60209bae1fc19650d22a6c7df3b5c16b45b8ea9a8d50c15fb65a6e3f1b8abf6`
- server command:
  `bash r5_n4_hw_v52_ndproot_gate/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x`
- expected return:
  `/home/panqs/ndp/simresult/r5_n4_hw_v52_ndproot_gate_return.zip`

Final ZIP audit:

- `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`
- `errors=[]`
- report SHA256:
  `0fea0798cf0d38726241a2016c65c81e946461eecd9b3f8b3237cace3d962020`
- root-gate report SHA256:
  `410ead185c05f00fb1d887c3765d8be6a9f324233f2c99a9bad6afe6910c828f`

Storage audit exited `0`.  v52 is the only pending package for
`conv_serialized_node0004`; v51 is absent from pending and present under
`superseded`.

## Rule feedback

`RULE_CONFIRMATION`: `CDA-SERVER-NDP-ROOT-TOPLEVEL-NO-NEW-ENTRY-001`
correctly forced an observable, fail-closed invariant instead of accepting
the weaker claim that no obvious root-level `mkdir` was present.  No
non-synonymous public rule delta is needed.
