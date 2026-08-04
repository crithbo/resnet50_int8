# ADR-024：复用原生 ndp-sim 执行链，禁止平行实现

日期：2026-07-23

状态：accepted。

## 1. 原仓已有能力

活动固定版本 `ndp-sim/model_execplan` 已经提供：

- `json_loader.py`：graph JSON、shape 表达式、dtype、source、remapping 和 slice mask；
- `control_registers.py`：48 个按 op type 注册的 shape-driven control handler；
- `template_manager.py`：`operator_base_info`、静态模板和初始 bitstream 状态；
- `output_writer.py`：base address 与 LC/PE/stream/buffer/SA/N2N 更新回写；
- `pipeline.py`：地址规划、逐 op patched JSON、bitstream 再生成和 execplan；
- instruction/SCA writer：Load_Config、Write_Reg、Start_Comp、manifest 和 SCA。

当前 DeepSeek crosswalk 的 40 种 graph-referenced stage type 全部已有原生 control
handler。DeepSeek graph 中的 local/remote、local/ring 组合也已经由原生 op_json 或
原生 graph generator 显式选择。

## 2. 不重复实现

对原生已支持的精确 op type，本项目只生成或适配原生 op_json，随后调用
`ndp-sim/model_execplan/main.py`。本项目不得另写同类：

- graph/shape/source parser；
- per-op LC/stream/buffer/SA/GA/N2N patcher；
- 地址规划、bitstream、Write_Reg/Start_Comp、execplan 或 SCA generator。

`deepseek_stage_ir_crosswalk_v1.json`、`deepseek_reduction_rules_v1.json` 和
`deepseek_primitive_rules_v1.json` 的职责限于哈希索引、provenance、能力审计、
ResNet 迁移边界和 fail-closed 放行。

## 3. 本项目仍负责的缺口

原仓没有通用 ONNX→ResNet typed stage lowering，也不会从任意 ResNet stage 自动选择
正确 op type；它以 graph 中已经写明的 `type` 为输入。原仓也不提供本项目要求的
strict schema、qparam/独立数值合同、来源授权、candidate/formal 或 E4/E5 放行。

因此本项目继续负责这些上游/外围合同，但不得复制原生执行链。若 ResNet target type
不在 native registry，须先闭合 RTL/register-map/数值证据，再通过哈希锁定补丁在隔离
`ndp-sim` 副本中扩展原生 handler，最后仍由原生 pipeline 生成全部控制产物。

## 4. 已知边界

部分 `op_json` 是待 `gen_layer0_oplist.py` 注入完整参数后的 graph fragment，不能单独
交给 `json_loader.py`。crosswalk 可以只读索引这些声明，但不得自行求值 shape；最终
可执行 graph 必须由原生组装流程生成并由原生 parser 验收。
