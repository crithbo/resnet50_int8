# ResNet50 INT8 端到端实施计划

最后更新：2026-07-11

本文件是项目唯一的权威执行计划。默认入口是 `.agents/agent.md`；已经发生的事实见 `.agents/history.md`；单算子配置推导细则见 `.agents/rules/算子配置规则.md`。

## 最终目标

项目目标不再收窄为“先补 JSON”，而是完成以下 ResNet50 INT8 端到端闭环：

```text
正式 ONNX / 输入 / initializer
  -> ONNX 节点与硬件原子算子 lowering、稳定 manifest
  -> 每个算子的 raw golden input/output，以及必要的硬件子步骤 golden
  -> tensor partition / padding / relayout / packing / remapping
  -> 每个硬件原子算子的 JSON 与 bitstream
  -> JSON/bitstream 跑目标数值模拟器并导出结果
  -> 网络结构生成目标硬件格式 execplan、配置包和 Bank_data
  -> 硬件或 RTL 执行并导出结果
  -> golden、simulator、hardware 三方逐算子和整网一致
```

这里“每个算子”必须区分两层：ONNX 模型节点和硬件原子算子。一个 QLinearConv 可能拆成首 K tile bias、中间 psum、末 K tile requant；AvgPool 可能拆成 sum 与 requant。最终 manifest 必须显式记录一对多映射，不能把旧计划的 77 个模型级原语直接当成最终 StartComp/JSON 实例数。

## 状态和难度口径

状态统一使用：

- **已有可复用**：代码和接口存在，仍需用 ResNet 数据验证。
- **部分已有**：有参考或旧链，但未接入目标 JSON/硬件链。
- **暂时缺失资料**：生成代码或读取入口存在，但 ONNX、golden、DDR、execplan 等大文件未入库。
- **仓库中没有实现**：没有可调用的目标功能，例如目标 JSON 数值 emulator 或硬件 runner。
- **待外部确认**：仓库存在版本冲突，必须由学长、RTL 或硬件接口给出权威答案。

难度统一使用：低、中、高、很高、外部阻塞。难度表示技术和集成风险，不表示工期承诺。

## 执行原则

- 推进每一步前，先审查当前代码和文档是否支持计划。
- 如果方案不合理或存在更好路线，先向操作者说明并确认是否调整。
- 先完成一个单算子三方闭环，再扩到残差块和完整网络；禁止只以“JSON 能生成 bitstream”作为完成标准。
- 每个阶段都要产生机器可读 manifest，名字、shape、dtype、layout、slice、地址和来源不可只写在脚本常量中。
- 所有物理变换必须同时实现正向和逆向；不能 inverse-relayout 的输出不得宣布数值验证完成。
- INT8/UINT8/INT32 默认 bit-exact；FP32 必须记录 `atol/rtol`。
- 每完成一个阶段，更新本文件的状态，并在 `history.md` 追加记录。
- 从根仓库首版开始，每个经过测试确认有效的小步骤做原子Git提交；W1/W2等工作包通过验收门后推送GitHub里程碑。未经操作者再次确认，不删除、压缩或改写已有提交历史。

## 当前总体状态

- **已有可复用**：`CGRA_SIM/testing/resnet-50-int8/golden_model/golden.py` 已提供 ResNet50 的 ONNXRuntime 执行、ImageNet 预处理、batch=16 输入和输出保存基线；另有 ResNet QNN 软件语义、旧 77 原语调度、LC/stream/packing 的部分规则、JSON→bitstream 编译器、LLM 的 relayout 组织方式和 `model_execplan` 地址/指令框架。新增 `NDPFuncModel/conv_func` 提供 Conv 的 DRAM→AG→Buffer→8×8 PEA→ring reduction 逐字节功能 trace。
- **部分已有**：现有 `golden.py` 只 dump 手写的部分节点，尚未形成逐算子 input/output 与 manifest；旧 `.cu` 功能模拟只验证旧链；Conv layout 只有实验脚本；42 个 JSON 只局部覆盖 ResNet。
- **模型基线已取得/旧产物仍缺**：官方Model Zoo `resnet50-v1-12-int8.onnx` 已下载、校验并按SHA-256暂定为正式模型；固定 `cat.jpg` 的batch=16输入和ORT输出已生成。旧 `tensor_dict`、DDR/plan和完整逐节点golden仍未取得，但可从当前模型重建，不再作为开工阻塞。
- **仓库中没有实现**：能直接消费目标 JSON/bitstream 并完成正确 requant/writeback 的数值 emulator、ResNet ONNX→execplan lowerer、完整 ResNet relayout、硬件/RTL runner、通用三方比较器。Conv 功能模型存在，但当前硬编码 4 slice，不能替代这一项。
- **待外部确认**：正式物理 layout、INT8 SA/bias/psum/requant 接口、GA 无符号与转换语义、逐层量化常量协议、目标 RTL/ISA 版本、硬件加载和 dump 协议。

因此当前处于“参考代码和生成框架已定位，端到端接口尚未闭合”阶段；还没有任何目标 NDP ResNet 算子达到 golden=simulator=hardware。

### 接手进度总表

比例按“达到本阶段验收标准”估计，不按已有文件数量估计：

| 阶段 | 当前完成度 | 难度/阻塞 | 接手判断 |
|---|---:|---|---|
| A 权威输入和接口 | 约40% | 外部阻塞 | 模型/hash/暂定预处理已冻结；layout、ISA、emulator关系和硬件协议未冻结 |
| B lowering与manifest | 约10% | 高 | 只有旧77原语参考，没有统一实现 |
| C raw/subop golden | 25%~30% | 中高 | runner基线已有；全节点dump未实现，入口另有语法阻塞 |
| D 16-slice relayout | 10%~15% | 高 | 只有LLM/Conv候选，全部ResNet算子仍需正逆实现 |
| E 全算子JSON/bitstream | 20%~25% | 很高 | 42个参考JSON存在，核心INT8 SA/MatMul缺失 |
| F 目标数值模拟 | 5%~10% | 很高/部分外部阻塞 | Conv骨架有缺陷；通用JSON解释器未找到 |
| G ResNet execplan | 25%~30% | 高 | 框架可启动；ResNet前端、16-slice和qparams缺失 |
| H RTL/硬件运行 | 约0% | 外部阻塞 | runner、加载和dump协议均未入库 |
| I 三方比较/回归 | 5%~10% | 中高 | 只有旧checkpoint和二方物理比较脚本 |

总体工程完成度约15%~25%，仍余约75%~85%。代码地图摸底已基本完成，不应把后续时间继续投入无目的目录搜索。

### 当前可立即执行队列

1. **已完成**：W0根目录 `resnet50_pipeline/` 集成骨架、统一manifest、artifact manager、适配器接口和CLI；mock状态机及失败/resume路径通过G0。
2. **已完成**：独立小UINT8 activation×INT8 weight、INT32 bias/psum、UINT8 requant D golden；标量、im2col和ORT三方bit-exact。
3. **当前执行**：实现小Conv物理partition/layout及正逆round-trip，并为DRAM slice/bank、RDAG/WRAG transaction写地址/provenance测试。
4. 固化整数 PEA、reduction、requant和真实 writeback，使小 Conv 达到软件 golden=Conv functional model。
5. 恢复/重建 Conv 配置前端，把 `config_nse.py` 的旧字段关系映射到目标 JSON；之后才扩1/4/16 slice。
6. W1剩余硬件规格并行推进；模型已到位，修复 `layout_buffer.py:201` 后即可进入W3全节点golden改造。

环境已经准备完成，不再把安装依赖列为任务：使用根目录 `.venv` 和 `requirements-resnet50.lock.txt`。当前三个最小入口结果见 `agent.md`“本地 Python 环境与已验证入口”。

## 总体实施架构：先骨架，后纵向闭环

### 1. 集成边界

新增代码放在工作区根目录的独立集成层，不把新流水线继续散写进三个参考仓库：

```text
resnet50_int8/
  pyproject.toml               # 新建：集成层包、CLI、测试和静态检查入口
  repos.lock.json              # 新建：三个参考仓库remote/branch/commit/dirty状态
  resnet50_pipeline/          # 新建：唯一端到端集成层
  tests/                      # 新建：单元、集成、回归测试
  schemas/                    # 新建：manifest/config/result JSON schema
  contracts/                  # 新建：架构、量化、layout和后端批准契约
  .agents/decisions/          # 外部问题和批准结论记录（ADR）
  coverage/                   # 新建：逐算子/逐阶段覆盖矩阵
  fixtures/                   # 新建：可入库的小合成测试数据
  artifacts/                  # 已有且忽略：每次运行的全部产物
  CGRA_SIM/                   # 软件/QNN语义、旧计划、golden参考
  ndp-sim-ref/                # JSON/bitstream/execplan参考
  NDPFuncModel/               # Conv功能模型和旧固定配置参考
```

原则：

- 三个仓库由 adapter 调用，核心层不得通过全局 `sys.path` 或 package `__init__` 隐式导入全部仓库。
- 必须修改参考仓库的bug时，改动保持最小、单独记录并有对应测试；集成状态和manifest逻辑仍留在根目录。
- 大模型、DDR、trace、运行输出不入库；小fixture、schema、源码和测试必须入库。
- 每次运行固定三个仓库commit、Python/包版本、模型/input hash和目标架构版本。
- 根集成层的跟踪边界已由 `.gitignore` 和 `repos.lock.json` 固定：根仓库只跟踪集成源码、schema、fixture、文档和lock文件，三个嵌套仓库保持独立且不生成隐式gitlink。操作者已授权现在初始化本地根仓库并提交首版；W1/W2通过验收门后再推送GitHub里程碑。

### 2. 第一版目录骨架

```text
resnet50_pipeline/
  __init__.py
  cli.py                       # inspect/lower/golden/relayout/config/sim/execplan/hw/compare/run
  context.py                   # RunContext、路径、版本、日志
  errors.py                    # 分阶段异常和退出码
  stages.py                    # 阶段DAG、attempt、resume和失效规则
  contracts/
    architecture.py           # 资源、位宽、地址、ISA/RTL版本
    quantization.py           # scale/zp/multiplier/round/saturation契约
    backend.py                # adapter能力声明和版本探测
  manifest/
    models.py                  # Run/Model/Node/HwOp/Tensor/Layout/Config/Result记录
    io.py                      # JSON读写、schema version、hash
    validate.py                # 跨引用、状态和字段校验
  model/
    onnx_loader.py             # shape inference、node/tensor/initializer读取
    lowering.py                # ONNX node -> hw_op DAG
    registry.py                # 算子lowering插件注册
  golden/
    onnx_runner.py             # ORT逐节点raw input/output
    subop_reference.py         # psum/sum/requant硬件子步骤真值
    quantization.py            # rounding/zero-point/saturation公共实现
  layout/
    base.py                    # forward/inverse统一协议
    registry.py
    quantize.py
    conv.py
    maxpool.py
    add.py
    avgpool.py
    matmul.py
    dequantize.py
    view.py
  config/
    registry.py
    template_selector.py
    ndp_json_adapter.py
    validate.py
  simulator/
    base.py
    conv_func_adapter.py        # NDPFuncModel参数化入口
    external_adapter.py         # 未来非Conv/官方emulator
  execplan/
    builder.py
    ndp_adapter.py
  hardware/
    base.py                     # load/start/wait/dump接口
    external_adapter.py
  compare/
    tensor_compare.py
    provenance.py
    report.py
  artifacts/
    manager.py
    hashing.py
  memory/
    planner.py                 # 地址生命周期、对齐、边界和重叠检查
    model.py

tests/
  unit/
  integration/
  regression/

fixtures/
  conv_micro/
  quant_edges/
  layout_tails/

schemas/
  run_manifest.schema.json
  comparison.schema.json
  architecture.schema.json
  quantization.schema.json

contracts/
  architecture.json
  quantization.json
  backend_capabilities.json

coverage/
  operator_matrix.json
```

第一版骨架不用实现真实算法，但所有模块、接口、错误类型、CLI子命令和产物路径必须存在，并用mock adapter走完状态机。

### 3. 唯一 manifest 对象模型

第一版至少包含：

| 对象 | 必需字段 |
|---|---|
| `RunRecord` | schema version、run_id、创建时间、三个repo commit、环境版本、目标架构、状态 |
| `ModelRecord` | ONNX路径/hash/opset、ORT设置、输入预处理、固定输入hash |
| `NodeRecord` | onnx_node_id、name、op_type、attributes、input/output tensor ID |
| `HwOpRecord` | hw_op_id、parent node、stage、tile、前驱后继、JSON/execplan ID |
| `TensorRecord` | tensor_id、producer/consumer、logical shape/dtype、qparams、raw文件/hash |
| `LayoutRecord` | tensor_id、端口、slice partition、padding、轴序、packing、bank/remap、inverse状态 |
| `ConfigRecord` | hw_op_id、模板、patched JSON、bitstream、mapping、字段/版本/hash |
| `ExecutionRecord` | backend、输入包、开始/结束/退出码、日志、physical D、版本 |
| `ResultRecord` | logical D、reference ID、比较策略、首错和结论 |
| `ContractRecord` | contract类型、版本、candidate/approved状态、来源、批准人/时间、hash |
| `StageAttempt` | stage、对象ID、attempt编号、输入hash集合、代码版本、状态、错误码、产物hash |

不能只用一个全局线性状态描述整个网络：不同 `hw_op_id` 可以并行，hardware也可能在simulator通过后暂时blocked。采用两层状态：run级聚合状态，以及每个对象/阶段不可变的 `StageAttempt`。

```text
pending -> running -> succeeded
                   -> failed
                   -> blocked
                   -> skipped（仅显式允许的非目标阶段）
```

阶段依赖仍按 `declared -> golden -> physical -> config -> simulated -> hardware -> compared` 推进，但状态记录在每个 `hw_op/tensor/backend` 上。重跑创建新attempt，不覆盖旧记录；run状态由必需attempt聚合。任何缺文件、hash变化、字段未解析、inverse失败、模拟器非零退出或结果不一致都必须进入明确失败状态；不得打印警告后继续伪造后续成功产物。

### 4. CLI和阶段接口

统一入口计划为：

```powershell
.\.venv\Scripts\python.exe -m resnet50_pipeline.cli inspect-model ...
.\.venv\Scripts\python.exe -m resnet50_pipeline.cli lower ...
.\.venv\Scripts\python.exe -m resnet50_pipeline.cli golden ...
.\.venv\Scripts\python.exe -m resnet50_pipeline.cli relayout ...
.\.venv\Scripts\python.exe -m resnet50_pipeline.cli gen-config ...
.\.venv\Scripts\python.exe -m resnet50_pipeline.cli run-sim ...
.\.venv\Scripts\python.exe -m resnet50_pipeline.cli gen-execplan ...
.\.venv\Scripts\python.exe -m resnet50_pipeline.cli run-hw ...
.\.venv\Scripts\python.exe -m resnet50_pipeline.cli compare ...
.\.venv\Scripts\python.exe -m resnet50_pipeline.cli run ...
```

每条命令只消费上一阶段manifest和显式参数，输出更新后的manifest与阶段产物；`run`只是按顺序调用子命令，不另写一套逻辑。

所有backend实现统一能力探测接口：`probe()`、`version()`、`capabilities()`、`prepare()`、`run()`、`collect()`。能力至少声明支持的op、dtype、slice数、JSON/bitstream版本、中间dump和确定性；不支持的组合在执行前失败，不得运行到中途才发现。

### 5. 统一产物契约

```text
artifacts/<run_id>/
  manifest.json
  metadata/environment.json
  model/
  raw_golden/<onnx_node_id>/
  subop_golden/<hw_op_id>/
  physical/<hw_op_id>/sliceXX/
  configs/<hw_op_id>/
  simulator/<hw_op_id>/
  execplan/
  hardware/<hw_op_id>/
  compare/<hw_op_id>/
  logs/
```

所有数据文件必须有shape、dtype、元素数、byte order和SHA-256；物理数据还要记录逻辑坐标到slice/bank/address的provenance。禁止脚本通过目录排序、文件名前缀或全局计数器猜关联关系。

阶段缓存以“输入文件hash + manifest片段hash + contract hash + 三仓commit + 集成代码版本 + backend版本”为key；`--resume`只复用完整匹配且已成功的attempt。任何key变化都使本阶段及下游失效。产物先写临时文件，校验完成后原子发布，避免中断留下貌似完整的数据。

## 工作包和阶段门

本节 W0~W9 是实际执行顺序和交付批次；后文 A~I 是按领域展开的长期需求与验收细则。推进状态以 W/G 编号为主，查某一领域的完整规则时再阅读对应 A~I 章节。

### W0：搭建空流水线骨架【第一交付，难度：中】

目标：不依赖正式ONNX和硬件，用mock模型/adapter把全部阶段接口和失败状态跑通。

细分：

1. 新建上述目录、包、CLI和异常类型。
2. 处理根目录版本控制：建立根集成repo边界和 `repos.lock.json`，保留三个子repo现有dirty状态，不将其静默纳入根repo。
3. 新建 `pyproject.toml`，登记包、CLI、Python版本、测试和静态检查；锁文件继续作为可重建环境真值。
4. 实现manifest dataclass、JSON序列化、schema version、引用校验和schema迁移入口。
5. 实现artifact manager、原子写入、hash、日志、run_id、attempt和确定性环境记录。
6. 定义 `LayoutTransform`、`ConfigBackend`、`SimulatorBackend`、`HardwareBackend` 及backend capability接口。
7. 建立 `architecture/quantization/backend` 三类contract和candidate/approved状态；未批准contract只能驱动合成实验，不能生成“硬件验收通过”。
8. 实现阶段DAG、resume/cache key、下游失效和失败聚合。
9. 建立mock graph、mock tensor和mock backend；验证成功、缺文件、hash变化、能力不支持和backend失败五种路径。
10. 配置最小测试入口和CI骨架；所有测试只写临时目录，硬件/大模型测试默认不进入普通CI。

验收门 G0：

- `cli --help`和全部子命令存在。
- mock run生成完整目录和manifest，状态严格推进。
- 人为删除输入或令backend失败时流水线非零退出，后续阶段不执行。
- 核心包不导入三个参考仓库也能运行骨架测试。
- `repos.lock.json`和环境/contract hash进入manifest；任一版本改变会使下游缓存失效。
- backend不支持某op/dtype/version时在prepare前明确失败。
- schema旧版本要么可迁移，要么给出明确不兼容错误，不能静默按新结构读取。

当前状态（2026-07-11）：**G0已通过**。W0共11项测试通过；CLI、完整mock DAG、稳定对象引用、contract/backend能力探测、artifact原子写入、失败阻断、cache/resume、源码/环境/contract/三仓hash失效和旧schema处理均已验证。

### W1：冻结外部规格【与W0并行，难度：外部阻塞】

1. 取得正式ONNX、固定输入和预处理。
2. 冻结16-slice RTL/ISA/寄存器/JSON版本。
3. 确认正式layout、SA/GA、bias/psum/requant语义。
4. 取得目标emulator和硬件load/start/wait/dump协议。
5. 记录来源、负责人、版本和hash；未确认项不得填默认值冒充批准规则。
6. 将结论写入 `contracts/*.json` 和 `.agents/decisions/ADR-*.md`；每条字段标记candidate或approved，记录证据与适用commit。

验收门 G1：权威资料可定位、可重放，架构版本不再从冲突旧文件混选；architecture、quantization和backend contract均通过schema且关键字段为approved。W2可在candidate contract下做软件实验，但W5目标bitstream和W8硬件验收必须等待对应approved contract。

当前状态（2026-07-11）：

- **已完成**：从官方ONNX Model Zoo镜像下载并通过checker；模型SHA-256为 `c234f30975989788b4405f25253275aae247ab6dbdd34aaa69ab0a59ff76f6d0`，IR 4、opset 12、78节点、366 initializer，无external data。
- **已完成**：算子统计与旧计划完全一致：2 Quantize、53 QLinearConv、1 MaxPool、17 QLinearAdd、1 GlobalAveragePool、1 Flatten、1 QLinearMatMul、2 Dequantize。
- **已完成**：暂定旧脚本预处理contract；仓库 `cat.jpg` 生成 `[16,3,224,224]` float32输入并由ORT 1.27 CPU生成 `[16,1000]` 输出，模型/图片/输入/输出hash已写入 `contracts/model_baseline.json`。
- **已完成**：从模型确认53层Conv语义均为UINT8 activation、INT8 weight、INT32 bias、per-output-channel weight scale，全部weight zero point为0；input/output zero point并非全部为0。
- **已记录**：`contracts/model_baseline.json`、`contracts/quantization.json`、`contracts/architecture.json` 和 `.agents/decisions/ADR-001-model-and-preprocessing-baseline.md`。
- **未完成/仍需外部**：目标RTL/ISA/register-map版本、批准物理layout、硬件requant和qparams传递、NDPFuncModel/官方emulator关系、硬件load/start/wait/dump协议。

W1的模型子任务已完成，但G1尚未通过；architecture/quantization/backend关键硬件字段仍是candidate/unknown。W0和W2可并行继续，W5目标bitstream与W8硬件验收不得据此提前宣布完成。

### W2：小Conv纵向软件闭环【第二交付，难度：高】

目标：完全不依赖正式ResNet模型，让一个小Conv完成 raw→physical→functional model→logical D。

当前状态（2026-07-11）：第1～3项和第7项的软件候选实现已完成。标量循环、im2col/einsum与ONNX Runtime在QLinearConv样例上bit-exact；NDP DRAM地址正逆公式、16-byte transfer拆分、显式byte-stride transaction、逐字节provenance，以及1/4-slice activation-C/weight-output-K候选layout均已通过round-trip。当前20项测试通过。该layout仍为 `w2_ndp_ring_candidate_v1` candidate，NDP functional model尚未消费physical image，因此G2未通过、16-slice尚未扩展。

细分：

1. 用纯NumPy和CGRA QNN语义各写一份独立uint8×int8 Conv参考，覆盖int32 bias/psum和requant。
2. 准备零值、递增值、负weight、0/255、rounding tie、饱和和tail fixture。
3. 为DRAM slice/bank和RDAG/WRAG transaction编写地址序列/provenance单测。
4. 修复 `per_slice`、物理slice offset和multi-transaction地址。
5. 修复A/B符号、纯整数psum、`.asctype`、`np.float128`和branch逻辑。
6. 用LC `last/last_index` 修复最终reduction；实现requant、INT8 packing和真实DRAM writeback。
7. 实现小Conv forward/inverse layout，保存physical D和logical D。
8. 在quantization contract中同时保存ONNX原始float scale/zp和硬件派生multiplier/shift；明确运算顺序、中间位宽、溢出、nearest-even、saturation和可选ReLU位置。
9. 固定随机seed、数组内存序、线程数和参考实现版本；同一fixture重复执行至少两次验证确定性。

验收门 G2：1/4 slice小例中，NumPy=QNN=NDP functional model逐坐标bit-exact；所有物理字节能反查逻辑坐标。16-slice只在G2后扩展。

### W3：正式模型解析、lowering和全节点golden【难度：高】

1. 最小修复 `layout_buffer.py:201`，并隔离 `cgra_python` eager import。
2. 参数化 `golden.py` 的模型、图片和输出路径；固定ORT provider/优化设置。
3. ONNX shape inference，建立稳定node/tensor ID和initializer引用。
4. 定义QLinearConv、MaxPool、QLinearAdd、GlobalAveragePool、MatMul、Dequantize、View的lowering插件。
5. 保存每个节点全部运行时input/output；生成首/中/末K psum、sum和requant subop golden。
6. 对旧77原语逐一映射，不再依赖328项字典插入顺序。
7. 处理多输入/多输出、空名字、initializer复用、图优化融合和控制模型外部数据；每个raw output保存原始ONNX名称与稳定ID双映射。
8. 记录ORT版本、provider、图优化等级、intra/inter-op线程、随机seed和预处理代码hash，保证重放一致。

验收门 G3：任一ONNX node可查全部hw_op；任一hw_op结果可反查逻辑tensor；保存结果可由独立软件公式重放。

### W4：逐算子16-slice relayout【难度：高】

实施顺序：

1. Quantize/Dequantize/View：先建立简单端口、zero-copy和FP32/UINT8 packing规则。
2. Conv：activation、OIHW weight、bias/qparams、psum和D；处理im2col、C/K tile、padding、tail和ring。
3. MaxPool：窗口、padding、channel pack和tail。
4. QLinearAdd：两分支layout兼容、广播和各自qparams。
5. GlobalAveragePool：sum中间值、reduction和requant。
6. MatMul/dense：feature、weight、bias、K tile psum和1000类tail。

每个插件必须同时实现 `forward()`、`inverse()`、`explain_coordinate()` 和 `validate()`。

layout描述不能只写名称，必须能给出逻辑坐标→slice/bank/byte address的可执行公式、padding/tail来源、lane内端序和逆公式；对于zero-copy必须证明producer D与consumer A的合同完全相同。

验收门 G4：最小shape、真实ResNet shape和tail shape均通过 raw→physical→raw bit-exact；上游D/下游A的零拷贝或转换责任有显式记录。

### W5：逐算子JSON和bitstream【难度：很高】

1. 建立 operator family→模板选择表，区分SA/GA、local/ring和首/中/末tile。
2. 实现字段级shape/qparams patch，不做文本字符串替换。
3. 先用 `config_generator_ver2.py/config_nse.py` 推导Conv关系，再映射目标JSON；旧bit位置必须经过版本审计。
4. 补INT8 Conv/MatMul、QLinearAdd、AvgPool requant、Quantize/Dequantize模板和handler。
5. 清除28-slice执行假设，目标资源固定16；若指令容器仍28-bit，明确高12位为0并测试。
6. 每个配置输出mapping review、字段范围检查、bitstream hash和架构版本。
7. 建立逐字段provenance表：字段名、模型/shape来源、推导公式、旧参考位置、目标寄存器/bit range、contract版本和测试ID。

验收门 G5：G1所需contract已批准；每个算子族至少一个微型shape和一个真实shape稳定生成bitstream；改变shape/qparams后所有相关字段联动，零unresolved control；每个非默认字段可回溯推导依据。

### W6：目标simulator闭环【难度：很高/部分外部阻塞】

1. 把NDP Conv改成读取manifest/JSON adapter的backend，禁止复制硬编码shape。
2. 对同一physical input比较直接functional配置和JSON adapter配置。
3. 接入官方/外部非Conv emulator；若不存在，先实现能覆盖ResNet所需LC/stream/buffer/SA/GA子集的最小解释器。
4. 统一超时、退出码、日志、physical D、inverse layout和logical D。
5. 逐算子通过后再组合 `Quantize→conv0→MaxPool`、残差块和head。
6. 外部进程backend必须限制工作目录、超时、最大日志/产物大小并捕获版本；不得依赖交互式shell或个人环境变量。

验收门 G6：每个hw_op的golden=simulator；整数bit-exact，浮点按manifest tolerance；重复运行稳定。

### W7：网络execplan和数据包【难度：高】

1. 让 `model_execplan` 消费统一manifest，不再手写77+实例。
2. 扩展schema/handler承载多输入、attributes、qparams和中间psum。
3. 处理tensor地址生命周期、残差分支、in-place/zero-copy和slice routing。
4. 每个实例生成独立patched JSON/bitstream/control write。
5. 输出execplan、cfg_pkg、SCA、Bank_data和emulator bundle，并引用相同hash。
6. bitstream/模板/数据/handler缺失时严格失败。
7. memory planner输出每个tensor的 `[base,end)`、alignment、bank/slice、live range和复用来源；验证不越界、不重叠、不读取已释放数据，并对地址单位转换做round-trip。

验收门 G7：单算子、conv0子图、一个残差块和head依次通过simulator整子图逐hw_op比较；无28-slice残留或静默截断。

### W8：硬件/RTL接入【难度：很高/外部阻塞】

1. 实现 `HardwareBackend` 的load config/data/execplan、start、wait、timeout、status和dump。
2. 固定byte/word地址单位、端序、slice/bank编号、装载顺序和输出有效时机。
3. 先跑小Conv单算子包；保存原始physical dump并inverse成logical tensor。
4. 支持单算子停止点或逐层checkpoint；记录硬件/RTL/固件版本和运行日志。
5. 硬件backend先执行capability/protocol probe和只读健康检查；任何写入/启动动作都绑定明确run_id和输入/config hash，dump后验证长度与地址范围。

验收门 G8：同一包重复运行稳定，小Conv和conv0达到golden=simulator=hardware。

### W9：全算子扩展、三方比较与整网回归【难度：高】

1. 比较器按manifest执行golden↔simulator、golden↔hardware、simulator↔hardware三组比较。
2. 报告首错node/hw_op/slice/逻辑坐标/物理地址/三方值，不给污染后的下游逐层猜因。
3. 回归层级：微型算子→conv0→残差块→stage→head→整网。
4. 建立正常图片、固定随机、0/255、负weight、饱和、rounding tie和tail测试集。
5. 输出机器可读JSON和人读Markdown；保存所有版本/hash/命令。
6. 维护 `coverage/operator_matrix.json`：每个operator family×shape类别×backend×阶段门的pass/fail/blocked状态和最近run_id，禁止用单个样例代表全家族完成。

验收门 G9：所有整数中间结果三方bit-exact；批准浮点结果在tolerance内；整网logits/分类结果一致且可一键重建。

## 工作包依赖和并行关系

```text
W0 骨架 ──> W2 小Conv软件闭环 ──> W4 Conv relayout ──> W5 Conv JSON
                                              │                 │
W1 外部规格 ──> W3 正式golden/lowering ───────┘                 v
                                                        W6 simulator
                                                             │
                     W4/W5 其他算子 <────────────────────────┘
                                                             │
                                                             v
                                                        W7 execplan
                                                             │
                                                        W8 hardware
                                                             │
                                                        W9 整网回归
```

- W0与W1立即并行；W1阻塞不妨碍W0/W2使用合成数据。
- W3依赖正式ONNX，但golden入口修复和manifest骨架可提前做。
- W4/W5按算子族并行实现，但每个算子必须单独通过G4/G5后才能进入W6。
- W8不能阻塞软件侧单算子闭环；硬件接口到位前持续积累可重放测试包。

## 强制质量门和停止条件

1. 没有subop golden，不开始对应INT8 JSON数值验收。
2. forward/inverse relayout不bit-exact，不进入simulator调试。
3. simulator logical D未通过，不进入硬件。
4. 单算子三方未通过，不扩残差块；残差块未通过，不扩整网。
5. 正式规则未确认时允许实现可替换adapter，不允许把候选值写成批准真值。
6. 当前NDP `.npy`/psum trace、旧ADD伪代码、FP16 SA JSON和bitstream成功均不得替代数值验收。
7. 任何阶段的missing、schema mismatch、hash mismatch、非零退出和value mismatch必须使用不同错误码并终止当前run。
8. 地址越界、live range重叠、端序/行宽不匹配和读取未初始化区域属于独立P0错误，不能归并为普通value mismatch。
9. 比较器自身必须用故意注入的shape/dtype/layout/value错误做自测，证明能报告正确首错和provenance。

## 方案审核结论与补充约束（2026-07-11）

审核结论：W0→W2纵向切片→逐算子扩展→execplan→硬件→整网的主路线合理，无需推倒重来；但原方案在版本控制、状态模型、架构/量化契约、恢复执行、地址安全和持续验证方面不足。以上条目已经合并进W0~W9，实施时还必须遵守以下总约束：

1. **单一计划编号**：只使用W0~W9和G0~G9维护进度；A~I仅是领域细则。旧M0~M7编号已移除，避免三套状态漂移。
2. **根集成层可版本化**：根repo边界、忽略规则和业务源码已经建立，三个参考repo独立保留，commit/dirty patch由lock和manifest记录；本地首版按操作者要求现在提交。
3. **契约先于硬件真值**：16 PE已确认，但字段位宽、layout、SA/GA、qparams、ISA等必须分别标candidate/approved；candidate允许软件实验，不允许宣称硬件配置完成。
4. **量化是一级接口**：scale/zp、bias、multiplier/shift、rounding、overflow、saturation和activation融合顺序必须版本化，不能散落在handler常量中。
5. **状态按对象和attempt记录**：网络中不同op可并行、失败、重试或等待硬件；旧attempt不可覆盖，run汇总不能掩盖局部失败。
6. **可恢复但不误复用**：resume只复用内容寻址完全匹配的成功产物；模型、输入、contract、代码、repo或backend任一变化都使下游失效。
7. **地址正确性独立验收**：数值相等无法证明没有越界/别名。memory plan和provenance测试必须先于整网执行。
8. **adapter必须自描述能力**：不支持的op/dtype/slice/version在运行前报错；不能把缺官方emulator伪装成模拟通过。
9. **测试分层**：普通CI只跑schema、hash、状态机、quant、layout round-trip、mock backend和微型Conv；正式ONNX、大数据、官方simulator和硬件使用显式集成/夜间任务。
10. **资源受控**：大tensor采用流式或memmap读写，日志设上限；artifact提供保留策略，默认保留manifest、报告和失败首错附近数据，不无限复制完整DRAM trace。
11. **覆盖可量化**：以operator coverage matrix和最近通过run为完成证据，不以文件数量、一个shape或bitstream成功作为完成证据。
12. **外部决策可追溯**：学长/RTL/硬件回答写入ADR和contract，包含问题、答案、证据、适用版本和批准状态；聊天结论不能成为唯一真值。

W0实现前还需把以上补充转成可执行的schema字段、测试用例和CLI失败路径；只创建空目录而没有这些约束，不算通过G0。

## 阶段 A：取得权威输入和目标接口

目标：取得后续无法从仓库内部推导的权威资料，冻结目标版本。

状态：模型/固定输入基线已部分完成 + 硬件接口外部阻塞。

难度：外部阻塞；资料到位后的整理难度为中。

任务：

1. 取得正式 `resnet50-v1-12-int8.onnx`、输入预处理约定和至少一组固定测试输入。
2. 尽量取得原 `tensor_dict.json`、DDR、旧 `.cu/.pkl` plan 和 golden；没有时由正式 ONNX 重建，不再等待不可恢复的本地历史。
3. 确认 `NDPFuncModel/conv_func` 与目标 JSON emulator 的关系；取得缺失的 `conv_config`、可运行 `hex_data`、目标 JSON/bitstream→LC/AG/Buffer/PE 参数映射。若它只负责 Conv，则另外取得其他算子的 emulator 入口。
4. 取得硬件或 RTL 的配置/数据/execplan 加载、start/wait、结果 dump 协议。
5. 确认目标为 16 slice，并冻结对应的资源数、字段位宽、GA opcode、DDR row、指令 mask 和寄存器表版本。
6. 取得一份批准的 INT8 SA/GA 最小配置和 activation/weight/bias/scale layout 示例。

验收标准：

- 所有资料有来源、版本、hash 和本地路径记录。
- emulator 样例可运行并产生可解析输出。
- 硬件/RTL 接口至少能完成一次加载和 dump，或明确记录外部负责人和阻塞状态。
- 架构参数不再从冲突的旧文件中混选。

当前状态：官方模型、固定图片、暂定预处理、batch=16输入和ORT最终输出已建立可重放hash基线，阶段B/C不再等待ONNX。W0/G0已完成；Conv功能模型仍缺原始输入/gitlink且数值链有缺陷，目标layout、emulator和硬件接口继续作为外部阻塞并与W1/W2/W3并行推进。

## 阶段 B：建立统一图、lowering 和产物契约

目标：建立 ONNX 节点、硬件原子算子、JSON 实例、execplan op 和三方结果之间的唯一映射。

状态：仓库中没有通用实现；旧手写计划可作为参考。

难度：高。难点是一对多 lowering、残差分支、量化常量和中间 psum 的身份管理。

任务：

1. 用 ONNX shape inference 读取节点、边、initializer、dtype、shape、属性和量化参数。
2. 定义稳定 ID：`onnx_node_id`、`hw_op_id`、`json_instance_id`、`execplan_op_id`。
3. 定义 lowering 表，例如 `QLinearConv -> first_k / middle_k* / last_k_requant`，AvgPool 和 MatMul 同理。
4. 定义统一 manifest，至少含输入输出 tensor、source、shape、dtype、qparams、raw/physical layout、slice、文件、地址和状态。
5. 定义产物目录，禁止继续依赖 `/cluster/home/...` 和硬编码 instruction index。

验收标准：

- 任一 ONNX 节点都能查到对应的全部硬件原子算子；任一硬件结果能反查 ONNX tensor。
- 分支、复用、Flatten/View 和一对多 lowering 不依赖字典插入顺序。
- manifest 通过 schema 校验，并成为 golden、relayout、JSON、execplan、simulator 和 hardware 的共同输入。

当前状态：待实现。旧计划已精确给出 77 个模型级原语及固定 tile，但绑定依赖 328 个有序字典项，不能直接作为正式 manifest。

## 阶段 C：生成完整 raw golden 和硬件子步骤 golden

目标：对每个 ONNX 节点保存 raw input/output，并为 lowering 后需要观察的 psum、sum、requant 等子步骤生成软件 golden。

状态：模型和最终输出基线已有；完整逐节点input/output和subop dump仍需实现。

难度：中高。ONNX 节点输出 dump 本身难度中等，正确处理融合、dtype/shape、子步骤和名称映射难度较高。

任务：

1. 以 `CGRA_SIM/testing/resnet-50-int8/golden_model/golden.py` 为 ResNet50 ONNXRuntime 基线进行扩展：保留其预处理、batch=16、ORT 执行和输出保存流程，改为给所有节点输出补正确 ValueInfo，不再使用手写名称清单和统一 UINT8 四维假设。
2. 固定 ORT 优化策略和输入预处理；保存模型 hash、ORT 版本和输入 hash。
3. 每个节点保存所有运行时输入、输出和 initializer 引用；标量量化参数也进入 manifest。
4. 用 QNN 软件参考生成 lowering 子步骤 golden，尤其 Conv/MatMul 的 int32 psum、AvgPool sum、Add/Conv requant。
5. 至少准备正常图片、固定随机输入、0/255、饱和与 nearest-even 边界用例。

验收标准：

- manifest 中每个逻辑 tensor 都有可读取文件，元素数、dtype 和 hash 正确。
- 对任一算子能重放软件计算并复现保存的 output。
- 子步骤 golden 的累加顺序、zero point、rounding、saturation 与批准的 lowering 一致。

当前状态：ResNet50 ONNXRuntime实现入口已经明确为上述 `golden.py`；官方模型和固定batch=16输入/最终输出基线已取得。但它只覆盖30个唯一节点名，runner只有21个checkpoint，通用 `func_validator.py` 仍有名称映射、地址和比较TODO。项目 `.venv` 已补齐依赖，当前源码入口首先被 `CGRA_SIM/cgra_python/layout/layout_buffer.py:201` 的既有 `SyntaxError` 阻塞；修复后进入全节点dump改造。

## 阶段 D：实现 ResNet 16-slice 数据变换

目标：把 raw tensor 转成 simulator/hardware 使用的物理格式，并能无损逆变换回来。

状态：参考规则部分已有；完整 ResNet 实现不存在，逐算子 relayout 属于本项目明确需完成的代码工作。

难度：高。主要风险是正式 layout 未确认、Conv weight/im2col、尾块和不同算子间 layout 衔接。

1. 以旧计划为基线：batch=16 时每 slice 一张样本；activation 按 N 切分；weight/bias/qparams 按需要复制或分片。
2. 为 activation、Conv weight、bias/scale/zp、psum 和输出分别声明 logical/physical layout。
3. 为每一种 ONNX/硬件原子算子分别实现 partition、padding、im2col/weight reorder、tile reorder、128-bit packing、bank/remapping；不能用一份通用 reshape 假定覆盖全部算子。
4. 实现严格 inverse partition/relayout/unpack/merge。
5. 输出 `install/opX/sliceYY/matrix_{A,B,C,D}_linearized_128bit.{bin,txt}` 和对应 manifest。
6. 为非 2 的幂 C/H/W、最后 1000 类和尾 tile 编写 padding/tailing 测试。

逐算子 relayout 清单（全部标记为**需完成**）：

| 算子族 | 必须实现的物理数据对象 | 状态 |
|---|---|---|
| QuantizeLinear | FP32 输入、scale/zp、UINT8 输出及其逆变换 | 需完成 |
| QLinearConv | activation、OIHW weight、bias、scale/zp、首/中/末 K tile psum 和 D | 需完成 |
| MaxPool | UINT8 activation、padding/tail、池化输出 D | 需完成 |
| QLinearAdd | 两个残差分支输入、各自 qparams、对齐/广播和 UINT8 D | 需完成 |
| QLinearGlobalAveragePool | activation、int32 sum/中间结果、requant 参数和 D | 需完成 |
| QLinearMatMul / dense Add | feature、weight、bias、qparams、psum 和最终 D | 需完成 |
| DequantizeLinear | UINT8 输入、scale/zp 和 FP32 D | 需完成 |
| Flatten/View | 验证是否物理零拷贝；若不是，完成显式重排和逆变换 | 需完成 |

每一行还要按实际 lowering 拆到具体 `hw_op_id`，分别覆盖 A/B/B'/C/D 端口；“该算子的输入已由上游排好”也必须在 manifest 中证明，不能据此省略 relayout 规则。

验收标准：

- raw→physical→raw 对所有测试 tensor bit-exact。
- 每个 slice 的元素归属、复制规则、padding 区和 128-bit 行内顺序可由 manifest 验证。
- 上一算子 D 与下一算子 A 的物理布局不一致时，明确由 remapping、后继 stream 还是显式 relayout 解决。

当前状态：DeepSeek relayout 仅覆盖 28-slice LLM；`relayout_layer0.py` 只是把已有单算子目录复制拼装并按固定表重排 28 个 slice，不会推导新 layout；`conv_layout.py` 只是 conv0 候选实验；`layout_buffer.py` 还是未完成原型且当前有语法错误；address-remapping registry 没有 ResNet 算子。新增 `NDPFuncModel` 给出了固定 Conv 示例意图采用的 activation 按 C 分片、weight/output 按 K 分片、16-byte DRAM subword、Buffer 列反序、padding/branch mask 和 4-slice activation ring；但其当前 slice 物理地址错误，只能作为待修复的第二份候选规格，不能作为已验证 relayout。它也不是 16-slice 通用布局，没有从 raw ONNX tensor 生成 `hex_data` 的实现。ResNet relayout 仍由本项目按上表逐项实现；阶段 A 需要提供目标 layout/端口规则和校验样例来裁决不同参考之间的差异。

## 阶段 E：完成 ResNet 单算子 JSON 和数值参数化

目标：为全部硬件原子算子提供可参数化 JSON、bitstream 和数值语义闭环。

状态：部分已有；核心 INT8 SA 模板不存在。

难度：很高。QLinearConv/MatMul 的 INT8 SA、bias/psum/requant 和逐层量化常量传递是核心风险。

1. 完成 fp32→uint8 Quantize、INT8 Conv、uint8 MaxPool、完整 QLinearAdd、AvgPool sum+requant、INT8 MatMul、单输入 Dequantize 和 View 规则。
2. 决定 Conv/MatMul 首/中/末 K tile 是多 JSON 还是配置状态，并写明中间 psum dtype/位置。
3. 扩展 execution-plan schema/handler 传递 per-layer/per-channel scale、zp、bias，或采用批准的 tensor-stream/逐层 JSON 协议。
4. 补 `operator_base_info.json`、control handler、必要的 remapping registry 和 per-op 说明。
5. 每个 JSON 检查 loop、LC-PE、stream、padding/tailing、buffer、SA/GA、constant、转换和 `CONFIG`。
6. 多个固定 seed 生成 bitstream，并检查 mapping review、字段范围和目标 RTL 版本。
7. 为 Conv 建立 `ndp-sim-ref` JSON 字段到 `NDPFuncModel` LC/AG/Buffer/PE 参数的 adapter；adapter 必须读取 manifest/配置，不得复制主入口中的硬编码 shape。

验收标准：

- 每类算子至少一个最小 shape 与一个真实 ResNet shape 能稳定生成 bitstream。
- 改变 shape/qparams 后，所有相关 loop/stride/constant 都被 patch，不存在 unresolved control。
- bitstream 成功之外，还必须通过阶段 F 的目标模拟器数值测试。

当前状态：42 个 JSON 只有 MaxPool、sum 型 AvgPool、固定样例 quant 和 fp32 输出 add-dequant 可局部参考；6 个 SA JSON 全是 FP16、bias=0。`NDPFuncModel` 证明 Conv 数据通路原型存在，但没有对应 JSON、qparams schema 或参数化入口。尚未开始新增目标配置。

## 阶段 F：接通目标 JSON/bitstream 数值模拟器

目标：真正执行目标 JSON/bitstream，并按 manifest 导出每个原子算子的物理和逻辑输出。

状态：Conv 有可读但未闭环的功能模型；通用目标 JSON/bitstream 解释器仍没有。旧 CGRA 功能模拟器不解释目标 JSON。

难度：很高。Conv 路径因已有数据通路模型而从“完全外部阻塞”降为“可修复、可适配”，但非 Conv 和 bitstream 级执行仍可能外部阻塞。

任务：

1. 先把 `NDPFuncModel/main_CONV_N2N.py` 拆成参数化 Conv runner：输入来自 manifest/physical files，循环、地址、slice 和 qparams 来自 adapter。
2. 修复 Conv 阻塞：正确判定最后 reduction、真正写回 DRAM、实现 uint8 activation×int8 weight、int32 psum、per-channel requant/nearest-even/saturation，去掉 INT8 路径的 FP16 packing，并把函数内直接使用的 `np.float128` 改成跨平台累加类型。
3. 为 4-slice 合成例和目标 16-slice 建立坐标级比较；补齐 `ActivationUnit.sse2_round_to_int()` 或统一调用项目 QNN 量化实现。
4. 对接 `model_execplan --export-emulator` 的 per-slice JSON/`dram_data.bin`，建立目标 JSON 字段→功能模型参数映射；若目标要求 bitstream 级解释，另加 decoder 层。
5. 封装统一 runner：加载、执行、超时、退出码、日志、physical D dump、inverse-relayout 和 logical D。
6. 非 Conv 算子先用小 MaxPool 确认是否存在统一 emulator；不存在时按优先级实现最小 JSON 数据流解释器或接入外部程序。

验收标准：

- 同一输入重复运行结果稳定。
- simulator 输出可映射到 `hw_op_id` 和逻辑 tensor 坐标。
- 单算子 golden=simulator；整数 bit-exact，浮点符合 tolerance。
- emulator 不在仓库时，阻塞必须记录为外部依赖，不能用 bitstream 生成成功替代。

当前状态：已定位 Conv 功能模型，但尚不能完成一次可信 Conv 输出：入口依赖未入库 `hex_data`；最后 reduction 判定错误；DRAM 写回被注释；INT8 输出仍按 FP16 packing；requant 未接入；A/B 符号与 ResNet 软件语义相反；固定 4 slice；当前 Windows NumPy 无 `np.float128`，而 PE 执行函数仍直接调用它。`write_emulator_bundle()` 仍只写输入包，不执行；非 Conv 的目标 emulator 源码/二进制和命令未找到。

## 阶段 G：生成 ResNet 网络级硬件 execplan

目标：从阶段 B 的 lowering manifest 自动生成完整 ResNet 网络级 JSON、per-instance 配置、地址、Bank_data 和目标指令流。

状态：框架已有，ResNet 前端和适配不存在。

难度：高。主要风险是 16/28 slice、三维 shape、量化 attributes、一对多 lowering、地址生命周期和失败容错。

方案：

1. 扩展 `OperatorSpec/TensorSpec` 支持必要 attributes/constants、多输入语义和稳定 tensor ID。
2. 把 28-slice 硬编码收敛到目标 16 slice；同步地址 planner、指令 mask、slice routing 和测试。
3. 从 manifest 生成网络 JSON，不手写 77+ 实例和 source 关系。
4. 对每个实例 patch shape、qparams、base address、remapping 并重生成 bitstream。
5. bitstream/模板/寄存器 unresolved 时严格失败；修复 pipeline 当前打印失败后继续的问题。
6. 先生成单算子、`Quantize→conv0→MaxPool`、一个残差块、head，再扩整网。

验收标准：

- execplan 的每个 op 都能追溯 ONNX node/hw_op，输入 source 和地址无歧义。
- 生成 `execplan.txt`、说明、patched JSON、cfg_pkg、sca_cfg、Bank_data 和 emulator bundle。
- 没有 28-slice 残留、静默整除截断、缺模板或 unresolved control。
- 用阶段 F 模拟整子图时，逐原子输出与 golden 一致。

## 阶段 H：接通 RTL/硬件运行与结果导出

目标：把同一份 Bank_data、配置和 execplan 加载到 RTL/硬件，并导出每个验收点结果。

状态：仓库中没有完整 runner/testbench/dump 规范；外部阻塞。

难度：很高/外部阻塞。难点取决于硬件接口成熟度和是否支持中间 checkpoint。

方案：

1. 实现或接入 load config/data/execplan、start、wait、timeout、状态检查和 dump。
2. 明确 byte/word 地址、bank/slice 编号、端序、文件行宽和输出有效时机。
3. 若整网不能逐层 dump，先用单算子 execplan 或插入调试停止点完成逐算子验证。
4. 保存硬件版本、时钟、配置 hash、输入 hash、日志和 raw dump。
5. 将物理 dump 逆变换为逻辑 tensor。

验收标准：

- 同一包可重复运行并得到稳定结果。
- 每个验收点可追溯到 manifest、地址和配置版本。
- 单算子先达到 golden=simulator=hardware，再扩大子图。

## 阶段 I：三方比较、回归和整网完成

目标：自动比较 golden、simulator、hardware，定位第一处差异，最终使逐算子与整网三者一致。

状态：只有旧 runner 的 21 个硬编码 checkpoint和 LLM 物理文件二方比较脚本；通用实现不存在。

难度：中高。比较算法不复杂，难点是统一命名、逆 layout、checkpoint、地址和上游错误传播。

方案：

1. 比较器消费统一 manifest，先 inverse-relayout，再按逻辑坐标比较三份 tensor。
2. 整数 bit-exact；浮点报告 max abs/rel、首错、误差分布和 tolerance。
3. 报告 `onnx_node_id/hw_op_id/slice/逻辑坐标/物理地址/golden/sim/hw`。
4. 建立单算子、conv0、残差块、head、整网分层回归；第一处失败即停止后续归因。
5. 产出机器可读 JSON 和人读 Markdown 汇总。

最终完成标准：

- 正式测试集上每个验收原子算子的 input/output 可追溯。
- 所有整数中间结果三方 bit-exact；批准的浮点结果在 tolerance 内。
- 整网最终 logits/分类结果三方一致。
- 从正式 ONNX 到所有测试产物能用记录的命令重新生成，不依赖个人绝对路径。

## `NDPFuncModel` 问题账本与逐项解决顺序

整库复审后，W2 不应直接从“把 4 slice 改成 16”开始。当前已有 trace 和 `.npy` 由错误物理寻址生成，若先扩规模只会放大不可验证状态。按以下顺序解决：

| 顺序 | 问题 | 为什么先做/后做 | 解决与验收方案 | 难度 |
|---:|---|---|---|---|
| 1 | 建立独立最小 Conv 真值 | 现有 `extracted_*.npy`、psum trace 不可信，缺少判错基准 | 自建 1 个小 UINT8×INT8 Conv，保存 activation/weight/int32 bias、逐 K psum、requant D；NumPy/QNN 双实现互验 | 中 |
| 2 | 修复 slice/bank 物理寻址 | 当前四个逻辑 slice 都读物理 slice0，bias slice1~3 为空 | `per_slice` 包含 bank 维度；所有 DRAM→AG/AG→DRAM 地址显式带 slice；逐 byte provenance 验证每个 slice 唯一 | 中 |
| 3 | 修复 RDAG/WRAG transaction 地址 | 多 transaction stride 当前被计算后丢弃，真实 shape 会触发 | 对连续/非连续、1/2/多 transaction 编写地址序列单测，再修最终 transfer address | 中 |
| 4 | 固化 INT8 数值语义 | signed A×unsigned B、float32 中转会使 psum 非 bit-exact | activation uint8、weight int8、bias/psum int32，全程整数；明确溢出/branch；删除 `np.float128` 依赖 | 中高 |
| 5 | 修复 reduction 与输出坐标 | 最后 reduction 条件永假，当前没有真实 D | 使用各 LC 的 `last`/`last_index` 或词典序末状态，逐输出坐标只 flush 一次；小真值逐坐标核验 | 中 |
| 6 | 实现 requant 与真实 writeback | 没有 UINT8 D 就无法和 ResNet golden 比较 | per-channel multiplier/shift 或批准公式、nearest-even、zero-point、saturation；INT8 packing；真实 DRAM write 并 inverse-relayout | 高 |
| 7 | 恢复配置驱动 | 当前主程序完全绕过 `config/` 和 JSON | 先恢复 `graph` pyc 对应源码或取得 `conv_config`；把 `config_nse.py` 固定 Conv 逐字段映射到目标 JSON，明确架构版本，不复制整段位串 | 高 |
| 8 | 从 4 slice 扩到确认的 16 PE 阵列 | 只有前 7 步正确后，扩规模结果才可判定 | 参数化 slice 数、ring count、C/K partition、tail；1/4/16 slice 对同一逻辑 Conv 结果一致 | 高 |
| 9 | 接 ResNet conv0 与全层 relayout | 小模型通过后才能区分算法问题和布局问题 | raw ONNX→forward relayout→JSON runner→physical D→inverse→QNN/ORT golden；再覆盖全部 Conv shape | 很高 |

其中第 1~6 项不需要等待外部 `hex_data`：可以用小合成数据完成并形成回归。外部样例改为“兼容性验收资料”，不再作为修复当前模型的硬前置。第 7~9 项仍需要确认目标架构版本、正式 layout/端口和 JSON/bitstream 关系。

## 当前最高优先级请求

需要统一向学长或硬件侧确认/索取：

1. 提供目标16-slice RTL/ISA/register-map对应的源码commit或文档版本，覆盖资源数、字段位宽、opcode、DDR row、地址单位和指令mask。
2. 审核我们后续生成的最小INT8 Conv候选配置，确认activation/weight/bias/qparams/psum/D正式物理layout、PEA物理A/B端口、requant/rounding/saturation和writeback语义。模型语义已确定为UINT8 activation×INT8 weight×INT32 bias，不再询问ONNX数学类型。
3. 确认逐层qparams由constant patch、tensor stream、control write还是逐层静态JSON传递；若已有批准样例，请提供对应配置和目标版本。
4. 确认 `NDPFuncModel/conv_func` 是否为认可的Conv emulator，以及是否已有官方JSON/bitstream或非Conv emulator。`conv_config` URL、原 `hex_data` 和预期D只作为兼容性资料，可选提供。
5. 提供硬件/RTL的load config/data/execplan、start、wait/timeout、error/status和结果dump协议或现有runner/testbench。

正式模型、固定输入、旧脚本预处理、ONNX算子组成、Conv量化tensor类型、LC/`last_index`、`[start,end)`、stream端口顺序、byte stride、padding有效范围和lane内小端packing已经自行确认，不再重复提问。旧运行产物不再作为开工前置。
