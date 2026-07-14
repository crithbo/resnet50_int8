# ResNet50 INT8 端到端实施计划

最后更新：2026-07-13

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
- 每完成一个阶段，更新本文件的状态，并在 `history.md` 追加记录；凡形成Git提交，台账必须包含仓库、完整hash、父提交、范围、验证结果和精确回退位置。
- Git按改动规模分级：不改变行为、接口、schema/合同、layout/qparams、依赖锁或产物hash的微小文字/注释/格式修正不单独提交；范围明确且可聚焦验证的较小代码、测试、规则或文档语义改动做本地原子提交；阶段门、跨模块/跨仓重大集成、关键硬件合同、重要恢复检查点，或操作者明确要求时，才批量推送到操作者控制的GitHub仓库或fork并核对远端hash。微小改动可以合并进下一次相关本地提交，但必须在任务报告中说明。
- 尽量只保留必要工作树，不为备份额外创建clone/worktree/zip。冗余副本只有在无唯一未提交内容、全部需保留提交已推送、恢复路径验证通过且操作者批准具体绝对路径后才能删除；所有提交历史保留，不通过reset/rebase/filter/强推或裁剪历史释放空间。
- 并行协作采用“Local集中集成+tracked-only worktree”模式：managed worktree只使用Git跟踪文件和`.worktreeinclude`交付的小型固定元数据，禁止通过junction/symlink共享Local `.venv`、三个参考仓或产物。需要这些依赖、正式W3 tensor、整网报告或全量回归的任务只在Local执行；setup对非Local调用硬失败。项目配置使用自动审批reviewer而非全权限；达到本地提交门槛的任务只在结束时集中一次Git写操作，纯微小改动不强制单独提交。
- 当前冗余 `artifacts/smoke/NDPFuncModel` worktree已按批准删除；主仓 `main` 与NDP `conv_func` 已推送到各自Private仓并通过GitHub完整commit页面核验。CGRA的4项状态已证明仅是Windows权限位噪声，现已干净并锁定正式upstream，无需Private镜像。

## 当前总体状态

- **已通过**：W0/G0集成骨架，W2/G2小Conv候选软件纵向闭环，W3/G3正式图/lowering/全节点与subop golden。
- **部分通过**：W1已冻结正式候选模型、固定输入、预处理和软件量化事实；目标RTL候选已选`Trassic2.0_RTL@e3bdebba...`和28-slice。candidate审计已固定权威top/filelist、命令/WREG、HIGH/LOW、DRAM、SA/GA及运行接口的静态证据，但clean elaboration、正式端口layout、量化/requant、JSON/emulator和板级协议未批准，所以G1仍未通过。
- **当前主线**：ADR-007已由操作者采用。旧16-slice W4的12个candidate、93边审计和成本报告已隔离为历史证据；审计框架、生命周期/alias算法和逻辑比较器继续复用。C0/C1及C2逐算子布局已完成：14个RTL28 candidate layout覆盖simple、view、conv、maxpool、add、global_average_pool、matmul七个家族；QLinearAdd的双残差分支、六个独立qparam端口、正式广播范围、D布局和双输入同时活跃alias约束已有确定性回归，根仓176项测试通过。下一步单线程进入RTL28整网C3审计。G4=`not_passed`、`w5_authorized=false`；不生成正式W5 JSON/bitstream。
- **当前边界**：W2只证明小合成Conv的golden=NDP functional model；W3公式重放仍属于golden侧。当前没有任何正式ResNet算子达到golden=target simulator=hardware。

### 接手进度总表

| 工作包 | 门状态 | 已完成边界 | 接手动作 |
|---|---|---|---|
| W0 | G0通过 | manifest/contract/backend/artifact/cache/resume/mock DAG | 不重做，只回归 |
| W1 | G1未通过 | 模型、固定输入、预处理、ONNX量化事实；已选28-slice RTL并完成必要candidate静态审计 | 补clean elaboration、量化/端口/固件/板级批准合同 |
| W2 | G2通过 | 1/4-slice小Conv候选layout和NDP functional数值闭环 | 作为W4 fixture，不外推为硬件规格 |
| W3 | G3通过 | 78节点、133 hw_op、79 runtime tensor、55内部tensor、旧77映射 | 不重跑大artifact，除非hash/合同失效 |
| W4 | 旧16-slice readiness历史通过；28-slice重开/G4未通过 | C0/C1/C2逐算子布局完成；14个RTL28 candidate覆盖七个家族，正逆布局、容量、tail、广播与alias负例已回归 | 单线程重审RTL28 93边/成本/生命周期；不进W5 |
| W5～W9 | 未通过 | W9通用比较器基础设施已前置完成；其余仅有参考框架或mock接口 | 等待对应前置门和真实结果通过 |

### 当前可立即执行队列

1. 【已完成】终审16-slice泄漏：current layout registry只含RTL28/28，公共layout不导出旧16类；旧通用`conv_coverage.py`、`network_dry_run.py`和`w4_profiles.py`显式标为legacy16-only并由自动回归约束。
2. 【已完成】按P4使用三个共享Local协作子任务，严格隔离Conv、MaxPool+GAP、MatMul的实现/测试/候选报告文件；子任务未编辑公共合同、`.agents`或Git。
3. 【已完成】Local主任务依次复核三路结果，统一更新公共`layout.py`、`architecture.json`、coverage和G4插件登记；随后单线程完成QLinearAdd，当前为14个candidate/0个planned，七个必需布局家族均已登记。
4. 【下一步】进入C3，重新生成RTL28 transition、93边、91 qparam链、16个残差Add、生命周期/alias和性能成本报告；仍不读取W3大tensor、不生成正式W5产物。
5. 可独立推进W1的clean elaboration、量化/端口/固件/板级批准合同；没有approved合同不得宣布G4/G5通过。若模型、预处理、量化公式或lowering变化，先列出全部失效manifest/hash和下游产物。

Local执行环境已从事故前ZIP选择性恢复并重新验收：Python 3.12.13、`pip check`、三个锁定参考仓和根测试均通过；没有恢复任何managed-worktree junction。后续依赖任务可使用Local主任务或共享目录协作子任务，独立managed worktree仍只允许tracked-only工作。

## 总体实施架构：先骨架，后纵向闭环

### 1. 集成边界

新增代码放在工作区根目录的独立集成层，不把新流水线继续散写进三个参考仓库：

```text
resnet50_int8/
  pyproject.toml               # 新建：集成层包、CLI、测试和静态检查入口
  repos.lock.json              # v0.2：三仓upstream/private mirror/branch/commit/dirty状态
  resnet50_pipeline/          # 新建：唯一端到端集成层
  tests/                      # 新建：单元、集成、回归测试
  schemas/                    # 新建：manifest/config/result JSON schema
  tools/                      # 仓库恢复与验证等维护入口
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
- 仓库恢复合同已升级到lock 0.2和独立schema；`tools/sync_repositories.py verify`只读核验三仓，显式`sync`才克隆/检出。脚本优先Private镜像、采用partial clone、拒绝路径越界及脏工作树，当前三仓逐项验证通过。

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
2. 冻结28-slice RTL/ISA/寄存器/JSON版本；当前候选固定`Trassic2.0_RTL@e3bdebba95dec36ee8eba43caa92a326a88392cd`。
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
- **已完成候选选择**：审查`master/dc/xilinx`后选定最新且功能更完整的28-slice `master@e3bdebba...`；其活动参数、七小环/大环拓扑和28-bit mask已定位。
- **未完成/仍需外部或权威工具链**：`NDP_Top.sv`/`NDP_Top_new`命名闭合、clean elaboration、批准物理layout、硬件requant和qparams传递、NDPFuncModel/官方emulator关系、硬件load/start/wait/dump协议。

W1的模型子任务已完成，但G1尚未通过；architecture/quantization/backend关键硬件字段仍是candidate/unknown。W0和W2可并行继续，W5目标bitstream与W8硬件验收不得据此提前宣布完成。

### W2：小Conv纵向软件闭环【第二交付，难度：高】

目标：完全不依赖正式ResNet模型，让一个小Conv完成 raw→physical→functional model→logical D。

当前状态（2026-07-12）：**G2已通过**。同一带padding、C/K tail的确定性小Conv已分别以1-slice和4-slice执行；标量NumPy、im2col、ONNX Runtime、直接加载的CGRA QNN rounding和 `NDPFuncModel@35eab40` 在全部84个int32 accumulator及UINT8 D上逐元素一致。NDP参数化runner实际经过DRAM→input Buffer→SpecialPEA→ActivationUnit→output Buffer→DRAM，ring LC末态、per-channel requant、物理D覆盖和inverse logical D均验证；每个region的全部物理字节均能解释为data/tensor-padding/alignment并落在正确slice。G2只批准W2小Conv软件候选合同，不批准目标JSON/bitstream、正式硬件layout或旧固定56×56主入口；其4-slice fixture作为ADR-007七小环实现的最小数值基线。

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

验收门 G2【2026-07-12通过】：1/4 slice小例中，NumPy=QNN=NDP functional model逐坐标bit-exact；所有物理字节能反查逻辑坐标。证据为根仓28项、NDP 14项全量回归及1/4-slice同fixture完整D差分。现在可扩展为七小环/28-slice调度，但W5目标JSON仍受G1硬件合同约束。

### W3：正式模型解析、lowering和全节点golden【难度：高】

当前状态（2026-07-12）：**W3/G3已通过**。正式ONNX图解析得到78节点/617张量，78节点由8类插件lower为133个语义hw_op和55个内部tensor。正式batch16保存1个图输入+78个node output；55个内部INT32 tensor包括53个Conv accumulator、1个GlobalAveragePool centered sum和1个MatMul accumulator。独立公式已重放全部78个节点：55个内部累加/求和后requant、17个QLinearAdd affine requant、2个Quantize、2个Dequantize、1个MaxPool和1个Flatten，结果逐项等于ORT。旧77原语已按索引0..76逐项映射到当前node/hw_op，Flatten作为zero-copy明确排除。运行与subop合同分别见`contracts/golden_runtime.json`和`contracts/subop_golden.json`；根仓42项测试通过。旧`layout_buffer.py`通过零导入隔离但尚未修复；首/中/末K tile仍需W4/W5在目标tile/layout合同下把完整INT32边界细化为逐tile边界。

1. 最小修复 `layout_buffer.py:201`，并隔离 `cgra_python` eager import。【核心隔离已完成；子仓语法修复待独立提交/镜像】
2. 参数化 `golden.py` 的模型、图片和输出路径；固定ORT provider/优化设置。【模型/input.npy/output已完成；图片预处理沿用W1基线】
3. ONNX shape inference，建立稳定node/tensor ID和initializer引用。【已完成】
4. 定义QLinearConv、MaxPool、QLinearAdd、GlobalAveragePool、MatMul、Dequantize、View的lowering插件。【语义阶段已完成，硬件tile待contract】
5. 保存每个节点全部运行时input/output；生成accumulator、sum和requant subop golden。【已完成55个语义内部tensor；首/中/末K tile快照在W4/W5按批准tile合同细化】
6. 对旧77原语逐一映射，不再依赖328项字典插入顺序。【已完成；77项全部覆盖，Flatten单独记录为zero-copy】
7. 处理多输入/多输出、空名字、initializer复用、图优化融合和控制模型外部数据；每个raw output保存原始ONNX名称与稳定ID双映射。
8. 记录ORT版本、provider、图优化等级、intra/inter-op线程、随机seed和预处理代码hash，保证重放一致。

验收门 G3【2026-07-12通过】：任一ONNX node可查全部hw_op；任一hw_op结果可反查逻辑tensor；55个内部结果与全部78个node output均可由独立软件公式重放，并逐项匹配ORT。证据为42项根仓测试、重复运行55个内部文件hash全部一致，以及`legacy77_mapping.json`的77项全覆盖。

### W4：逐算子28-slice relayout与性能profile【难度：高】

当前状态（2026-07-14）：ADR-007已采用，旧16-slice W4物理候选全部失效为历史参考。W4按新目标重开；W0～W3不重做，旧93边集合、生命周期/alias算法和逻辑比较器复用，旧物理签名、容量与ring成本不复用。真实`topology28`和`profile28`调度底座、C0-01～07机器合同/legacy隔离、C1公共geometry与Quantize/Dequantize/View，以及C2的Conv、MaxPool、GAP、MatMul、QLinearAdd两profile正逆布局已经完成，176项根测试通过。现行G4、architecture/approval/backend合同、九份旧报告、旧生成器和RTL external evidence继续fail-closed。当前14个candidate layout覆盖七个必需家族，planned registry为空；RTL28 93边/成本、正式硬件批准和clean elaboration仍缺，因此G4未通过且W5未授权。下一步单线程进入C3整网审计。

#### 方案切换遗留修改清单（2026-07-13全工作文件夹复审）

审计边界：复核根仓现行Markdown/ADR、合同/schema、Python入口、测试、W4小型JSON报告、coverage与仓库恢复配置；只核对W3文件名/合同元数据，没有读取或重跑W3 `.npy`大产物。结论是旧16-slice不只残留在说明文字里，还能被现行审批validator、G4 audit和通用名称工具实际选择。最严重路径为：测试用虚构16-slice批准可通过现有validator，并按当前回归预期直接令`g4_status=passed`、`w5_authorized=true`。因此C0必须先封住错误放行，不能直接开始28-slice算子layout。

| ID | 优先级/阶段 | 已确认问题 | 计划修改 | 完成判据 | 状态 |
|---|---|---|---|---|---|
| ENV-01 | P0/C0前 | 已定位为commit `29da593...`引入的managed-worktree junction设计在宿主回收时穿透目标；Local四目录于16:25依次被清空 | 已解除全部残留junction，仅从13:00的项目ZIP选择性恢复`.venv`和三个参考仓；setup已改为非Local fail-closed，不覆盖主仓/`.git`/W3 | Python 3.12.13与`pip check`通过；三仓HEAD/dirty匹配lock；根测试通过；恢复来源、hash和事故边界已记录 | 已完成 |
| C0-01 | P0/立即 | 旧入口曾把结构合法的16-slice批准同时当成三项硬件门，并用两个无条件True补软件门 | 已将结构validator与G4授权分离；旧布局/93边/容量/alias结果只进入`legacy16_evidence`，当前门显式要求28架构、算子布局、93边、成本和clean elaboration | 合成旧批准仍可结构valid，但`current_gate_eligible=false`；当前readiness=fail、`G4=not_passed`、`w5_authorized=false`；无条件True已移除；109项测试通过 | 已完成 |
| C0-02 | P0 | 旧合同曾把16 slice、15次邻传、旧NDP内存/address order和旧W4 layouts/reports放在现行`known/candidate`空间 | `architecture.json`已升级为0.2；登记RTL28、SA 8×8、GA 4×4、28-bit mask、显式HIGH/LOW拓扑、精确profile与14个planned layout ID；静态RTL证据保持`candidate_unapproved`，旧16条目移入`legacy_layouts/legacy_evidence` | 当前target机器可读且唯一指向RTL28；旧16布局不在审批可选registry；真正未知、planned和静态未批准证据分开 | 已完成 |
| C0-03 | P0 | 旧批准schema、validator和fixture曾固定16 slice、旧`batch/ring_channel/mixed`及旧layout ID | schema与手写validator已同步迁移到28，精确交叉校验architecture版本、RTL入口/commit、拓扑、SA/GA、DRAM、mask、profile布局、numeric/ISA/runtime和证据；合成fixture只验证结构 | 28 fixture结构valid但`layout_evidence_complete=false`且不能打开G4；16/mixed/错误commit/错误布局均失败；没有生成真实`hardware_approval.json` | 已完成 |
| C0-04 | P0 | 旧`validate-contracts`只查schema版本、类型和根status，旧16主合同也会被报告valid | 已增加按contract type的版本策略和architecture语义validator；校验target、RTL入口、资源、显式拓扑、profile、DRAM、layout registry、legacy隔离与RTL审计hash；W0 mock复制小型RTL证据 | `validate-contracts`能拒绝旧16 target、算术/损坏拓扑、含混profile、legacy泄漏、错误RTL入口和address order；122项根测试通过 | 已完成 |
| C0-05 | P0/P1 | 旧九份报告曾缺统一target/superseded标记且只有4份tracked，合同引用无法从fresh checkout完整复核 | 九份原报告已保留原路径并统一加`legacy16/16/superseded_by_adr_007/current_gate_eligible=false`；`legacy16_index.json`登记全部hash/size，architecture交叉验证；全部小报告纳入Git | 合同和index逐字节复核九份报告；旧`all_profiles_pass=true`只能作为legacy诊断；current证据路径固定为architecture hash+content hash | 已完成 |
| C0-06 | P0/P1 | 旧network/verify工具名像现行入口且可覆盖旧报告；current G4输出缺target/profile/architecture身份 | 八个旧生成器现在必须显式`--legacy16`且只能写`artifacts/w4/legacy16/`；current G4报告携带RTL28 identity并支持内容寻址路径，拒绝覆盖旧快照 | 无显式legacy flag时在读取W3前失败；旧根快照不可写；current报告包含target/slice/architecture/profile IDs/hash | 已完成 |
| C0-07 | P1 | `repos.lock.json`曾未覆盖RTL28证据，backend只写target unknown | 采用tracked external evidence snapshot+hash方案：lock 0.3验证来源repo/commit、size/hash、内嵌非批准状态；backend登记不可执行candidate evidence，target sim/hw显式unapproved | `verify --evidence-only`可在无参考仓的fresh checkout验RTL快照；NDPFuncModel固定W2-only且不能冒充target backend | 已完成 |
| C1-01 | P1/C1 | `memory.py`无参数`DramGeometry()`静默默认16并固化旧address order；新代码易误用 | 已分离显式`TARGET_DRAM_GEOMETRY28`与`LEGACY_DRAM_GEOMETRY16`，并禁止无参构造；未批准地址解释保持candidate | current 28路径不存在隐式16默认；旧16回归显式申请legacy几何；141项根测试通过 | 已完成 |
| C1-02 | P1/C1 | `simple_layout.py`名称通用但硬要求16；`layout.py`公共入口仍正常导出所有旧16类 | 已用28公共Quantize/Dequantize/View实现替换current导出；旧实现迁至`simple16_layout.py`，明确只作历史回归 | current registry/public API只暴露28合同；旧测试继续在legacy suite通过；4个layout由planned转candidate | 已完成 |
| C2-01 | P1/C2 | Conv、MaxPool/GAP、MatMul仍只有旧16实现或W2小fixture，无法表达七个HIGH小环和LOW大环 | 三个共享Local子任务按互不重叠文件并行实现，主任务逐项复核并串行登记公共API/合同；8个layout由planned转candidate | 两profile正逆bit-exact、tail/对齐/容量/显式owner/transition负例通过；公共registry只剩Add；167项根测试通过 | 已完成 |
| C2-02 | P1/C2 | QLinearAdd仍缺RTL28双分支布局，不能验证残差owner、独立qparams、广播和双输入生命周期 | 主任务单线程实现两profile；只支持同shape rank-2/rank-4及`[N,F]+[F]`，其他广播fail-closed；A/B精确alias分别验证且同时活跃范围不得重叠 | 17个正式Add shape均可规划；Conv/既有Add/MatMul D兼容证明、双alias冲突与非冲突负例、正逆/tail/破坏性测试通过；2个layout转candidate | 已完成 |
| C3-01 | P1/C3 | `w4_profiles.py`和`network_dry_run.py`仍把16同时当batch、slice/owner和ring步数，无法表达`[3,3,2,2,2,2,2]`与GAP后唯一转换 | 等28 producer/consumer layout冻结后重写profile transition、93边、生命周期/alias与成本审计，不机械改名旧公式 | 报告以28真实owner/HIGH/LOW计算，区分模型batch16与slice28；旧网络报告只作legacy | 待执行 |
| DOC-01 | P1/C0同批 | `agent.md`曾混写旧main缺陷、参考工具权威性和错误下一步 | 摘要/优先级已改为C0完成→C1；明确ndp-sim只作框架参考、NDPFuncModel仅W2 backend，并区分上游固定入口与W2修复 | `agent.md`摘要、当前优先级和详细地图已一致 | 已完成 |
| DOC-02 | P1/C0同批 | 算子规则曾把W3全节点golden/manifest、ResNet lowerer和旧一sample一slice写成当前待办 | 相关段已标W1/W3前历史；当前事实为W3 79 runtime+55 internal/78节点与W2五层链已过，缺口改为28 physical、JSON实例/execplan adapter、target sim/hw | 不再诱导重跑W3或恢复旧16调度，旧脚本缺陷仍保留为历史证据 | 已完成 |
| DOC-03 | P1/C0同批 | ADR-004曾写有效批准加旧W4回归即可开G4并称software readiness通过 | 已增加ADR-007/C0覆盖：批准结构只是门的一部分，current布局/93边/成本/clean elaboration缺一不可 | ADR-004与现行G4代码/测试一致，当前readiness仍fail | 已完成 |
| DOC-04 | P2 | RTL审计文档早期worktree错误数和coverage目标身份容易被当现状 | 已把63 tests/16 errors标为隔离worktree历史观察；coverage新增target/profile/legacy superseded列；W0/W3段落改为历史/完成态 | 当前状态与历史快照可直接区分且未改写history事实 | 已完成 |

明确不修改/不重算：`golden_batch16`、`subop_batch16`、W3 metadata中的16是模型batch size；`profile28.py`的`BATCH_SIZE=16`及七组`[3,3,2,2,2,2,2]`正确；W0 mock的16只保留在`approved_for_w0_only` scope；`conv16_*`、`maxpool16`、`add16`、`avgpool16`、`matmul16`及明确命名测试作为legacy算法证据保留；W2的1/4-slice fixture继续作为软件基线；ADR-002/003/005和`history.md`已标历史的旧结论不改写；没有发现误生成的正式W5 JSON/bitstream。

执行顺序固定为：`ENV-01 → C0-01 → C0-02/03/04 → C0-05/06/07 + DOC-01/02/03/04 → C1-01/02 → 既定算子波次 → C3-01`。其中C0共享同一真值链，默认单线程；只有合同/API冻结且文件不重叠后才按P4并行。C0整体验收还必须满足：旧16 approval/layout/report无法进入current gate；合成fixture永不授权W5；缺真实approval或clean elaboration时继续`G4=not_passed`；所有小型合同/证据可从fresh checkout复核；根测试通过；全程不读取或重跑W3大tensor。

实施顺序：

0. 机器合同迁移：将架构合同、硬件批准schema/validator、fixture和G4入口切换为28-slice candidate口径；旧16-slice候选/报告只保留在显式legacy区域或历史文件中。冻结RTL commit、HIGH/LOW拓扑ID、七小环主profile和大环候选ID，但不伪造approved合同。
1. 建立`topology28`：精确编码RTL的七个HIGH 4-slice小环和一条LOW 28-slice大环，提供owner/step正逆查询并拒绝`(owner+step)%28`等伪物理拓扑。【已完成】
2. Quantize/Dequantize/View：建立七batch group、环内C/F owner、zero-copy和FP32/UINT8 packing规则。【C1已完成；group4x7与global LOW两个profile共4个candidate layout】
3. Conv：主体profile使用七小环；每组负责`[3,3,2,2,2,2,2]`个样本，activation按C owner环行4步/3 hop，weight在七组复制并按K owner分片，bias/qparams/P/D跟随K owner。【C2第一波已完成group4x7与global LOW候选】
4. MaxPool：保持batch group和channel owner，窗口/padding/tail在本地完成。【C2第一波已完成两profile候选】
5. QLinearAdd：两残差分支必须具有相同batch group、C/K owner和物理轴；A/B/D分别使用自身zero point tail，六个qparam端口保持独立，双分支地址同时活跃时不得冲突。【C2已完成两profile候选；正式范围为同shape rank-2/rank-4与dense `[N,F]+[F]`】
6. GlobalAveragePool：每个channel owner本地完成H×W centered sum/requant，不做不必要的跨组归约。【C2第一波已完成两profile候选】
7. MatMul/dense：先实现七小环一致profile；另实现`w4_global_ring28_candidate_v1`代表层，优先比较GAP后`[16,2048]×[2048,1000]`。【C2第一波已完成两profile候选及显式转换分类】
8. transition：不得在残差块内切profile；第一版整网最多允许一次小环→大环显式转换，优先放在GAP后，只有总成本/实测占优才启用。

每个插件必须同时实现`forward()`、`inverse()`、`explain_coordinate()`和`validate()`。layout描述必须给出逻辑坐标→物理slice/ring step/bank/byte address公式、padding/tail来源、lane端序和逆公式。

性能报告至少包含SA有效lane比例、activation字节×hop、weight复制倍数、每slice/整机DDR占用、3/2样本组barrier尾部、transition读写量和估算来源；估算不得标为cycle。确认per-slice queue/barrier语义后，可增加异步wavefront候选。

验收门 G4：最小shape、真实ResNet shape和tail shape均raw→physical→raw bit-exact；新93边、91量化链和16个残差Add重新通过物理兼容、生命周期和alias审计；HIGH/LOW映射匹配RTL；目标commit完成权威clean elaboration并形成带版本layout/ISA合同。未全部满足前G4=`not_passed`、W5未授权。

#### W4-28下一执行包与并行波次

**W4-28C0：机器合同迁移与legacy隔离，已完成。** ENV-01、现行G4 fail-closed、architecture/approval/backend合同、fixture、旧报告索引、旧工具guard、RTL external evidence lock和文档清理已经统一为28-slice candidate口径。当前满足：目标slice为28；固定`Trassic2.0_RTL@e3bdebba...`candidate来源；HIGH/LOW映射和两个profile ID可机器读取；旧16-slice证据显式legacy且不能被新批准合同选择或工具覆盖；28结构fixture不能授权G4；缺少28算子证据、真实批准或clean elaboration时仍为`G4=not_passed`、`w5_authorized=false`。

**W4-28C1：Quantize/Dequantize/View公共布局，已单线程完成。** 已冻结显式28/legacy16 geometry、七组sample owner、环内C/F owner、16-byte对齐、FP32/UINT8小端packing、qparam全slice副本、inactive/tail和zero-copy证明接口；DRAM geometry/address order继续标`candidate_unapproved`。group4x7采用HIGH owner顺序与固定3个sample存储槽，global profile采用LOW 28-owner顺序；Quantize/Dequantize按端口使用0、zero point或0.0语义padding。最小shape、正式`[16,3,224,224]`、`[16,2048,1,1]→[16,2048]`、3/2边界、feature tail、两profile、破坏性负例均bit-exact；141项根测试通过，全程未读取W3大tensor。

**并行判定门P4，2026-07-13已通过并完成第一波。** 三个共享Local协作子任务分别只修改Conv、Pool、MatMul的独立实现/测试/候选报告文件，未触碰`.agents`、公共合同、共享geometry/profile/topology或Git；主任务按Conv→Pool→MatMul顺序复核后串行集成公共API、合同和门审计。该隔离方式有效，未发生交叉覆盖。

**W4-28C2：逐算子布局已完成。** Conv、MaxPool/GAP、MatMul、QLinearAdd分别提供group4x7和global LOW的forward/inverse/explain/validate、正式shape容量计划、tail/对齐破坏性负例和小型确定候选报告。Add额外冻结六个独立qparam端口、三种语义tail、正式广播白名单，以及A/B同时活跃时逐slice地址区间不能重叠；默认两个Conv D即使字节兼容，只要地址相撞也会拒绝双alias。14个布局均为current candidate但仍未硬件批准；根仓176项全量测试通过。

**W4-28C3：整网审计，单线程。** 在Local统一实现允许的profile transition，重跑新28-slice的93边、91条qparam链、16个残差Add、生命周期/alias和成本报告；报告包含lane利用率、hop字节、weight复制、容量、3/2 barrier尾部和转换成本，不宣称cycle。最后接入版本化硬件批准与clean elaboration证据重新审G4；未满足全部五项门槛时继续停在W4。

### W5：逐算子JSON和bitstream【难度：很高】

1. 建立 operator family→模板选择表，区分SA/GA、local/ring和首/中/末tile。
2. 实现字段级shape/qparams patch，不做文本字符串替换。
3. 先用 `config_generator_ver2.py/config_nse.py` 推导Conv关系，再映射目标JSON；旧bit位置必须经过版本审计。
4. 补INT8 Conv/MatMul、QLinearAdd、AvgPool requant、Quantize/Dequantize模板和handler。
5. 目标资源固定28；保留并验证完整28-bit slice mask、per-slice WREG和真实HIGH/LOW routing，清除旧16-slice目标及高12位强制清零逻辑。
6. 每个配置输出mapping review、字段范围检查、bitstream hash和架构版本。
7. 建立逐字段provenance表：字段名、模型/shape来源、推导公式、旧参考位置、目标寄存器/bit range、contract版本和测试ID。

验收门 G5：G1所需contract已批准；每个算子族至少一个微型shape和一个真实shape稳定生成bitstream；改变shape/qparams后所有相关字段联动，零unresolved control；每个非默认字段可回溯推导依据。

### W6：目标simulator闭环【难度：很高/部分外部阻塞】

1. 把NDP Conv改成读取manifest/JSON adapter的backend，禁止复制硬编码shape。
2. 对同一physical input比较直接functional配置和JSON adapter配置，并分别覆盖一个4-slice小环、七小环并发和代表性28-slice大环。
3. 接入官方/外部非Conv emulator；若不存在，先实现能覆盖ResNet所需LC/stream/buffer/SA/GA子集的最小解释器。
4. 统一超时、退出码、日志、physical D、inverse layout和logical D。
5. 逐算子通过后再组合`Quantize→conv0→MaxPool`、残差块和head；同时记录两profile的模拟cycle/stall（若模拟器提供），不能只比较数值。
6. 外部进程backend必须限制工作目录、超时、最大日志/产物大小并捕获版本；不得依赖交互式shell或个人环境变量。

验收门 G6：每个hw_op的golden=simulator；整数bit-exact，浮点按manifest tolerance；重复运行稳定。

### W7：网络execplan和数据包【难度：高】

1. 让 `model_execplan` 消费统一manifest，不再手写77+实例。
2. 扩展schema/handler承载多输入、attributes、qparams和中间psum。
3. 处理tensor地址生命周期、残差分支、in-place/zero-copy、七组3/2样本调度和真实HIGH/LOW slice routing。
4. 每个实例生成独立patched JSON/bitstream/control write。
5. 输出execplan、cfg_pkg、SCA、Bank_data和emulator bundle，并引用相同hash。
6. bitstream/模板/数据/handler缺失时严格失败。
7. memory planner输出每个tensor的 `[base,end)`、alignment、bank/slice、live range和复用来源；验证不越界、不重叠、不读取已释放数据，并对地址单位转换做round-trip。

验收门 G7：单算子、conv0子图、一个残差块和head依次通过simulator整子图逐hw_op比较；无旧16-slice目标残留、伪modulo拓扑或静默截断。

### W8：硬件/RTL接入【难度：很高/外部阻塞】

1. 实现 `HardwareBackend` 的load config/data/execplan、start、wait、timeout、status和dump。
2. 固定byte/word地址单位、端序、slice/bank编号、装载顺序和输出有效时机。
3. 先跑小Conv单算子包；保存原始physical dump并inverse成logical tensor。
4. 支持单算子停止点或逐层checkpoint；记录硬件/RTL/固件版本和运行日志。
5. 硬件backend先执行capability/protocol probe和只读健康检查；任何写入/启动动作都绑定明确run_id和输入/config hash，dump后验证长度与地址范围。
6. 对Conv0、56×56残差块、14×14/7×7深层块、GAP和head记录cycle、neighbor/DDR stall及有效slice利用率，决定是否启用大环或profile转换。

验收门 G8：同一包重复运行稳定，小Conv和conv0达到golden=simulator=hardware；至少一个主体残差块证明28个slice按新profile被调度，并形成可比较的性能基线。

### W9：全算子扩展、三方比较与整网回归【难度：高】

当前前置进度（2026-07-13）：manifest式逻辑tensor比较器、请求/报告schema和CLI已经完成；整数bit-exact、浮点显式`atol/rtol`、missing/load/inverse/shape/dtype/value分类、拓扑首错、坐标provenance及分块mmap均有回归。它只表示工具就绪；目标simulator/hardware结果、批准inverse layout和逐算子/整网三方通过仍未取得，G9不变。

1. 比较器按manifest执行golden↔simulator、golden↔hardware、simulator↔hardware三组比较。
2. 报告首错node/hw_op/slice/逻辑坐标/物理地址/三方值，不给污染后的下游逐层猜因。
3. 回归层级：微型算子→conv0→残差块→stage→head→整网。
4. 建立正常图片、固定随机、0/255、负weight、饱和、rounding tie和tail测试集。
5. 输出机器可读JSON和人读Markdown；保存所有版本/hash/命令。
6. 维护 `coverage/operator_matrix.json`：每个operator family×shape类别×backend×阶段门的pass/fail/blocked状态和最近run_id，禁止用单个样例代表全家族完成。

验收门 G9：所有整数中间结果三方bit-exact；批准浮点结果在tolerance内；整网logits/分类结果一致且可一键重建。正式profile必须附整网cycle、主要stall、有效slice利用率和profile转换成本；主体不得以“低16位工作、其余闲置”的兼容方式作为最终实现。

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
- W4只有在C0/C1冻结公共合同/API并通过P4判定后，才按互不重叠的算子族并行实现；G4/G5是整阶段门，不存在单算子自行打开W5/W6的口径。
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
3. **契约先于硬件真值**：当前RTL候选静态显示28 slice、每slice SA 8×8与GA 4×4；字段位宽、layout、qparams、ISA及板级行为仍必须分别标candidate/approved。candidate允许软件实验，不允许宣称硬件配置完成。
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

状态：正式模型、固定输入、预处理、W3 manifest/lowering/golden已完成；RTL28静态candidate已固定，clean elaboration、批准数值/物理layout、目标emulator和硬件运行接口仍阻塞。

难度：外部阻塞；资料到位后的整理难度为中。

任务：

1. 正式 `resnet50-v1-12-int8.onnx`、输入预处理约定和固定测试输入已取得并冻结；除非合同/hash失效，不再重做。
2. 原 `tensor_dict.json`、DDR、旧 `.cu/.pkl` plan、golden、`conv_config`和`hex_data`仅是可选兼容性资料，不再作为开工前置。
3. 继续确认 `NDPFuncModel/conv_func` 与目标 JSON emulator 的关系，并取得/实现目标 JSON/bitstream→LC/AG/Buffer/PE 参数adapter；若它只负责 Conv，则另外取得其他算子的 emulator 入口。
4. 取得硬件或 RTL 的配置/数据/execplan 加载、start/wait、结果 dump 协议。
5. 目标已确认28 slice、候选RTL已固定`master@e3bdebba...`；继续冻结其权威顶层/filelist、资源数、字段位宽、GA opcode、DDR row、28-bit指令mask和寄存器表版本。
6. 取得一份批准的 INT8 SA/GA 最小配置和 activation/weight/bias/scale layout 示例。

验收标准：

- 所有资料有来源、版本、hash 和本地路径记录。
- emulator 样例可运行并产生可解析输出。
- 硬件/RTL 接口至少能完成一次加载和 dump，或明确记录外部负责人和阻塞状态。
- 架构参数不再从冲突的旧文件中混选。

当前状态：模型、固定图片、暂定预处理、batch=16输入和ORT输出已建立可重放hash基线，W3已基于它通过G3。28-slice RTL候选commit和物理环已选定；W1仍未通过G1，因为clean elaboration、目标layout、RTL/ISA、JSON/emulator关系和硬件接口没有approved合同；这些继续与W4并行推进。

## 阶段 B：建立统一图、lowering 和产物契约

目标：建立 ONNX 节点、硬件原子算子、JSON 实例、execplan op 和三方结果之间的唯一映射。

状态：W3语义层已实现；JSON实例、逐K-tile和execplan身份将在W4/W5/W7扩展。

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

当前状态：G3已通过。正式图目录含78节点/617 tensor，lowering含133个语义hw_op和55个内部tensor；旧77原语已按稳定node/hw_op ID逐项映射，Flatten明确为zero-copy。当前manifest尚未包含正式layout、JSON实例、地址和execplan记录，属于后续阶段而非W3缺失。

## 阶段 C：生成完整 raw golden 和硬件子步骤 golden

目标：对每个 ONNX 节点保存 raw input/output，并为 lowering 后需要观察的 psum、sum、requant 等子步骤生成软件 golden。

状态：W3/G3已完成当前批准范围；正式batch16逐节点输出和55个语义内部tensor均已保存、hash锁定并可重放。

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

当前状态：G3已通过。根集成runner绕开旧CGRA eager import，保存1个图输入+78个node output并引用366个initializer；55个内部tensor包括53个Conv accumulator、1个GAP sum和1个MatMul accumulator。全部78节点由独立公式重放匹配ORT，重复运行文件hash一致。旧`golden.py`的30个唯一检查名、21个checkpoint和`layout_buffer.py`语法错误只影响旧入口，不再阻塞W3；逐K-tile快照待W4/W5取得正式tile合同后细化。

## 阶段 D：实现 ResNet 28-slice 数据变换

目标：把 raw tensor 转成 simulator/hardware 使用的物理格式，并能无损逆变换回来。

状态：旧16-slice逐算子candidate已被ADR-007判定为目标失效。当前28-slice已完成七个家族的两profile软件candidate；RTL28整网物理审计和硬件批准仍待完成。

难度：高。主要风险是正式 layout 未确认、Conv weight/im2col、尾块和不同算子间 layout 衔接。

1. 以ADR-007为基线：七个4-slice小环分别处理`[3,3,2,2,2,2,2]`个样本，环内activation按C owner、weight/P/D按K owner；禁止把旧“一样本一slice”直接扩展到28。
2. 为activation、Conv weight、bias/scale/zp、psum和输出分别声明logical/physical layout，并显式记录小环ID、真实物理slice顺序和可选大环step。
3. 为每一种 ONNX/硬件原子算子分别实现 partition、padding、im2col/weight reorder、tile reorder、128-bit packing、bank/remapping；不能用一份通用 reshape 假定覆盖全部算子。
4. 实现严格 inverse partition/relayout/unpack/merge。
5. 输出 `install/opX/sliceYY/matrix_{A,B,C,D}_linearized_128bit.{bin,txt}` 和对应 manifest。
6. 为非 2 的幂 C/H/W、最后 1000 类和尾 tile 编写 padding/tailing 测试。

逐算子 relayout 清单（candidate只表示软件布局可审计，不表示硬件批准）：

| 算子族 | 必须实现的物理数据对象 | 状态 |
|---|---|---|
| QuantizeLinear | FP32输入、scale/zp、七batch group的UINT8输出及逆变换 | C1两profile candidate已完成 |
| QLinearConv | activation、OIHW weight、bias、scale/zp、最终int32 P和D；逐K-tile边界在W5细化 | C2两profile candidate已完成 |
| MaxPool | UINT8 activation、padding/tail、保持group/channel owner的D | C2两profile candidate已完成 |
| QLinearAdd | 两残差输入、各自qparams、owner兼容、广播和UINT8 D | C2两profile candidate已完成；双alias范围冲突已fail-closed，整网地址分配在C3复核 |
| QLinearGlobalAveragePool | activation、owner-local int32 sum、requant参数和D | C2两profile candidate已完成 |
| QLinearMatMul / dense Add | feature、weight、qparams、最终int32 P和D；dense bias属于后继Add | MatMul及dense Add两profile candidate均已完成 |
| DequantizeLinear | UINT8输入、scale/zp和FP32 D | C1两profile candidate已完成 |
| Flatten/View | 证明物理零拷贝，或实现显式forward/inverse重排 | C1两profile zero-copy candidate已完成 |

每一行还要按实际 lowering 拆到具体 `hw_op_id`，分别覆盖 A/B/B'/C/D 端口；“该算子的输入已由上游排好”也必须在 manifest 中证明，不能据此省略 relayout 规则。

验收标准：

- raw→physical→raw 对所有测试 tensor bit-exact。
- 每个 slice 的元素归属、复制规则、padding 区和 128-bit 行内顺序可由 manifest 验证。
- 上一算子 D 与下一算子 A 的物理布局不一致时，明确由 remapping、后继 stream 还是显式 relayout 解决。

当前状态：W2语义保持冻结；旧`artifacts/w4/g4_gate_audit.json`及配套报告已在ADR-003/005标为历史16-slice证据。ADR-007已经给出目标版本和软件profile方向，因此不再等待旧拓扑裁决；当前直接实现28-slice W4并生成新版本报告。G4未通过且W5未授权，旧candidate不得原地改写为新profile。

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
3. 为4-slice合成例、七个4-slice小环并发和代表性28-slice大环建立坐标级比较；补齐`ActivationUnit.sse2_round_to_int()`或统一调用项目QNN量化实现。
4. 对接 `model_execplan --export-emulator` 的 per-slice JSON/`dram_data.bin`，建立目标 JSON 字段→功能模型参数映射；若目标要求 bitstream 级解释，另加 decoder 层。
5. 封装统一 runner：加载、执行、超时、退出码、日志、physical D dump、inverse-relayout 和 logical D。
6. 非 Conv 算子先用小 MaxPool 确认是否存在统一 emulator；不存在时按优先级实现最小 JSON 数据流解释器或接入外部程序。

验收标准：

- 同一输入重复运行结果稳定。
- simulator 输出可映射到 `hw_op_id` 和逻辑 tensor 坐标。
- 单算子 golden=simulator；整数 bit-exact，浮点符合 tolerance。
- emulator 不在仓库时，阻塞必须记录为外部依赖，不能用 bitstream 生成成功替代。

当前状态：W2参数化runner已实际经过DRAM→input Buffer→SpecialPEA→ActivationUnit→output Buffer→DRAM，1/4-slice小Conv全部84个accumulator及physical/logical UINT8 D与golden一致；slice/transaction寻址、INT8 A/B、LC末态、psum生命周期和候选requant均有回归。该runner仍由fixture/adapter驱动而非目标JSON/bitstream，旧硬编码主入口和正式flush/packing不能据此批准；`write_emulator_bundle()`仍只写输入包，非Conv目标emulator也未找到。

## 阶段 G：生成 ResNet 网络级硬件 execplan

目标：从阶段 B 的 lowering manifest 自动生成完整 ResNet 网络级 JSON、per-instance 配置、地址、Bank_data 和目标指令流。

状态：框架已有，ResNet 前端和适配不存在。

难度：高。主要风险是七小环/大环混合profile、三维shape、量化attributes、一对多lowering、地址生命周期、3/2样本组调度和失败容错。

方案：

1. 扩展 `OperatorSpec/TensorSpec` 支持必要 attributes/constants、多输入语义和稳定 tensor ID。
2. 保留28-slice地址与28-bit mask框架，把抽象`range(28)`升级为ADR-007的真实HIGH/LOW routing、七batch group和per-slice配置，并删除旧16-slice目标适配逻辑。
3. 从 manifest 生成网络 JSON，不手写 77+ 实例和 source 关系。
4. 对每个实例 patch shape、qparams、base address、remapping 并重生成 bitstream。
5. bitstream/模板/寄存器 unresolved 时严格失败；修复 pipeline 当前打印失败后继续的问题。
6. 先生成单算子、`Quantize→conv0→MaxPool`、一个残差块、head，再扩整网。

验收标准：

- execplan 的每个 op 都能追溯 ONNX node/hw_op，输入 source 和地址无歧义。
- 生成 `execplan.txt`、说明、patched JSON、cfg_pkg、sca_cfg、Bank_data 和 emulator bundle。
- 没有旧16-slice目标残留、伪modulo拓扑、静默整除截断、缺模板或unresolved control。
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

状态：通用逻辑结果比较器已就绪，支持inverse后两方/三方、整数bit-exact、浮点容差、首错分类、拓扑/物理provenance与分块mmap；当前缺少获批28 inverse layout、目标simulator结果和hardware dump，因此尚无真实三方通过结论。

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

整库复审后，W2没有直接把4 slice机械扩成旧16；它先修复物理寻址和数值链。ADR-007之后，4-slice fixture将作为每个HIGH小环的基线，再扩成七小环/28-slice调度。按以下顺序解决：

| 顺序 | 问题 | 为什么先做/后做 | 解决与验收方案 | 难度 |
|---:|---|---|---|---|
| 1 | 建立独立最小 Conv 真值 | 现有 `extracted_*.npy`、psum trace 不可信，缺少判错基准 | 自建 1 个小 UINT8×INT8 Conv，保存 activation/weight/int32 bias、逐 K psum、requant D；NumPy/QNN 双实现互验 | 中 |
| 2 | 修复 slice/bank 物理寻址【已完成候选修复】 | 上游四个逻辑slice都读物理slice0，bias slice1~3为空 | `789d121`已使`per_slice`包含bank并将slice span加入AG base；4-slice逐byte provenance和bundle hash读回通过 | 中 |
| 3 | 修复 RDAG/WRAG transaction 地址【已完成候选修复】 | 上游计算stride后丢弃，真实shape会触发 | `789d121`已分离逻辑counter和物理transaction offset；非连续、跨16-byte边界的RDAG/WRAG序列测试通过 | 中 |
| 4 | 固化 INT8 数值语义【W2软件候选已完成】 | signed A×unsigned B、float32 中转会使 psum 非 bit-exact | `deee41f`已实现activation uint8、weight int8、bias/psum int32和branch清零；W2最终验证全部84个physical-address accumulator。溢出暂显式报错，硬件wrap/saturate/error规则待确认 | 中高 |
| 5 | 修复 reduction 与输出坐标【W2软件候选已完成】 | 上游最后reduction条件永假且每个R后清空psum | `86cd3e3`修复末态/生命周期；`d212225`及后续runner验证全部坐标四段ring和每坐标候选flush；正式JSON调度仍在W5验证 | 中 |
| 6 | 实现 requant 与真实 writeback【W2软件候选已完成】 | 没有 UINT8 D 就无法和 ResNet golden 比较 | `7a47701`+`3cb0ef9`及后续buffered runner完成nearest-even、zp/saturation、output Buffer→DRAM、实际D地址覆盖和inverse；硬件multiplier/shift与正式pack仍待合同/W5 | 高 |
| 7 | 恢复配置驱动 | 当前主程序完全绕过 `config/` 和 JSON | 先恢复 `graph` pyc 对应源码或取得 `conv_config`；把 `config_nse.py` 固定 Conv 逐字段映射到目标 JSON，明确架构版本，不复制整段位串 | 高 |
| 8 | 从4 slice扩到七小环/28-slice【当前W4】 | 只有前7步正确后，扩规模结果才可判定 | 参数化group、真实ring map、3/2 batch、C/K owner和tail；1/4-slice与28-slice恢复同一逻辑Conv结果 | 高 |
| 9 | 接 ResNet conv0 与全层 relayout | 小模型通过后才能区分算法问题和布局问题 | raw ONNX→forward relayout→JSON runner→physical D→inverse→QNN/ORT golden；再覆盖全部 Conv shape | 很高 |

其中第 1~6 项不需要等待外部 `hex_data`：可以用小合成数据完成并形成回归。外部样例改为“兼容性验收资料”，不再作为修复当前模型的硬前置。第 7~9 项仍需要确认目标架构版本、正式 layout/端口和 JSON/bitstream 关系。

## 当前最高优先级请求

需要统一向学长或硬件侧确认/索取：

1. 对已选`Trassic2.0_RTL@e3bdebba...`提供权威顶层/filelist和clean elaboration命令，冻结对应ISA/register-map、资源数、字段位宽、opcode、DDR row、地址单位和28-bit指令mask。
2. 审核我们后续生成的最小INT8 Conv候选配置，确认activation/weight/bias/qparams/psum/D正式物理layout、PEA物理A/B端口、requant/rounding/saturation和writeback语义。模型语义已确定为UINT8 activation×INT8 weight×INT32 bias，不再询问ONNX数学类型。
3. 确认逐层qparams由constant patch、tensor stream、control write还是逐层静态JSON传递；若已有批准样例，请提供对应配置和目标版本。
4. 确认 `NDPFuncModel/conv_func` 是否为认可的Conv emulator，以及是否已有官方JSON/bitstream或非Conv emulator。`conv_config` URL、原 `hex_data` 和预期D只作为兼容性资料，可选提供。
5. 提供硬件/RTL的load config/data/execplan、start、wait/timeout、error/status和结果dump协议或现有runner/testbench。

正式模型、固定输入、旧脚本预处理、ONNX算子组成、Conv量化tensor类型、LC/`last_index`、`[start,end)`、stream端口顺序、byte stride、padding有效范围和lane内小端packing已经自行确认，不再重复提问。旧运行产物不再作为开工前置。
