# node0004 v1 return 与服务器包规则增量主线裁决

日期：2026-07-29

## 裁决

真实回传绑定 `r5_node0004_hw_v1.zip`
SHA-256=`335a174251c2d0070a29f204f5ad0c5b2ae5e471350f7bbcc8875b3b06bed989`。
服务器 VCS 在 `SA_PE_Float_Control.v:1` 的 `<<<<<<< HEAD` 处编译失败：
compile=2、run=125、simulation 未启动、正式动态 readback=0。

原 v1 包的 320 个 runtime D 目标全部随包预置，导致编译失败后仍能与 golden 比较并
误报 320/320 PASS。该结果不是硬件 readback，不能计 E3/E4/E5。

主线接受 Conv/SA 的三项通用规则增量：

- `CDA-SERVER-RUNTIME-READBACK-TARGET-ABSENT-001`
- `CDA-SERVER-RESULT-GATE-CONJUNCTION-001`
- `CDA-SERVER-RETURN-MANIFEST-ALLOWLIST-001`

已发布到 `.agents/rules/服务器测试包生成规则.md`，SHA-256=
`153b0f03210f8e4f98b6b39a7ca7a40b11c788085ba3775826e42beb171167a2`。

## 新候选

- v1：撤销运行资格，只保留失败证据。
- v2：
  `artifacts/operator_config_validation/r5-server-test-packages/r5_node0004_hw_v2_failclosed.zip`
- v2 SHA-256：
  `4bc0be9903e877b79cb11a82997ad5d6b5c6eed36666ec5a47771e83eb339446`
- 状态：`PACKAGE_READY_NOT_RUN`

v2 不预置 runtime D，PASS 必须同时满足 compile、所有 simulation/run、terminal、
readback exact-set、missing=0 和 mismatch=0；return 只按 manifest allowlist 收集。

## 当前 blocker

- `B_NODE0004_SERVER_SOURCE_MERGE_CONFLICT`
- `B_NODE0004_DYNAMIC_RESULT_PENDING`

必须由服务器源码 owner 先清除 RTL merge-conflict marker。该修复不属于算子包权限。
本地主线仍可继续其余 52 Conv 的合同和 signature 规划，但不得在 node0004 有效动态
结果前批量封包。

## 控制面

- `.agents/plan.md` SHA-256：
  `0d78a70b4e2a984b4f34b0d3be1d790bbdf4c4c8c04d0b0dac8e3a799a5a4299`
- 功能 RTL 修改：否
- 服务器检查、上传或运行：否

