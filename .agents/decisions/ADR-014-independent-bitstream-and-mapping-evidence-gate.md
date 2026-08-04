# ADR-014：独立 bitstream 镜像与 mapping 证据门

日期：2026-07-23

状态：accepted；R3 的 encoded-bit、mapping report 和可移植 evidence bundle 已实现。后续 execplan/address/SCA/qparam/layout/provenance 闭环及 R3 退出见 ADR-015；历史产物仍保持原证据等级。本文不授权修改原生 `ndp-sim`、活动 JSON 或现有候选。

## 1. 决策

新增 `resnet50_pipeline/operator_config_artifact_validator.py`，在不 import `ndp-sim` 的前提下独立完成：

1. 从严格 JSON 与 `mapping_review.json` 重建 12 类配置模块的物理槽位、字段编码、presence bit、chunk 和 CONFIG mask；
2. 独立重建 `parsed_bitstream.txt`、64-bit dump 与交换半字顺序后的 128-bit dump；
3. 为每个 JSON 字段建立最终 binary stream 的真实 bit range；
4. 检查 mapping node/resource/connection 集合、资源唯一性、硬连线和相对 selector 的 RTL 可达性；
5. 强制读取独立 mapping evidence，拒绝非零 penalty、fallback、未绑定 mapping review 哈希、错误 encoder commit 和不可移植 cache；
6. 在 JSON 严格校验失败时停止镜像，避免原生 silent default 或位宽 wrap 被“产物一致”掩盖。

只读入口为 `tools/validate_operator_config_artifacts.py`。它需要显式提供 source JSON、原生产物目录和 mapping evidence JSON；只有全部层通过才返回 0。报告 schema 为 `operator-config-artifact-validation-report-v1`。

## 2. 已覆盖的真实编码

镜像覆盖原生固定顺序和聚合位宽：20 DRAM LC、5 ROW LC、5 COL LC、10 LC PE、4 read stream、1 write stream、2 neighbor stream、6 buffer、1 SA、3 GA inport、1 GA outport、16 GA PE。字段转换包含连接相对编号、float32/raw-hex constant、3/2 维 list packing、派生 `idx_size_log/total_size`、address remapping、spatial stride 反序补齐、padding/tailing bounds、buffer lifetime `x-1`、SA row/col bit 和 GA opcode/conversion。

Decode summac 的独立结果为 2252 个未补齐 bit、36 行 64-bit、18 行 128-bit、407 条字段/presence range；三种产物与历史原生文件逐 bit 一致。相同镜像还对以下四个现存目录通过：

- `decode_summac_fp32N_fp32N_graph/config/op0`；
- `deepseek_hwverified_decode_summac_graph/config/op0`；
- `decode_max_fp32N_fp32N_graph/config/op10`；
- `silu_withbaseaddr/config/op0`。

这些结果证明 JSON+mapping 到 bitstream 的独立解释与现存文件一致；单元测试中的 valid mapping evidence 是接口 fixture，不自动把历史目录升级为已保存 penalty provenance。

## 3. 负例

`tests/test_operator_config_artifact_validator.py` 当前 6 项，覆盖：

- 64-bit dump 单 bit 篡改，并定位到字段或 presence owner；
- 删除必填字段触发 native silent-default 前 fail closed；
- 20-bit stride 溢出在 native wrap 前 fail closed；
- 非零 placement penalty 与 fallback 拒绝；
- mapping review 哈希不绑定与非便携 cache 拒绝；
- mapping review 内部资源名自洽、但连接在 RTL 上不可达时拒绝。

新增 `resnet50_pipeline/operator_config_evidence_bundle.py` 与 `tools/generate_operator_config_mapping_evidence.py`。生成器从初始空 cache 的临时 `bitstream` 副本运行原生代码，把 exact `last_mapping_cost`、同次 cache、source/commit/tree manifest、seed/命令、stdout/stderr、source JSON 和四个核心产物复制到项目侧新目录，再调用独立镜像验收；失败或非零 penalty 不发布目录。操作入口 `tools/validate_operator_config_artifacts.py` 只接受完整 `operator-config-mapping-evidence-v2`。

`tests/test_operator_config_evidence_bundle.py` 另有 4 项，覆盖真实 bundle 生成、不触碰活动 native cache、state penalty 篡改、stdout/cache 篡改、禁止覆盖和禁止向 `ndp-sim` 内写 bundle。连同 JSON、legacy 裁决和 artifact 测试，定向执行 34 项通过。

## 4. 新发现的原生行为

1. Decode summac 未声明 `buffer1..4`，但原生 `BufferConfig` 对缺项不会置空：`buffer_nbr_cnt=None→27`、`buffer_life_time=0→-1→4-bit 15`，因此四个槽仍以 presence=1 写入非零配置。镜像已把槽号记录为 `native_implicit_buffer_defaults`；目前只作为待裁决事实，不擅自判为合法默认，也不修改旧候选。
2. 对 Decode summac、FP32 max、Silu 以隔离工具树、初始空 cache、seed=42 重跑，原生均找到零 penalty 映射；但其新 mapping 及 bitstream 哈希与历史目录不同，所以不能用新运行的 penalty 证明旧目录的 mapping 身份。
3. 原生 heuristic wrapper 在首次搜索打印“找到 0 violations”并写 cache 后，仍把返回值解释为 `inf` 而进入 retry；第二次 retry 从同一次隔离运行刚写出的 cache 加载零代价映射。因而“Loaded cached mapping”不能仅靠 stdout 字符串判断为预存宿主 cache，后续证据生成器必须区分 `preexisting` 与 `same-run-generated`。

## 5. 已生成的可移植 bundle

目录根为 `artifacts/operator_config_validation/r3-mapping-evidence/`。三份均为 strict-valid、penalty=0、fallback=false、初始 cache 文件数 0、最终 cache 为 same-run-generated-loaded，且通过 v2 provenance 和独立逐 bit 镜像：

| bundle | 未补齐 bit | range | mapping review SHA-256 | bundle tree SHA-256 |
|---|---:|---:|---|---|
| `decode_summac-seed42-v1` | 2252 | 407 | `014a0c5e34026ce60856985fecfaf6ec9ae0d2f94fb0c9b762ffc46c18370472` | `2dad3f6d35350bde11e230ad08043e1c522a6d8d175f64dcfb850126aa132a78` |
| `decode_max-seed42-v1` | 2108 | 390 | `cac0dc0959e6789b0eae608d0a74338b4fc8629f083b28539752e1882ea8eba5` | `a0f4c15885dcff3ec680dfe067eb86396cbd6c1a8a4710c727ad3ca7407616b2` |
| `silu-seed42-v1` | 3172 | 527 | `6c234eaa3117248316c8f81cc01943db6fef12d8af0392e26c68fd199cabeab0` | `59b1f0428c7d250c49f2d7ca440ec2210a6358f7260c086026817e33139d5d39` |

Decode summac 另做一次不保留的相同 seed/初始空 cache 双跑；四个核心产物、cache tree、penalty=0 和 fallback=false 均一致。该结果证明当前输入的确定性，但临时第二份未作为持久证据，不能替代以后正式的不确定双跑报告。

## 6. 后续闭环结果

真实 execplan 顺序、跨 stage CONFIG、remap 后地址、SCA/qparam/layout/provenance 和持久化双跑已经在 ADR-015 闭合。4 个 mapping-blocked legacy 规范化配置仍只能保留字段等价证据；该限制不阻塞验证器本身退出，但阻止对应 legacy 配置升级身份。不得用 direct-mapping fallback 或未经授权修改 `ndp-sim`；原生 wrapper 的 `inf→retry` 问题继续登记。
