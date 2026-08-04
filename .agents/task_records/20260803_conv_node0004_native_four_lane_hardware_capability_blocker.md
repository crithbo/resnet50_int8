# Conv node0004 native four-lane RTL capability blocker

## Terminal disposition

- date: `2026-08-03`
- mainline thread: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- independent performance owner:
  `019fc783-1146-7901-9e40-64d0ed8e052d`
- serialized correctness owner, unchanged:
  `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- status: `HARDWARE_CAPABILITY_BLOCKED`
- `candidate_release=false`
- `PACKAGE_RELEASE=NONE`
- functional RTL modified: `false`
- server package generated: `false`
- server action taken: `false`

The frozen node0004 instance itself does not reach either named
`SA_PE_Float_CSA` boundary.  The same mandatory gate over the intended 53-Conv
scope does reach `psum=-5, dot4=+5` in a real W3 occurrence.  The user dispatch
explicitly requires a stop if either the representative instance or intended
expansion reaches a boundary.  Therefore this task stops before target JSON,
mapping, bitstream, execplan, SCA, config-bound E2 or package generation.

This result does not change or supersede the independent serialized correctness
baseline, node0004 v28 diagnostics, or their owner.

## Immutable rule and authority receipts

The plan matched the dispatch SHA at task start:

- `.agents/plan.md`:
  `5f5715b1cb3d7649b36dc79736eb2da1038ef8ea94acd1884bf17092033f8654`

During the read-only audit, a concurrent mainline update changed current
`.agents/plan.md` to
`8bde3e23b345853d4058099eb8215b4a710ce9adbf182fcbabf14fea8f6d4aec`.
The current file retains this owner and the negative-psum reachability gate as
open/pending; it does not yet contain this task's new witness.  This is treated
as legitimate mutable provenance awaiting the structured return, not as an
authority rollback.  This task did not modify the plan.
- `.agents/agent.md`:
  `d9fe95839c2c92a83083d956392a66876c1007fbb7922522c6a8920babab6721`
- `.agents/rules/生成前必读索引.md`:
  `db339fb8f47105b76deef85cdd43cfc85af6358a0c8155571fde54c2006f26c5`
- `.agents/rules/算子配置规则.md`:
  `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171`
- `.agents/rules/NDP硬件字段语义.md`:
  `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055`
- `.agents/rules/服务器测试包生成规则.md`:
  `5761987d07f425a316bd845e390405c0c64d78c9a371b9cce22cc491c8f25f48`
- `.agents/rules/INT8_SA点积专项规则.md`:
  `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`
- `.agents/rules/精确UINT8量化尾专项规则.md`:
  `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e`
- `NDP_copy01/README_HARDWARE_SIM_ENTRY.md`:
  `4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7`
- `.agents/task_records/20260727_int8_sa_dot_product_common_cause_adjudication.md`:
  `d844505b0dd098888d05e52f7872e1affb1cde92b9bfe7c885665b4fa81516d8`
- `.agents/task_records/20260727_int8_sa_rtl_repair_acceptance.md`:
  `45d9c1f9c7e209e7b949db59de3fd00a5a71c951325971955f5c42d87b7a5e7b`
- `.agents/task_records/20260729_trassic2_github_master_sync_and_interface_adjudication.md`:
  `15d5cb4aecb35bf46bab2d913c8d6cda630534f79bd6cf48c6c72493af9f21a7`
- `outputs/conv_sa_rtl_compile_audit_b7acbe5/report.json`:
  `d9bcdc5d02866cd0510128e89b80ad15b03c52299722bb0e3995502fb24bc6af`
- `.agents/task_records/20260803_conv_node0004_v26_return_v28_dwrite_path_successor.md`:
  `3fce2611614b7566dab59c088d10fc80e8be011f5492f5144e7c2ca161c0d622`
- `resnet50_pipeline/conv_serialized_one_product_local_e2.py`:
  `00032b9e933a6effcdd05ddd6ee3ee6cebe71af13e40572febcf3f833273f642`
- `resnet50_pipeline/conv_stem_serialized_contract.py`:
  `0103310ae95e7233c189800d60e6aa31d4e5bad9cec2af4fb16613f106d0ee77`
- `contracts/operator_config/conv_sa_remaining52_expansion_v1.json`:
  `31065f28bc5c9ec46d150c74a1c3370a6166a3f4bff3fa54c711f3d7b5ef7063`

## RTL identity and arithmetic adjudication

The current local active RTL is byte-identical across 2,242 files to the
authenticated Trassic snapshot:

- source commit:
  `b7acbe55340ca7e98ead70335156f555929c0777`
- archive SHA256:
  `3573d0c03f24d6433a655536653caf45702a0b71441590a09e375f0ed0f7334c`
- source-tree SHA256:
  `62cc16b630046e7a1ed09351de8065e37764e2afb4c881f44d2f84e57c55bdc7`
- `SA_PE_Mul_Array.v`:
  `135306563de4407c7d1279c942a7d1ce4e347dd8d263e3fd4a7d63f0e8a2587a`
- `SA_PE_Float_CSA.v`:
  `04cc5d95754a05a7580c1e6a4649c19c067f41af6f0d12184d736bfef2164cf5`
- `SA_PE_Float_Control.v`:
  `c6018e761f208fcbd54936544608e5053d63888c6e97fa06cc43e6e94133c4b`
- `SA_ALU.v`:
  `c986ea2dce5a9e1e70a881615b1ce70abff4cf465ca312b581b9b62af41fee06`

The leaf binding reaches `SA_ALU` through the authoritative nested filelists.
The active `SA_PE_Mul_Array.v` has the required first `CSA_4to2` width 18 and
passes `carry_int` directly as `last_B`, without the historical duplicate carry
shift.

A fresh focused Icarus compile against the existing syntax-only diagnostic copy
(whose arithmetic leaves are byte-identical and whose Control leaf only removes
the trailing comma) succeeded.  The ordered source-manifest SHA256 was
`cb029f0714603151cf61f04478445b89ea8551c7441a501ccc6c39a2e24b6758`.
Independent RTL positives included:

- `4 * 127 * 255 = 129540`;
- `4 * -128 * 255 = -130560`;
- an alternating signed case;
- ordinary positive and negative psum additions;
- 20,000 arbitrary `s8 * u8` dot4 plus arbitrary psum samples, zero failures.

The immutable old-stock negative control
`outputs/c0_independent_rtl_audit_20260728/tb_csa4to2_stock_handoff.vvp`
reproduced the invalid duplicate-shift/17-bit results, including `4 -> 6`,
`129540 -> 194310`, and `-130560 -> -195840`.

The same current arithmetic leaves independently reproduce both known
`SA_PE_Float_CSA` failures:

- `(-5) + 5`: RTL `0x80000000`, expected `0x00000000`;
- `INT32_MIN + 0`: RTL `0x00000000`, expected `0x80000000`.

The active tree itself is not an executable local compile identity because
`SA_PE_Float_Control.v` retains a trailing port-list comma.  The v26 server
return does not provide production `SA_PE_Mul_Array`, `SA_PE_Float_CSA`,
`SA_PE_Float_Control` or full-filelist hashes.  Local reference and server
production RTL identities therefore remain explicitly distinct; no production
RTL identity, E4 or E5 claim is made.

## Exact W3 reachability result

Primary fail-fast evidence:

- report:
  `contracts/operator_config/conv_native_four_lane_negative_psum_reachability_v1.json`
- report SHA256:
  `a97e65f3e2f0de08095480873a57b9b1ca497c239b1678ff8c60ee1356ece6bc`
- lowering SHA256:
  `bf661e4eda2011025d9922708ab46a64f8d1b3c279527b88aa7d630bb3545432`
- W3 manifest SHA256:
  `f7e90cf1f087acf255e93d98d1788e0fb0b4c77bbe935ea9addb17feea583180`
- ONNX SHA256:
  `c234f30975989788b4405f25253275aae247ab6dbdd34aaa69ab0a59ff76f6d0`

The scan uses formal W3 activations plus ONNX weights/bias/zero points, exact
stride and padding, OIHW-flattened original K order, natural groups of four,
tail activation `x_zp`, tail weight zero, corrected initial psum
`s32(bias - x_zp * sum(weight))`, and modulo-s32 recurrence.  It scans node0004
first and then the intended Conv domain, stopping on the first exact hit as
required.

Frozen node0004 complete result:

- exact occurrences: `51,380,224`;
- dot4 observed range: `[-25736, 20597]`;
- `(-5,+5)` joint hits: `0`;
- `(INT32_MIN,0)` joint hits: `0`;
- evidence:
  `outputs/conv_native_four_lane_negative_psum_reachability/node0004.json`;
- evidence SHA256:
  `1d2575d29bdd5a124a39bff50a9b21a9060e4423bdd9d9feb83e536c44867cb1`.

The nonzero-`x_zp` stem, including K=147 tail packing and corrected bias,
also completed with zero joint hits over `475,267,072` occurrences:

- evidence:
  `outputs/conv_native_four_lane_negative_psum_reachability/stem_node0001.json`;
- evidence SHA256:
  `8bf8a8ea4c0bda8b85a44a6212e692b1b6a8575ecc2d92a3417f954cb6404223`.

The required expansion gate then failed in `hwop-0003-00`:

- request SHA256:
  `258de9630b244851cecd8b9bcb0c19686f4909d82d16cb124d46d42815a34fbd`;
- output position: `n=0, h=23, w=40`;
- output channel: `33`;
- original K group: `14`;
- activation lanes: `[21,24,24,26]`;
- weight lanes: `[-1,0,0,1]`;
- lane products: `[-21,0,0,26]`;
- initial psum: `5687`;
- groups 0 through 13 sum: `-5692`;
- psum before group 14: `-5`;
- group-14 dot4: `+5`;
- correct modulo-s32 result: `0`;
- current RTL result established by the independent directed RTL test:
  `INT32_MIN`.

An independent full-domain cross-check enumerated all 53 instances and
`15,426,912,256` occurrences, with zero final-accumulator mismatches against
formal W3.  It found 528 `(-5,+5)` joint hits across 19 instances and zero
`(INT32_MIN,0)` joint hits.  The ordered instance-summary digest was
`7aae34309470a4bd74a98dc4caffe0682965b6b60d9a9addbcf0e943218f6429`;
the ordered first-witness digest was
`b60d4d5c387f8aca22f37fa7c5b30f8b720dc0a787bef905a985366044da9dc1`.
This secondary scan confirms, but is not needed to weaken, the primary
fail-fast blocker.

## Fresh evidence implementation

- `resnet50_pipeline/conv_native_four_lane_performance.py`:
  `61d816655a502f9051c4c90576cc299eb7d8587f5ea5a6c08fa949365465930d`
- `tools/build_conv_native_four_lane_reachability.py`:
  `87afab31aa547908a729f12b018793dda0d09780baf1750cdfd5d9533cb0787c`
- `tests/test_conv_native_four_lane_performance.py`:
  `be1ac6afbc794c168ccfac1d9e1c3f36e547473e6ea1149f93695b7d474940b0`

Verification:

```text
python -m py_compile <three fresh Python files>
exit=0

python -m unittest tests.test_conv_native_four_lane_performance -v
Ran 3 tests
OK

python tools/build_conv_native_four_lane_reachability.py
status=HARDWARE_CAPABILITY_BLOCKED
exit=nonzero
```

The unit tests contain positive controls for both named counterexample pairs
and a no-hit negative control.  The real-W3 report is the config/input-bound
evidence; the unit tests alone are not credited as reachability proof.

## Performance and local/server gate accounting

No final native configuration was materialized because the pre-generation
hardware gate failed.  Therefore:

- actual native compute occurrence: `NOT_MATERIALIZED`;
- actual native weight traffic: `NOT_MATERIALIZED`;
- actual native activation traffic: `NOT_MATERIALIZED`;
- actual native useful-lane utilization: `NOT_MATERIALIZED`;
- native-vs-serialized ratios: `NOT_CLAIMED`;
- deterministic double build: `NOT_RUN_AFTER_MANDATORY_STOP`;
- config-bound E2: `NOT_RUN_AFTER_MANDATORY_STOP`;
- native-vs-serialized-vs-ONNX/W3 three-way comparison:
  `NOT_RUN_AFTER_MANDATORY_STOP`;
- mapping/bitstream/execplan/SCA closure:
  `NOT_GENERATED`;
- package/final-ZIP/runner gates: `NOT_GENERATED`;
- natural terminal and 320/320 formal D: `NOT_RUN`;
- performance/E4/E5: `NOT_CLAIMED`.

For orientation only, the frozen historical configs—not a fresh candidate
result—encode `205,520,896` serialized one-product occurrences at maximum 25%
useful-lane utilization versus `51,380,224` natural-dot4 occurrences at 100%.
Their request reports show weight payload `262,144 -> 65,536` bytes.  Activation
must be reported in both forms: one natural B stream is `12,845,056` bytes
versus serialized `51,380,224`, but the historical natural config has both B
and B-prime streams, so total physical activation payload is `25,690,112`
bytes, only a 2x reduction.  These historical numbers are not credited as this
blocked task's deterministic build, E2 or performance result.

The serialized baseline remains a separate config-only correctness asset:
`contracts/operator_config/r5_conv_node0004_serialized_one_product_local_e2_v1.json`
SHA256
`3bfa060ef8598c932d7e456eec4d016ed3f8ff04f2cb9b7744eb8668884f4627`.
The v28 package is an assumed-fixed-hardware natural-dot4 diagnostic, not the
serialized single-nonzero-product oracle; it must not be relabeled as such.

## Blocker delta

- open:
  `B_CONV_SA_INT32_NEGATIVE_PSUM_BOUNDARY_REACHABLE`
- keep:
  `B_CONV_NATIVE_FOUR_LANE_RTL_IDENTITY_AND_E2_PENDING`
- close: none

Only a new explicit user authorization that changes RTL or narrows the scope
may restart materialization.  This task does not propose or authorize any RTL
change.

## RULE_CONFIRMATION

The current routed rules correctly forced immutable identity receipts,
independent RTL positive/negative controls, real-W3 boundary reachability,
fail-fast package suppression, local/server identity separation, and
claim-level separation.  They prevented a model-local node0004 no-hit result
from being incorrectly promoted to a 53-Conv performance candidate.

`RULE_DELTA_PROPOSAL=[]`
