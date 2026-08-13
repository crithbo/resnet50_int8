# Conv native-four-lane p6 formal return: terminal production RTL identity mismatch

Date: 2026-08-05  
Owner: `019fc783-1146-7901-9e40-64d0ed8e052d`  
Unique mainline / return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`

## Scope and terminal result

The p6 public-interface observer crossed the p5 private-XMR failure in the real
production VCS compile. The immediately following post-compile identity gate
found that three of eight required production RTL leaves differ from the
package-approved e1fb0f7 identity and failed closed before the first c0
simulator invocation.

Classification:

`SERVER_PRODUCTION_RTL_IDENTITY_MISMATCH_TERMINAL_NO_PACKAGE`

Status:

`TERMINAL_NO_PACKAGE_SERVER_RTL_IDENTITY_MISMATCH`

`PACKAGE_RELEASE=NONE`

No fresh successor is generated. A package-local config, runner, observer, or
manifest change cannot repair or safely accept unknown/non-authoritative
production RTL bytes. This owner is not authorized to change functional or
server RTL.

## Current rules and ownership

Current disk rules were fully reread before analysis:

- `.agents/agent.md`:
  `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f`
- generation index:
  `93b66e7986beeaddb01f237710af6874bb4bbfcc4c6c6929563c5e98d8397eb2`
- config rule:
  `d4069167000ae5e0076401afbc6c8db20965965ef4f5da30914f40297f59cba0`
- hardware-field rule:
  `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055`
- server-package rule:
  `68fafe7c33e8ac037d94308a0902cdb52afec32f1325d6cee9bc14f70ca9d69d`
- INT8 SA rule:
  `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`
- exact UINT8-tail rule:
  `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e`
- hardware simulation entry:
  `e82f51c73f658fa567d47c8ab277c1cfb2cdf6d7cd2b4debefb3d0543e2228ba`
- `.agents/plan.md` mutable provenance at analysis:
  `58be3123e7d11890403f6d9fae2ffde133c2aa2df2cfef8733cdd8fe60738a5a`

No plan, public rule, functional RTL, serialized Conv asset, numeric/config
asset, or other family was modified. No server upload/run/lease was performed
by this analysis.

## Exact identities

Formal p6 return:

`C:/Users/15383/xwechat_files/wxid_vwpfpfs4fgyk22_29b7/msg/file/2026-08/r5_n4_e1f_p6_armif_return.zip`

- bytes: `51456`
- SHA256:
  `9c590ae7ae17b55ef3471032dc8b3471bbf949e07eeb1a9dd61b0639fd5ccf59`
- adjacent sidecar absent; current return-transport rule makes it optional.

Exact p6 source package:

`artifacts/operator_config_validation/r5-server-test-packages/r5_n4_e1f_p6_armif.zip`

- bytes: `5811422`
- SHA256:
  `05fc4f385d544195ad3cbc68256525d70775cc490d4a42ff784e9b9f7c5d34c1`

Analyzer:

`tools/analyze_conv_native_four_lane_e1fb0f7_p6_return.py`

- bytes: `22187`
- SHA256:
  `d85f2446efcea1494d699ea3bb7bb23ee3785ab865538d19fe43c6559408c964`

Machine report:

`outputs/conv_native_four_lane_e1fb0f7_p6_return_analysis/report.json`

- bytes: `14714`
- SHA256:
  `de253112fde6a0948bdb9ee2c0eeca01828ecae7b7ebe99573a819d4641a8e67`
- `valid=true`

## Internal return receipt

The return ZIP is safe, CRC-valid, single-root and contains 14 files.

- `RETURN_MANIFEST.json` SHA256:
  `4d96a9f370d125786c6b810e9d2db1c7c9c6b1919b76cbd007330efa9f653065`
- `RETURN_ALLOWLIST.json` SHA256:
  `febadc3b820e0329989b1146cd55f4234cabdde35920d0684f1e2a8fc82a77fa`
- returned canonical source manifest SHA256:
  `dc375971f57c92c9464093b6b7c8c7d334523d9273b4383017b1ace609918838`

The observed exact set equals the return-manifest records plus the return
manifest and allowlist. All record sizes/SHA values match. The returned source
manifest is byte-equal to the canonical manifest inside the exact p6 source
ZIP, and its complete file table matches the source package.

Package, install and observer precompile receipts all report `valid=true`:

- package file count: `97`
- install file count: `89`
- runtime-D/preloaded-D count: `0`
- observer SHA:
  `a00c76b17aec6b9b257356cc8b254a571e2958c708630e93a9827691de24e3b3`

## Production compile and private-XMR adjudication

Actual compile:

- compile exit status: `0`
- VCS XMRE count: `0`
- private token `buf2arm_valid_hold` in compile log: absent
- compile driver SHA256:
  `56eca56ee1fe075068a927aec11e5211ce65f4dd49f44cb6cc74443fe0f829ca`
- secondary compile log SHA256:
  `96807bd10c5ddab11518007a6627d3d215e2de1b26336c1d4896021ecae79685`
- production summary: 91.464 s compile + 4.998 s elaboration + 1.818 s
  link; 0 errors and 1 warning.

The actual compile used:

`+define+NATIVE_RETURN_OBSERVER_ENABLE`

and the exact p6 `tb_probe` include directory. Therefore:

`B_P5_OBSERVER_PRIVATE_XMR_PRODUCTION_RESOLUTION=CLOSED`

and p6 is a production-confirmed positive example of
`CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001`.

## Actual production identity

The identity receipt was collected from the actual VCS parsing paths followed
by post-compile hashing. Five required leaves match and three do not.

Mismatches:

| Leaf | Actual bytes | Actual SHA256 | Approved e1fb0f7 SHA256 |
|---|---:|---|---|
| `Array_Request_Manager.sv` | 14630 | `026019ed9643b3b7d83bc0888c4f5b89fc4776015524df1c69bacbab5315e557` | `d3f100b2a1415ff561791ccafd157b038c4d8e80a80bf18dcedb89c1fec7c4eb` |
| `Buffer_AG_Idx_Queue.sv` | 9977 | `7bbf229f60fb91fe89fd78d8e2df8716cd4de2be3fc578c5270c570ea33c7bca` | `b5fc30fa970a4ed38ebdfaf825946a80562ded91d72c600dd1ee89d14103b1ef` |
| `RD_Data_Channel.sv` | 27591 | `449ce3bb75535b7fb9d7d00f5f940e35165ac47929d29b1c654c4755b3c4fcaa` | `6c612cdd0eb907678a4825215553fd4a1b1b79869b1314fafba9b0e8c072f60e` |

Matched:

- `Neighbor_Out_AG.sv`
- `SA_PE_Float_CSA.v`
- `SA_PE_Float_Control.v`
- `SA_PE_Mul_Array.v`
- `SA_ALU.v`

An independent read-only Git-history probe found no exact match for any actual
mismatching SHA among blobs for the same path reachable from current local Git
refs:

- Array Request Manager: 26 unique known blobs, no match
- Buffer AG queue: 14 unique known blobs, no match
- RD Data Channel: 34 unique known blobs, no match

This does not identify the unknown bytes; it proves that none may be promoted
to a locally known authoritative commit identity.

## LPG / FD / terminal root cause

LPG:

1. exact source p6 and exact formal return;
2. exact internal set/hashes/source-manifest binding;
3. package/install/observer guards;
4. production VCS compile, elaboration and link with public observer;
5. actual post-compile hashing of all eight required leaves.

FD:

`post-compile production RTL identity conjunction`, before the first c0
simulator invocation.

Runner ordering is explicit:

```text
compile status == 0
-> compile-identity (fails closed)
-> simv assignment/invocation (not reached)
```

Observed:

- run status: `125` (never initialized by a simulator result)
- signal: `NONE`
- c0 simulator argv/log/observer: absent
- feature binding: absent
- natural-terminal receipt: absent
- canonical record count: `0`

`HANG_ROOT_CAUSE =
NOT_ENTERED_C0_SERVER_PRODUCTION_RTL_IDENTITY_MISMATCH`

The c0 `exec_start -> slice_finish` causal path was not observed. The return
cannot localize memory/RD/Buffer_AG/ARM/SA/MSE4 behavior because simulation
never started.

## Blocker delta and claim ceiling

Closed:

- p5 private-XMR production resolution;
- production VCS compile/elaboration/link reachability;
- actual production eight-leaf identity collection.

Terminal:

- `B_P6_ACTUAL_PRODUCTION_RTL_IDENTITY_MISMATCH_3_OF_8`

Preserved:

- `B_CONV_NATIVE4_C0_EXEC_TO_SLICE_FINISH_UNDIAGNOSED`
- `B_CONV_NATIVE4_NATURAL_TERMINAL_UNPROVEN`
- `B_CONV_NATIVE4_FORMAL_320D_NOT_IN_P6_SCOPE`
- `B_CONV_NATIVE4_E3_E4_E5_UNPROVEN`

p6 intentionally contains no formal 320D payload. No formal-D pass/failure,
performance pass, E3, E4 or E5 is claimed.

## Release-gate impact matrix

| Gate | Applicable | Pass | Evidence/disposition |
|---|---:|---:|---|
| core always | yes | yes | exact source/return/internal receipt and preflight |
| real runner | yes | yes | reached compile, identity gate, finalizer and allowlist return; failed closed before sim |
| package-local HDL | yes | yes | actual VCS compiled/elaborated/linked the public-surface observer, zero XMRE |
| materialized config | no | yes | `receipt_reuse`; no successor/config change |
| diagnostic semantics | no | yes | `record_only`; no fresh changed predicate is released |
| return/result conjunction | yes | **no** | 3/8 production leaves mismatch; c0 not started |

Overall:

- `blocking_failures =
  [B_P6_ACTUAL_PRODUCTION_RTL_IDENTITY_MISMATCH_3_OF_8]`
- `pass=false`
- `status=TERMINAL_NO_PACKAGE`

Changed causal config does not exist, so
`CDA-CONFIG-CAUSAL-TRANSACTION-LEDGER-001` and
`CDA-CONFIG-BOUNDARY-MICROTRACE-001` are
`not_applicable/receipt_reuse`. No numeric/W3/golden/config/runner/HDL/path
regression is repeated.

No fresh observer/parser/canonical predicate is released, so the new predicate
event-trace unit is `not_applicable`. The grandfathered p6 public-surface change
has stronger production evidence: the actual VCS compile crossed it.

## Minimum next action

An operator with server RTL authority must synchronize the real server RTL to
one approved immutable identity. Only after that external state change may the
mainline dispatch a fresh package bound to those exact bytes and rerun the c0
diagnostic.

It is unsafe to build a package that merely replaces the three expected hashes:
the actual leaf bytes were not returned, do not match any known same-path Git
blob, and have not passed local semantic or focused-scope validation.

## Rule feedback

`RULE_CONFIRMATION`

The current public rules correctly:

- make actual post-compile production identity a blocking result gate;
- prefer public module/interface surfaces over private XMR;
- permit receipt reuse when the materialized config slice is unchanged;
- prohibit compile-only evidence from claiming simulation, natural terminal,
  formal D, performance, E3, E4 or E5.

No evidence-backed non-synonymous `RULE_DELTA_PROPOSAL` is required.

