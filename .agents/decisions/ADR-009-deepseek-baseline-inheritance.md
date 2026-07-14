# ADR-009：继承DeepSeek已跑通硬件基线并冻结ResNet50混合28-slice W4合同

日期：2026-07-14
状态：accepted
决策权威标识：`resnet50_int8_project_operator`

## 决策

项目操作者明确确认：本项目使用的正式硬件基线正确，ResNet50应继承学长已经完成的DeepSeek整网调试方法，不再把相同的硬件基线、通用地址格式和通信方法重新作为外部硬件调查任务。

该确认按以下诚实边界记录：

1. 本ADR确认的是“已知可用硬件基线”，不声称本工作区重新取得或运行了clean-elaboration日志。
2. 不伪造elaboration工具、版本、日志URI或SHA-256；旧静态RTL审计在其原始范围内继续有效。
3. `ndp-sim-ref@e299b2804448242d1589b3e58ed7c5a9a5eca09f`是DeepSeek配置、bitstream、execplan与物理方法的继承来源。
4. DeepSeek实际整层使用28位全slice mask；`prefill_gemm_ring_4slice`等算子在七个HIGH-4组上并行，LOW-28只由需要跨组归约/传输的算子使用。因此撤销“全网group4x7或全网global-ring二选一”的批准模型。
5. ResNet50当前七算子族固定为：simple/local、view/local、conv/HIGH-4、maxpool/local、add/local、global-average-pool/local、matmul/HIGH-4。当前没有族需要LOW-28，也不在GAP后切换全网物理布局。
6. W4批准范围只包含目标版本、通信域、物理对象所有权/轴/对齐/tail、93边兼容、qparam身份链和profile成本。INT8 Conv/MatMul数值配置、qparams字段编码、目标数值模拟器和硬件load/dump继续分别属于W5/W6/W8。

## 产物与覆盖关系

- `contracts/deepseek_rtl28_physical_baseline.json`记录可继承的DeepSeek公共物理事实及逐文件SHA-256。
- `contracts/resnet50_rtl28_w4_delta.json`记录ResNet50的七族通信域、layout选择、物理对象差异和W5延期项。
- `contracts/hardware_approval.json`只批准上述W4范围并引用本ADR；它不得被解释成目标数值模拟器、板级runner或三方数值结果已经通过。
- 本ADR覆盖ADR-004中“必须提供clean-elaboration日志才能过G4”的要求，覆盖ADR-007/008中“W4仍等待外部profile/layout批准”的旧状态；它不推翻这些ADR锁定的RTL commit、28-slice拓扑和正式配置来源。

## 验收

只有当引用合同与证据hash全部匹配、七族选中layout都登记为W4批准、93边和成本证据仍匹配当前architecture basis，且G4机器审计全部通过时，才允许结束W4并进入W5。任何引用漂移都必须fail closed。
