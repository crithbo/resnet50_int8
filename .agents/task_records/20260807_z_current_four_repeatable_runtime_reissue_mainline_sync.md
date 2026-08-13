# 2026-08-07 current四包可重复运行runtime-only主线同步

## 裁决

状态：`MAINLINE_SYNC_COMPLETE / FOUR_PENDING_REPEATABLE_RUNTIME_REISSUED`。

用户要求同一exact测试包可在同一`NDP_copy0x`中顺序重复执行：

- 只重置本包精确拥有的
  `install/cfg_pkg/<install_name>`与
  `install/codex_runs/<package_id>/<attempt>`；
- shared parent、foreign siblings和NDP根直接`name+type` exact-set保持；
- 历史`/home/panqs/ndp/simresult`结果不删除、不覆盖；每轮发布
  `<package_id>_r<epoch-ns>_<pid>_return.zip[.sha256]`；
- 只承诺顺序重跑，不声明同包并发锁，不升级fresh identity或E5。

主线已窄幅合入
`CDA-SERVER-PACKAGE-REPEAT-EXECUTION-EXACT-OWNED-RESET-001`，同步共享helper、
schema、validator、tests及四包changed-surface builder/validator。未机械覆盖专项整份规则，
保留了主线既有runner非零早退stderr可见性等并行增量。

## current四包

| family | package | bytes | SHA-256 |
|---|---|---:|---|
| `gap_node0071` | `r5_n71_gap_v50_ga_ob_conjunction_diag.zip` | 1961478 | `96c23c3762b9fca323ff3d76250f8ca9482c74d536a93b843321c8be3f37252d` |
| `qlinearadd_node0007` | `r5_qadd_n7_fullchain_returnfix_v46.zip` | 38062055 | `8c015af623b5b12f924c2ce9e85b5bff708d97e6372d68af565890b498b4fab1` |
| `conv_serialized_node0004` | `r5_n4_hw_v64_dskew_diag.zip` | 5894586 | `8d4bce53f152e829973212a0cf8403c59a86c588a62ef9f11ab5e90937dd2268` |
| `conv_native_four_lane` | `r5_n4_0cc_p18_pekeep3.zip` | 5854983 | `58a7a5e15d3dc05f96431783bb8212d11ea686f5d29d1815a920194272a09b8f` |

四包pickup均位于
`artifacts/operator_config_validation/r5-server-test-packages/pending/<package>.zip`；
pending为扁平ZIP-only，每个在测family恰好一个current包。

## changed-surface与验证

四包均只改变以下五类runtime/metadata成员：

1. `PREPARE_AND_RUN.sh`；
2. `SERVER_RUNTIME_LAYOUT_CONTRACT.json`；
3. package manifest；
4. package return collector/publisher；
5. package内共享runtime-layout helper。

其余functional成员byte-equal：GAP 228、QAdd 142、serialized Conv 112、
native Conv 102。config、numeric、workload、mapping、bitstream、execplan、SCA/SCA_D、
golden、observer与functional RTL均未修改。

共享runtime-layout单测11/11 PASS，Windows无symlink权限的真实symlink case 1 SKIP；
`py_compile` PASS。四包changed-surface validator：

- `artifacts/operator_config_validation/r5-current-four-repeatable-return-v1/mainline_pre_rotation_validation.json`
- bytes=14066
- SHA-256=`42704737a2c04569ddb2958bc4eaff2567ffde31340be6f7137ac5079f723492`
- `pass=true`、`errors=[]`

generated-heredoc分别为GAP 6、QAdd 3、serialized Conv 4、native Conv 2，
全部syntax PASS。共享helper连续执行正控证明stale exact cfg/run被清除、foreign siblings保留、
NDP根exact-set不变；ownership/file/type负控fail closed。

## 存储轮换

四个旧fixed-basename/fresh-only runtime包及其旧收据均无覆盖归档到`superseded`：

| family | archive alias | old ZIP SHA-256 |
|---|---|---|
| `gap_node0071` | `gap_v50_pre_repeat` | `e0eb03f4cba385e054b280c1e3915765a7465bb17f359bf7048669a6951a1c5a` |
| `qlinearadd_node0007` | `qadd_v46_pre_repeat` | `58f5204886fef6015501dedc7e4443936c8ba118be248d12c102b46bf5afa3c5` |
| `conv_serialized_node0004` | `conv_ser_v64_pre_repeat` | `e2ad1cbb94bec3379b5a810352cdfe8d9d5cfa17f2870696a862650b593d7e25` |
| `conv_native_four_lane` | `conv_nat_p18_pre_repeat` | `381e0d8597e72350d5403b73c98ea4d5986d220481cf643b188252b34286eada` |

storage index：

- path=`artifacts/operator_config_validation/r5-server-test-packages/PACKAGE_STORAGE_INDEX.json`
- bytes=179288
- SHA-256=`672b5054403261af1c620171ff150af1ee8d9f3abadd2baa9d333f7af6342f32`
- counts=`pending 4 / tested 60 / superseded 35`
- `pass=true`

## current规则与plan收据

- `.agents/rules/服务器测试包生成规则.md`
  SHA-256=`7cf2cb4511cba04cb8a14d06473d67061deae64f602988d27053d8289c964b13`
- `.agents/rules/生成前必读索引.md`
  SHA-256=`d4ff32f162538574a0dd48402e299fa25a11fb95074352c19fcfb007ebb77603`
- `.agents/plan.md`
  SHA-256=`4f04b3e207a5fd200b6bbc6e66b6c0a312d1e4f24317cd9266d31d2018aecc13`

服务器完成度保持GAP 60%、QAdd 70%、serialized Conv 70%、native Conv 60%；
runtime-only重发不增加服务器证据分。

## claim boundary

本轮只证明本地exact ZIP的repeat-safe runtime reset、per-execution unique return、
changed-surface、规则和storage闭合。没有上传、server compile/simulation、lease、
natural terminal、正式D或E3/E4/E5；没有修改RTL/ISA/hardware/active ndp-sim、
算子config、numeric、workload、mapping、bitstream、execplan、SCA或golden。
