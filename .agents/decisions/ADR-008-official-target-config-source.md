# ADR-008：确认正式硬件配置来源并建立逐算子前置审计

状态：已由操作者采用（adopted）；只批准配置来源，不批准数值模拟器、物理布局、RTL构建或板级运行
日期：2026-07-14

2026-07-14更新：ADR-009在不改变本ADR配置来源结论的前提下，另行批准DeepSeek公共物理基线与ResNet W4差异layout；它没有批准数值模拟器或板级运行。下文关于G4仍缺物理layout/profile与clean elaboration的描述已过时，当前门状态以ADR-009和G4 v2审计为准。

## 决定

1. `ndp-sim-ref@e299b2804448242d1589b3e58ed7c5a9a5eca09f`中的`jsons/`、`bitstream/`和`model_execplan/`被确认为正式28-slice硬件配置来源，不再只称为“参考框架”。
2. `model_execplan/config/register_map_with_groups1.csv`用于解释JSON字段的寄存器/端口语义；实际字段排列遵循同一commit中`register_mapping.py`已经实现的规则：读取`Nbit`宽度前缀并按行累加，不使用CSV内不可靠的`[high:low]`说明文字直接排位。
3. 每个ResNet算子在形成正式W5实例前，必须依次通过：结构/资源/字段范围前置校验、JSON→编码类→寄存器CSV字段追踪、固定进程哈希和seed的两次bitstream复现、相关字段差分敏感性、非法字段fail-closed。未通过的模板不能因CLI退出0而放行。
4. 官方底层`Bit`会按字段宽度取模；根项目必须在调用官方编码器前拒绝溢出，不能修改或猜测官方JSON后继续静默截断。
5. 本决定消除“目标JSON/bitstream配置来源和版本未知”这一项，但不改变G4门：clean elaboration、批准物理layout/profile、数值requant/qparams、目标数值模拟器以及板级load/start/wait/dump仍需各自证据。

## MaxPool首条验证结果

- 42个静态JSON均可读取，其中7个是ResNet或共享候选模板、35个以DeepSeek/Transformer为主；没有文件名或静态模板明确表示Conv。
- 正式MaxPool模板`jsons/maxpool_config_16_112_112_stride2_padding1.json`通过结构、20 LC/10 LC-PE/5 buffer loop/4读1写stream/6 buffer/4×4 GA等资源上限和字段范围检查。
- CSV共有13处“声明宽度”和方括号范围文字不一致；这印证方括号不能作为真值，但不构成当前映射失败。MaxPool涉及的10类模块按正式消费者实际使用的宽度前缀计算，加入编码器显式padding后全部与`FIELD_MAP`总位数一致。
- 在`PYTHONHASHSEED=0`、`PYTHONUTF8=1`、seed 42、10000 iterations、10 restarts下，两次独立生成的全部7个输出逐字节相同；128-bit bitstream为3900 bytes，SHA-256为`2e4096f261adb67296116929d94b691b7e27bf3ff2d327a4bb9db8b017900353`。
- 把`stream_engine.stream0.base_addr`从1024改成1040后，128-bit bitstream变为`a35fd35fbc33fa85a506df733e9c0a012c79d6fd52ee3eb3b888aa144a0d7d36`；把17-bit的`LC1.end`改成131072会在官方编码器前被拒绝。
- 机器证据见`contracts/target_config_authority_audit.json`；它只保存小型JSON、hash、字段追踪和试跑摘要，不保存或宣称正式W5网络产物。

## 对旧规则的纠正

旧审计直接用CSV的`[high:low]`文字计算DRAM LC=48 bit、Read MSE=512 bit等结论，忽略了正式`register_mapping.py`明确改用宽度前缀和行顺序。该判断现被纠正：对于MaxPool涉及模块，当前CSV声明宽度与编码器是一致的；括号范围仍是有缺陷的说明文字，不能独立使用。

旧参数镜像、16-slice文件和活动配置链仍不得混用；本纠正不表示所有42个模板、ResNet全部算子、shape handler、qparams或地址规划已经正确。

## 明确不宣称

- MaxPool bitstream复现不等于MaxPool数值结果正确。
- 正式配置来源不等于`model_execplan`已有完整ResNet handler；当前仍没有命名Conv模板。
- 本决定不批准W4 candidate物理布局，不使`hardware_approval.json`出现，也不使G1/G4通过。
- 本决定不生成正式W5 JSON/bitstream、execplan、Bank_data或板卡包。

## 后续顺序

以下是本ADR刚采用时的历史顺序；其中模板审计和typed参数合同已完成，W4/G4也已由ADR-009关闭。尚未完成的数值模拟器与板级协议继续属于W6/W8。

1. 先把同一审计扩展到另一个MaxPool模板、AvgPool、Quantize、Add/Dequantize、GEMV/MatMul和sum模板，形成可复用字段规则。
2. 从W3稳定`hw_op_id`和qparams建立ResNet参数化adapter；没有现成Conv模板时，先以SA/stream/buffer正式字段组合出最小候选，并继续保持非正式W5状态。
3. 目标数值模拟器能执行同一配置后，先完成一个MaxPool或Quantize的golden=simulator，再扩大算子覆盖。
4. 收到clean elaboration、物理layout/profile及板级协议后重审G4；只有门通过才生成正式W5实例。
