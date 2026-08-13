# Conv native four-lane p18 RETURN_ANALYSIS → p19b D-flow successor

## Scope and ownership

- Family: frozen node0004 native four-lane performance candidate.
- Mainline return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`.
- Serialized Conv baseline, functional RTL, numeric/W3/golden, workload, mapping,
  bitstream, execplan, SCA semantics and timeout remain frozen.
- No server upload, run or lease was performed locally.

## Formal p18 identities

- Formal return:
  `C:/Users/15383/Downloads/r5_n4_0cc_p18_pekeep3_r1786110514921865390_3724786_return.zip`
  - bytes: `2122559`
  - SHA256: `7e4aeaed79a344dc35f392248f17505dbdba3a7b8eda1ae1328c67ef4a609dc5`
- Exact source:
  `r5_n4_0cc_p18_pekeep3.zip`
  - bytes: `5854983`
  - SHA256: `58a7a5e15d3dc05f96431783bb8212d11ea686f5d29d1815a920194272a09b8f`
- Canonical analysis:
  `outputs/conv_native_four_lane_0ccae916_p18_return_analysis/report_v2.json`
  - bytes: `32376`
  - SHA256: `cd2895c21c8ad79c716f50c9ff6e9a837ceb62e4d8502e522b74b25086d152b5`

The repeatable-return basename is a per-execution identity and was not
misclassified as a source-package mismatch. CRC, safe root/path, internal
exact-set, allowlist, returned source manifest, install-only layout,
repeat reset and unique-return receipts all pass.

## p18 execution adjudication

- Production compile: exit `0`; actual compiled leaf identity collected.
- DUT simulation started and observers ran.
- Final signal: external `INT`; run exit `125`.
- The actual/local/cloud leaf differences are nonblocking provenance after a
  successful compile. Relevant Buffer/ARM/MRM differences remain attached to
  this evidence and prevent any current-cloud E3/E4/E5 claim.
- This c0 diagnostic intentionally has no formal-D payload.

Qualified event comparison closes the old PE keep threshold boundary:

| Event | p17 | p18 | Delta |
|---|---:|---:|---:|
| SA input acceptance | 30 | 30 | 0 |
| SA output acceptance | 4 | 5 | +1 |
| MSE4 index acceptance | 3 | 3 | 0 |
| Buffer5 ARM acceptance | 4 | 5 | +1 |

Therefore `keep_last_index=3` dynamically admits the fifth SA output and the
fifth Buffer5 ARM transaction. Held valid levels are not counted as
transactions.

After the new acceptance, four consecutive qualified windows have the same
progress digest and total (`202`). The last public boundary is:
Buffer5 ARM valid `0xff`, ARM ready `0`, MRM valid `0`, SA valid `1`, SA ready
`0`. No `slice_finish` follows before the external interrupt.

- Last proven good: PE keep3 release and fifth Buffer5 acceptance.
- First divergence: qualified D-flow stops after that acceptance.
- Root classification: `POST_PEKEEP3_D_FLOW_CONTROL_STALL`.
- Root is not yet unique. Remaining low-cost candidates are
  prepared-data/descriptor issue-pop skew, MSE4 descriptor/index propagation,
  Buffer_AG source/tag/address lifetime, and D-write/global terminal ownership.
- Serialized v63 similarity is not treated as root proof.
- Natural terminal: not proven.
- 27/27 terminals: not proven.
- Formal 320D: not present/not proven.
- E3/E4/E5 and performance: not claimed.

Blocker delta:

- Closed: p18 formal-return receipt; repeatable-runtime proof; dynamic
  `keep_last_index=3` boundary.
- Opened: post-keep3 D-flow first divergence is not unique.
- Preserved: c0 `slice_finish`, 27 natural terminals, formal 320D and E3/E4/E5.

## Fresh p19b successor

Disposition: `PACKAGE_READY_NOT_RUN`, diagnostic-only, `candidate_release=false`.

Pickup ZIP:

`artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p19b_dflow.zip`

- bytes: `5873801`
- SHA256: `ac920faca1e90bcf31371a49529579bd8ec31a0c711a10f6f4820f60778114ef`
- sidecar SHA256:
  `90c7407d1846382b2cc8abe5e92cd17c88f8a45fe4ffd063e4b6327077e07843`

The only changed functional surface is a bounded, time-aligned, qualified
D-flow observer covering MSE4 descriptor/index, LC18/PE7, row-LC/Buffer_AG,
Buffer5 read, D-write, DataHub, write drain/terminal, LC9 split/actual,
D-terminal owner, LC13/14 and D-skew. Production VCS remains dynamic.

Frozen receipts:

- deterministic double build: pass;
- 87 installed payload members byte-equal to p18;
- SCA pair equal after package-identity normalization;
- observer exact imported tail SHA256:
  `328fa3390389906fd4bf9f1e322ea9559f2163daa7ef37e1b64229e0abe82615`;
- final observer SHA256:
  `dd250ebe473a7c2a454f2ce55501d843dc4994b2ceda0bef4f860eb22c367c07`.

Final audits:

- build:
  `r5_n4_0cc_p19b_dflow.build.json`,
  SHA256 `9475ff47dbd45218c68bd8302a9fac51cdc70357fbb5af5bfca040223a0bf702`;
- family audit: pass, errors `0`,
  SHA256 `444c235f446631caac28002833f34404c643688a56fa706288182add815282c4`;
- required normal/preflight-fail/compile-fail/HUP/INT/TERM runtime harness:
  pass,
  SHA256 `d678e2fcbfb97c6781752f24d1b1945ae50a665f48a9230917da52143617b3de`;
- shared runtime-layout validator: pass, errors `0`, exact final ZIP invocation
  count `1`,
  SHA256 `496026db459744509b19f457f8dc4baf7884fdf25ebde70cfedcb71b05882fa8`;
- final ZIP audit: valid,
  SHA256 `7a004d1bf12bb09527d8314b95dbf6b7dcdf9fa8f59b5c8d053f9e30bffdf747`.

Server command after extracting the ZIP:

```bash
bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02
```

Expected return is one per-execution uniquely named ZIP plus its SHA256 sidecar
under `/home/panqs/ndp/simresult`; no fixed basename should be assumed.

Storage rotation passed:

- p18 moved to `tested/conv_native_four_lane/r5_n4_0cc_p18_pekeep3/`;
- p19b is the sole `conv_native_four_lane` pending ZIP;
- `pending/` remains ZIP-only; sidecar and audit receipts are under
  `pending_receipts/conv_native_four_lane/r5_n4_0cc_p19b_dflow/`.

## Rule feedback

`RULE_CONFIRMATION`: current return identity, repeatable-return, actual/cloud
nonblocking identity, qualified-event, install-only V2, fixed simresult,
root-direct exact-set, early-finalizer, final-ZIP, release-matrix and storage
rotation rules were sufficient. No non-synonymous `RULE_DELTA_PROPOSAL` is
raised.
