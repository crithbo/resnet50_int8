# Conv native four-lane d0aa87f independent revalidation blocker

## Terminal disposition

- date: `2026-08-03`
- mainline: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- independent owner: `019fc783-1146-7901-9e40-64d0ed8e052d`
- status: `HARDWARE_CAPABILITY_BLOCKED`
- `candidate_release=false`
- `PACKAGE_RELEASE=NONE`
- `B_CONV_SA_INT32_NEGATIVE_PSUM_BOUNDARY_REACHABLE`: retained open
- functional RTL modified: `false`
- plan/public rules modified: `false`
- serialized Conv assets modified: `false`
- 53-Conv enumeration rerun: `false`
- E2 entered: `false`
- package generated: `false`
- server action: `false`

The authenticated source change is real, current, conflict-free and
independently compilable.  It still returns `0x80000000` for the frozen
node0003 exact cancellation `(-5)+5`, while adjacent controls pass.  A fresh
single-instance formal-W3 reachability run reproduces the same real occurrence.
The performance owner therefore stops before native materialization, E2 or
package generation.

## Current identity

- current Trassic master:
  `d0aa87f682880a260fb792aaac88f70a23aba414`
- functional commit:
  `cb11353d4196b4af26aac18b4dcc39ba0027e8bc`
- sync machine report:
  `artifacts/rtl_sync/trassic_master_d0aa87f_20260803/report.json`
- sync report SHA256:
  `fb104ea11c9a5ad2d3b83998cec331fb7b0440b781cd2beb690de915ed8c2771`
- sync task record:
  `.agents/task_records/20260803_trassic_master_d0aa87f_active_rtl_sync.md`
- sync task-record SHA256:
  `9ecce80032be2d9573512928d806fecdbdb31caf7344b516ae88c7762b8409d6`
- current plan SHA256:
  `7e576abb1d965450886480eb604dbd887c06a2989d30ac90ec9ec2639ddf1af8`

The sync report binds exactly two changed RTL files with three-way conflict
count zero:

- `SA_PE_Float_CSA.v`:
  `429a29a929a508f7562f9c78d4ab2cd4095961296d0e6f65e8419a4444a6145a`
- `SA_PE_Float_Control.v`:
  `00107da5137ada324407ba7dbf3e74d6e32428a42631aa23f44c5077ea7b7eeb`

Other arithmetic leaves used by the focused compile remain:

- `SA_PE_Mul_Array.v`:
  `135306563de4407c7d1279c942a7d1ce4e347dd8d263e3fd4a7d63f0e8a2587a`
- `SA_ALU.v`:
  `c986ea2de79381afb220ccef83f28466ec3bdda39cd4d80255419bfa214fee06`

The current source performs full-width negative DataC magnitude formation at
`SA_PE_Float_Control.v:186` and defines
`Int_Res_Sign = c_Result0_wire[31] ^ i_SignC` at
`SA_PE_Float_CSA.v:47`.  However, the inactive full-width output assignment at
line 49 remains commented.  Live line 50 still reconstructs only
`o_IntResult[30:0]`; live line 51 assigns the sign separately.  Source change
and compile success are therefore not assumed to be functional acceptance.

## Independent current-source RTL test

Fresh testbench:

- path:
  `tests/rtl_audit/conv_native_four_lane_d0aa87f_witness_tb.sv`
- SHA256:
  `788347d89c27d36fcdcff7364025da9df34d3461134fe6b4264dc6a4b3cd7ab7`
- top:
  `conv_native_four_lane_d0aa87f_witness_tb`

The testbench was compiled with Icarus Verilog 12.0 against 22 explicitly
listed current sources.  The ordered path-and-SHA manifest digest is
`38809765814494eed0d1f1a666f200a4866ce20620f06a3c323491ec2d2d9a33`.
Compilation exit was zero.

Compiled image:

- path:
  `outputs/conv_native_four_lane_d0aa87f_revalidation/conv_native_four_lane_d0aa87f_witness.vvp`
- SHA256:
  `f85fa6d8d17d000920981a86d30f0a6cfda689c13b57564905653e16fe30b1fb`

VVP intentionally gates on mathematical correctness and exited nonzero:

```text
NEG6_PLUS5_CONTROL:
  raw=0x00000001, signC=1, observed=0xffffffff, expected=0xffffffff, pass

NODE0003_NEG5_PLUS5:
  raw=0x00000000, signC=1, observed=0x80000000, expected=0x00000000, fail

NEG4_PLUS5_CONTROL:
  raw=0xffffffff, signC=1, observed=0x00000001, expected=0x00000001, pass

CAPABILITY_OPEN failures=1
simulation exit=1
```

The adjacent controls constrain the failure to exact negative-psum
cancellation in this focused test.  This is independent local RTL evidence,
not production full-design VCS or server evidence.

## Fresh real-W3 necessary gate

Only the required frozen instance was rescanned:

```text
python tools/build_conv_native_four_lane_reachability.py \
  --hw-op-id hwop-0003-00 \
  --output outputs/conv_native_four_lane_d0aa87f_revalidation/node0003_reachability.json
```

The tool correctly returned nonzero with
`status=HARDWARE_CAPABILITY_BLOCKED`.

- W3 reachability report:
  `outputs/conv_native_four_lane_d0aa87f_revalidation/node0003_reachability.json`
- SHA256:
  `a8fc9766a57af0a86314dcb7bcbe75dca0e28e0921158726f2db68657aefd861`
- request: `r5:hwop-0003-00`
- request SHA256:
  `258de9630b244851cecd8b9bcb0c19686f4909d82d16cb124d46d42815a34fbd`
- first hit:
  `(n,h,w,oc,k_group)=(0,23,40,33,14)`
- activation lanes: `[21,24,24,26]`
- weight lanes: `[-1,0,0,1]`
- `psum_in=-5`
- `dot4=+5`
- correct modulo-s32 result: `0`
- current independent RTL result: `0x80000000`
- occurrences enumerated before required fail-fast: `6,291,456`
- single-instance planned occurrences: `205,520,896`
- 53-Conv enumeration rerun: `false`

One real hit is sufficient to keep the capability blocker open; continuing the
instance or 53-Conv census would not change the release decision and was
therefore not performed.

## Machine adjudication

- report:
  `outputs/conv_native_four_lane_d0aa87f_revalidation/report.json`
- report SHA256:
  `3020f79c46338c8148c8d86f3e481e92fe368f64d703b775cf27090d46634081`

Blocker delta:

- close: none
- retain:
  `B_CONV_SA_INT32_NEGATIVE_PSUM_BOUNDARY_REACHABLE`
- retain:
  `B_CONV_NATIVE_FOUR_LANE_RTL_IDENTITY_AND_E2_PENDING`
- retain:
  `SA_INT32_NEGATIVE_PSUM_FULL_WIDTH_RECONSTRUCTION`

No fresh native configuration exists, so occurrence, traffic and utilization
remain `NOT_MATERIALIZED / NOT_CLAIMED` for this identity.  The serialized
correctness baseline remains untouched at
`contracts/operator_config/r5_conv_node0004_serialized_one_product_local_e2_v1.json`,
SHA256
`3bfa060ef8598c932d7e456eec4d016ed3f8ff04f2cb9b7744eb8668884f4627`.

## RULE_CONFIRMATION

The current rules correctly prevented an authenticated source sync, named
functional commit and focused compile success from being promoted to an
arithmetic repair without an independent directed RTL pass.  They also
correctly required real-W3 reachability and fail-closed routing before
performance materialization.

Confirmed:

- `CDA-SA-INT8-RTL-COMPATIBILITY-001`
- `CDA-SA-INT8-CONV-MATMUL-COMMON-GATE-001`
- generation-stop and `HARDWARE_CAPABILITY_BLOCKED` routing in
  `.agents/rules/生成前必读索引.md` and `.agents/agent.md`.

Claim boundary: focused current-source Icarus plus single-instance fail-fast W3
reachability only.  No E2, mapping, bitstream, execplan, SCA, server package,
full VCS, natural-terminal, formal-D, performance, E4 or E5 claim.

`RULE_DELTA_PROPOSAL=[]`
