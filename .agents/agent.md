# ResNet50 INT8 项目入口与代码地图

最后更新：2026-07-14

本文件是新会话进入本项目时的默认入口，记录最终目标、当前闭环状态、协作规则、仓库基线和代码地图。唯一权威执行计划见 `.agents/plan.md`，已经发生的事实见 `.agents/history.md`。

## 五分钟接手摘要

- **最终验收**：正式 ResNet50 INT8 ONNX→逐节点/硬件原子算子 golden→28-slice relayout→JSON/bitstream→目标 simulator→execplan/Bank_data→RTL/硬件→三方逐算子和整网一致，并以真实cycle/带宽证据选择性能profile。
- **W3业务封版检查点**：`35a4fde106d102b0e165e7eb13d60f7dd980db71`；W0/G0、W2/G2、W3/G3已通过，W1只完成模型/输入/软件量化事实，G1因目标硬件合同缺失尚未通过。交接文档可能有后续纯文档提交，当前恢复点以`git rev-parse HEAD`和`history.md`精确台账为准。
- **三个仓库分工**：`CGRA_SIM` 给软件/QNN语义和旧 ResNet 计划；`ndp-sim-ref` 只给 JSON、bitstream、relayout/execplan 的参考框架，尚未获批为目标工具；`NDPFuncModel` 只给W2 Conv功能数据通路，不是目标backend。根集成层已经统一W3图/lowering/golden身份，但配置、simulator、execplan和hardware尚未接入同一manifest。
- **当前成果**：正式图含78节点/617张量，lower为133个语义hw_op；保存79个运行时tensor和55个INT32内部tensor，全部78节点独立公式重放匹配ORT，旧77原语已逐项映射。W4-28的C0/C1/C2/C3软件候选工作已完成：14个RTL28 candidate layout覆盖全部七族；两种整网调度完成93边、91 qparam链、16残差Add和79 tensor生命周期/alias审计，并生成lane/hop/复制/容量/barrier/转换静态成本。两份current软件证据已内容寻址登记，根仓190/190全量回归通过；旧16-slice物理证据只作历史参考。
- **当前硬件裁决**：目标为28-slice，RTL候选固定`Trassic2.0_RTL@e3bdebba95dec36ee8eba43caa92a326a88392cd`；主体采用七个4-slice小环的batch/channel混合profile，28-slice大环只作代表层性能候选。W4按该方案重开，G4仍未通过，`w5_authorized=false`。
- **下一主线**：等待三类外部责任方返回批准请求包所需的原始证据与签署合同；收到后单线程执行approved合同导入、版本/hash/权威性检查和G4自动重审。等待期间不重复C3、不重跑约951 MB的W3产物；不生成正式W5 JSON/bitstream，且在批准合同和全部当前证据齐全前不宣称G4通过。
- **当前外部阻塞**：正式模型和固定输入基线已经自行取得；剩余外部阻塞为目标commit的clean elaboration/顶层命名闭合、正式端口layout、INT8 SA/GA/qparams硬件约定、目标emulator关系、硬件加载与dump协议。
- **禁止误用**：NDPFuncModel 当前 `extracted_*.npy` 和 `verify_pe` psum 不是可信 golden；42个 JSON也不等于 ResNet算子配置已完成；bitstream生成成功不等于数值正确。
- **接手检查**：Local主工作区依次运行`git status --short`、`.venv\Scripts\python.exe tools\sync_repositories.py verify`、`.venv\Scripts\python.exe -m unittest discover -s tests -v`；fresh checkout可先用`verify --evidence-only`只核对tracked RTL28审计快照。预期根工作树干净、三参考仓匹配lock、RTL28 external evidence匹配hash、登记的全量测试全部通过。2026-07-13已确认managed worktree回收会穿透依赖junction清空Local目标，因此setup对非Local工作树硬失败；依赖`.venv`、三个参考仓或正式W3的任务统一回Local，直到有隔离且通过“销毁安全”验证的新方案。

下一步任务和验收条件只以 `.agents/plan.md` 为准；本文件后半部分是查代码时使用的详细地图，不需要接手时从头逐行阅读。

## 文件入口

- `.agents/agent.md`：默认入口。记录项目背景、当前状态、关键路径、工作原则和风险点。
- `.agents/plan.md`：唯一权威实施计划。记录端到端阶段、已有/缺失状态、难度、方案、依赖和验收门槛。
- `.agents/history.md`：历史日志。记录已经做过的操作、发现、产物和阻塞点。
- `.agents/经验.md`：Codex managed worktree 的可复用经验、失败路径、全局/项目级配置边界和下一项目实施检查表。
- `.agents/rules/算子配置规则.md`：从模型计算到单算子JSON、bitstream、`model_execplan`和数值验证的工作规则，以及对当前DeepSeek资料的反向审核结论。
- `contracts/`：W1开始建立的版本化事实/候选契约；当前包含模型基线、量化语义和仍待批准的架构字段。
- `.agents/decisions/`：关键选择的ADR；ADR-007是当前28-slice RTL/profile权威裁决，ADR-002/003/005已标为旧16-slice历史，ADR-004/006继续有效。

推进任务时，先读本文件；真正开始分析或实现前，再读 `plan.md`；需要追溯之前为什么这么做时，再读 `history.md`。

## 协作原则

- Agent 操作者，也就是当前项目使用者，并不熟悉这个项目；前面部分开发也不是操作者完成的。
- 推进计划前，必须先审查当前代码、文档、路径、依赖和已有产物是否与计划一致。
- 如果发现当前计划不合理、信息不足，或者有明显更好的方案，应先说明判断依据并询问操作者是否更改方案；不要明知方案有问题还继续执行。
- 局部实现细节可以在不改变总体路线的前提下直接做更稳妥的调整，但完成后要说明调整内容。
- 每完成一个明确子任务后，需要向操作者说明：完成了什么、如何验证、还剩什么风险，并同步更新 `plan.md` 和 `history.md`。
- 每次运行、工作包或对话任务结束前，必须根据实际代码、验证结果和`.agents/plan.md`做一次收尾分析，并在最终报告中单列“当前完成位置”和“下一步建议”：明确本轮完成的是哪个W/C/G步骤，区分已完成、部分完成、阻塞和未开始，说明验证与门状态是否变化以及工作树中不属于本轮的改动；下一步建议必须给出按依赖排序的最小原子工作包、选择理由、前置条件、适合单线程还是并行、验收标准和禁止越界事项。即使本轮只是检查、暂停、失败或等待外部信息，也不能省略这两项；不得把candidate登记完整误写成门已通过。
- 不要回退或覆盖已有未提交修改，除非操作者明确要求。
- Git采用三级规则：不改变行为、接口、schema/合同、layout/qparams、依赖锁或产物hash的错字、措辞、注释、空白等微小改动，不单独提交，可随下一次相关提交合并；范围明确且可聚焦验证的较小代码、测试、规则或文档语义改动，只做本地原子Git提交；阶段门通过、跨模块/跨仓重大集成、关键硬件合同、重要恢复检查点，或操作者明确要求时，才把相关本地提交批量推送GitHub并核对远端hash。凡形成提交，都必须在 `.agents/history.md` 台账记录仓库、完整hash、父提交、范围、验证和精确回退点；微小未提交改动在任务报告中列明。大模型、运行产物、trace和其他可再生大文件不得进入普通Git历史。
- 永久保留的是提交，不是副本：尽量只保留完成工作所需的一份工作树，不为备份额外创建clone/worktree/zip；主仓和修改过的子仓提交在history登记后推送到操作者控制的GitHub仓库/fork。冗余副本仅在无唯一未提交内容、远端hash已核对且操作者批准具体路径后删除；不得通过改写或裁剪提交历史节省空间。
- GitHub owner为 `crithbo`。Private主仓 `crithbo/resnet50_int8` 的 `origin/main` 保存根集成代码，Private镜像 `crithbo/NDPFuncModel-private` 的 `private/conv_func` 保存NDP独有提交，公开上游仍保留为 `origin`。本地源码即使全部丢失，也可按主仓 `repos.lock.json` 和 `tools/sync_repositories.py sync` 恢复四份代码工作树；`.venv`、ONNX、golden/trace/hardware dump和普通运行artifact不在GitHub普通提交中，需按lock/hash重新下载或生成。当前这种“代码云端提交、可再生产物不入库”的恢复范围已获操作者接受。后续提交作者名和操作者确认的Gmail已写入四仓repository-local配置；既有提交不改写。

### Codex并行任务与worktree规则

- 必须区分两种并行执行环境。Local任务内派生的协作子代理与主任务共享同一Local工作目录，因此能读取当前tracked源码、`.venv`、三个参考仓和Local-only产物；它们不需要也不得创建junction，但共享工作树意味着只能分配互不重叠的文件范围，Git暂存、提交、全局合同和最终集成仍由Local主任务串行完成。独立Codex managed worktree则只拥有创建时基线commit的tracked快照和明确交付的小型元数据，默认看不到`.venv`、三个参考仓或Local-only产物，也不能假定旧detached worktree包含当前HEAD。
- 每个新工作包开工前必须先判断是否适合并行，不为了“看起来更快”强行拆分。只有共享合同/API已经冻结、子任务没有前后依赖、主要修改文件互不重叠、各自能独立测试和形成可集成提交时，才采用并行worktree；满足条件时优先并行以缩短等待时间。
- 以下情况默认单线程：修改同一schema/contract/公共基类；下游必须读取上游刚确定的layout、qparams或地址规则；需要正式W3数据、整网93边、全量回归或最终集成；仍等待同一项硬件裁决；拆分后会重复实现或产生多套真值。单线程不是保守停滞，而是避免并行返工。
- 并行任务开始前由Local主任务冻结基线commit、公共接口、允许修改的文件集合和验收命令；子任务不得自行编辑共享`.agents`、全局合同或其他任务文件。Local负责按依赖顺序集成、解决接口问题、统一更新合同/文档、执行全量测试并判断是否开启下一并行波次。
- 只读全项目审查优先在Local任务执行；只依赖Git跟踪文件且互不重叠的代码实现才可放新建的独立Codex worktree。任何需要`.venv`、三个参考仓、正式W3或其他Local-only内容的任务，使用Local主任务或其共享目录协作子代理；整网93边、正式W3输入、全量回归和最终集成只在Local主工作区串行执行。
- Codex worktree只天然包含Git跟踪文件。根目录`.worktreeinclude`只复制W3目录第一层的2个小型JSON；桌面宿主当前不能可靠复制更深的ignored路径，因此2个manifest以固定hash的base64快照纳入Git，由setup在worktree内部恢复到原路径。禁止加入W3 `.npy`、整个`artifacts/`、`.venv`或三个参考仓，避免每个worktree重复约951 MB或更多数据。
- `tools/setup_codex_worktree.ps1`只保留Local环境/元数据自检；非Local调用会在任何恢复或链接动作前硬失败。禁止再把Local `.venv`、参考仓或产物以junction/symlink挂入managed worktree；“只读约定”不能约束桌面宿主的回收器。
- 必须修改参考仓时使用独立、可恢复的正式Git工作树并单独提交；不得把Local源目录作为临时worktree清理范围内的链接目标。
- 项目级`.codex/config.toml`使用`approval_policy="on-request"`、`approvals_reviewer="auto_review"`和`workspace-write`；不使用`danger-full-access`。安全操作可自动审查，破坏性、越界写入和不在计划内的网络操作仍需人工许可。
- 并行任务达到“较小改动”本地提交门槛时，只在结束时集中执行一次Git暂存/提交，避免重复权限请求；纯微小改动不强制单独提交。已提交任务报告完整commit、父commit、文件、聚焦测试和回退命令，由Local集成任务统一登记`history.md`并跑全量测试。

## 最终目标

> 从正式 ResNet50 INT8 模型生成每个 ONNX 节点和硬件原子算子的 golden input/output；把 raw tensor 做 partition、padding、relayout、packing 和 remapping，生成硬件测试数据；完成全部单算子 JSON/bitstream；用目标 JSON 模拟器得到结果；把网络 lowering 成目标硬件 execplan；运行 RTL/硬件；最终使 golden、simulator、hardware 在逐算子和整网层面一致。

这不是“JSON 编写任务加几个后续可选项”，而是一条统一的端到端验证链。Golden、数据变换、JSON、模拟器、execplan、硬件 runner 和三方比较全部属于明确目标，不再列为暂缓事项。

需要特别注意：

- “每个算子”包含 ONNX 模型节点和 lowering 后的硬件原子算子；一个 QLinearConv 可能对应多个 K-tile 配置/执行实例。
- 目标硬件已由操作者确认是28个slice；当前物理拓扑和资源事实以ADR-007锁定的`Trassic2.0_RTL@e3bdebba...`活动RTL为准，旧16-slice参数镜像和W4候选不得再作为目标真值。
- `CGRA_SIM` 的旧 `.cu` 功能模拟链和 `ndp-sim-ref` 的 JSON/bitstream 链彼此独立；前者是语义参考，不能代替目标 JSON 模拟器。
- bitstream 生成成功只证明编码/placement 通过，不证明数值正确；单算子至少达到 golden=simulator，最终必须达到三方一致。
- 详细阶段、难度和验收门槛以 `.agents/plan.md` 为准；`.agents/rules/算子配置规则.md` 约束每个配置和跨阶段产物怎样推导与验收。

## 项目流程

本项目本质是硬件开发和验证项目。权威流程是：

1. 固定 ONNX、输入、预处理、软件版本和模型 hash。
2. 建立 ONNX 节点→硬件原子算子 lowering manifest。
3. 生成每个逻辑/原子算子的 raw golden input/output。
4. 对 tensor 做28-slice partition、relayout、packing、remapping，并保留 inverse 变换；主体优先映射到七个真实4-slice小环。
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
  tools/                 # 仓库恢复/验证等维护工具
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

`repos.lock.json` 版本为0.3：三个参考仓显式记录`upstream`、可选`private_mirror`、`branch`、完整`commit`和dirty状态；另以`external_evidence`锁定RTL28静态审计的来源commit、tracked路径、大小和SHA-256。结构由`schemas/repositories_lock.schema.json`约束。仓库/证据操作入口：

```powershell
.\.venv\Scripts\python.exe tools\sync_repositories.py verify
.\.venv\Scripts\python.exe tools\sync_repositories.py verify --evidence-only
.\.venv\Scripts\python.exe tools\sync_repositories.py sync --repo NDPFuncModel
```

`verify`只读并总是先核验external evidence；`verify --evidence-only`不要求三个参考仓存在，适合fresh checkout；`sync`优先从Private镜像恢复本地独有commit，否则使用upstream，并采用partial clone减少空间。现有脏仓、非Git目录、路径越界、证据篡改、HEAD/remote/dirty不一致都会硬失败，不会覆盖现场。

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

`resnet50_pipeline/`、CLI、manifest、contract/backend、artifact、cache/resume、schema、mock fixture和测试已经建立；W0/G0、W2/G2和W3/G3均已通过。接手者不得重做W2/W3，除非合同/hash/回归失败；下一业务阶段是W4。

## 仓库和恢复检查点

| 工作树 | 锁定分支/commit | 远端与作用 |
|---|---|---|
| 根集成仓 | W3业务封版`35a4fde106d102b0e165e7eb13d60f7dd980db71`；当前文档HEAD见Git | Private `crithbo/resnet50_int8`，W0～W3代码、合同和文档 |
| `CGRA_SIM` | `53c41e02c294bcc54379e686dc9d25bbb93919fa` | 公开upstream，QNN语义和旧ResNet参考 |
| `ndp-sim-ref` | `e299b2804448242d1589b3e58ed7c5a9a5eca09f` | 公开upstream，JSON/bitstream/execplan参考 |
| `NDPFuncModel` | `conv_func@35eab40e5314bf603481dd6268bc96ab2ca514a6` | Private `crithbo/NDPFuncModel-private`，W2修复后的Conv功能模型 |

`repos.lock.json`是三个参考仓的恢复真值，也是RTL28静态审计快照的离线校验真值；用`tools/sync_repositories.py verify`统一核验，用`verify --evidence-only`在fresh checkout只验tracked证据，用显式`sync --repo <name>`恢复缺失参考仓。当前四个代码工作树均应干净。正式模型、`.venv`和W3大产物不在普通Git提交中；C0登记的九份小型legacy16 W4报告例外，已按hash跟踪以保证合同可复核。

NDPFuncModel仍不是目标JSON/bitstream解释器；其`conv_config`缺URL、`graph/`缺源码、`hex_data/`未随仓提供。W2参数化fixture已绕开这些缺失并完成软件验证，但不能据此批准正式硬件接口。

## 本地 Python 环境与已验证入口

项目使用根目录持久化虚拟环境：

```text
.venv\Scripts\python.exe
```

- 基础约束记录在 `requirements-resnet50.txt`，2026-07-11 的精确解析版本记录在 `requirements-resnet50.lock.txt`；`.venv/` 已由根目录 `.gitignore` 忽略。
- 环境为 CPython 3.12.13，直接依赖包含 NumPy 1.26.4、ONNX 1.22.0、ONNX Runtime 1.27.0、PyTorch 2.13.0+cpu、OpenCV、Pillow、Matplotlib、OpenPyXL 和 tqdm；`pip check` 已通过。
- PyTorch不能继续视为可选：`CGRA_SIM/cgra_python/__init__.py` 会传递导入 `op_lib`，其中 MaxPool 直接导入 torch。
- `ndp-sim-ref/model_execplan/main.py --help` 已成功，证明 execplan Python 前端可启动。
- `NDPFuncModel/main_CONV_N2N.py` 曾在 `artifacts/smoke/NDPFuncModel` 隔离worktree中运行到 `DRAM.init_from_file()`，停在缺少 `./hex_data`，不再缺Python包。该额外worktree已在操作者批准后删除并清理Git元数据，释放约130.68 MiB；现场结论保留在history。
- `CGRA_SIM/.../golden.py` 旧入口仍会被 `cgra_python/layout/layout_buffer.py:201` 的既有 `SyntaxError`影响；W3已经通过根集成层零导入隔离完成正式全节点golden，不得再把该语法错误写成W3阻塞。只有需要修复/运行旧CGRA入口时才单独处理。
- `.venv` 当前约917 MiB，主要体积来自CPU PyTorch；运行产物统一放 `artifacts/`，不要覆盖三个仓库内的跟踪trace。

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

`NDPFuncModel/main_CONV_N2N.py` 是上游固定4-slice Conv示例入口：4 bank、6144 row、64 col、每subword 16 byte，每slice使用8×8 `SpecialPEA`。上游`89d1655`曾让四个逻辑slice的activation实际都读物理slice0；W2本地修复`789d121`已经修正slice/bank与transaction寻址，参数化fixture的1/4-slice数据通路已逐地址通过。固定主入口仍未接入JSON/qparams/正式writeback，因此以下缺陷清单必须区分“上游/固定入口遗留”和“W2 adapter已修复”，不能再统称当前根主线未实现。

关键目录和职责：

- `component/DRAM.py`：slice/bank/row/col/subword 存储及物理地址换算，只从每 slice 的 bank0 文本载入字节。
- `component/IGA.py`：LC 的 `[start,end)` 迭代，以及 `last`/`last_index` 解析；与已确认的“LC 控制循环、last_index 表示循环层级”一致。
- `component/RDAG.py`、`WRAG.py`、`BufAG.py`：DRAM 读写和 Buffer 地址生成、16-byte valid/padding/branch mask。
- `component/Buffer.py`：数据、last/last_index/branch tag、列反序存取和 tag 压缩。
- `component/SpecialPEA.py`：8×8 PEA、每 PE dot、int32 psum、邻接/分支处理和输出 buffer packing。
- `component/DataTransfer.py`：DRAM→AG→Buffer→PE、PE 执行、邻接传输和候选写回的主要 trace 链；Conv AG 参数仍由 Python 函数硬编码，不从 JSON 读取。
- `component/ActiUnit.py`：`7a47701` 已修复候选requant，支持int32×float32 multiplier、nearest-even、scalar/per-channel广播、output zero-point和uint8饱和；physical probe已调用，Conv主入口仍未调用。
- `main_GEMM*.py`、`main_GEMV.py`、`generate_gemm_fp16.py`：GEMM/GEMV 开发与验证参考，不是 ResNet Conv 主线。
- `verify_*.py`、`torch_verify*.py`、`test_compare.py`、`track_data_path.py`：trace/统计验证工具；当前没有对 QLinearConv 做坐标级 bit-exact 全输出比较。
- `config/`：旧配置位拼接工具，与 `ndp-sim-ref` 同源的历史参考；没有接入 Conv 主入口。其中 `config_generator_ver2.py` 是固定 Conv 配置，`config_nse.py` 是增加邻居流和重复 LC 链的版本，`nse_cnt_size=15` 只说明旧16-slice/ring样例，已被ADR-007判定为非目标证据。它们属于旧寄存器架构，且输出路径硬编码，不能不经版本映射直接复制成目标 JSON。
- `kernel/add_config_MN_N.json`、`output/add_config_MN_N_pseudocode.py`：ADD JSON 与生成伪代码的完整工作样例，不是 Conv 配置。`graph/` 虽只跟踪 CPython 3.12 `.pyc`，但已恢复其职责：加载 JSON 为 LC/PE/AG 依赖图、拓扑排序、生成嵌套循环伪代码和地址队列；因此是可恢复的配置前端，不再视为完全未知文件。
- `verify_pe/` 及各 dump 目录：大量生成 trace/日志，属于验证产物，不是配置规则真值。

该仓库补齐的是“Conv 数据通路怎样走”的W2功能参考：DRAM几何、地址/掩码、Buffer行列、8×8 PEA、4-slice ring和psum provenance可用于设计ResNet Conv relayout与配置适配。下列条目记录固定主入口/上游遗留；其中寻址、整数乘累加、reduction和probe requant/writeback已由W2 adapter形成软件候选回归，但目标JSON、RTL28布局和正式主入口仍未闭合：

1. 上游 `reduc_state = r*s*cc_shared` 不可能正确表示多层循环末态，且在每个R后清空psum；本地 `86cd3e3` 已改用LC `last/last_index`并把清零移到完整C/S/R+ring之后。`d212225` 和根adapter已用全部输出坐标验证四段ring整数累加；真实主入口flush/writeback仍未恢复。
2. `run_buffer_writeback_to_dram()` 仍只记录“将要写回”的日志，实际 `dram.stream_write()` 被注释；`3cb0ef9`完成的是probe路径按provenance地址的真实单字节写回，不能冒充主WRAG路径已修复。
3. INT8 Conv主入口输出仍走FP16 packing；虽然probe已执行per-channel requant/zero-point/saturation，主入口创建的 `ActivationUnit` 仍没有被使用。
4. 上游PEA按signed A×unsigned B计算；本地 `deee41f` 已按主链实际端口修为uint8 activation A×int8 weight B，并由physical-address dot probe与QLinearConv accumulator对齐。目标硬件物理端口仍需外部确认。
5. 主示例固定4 slice，只能作为一个小环的数据通路参考，不等于七小环/28-slice整机，也没有 JSON/bitstream、qparams 或命令行参数化接口。
6. 上游 `SpecialPEA.PE.execute()` 的INT8路径经过 `np.float128/float32` 且debug含 `.asctype`；本地 `deee41f` 已改为纯int32 psum、int64检查中间值并移除函数内直接 `np.float128`。溢出暂显式报错，等待硬件规则裁决。
7. 上游 `89d1655` 的 `DRAM.per_slice` 少乘 `bank_num`；本地 `789d121` 已修复并用4-slice独立写读验证。旧 `extracted_bias.npy` 和旧trace仍由错误版本生成，继续禁止作为真值。
8. 上游 `run_dram_to_ag()` 只把 `slice_id` 写进日志名；本地 `789d121` 已把完整slice byte span加入AG tensor base，slice0～3数据与物理provenance测试通过。
9. 上游RDAG/WRAG多transaction路径丢弃strided transaction地址；本地 `789d121` 已分离逻辑counter与物理transaction offset，读写AG的跨16-byte边界地址序列对称通过。
10. `verify_pe` 的 psum 文件在卷积 reduction 前写出，实际只是 bias preload 快照；`extracted_act/weight/bias.npy` 又由缺陷链路生成，均不得作为 Conv golden 或回归真值。

因此它应标为【W2 Conv功能参考/目标适配待完成】，不能标为“目标JSON emulator已有”。根adapter与统一manifest已经存在；后续任务是把获批的RTL28 Conv layout/JSON字段映射到该参数化runner，验证正式shape后再判断它能否升级为目标Conv emulator，而不是重新实现W2小Conv真值。

## 当前闭环状态

- **模型和golden——W3/G3已通过**：模型/input/hash和ORT设置已锁定；正式保存79个运行时tensor和55个lowering内部INT32 tensor，全部78节点由独立公式重放并匹配ORT。旧`golden.py`的30个唯一检查点只保留为历史参考。
- **lowering和身份映射——W3语义层已完成**：78个ONNX节点稳定lower为133个语义hw_op；旧77模型级原语已逐项映射，Flatten明确为zero-copy。JSON实例、逐K-tile和execplan身份在W4/W5/W7继续扩展，不得说成W3尚未实现。
- **数据变换——RTL28 C1已完成/其余W4继续**：C1已提供Quantize、Dequantize和singleton-spatial View在group4x7/LOW两个profile上的正逆、坐标解释与验证；旧综合审计虽覆盖78/78节点、93条runtime边和91条量化qparam链，但旧物理签名、成本和容量仍已过时。新W4还必须完成Conv、Pool、Add、GAP、MatMul以及新93边、生命周期/alias和性能成本；G4=`not_passed`、`w5_authorized=false`。
- **单算子配置——部分已有**：42 个静态 JSON 中只有 MaxPool、sum 型 AvgPool、固定样例 quant、fp32 输出 add-dequant 可局部参考；6 个 SA JSON 全是 FP16、bias=0；没有核心 INT8 Conv/MatMul。
- **W2/G2小Conv软件闭环已通过**：`NDPFuncModel@35eab40` 的参数化runner在同一fixture上完成1/4-slice全部84坐标，实际经过DRAM、input Buffer、SpecialPEA、ActivationUnit、output Buffer和DRAM；NumPy、im2col、ORT、CGRA QNN rounding与NDP的accumulator/D一致，physical D可inverse且全部物理字节可解释。该结论不批准旧固定主入口、目标JSON或硬件layout；C0/C1已冻结RTL28机器合同和公共布局，下一Conv算子波次再把该fixture能力组合进七个真实小环。
- **execplan——28-slice框架已有/ResNet适配没有**：可规划28个slave、28-bit mask、地址、bitstream、指令和Bank_data；schema仍缺numeric attributes，旧配置镜像与目标RTL存在版本冲突，bitstream失败后部分路径还会继续。
- **RTL/硬件——外部阻塞**：没有完整 runner/testbench、加载/启动/完成/dump 协议或逐算子 checkpoint 入口。
- **三方比较——通用逻辑比较器已就绪/真实结果未到位**：根集成层已实现inverse-relayout之后的两方/三方比较、整数bit-exact、浮点显式容差、错误分类、拓扑首错和provenance；旧runner与128-bit物理文件工具仍不能替代它。当前没有目标simulator/hardware逻辑输出，也没有获批inverse layout，因此尚无真实三方通过结论。

## 当前最高优先级

严格按`.agents/plan.md`的W0→W9工作包和G0→G9验收门推进。W0/G0、W2/G2、W3/G3已经完成；W1已选定目标RTL commit但G1未通过。W4-28的C0机器合同/legacy隔离和C1公共geometry与Quantize/Dequantize/View布局已经完成，P4已允许下一波分文件并行Conv、Pool、MatMul；旧16-slice software readiness不再代表当前进度。下一业务步骤仍属于W4，不进入W5。任何W1～W3修改都必须先说明会使哪些manifest/hash/下游产物失效。

优先推进：按P4边界实现Conv七小环、Pool（MaxPool+GAP）和MatMul七小环/大环候选，主任务只读审阅各任务并顺序集成；若需要修改C1公共API，立即退回单线程。与此同时继续等待`e3bdebba...`的clean elaboration、端口layout、最小INT8 SA+bias+requant、目标emulator以及硬件load/dump批准。旧ONNX、旧16-slice产物、原`hex_data`和`conv_config`均只作兼容性资料。

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
  -> 统一 ONNX node/tensor/语义 hw_op lowering（W3/G3已完成）
  -> raw node golden + 55个语义内部tensor golden（W3/G3已完成）
  -> 28-slice七小环主profile/大环候选的partition/relayout/packing/remapping（待实现）
  -> ndp-sim-ref/jsons + bitstream（框架已有，ResNet INT8 配置待实现）
  -> 目标 JSON/bitstream emulator（仓库内缺失）
  -> model_execplan + cfg_pkg + Bank_data（28-slice框架已有，ResNet/真实拓扑待适配）
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
- `utils/config_parameters.py`、`config_parameters_ver1.py`：已失效的旧16-slice参数镜像；给出16/4/4/8/3等slice内资源数和寄存器位宽，但与当前bitstream及目标RTL冲突，只作版本考古。
- `utils/bitgen.py`、`module_idx.py`：旧位拼接和模块编号辅助。
- `utils/excel_config.py`、`excel_generator.py`：从表格生成/整理寄存器配置说明。
- `get_parameters.py`、`get_random_data.py`：参数和随机数据辅助。
- `temp.txt`：旧编码器输出的一份 63-bit 左右二进制行样例，没有来源/版本元数据，只能作为历史产物，不能决定目标位流。

这部分只能交叉验证字段来源，不能直接决定目标 RTL 编码。

### 其他顶层内容

- `run_all_slices.py`【实验】：生成并运行ring GEMM多slice JSON，默认4 slice；按slice改高位地址。bitstream失败会每两秒无限重试，不能作为目标七小环/28-slice入口。
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

两版`sm_count=16`仅描述旧性能模型，已不匹配目标28-slice；仍可参考单阵列吞吐公式，但不能用于整机数量、LC/stream/PE位宽或正式性能结论。

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
- `config/`是历史配置生成/寄存器拼接代码；`config_generator_ver2.py`和`config_nse.py`分别给出固定Conv与旧邻居流Conv字段实例，后者NSE计数15只对应已废止的16-slice样例；`config_parameters.py`与`config_parameters_ver1.py`对应不同旧版本。主Conv没有导入该目录，不能据此认为Conv已由配置驱动或符合目标28-slice RTL。
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

结论不是“所有代码都可运行”，而是“没有仍无法解释用途的有效文件”：未闭环文件已标为实验/骨架，空文件、第三方PLY、生成parser表、Office锁文件、测试桩和无关备份已单独识别。参考仓本身没有提供正式ResNet INT8 ONNX/参数/golden产物、完整目标28-slice逐算子relayout、能直接解释目标JSON/bitstream的数值emulator、ResNet ONNX→NDP实例/execplan adapter、RTL/硬件runner或通用三方比较器。根集成层后来已自行补齐正式模型/W3全节点golden/lowering身份、旧16布局审计框架和通用逻辑比较器；当前仍缺28物理布局、JSON实例/execplan adapter和目标sim/hardware链。

## 剩余问题按解决方式分级

### 必须取得外部权威信息

1. activation、weight、bias、scale/zp 的正式物理layout和三维shape解释。
2. INT8 SA 的端口、`bias_enable`、int32 psum、requant和可选ReLU接口。
3. GA 的unsigned max、转换、rounding、saturation和溢出语义。
4. per-layer/per-channel qparams采用constant patch、tensor stream还是逐层静态JSON。
5. 已选`Trassic2.0_RTL@e3bdebba...`的clean elaboration、ISA/register-map最终批准、板级地址和指令/配置流闭合；顶层`NDP_Top_new`、filelist、28-slice资源与静态字段证据已由C0锁定为candidate，不再重复询问源码位置。
6. `NDPFuncModel/conv_func`是否就是目标Conv模拟器基线；若是，需提供目标JSON/bitstream到参数化runner的映射和获批的uint8×int8/requant/七小环/writeback约定。原`conv_config`/`hex_data`只作可选兼容资料，不再作为W4开工前置。
7. 非Conv算子的目标emulator，以及硬件/RTL的加载、运行、完成判定和dump协议。

配置算法类问题的详细证据见 `.agents/rules/算子配置规则.md` 第14.3节；完整资料请求见 `plan.md`。

### 仓库内必须实现

- 统一ONNX→硬件原子算子lowering和manifest。【W3语义身份已完成；W5/W7继续扩JSON实例、tile与execplan字段】
- 全节点raw golden、QNN子步骤golden和可重放测试输入。【W3/G3已完成79个runtime+55个internal tensor；不得作为待办重跑】
- 逐算子实现ResNet 28-slice partition/relayout/packing/remapping及全部逆变换，主体使用七个4-slice小环，并为代表层实现28-slice大环候选；覆盖Quantize、Conv、MaxPool、Add、AvgPool、MatMul/dense、Dequantize和Flatten/View。
- 全部 ResNet 原子 JSON、base-info、handler、量化常量参数化和稳定 bitstream。
- 目标 emulator runner、输出提取和逻辑 tensor 恢复。
- 28-slice真实物理拓扑的ResNet execplan前端、schema扩展、严格失败和完整数据包。
- RTL/硬件 runner、checkpoint/dump 和版本记录。
- 用已完成的通用逻辑比较器接入真实golden/simulator/hardware结果，并建立逐算子到整网的分层回归。

### 功能正确性闭环后再做

- 性能模型/Ramulator 与真实硬件时序的精确标定。
- 非 ResNet 模型通用化和 batch≠16 的性能调度优化。
- 对未接入目标链的 Python/Go/TOML 时序骨架做大规模重构。

这些不阻止功能正确性闭环，但只要影响实际 JSON 编码、地址或硬件结果，就必须提前升级为阻塞项。

## 已经不再未知的规则

- 目标是28个slice；主体性能profile使用七个真实4-slice小环，28-slice大环只在成本/实测占优的层启用。
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
