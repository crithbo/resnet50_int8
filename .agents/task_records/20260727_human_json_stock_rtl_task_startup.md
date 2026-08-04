# 人工算子 JSON → stock-RTL 专用任务启动记录

读取时间：2026-07-27T14:28:04+08:00

## 职责边界

- 只消费用户明确指定的人手编写/修改算子配置 JSON。
- `jsons/` 中经确认的配置和 `ndp-sim/jsons/` 中云端原生且 RTL 验证的配置只作参照，
  不得静默替换或修补人工候选。
- 在取得精确人工 JSON 路径、算子、shape/qparam、输入和 golden 前，只做规则读取与
  路径盘点；不生成 mapping、bitstream、execplan、SCA/SCA_D 或服务器包。
- 不接管或重跑既有 Dequant node0077、Requant node0001 包。
- 不修改公共规则或功能 RTL；后续只在报告中提出可复用规则增量。

## 读取收据

| 路径 | bytes | SHA-256 | 原因 |
|---|---:|---|---|
| `.agents/agent.md` | 3439 | `367f4f4260246d40531d83cc6d24fe94946cb05bce6fbef18c428f05b634c083` | 项目稳定边界 |
| `.agents/plan.md` | 13195 | `a9f0c3397dad32473f542c82852bef9d244535ca40abdb688623aa3c47f14354` | 当前冻结路线与停止门 |
| `.agents/rules/生成前必读索引.md` | 5650 | `539e8dfbe52ad9fc8bd9fdef8c69d448fb5fd713e938e3adc5f663f82fd806d7` | 读取路由与停止门 |
| `.agents/rules/算子配置规则.md` | 12168 | `a5fbe2f0fa2e26d8cd4ebfe8772d5a3c69516d6918cfaa5087198706a352427b` | JSON、provenance、完整重建门 |
| `.agents/rules/NDP硬件字段语义.md` | 12602 | `7f446adb1719658ce75c2614c6d619fc2c7cdcabf5e4fd34945482645539158f` | LC/MSE/Buffer/SA/GA/N2N 字段语义 |
| `.agents/rules/服务器测试包生成规则.md` | 15938 | `0fec7a4f72246c9e802fb2e91e972c2f636e2721aaeef1194c2d4d3fba103fbc` | 包、身份、回传与动态门 |
| `NDP_copy01/README_HARDWARE_SIM_ENTRY.md` | 5461 | `4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7` | stock-RTL 实际仿真入口 |

上述文件均以 UTF-8 分文件读取到 EOF。目标算子尚未指定，因此没有擅自选择算子专项规则；
专项规则将在候选绑定后按精确算子和实际消费字段完整读取。

## 候选位置盘点

- `jsons/`：53 个 JSON；属于用户授权参考语料，不自动视为本轮人工候选。
- `ndp-sim/jsons/`：55 个原生静态 JSON；只有已确认云端原生且 RTL 验证者可作参照，
  不自动视为本轮人工候选。
- `ndp-sim/model_execplan/op_json/`：26 个图级 op_json；属于 graph/planner 输入层，
  不是人工静态算子 JSON 的默认候选目录。
- `.agents/candidates/`、`candidates/`、`human_jsons/`：当前均不存在。

当前结论：没有可由任务自行选择的精确人工候选。必须等待用户提供候选路径。

## 已确认的原生消费入口

- planner/execplan：`ndp-sim/model_execplan/main.py` 与
  `ndp-sim/model_execplan/src/execution_plan_generator/`
- mapper/encoder/bitstream：`ndp-sim/bitstream/main.py`、
  `ndp-sim/bitstream/parse.py`、`ndp-sim/bitstream/config/mapper.py`
- stock-RTL：`NDP_copy01/Makefile.tb_NDP_Top_new_phy`、
  `NDP_copy01/tb_NDP_Top_new_phy.sv`、
  `NDP_copy01/rtl/filelists/NDP_Top_phy_filelist.f`

这些入口本轮仅盘点和哈希，不执行。目标 handler、op_json、golden/relayout 和直接 RTL
消费者必须在算子明确后再按实际调用路径确定并完整阅读。

## 等待的最小输入

1. 人工 JSON 的精确绝对路径或仓内路径；
2. 算子类型和目标 ResNet node/hwop/stage 标识；
3. 输入/输出 shape、dtype、layout；
4. qparam（scale、zero-point、axis、舍入/饱和；不适用时明确写明）；
5. 输入 tensor 路径及 bytes/SHA-256，或获准生成它的锁定来源与命令；
6. 独立 golden 路径及 bytes/SHA-256，或获准生成它的锁定来源与公式；
7. 需要覆盖的 stage/slice/occurrence 范围和预期输出 region；
8. 若发现字段错误，是否授权“保留原件并另存 corrected candidate”；默认不授权。

状态：`READY_WAITING_FOR_EXACT_HUMAN_JSON_PATH`。

