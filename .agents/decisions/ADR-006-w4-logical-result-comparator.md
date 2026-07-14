# ADR-006：W4通用逻辑结果比较器

状态：软件工具就绪；G4已由ADR-009的物理合同独立通过，但尚无目标simulator/硬件结果，不构成G6/G8数值通过
日期：2026-07-13

## 决定

在等待正式硬件profile、布局与运行协议期间，先实现不依赖具体slice/bank/D布局的通用结果比较器。比较器的输入边界固定为“已完成inverse-relayout、恢复成统一逻辑shape/order的tensor”；物理D文件仍由未来获批layout负责恢复，比较器不猜测硬件布局。

实现位置：

- `resnet50_pipeline/compare/logical.py`：分块加载和逐元素比较核心；
- `schemas/comparison_request.schema.json`：多tensor比较请求；
- `schemas/comparison_report.schema.json`：机器可读报告；
- `resnet50-pipeline compare-results <request.json> --output <report.json>`：CLI入口；
- `tests/test_logical_comparison.py`：bit-exact、浮点容差、缺失、inverse失败、shape/dtype/value首错、拓扑顺序和确定性报告回归。

## 比较语义

1. 默认三方生成`golden↔simulator`、`golden↔hardware`、`simulator↔hardware`三组比较；也可显式配置任意两方或更多来源。
2. BOOL/UINT/INT按逻辑元素bit-exact；FP16/FP32/complex必须逐tensor声明有限且非负的`atol/rtol`，缺少容差会报告`incomplete/tolerance_required`，不会偷偷使用默认值。
3. `missing`、`load_error`、`layout_inverse_failure`、`shape_mismatch`、`dtype_mismatch`和`value_mismatch`分别报告，缺文件或inverse失败不能伪装成数值失败或通过。
4. 首个value mismatch记录逻辑坐标、双方值和来源provenance；未来获批layout可通过`coordinate_explainer`附加slice、bank和物理地址，不需要改比较算法。
5. 多tensor请求按`topology_index`排序，整网报告定位最早失败/不完整tensor，避免对已被上游污染的下游结果逐个猜因。
6. `.npy`使用mmap并按默认1,048,576元素分块比较，避免一次性载入整套W3/W5/W8结果；报告不写入时间戳，相同输入可产生稳定JSON SHA。

## 边界

- 本工作没有读取或重算约951 MB的W3 golden，只用小型临时tensor做回归。
- 本工作没有生成正式W5 JSON、bitstream、execplan、DDR地址或硬件执行包。
- 当前没有目标simulator/hardware逻辑输出，因此只批准“比较工具就绪”，不批准任何真实三方一致结论。
- 比较器本身从未授权W5；W5授权来自后续ADR-009的物理合同与G4 v2闭环。当前W4 inverse layout已经批准，但仍没有目标simulator/hardware结果，因此比较器只保持“工具就绪”，尚无G6/G8或真实三方通过结论。
