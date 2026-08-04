# Conv native four-lane current RTL identity receipt at 8f2f318

## Disposition

- date: `2026-08-03`
- mainline thread: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- owner: `019fc783-1146-7901-9e40-64d0ed8e052d`
- scope: receipt-only current identity revalidation
- status: `HARDWARE_CAPABILITY_BLOCKED`
- `candidate_release=false`
- `PACKAGE_RELEASE=NONE`
- 53-Conv enumeration rerun: `false`
- E2 entered: `false`
- package generated: `false`
- functional RTL modified: `false`
- plan/rules modified: `false`
- server action: `false`

The authoritative source synchronization closes the old
`SA_PE_Float_Control` trailing-comma syntax blocker.  It does not change the
live negative-psum reconstruction that produced the already-proven
`(-5,+5)` counterexample.  The Conv native-four-lane capability blocker
therefore remains unchanged.

## Current authoritative identity receipts

- source repository: `xlsjdjdk/Trassic2.0_RTL`
- source branch: `master`
- source commit:
  `8f2f3181c1103d705cdf9b9722959e7315f8b875`
- source archive SHA256:
  `8947ee990100b68f8ae082bc1934d2f9b296ee225a4f8d12e4bf4c428810dcab`
- sync report:
  `artifacts/rtl_sync/trassic_master_8f2f318_20260803/report.json`
- sync report SHA256:
  `4a798e2257ece9d49d64ff8fc00acc826fef3d4dbd35291e26e88f141c273e18`
- sync task record:
  `.agents/task_records/20260803_trassic_master_8f2f318_active_rtl_sync.md`
- sync task-record SHA256:
  `3a401af64c1742580c3955eaebdf211fa4c6235038f35e9ed9e1ac7327fe019f`
- current plan SHA256:
  `0c6bc109775d38545cabea1ac61149272bf024eeabc311541f49f8a4a2329eaa`

The sync report records 18 synchronized source/filelist paths and
`2011/2011` relevant source files byte-identical to the authoritative archive,
with zero different or missing files.  Its focused compile receipts are
`SA_PE_Float_Control=0`, `SA_ALU=0`, `SA_PE_ALU=0`, `SA_PE=0`, and
`SA_PE_Group=0`.  This owner does not rerun those compile jobs or promote them
above focused local syntax/elaboration.

Current leaf receipts:

- `SA_PE_Float_Control.v`:
  `4214262e12ab80bf3be867f558d762e134c3122f16df4f7d08063e383242c4e6`
- `SA_PE_Float_CSA.v`:
  `ea24759841d990f230f9c33a111f934e107c996a85b2f5ea00c9408ca73d0223`
- `SA_PE_Mul_Array.v`:
  `135306563de4407c7d1279c942a7d1ce4e347dd8d263e3fd4a7d63f0e8a2587a`
- `SA_ALU.v`:
  `c986ea2de79381afb220ccef83f28466ec3bdda39cd4d80255419bfa214fee06`
- `SA_PE_ALU.sv`:
  `bd59aed271fd65530d7b452c437154159921116d09c76c15acd63817ffbd23c8`
- `SA_PE_Float_Last.v`:
  `86e1cace29c4519759b16d8b95086b3bd5f0bb821a1c04fc173f434f8844451e`

The active and synchronized-source copies of `SA_PE_Float_CSA.v` have the same
SHA256.  The current file differs from the prior independently tested
split-reconstruction leaf only by adding the commented alternative assignment
at current line 49; the live assignments remain content-identical.

## Current filelist and module binding

The current nested filelist chain is:

- `filelists/NDP_Top_phy_filelist.f`
  `67f8e8407390aeff2e2b99cec8e24e1267083692f24d1b9506bbb256d8ddf808`
  includes `Slice_filelist.f`;
- `filelists/Slice_filelist.f`
  `4ac3832bb06b7fb424779b163a36e6b898d954c41c1d3dd7f5964d0bddbc9b9f`
  includes `Specialized_Array_filelist.f`;
- `filelists/Specialized_Array_filelist.f`
  `b978643437cf13c2528e27df602f77f295c4da0c607a957ca3e1bac072ad63c8`
  includes `SA_PE_Group_filelist.f`;
- `filelists/SA_PE_Group_filelist.f`
  `c9f22ba23dee25ba7a0cb504f67566593058f37fa24078610177db9a0f1fedd1`
  includes `SA_PE_filelist.f`;
- `filelists/SA_PE_filelist.f`
  `5ede1ba8f93cd0a42b9e41abef886cdbaef0850a290e5f830c27f5c3a7a06545`
  directly lists `SA_ALU.v`, `SA_PE_Float_Control.v`,
  `SA_PE_Float_CSA.v`, `SA_PE_Mul_Array.v`, `SA_PE_ALU.sv` and
  `SA_PE_Float_Last.v`;
- `filelists/vcs_utils_filelist.f`
  `b23382f1f39822f01cbb9889dd5804c1beccada37102ad532c05ad6067ef7ce0`
  binds the CLA and CSA utility leaves.

`SA_PE_ALU.sv:23-31` maps inport0/inport1/ob2alu-psum to
`SA_ALU.FMA_DataA/FMA_DataB/FMA_DataC`.  `SA_ALU.v:166-178` instantiates the
current `SA_PE_Float_CSA` and connects its integer result to `Int_Result`.
`SA_ALU.v:205-220` passes that result to `SA_PE_Float_Last`, whose current
lines 203-205 forward `i_IntData` unchanged in INT8 mode.

## Existing counterexample bound to current live logic

Existing immutable W3 evidence:

- reachability report:
  `contracts/operator_config/conv_native_four_lane_negative_psum_reachability_v1.json`
- report SHA256:
  `a97e65f3e2f0de08095480873a57b9b1ca497c239b1678ff8c60ee1356ece6bc`
- original capability-blocker record:
  `.agents/task_records/20260803_conv_node0004_native_four_lane_hardware_capability_blocker.md`
- record SHA256:
  `933092c5df4da1dc41fe23ebd65fef860356bb60c54cacc52d1144bb3e6bcf84`

The already-proven first witness remains:

- request: `hwop-0003-00`
- request SHA256:
  `258de9630b244851cecd8b9bcb0c19686f4909d82d16cb124d46d42815a34fbd`
- `(n,h,w,oc,k_group)=(0,23,40,33,14)`
- activation lanes: `[21,24,24,26]`
- weight lanes: `[-1,0,0,1]`
- psum before the group: `-5`
- natural dot4: `+5`
- correct modulo-s32 result: `0`
- full 53-Conv count: `528` joint hits across `19` instances.

The current live semantic path is:

1. `SA_PE_Float_Control.v:185-190` converts negative DataC to magnitude and
   carries its sign separately as `o_SignC`.
2. `SA_PE_Float_CSA.v:24-33` reconstructs the raw 32-bit adder result.
3. The potential full-width assignment at current line 49 is commented out and
   therefore has no hardware effect.
4. Current line 50 assigns only `o_IntResult[30:0]` through the negative-C
   complement path, while current line 51 copies raw `c_Result0_wire[31]`
   independently.
5. The current downstream integer path forwards that split result unchanged.

Those live statements are the same statements used by the prior independent
directed RTL evidence, which returned `0x80000000` for `(-5)+5` instead of
`0x00000000`.  The authoritative sync changes the leaf SHA by adding a comment
but does not change the executable reconstruction.  The old witness therefore
binds content-neutrally to the current identity without re-enumeration or a new
simulation claim.

This receipt does not assert that merely uncommenting the line-49 alternative
would be a sufficient fix; that expression is inactive, has not been authorized
as a repair, and is outside this receipt-only task.

## Blocker and claim boundary

- retain open:
  `SA_INT32_NEGATIVE_PSUM_FULL_WIDTH_RECONSTRUCTION`
- retain:
  `B_CONV_SA_INT32_NEGATIVE_PSUM_BOUNDARY_REACHABLE`
- retain:
  `B_CONV_NATIVE_FOUR_LANE_RTL_IDENTITY_AND_E2_PENDING`
- close for this owner: none
- terminal status:
  `HARDWARE_CAPABILITY_BLOCKED / PACKAGE_RELEASE=NONE`

The current plan already records this same terminal state and explicitly
prohibits 53-Conv re-enumeration, E2 and package generation until the live
reconstruction is repaired and a new current identity is synchronized.

## RULE_CONFIRMATION

The current rules correctly distinguish source synchronization and focused
compile success from functional arithmetic repair.  They also require the
operator owner to preserve a real W3 capability blocker when executable leaf
semantics remain unchanged, and to stop before E2/package generation.

Confirmed rules:

- `CDA-SA-INT8-RTL-COMPATIBILITY-001`
- `CDA-SA-INT8-CONV-MATMUL-COMMON-GATE-001`
- the generation-stop and explicit
  `HARDWARE_CAPABILITY_BLOCKED` terminal routing in
  `.agents/rules/生成前必读索引.md` and `.agents/agent.md`.

Claim boundary: this is a source-identity and live-semantic receipt only.  It
does not add new W3 coverage, RTL simulation, full-design VCS, natural-terminal,
formal-D, performance, E2, E4 or E5 evidence.

`RULE_DELTA_PROPOSAL=[]`
