# ResNet50 INT8 端到端实施计划

最后更新：2026-07-14

本文件是项目唯一的权威执行计划。W5新对话先读`.agents/W5_HANDOFF.md`；项目总入口见`.agents/agent.md`，W4追溯见`.agents/W4_ARCHIVE.md`，已经发生的事实见`.agents/history.md`，单算子配置推导细则见`.agents/rules/算子配置规则.md`。

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
- **部分通过**：W1已冻结正式候选模型、固定输入、预处理和软件量化事实；目标RTL已选`Trassic2.0_RTL@e3bdebba...`和28-slice。ADR-008按操作者确认，把`ndp-sim-ref@e299b280...`的JSON/bitstream/model_execplan固定为正式硬件配置来源；ADR-009进一步把已完成DeepSeek整网调试记录为具名硬件基线，并明确不声称新的clean elaboration日志。W4物理profile/layout已经批准；INT8 SA/psum/requant、sum跨slice/完成协议、目标数值模拟器和板级协议仍分别留在后续阶段。
- **当前主线**：W4/G4已闭环，W5首个真实Conv在根仓`e9b6492...`与NDP `1d3181d...`形成单算子配置冻结提交。累加JSON与8份真实requant JSON均通过正式encoder；schema 0.3把全部原文/SHA送入NDP，28个slice各执行双staging D写回/inverse，单坐标、首tile和全算子INT32 P/UINT8 D全部与W3 golden bit-exact。确定性导出器又生成339个受hash约束的physical输入/golden/config/bitstream/地址与比较交付文件。下一阶段允许硬件负责人只使用冻结镜像手工运行，同时扩展负责人从同一提交处理第二个1×1/shape-family；公共合同、Git和全量回归仍串行。
- **当前边界**：操作者已确认先前DeepSeek算子JSON可由目标硬件执行，HIGH-4 selector固定为`mem/src/dst=4/1/1`；真实64-channel requant、GA常量、16B staging、LC `1/9408/2352`和唯一flush也已config-bound闭合，`B_REQUANT_TARGET_NUMERICS`从该首例清单删除。只剩`B_EXECPLAN_TYPED_TRANSPORT`阻碍自动扩展/整网执行，不妨碍手工硬件加载。G5/G6仍不升级，因为bulk路径不是逐周期LC/stream/buffer或bitstream解释器，且精确新配置硬件P/D尚未取得。

### 接手进度总表

| 工作包 | 门状态 | 已完成边界 | 接手动作 |
|---|---|---|---|
| W0 | G0通过 | manifest/contract/backend/artifact/cache/resume/mock DAG | 不重做，只回归 |
| W1 | G1未整体通过 | 模型/输入/量化事实、28-slice RTL、正式配置源和W4物理基线已冻结；后续数值/运行协议仍分阶段缺失 | 不重开G4；在W5/W6/W8分别闭合INT8配置语义、目标模拟器和板级协议 |
| W2 | G2通过 | 1/4-slice小Conv候选layout和NDP functional数值闭环；RTL28 Conv到该功能模型的candidate-only探针 | 作为W4/W6前置fixture，不外推为目标simulator或硬件规格 |
| W3 | G3通过 | 78节点、133 hw_op、79 runtime tensor、55内部tensor、旧77映射 | 不重跑大artifact，除非hash/合同失效 |
| W4 | G4通过 | C0-C7、DeepSeek公共物理合同、ResNet差异合同、混合28-slice profile、七族layout/domain、93边/成本和具名批准均闭环 | 不重开；版本或合同hash变化时自动重审 |
| W5～W9 | W5首例配置与两方数值闭环完成，G5/G6仍未批准，其余未通过 | DeepSeek JSON硬件执行能力已确认；真实1×1 JSON/bitstream、HIGH-4 selector及三档P/D均闭合 | 参数化requant并接typed transport；硬件实跑延期 |

### 当前可立即执行队列

1. 【已完成】终审16-slice泄漏：current layout registry只含RTL28/28，公共layout不导出旧16类；旧通用`conv_coverage.py`、`network_dry_run.py`和`w4_profiles.py`显式标为legacy16-only并由自动回归约束。
2. 【已完成】按P4使用三个共享Local协作子任务，严格隔离Conv、MaxPool+GAP、MatMul的实现/测试/候选报告文件；子任务未编辑公共合同、`.agents`或Git。
3. 【已完成】Local主任务依次复核三路结果，统一更新公共`layout.py`、`architecture.json`、coverage和G4插件登记；随后单线程完成QLinearAdd，当前为14个candidate/0个planned，七个必需布局家族均已登记。
4. 【并行完成】新增RTL28 Conv→NDP functional candidate探针，在紧凑可逆shadow几何中保留真实slice owner/offset，实际遍历七个HIGH小环和代表性LOW大环；显式标记`candidate_only`、`target_simulator_validated=false`、`g6_validated=false`。
5. 【已完成】C3建立两种可执行候选调度：全网group4x7，以及仅在Quantize→MatMul head边界发生一次group4x7→global转换；重新生成并登记93边、91 qparam链、16个残差Add、79 tensor生命周期/alias和静态成本证据。没有读取W3大tensor或生成正式W5产物。
6. 【已完成】ADR-008冻结正式配置来源；盘点42个JSON，三向对照MaxPool JSON→`FIELD_MAP`→register CSV，纠正旧规则对CSV方括号范围的误读。固定`PYTHONHASHSEED=0`/UTF-8/seed后两次bitstream逐字节一致，地址字段差分会改变bitstream，17-bit溢出在编码前失败。
7. 【已完成】单线程把同一审计扩展到第二个MaxPool和AvgPool，确认三模板共用shape→LC→stream→buffer→GA五段链；两个MaxPool的18项差异全部归因，AvgPool明确只到int32 sum，未包含除法/requant。三模板均通过确定性、地址差分和溢出拒绝。
8. 【已完成】C5单线程审计Quant与Add-Dequant；确认静态constant与正式ResNet qparams直接匹配数均为0，现有handler没有typed qparam通道，目标数值rounding和完整QLinearAdd仍未闭环。
9. 【已完成】C6用两个共享Local子任务隔离审计6个GEMM/GEMV与11个sum族模板；主任务完成公共报告0.4、backend fail-closed绑定和确定性复核。未生成正式W5实例。
10. 【已完成】C7单线程建立W3 hw_op/tensor/qparams到正式配置字段的typed参数合同、provenance和严格失败测试；覆盖78节点/133 hw_op、491个initializer参数引用和三态字段解析，只定义参数映射，没有生成patched JSON、bitstream或execplan。
11. 【已完成】按ADR-009完成最小DeepSeek基线继承闭环：schema 0.3不再强迫全网group/global二选一；公共物理合同与ResNet W4差异合同均按本地证据hash验证；七族绑定到`local`或`HIGH-4`，LOW-28只保留为未选替代；没有伪造elaboration日志。全量G4审计12/12为true，阻塞列表为空，正式结束W4。
12. 【已完成到候选边界】已定位DeepSeek链并固定首例`node-0004`/`hwop-0004-00~01`。逐LC/PE/stream合同裁决了伪代码循环、PE算式、stream维序和端口角色；派生`conv_1x1_real.json`并由正式encoder以46连接、零违规placement稳定生成bitstream。target配置与合同文本/hash已进入NDPFuncModel request；单坐标1元素、首tile 150,528元素和全算子3,211,264元素的P/D全部零不匹配，证据见`artifacts/w5/hwop-0004-00/preflight.json`。
13. 【单算子冻结已完成】保持G5/G6 fail-closed：HIGH-4 selector已按`4/1/1`正式编码，真实Quant路径的64个multiplier、末次reduction、双staging inverse和唯一UINT8 flush已由schema 0.3闭合。当前下一步拆为硬件负责人使用冻结镜像取得P/D，以及扩展负责人从同一提交处理第二个1×1/shape-family candidate；execplan typed qparams仍串行推进。不得生成整网W5或宣称硬件三方通过。

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
  ndp-sim-ref/                # ADR-008固定的正式JSON/bitstream/execplan配置来源
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
2. 冻结28-slice RTL/ISA/寄存器/JSON版本；当前W4物理基线固定`Trassic2.0_RTL@e3bdebba95dec36ee8eba43caa92a326a88392cd`。
3. 确认正式layout、SA/GA、bias/psum/requant语义。
4. 取得目标emulator和硬件load/start/wait/dump协议。
5. 记录来源、负责人、版本和hash；未确认项不得填默认值冒充批准规则。
6. 将结论写入 `contracts/*.json` 和 `.agents/decisions/ADR-*.md`；每条字段标记candidate或approved，记录证据与适用commit。

验收门 G1：权威资料可定位、可重放，架构版本不再从冲突旧文件混选；architecture、quantization和backend contract均通过schema且关键字段为approved。W2可在candidate contract下做软件实验，但W5目标bitstream和W8硬件验收必须等待对应approved contract。

当前状态（2026-07-14）：

- **已完成**：从官方ONNX Model Zoo镜像下载并通过checker；模型SHA-256为 `c234f30975989788b4405f25253275aae247ab6dbdd34aaa69ab0a59ff76f6d0`，IR 4、opset 12、78节点、366 initializer，无external data。
- **已完成**：算子统计与旧计划完全一致：2 Quantize、53 QLinearConv、1 MaxPool、17 QLinearAdd、1 GlobalAveragePool、1 Flatten、1 QLinearMatMul、2 Dequantize。
- **已完成**：暂定旧脚本预处理contract；仓库 `cat.jpg` 生成 `[16,3,224,224]` float32输入并由ORT 1.27 CPU生成 `[16,1000]` 输出，模型/图片/输入/输出hash已写入 `contracts/model_baseline.json`。
- **已完成**：从模型确认53层Conv语义均为UINT8 activation、INT8 weight、INT32 bias、per-output-channel weight scale，全部weight zero point为0；input/output zero point并非全部为0。
- **已记录**：`contracts/model_baseline.json`、`contracts/quantization.json`、`contracts/architecture.json` 和 `.agents/decisions/ADR-001-model-and-preprocessing-baseline.md`。
- **已完成候选选择**：审查`master/dc/xilinx`后选定最新且功能更完整的28-slice `master@e3bdebba...`；其活动参数、七小环/大环拓扑和28-bit mask已定位。
- **已完成W4具名批准闭环**：早期`contracts/rtl28_hardware_approval_request.md`仍保留八项APR及责任方，随后ADR-009和schema 0.3的`hardware_approval.json`以操作者对已完成DeepSeek整网硬件基线的具名确认为W4物理批准依据；合同明确`clean_elaboration_claimed=false`，没有伪造日志。
- **未完成/仍需后续阶段闭合**：INT8 SA/bias/psum/requant和逐实例qparams传递属于W5；target JSON/bitstream到已确认NDPFuncModel Conv simulator的适配与同配置数值验证属于W6；6144-row整网地址属于W7；硬件load/start/wait/dump属于W8。`NDP_Top.sv`/`NDP_Top_new`和新的clean elaboration命令可继续作为额外RTL诊断，但不回退已通过的G4。

W1的模型、RTL、正式配置来源和W4物理基线子任务已完成，但G1作为端到端外部规格总门尚未整体通过。现行阶段允许在ADR-009授权下进入W5；不得因此提前宣布G5/G6/G8或三方一致。

### W2：小Conv纵向软件闭环【第二交付，难度：高】

目标：完全不依赖正式ResNet模型，让一个小Conv完成 raw→physical→functional model→logical D。

当前状态（2026-07-14）：**G2已通过，NDPFuncModel Conv simulator身份已由操作者确认，target配置适配未完成**。小Conv的1/4-slice全部84坐标与各软件golden一致；RTL28 adapter覆盖七个HIGH环和LOW代表路径。W5又执行真实`hwop-0004-00`坐标`(0,0,0,0)`，HIGH-4四段partial accumulator、INT32 P、UINT8 writeback和inverse D均与W3一致。非零weight zero-point仍fail-closed；该结果不批准target JSON/bitstream驱动或G6。

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

当前状态（2026-07-14）：ADR-009已在ADR-007/008基础上完成DeepSeek基线继承。W4-28 C0～C7、七族14个正逆布局实现、93边/91 qparam链/16残差Add/79 tensor生命周期与成本审计全部保留；其中七个group4x7布局由混合profile选中并批准，七个LOW-28布局只作未选替代。G4 v2的12项条件全部为true、阻塞列表为空，W4结束且W5已授权。该批准不声称clean elaboration日志，也不批准W5数值、W6 simulator、W7整网地址或W8板级协议。

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
| C3-01 | P1/C3 | 旧`w4_profiles.py`和`network_dry_run.py`把16同时当batch、slice/owner和ring步数，无法表达`[3,3,2,2,2,2,2]`与head唯一转换 | 已新增独立RTL28审计器，直接消费冻结的小型W3图目录和现行28布局API；覆盖两调度、93边、生命周期/alias与静态成本，不机械改名旧公式 | 报告以28真实owner/HIGH/LOW计算；79 tensor和全部边无冲突；证据内容寻址且G4只放行软件两项 | 已完成 |
| DOC-01 | P1/C0同批 | `agent.md`曾混写旧main缺陷、参考工具权威性和错误下一步 | 摘要/优先级已改为C0完成→C1；明确ndp-sim只作框架参考、NDPFuncModel仅W2 backend，并区分上游固定入口与W2修复 | `agent.md`摘要、当前优先级和详细地图已一致 | 已完成 |
| DOC-02 | P1/C0同批 | 算子规则曾把W3全节点golden/manifest、ResNet lowerer和旧一sample一slice写成当前待办 | 相关段已标W1/W3前历史；当前事实为W3 79 runtime+55 internal/78节点与W2五层链已过，缺口改为28 physical、JSON实例/execplan adapter、target sim/hw | 不再诱导重跑W3或恢复旧16调度，旧脚本缺陷仍保留为历史证据 | 已完成 |
| DOC-03 | P1/C0同批 | ADR-004曾写有效批准加旧W4回归即可开G4并称software readiness通过 | ADR-007/C0先封住旧16误放行，ADR-009最终改为具名DeepSeek硬件基线+引用合同hash+current布局/93边/成本共同放行，不要求伪造elaboration日志 | ADR-004已标明由ADR-009覆盖；现行G4测试区分真实具名合同与合成fixture | 已完成 |
| DOC-04 | P2 | RTL审计文档早期worktree错误数和coverage目标身份容易被当现状 | 已把63 tests/16 errors标为隔离worktree历史观察；coverage新增target/profile/legacy superseded列；W0/W3段落改为历史/完成态 | 当前状态与历史快照可直接区分且未改写history事实 | 已完成 |

明确不修改/不重算：`golden_batch16`、`subop_batch16`、W3 metadata中的16是模型batch size；`profile28.py`的`BATCH_SIZE=16`及七组`[3,3,2,2,2,2,2]`正确；W0 mock的16只保留在`approved_for_w0_only` scope；`conv16_*`、`maxpool16`、`add16`、`avgpool16`、`matmul16`及明确命名测试作为legacy算法证据保留；W2的1/4-slice fixture继续作为软件基线；ADR-002/003/005和`history.md`已标历史的旧结论不改写；没有发现误生成的正式W5 JSON/bitstream。

以下执行顺序与C0验收条件记录当时的迁移过程，不再是当前待办：`ENV-01 → C0-01 → C0-02/03/04 → C0-05/06/07 + DOC-01/02/03/04 → C1-01/02 → 既定算子波次 → C3-01`。最终口径是旧16 approval/layout/report不能进入current gate、合成fixture永不授权W5、具名审批必须验证ADR与两层物理合同hash、所有小型合同/证据可从fresh checkout复核，且全程不读取或重跑W3大tensor。

实施顺序：

0. 机器合同迁移：将架构合同、硬件批准schema/validator、fixture和G4入口切换为28-slice candidate口径；旧16-slice候选/报告只保留在显式legacy区域或历史文件中。冻结RTL commit、HIGH/LOW拓扑ID、七小环主profile和大环候选ID，但不伪造approved合同。
1. 建立`topology28`：精确编码RTL的七个HIGH 4-slice小环和一条LOW 28-slice大环，提供owner/step正逆查询并拒绝`(owner+step)%28`等伪物理拓扑。【已完成】
2. Quantize/Dequantize/View：建立七batch group、环内C/F owner、zero-copy和FP32/UINT8 packing规则。【C1已完成；group4x7与global LOW两个profile共4个candidate layout】
3. Conv：主体profile使用七小环；每组负责`[3,3,2,2,2,2,2]`个样本，activation按C owner环行4步/3 hop，weight在七组复制并按K owner分片，bias/qparams/P/D跟随K owner。【C2第一波已完成group4x7与global LOW候选】
4. MaxPool：保持batch group和channel owner，窗口/padding/tail在本地完成。【C2第一波已完成两profile候选】
5. QLinearAdd：两残差分支必须具有相同batch group、C/K owner和物理轴；A/B/D分别使用自身zero point tail，六个qparam端口保持独立，双分支地址同时活跃时不得冲突。【C2已完成两profile候选；正式范围为同shape rank-2/rank-4与dense `[N,F]+[F]`】
6. GlobalAveragePool：每个channel owner本地完成H×W centered sum/requant，不做不必要的跨组归约。【C2第一波已完成两profile候选】
7. MatMul/dense：先实现七小环一致profile；另实现`w4_global_ring28_candidate_v1`代表层，优先比较GAP后`[16,2048]×[2048,1000]`。【C2第一波已完成两profile候选及显式转换分类】
8. transition：残差块内切profile继续禁止。旧“GAP后最多一次小环→大环”只保留为成本比较场景；ADR-009正式profile不做整网转换，未来只有某个算子证明跨组依赖时才可单独选择LOW-28。

每个插件必须同时实现`forward()`、`inverse()`、`explain_coordinate()`和`validate()`。layout描述必须给出逻辑坐标→物理slice/ring step/bank/byte address公式、padding/tail来源、lane端序和逆公式。

性能报告至少包含SA有效lane比例、activation字节×hop、weight复制倍数、每slice/整机DDR占用、3/2样本组barrier尾部、transition读写量和估算来源；估算不得标为cycle。确认per-slice queue/barrier语义后，可增加异步wavefront候选。

验收门 G4【2026-07-14通过】：最小shape、真实ResNet shape和tail shape均raw→physical→raw bit-exact；93边、91量化链和16个残差Add通过物理兼容、生命周期和alias审计；HIGH/LOW映射匹配锁定RTL；DeepSeek公共物理基线、ResNet W4差异、版本化ISA/register-map和七族profile/layout绑定均由具名合同及hash验证。门明确记录`clean_elaboration_claimed=false`；没有把W5数值或W8运行证据混入W4。

#### W4-28下一执行包与并行波次

本节C0～C7各段保留“该子步骤刚完成时”的历史门状态；其“仍停在W4/不改变G4”字样均已由上面的ADR-009闭环状态取代，不能再解释为当前阻塞。

**W4-28C0：机器合同迁移与legacy隔离，已完成。** ENV-01、现行G4 fail-closed、architecture/approval/backend合同、fixture、旧报告索引、旧工具guard、RTL external evidence lock和文档清理已经统一为28-slice candidate口径。当前满足：目标slice为28；固定`Trassic2.0_RTL@e3bdebba...`candidate来源；HIGH/LOW映射和两个profile ID可机器读取；旧16-slice证据显式legacy且不能被新批准合同选择或工具覆盖；28结构fixture不能授权G4；缺少28算子证据、真实批准或clean elaboration时仍为`G4=not_passed`、`w5_authorized=false`。

**W4-28C1：Quantize/Dequantize/View公共布局，已单线程完成。** 已冻结显式28/legacy16 geometry、七组sample owner、环内C/F owner、16-byte对齐、FP32/UINT8小端packing、qparam全slice副本、inactive/tail和zero-copy证明接口；DRAM geometry/address order继续标`candidate_unapproved`。group4x7采用HIGH owner顺序与固定3个sample存储槽，global profile采用LOW 28-owner顺序；Quantize/Dequantize按端口使用0、zero point或0.0语义padding。最小shape、正式`[16,3,224,224]`、`[16,2048,1,1]→[16,2048]`、3/2边界、feature tail、两profile、破坏性负例均bit-exact；141项根测试通过，全程未读取W3大tensor。

**并行判定门P4，2026-07-13已通过并完成第一波。** 三个共享Local协作子任务分别只修改Conv、Pool、MatMul的独立实现/测试/候选报告文件，未触碰`.agents`、公共合同、共享geometry/profile/topology或Git；主任务按Conv→Pool→MatMul顺序复核后串行集成公共API、合同和门审计。该隔离方式有效，未发生交叉覆盖。

**W4-28C2：逐算子布局已完成。** Conv、MaxPool/GAP、MatMul、QLinearAdd分别提供group4x7和global LOW的forward/inverse/explain/validate、正式shape容量计划、tail/对齐破坏性负例和小型确定候选报告。Add额外冻结六个独立qparam端口、三种语义tail、正式广播白名单，以及A/B同时活跃时逐slice地址区间不能重叠；默认两个Conv D即使字节兼容，只要地址相撞也会拒绝双alias。14个布局均为current candidate但仍未硬件批准；根仓176项全量测试通过。

**W4-28C3：整网审计已单线程完成。** Local审计器只读取小型W3图目录，实际调用冻结的28布局计划API，为全网group4x7和head切global两种调度生成逐slice物理签名。两者均覆盖93边、91条qparam链、16个残差Add和79个运行时tensor；前者0次转换，后者只在UINT8 Quantize→MatMul发生1次显式转换，残差块内不切profile。生命周期采用确定性16-byte first-fit候选，全部同时活跃范围无冲突；报告包含lane利用率、hop字节、weight/broadcast复制、容量、3/2 barrier尾部和转换读写量，明确不宣称cycle。edge/cost两份报告登记为current软件证据，因此G4中的93边与成本两项为真；正式硬件批准、clean elaboration、ISA/register-map及物理layout仍未满足，继续停在W4。

**W4-28C4：正式配置来源冻结与Pool族三模板前置审计已完成。** ADR-008和backend 0.2把`ndp-sim-ref@e299b280...`固定为正式JSON/bitstream/execplan配置来源，但明确不升级为数值模拟器或硬件backend。审计盘点42个JSON（7个ResNet/共享、35个DeepSeek/Transformer、0个命名Conv），验证两个MaxPool和一个AvgPool的结构/资源/字段范围，按正式`register_mapping.py`的“宽度前缀+行顺序”规则证明10类模块与编码器总宽对齐；固定进程哈希/UTF-8/seed后每个模板两次全部输出一致，地址差分敏感且溢出fail-closed。两个MaxPool的16个shape/调度差异和2个planner地址差异已完整归因；AvgPool只完成uint8→int32 sum，除法/requant仍缺。该步骤只生成`contracts/target_config_authority_audit.json`，不生成正式W5配置，不改变G4/W5状态。

**W4-28C5：Quant与Add-Dequant公共GA crosswalk已单线程完成。** `quant_from_buffer_int32MN_uint8MN`已证明是INT32累加结果到UINT8的requant候选，而不是ONNX FP32 `QuantizeLinear`直连模板：八路GA均执行`int32→fp32`、乘固定0.06375、加入编码后为`0x4b400040`的FP32魔数、再以`int32_sub`减raw `0x4b400000`，由此静态样例导出输出zero point 64；RTL静态证据确认末端负数夹0、超8位夹255，但nearest-even只确认到魔数配方，尚无目标数值执行。`add_dequant_uint8CWH_uint8CWH_fp32CWH`两路均为`uint8→fp32`，静态计算`(A*1+1)+(B*1+1)`并输出FP32，不读取`y_scale/y_zero_point`，因此不是完整QLinearAdd或QLinearAdd+Dequantize融合。锁定ONNX中的2个Quantize、2个Dequantize和17个QLinearAdd标量qparams已只读提取，三个直接匹配计数均为0；正式常量注入规则冻结为Quant的multiplier/魔数zero-point patch和Add-Dequant两支独立`scale`、`-zero_point*scale` patch。现有execplan handler只修改5/8个shape与stream-stride字段，`OperatorSpec`没有typed qparams，仍是进入正式配置前必须补的缺口。两模板均通过结构、确定性、GA constant差分敏感性和溢出fail-closed；报告保持数值未验证，不授权W5。

**W4-28C6：GEMV/MatMul与sum组配置审计已完成。** 两个共享Local子任务分别只新增独立实现与测试，公共crosswalk、backend、权威报告、`.agents`和Git由主任务单线程集成。GEMV/MatMul组锁定6个SA模板与5个placeholder handler：全部FP16、`bias_enable=0`，只有decode两模板经GA sum输出FP16；ResNet `M/N/K=16/1000/2048`套入现有local GEMM整块公式会出现`M//32=0`和N余8，且无typed qparams、zero-point correction、外部INT32 psum生命周期、tail或UINT8 requant。sum组锁定11个local/remote/summac/sum-rec模板：全部remote名称模板都没有N2N/neighbor，只能证明对已放入A流的数据归约；静态last-index链不能升级为硬件完成协议；`sum_config_32_32`无base-info/handler/除法/requant，FP16 4-slice remote另有base-info与JSON/handler冲突。代表GEMV以及全部11个sum模板的官方编码均在临时目录中确定复现，但数值、跨slice通信和硬件完成语义仍为`not_validated`。权威报告升至0.4并保持`no_gate_authority=true`；未生成正式W5实例，G4/W5状态不变。

**W4-28C7：typed配置参数合同已单线程完成。** `contracts/typed_config_parameter_contract.json`把锁定ONNX、W3 model graph、batch16 runtime manifest、subop manifest和lowering逐项绑定到78节点/133个语义`hw_op`；只读取三个小型W3 JSON和ONNX initializer，没有读取约951 MB `.npy`。合同保存491个initializer参数引用，其中438个scale/zero-point和53个bias；159个per-channel原始参数保留元素数、axis、精确字节hash和范围，绝不隐式压成scalar；另生成94个float32/int32公式参数。757个字段绑定逐项标为`derived`、`approval_required`或`rejected`，且三态全部固定`formal_target_write_allowed=false`；缺INT8 SA、tail、psum、requant、typed execplan transport、sum完成协议和批准layout时严格拒绝。backend按path/size/SHA-256绑定该合同，G4审计同步验证其语义和配置权威报告身份。该步骤没有复制静态样例constant，没有生成patched JSON、bitstream、execplan/Bank_data或任何正式W5实例，G4/W5状态不变。

**W4-28 DeepSeek基线继承闭环：已完成，原C8候选取消。** schema 0.3不再强迫全网group/global二选一；操作者确认作为具名基线决定写入ADR-009但不伪造elaboration日志；公共物理合同、ResNet差异合同和七族`local/HIGH-4`绑定均已验证。93边和成本证据按新architecture basis重新内容寻址，G4通过。原C8的typed qparam连续性不再作为W4等待工作，真正的实例qparams→寄存器/stream绑定直接在W5最小Conv中完成。

### W5：逐算子JSON和bitstream【难度：很高】

**当前首包状态（2026-07-15）：真实1×1累加/requant配置和两方数值闭环已完成，并形成单算子冻结提交。** `node-0004`已完成逐字段provenance、累加与8-shard requant正式encoder、schema 0.3 config-bound request、双staging inverse，以及单坐标/首tile/全算子P/D bit-exact。HIGH-4使用`mem/src/dst=4/1/1`，旧`4/0/0`立即失败；64通道requant/唯一flush漂移也立即失败。当前只剩execplan typed qparam transport，精确硬件实跑仍未发生。

0. 【已完成】已区分`ndp-sim-ref` bundle/bitstream打包器与NDPFuncModel Conv simulator；入口、命令、physical request和D writeback均已验证。当前停止条件改为配置适配缺失，而不是模拟器入口缺失。
1. 建立 operator family→模板选择表，区分SA/GA、local/ring和首/中/末tile。
2. 实现字段级shape/qparams patch，不做文本字符串替换。
3. 先用 `config_generator_ver2.py/config_nse.py` 推导Conv关系，再映射目标JSON；旧bit位置必须经过版本审计。
4. 补INT8 Conv/MatMul、QLinearAdd、AvgPool requant、Quantize/Dequantize模板和handler。
5. 目标资源固定28；保留并验证完整28-bit slice mask、per-slice WREG和真实HIGH/LOW routing，清除旧16-slice目标及高12位强制清零逻辑。
6. 每个配置输出mapping review、字段范围检查、bitstream hash和架构版本。
7. 建立逐字段provenance表：字段名、模型/shape来源、推导公式、旧参考位置、目标寄存器/bit range、contract版本和测试ID。
8. 第一份真实Conv配置形成后立即进入最小W6数值probe：同一physical A/B/bias/qparams和JSON/bitstream运行目标模拟器，dump INT32 P与UINT8 D，使用W4 inverse layout后与W3 golden bit-exact。该probe不改变G5/G6各自门定义，但能防止在数值错误模板上继续横向扩展。

验收门 G5：W4授权、正式配置来源、所选profile/layout和该实例所需配置合同均通过版本/hash检查；至少一个微型shape和一个真实shape稳定生成bitstream；改变shape/qparams后所有相关字段联动，零unresolved control；每个非默认字段可回溯推导依据。目标simulator与硬件runtime未就绪不阻止G5配置preflight，但没有golden=target simulator就不能宣称算子数值通过或继续大范围扩展。

### W6：目标simulator闭环【难度：很高/部分外部阻塞】

1. 把NDP Conv改成读取manifest/JSON adapter的backend，禁止复制硬编码shape。
2. 对同一physical input比较直接functional配置和JSON adapter配置，并分别覆盖一个4-slice小环、七小环并发和代表性28-slice大环。
3. 实现`ndp-sim-ref` Conv JSON/bitstream字段到NDPFuncModel physical request的受控adapter；非Conv emulator仍按各算子族另行接入。
4. 统一超时、退出码、日志、physical D、inverse layout和logical D。
5. 逐算子通过后再组合`Quantize→conv0→MaxPool`、残差块和head；同时记录两profile的模拟cycle/stall（若模拟器提供），不能只比较数值。
6. 外部进程backend必须限制工作目录、超时、最大日志/产物大小并捕获版本；不得依赖交互式shell或个人环境变量。

验收门 G6：每个hw_op的golden=simulator；整数bit-exact，浮点按manifest tolerance；重复运行稳定。

当前前置进度（2026-07-15）：真实1×1累加与requant配置已经通过正式encoder并由NDP request schema 0.3实际消费；同一physical bundle上的单坐标、首tile和全算子P/D均与W3 bit-exact，28个slice的两份staging D均读回并inverse为canonical D。`B_CONV_TARGET_EXECUTION_SEMANTICS`、`B_N2N_TARGET_SELECTOR`和该首例`B_REQUANT_TARGET_NUMERICS`已解除，只剩`B_EXECPLAN_TYPED_TRANSPORT`；由于尚非逐周期/bitstream解释且未跑精确硬件，`g6_validated=false`。

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

状态：正式模型、固定输入、预处理、W3 manifest/lowering/golden、RTL28目标、正式配置来源和W4物理layout/profile均已冻结；新的clean elaboration只作额外诊断，不阻塞已通过的G4。INT8数值配置、目标emulator、整网地址和硬件运行接口分别在W5/W6/W7/W8继续闭合。

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

当前状态：模型、固定图片、暂定预处理、batch=16输入和ORT输出已建立可重放hash基线，W3已基于它通过G3。28-slice RTL、物理环、正式JSON/bitstream/execplan来源以及W4 layout/profile均已冻结。W1的历史G1口径不用于回退已通过的G4；INT8 requant/qparams、目标数值模拟器和硬件接口按现行W0～W9阶段分别在W5/W6/W8闭环。

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

状态：旧16-slice逐算子candidate已被ADR-007判定为目标失效。当前28-slice七族正逆布局、整网物理审计、DeepSeek继承profile与W4物理批准均已完成；七个LOW-28实现仅作未选替代。

难度：高。该阶段已经完成；历史主要风险是Conv weight/im2col、尾块和不同算子间layout衔接。正式W4 layout/profile现已由ADR-009批准，后续不得再把“layout未确认”列为W4待办。

1. 以ADR-007为基线：七个4-slice小环分别处理`[3,3,2,2,2,2,2]`个样本，环内activation按C owner、weight/P/D按K owner；禁止把旧“一样本一slice”直接扩展到28。
2. 为activation、Conv weight、bias/scale/zp、psum和输出分别声明logical/physical layout，并显式记录小环ID、真实物理slice顺序和可选大环step。
3. 为每一种 ONNX/硬件原子算子分别实现 partition、padding、im2col/weight reorder、tile reorder、128-bit packing、bank/remapping；不能用一份通用 reshape 假定覆盖全部算子。
4. 实现严格 inverse partition/relayout/unpack/merge。
5. 输出 `install/opX/sliceYY/matrix_{A,B,C,D}_linearized_128bit.{bin,txt}` 和对应 manifest。
6. 为非 2 的幂 C/H/W、最后 1000 类和尾 tile 编写 padding/tailing 测试。

逐算子 relayout 清单（表内“candidate已完成”记录实现阶段；ADR-009后来选中七个group4x7布局并批准，LOW-28对应实现只作未选替代）：

| 算子族 | 必须实现的物理数据对象 | 状态 |
|---|---|---|
| QuantizeLinear | FP32输入、scale/zp、七batch group的UINT8输出及逆变换 | C1两profile candidate已完成 |
| QLinearConv | activation、OIHW weight、bias、scale/zp、最终int32 P和D；逐K-tile边界在W5细化 | C2两profile candidate已完成 |
| MaxPool | UINT8 activation、padding/tail、保持group/channel owner的D | C2两profile candidate已完成 |
| QLinearAdd | 两残差输入、各自qparams、owner兼容、广播和UINT8 D | C2两profile candidate及C3全16个残差Add整网双分支生命周期/alias复核均已完成 |
| QLinearGlobalAveragePool | activation、owner-local int32 sum、requant参数和D | C2两profile candidate已完成 |
| QLinearMatMul / dense Add | feature、weight、qparams、最终int32 P和D；dense bias属于后继Add | MatMul及dense Add两profile candidate均已完成 |
| DequantizeLinear | UINT8输入、scale/zp和FP32 D | C1两profile candidate已完成 |
| Flatten/View | 证明物理零拷贝，或实现显式forward/inverse重排 | C1两profile zero-copy candidate已完成 |

每一行还要按实际 lowering 拆到具体 `hw_op_id`，分别覆盖 A/B/B'/C/D 端口；“该算子的输入已由上游排好”也必须在 manifest 中证明，不能据此省略 relayout 规则。

验收标准：

- raw→physical→raw 对所有测试 tensor bit-exact。
- 每个 slice 的元素归属、复制规则、padding 区和 128-bit 行内顺序可由 manifest 验证。
- 上一算子 D 与下一算子 A 的物理布局不一致时，明确由 remapping、后继 stream 还是显式 relayout 解决。

当前状态：W2语义保持冻结；旧`artifacts/w4/g4_gate_audit.json`及配套报告已在ADR-003/005标为历史16-slice证据。当前G4 v2按ADR-009、schema 0.3和内容寻址RTL28报告通过，W5已授权；旧candidate和历史成本报告仍不得原地改写成新profile事实。

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

当前状态：42个上游JSON继续作为正式配置来源，且其目标硬件可执行能力已由操作者确认。项目真实1×1 Conv候选已完成字段审计、稳定编码、HIGH-4 `4/1/1` selector和配置绑定两方数值闭环。C7 typed参数合同已覆盖78节点/133 hw_op及真实qparams身份，仍未实现到整网execplan字段的写入。AvgPool、Quant/Add-Dequant、GEMM/GEMV和remote-sum的既有阻塞保持不变。

## 阶段 F：接通目标 JSON/bitstream 数值模拟器

目标：真正执行目标 JSON/bitstream，并按 manifest 导出每个原子算子的物理和逻辑输出。

状态：Conv已有读取并严格校验真实1×1 target JSON/语义合同的NDPFuncModel request入口，并完成物理DRAM等价数值执行；目标硬件执行DeepSeek JSON的通用能力已确认，本候选精确硬件实跑延期。HIGH-4 selector已闭合；当前阶段不再等待cycle-accurate入口，而先闭合真实requant参数化和execplan typed transport。

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

当前状态：真实`hwop-0004`的累加JSON、requant manifest与8份JSON已由schema 0.3 config-bound adapter消费；单坐标走组件路径，首tile/全算子走带GA常量、双staging D与inverse的`physical_dram_bulk_int8_equivalent`，三档P/D均与golden bit-exact。平台执行DeepSeek JSON的能力、HIGH-4 `4/1/1`和真实per-channel requant/唯一flush均已闭合；当前配置缺口只剩execplan参数注入。精确硬件P/D dump仍待硬件负责人完成。

### 首个真实Conv到全Conv/全算子扩展前的强制门

首例不是合成算子，而是锁定ResNet50 INT8 ONNX中的真实`node-0004`：`fused resnetv17_stage1_conv0_fwd_quant`（`QLinearConv`）。它被lowering为`hwop-0004-00 ConvInt32Accumulate`和`hwop-0004-01 RequantizeUint8`，使用正式`[16,64,56,56]` UINT8 activation、`[64,64,1,1]` INT8 weight、64路INT32 bias、真实per-channel weight qparams、scalar input/output qparams和W3 P/D golden。不得把脱离该模型、随机生成或手工缩小的数据替换为首例验收依据。

当前执行边界必须保持显式：`NDPFuncModel/main_CONV_N2N.py`仍把4-slice、`[256,64,3,3]` weight、R/S三次循环、`./hex_data`和固定requant写死；真实1×1不使用该旧主程序。现有schema 0.3路径由根仓adapter调用`python -m tools.physical_image_probe <request.json>`：单坐标通过物理地址列表执行DRAM→Buffer→SpecialPEA→ActivationUnit→DRAM，首tile/全算子通过config-bound `physical_dram_bulk_int8_equivalent`重组HIGH组、使用8份JSON的GA常量、写两份staging D并inverse。累加/requant JSON和语义合同在计算前被严格校验，但尚未逐LC/stream/buffer/N2N解释，也没有执行正式bitstream。因此当前两方P/D通过不能替代配置驱动模拟器门，仍不能证明真实N2N搬运、ping-pong或逐周期调度正确。

从该首例扩展到其他Conv shape、53层Conv或其他算子族前，必须完成以下原子工作包：

1. 将旧3×3主程序重构为参数化Conv runner，或实现一个等价的统一runner；输入只来自manifest/physical bundle和锁定target JSON，不再从函数常量或固定`./hex_data`取得shape、循环和地址。
2. 让配置实际驱动kernel R/S、stride/pad/dilation、C/K tile、LC range/last、stream地址、buffer生命周期、HIGH/LOW N2N selector、ping-pong、bias/psum首中末状态、per-channel requant和唯一末次UINT8 flush；修改任一受控字段必须改变执行结果或fail-closed，不能只改变hash/报告文本。
3. 同一入口至少覆盖当前真实1×1首例和一个正式ResNet50 3×3代表实例；二者都必须从各自真实shape/qparams生成request，不得保留“1×1走bulk、3×3走写死脚本”两套不可比真值。7×7/stride2等其余shape族按此冻结接口继续扩展。
4. 对每个实例输出可追溯的INT32 P、最终UINT8 D、physical地址、inverse logical坐标和首错；同一输入重复运行稳定，并与W3 golden整数bit-exact。
5. 如果目标验收要求bitstream级语义，则接入正式decoder/解释器或外部target simulator；仅校验JSON字段后调用数学等价kernel不得标记G6，也不得作为开放全算子扩展的唯一依据。

开放横向扩展的验收条件：当前真实1×1在新配置驱动路径上重复通过单坐标、首tile和全算子P/D；代表性真实3×3通过同一runner与同一错误报告合同；selector/requant/typed transport均闭合；旧写死入口不再是任何正式验收路径。达到该门后，可以冻结公共request/schema和验收命令，再把硬件协作与不同shape族扩展拆为互不修改公共合同的并行任务。

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

状态：通用逻辑结果比较器和W4批准的28-slice inverse layout已就绪，支持inverse后两方/三方、整数bit-exact、浮点容差、首错分类、拓扑/物理provenance与分块mmap；当前缺少目标simulator结果和hardware dump，因此尚无真实三方通过结论。

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
| 7 | 恢复配置驱动【真实1×1候选已完成】 | 旧主程序绕过 `config/` 和 JSON | 当前adapter读取并校验真实1×1 JSON/语义合同后构造physical request；下一步需升级到逐LC/stream/buffer或bitstream解释 | 高 |
| 8 | 从4 slice扩到七小环/28-slice【W4已完成】 | 只有前7步正确后，扩规模结果才可判定 | group4x7七条HIGH环与代表LOW路径的candidate探针、3/2 batch、C/K owner和tail已有回归；W4物理layout已批准，但该探针仍不是目标simulator | 高 |
| 9 | 接一个真实ResNet Conv配置与数值链【两方闭环完成】 | 小模型通过后才能区分算法问题和布局问题 | 真实1×1已完成raw/真实qparams→W4 forward→target JSON绑定→physical P/D→inverse→W3 golden；硬件执行能力已确认，selector已闭合，保持单实例修复requant/transport | 很高 |

其中第1～6项已经用小合成数据完成，不需要外部`hex_data`。第7/9项的真实1×1候选已闭合target JSON绑定、HIGH-4 selector和等价数值关系，通用硬件执行能力也已确认；当前只保留真实requant/唯一flush和execplan typed qparams两项配置缺口。

## 当前最高优先级工作包

新对话严格执行`.agents/W5_HANDOFF.md`：

1. 【已完成】保持首个真实1×1实例不变，将候选由`mem/src/dst=4/0/0`改为可执行DeepSeek HIGH-4规则`4/1/1`；`ping_pong=0`独立保留。正式parsed dump为`src=1,dst=1,mem_loop=4→00011`，逻辑字段串为`11000011`；128/64位bitstream SHA均改变，placement仍为46条连接/cost 0，三档软件P/D SHA保持不变，旧组合由adapter立即拒绝。
2. 【已完成】复用已知可执行DeepSeek Quant数据通路，将本层64个per-channel multiplier、output zero point、nearest-even、saturation和唯一末次flush参数化为8份正式配置，并由NDP实际消费。
3. 扩展execplan typed qparam transport，使同一首例完全由manifest/execplan重建，不再由W5脚本手工注入。
4. 【已完成软件两方】重复单坐标、首tile和全算子P/D，全部bit-exact；精确硬件实跑与dump交由硬件负责人从冻结提交执行。
5. 按“首个真实Conv到全Conv/全算子扩展前的强制门”把旧写死3×3入口升级为真正消费manifest/physical bundle/target JSON的参数化runner；当前单坐标组件probe和1×1 bulk等价kernel继续作为交叉检查，不得单独开放53层Conv扩展。
6. W7以后地址规划统一以6144-row逻辑容量为硬上限；W8再索取或接入load/start/wait/error/dump协议。新的clean elaboration日志只作额外RTL诊断，不再是W4/G4或W5开工前置。

正式模型、固定输入、旧脚本预处理、ONNX算子组成、Conv量化tensor类型、W4物理layout/profile、LC/`last_index`、`[start,end)`、stream端口顺序、byte stride、padding有效范围和lane内小端packing已经确认，不再重复询问。旧运行产物不作为开工前置。

**2026-07-15 requant冻结状态：** 8个真实GA shard写入64个互异float32 multiplier、`y_zero_point=0`、nearest-even magic和UINT8 saturation；每个shard正式encoder均为21条连接、cost 0，双重重建的parsed/64b/128b/detailed逐字节稳定。两个对齐staging区固定为`904400/979664`。NDP request schema 0.3现实际消费manifest和8份JSON原文/SHA，严格验证64通道、HIGH-ring、16B地址、LC `1/9408/2352`与唯一flush；28个slice的staging写回均inverse匹配canonical D，三档P/D bit-exact。硬件交付目录freeze ID为`f687debd...`，physical P/D自检inverse后仍为全算子0 mismatch。因此该首例`B_REQUANT_TARGET_NUMERICS`已删除，只剩typed execplan transport；根仓冻结提交为`e9b6492...`，NDP为`1d3181d...`。
