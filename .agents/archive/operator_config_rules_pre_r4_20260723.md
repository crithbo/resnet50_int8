# NDP 原生算子配置、数据与复现规则

最后更新：2026-07-22

本规则服务当前原版控制链和用户明确授权的最小 bridge。静态算子配置必须已经存在；graph/tensor 若活动仓库没有专用入口，可由可审计 bridge 描述或生成，但地址、bitstream、execplan 和 SCA 必须由活动原版 `ndp-sim` 产生。旧 server profile、freeze/v20 包、barrier 和三方比较规则不得执行。

## 1. 活动来源

唯一活动配置/生成仓库：

`C:\Users\15383\Desktop\Codex\project\resnet50_int8\ndp-sim`

当前提交：

`ec12424516ae0304228dd2321d4e604fe225e04e`

暂停使用：

`C:\Users\15383\Desktop\Codex\project\resnet50_int8\ndp-sim-ref`

服务器已运行参考目录：

`C:\Users\15383\Desktop\Codex\project\resnet50_int8\jsons`

参考目录只用于确认文件类别和服务器成功先例，不是 JSON、数据或配置来源，也不是最新版工具输出的逐字节基准。

## 2. JSON 层级不得混淆

原生流程中至少区分：

1. `ndp-sim/model_execplan/op_json/*.json`：模型/复合算子图，声明参数、operator 顺序、输入来源、输出 shape 和 slice mask；
2. `ndp-sim/jsons/*.json`：已经写好的硬件原子算子静态配置，包含 loop、stream、buffer、SA/GA/SFU 等字段；
3. `*_withbaseaddr.json` 或原生输出中的 patched JSON：`model_execplan` 按 tensor 地址和实例参数生成的消费配置；
4. `sca_cfg*.json`、`install/cfg_pkg`、`install/execplan.txt`、可选 `Bank_data`：原生 planner/writer 生成的服务器消费内容；
5. tensor/golden/relayout 文件：由原生数据与 layout 工具产生，不由 `model_execplan` 凭空生成。

不得把第 3～5 层文件当作第 1～2 层输入，也不得把参考目录中的最终文件倒灌为源 JSON。

## 3. 只使用已经存在的算子配置

- 首个参考阶段优先选择活动 `ndp-sim` 中已经写好 `op_json` 和全部被引用 `jsons/*.json` 的算子；后续用户授权的本地算子允许把工作库已有静态配置逐字节复制为活动 `type` 别名，但不得在本轮生成或修改配置语义。
- 不允许根仓工具即时发明静态算子 JSON，不允许从参考输出逆向生成源 JSON。
- 不允许手填缺失字段、地址、shape、slice、loop、stream、buffer、PE、dtype 或长度。
- 原生 `model_execplan` 根据 `op_json` 参数 patch 静态 JSON 属于允许的原生步骤；任何仓外 patch 都不允许。
- 目标算子引用的每一种 `type` 都必须在活动 `ndp-sim/jsons/` 中找到唯一、可追溯的文件；若为本地既有配置别名，manifest 必须记录原路径、原哈希和别名同哈希证明。
- 文件同名不等于语义相同；必须以当前 `op_json` 的 `type`、参数表达式和原生 loader 行为为准。

## 4. 当前单原子算子链

当前服务器冒烟图由原生生成器产生：

`ndp-sim/generate_python_golden/model_execplan/op_json/decode_summac_fp32N_fp32N_graph.json`

它只引用一个已经存在的原生原子算子类型：

| operator type | 活动静态 JSON |
|---|---|
| `decode_summac_fp32N_fp32N` | `ndp-sim/jsons/decode_summac_fp32N_fp32N.json` |

对应原生数据和 relayout 入口：

`ndp-sim/generate_python_golden/decode_ops.py`

`ndp-sim/generate_python_golden/run_single_op_decode.py --target-op decode_summac_fp32N_fp32N`

该链已生成 28-slice op0 数据、单图、bitstream、execplan 和自包含服务器目录并通过本地结构/哈希检查；用户已确认服务器完整跑通，但未做数值正确性证明。

## 5. 数据与 golden 来源

- tensor、权重、golden 或初始化数据必须由活动 `ndp-sim` 的原生脚本产生，或来自用户明确允许且独立于禁用参考仓/旧服务器包的正式输入；W3 与形式模型属于允许来源。
- 每份数据都记录来源脚本、命令、shape、dtype、layout、字节数和 SHA-256。
- 原生 relayout/packing 脚本只按其 README/源码约定使用，不能因参考文件大小不同而手改参数或补零。
- 参考目录中的输入、Bank、SCA 或空占位文件也属于禁止提取内容，不能因为其“不是结果”而复制。
- 若当前目标仅为服务器冒烟运行，允许使用活动 `ndp-sim` 明确提供、固定 seed 且可复现的合成输入/权重回退路径；不得另写随机生成器、使用空文件或用参考目录数据填充。需要数值验证时仍必须切回正式数据源。

## 6. 原生参数、地址与 bitstream

- 参数表达式由 `op_json` 和原生 parser 求值，不在外部复制一套解释器。
- 地址由原生 planner/remapping 生成；是否执行 address remapping 只依据当前 README 和目标算子源码路径。
- bitstream 只由活动 `ndp-sim` 的原生 placement/encoder 产生。
- 任何 placement 约束失败、bitstream 缺失、原生异常被吞掉或同输入重跑结果变化，都必须判失败。
- 不得用历史 `ndp-sim-ref` bitstream、根仓 freeze、旧 parsed evidence 或参考目录 bitstream 替换原生输出。
- 不得为服务器额外插入 completion barrier、改 opcode、拆 4 KiB、改地址或重排指令，除非这些就是当前原生 README/源码的默认步骤。

## 7. 配置验收

生成目录自洽检查至少包括：

- `op_json` 中每个 operator 都解析成功；
- 每个静态 JSON 来源唯一且哈希已记录；
- patched JSON 与原生 planner 的地址/shape 记录一致；
- 每个原生 bitstream 与其配置实例一一对应；
- `sca_cfg*.json`、`cfg_pkg`、`execplan.txt` 和可选 `Bank_data` 的引用路径均存在；
- 日志没有 placement、mapping、encoder、writer 或数据生成错误；
- 从全新目录重复执行时输出确定。

通过自洽检查后，可以只读比较参考目录以辅助理解服务器消费类别，但不得把差异当作失败条件。验收以 `.agents/rules/服务器测试包生成规则.md` 的最新版当前格式合同为准：manifest/SCA 引用全部存在、bitstream 真实生成成功、正式数据来源可追溯。

## 8. 当前不启用的旧规则

当前阶段明确不启用：

- 根仓 `tools/generate_*` 生成新的算子配置；
- `ndp-sim-ref` 的 parser、placement、encoder 或 server profile；
- 用历史 typed request、freeze manifest、旧 28-slice execplan/address plan 直接构造控制内容；允许用户授权的数据 bridge 调用当前 tensor 描述和纯数据 layout，但原版 planner 必须重新规划服务器地址；
- config-bound NDPFuncModel preflight；
- hardware freeze、package、overlay、runner、ZIP 和 sidecar；
- 自定义 barrier、readback 合同和三方 P/D/A/D 比较；
- 历史 revision 的 G0～G8 门状态作为当前生成许可。

这些内容仍可在归档和历史中追溯，但只能在后续计划明确恢复时使用。

## 9. 后续 ResNet50 与 Conv

已测参考算子完成本地严格复现并由用户服务器测试通过后，才评估最简单 ResNet50 算子。

`node-0002` MaxPool 是优先候选，但必须重新确认：

- 活动 `ndp-sim` 中已有对应静态 JSON，而非根仓工具新生成；
- 有完整原生 `op_json` 或原生入口；
- 数据、relayout、地址、bitstream 和服务器消费目录均可由原生步骤生成；
- 不复用 `output/maxpool_node0002` 或任何参考目录占位文件。

用户已明确批准 `node-0004 accumulate-wave-0` 单阶段例外：根目录既有 `conv_1x1_real.json` 逐字节别名到活动 `ndp-sim/jsons`，正式 W3 数据经当前 signed-A Conv28 layout 生成单样本槽，graph 由最小 bridge 产生，控制内容由原版工具重建。该例外不授权其他 Conv、完整三波次、requant 或三方比较；缺口仍须向用户确认。

## 10. 停止条件

出现以下任一情况停止：

- 对应算子的静态 JSON 不存在；`op_json` 缺失时只有在用户授权且最小 graph bridge 能完整描述输入/输出时才可继续；
- 数据来源、原生命令、依赖版本或 remapping 条件无法从活动仓库复现；
- 需要从参考目录、`ndp-sim-ref` 或根仓旧产物提取内容；
- 需要修改原生源码或手工修正原生输出；
- 重复生成不确定；
- 当前 manifest/SCA 引用缺失、bitstream 未真实生成成功或当前格式目录不自洽。

停止时只报告可复现证据、第一处差异和明确缺口；不能继续补文件或通过服务器试跑猜测配置。
