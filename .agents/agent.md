# ResNet50 INT8 项目入口与代码地图

最后更新：2026-07-11

本文件是新会话进入本项目时的默认入口，记录最终目标、当前闭环状态、协作规则、仓库基线和代码地图。唯一权威执行计划见 `.agents/plan.md`，已经发生的事实见 `.agents/history.md`。

## 五分钟接手摘要

- **最终验收**：正式 ResNet50 INT8 ONNX→逐节点/硬件原子算子 golden→16-slice relayout→JSON/bitstream→目标 simulator→execplan/Bank_data→RTL/硬件→三方逐算子和整网一致。
- **实际进度**：代码和资料摸底基本完成，但端到端工程完成度仅约 15%~25%；当前没有一个目标 NDP ResNet 算子达到 `golden=simulator=hardware`。
- **三个仓库分工**：`CGRA_SIM` 给软件/QNN语义和旧 ResNet 计划；`ndp-sim-ref` 给目标 JSON、bitstream、relayout/execplan 框架；`NDPFuncModel` 给 Conv 数据通路和旧固定配置。三者尚无共同 manifest 或可运行适配层。
- **当前可直接推进**：W0/G0和小UINT8×INT8 QLinearConv软件golden已经通过；当前进入W2物理partition/layout、地址provenance和正逆round-trip，再依次修复NDPFuncModel的slice/bank寻址、AG transaction、整数PEA、reduction、requant/writeback。
- **当前外部阻塞**：正式模型和固定输入基线已经自行取得；剩余外部阻塞为目标16-slice RTL/ISA版本、正式物理layout、INT8 SA/GA/qparams硬件约定、目标emulator关系、硬件加载与dump协议。
- **禁止误用**：NDPFuncModel 当前 `extracted_*.npy` 和 `verify_pe` psum 不是可信 golden；42个 JSON也不等于 ResNet算子配置已完成；bitstream生成成功不等于数值正确。
- **接手第一条命令**：使用根目录 `.venv\Scripts\python.exe`，不要调用系统 `python`，也不要重新把依赖装进 Codex 公共运行时。

下一步任务和验收条件只以 `.agents/plan.md` 为准；本文件后半部分是查代码时使用的详细地图，不需要接手时从头逐行阅读。

## 文件入口

- `.agents/agent.md`：默认入口。记录项目背景、当前状态、关键路径、工作原则和风险点。
- `.agents/plan.md`：唯一权威实施计划。记录端到端阶段、已有/缺失状态、难度、方案、依赖和验收门槛。
- `.agents/history.md`：历史日志。记录已经做过的操作、发现、产物和阻塞点。
- `.agents/rules/算子配置规则.md`：从模型计算到单算子JSON、bitstream、`model_execplan`和数值验证的工作规则，以及对当前DeepSeek资料的反向审核结论。
- `contracts/`：W1开始建立的版本化事实/候选契约；当前包含模型基线、量化语义和仍待批准的架构字段。
- `.agents/decisions/`：关键选择的ADR；当前ADR-001记录官方模型与旧脚本预处理的暂定采用及失效规则。

推进任务时，先读本文件；真正开始分析或实现前，再读 `plan.md`；需要追溯之前为什么这么做时，再读 `history.md`。

## 协作原则

- Agent 操作者，也就是当前项目使用者，并不熟悉这个项目；前面部分开发也不是操作者完成的。
- 推进计划前，必须先审查当前代码、文档、路径、依赖和已有产物是否与计划一致。
- 如果发现当前计划不合理、信息不足，或者有明显更好的方案，应先说明判断依据并询问操作者是否更改方案；不要明知方案有问题还继续执行。
- 局部实现细节可以在不改变总体路线的前提下直接做更稳妥的调整，但完成后要说明调整内容。
- 每完成一个明确子任务后，需要向操作者说明：完成了什么、如何验证、还剩什么风险，并同步更新 `plan.md` 和 `history.md`。
- 不要回退或覆盖已有未提交修改，除非操作者明确要求。
- 根仓库从首版本开始，每个经过验证的有效小步骤做原子Git提交；W1/W2等完整工作包通过验收门后形成里程碑并推送GitHub。大模型、运行产物、trace和其他可再生大文件不得进入普通Git历史。
- 不自行删除、压缩或改写既有提交；如果历史明显占用空间，必须先报告拟清理范围、远端影响和恢复方案，得到操作者确认后才能执行。

## 最终目标

> 从正式 ResNet50 INT8 模型生成每个 ONNX 节点和硬件原子算子的 golden input/output；把 raw tensor 做 partition、padding、relayout、packing 和 remapping，生成硬件测试数据；完成全部单算子 JSON/bitstream；用目标 JSON 模拟器得到结果；把网络 lowering 成目标硬件 execplan；运行 RTL/硬件；最终使 golden、simulator、hardware 在逐算子和整网层面一致。

这不是“JSON 编写任务加几个后续可选项”，而是一条统一的端到端验证链。Golden、数据变换、JSON、模拟器、execplan、硬件 runner 和三方比较全部属于明确目标，不再列为暂缓事项。

需要特别注意：

- “每个算子”包含 ONNX 模型节点和 lowering 后的硬件原子算子；一个 QLinearConv 可能对应多个 K-tile 配置/执行实例。
- 目标硬件已由操作者确认是 16 个 slice / PE 阵列；仓库中的 28-slice DeepSeek 约定是待移除的软件假设。
- `CGRA_SIM` 的旧 `.cu` 功能模拟链和 `ndp-sim-ref` 的 JSON/bitstream 链彼此独立；前者是语义参考，不能代替目标 JSON 模拟器。
- bitstream 生成成功只证明编码/placement 通过，不证明数值正确；单算子至少达到 golden=simulator，最终必须达到三方一致。
- 详细阶段、难度和验收门槛以 `.agents/plan.md` 为准；`.agents/rules/算子配置规则.md` 约束每个配置和跨阶段产物怎样推导与验收。

## 项目流程

本项目本质是硬件开发和验证项目。权威流程是：

1. 固定 ONNX、输入、预处理、软件版本和模型 hash。
2. 建立 ONNX 节点→硬件原子算子 lowering manifest。
3. 生成每个逻辑/原子算子的 raw golden input/output。
4. 对 tensor 做 16-slice partition、relayout、packing、remapping，并保留 inverse 变换。
5. 生成每个原子算子的 JSON、bitstream 和参数化元数据。
6. 用目标 JSON/bitstream emulator 执行并导出 D。
7. 从 manifest 自动生成网络 execplan、cfg_pkg、Bank_data 和 emulator bundle。
8. 把同一份包加载到 RTL/硬件并导出结果。
9. inverse-relayout 后做 golden↔simulator↔hardware 三方比较。
10. 从单算子扩到 conv0、残差块、head 和整网回归。

三方结果必须共享同一 manifest、输入 hash、qparams、layout 和配置版本；否则“相等”没有可审计意义。

## 根集成骨架说明与实施规则【W0/G0已完成】

三个参考仓库职责不同，后续端到端代码统一放在工作区根目录的独立集成层，不继续把流程散写进任一参考仓库：

```text
resnet50_int8/
  resnet50_pipeline/     # 端到端Python集成包
  tests/                 # unit/integration/regression
  schemas/               # manifest、contract、comparison schema
  contracts/             # 机器可读模型/量化/架构/backend契约
  fixtures/              # 可入库的小型确定测试数据
  artifacts/             # 忽略的运行产物和大模型
  .agents/
    agent.md              # 接手入口、代码地图、骨架规则
    plan.md               # 唯一执行计划和阶段状态
    history.md            # 精简后的关键事实日志
    rules/                # 详细推导与验收规则
    decisions/            # ADR和外部批准结论
  CGRA_SIM/               # 软件/QNN语义与旧ResNet参考
  ndp-sim-ref/            # 目标JSON/bitstream/execplan参考
  NDPFuncModel/           # Conv功能模型和旧配置参考
```

计划中的 `resnet50_pipeline/` 模块边界：

- `manifest/`：Run、Model、Node、HwOp、Tensor、Layout、Config、Execution和Result记录。
- `model/`、`golden/`：ONNX解析、lowering、ORT全节点输出和subop软件真值。
- `layout/`：各算子的forward/inverse/explain/validate插件。
- `config/`：模板选择、目标JSON字段patch、mapping review和bitstream校验。
- `simulator/`、`hardware/`：统一backend接口，不把外部程序细节泄漏到核心层。
- `execplan/`：从manifest构建地址、配置、Bank_data和指令流。
- `compare/`：physical/logical恢复、三方比较和首错provenance。
- `artifacts/`、`memory/`：原子产物、hash、缓存失效、地址生命周期和重叠检查。

实施时必须遵守：

1. **文档集中**：根集成层的说明、规则和ADR全部放 `.agents/`；requirements是环境清单、contracts是机器输入，继续留在根目录。三个参考仓库自己的README不迁移。发现疑似过时文档先向操作者列出理由，未经确认不删除。
2. **核心解耦**：核心包通过adapter访问三个仓库，禁止依靠全局 `sys.path`、个人环境变量或仓库package的全量eager import。
3. **manifest唯一真值**：节点、tensor、hw_op、layout、配置、地址和结果只通过稳定ID关联，禁止依赖目录排序、名字前缀或全局计数器。
4. **contract分级**：模型、量化、架构和backend字段标记candidate/approved；candidate可做软件实验，不能宣布硬件配置验收通过。
5. **状态不可覆盖**：每个阶段、对象和backend记录不可变attempt；重跑产生新attempt，run状态不能掩盖局部失败或blocked。
6. **产物可恢复**：cache key包含输入、contract、代码、三仓commit和backend版本；任何变化使下游失效。产物校验hash后原子发布。
7. **正逆布局成对**：每个relayout同时提供forward、inverse、坐标解释和验证；round-trip未bit-exact不得进入simulator。
8. **backend先探测**：adapter必须声明支持的op、dtype、slice、JSON/bitstream版本和dump能力；不支持时在执行前失败。
9. **逐门推进**：W0~W9是执行顺序、G0~G9是验收门；无subop golden不验JSON，无simulator通过不进硬件，单算子未三方一致不扩整网。
10. **禁止伪证据**：当前NDP `.npy`/psum trace、旧ADD伪代码、FP16 SA JSON和bitstream生成成功都不能替代数值验收。

`resnet50_pipeline/`、CLI、manifest、contract/backend、artifact、cache/resume、schema、mock fixture和测试已经建立；W0共11项测试通过并达到G0。当前业务实现从W2小Conv物理layout和地址provenance继续。

## 本地仓库状态

主仓库：

```text
C:\Users\15383\Desktop\Codex\project\resnet50_int8\CGRA_SIM
```

当前已知提交：

```text
53c41e0 Ignore .bin files in data_bin directory. Complete the tile-wise computation for the PE array.
```

主仓库中已有未提交修改，属于进入当前任务前已经存在的状态，不要随意回退：

```text
cgra_python/arch/__init__.py
cgra_python/arch/arch_base.py
cgra_python/util/extract_blocks.py
env.sh
```

`ndp-sim` 参考仓库：

```text
C:\Users\15383\Desktop\Codex\project\resnet50_int8\ndp-sim-ref
```

当前已知提交：

```text
e299b2804448242d1589b3e58ed7c5a9a5eca09f
```

状态说明：

- `ndp-sim-ref` 已尽量拉成完整工作树，当前工作树干净。
- 该副本仍是 shallow / partial clone，历史不完整，但代码和配置分析所需文件已经展开。
- 旧的半成品 `ndp-sim/` 目录已经删除，后续使用 `ndp-sim-ref/`。

Conv 功能模型仓库：

```text
C:\Users\15383\Desktop\Codex\project\resnet50_int8\NDPFuncModel
```

当前分支和提交：

```text
conv_func
789d121327d8e855d33f16c2103a6422a521fa25
```

状态说明：

- 从 `runoobb/NDPFuncModel` 的 `conv_func` 分支单分支克隆；当前本地分支在上游 `89d1655` 基础上增加寻址修复提交 `789d121`，工作树干净、相对origin ahead 1。
- 它是以 Python 硬编码循环和数据通路的 Conv 功能模型，不是 `ndp-sim-ref/jsons` 或 bitstream 的解释器。
- 仓库按 Git 记录了 `conv_config` gitlink，但没有 `.gitmodules` 和 URL；该目录无法还原。`graph/` 也只有 `.pyc`，没有对应 `.py` 源码。
- `hex_data/` 被忽略且未随仓库提供，因此 `main_CONV_N2N.py` 当前不能从干净 clone 直接完整运行。

## 本地 Python 环境与已验证入口

项目使用根目录持久化虚拟环境：

```text
.venv\Scripts\python.exe
```

- 基础约束记录在 `requirements-resnet50.txt`，2026-07-11 的精确解析版本记录在 `requirements-resnet50.lock.txt`；`.venv/` 已由根目录 `.gitignore` 忽略。
- 环境为 CPython 3.12.13，直接依赖包含 NumPy 1.26.4、ONNX 1.22.0、ONNX Runtime 1.27.0、PyTorch 2.13.0+cpu、OpenCV、Pillow、Matplotlib、OpenPyXL 和 tqdm；`pip check` 已通过。
- PyTorch不能继续视为可选：`CGRA_SIM/cgra_python/__init__.py` 会传递导入 `op_lib`，其中 MaxPool 直接导入 torch。
- `ndp-sim-ref/model_execplan/main.py --help` 已成功，证明 execplan Python 前端可启动。
- `NDPFuncModel/main_CONV_N2N.py` 已在 `artifacts/smoke/NDPFuncModel` 隔离 worktree 中运行到 `DRAM.init_from_file()`，当前停在缺少 `./hex_data`，不再缺 Python 包。
- `CGRA_SIM/.../golden.py` 在设置仓库根为 `PYTHONPATH` 后，当前首先停在 `cgra_python/layout/layout_buffer.py:201` 的既有 `SyntaxError`；官方模型、固定图片和ORT最终输出基线已经准备完成，修复后可直接进入全节点golden改造。
- `.venv` 当前约 962 MB，主要体积来自 CPU PyTorch；运行产物统一放 `artifacts/`，不要覆盖三个仓库内的跟踪 trace。

重建环境：

```powershell
& '.\.venv\Scripts\python.exe' -m pip install -r requirements-resnet50.lock.txt
& '.\.venv\Scripts\python.exe' -m pip check
```

## ndp-sim 关键内容

`uSFrances/ndp-sim` 是 ResNet50 和先前已完成 DeepSeek 两个模型共用的工具链。当前任务应主要在这个工具链里学习和补充 ResNet50 算子配置。

重要目录：

```text
ndp-sim-ref/jsons/
ndp-sim-ref/bitstream/
ndp-sim-ref/model_execplan/
ndp-sim-ref/generate_python_golden/
ndp-sim-ref/address_remapping/
```

目录职责：

- `jsons/`：当前有 42 个单算子 JSON 配置模板。与 ResNet50 可能相关的模板包括 maxpool、avgpool、quant、add_dequant，也有大量 DeepSeek / LLM 的 gemm、gemv、summac、softmax、silu 等模板。
- `bitstream/`：把单算子 JSON 生成 bitstream。入口是 `bitstream/main.py`。
- `model_execplan/`：把多算子输入 JSON 变成 execution plan，同时做地址规划、patch 单算子 JSON、重新生成 bitstream。`model_execplan/README.md` 是优先阅读入口。
- `model_execplan/config/register_map_with_groups1.csv`：解释算子 JSON 中每个配置项对应的硬件含义、端口、默认值，是理解 JSON 字段的核心表。
- `model_execplan/config/operator_base_info.json`：记录每个 op type 的基础信息。新增 op type 时要检查是否也需要补这里。
- `generate_python_golden/`：DeepSeek 已有 golden 数据和单算子 relayout 流程，可作为 ResNet50 参考，但不能直接假设适配。
- `address_remapping/`：生成和分析 remapping 信息，后续处理 tensor layout、bank、地址映射时需要参考。

两层 JSON 必须区分：

- `jsons/<op_type>.json`：单算子硬件配置模板。
- `model_execplan/main.py` 的输入 JSON：网络或子图级描述，引用 `operators[*].type` 对应的单算子模板。

常用命令形态：

```text
python bitstream/main.py --visualize-placement -c jsons/<op_type>.json -o <output_dir> -q
python model_execplan/main.py <input_json>
```

`model_execplan` 主要输出包括：

```text
install/execplan.txt
instructions_explained.txt
sca_cfg.json
install/cfg_pkg/
patched jsons/
per-op config/
optional Bank_data/
optional emulator_<name>/
```

## CGRA_SIM 关键内容

ResNet50 INT8 相关入口：

```text
CGRA_SIM/testing/resnet-50-int8/
```

重要文件和职责：

- `testing/resnet-50-int8/golden_model/golden.py`（[GitHub 上游](https://github.com/KingICCrab/CGRA_SIM/blob/main/testing/resnet-50-int8/golden_model/golden.py)）：现有 ResNet50 ONNXRuntime golden 实现入口；包含 ImageNet 预处理、batch 复制到 16、向图中追加检查输出、`InferenceSession` 执行及 `.npy/.log` 导出。它是后续全节点 golden 的改造基线，目前还不是完整逐算子 input/output dump。
- `testing/resnet-50-int8/gen_execu_plan_ver1.py`：手写生成 ResNet50 INT8 的 `.cu` 风格 execution plan。它不是 ndp-sim 单算子 JSON 生成器。
- `testing/resnet-50-int8/run.py`：跑 Python functional simulator，并在若干硬编码 checkpoint 上和 golden 对比。
- `cgra_python/execution_plan/get_params.py`、`gen_ddr.py`：从 ONNX initializer 提取参数，做预处理并生成 DDR 数据。
- `cgra_python/execution_plan/register_preprocessor.py`：注册 QNN 参数预处理器，目前包括 `QLinearConv`、`QLinearMatMul`、`QLinearGlobalAveragePool`、`DequantizeLinear`。
- `cgra_python/op_lib/qnn/`：Python functional simulator 使用的 QNN 软件算子实现，包括 quantize、dequantize、conv、add、average pool、matmul 等。
- `cgra_python/simulator/func_sim.py`：Python functional simulator 主入口。
- `cgra_python/layout/`：layout、partition、im2col、buffer mapping 等实验性工具，后续做 tensor relayout 时可参考，但需要先审查硬编码路径和输入输出约定。
- `scripts/func_validator.py`：更通用的 functional simulator 验证框架雏形，仍有多个 TODO。

`CGRA_SIM` 提供 ResNet/QNN 软件语义、旧调度和旧功能模拟参考；`ndp-sim-ref` 提供目标 JSON、bitstream、relayout 组织和 execplan 框架。两者都是最终目标的输入，但当前没有共同 manifest 或适配层，不能把旧 `.cu` simulator 的结果当成目标 JSON simulator 结果。

### 旧 ResNet50 INT8 预处理脚本的定位

- `golden_model/golden.py` 和 `image_prepro/input.py` 都写死加载 `resnet50-v1-12-int8.onnx`，其 `resnetv17_*` 检查节点与当前正式模型图匹配；相同的直接256×256缩放还用于 `cgra_python/execution_plan/gen_input.py`。它明确服务于旧 `resnet50-v1-12-int8` 功能模拟链，不是与当前模型无关的临时样例。
- 旧仓库没有提交当时的ONNX或hash，所以只能确认文件名、输入和图节点结构兼容，不能证明旧文件与当前SHA-256基线逐字节相同。
- 该实现含个人绝对路径、固定 `cat.jpg`、手写checkpoint和固定batch=16，属于实验性golden/checkpoint生成脚本而非通用发布库；但其结果被 `run.py` 用作旧功能模拟器真值，因此是旧工程事实上的复现协议。
- ONNX只约束float输入 `[N,3,224,224]`，不包含Resize/Crop/Normalize。直接缩放和保持宽高比都不是模型数学意义上的非法操作，正确性取决于评测协议。当前为复现旧CGRA链采用直接缩放，并锁定预处理代码和input tensor hash。
- 不再把“官方Model Zoo必然保持宽高比、因此与旧脚本冲突”当作已证实事实；官方精度复现须再核对该版本评测源码中的resize、插值、解码和舍入。正方形 `cat.jpg` 在相同OpenCV插值下两种几何策略等价，非正方形输入变更协议则必须重建全部下游产物。

## NDPFuncModel Conv 功能模型关键内容

`NDPFuncModel/main_CONV_N2N.py` 是本分支 Conv 入口，当前固定模拟 4 slice、4 bank、6144 row、64 col、每 subword 16 byte；每个 slice 使用 8×8 `SpecialPEA`，意图通过 activation 邻接环完成跨 slice reduction。固定示例声明的逻辑对象是 activation `[1,64,66,4]`、weight `[256,64,3,3]`、bias `[256]`，意图让 activation 按 C 分到 4 slice、weight/output 按 K 分到 4 slice；但当前物理地址实现没有实现这一意图，四个逻辑 slice 的 activation 实际都读自物理 slice0。

关键目录和职责：

- `component/DRAM.py`：slice/bank/row/col/subword 存储及物理地址换算，只从每 slice 的 bank0 文本载入字节。
- `component/IGA.py`：LC 的 `[start,end)` 迭代，以及 `last`/`last_index` 解析；与已确认的“LC 控制循环、last_index 表示循环层级”一致。
- `component/RDAG.py`、`WRAG.py`、`BufAG.py`：DRAM 读写和 Buffer 地址生成、16-byte valid/padding/branch mask。
- `component/Buffer.py`：数据、last/last_index/branch tag、列反序存取和 tag 压缩。
- `component/SpecialPEA.py`：8×8 PEA、每 PE dot、int32 psum、邻接/分支处理和输出 buffer packing。
- `component/DataTransfer.py`：DRAM→AG→Buffer→PE、PE 执行、邻接传输和候选写回的主要 trace 链；Conv AG 参数仍由 Python 函数硬编码，不从 JSON 读取。
- `component/ActiUnit.py`：候选 requant 单元，但 Conv 主入口没有调用它，且 `quantize()` 引用了未实现的 `sse2_round_to_int()`。
- `main_GEMM*.py`、`main_GEMV.py`、`generate_gemm_fp16.py`：GEMM/GEMV 开发与验证参考，不是 ResNet Conv 主线。
- `verify_*.py`、`torch_verify*.py`、`test_compare.py`、`track_data_path.py`：trace/统计验证工具；当前没有对 QLinearConv 做坐标级 bit-exact 全输出比较。
- `config/`：旧配置位拼接工具，与 `ndp-sim-ref` 同源的历史参考；没有接入 Conv 主入口。其中 `config_generator_ver2.py` 是固定 Conv 配置，`config_nse.py` 是增加邻居流和重复 LC 链的版本，`nse_cnt_size=15` 是当前仓库里最直接的 16-slice/ring 配置证据。它们属于旧寄存器架构，且输出路径硬编码，不能不经版本映射直接复制成目标 JSON。
- `kernel/add_config_MN_N.json`、`output/add_config_MN_N_pseudocode.py`：ADD JSON 与生成伪代码的完整工作样例，不是 Conv 配置。`graph/` 虽只跟踪 CPython 3.12 `.pyc`，但已恢复其职责：加载 JSON 为 LC/PE/AG 依赖图、拓扑排序、生成嵌套循环伪代码和地址队列；因此是可恢复的配置前端，不再视为完全未知文件。
- `verify_pe/` 及各 dump 目录：大量生成 trace/日志，属于验证产物，不是配置规则真值。

该仓库补齐的是“Conv 数据通路怎样走”的重要参考：DRAM 几何、地址/掩码、Buffer 行列、8×8 PEA、4-slice ring 和 psum provenance 都能用于设计 ResNet Conv relayout 与配置适配。它尚未补齐目标数值闭环，已确认的直接阻塞包括：

1. `reduc_state = r*s*cc_shared` 不可能等于 `end` 乘积减一，导致 `flush_output` 永不成立。
2. `run_buffer_writeback_to_dram()` 只记录“将要写回”的日志，实际 `dram.stream_write()` 被注释。
3. INT8 Conv 输出仍走 FP16 packing，未执行 per-channel requant/zero-point/saturation；主入口创建的 `ActivationUnit` 没有被使用。
4. PEA 当前按 signed A × unsigned B 计算，而 ResNet 软件参考是 uint8 activation × int8 weight；需要确认端口交换还是实现错误。
5. 主示例固定 4 slice，不等于已确认的目标 16 slice，也没有 JSON/bitstream、qparams 或命令行参数化接口。
6. `SpecialPEA.PE.execute()` 虽在模块顶部为无 `np.float128` 的平台定义了 `FLOAT_ACCUM` fallback，函数内部仍直接调用 `np.float128`；在当前 Windows NumPy 环境中，最小 INT8 PE 执行会立刻报错。
7. 上游 `89d1655` 的 `DRAM.per_slice` 少乘 `bank_num`；本地 `789d121` 已修复并用4-slice独立写读验证。旧 `extracted_bias.npy` 和旧trace仍由错误版本生成，继续禁止作为真值。
8. 上游 `run_dram_to_ag()` 只把 `slice_id` 写进日志名；本地 `789d121` 已把完整slice byte span加入AG tensor base，slice0～3数据与物理provenance测试通过。
9. 上游RDAG/WRAG多transaction路径丢弃strided transaction地址；本地 `789d121` 已分离逻辑counter与物理transaction offset，读写AG的跨16-byte边界地址序列对称通过。
10. `verify_pe` 的 psum 文件在卷积 reduction 前写出，实际只是 bias preload 快照；`extracted_act/weight/bias.npy` 又由缺陷链路生成，均不得作为 Conv golden 或回归真值。

因此它应标为【Conv 功能参考/待修复集成】，不能标为“目标 JSON emulator 已有”。推荐在统一 manifest 后增加一个 adapter，把目标 Conv JSON/bitstream 字段转换成该模型的 LC/AG/Buffer/PE 参数；先修复写回和量化，再用 conv0 做 golden=Conv functional model，随后才讨论其能否升级为目标 JSON/bitstream emulator。

## 当前闭环状态

- **模型和 golden——正式模型基线已有/全节点dump待做**：官方Model Zoo模型已按SHA-256暂定为正式模型，固定 `cat.jpg`、batch=16输入和ORT最终输出均已hash锁定；`golden_model/golden.py` 仍只列35个检查名、30个唯一节点，全节点input/output与硬件子步骤golden需补全。
- **lowering 和统一 manifest——仓库中没有**：旧计划精确还原为 77 个模型级原语，但依赖 328 个有序字典项；没有 ONNX node→硬件原子 op→JSON→execplan→结果的一对多映射。
- **数据变换——Conv候选已开始/其余需完成**：W2已实现1/4-slice `w2_ndp_ring_candidate_v1`，覆盖DRAM五维地址、activation-C和weight/output-K分片、bias/qparams、C/K tail、16-byte对齐、逐字节provenance及正逆round-trip；它尚未由NDP functional model验证，也不是硬件批准layout。ResNet 16-slice Conv以及Quantize、MaxPool、Add、AvgPool、MatMul/dense、Dequantize、Flatten/View仍需继续实现。
- **单算子配置——部分已有**：42 个静态 JSON 中只有 MaxPool、sum 型 AvgPool、固定样例 quant、fp32 输出 add-dequant 可局部参考；6 个 SA JSON 全是 FP16、bias=0；没有核心 INT8 Conv/MatMul。
- **目标数值模拟——DRAM ingress已修复/PEA数值链仍没有闭环**：本地 `NDPFuncModel@789d121` 已能由独立adapter消费W2 physical bundle，并逐region读回相同hash；slice跨度、slice AG读取和RDAG/WRAG transaction已回归。它仍不消费 `ndp-sim-ref` JSON/bitstream，A/B符号、整数PEA、reduction、requant、真实writeback和16-slice尚未闭环，因此仍不能称为可信Conv数值模拟器。
- **execplan——框架已有/ResNet 适配没有**：可规划地址、重生成 bitstream、输出指令和 Bank_data，但 schema 无 numeric attributes，仍硬编码 28 slice，bitstream 失败后部分路径继续。
- **RTL/硬件——外部阻塞**：没有完整 runner/testbench、加载/启动/完成/dump 协议或逐算子 checkpoint 入口。
- **三方比较——仓库中没有通用实现**：旧 runner 只有 21 个硬编码 checkpoint，另一个工具只比较两个 128-bit 物理文件；没有 inverse-relayout 后的三方比较。

## 当前最高优先级

严格按 `.agents/plan.md` 的 W0→W9 工作包和 G0→G9 验收门推进。W0/G0已经完成，W1外部规格继续并行，当前执行W2小Conv物理layout和地址provenance。relayout实现本身不再等待外部提供现成脚本。

优先向学长或硬件侧确认：目标16-slice RTL/ISA/register-map版本、正式物理layout、最小INT8 SA+bias+requant硬件配置、量化参数传递协议、NDPFuncModel/官方emulator关系，以及硬件加载和dump接口。旧ONNX、旧产物、原 `hex_data` 和 `conv_config` 来源已降级为兼容性资料，不再阻塞软件推进。

配置字段层的Q1~Q4详细背景仍见 `.agents/rules/算子配置规则.md` 第14.3节；端到端外部资料清单以 `plan.md`“当前最高优先级请求”为准。

## 常见产物缺失

`.gitignore` 会忽略大量运行产物，例如：

```text
*.npz
*.dat
*.npy
*.txt
**/*.cu
**/*.onnx
**/*.pkl
**/*.bin
cgra_python/execution_plan/tensor_dict.json
```

如果新会话找不到 ONNX、golden `.npy`、`ddr.dat`、`tensor_dict.json`、`execu_plan_ver1.cu` 等产物，不要直接判断脚本坏了；先确认这些产物是否本来就未纳入仓库。

## 逐目录复审的标记和覆盖口径

下面是对三个嵌套仓库的完整代码地图，使用以下标记：

- **主线**：端到端目标会直接使用，包括 golden、manifest/lowering、数据变换、JSON、模拟器、execplan、硬件和比较。
- **语义参考**：帮助理解算法、量化、tile 或 layout，但不会直接生成目标 JSON。
- **验证**：用于 golden、功能模拟、结果对比。
- **旧版参考**：历史编码器或参数镜像；能提供线索，不能和当前版本直接混用。
- **实验/骨架**：存在未完成函数、硬编码样例或缺少稳定入口。
- **产物**：生成数据、图片、缓存或报告，不是规则真值。
- **版本冲突**：代码内部存在多套硬件参数，必须等待权威版本或谨慎选用。

“每部分代码”按功能模块和入口文件标注；第三方拷贝代码、自动生成 parser 表、重复备份和批量输出按目录分组，不把每个文件误写成独立业务模块。

## 总体调用关系

目标主线：

```text
正式 ResNet ONNX / 输入 / initializer
  -> 统一 lowering + tensor/op manifest（待实现）
  -> raw golden + 硬件子步骤 golden（部分参考已有，待完整实现）
  -> 16-slice partition/relayout/packing/remapping（待实现）
  -> ndp-sim-ref/jsons + bitstream（框架已有，ResNet INT8 配置待实现）
  -> 目标 JSON/bitstream emulator（仓库内缺失）
  -> model_execplan + cfg_pkg + Bank_data（框架已有，ResNet/16-slice 待适配）
  -> RTL/硬件 runner（仓库内缺失）
  -> inverse-relayout + 三方比较（待实现）
```

旧 ResNet 验证链：

```text
testing/resnet-50-int8/gen_execu_plan_ver1.py
  -> 打印旧 .cu 风格 execution plan
  -> simulator/driver 解析和预处理
  -> simulator/func_sim.py 执行 DMA + 软件算子
  -> testing/resnet-50-int8/run.py 对比 ONNXRuntime golden
```

第二条链说明 ResNet 的算法拆分、tile 和量化语义，但不生成 `ndp-sim/jsons`，也不解释目标 JSON/bitstream；它只作为软件参考和旧结果线索。

另外还有三条独立参考链：

- `CGRA_SIM/cgra_python/slice/`：TOML/XML 单 slice 数据流模拟。
- `CGRA_SIM/cgra_python/simulator/engine + dram/` 与 `CGRA_SIM/timing/`：两套尚未统一的时序/DRAM 模拟框架。
- `ndp-sim-ref/address_remapping/`：layout 位排列、bank/interleave、地址 remapping 和性能分析。

这些参考链仍没有形成统一、可直接运行的 ResNet 端到端闭环；缺口和实施顺序以 `plan.md` 为准。

## `ndp-sim-ref` 详细代码地图

### `jsons/`：单算子硬件配置模板【主线】

现有 42 个 JSON，可按功能分为：

- ResNet 候选：`maxpool_config_*`、`avgpool_config_2048_7_7`、`quant_from_buffer_int32MN_uint8MN`、`add_dequant_uint8CWH_uint8CWH_fp32CWH`、`sum_config_32_32`。
- GEMM/GEMV：`prefill_gemm_*`、`gemv_config_*`、`decode_gemv_*`。
- 点运算：`prefill_add_*`、`prefill_mul_*`、`decode_add_*`、`decode_mul_*`。
- reduce/跨 slice：`prefill_remote_sum_*`、`prefill_remote_max_*`、`decode_remote_sum_*`、`decode_max_*`。
- 累加/SFU：`prefill_summac_*`、`prefill_mac_*`、`prefill_silu_*`、`prefill_sum_rec_*`、`decode_summac_*`、`decode_mac_SFU_*`、`decode_sum_rec_*`。

这些是静态硬件数据流模板，不是可对任意 shape 自动参数化的算子实现。全量结构审计确认：只有 6 个模板使用 SA，而且全部是 fp16、`bias_enable=0`；INT8/UINT8 相关 GA 只覆盖 max、sum、固定常量的 int32→uint8 quant 和双路 uint8→fp32 add-dequant。累计 38/42 个模板曾生成完整 bitstream；4 个 placement 复测仍失败：

- `prefill_gemm_local.json`
- `prefill_gemm_local_qkt.json`
- `prefill_gemm_ring_4slice.json`
- `maxpool_config_16_112_112_stride2_padding1.json`

### `bitstream/`：JSON 到配置位流【主线】

- `main.py`：CLI 入口；读取 JSON，初始化配置模块和映射器，执行 placement，输出 mapping review、解析位流、64/128-bit 二进制和可选图。`--compare` 仍显示在接口中，但实现明确抛 `NotImplementedError`。
- `parse.py`：把 JSON 字段实例化为 loop、PE、stream、buffer、GA/SA 等配置对象并编码。当前资源数采用 20 DRAM-LC、5 ROW-LC、5 COL-LC、10 LC-PE、4 Read-MSE 等定义。
- `mapper.py`：建立逻辑节点图、资源池和连接约束；支持直接映射和启发式 placement。抽象约束基类的 `NotImplemented` 是接口，实际约束由子类实现。
- `index.py`：定义逻辑 `NodeIndex`、连接关系和逻辑到物理资源的解析。TODO 表明节点创建接口曾处在迁移过程。
- `bit.py`：固定宽度值和拼接/切片运算；超宽值按位宽截断，所以“成功输出 bitstream”不能替代范围审查。
- `visualize.py`：生成 placement/连接可视化。
- `config/base.py`：配置对象共同接口、chunk/bit 拼接和映射辅助。
- `config/loop.py`：DRAM/ROW/COL/LC-PE 循环字段编码。
- `config/stream.py`：read/write MSE、transaction、stride、padding、remapping 编码。
- `config/buffer.py`：buffer loop、地址、ping-pong、full/keep 编码。
- `config/general.py`：GA 输入、输出、PE 和通用运算配置。
- `config/special.py`：SA/SFU 等特殊阵列配置。
- `config/neighbor.py`：slice/节点间邻接通信配置。
- `config/mapper.py`：配置模块使用的映射节点和约束辅助。
- 两级 `__init__.py`：包导出。

### `model_execplan/`：多算子 execution plan【后续主线】

顶层：

- `README.md`：输入 JSON、地址规划、输出目录和 CLI 的主要说明入口。
- `main.py`：调用 pipeline，生成 install、指令、配置包、可选 bank data/emulator。
- `gen_layer0_oplist.py`：拼 DeepSeek layer0 复合模板并改写 source。别名表引用 24 个模板，但 `op_json/` 仅有 3 个，默认完整 layer0 会缺 21 个文件。
- `split_linearized_128bit_banks.py`：把线性 128-bit 数据记录轮转拆到多个 bank。
- 顶层 `execution_plan_generator/`：兼容旧 import 的 shim；实现位于 `src/execution_plan_generator/`。

`src/execution_plan_generator/`：

- `pipeline.py`：总编排。加载网络 JSON/模板，先规划地址，逐 op patch JSON 并调用 bitstream，再按实际 config 长度重规划，最后生成指令。bitstream 子进程失败时部分路径只打印并 `continue`，不是严格 fail-fast。
- `models.py`：Tensor、Operator、AddressPlan、Template、Artifact 数据模型。shape 规范为 3 维，enabled slice 硬编码遍历 28 位；Tensor/Operator 没有数值 attributes/constants 字段。
- `json_loader.py`：解析网络级 JSON、受限 shape 表达式、source、dtype、remapping、special type、bank interleave 和 mask。顶层 `params` 只保留整数供 shape 表达式使用，浮点量化参数会被忽略。
- `template_manager.py`：读取 op base info、寄存器映射和初始 bitstream，识别 config/SFU 长度并生成模板。缺元数据时存在容错默认值，可能把资料缺失推迟成后续告警。
- `address_planner.py`：为外部 tensor、生产者输出、config 和 SFU 数据分配 slice/bank/row/col 地址，并让消费者引用生产者地址。硬编码 28 slave、4 bank、8192 row、64 col；8192 row 与其他版本 6144 冲突。
- `register_mapping.py`：读取两张 CSV，把逻辑字段拆成寄存器片段并生成 masked/partial write。代码不完全相信 CSV 的位范围，而按行序和位宽重建，说明表格与实现曾漂移。
- `config_stream_decoder.py`：从 bitstream/template chunk 解码寄存器现值，处理 enable 和 padding。
- `control_registers.py`：按 op type/shape 计算 loop、stream、buffer、GA patch。当前约 37 个 handler；大量 docstring 仍写 Placeholder，但不少会返回部分更新，表示尚未完全定稿，不等于空函数。没有覆盖 ResNet MaxPool/AvgPool/Conv 的完整 handler；quant/add-dequant handler 只改循环和 stride，不 patch 模板中的 scale/zp 常量。
- `slice_routing.py`：把 `special_type` 解析为 source slice，当前是 rope/xor/slice0/slice4 等 LLM 规则。
- `instruction_generator.py`：编码 ClockEnable、LoadConfig、WriteReg、StartComp；先全局开时钟，再逐 op 装配置、写寄存器、启动，并记录 unresolved 字段。
- `bank_data_exporter.py`：读取 manifest 的 tensor matrix 文件，支持 binary、hex、64/128-bit 文本，按地址放入 slice/bank 镜像并导出。
- `output_writer.py`：写 execution plan、解释文件、SCA/config 包、install manifest、patched/emulator JSON 和 DRAM 数据；也把地址、remapping、control update 反写到算子 JSON。
- `errors.py`、`__init__.py`：异常类型与包导出。

配置/数据：

- `config/register_map_with_groups1.csv`：JSON 字段到寄存器、位宽、端口和默认值的核心索引，但与 encoder/参数镜像存在版本冲突。
- `config/config_output.csv`：寄存器输出/分组映射辅助表。
- `config/operator_base_info.json`：27 个 op type 的基础元数据；42 个静态 JSON 中有 15 个不在其中。
- `config/SFU_Coeff/*.txt`：Exp、GELU、Reciprocal、Reciprocal sqrt、ReLU、Sigmoid、SiLU、sqrt、tanh 系数。
- `op_json/{rmsnorm,rope,softmax}.json`：仅有的 3 个复合算子/子图模板。
- `output/compare_matrix_outputs.py`：按 op/slice 对 A/B/D 的两个 128-bit 文本目录做逐行精确比较并写 JSON 报告；不理解 dtype、逻辑坐标或 inverse-relayout，不能替代三方比较器。
- `output/generate_sca_cfg_ad.py`：合并 `sca_cfg.json` 的 A/B 与 `sca_cfg_D.json` 的 D，根据物理矩阵文本实际行数补 `length`；只处理 A/B/D 路径约定。
- `output/generate_data_with_addr.py`：把 SCA 配置引用的物理矩阵转成 128-bit hex，并生成 byte/128-bit word 地址对照；十进制解析只支持 fp16/fp32，INT8 数据需直接提供已打包 binary/hex 或扩展 dtype 支持。
- `output/` 下其余层目录是上述脚本和 pipeline 的生成数据，不是源码真值。

### `generate_python_golden/`：DeepSeek 数据与 relayout【语义参考/验证】

- `README.md`：明确把流程分成“逐节点 Python golden”和“单算子 slice/relayout”两阶段，输出 `opX/sliceYY` 的 bin/128-bit 文本；也说明未跟踪的 DeepSeek f16 权重必须外部下载。这是 ResNet 数据工具应借鉴的组织契约，但现有实现只服务 LLM。
- `Makefile`：当前默认链为 `generate_seq_input.py -> weight_gen.py -> deepseek1.5b_3_time_golden_smallsize.py -> run_single_op.py`，所以 `smallsize.py` 是可见构建入口采用的版本。
- `config.json`：模型尺寸、数据路径、`target_op` 等参数。
- `generate_seq_input.py`、`create_dummy_inputs.py`：生成序列输入/占位输入。
- `weight_gen.py`：读取并切分 DeepSeek/HF 权重。
- `deepseek1.5b_3_time_golden_smallsize.py`：当前默认 DeepSeek golden 主脚本。
- `deepseek1.5b_3_time_golden.py`、`smallsize copy.py`、`smallsize_0527.py`：完整或历史快照，缺少清晰版本说明，不能混合作唯一真值。
- `create_summac_data.py`：构造 summac 测试数据。
- `run_single_op.py`：按 target op 调 relayout；rmsnorm/softmax 会先跑 address remapping，再调用 `model_execplan/main.py`。
- `single_op_data/relayout_*.py`：把 DeepSeek golden 转成各 slice/算子布局，覆盖 gemm、rmsnorm、rope、softmax、remote sum 等；普遍带 28-slice/LLM shape 假设。
- `single_op_data/relayout_layer0.py`：读取 `layer0_op_listing.json`，按硬编码的模板名/数据目录把已经生成的单算子 `install/opX` 复制拼成 layer0，再按固定 `order` 重排 28 个 slice 并注入 ring GEMM。它是网络级数据装配范例，不会根据算子语义计算新 relayout，也不能直接生成 ResNet 数据。
- `single_op_data/backup/`、`relayout_gemm_old.py`：旧备份，只供追溯。
- `rope_fp32/`、`softmax_scale.bin` 和生成目录：数据产物，不是通用 ResNet 工具。

这里没有 ResNet INT8 的 activation/weight relayout、packing 和逐 op golden 流程。

### `address_remapping/`：layout 与物理地址映射【后续主线/分析】

- `AGENTS.md`：该子项目的约束和术语真值；remapping 定义为 `remapping[new_bit]=old_bit`。
- `layout.py`：声明式 factorized layout，把 tensor 轴拆成位；要求相关轴/因子为 2 的幂并组成 128-bit block。
- `model_parser.py`：解析小型图 DSL，计算 shape/partition 并生成 tensor/op/edge。
- `registry.py`：登记各 op 端口 layout 和 shape resolver；默认 registry 精确为 23 个 DeepSeek FP16/FP32 算子，quant、add-dequant、avgpool、maxpool、INT8 Conv/MatMul 均未登记。
- `graph.py`：把模型图、registry、硬件配置和 solver 串起来，生成每条边的映射结果。
- `solver.py`：求 producer 到 consumer layout 的位排列，并选择物理 bank/interleave 位。
- `addressing.py`：应用、组合、求逆 bit permutation，并转换逻辑/物理 DRAM 地址。
- `hardware.py`：硬件、solver 和性能参数数据类。
- `rmsnorm_bridge.py`：规范化外部 DeepSeek/layer 图并回填 remapping、bank interleave，包含特例。
- `json_format.py`：稳定输出紧凑 remapping JSON。
- `performance.py`：生成请求和分析延迟，不负责功能正确性。
- `roofline.py`：输出 roofline 摘要、JSON/SVG。
- `validation.py`：内部请求校验、trace/Ramulator 配置和可选外部 Ramulator 对比。
- `cli.py`：solve、fill-remapping、performance、validation、roofline 命令入口。
- `tests/test_solver.py`：覆盖 remap 方向、桥接、bank interleave、外部输入/叶输出、B' 镜像和 CLI 等回归；`tests/test_performance.py`：闭环 bank controller 与 ring GEMM group completion 回归。
- `examples/`：只包含 DeepSeek/layer0、RMSNorm、RoPE、Softmax、local/ring GEMM 等图和硬件/性能配置，没有 ResNet 图或 INT8 Conv registry。
- `scripts/analyze_rms_norm_summac_row_changes.py`、`compare_rms_norm_summac_requests.py`、`merge_rms_norm_summac_handshake.py`：分析/对齐 RMSNorm summac 的 local-hub 与 bank trace、行切换和握手。
- `scripts/estimate_ttft_from_config.py`、`export_op_performance_summary.py`：估算 transformer TTFT 并导出逐算子性能/roofline 汇总。
- `scripts/export_ttft_*`、`generate_*ppt.py`：抓取或整理外部性能数据，生成 CSV/PPT；属于报告工具，不参与功能正确性链。
- `scripts/setup_ramulator_{windows,wsl}.*`：下载/构建外部 Ramulator2；当前跟踪的 `outputs/tests/test_ramulator_root/build-linux/ramulator2` 及其 address_remapping 副本都只有 `exit 0`，是单测桩而非真实 Ramulator。
- `BANK_CONTROLLER_COST_MODEL_RULES.md`、`GENERAL_OPERATOR_LATENCY_MODEL.md`、`LATENCY_BREAKDOWN_SUMMAC_MAC_SFU.md`、`ORDINARY_OPERATOR_PERFORMANCE_MODEL_DIAGRAMS.md` 和 `PLAN.md`：描述 bank 仲裁/回压、普通算子 latency、summac/mac_SFU 拆解、roofline 和项目设计；用于性能模型，不是 JSON 字段或 ResNet 功能规范。
- `outputs/`、`golden/`：solver、trace、性能报告和测试快照，包含大量重复/巨大 JSON；可作回归参考，不是新的执行入口。`outputs/modeling/~$ordinary_operator_performance_model.pptx` 是 Office 锁文件。
- `Makefile` 是 address-remapping CLI 编排；`Makefile copy` 实际是无关的 Soc_lab1/VCS 加法器仿真脚本，所引用 `adder.v/tb.sv` 也不在仓库，不能作为本项目硬件入口。

该模块常用两阶段映射：producer 写入 `P_physical ∘ P_layout`，consumer 读取使用 `P_physical`；外部输入/最终输出通常只应用物理映射。它能确认 int8 的一个 128-bit block 是 16 个元素，但没有 ResNet op registry，因此不能自行决定 C/H/W 的轴顺序；其 2 的幂/128-bit 假设如何处理 ResNet 非整齐 tail，仍未解决。

### `config/`：旧手工配置编码器【旧版参考/版本冲突】

- `component_config/`：旧版逐模块 packer，覆盖 buffer、GA in/out/PE、IGA loop/PE、read/write MSE、NSE、SA。
- `config_generator.py`、`config_generator_ver2.py`、`config_nse.py`：手工拼配置的样例/原型，含硬编码 cluster 路径和未实现 `pass`，不是当前 JSON 编译入口。
- `iga_generator.py`、`iga_generator_ver2.py`：旧 IGA loop/tag 传播原型；可帮助理解 LC 层级，但区间/接口与当前 encoder 不完全一致。
- `utils/config_parameters.py`、`config_parameters_ver1.py`：16-slice 参数镜像；给出 16/4/4/8/3 等 slice 内资源数和寄存器位宽，但与当前 bitstream 20/5/5/10/4 定义冲突。
- `utils/bitgen.py`、`module_idx.py`：旧位拼接和模块编号辅助。
- `utils/excel_config.py`、`excel_generator.py`：从表格生成/整理寄存器配置说明。
- `get_parameters.py`、`get_random_data.py`：参数和随机数据辅助。
- `temp.txt`：旧编码器输出的一份 63-bit 左右二进制行样例，没有来源/版本元数据，只能作为历史产物，不能决定目标位流。

这部分只能交叉验证字段来源，不能直接决定目标 RTL 编码。

### 其他顶层内容

- `run_all_slices.py`【实验】：生成并运行 ring GEMM 多 slice JSON，默认 4 slice；按 slice 改高位地址。bitstream 失败会每两秒无限重试，不能作为通用 16-slice 入口。
- `outputs/`【产物】：批量 bitstream、报告和调试输出。
- `.gitignore`【仓库规则】：忽略大量模型、矩阵和二进制产物，缺文件时先判断是否未入库。

## `CGRA_SIM` 详细代码地图

### 顶层文件和文档

- `README.md`：只说明把仓库加入 `PYTHONPATH`，没有完整构建/运行手册。
- `env.sh`：设置当前目录到 `PYTHONPATH`；该文件已有用户修改。
- `docs/oplib.pptx`【重要语义参考/旧硬件设想】：18 页算子分类文档。除 reduce/elementwise/GEMM/nonlinear 的 SIMD、RDFIFO/WRFIFO/PE 数量设想外，还明确区分 dimension transform：`reshape/expand_dims/squeeze` 候选为物理零拷贝只改 shape/stride；`layout_transform` 需要物理重排；低三维 `transpose` 可用 stride/AG direction 表达，但旧方案也考虑物化到新内存；高维或跨 slice broadcast/strided_slice/take 倾向 TMA。它能指导 lowering/relayout 分类，但资源数和实现路线必须由目标 NDP RTL/JSON 再确认。
- `scripts/func_validator.py`【实验/未完成】：拟把 ONNX 每节点输出、execution plan 注释和模拟结果统一验证；ONNX->CGRA 名称映射、激活地址、注释解析、比较仍是 TODO。

### `cgra_python/arch/`：性能参数模型【语义参考/版本冲突】

- `arch_base.py`：通用算力、带宽、容量、利用率字段容器；不是 JSON 中的 slice 内资源定义。该文件已有用户修改。
- `cgra_ver15.py`：16 个计算阵列、8x8x1 tensor core 等 ver15 性能估算参数。
- `cgra_ver20.py`：16 个计算阵列、8x8x8 tensor core 和 INT8 吞吐等 ver20 参数。
- `__init__.py`：导出两版架构；已有用户修改。

两版 `sm_count=16` 支持目标阵列数量，但不能解决 LC/stream/PE 配置位宽版本冲突。

### `cgra_python/execution_plan/`：ONNX 参数和旧计划辅助【语义参考/验证】

- `ep_input.py`：ONNX 输入的 `(name,value)` 轻量结构。
- `get_params.py`：加载 ONNX initializer，交给 QNN preprocessor，按 32-bit word 地址写 DDR，输出 weight/tensor 字典。
- `register_preprocessor.py`：注册 `QLinearConv`、`QLinearMatMul`、`QLinearGlobalAveragePool`、`DequantizeLinear` 参数预处理。
- `params_preprocessor/qnn_conv_pre.py`：折叠 Conv scale/bias；是 `scale_eff=x_scale*w_scale/y_scale`、`bias_eff=bias-x_zp*sum(w)` 的主要软件证据，后式完整成立依赖 `w_zp=0`。
- `qnn_matmul_pre.py`、`qnn_averagepool_pre.py`、`dequan_pre.py`：分别预处理 MatMul、量化全局平均池和反量化参数。
- `gen_input.py`：ImageNet resize/crop/normalize，写输入 DDR。
- `gen_ddr.py`：组合权重和 batch=16 输入生成 DDR；使用硬编码 `/cluster/home/...` 路径。
- `gen_ddr_2.py`：在前述 DDR 基础上额外注入一个中间 MatMul checkpoint，供断点/恢复实验。
- `memory_allocate.py`：硬编码少量 activation/input/output shape 的早期内存草稿；不是完整 ONNX allocator，且 output 字典代码有明显复制错误。
- `conv_ir.py`：Conv、padding、量化、rounding 和内存读取的软件参考。
- `myonnx.py`：自定义 ONNX `QLinearConv` 实验；只覆盖部分 shape，其他情况报未实现。
- `test.py`、`test_avg.py`、`test_sum.py`：Conv、量化 AvgPool、sum 手工验证脚本，不是自动测试套件。

### `cgra_python/op_lib/`：功能模拟软件算子【语义参考/验证】

- `base_op.py`：dtype/bytes 转换、tile reshape、layout、nearest-even rounding、uint8 saturation；metaclass 按类名自动登记算子。
- `op_instance.py`：按 opcode+参数缓存并实例化 registry 算子。
- `stream.py`：SPM stream 的二维起点、宽度、大小和 load/store 标志。
- `elementwise_op/`：`ADD`、`BIAS_ADD`、`MULTIPLY`、`NEGATIVE`、`RELU`、`FILL_ZERO`。
- `nonlinear_op/`：`DIVIDE`、`EXP`、`SQRT`。
- `reduce_op/`：`MAX`、`SUM`、`AVGPOOLING`、`MAXPOOLING`。
- `tensor_op/conv.py`：当前包实际导出的浮点/通用 `CONVOLUTION`。
- `tensor_op/gemm.py`：当前包实际导出的 `GEMM`。
- `tensor_op/conv2d.py`、`gemm_c.py`：未被 `tensor_op/__init__.py` 导出的另一版/配置原型；`conv2d.py` 也叫 `CONVOLUTION`，若直接导入会与 registry 类名冲突。
- `qnn/quantize.py`、`dequantize.py`、`quantize_linear_add.py`：分别实现 QuantizeLinear、DequantizeLinear 和 QLinearAdd，并带 ORT 小模型对照辅助。
- `qnn/qnn_conv.py`、`qnn_conv_bias.py`、`qnn_conv_quan.py`：分别实现 int32 psum 累加、bias 初始化和末 tile requant 三种 Conv 阶段，和旧 ResNet 首/中/末 K tile 调度对应。
- `qnn/qnn_matmul.py`、`qnn_matmul_quant.py`：分别实现 MatMul int32 累加和带 scale/zp 的末阶段 requant；源码注明只适用于零点受限情形。
- `qnn/qnn_averagepool.py`：量化全局平均池，明确只支持输入/输出 zero point 都为 0；`qnn_round.py`：模拟 ORT/SSE2 nearest-even 的 per-channel requant。
- 各 `__init__.py`：决定 registry 实际加载范围；存在源码文件不代表默认 simulator 会注册它。

这套库用 NumPy/Torch/ONNXRuntime 复现结果，不模拟目标 LC/stream/buffer/SA/GA 的逐周期行为；能决定算法语义和候选拆分，不能直接给出 JSON 字段。

### `cgra_python/simulator/driver/`：旧 `.cu` execution plan 前端【验证】

- `lexer.py`、`parser.py`：PLY 词法/语法，解析 `make_tensor`、DMA、SPM allocate/free 和 `slice_<OP>` 指令。
- `compiler.py`：`execution_plan_preprocessor`；记录 tensor/SPM，计算 tile DDR 地址、dtype scaling、padding/extraction 参数，转成 simulator `Instruction`。
- `convert.py`：把 execution plan 文本转小写的单用途脚本，默认指向 Nerf 样例。
- `parser.out`、`parsetab.py`：PLY 自动生成表，不应手工当业务代码修改。

### `cgra_python/simulator/emu/` 与 `func_sim.py`：功能模拟主链【验证】

- `func_sim.py`：读取/预处理 execution plan；构造 16 个 `Slice(PeArray,Storage2D)`；执行 DMA、SPM stream 和 registry 软件算子；记录 checkpoint。`make_tensor`/`reallocate_tensor` 在执行阶段为 `pass`，因为主要信息已由 preprocessor 消化。
- `emu/storage.py`：用 `numpy.memmap uint32` 模拟 DDR 和二维 SPM，地址单位主要为 32-bit word。
- `emu/array.py`：从 SPM 读 stream，调用软件 op，再写回 SPM；不是物理 PE 阵列逐节点仿真。
- `emu/tensor_iterator.py`、`extraction_iterator.py`：正常 tile 和带 padding/extraction 的 DDR 地址迭代。
- `emu/dma.py`：更早的一体式 DMA/iterator 和 round-robin 辅助，部分逻辑与新 iterator 重复。

### `cgra_python/simulator/engine/`、`dram/` 和外围【实验/非目标 JSON 模拟器】

- `engine/`：Event、EventQueue、Port、Connection、Ticker、Task、SerialEngine 等离散事件基础设施；部分基类 `NotImplemented` 是抽象接口。
- `dram/`：bank/channel、命令生成/队列、地址 mapper、memory controller、transaction splitter 和 builder，尝试建立 DRAM 时序模型。
- `dma.py`、`dmacmdqueue.py`：DMA 请求和队列。
- `requestgen.py`：从 execution plan 产生 DMA/operator 请求。
- `execplan.py`：时序模型的 execution-plan message/command。
- `execmanager.py`：调度 DMA/operator；多条分支直接抛 `NotImplementedError`，未闭环。
- `con_man.py`：全局配置管理，仍有“等待全部配置”的 TODO。
- `slice.py`：时序模型中的 slice/config message，不等于 `cgra_python/slice/` 模拟器。
- `platform.py`、`test.py`：builder/stride 局部测试。
- `arch.svg`、`dma.svg`、`dram/dramsim.svg`：结构图产物。

没有看到这套时序骨架被 ResNet INT8 `run.py` 调用；当前 runner 使用 `func_sim.py`。

### `cgra_python/slice/`：TOML/XML 单 slice 模拟器【旧版参考/实验】

- `README.md`：描述 LC、PE、AG 的 TOML 字段；标明配置、地址生成、PE 计算、参数化生成已验证，连接资源、SPM layout、bank conflict 未完成。
- `node.py`：`Iteration`、`Compute`、`TensorCompute`、`AddressGenerator`、`Read`、`Buffer` 等节点语义。`Iteration.compute` 使用 `range(start,end,step)`，支持 `[start,end)` 结论。
- `parse_toml.py`：把 TOML 参数、loop、PE、AG、SPM stream 解析成 networkx 图。
- `analysis.py`：删除逻辑 buffer/transin、分析 loop period、传播序列和地址；connected component、并行周期同步仍有 TODO。
- `simulator.py`：拓扑执行 tensor compute，读取 tag/常量/前驱序列并写回边。
- `spm.py`、`storage.py`：scratchpad、二维存储和 interleaving。
- `operator.py`：`OperatorConfiguration` 外壳；构造函数硬编码 GEMM TOML，`execute()` 为 `pass`。
- `main.py`：硬编码运行 `inputs/gemm_64_64_64_0.toml` 的演示入口，使用相对 import/路径，需从特定目录执行。
- `inputs/*.toml`、`*.xml`：GEMM、PE array、simple loop 和历史样例。
- `xml_to_toml/`：解析 XML 参数/数据流、求值表达式并生成 TOML；不输出 ndp-sim JSON。
- `test/golden_model/`：GEMM/SPM 生成和检查；`interface.svg`：接口结构图。

### `cgra_python/layout/`：layout/tiling 实验【语义参考/未闭环】

- `conv_layout.py`：Conv padding、im2col、PE array 对齐；支持候选 `A[M,K] x B[K,N]` 布局。
- `layout_buffer.py`：Buffer、Timeline、Axis、Layout、Tensor、PE/PEArray 和 buffer mapping 原型；部分方法为空实现，并且当前第 201 行把 `pass` 写进 `PE.execute(...)` 实参列表，导致整文件 `SyntaxError`，修复前不能作为可导入的 relayout 库。
- `layout_yemp.py`：生成输入/权重布局数据，padding 是 TODO。
- `make_tensor.py`：tensor/layout transformation 原型，多处 `pass`。
- `tile_val.py`、`validation.py`：逐 tile/operator golden 校验草稿，含未完成辅助函数，二者高度相似。
- `lc.py`：loop-control/layout 实验数据结构。
- `pycute/`：CuTe 风格 tuple、layout、swizzle 数学工具；是通用布局库，不是业务入口。

已从这里确认候选 INT8 实验布局：4 个连续 INT8 按低字节到高字节装入 32-bit lane，SA 候选 8x8、每步 K=8，im2col K 顺序 `KH,KW,C`，M/K/N 候选对齐 16/8/16。但它尚未接入 ndp-sim JSON/relayout。

### `cgra_python/memory/` 和 `util/`【辅助/验证】

- `memory/scripts/get_memory.py`、`check_tile.py`：从 DDR 读取 tensor/tile 并比较。
- `generate_mem.py`、`get_first_gemm.py`：生成/抽取特定测试内存数据。
- `util/generate_spm.py`：格式化输出 SPM 数据。
- `util/spm_check_tensor.py`：将矩阵写入 checkpoint 日志。
- `util/extract_blocks.py`：从网格抽取 block；已有用户修改。

### `testing/`：模型和算子样例【验证/参考】

- `resnet-50-int8/`：最相关。`gen_execu_plan_ver1.py` 打印 batch=16 的 Quantize/Conv/MaxPool/Add/AvgPool/MatMul/Dequantize 旧计划；`run.py` 执行功能模拟并按固定 instruction index 对比；`golden_model/golden.py` 是已有的 ResNet50 ONNXRuntime 实现，负责修改图输出、预处理并生成部分 checkpoint；`image_prepro/input.py` 做输入预处理；`get_shape.py` 把 graph name 当节点迭代，不能作为可靠 shape 提取器；`test.py` 是局部实验。
- `resnet-50-fp32/gen_resnet_execution_plan{,_ver2,_ver3}.py`、`gen_avgpooling.py`：多版手写 Conv/Add/Mul/ReLU/Pool/GEMM 调度；版本间有复制和未完成 `pass`，可参考网络组织与地址生命周期，不能作为 INT8 或 NDP execplan 前端。
- `resnet-50-fp32/golden_model/get_activations.py`：同样通过追加手写 ONNX outputs 生成部分 ORT checkpoint，并不比 INT8 `golden.py` 更通用。
- `resnet-50-fp32/gen_ddr.py`、`params/*`、`check_mem.py`、`test_ddr.py`：旧 graph.params/输入提取、排序、DDR 生成和内容核对；`process_txt.py` 是旧 `.cu` 语法的正则修补脚本。
- `resnet-50-fp32/conv_triton_ref.py`、`Heatmap.py`、`mac_num.py`：Triton Conv 参考/benchmark、误差热图和 MAC 统计；不生成 NDP JSON。
- `resnet-50-fp32/run.py`：运行旧功能模拟器；`test.py`、`golden_model/test.py` 是局部 NumPy 实验；`resnet50_shape.py` 是 0 字节空文件。
- `resnet-50-fp32/graph.json`、约 102 MB `params/graph.params` 和 Welder tuning JSON：旧 FP32 模型/调优数据，可复跑旧链的一部分，不能补出缺失的 INT8 ONNX/参数。
- `mobilenet_v2_fp32_bs16/`：TVM graph/params 和相关数据，主要是模型覆盖样例。
- `nerf_case/`、`nerf_no_fusion_case_fp32/`：execution plan 生成、golden、DDR、runner 示例。
- `gemm_relu_case/`、`tile_gemm/`、`ndp_gemm/`：GEMM/ReLU、tile 和 NDP execution plan 小样例。
- `data_format_numerical/`：FP16/FP32 精度测试和 Excel 结果。

`resnet-50-int8/` 当前只跟踪 7 个源/图片文件，没有目标 ONNX、DDR、tensor_dict、`.cu` plan 或 golden `.npy`，所以仓库现状无法直接复跑完整旧流程。

### `timing/`：Go 时序模拟与 Python parser【实验/非目标 JSON 模拟器】

- `timing/bitstream/parser/lexer.py`、`parser.py`、`converter.py`：解析一种 Python-like bitstream/配置文本。
- `lex.py`、`yacc.py`：内置第三方 PLY 源码。
- `timing/simulator/engine/*.go`：串行/并行事件引擎、端口、buffer、连接、频率和 ticker。
- `timing/simulator/dram/*.go`：DRAM bank/channel/controller/queue/transaction/address mapper。
- `timing/simulator/emu/*`：存储、地址转换和 PE array 软件结构。

目录中没有 `go.mod`、`package main` 或 `func main` 入口，也没有看到 ResNet runner 调用；`engine/connection.go` 会 `panic("not implemented")`，`timing/simulator/emu/slice/pearray.go` 只有 15 字节的 package 声明，没有 PE array 实现，更像未集成的另一版时序库。

### `to_support_ops/`：算子覆盖统计【分析产物】

- `op_library/supported_ops.py`：静态列出 35 类 TVM/Relay 风格算子。
- `2d_dimension_op.py`、`models_op.py`：扫描 `.cu`/Relay 文本，统计模型使用哪些 op。
- `model_op_matrix.csv`、`model_op_statistics.csv`、`op_statistics.csv`：扫描结果；旧 FP32 ResNet 主要有 conv2d、bias_add、maxpool、global avgpool、relu、add 等。
- `tile_op_template/op_template.py`：把 reduce/GEMM/elementwise 统一为二维 tile 的注释草稿。

这些是字符串扫描统计，不代表 ndp-sim 已支持对应算子或目标 INT8 配置已完成。

## `NDPFuncModel` 详细代码地图【Conv 功能参考/待修复集成】

- 根目录 4 个 `main_*` 分别驱动 Conv/GEMM/GEMV；ResNet 当前只以 `main_CONV_N2N.py` 为核心。
- `component/` 是运行主体；`GeneralPEA.py` 为空，实际使用 `SpecialPEA.py`。
- `config/` 是历史配置生成/寄存器拼接代码；`config_generator_ver2.py` 和 `config_nse.py` 分别给出固定 Conv 与邻居流 Conv 的字段实例，后者的 NSE 计数 15 与 16 个 slice 相符；`config_parameters.py` 与 `config_parameters_ver1.py` 对应不同架构版本，资源数/位宽并不等价。主 Conv 没有导入该目录，不能据此认为 Conv 已由配置驱动。
- `utils/` 提供 dump、初始化、解析和输出重置；`requirements.txt` 仅列 numpy/openpyxl/tqdm，但 PyTorch 验证脚本还依赖未声明的 torch。
- `conv_config` 是无法解析来源的 gitlink；没有 `.gitmodules`，只知道对象提交 `51c15b6…`，无法恢复 URL。`graph/` 只有 CPython 3.12 字节码，但已可反序列化确认其 JSON 图、依赖树、伪代码和地址 dump 功能；适合后续恢复为源码，不适合直接当长期依赖。
- `verify_pe/` 有 1000 余个 trace 文件，另有多组 GEMM dump、根目录 `.npy/.log/.txt`；统一按生成验证产物处理。
- 静态复核 81 个 Python 文件全部能通过 AST；2 个 JSON 中 `kernel/add_config_MN_N.json` 可解析，`.vscode/launch.json` 是带注释 JSONC，不能按严格 JSON 解析。

完整 Git 历史可用：仓库不是 shallow clone，共 47 个提交。历史节点能看到固定 Conv 配置完成、FP16 local GEMM、4-slice ring GEMM、GEMV 和写回检查的演进；旧提交 `ef2e8c1` 的 Conv 入口虽声明 `slice_num=16`，但当时仍只加载 slice0/bank0，不能据此证明曾有可工作的 16-slice Conv。当前跟踪文件约 137 MB，其中 Python 源码约 0.54 MB，txt/log 约 128.8 MB，仓库体积主要由生成 trace 和 DRAM fixture 构成。

其余有效内容已归类如下：

- `main_GEMM.py` 是 FP16 local GEMM；`main_GEMM_N2N.py` 是 4-slice ring GEMM；`main_GEMV.py` 展示 FP16 GEMV 和输出 packing。四份 GEMM word 文件是完全重复的同一 fixture；GEMV byte 文件与其底层字节相同，只有 byte 版本能直接由当前 `DRAM.init_from_file(dtype=uint8)` 加载。
- `generate_gemm_fp16.py` 是少数可移植 CLI 数据生成器；`randomdtat_fp16.py`/`fp32.py` 能生成完整 DRAM 几何但导入即运行且写死集群路径；`get_random_data.py` 的 6000×2048 默认格式与当前 6144×1024-byte loader 不兼容。
- `dram_viewer.py`、`parser.py`、byte/word 转换脚本可保留为诊断工具；`patch_*`、`fix_hex_sign.py`、`format_fix.py` 都是导入即改源码的一次性迁移脚本，只能当历史证据，其中 `patch_ag.py` 还显示 slice offset 曾被主动移除。
- `config_generator.py` 是不可运行骨架；两份 `iga_generator*` 是旧实验。`module_idx.py` 的注释/分段宽度与当前 encoder 实际宽度不一致，BMC/NSE 的部分 enable 参数声明后未进入位串，正式使用前必须做逐字段 round-trip 审计。
- `verify_special_pea_gemm.py` 期待旧日志格式，无法解析仓库现有 GEMV `[PEIN]` 日志；当前没有兼容的自动 validator，也没有跟踪 golden output。
- 仓库没有 README、测试框架、CI、package metadata 或锁定环境；根目录多个测试/生成脚本没有 main guard，不能用“全部 import”作为健康检查。

## 全量文件复审边界与结论（2026-07-11）

当前以三个仓库全部 Git 跟踪文件为总账，并额外检查 ignored/untracked：

| 仓库 | 跟踪文件 | 逐目录覆盖 | 未分类的有效源码 |
|---|---:|---|---:|
| `ndp-sim-ref` | 413 | `jsons` 42、bitstream 15、旧 config 29、DeepSeek golden/relayout 34、model_execplan 38、address_remapping 252、根文件 2、outputs 1 | 0 |
| `CGRA_SIM` | 275 | `cgra_python` 163、testing 64、timing 35、to_support_ops 8、根/文档/脚本 5 | 0 |
| `NDPFuncModel` | 1232 | 81 个 Python、2 个 JSON/JSONC、组件/配置/工具源码，以及 1000 余个 Conv/GEMM trace、75 个被跟踪的 `.pyc` 和其他生成产物 | 0 |

审计口径：Python/Go/shell/PowerShell/Makefile/Markdown/TOML/JSON/CSV 逐目录检查入口、类/函数、TODO/`pass`/`NotImplemented` 和调用关系；PPTX/XLSX 检查页/表结构与内容类别；`.params/.bin/.trace/.log/.svg/.png/.jpg` 按生产者、消费者和用途分类。原两仓库 319 个 Python、30 个 Go 均已落入已有功能分组；新增仓库的 81 个 Python 全部通过 AST。原审计唯一 Python 语法失败仍是 `CGRA_SIM/cgra_python/layout/layout_buffer.py:201`。`NDPFuncModel` 的严格 JSON 输入只有 `kernel/add_config_MN_N.json`，`.vscode/launch.json` 按 JSONC 处理。三个仓库未发现新的未分类业务源码。

结论不是“所有代码都可运行”，而是“没有仍无法解释用途的有效文件”：未闭环文件已标为实验/骨架，空文件、第三方 PLY、生成 parser 表、Office 锁文件、测试桩和无关备份已单独识别。新增仓库确实提供了此前缺少的 Conv 功能数据通路模型，但未发现正式 ResNet INT8 ONNX/参数/golden 产物、完整 ResNet 逐算子 relayout、能直接解释目标 JSON/bitstream 的数值 emulator、ResNet ONNX→NDP execplan lowerer、RTL/硬件 runner 或通用三方比较器。

## 剩余问题按解决方式分级

### 必须取得外部权威信息

1. 正式 ResNet ONNX、输入预处理和旧运行产物是否可提供。
2. activation、weight、bias、scale/zp 的正式物理 layout 和三维 shape 解释。
3. INT8 SA 的端口、`bias_enable`、int32 psum、requant 和可选 ReLU 接口。
4. GA 的 unsigned max、转换、rounding、saturation 和溢出语义。
5. per-layer/per-channel qparams 采用 constant patch、tensor stream 还是逐层静态 JSON。
6. 目标 16-slice RTL/ISA 对应的资源数、字段位宽、opcode、DDR row 和指令格式。
7. `NDPFuncModel/conv_func` 是否就是目标 Conv 模拟器基线；若是，需提供缺失 `conv_config`/`hex_data`、目标 JSON/bitstream 到其参数的映射，以及正确的 uint8×int8、requant、16-slice 和写回约定。
8. 非 Conv 算子的目标 emulator，以及硬件/RTL 的加载、运行、完成判定和 dump 协议。

配置算法类问题的详细证据见 `.agents/rules/算子配置规则.md` 第14.3节；完整资料请求见 `plan.md`。

### 仓库内必须实现

- 统一 ONNX→硬件原子算子 lowering 和 manifest。
- 全节点 raw golden、QNN 子步骤 golden 和可重放测试输入。
- 逐算子实现 ResNet 16-slice partition/relayout/packing/remapping 及全部逆变换，覆盖 Quantize、Conv、MaxPool、Add、AvgPool、MatMul/dense、Dequantize 和 Flatten/View；这是本项目需完成内容，不等待现成 ResNet relayout。
- 全部 ResNet 原子 JSON、base-info、handler、量化常量参数化和稳定 bitstream。
- 目标 emulator runner、输出提取和逻辑 tensor 恢复。
- 16-slice ResNet execplan 前端、schema 扩展、严格失败和完整数据包。
- RTL/硬件 runner、checkpoint/dump 和版本记录。
- golden/simulator/hardware 三方比较器和分层回归。

### 功能正确性闭环后再做

- 性能模型/Ramulator 与真实硬件时序的精确标定。
- 非 ResNet 模型通用化和 batch≠16 的性能调度优化。
- 对未接入目标链的 Python/Go/TOML 时序骨架做大规模重构。

这些不阻止功能正确性闭环，但只要影响实际 JSON 编码、地址或硬件结果，就必须提前升级为阻塞项。

## 已经不再未知的规则

- 目标是 16 个 slice/PE 阵列，不是 28。
- LC 控制循环，区间按 `[start,end)`；`last_index` 是循环层级，外层到内层递增。
- keep、buffer full、ping-pong、transout 的 last index 引用相应循环层结束事件。
- stream 端口配置顺序为 `[port2,port1,port0]`。
- `idx_size=真实长度-1`；`dim_stride` 是 byte stride；padding low/up 是包含端点的有效范围。
- 现有模板 transaction 维度使用 2 的幂，乘积不超过 128；新增配置暂沿用这一保守约束。
- INT8 lane 内每 4 个连续元素按低字节到高字节装入 32-bit lane，第一个元素在最低 8 bit。
- 软件 QNN 参考采用 nearest-even rounding 和 uint8 saturation。
- Conv 软件预处理候选公式为 `scale_eff=x_scale*w_scale/y_scale`，在 `w_zp=0` 条件下 `bias_eff=bias-x_zp*sum(w)`。
- 旧计划精确包含 77 个原语，Conv 的首/中/末 K tile 分别承担 bias 初始化、int32 psum 累加和 requant；MatMul bias 是后继 QLinearAdd。
- 软件 MaxPool 的 padding 已在 extraction 阶段填 0；AvgPool 的算法公式和 nearest-even/uint8 saturation 已知，未知的是目标 NDP 如何组合与注入常量。
