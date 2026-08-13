# Conv native-four-lane p16 XMRE → p17 genvar-static successor

## Scope and ownership

- Unique mainline/return target:
  `019fbec2-fe93-7e03-9314-cff6f222f33d`.
- Family: `conv_native_four_lane`, frozen node0004 c0 diagnostic branch.
- Serialized Conv baseline, functional RTL, public rules, plan, numeric/W3/golden,
  mapping, bitstream, execplan and timeout were not modified.
- No server upload, execution or lease action was performed.

## Current authority receipts used

- `.agents/agent.md`:
  `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f`
- `.agents/plan.md` mutable provenance:
  `e52c64fa74ef5f87e07114f63328632c7772d869932da27ae9e1ae671ab060d9`
- `.agents/rules/生成前必读索引.md`:
  `3c2bd9017f351b6456eac49c966063cc9b76e96420d71162a1ca57d1b62b552c`
- `.agents/rules/服务器测试包生成规则.md`:
  `89d27141f1a151ef5e6cc98603238050c9b0442a3d1937b2ec23cf92e55a27a2`
- `.agents/rules/算子配置规则.md`:
  `dc5243226bacde799b368d37fb9eb656e6b7e3d33a0a2932ae72ab35415ae3e1`
- `.agents/rules/整网测试收敛优化专项规则.md`:
  `12340cd5e619e1923c74e8853006ee21bce8a7a07b0538e9a5196d7800638cd7`
- `NDP_copy01/README_HARDWARE_SIM_ENTRY.md`:
  `0b271cd2ba4f16a0fd277d8f52f926be0ef51431ab9a995042363215afb9caa6`

## Formal p16 return adjudication

- Exact source p16 ZIP:
  `b9dfb0d282013e45328c905c19957523afba81d505bbf5b4600dc82ace6c3611`,
  45,938,384 bytes.
- Server fixed return:
  `/home/panqs/ndp/simresult/r5_n4_0cc_p16_b5port_return.zip`,
  SHA-256
  `80521819781eacb2cd066e26c2095624527907c55e9f4e951a3c1de16af09192`,
  791,191 bytes, `duplicate_absent=true`.
- Production compile exit was `2`; DUT simulation never started.
- First divergence is package-local
  `tb_probe/native_return_observer.svh:1871`, VCS token
  `slice_with_datahub_mc_group_gen`, originating module
  `tb_NDP_Top_new_phy`.
- Root cause:
  p16 used runtime integers `n4d_group_id` and
  `n4d_local_slice_id` to index hierarchical generate arrays inside
  procedural/task consumers. This violates elaboration-constant XMR
  requirements. It does not implicate DUT numeric/config semantics or the
  server environment.
- Formal analysis:
  `outputs/conv_native_four_lane_0ccae916_p16_compile_return_analysis/report.json`,
  SHA-256
  `0535860dec2c9657b58a4c947a3291ed4aac0d30ed35365472bd838569135123`,
  3,076 bytes.

## p17 corrective design

- Fresh package identity and install namespace:
  `r5_n4_0cc_p17_gxmr`.
- All 12 Buffer5 public-port hierarchy reads are continuous assignments
  expanded under enclosing `genvar` loops.
- Procedural/task logic reads only unpacked local monitor arrays; final exact
  observer scan reports:
  - static genvar assignments: `12`
  - procedural local monitor reads: `34`
  - runtime-indexed instance paths: `0`
  - private Buffer state XMR added: `0`
- SCA input paths were mechanically rebound from
  `install/cfg_pkg/r5_n4_0cc_p11f_pubord/` to
  `install/cfg_pkg/r5_n4_0cc_p17_gxmr/` for exactly 86 consumers.
- SCA_D paths were mechanically rebound from the p16 run namespace to the p17
  run namespace for exactly 28 consumers.
- All matrix/bitstream/execplan/mapping/numeric/W3/golden payload bytes remain
  equal to p16.
- Exact longest projected relative path is 112 characters; declared/computed
  budget is 112/112 and the exact-minus-one negative fails closed.

## Final-ZIP release evidence

- Unique operator pickup:
  `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p17_gxmr.zip`
- ZIP bytes: `45,937,639`
- ZIP SHA-256:
  `3828628f2573c3cd970330fba60bd3393b305555085c5517ea074a919f40a978`
- Final ZIP audit:
  `artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/conv_native_four_lane/r5_n4_0cc_p17_gxmr/r5_n4_0cc_p17_gxmr.final_zip_audit.json`
  - bytes: `165,734`
  - SHA-256:
    `90e1fb7f4404690f54a7791e126c8c9a8b1b5b7dfa6fee6bb114f9042f5b8c29`
  - status: `PACKAGE_READY_NOT_RUN`
  - `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`
- Shared runtime-layout report:
  `54ba1fa27024cecbf8165684bf9494a6561d319645fdf0fe94e9d4af68da562b`,
  errors `0`, pass `true`.
- Runtime-layout harness:
  `e67cf538da89a99ed5e62d238963c881cfd3e1344f0683eb5187fd9e78954523`.
- Shadow build profile:
  `ee3f2c4bcdd2c3e2f9f17721c5153cc8cce92ee1c6ca93c5b3bb6ca8c2b9f23a`.
- Release report:
  `outputs/conv_native_four_lane_0ccae916_p17_release/report.json`,
  SHA-256
  `72e065473ed734bd2466ef5cf6583188138df38c696270f5b9fbce7170be1df3`,
  4,624 bytes.

## Blocking gates

- Focused exact changed-span Icarus elaboration: exit `0`.
- Required negative controls:
  - delete required declaration: exit `36`, fail closed
  - misspell required consumer: exit `3`, fail closed
  - delete required continuous assignment: semantic closure reports one
    ownerless monitor, fail closed
- Exact observer guard positive and mutated-manifest negative: pass.
- Diagnostic predicate trace: pass; predicate semantics reused.
- Runner scenarios:
  - normal: exit `0`, compile/simulator stub reached
  - preflight fail: exit `5`, no compile/simulation, partial return
  - compile fail: exit `42`, compile reached, no simulation, partial return
  - HUP/INT/TERM: exits `129/130/143`, compile/simulation reached, partial
    returns
  - missing `install`: exit `12`, no compile/simulation, partial return
- NDP root direct name+type exact-set remains unchanged in all scenarios.
- Existing p11f cfg and p16 run sibling namespaces were injected before the
  normal positive; both marker files survived byte-equal while p17 created its
  fresh cfg root and reached compile/simulator stub.
- Fixed return remains only:
  `/home/panqs/ndp/simresult/r5_n4_0cc_p17_gxmr_return.zip`
  and its sidecar.

## Storage rotation

- p16 is archived under
  `tested/conv_native_four_lane/r5_n4_0cc_p16_b5port` because it was actually
  run and produced formal compile-failure evidence.
- p17 is the family's only pending ZIP.
- Pending pickup is ZIP-only; sidecar/audits are under `pending_receipts`.
- Storage index SHA-256:
  `e8cb5da56ceb49d34005c07b2a0967467dc9d27e5501dfa97c09a1392c124c70`.

## Server handoff and claim boundary

```bash
cd /home/panqs/ndp
unzip r5_n4_0cc_p17_gxmr.zip
cd r5_n4_0cc_p17_gxmr
bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02
```

Expected fixed return:

`/home/panqs/ndp/simresult/r5_n4_0cc_p17_gxmr_return.zip`

No production full-design VCS result, c0 natural terminal, formal 320D,
performance, E3, E4 or E5 is claimed before that formal return is consumed.

## Rule feedback

`RULE_CONFIRMATION`:

- `CDA-SERVER-OBSERVER-XMR-ELABORATION-CONSTANT-001`
- `CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001`
- `CDA-SERVER-INSTALL-SUBTREE-RUNTIME-LAYOUT-001`
- `CDA-SERVER-RETURN-FIXED-SIMRESULT-ATOMIC-PUBLISH-001`
- `CDA-SERVER-NDP-ROOT-TOPLEVEL-NO-NEW-ENTRY-001`
- `CDA-SERVER-PACKAGE-STORAGE-ROTATION-001`

No non-synonymous `RULE_DELTA_PROPOSAL` is required.
