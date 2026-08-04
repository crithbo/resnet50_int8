# RequantizeUint8 / AverageRequant 算子族接手与 shape holdout 启动记录

日期：2026-07-27

## 当前裁决

- 已接手唯一候选
  `rq_node0001_guardonly_sfu_eventedge_stock_v1`，状态保持
  `PACKAGE_READY_NOT_RUN`。
- ZIP 为 78,068 bytes，SHA256
  `31877dcf0f11a52a0822525e8f49312d25807f81884377f748425693c89b4a53`；
  sidecar 一致，包级 `--validate-only`、fresh-extract、自身 exact-set、
  observer 安装/恢复与 XMR 静态门通过。
- 未取得主线组 A lease，未上传、未运行服务器，未创建后继服务器包。
- node0001 物化 E2 冻结树保持 544 files，tree SHA256
  `01463d7b92d36192c63fff3ffcdb6a4a0b8938eb15cd8349f4a5e5be1a12decc`。
- 四个 `y_zero_point=0` 未物化 shape 已进入参数化准备，但尚未生成 JSON；
  证据等级仅为 `LOCAL_E2_PLANNING_ONLY`，不是正式 target config、E4 或 E5。

## 启动读取收据

本轮磁盘 SHA 与委派入口一致：

- `.agents/agent.md`：
  `5a4660df1e771b75045c45f75e08b7eba771542750b91ab18af6ab0434043de0`
- `.agents/plan.md`：
  `81d57f8143c495b9c2d7e0a33f4eeeb3824ba1b318b03a3b3731552ce045016d`
- `.agents/rules/生成前必读索引.md`：
  `539e8dfbe52ad9fc8bd9fdef8c69d448fb5fd713e938e3adc5f663f82fd806d7`
- `.agents/rules/算子配置规则.md`：
  `f7e3f80e7fb4edd2b42d7ff41a70bba55abfde6797013648dfedccdc6385e023`
- `.agents/rules/NDP硬件字段语义.md`：
  `a955834fc059f08bada8131adc94db5c05112eb1e6acc0a0976eee7e6ae17c59`
- `.agents/rules/服务器测试包生成规则.md`：
  `f3fe8dd18c9e2009db4a2736c6c1e86841760d8ec023bb7b57562f27f5faff04`
- `.agents/rules/RequantizeUint8算子配置规则.md`：
  `44e8ee38d1361f15d78bf5d7918fa10e4648370153178ad10d044fd5c9d26265`
- `.agents/rules/最小双Stage生命周期规则.md`：
  `821b8b04b0e33d0a93e06a3a1bca8307b417bcb63f109cf12414891e9a0bc171`
- `NDP_copy01/README_HARDWARE_SIM_ENTRY.md`：
  `4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7`

同时读取了本族生成器、family classifier、config-bound simulator、validator、
native planner/encoder/execplan 消费链在既有 node0001 generation receipt 中绑定的
入口。未修改 `.agents/plan.md`、`.agents/rules/**`、功能 RTL 或其他算子族资产。

## 四个 holdout

机器报告：
`artifacts/operator_config_validation/r5-requant-zero-point-shape-holdouts-v1/analysis.json`

- file SHA256：
  `9ab7c724266c7ae9f61bceaf3f2001be5a99bcd06564c989a444934fb08d9259`
- semantic analysis SHA256：
  `63800bab834cdae5527731a36b695c9ff3da7172a77456e2c2411c817797877c`

代表项按每个 shape 在冻结 family classification 中的首项确定：

| shape | representative | shards | 状态 |
|---|---|---:|---|
| `[16,64,56,56]` | `r5:hwop-0004-01` | 8 | `LOCAL_E2_PARAMETERIZATION_PENDING` |
| `[16,128,28,28]` | `r5:hwop-0017-01` | 16 | `LOCAL_E2_PARAMETERIZATION_PENDING` |
| `[16,256,14,14]` | `r5:hwop-0034-01` | 32 | `LOCAL_E2_PARAMETERIZATION_PENDING` |
| `[16,512,7,7]` | `r5:hwop-0059-01` | 64 | `LOCAL_E2_PARAMETERIZATION_PENDING` |

本轮只完成 shape/代表项/预计 shard 与物化门的确定性审计。下一步仍须逐 shape
关闭 typed/W3 绑定、LC/MSE/Buffer 字节守恒、strict address-bound JSON、空 cache
mapping/bitstream、execplan/SCA 双 stage 生命周期、config-bound 全量 W3 回放和第二次
隔离重建，之后才可称物理 E2。

## 生成器身份修正

既有 Requant vertical 生成器仍绑定旧公共规则 SHA，导致当前真实规则入口下
fail-closed。仅更新了
`resnet50_pipeline/requantize_uint8_vertical.py` 的三项读取身份常量到本轮磁盘 SHA；
没有重建或修改 node0001 冻结资产。随后重建只读 family classification 收据/报告和
合同，54/54 数值分类保持：

- 33 项 `y_zero_point=0`；
- 21 项 nonzero zero-point guard contradicted；
- node0001 仍是唯一已物化 E2；
- 新 shape JSON emission 仍未授权。

## 验证

- guard event-edge package `--validate-only`：PASS；
- `tests.test_build_requant_guard_eventedge_onecmd_server_test`：5/5 PASS；
- holdout、family classification、vertical 与 package 合并回归：16/16 PASS；
- 环境没有 pytest 模块，故使用仓库 unittest 入口；
- node0001 冻结树和候选 ZIP 身份在本轮前后不变。

## 正式 D 与 observer 分栏

- 本轮无服务器 return，正式 D：`EVIDENCE_MISSING`。
- observer：仅完成包内静态/fresh-extract 验证，未产生运行期 checkpoint。
- 最后可信动态边界沿用既有正式证据：
  `SFU_BST_DATA_AND_COEFF_ADDR_64_OF_64_BIT_EXACT`。
- 首个未观测区间沿用：
  `selected coefficient SRAM output → ALU capture/tag/result → postprocess →
  normal outbuffer write`。
- 下游坏边界沿用：
  `NORMAL_OUTPORT_ACCEPTED_64_ALL_ZERO → MSE4_WDATA_16_ALL_ZERO →
  formal D all zero`。

## BLOCKER_DELTA

- keep：
  `B_REQUANT_SHAPE_LIFETIME_MATERIALIZED_E2`、
  `B_REQUANT_GUARD_DYNAMIC_DATA_PATH`、
  `B_REQUANT_SERVER_E4_E5`。
- close：无。
- add：无。

## RULE_DELTA_PROPOSAL

无。当前发现是生成器读取身份常量陈旧，已在本族代码内修正；没有足够证据建议修改
公共或专项规则。
