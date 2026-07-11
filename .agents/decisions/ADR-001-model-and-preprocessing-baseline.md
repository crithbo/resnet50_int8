# ADR-001：ResNet50 INT8模型与预处理暂定基线

状态：暂定接受（candidate）
日期：2026-07-11

## 决策

项目暂定使用ONNX Model Zoo发布的 `resnet50-v1-12-int8.onnx`，以本地下载文件SHA-256
`c234f30975989788b4405f25253275aae247ab6dbdd34aaa69ab0a59ff76f6d0` 作为模型身份。

预处理暂定复现 `CGRA_SIM/testing/resnet-50-int8/golden_model/golden.py`：RGB图像除以255，直接缩放到256×256，中心裁剪224×224，ImageNet mean/std归一化，HWC转CHW并复制为batch=16。

## 依据

- ONNX checker通过；模型IR version 4、opset 12、78个节点、366个initializer。
- 算子数量与旧ResNet计划完全一致：2 Quantize、53 Conv、1 MaxPool、17 Add、1 GlobalAveragePool、1 Flatten、1 MatMul、2 Dequantize。
- 使用仓库已有 `cat.jpg` 和ONNX Runtime 1.27.0 CPU provider已成功得到 `[16,1000]` 输出；batch 16行完全一致。

## 已知差异

ONNX图本身只约束 `[N,3,224,224]` float输入，不编码resize/crop/normalize。旧 `golden.py` 明确加载同名模型，其节点名与当前图匹配，并被旧runner用作checkpoint真值，因此本项目当前有意复现其直接256×256缩放协议。此前“官方必然保持宽高比、与旧脚本冲突”的判断缺少该版本官方评测源码证据，现改为待核验；未来若更换预处理协议，将创建新contract版本并使所有下游产物失效重建。

## 后果

- 正式ONNX、基础预处理和固定测试输入不再阻塞W1/W3。
- 旧ONNX、DDR、golden和原始 `hex_data` 降级为兼容性回归资料。
- 任何模型hash或预处理步骤变化都必须重建golden、relayout、JSON、simulator、execplan和硬件比较结果。
