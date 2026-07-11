# ResNet50 INT8 工作日志

最后更新：2026-07-11

本文件只保留已经发生的关键决策、验证和状态变化。当前任务看 `.agents/plan.md`，代码和仓库细节看 `.agents/agent.md`，单算子推导看 `.agents/rules/算子配置规则.md`。

## Git提交、GitHub备份与本地空间规则（2026-07-11最终修正）

- 每个有效小步骤都要提交；`history.md` 必须记录仓库、完整40位commit、直接父commit、改动范围、验证结果和精确回退位置。短hash只用于正文易读，不能替代本节台账。
- 回退默认使用 `git revert <commit>` 生成保留历史的新提交；不得自行使用reset、rebase、filter、强推或删除提交。任何改写历史仍须操作者单独确认。
- 操作者最终澄清：真正需要永久保留的是提交，不是仓库目录副本。项目应尽量只保留一份必要工作树，不为备份目的额外创建clone、worktree、zip或目录复制；云端恢复以GitHub已推送提交为主。
- 主仓和发生修改的子仓都必须先提交、在history登记，再推送到操作者控制的GitHub仓库或fork。不得把对上游仓库可能无权限的 `origin` 当成已经完成云端备份。
- 冗余本地副本只有在其中没有唯一未提交内容、所有需保留提交已经推送并核对远端hash、且操作者批准具体路径后才能删除。删除副本不等于删除提交；不得通过reset/rebase/filter/强推或裁剪历史来节省空间。
- `.venv`、模型、golden、trace和运行artifact不是仓库副本，也不会由普通GitHub提交自动备份；它们按可重建性和大文件策略另行管理，不能混入普通Git历史。
- Git commit hash由提交内容决定，提交无法在自身文件内容中稳定写入自己的hash。因此业务/代码提交在同一次或紧随其后的history同步提交中登记；最新一笔“只更新台账”的提交以当前 `HEAD` 和 `git log -1 --format=fuller` 精确定位，并在下一次台账同步时补入。不得借此漏记任何业务提交。

## 精确提交台账

### 根集成仓库 `resnet50_int8`

1. `5bf423fe49170b5a4333b4912a6f3d44ab85624d`，无父提交，`chore: establish ResNet50 INT8 pipeline baseline`。
   - 范围：建立W0集成骨架、contracts/schema/manifest/backend/artifact/cache、QLinearConv双golden、测试、三个接手文档及仓库边界。
   - 验证：W0 11项和QLinearConv 4项，共15项测试通过；正式模型/输入hash与环境锁定已记录。
   - 精确位置：这是根仓库首个可恢复基线；查看或重建首版使用本commit。没有可回退的根仓父提交。
2. `dbd78ab2ed8343e4571eda9d48ef44689da962bc`，父提交 `5bf423fe49170b5a4333b4912a6f3d44ab85624d`，`feat: add reversible small-conv physical layout`。
   - 范围：新增NDP DRAM几何、稀疏物理镜像、1/4-slice Conv候选layout、逐字节provenance、forward/inverse与tail/alignment处理。
   - 验证：根仓20项测试通过；1/4-slice raw↔physical round-trip bit-exact。
   - 精确回退：保留后续历史时revert本commit；需要检查改动前状态时定位父提交 `5bf423f…`。
3. `016b594051b6501491d7440cd738ee3976c8e106`，父提交 `dbd78ab2ed8343e4571eda9d48ef44689da962bc`，`feat: connect W2 physical image to NDP DRAM`。
   - 范围：新增显式NDP子进程adapter，把W2 physical bundle写入NDP DRAM并逐region校验hash/slice；锁定NDP寻址修复版本。
   - 验证：根仓21项、NDP寻址4项测试通过；raw↔physical↔NDP DRAM bit-exact。
   - 精确回退：revert本commit；改动前根状态为 `dbd78ab…`，配套NDP基线应回看 `789d121…` 的父提交说明。
4. `8e3f7db689ed66d0344fc22e2c260db69d8241b5`，父提交 `016b594051b6501491d7440cd738ee3976c8e106`，`feat: validate INT8 PEA from physical addresses`。
   - 范围：adapter新增physical-address INT8 dot probe；从activation/weight物理地址驱动PEA；合同和覆盖矩阵记录候选INT8语义。
   - 验证：根仓21项、NDP 8项测试通过；单输出坐标int32 accumulator与独立QLinearConv golden一致。
   - 精确回退：revert本commit；改动前根状态为 `016b594…`，配套NDP状态为 `789d121…`。
5. `7ca487b5da2be273dcef435c474c6d6ef45ec99d`，父提交 `8e3f7db689ed66d0344fc22e2c260db69d8241b5`，`chore: record corrected Conv reduction control`。
   - 范围：把NDP reduction修复hash写入lock/quantization contract，并同步agent/history/plan/规则的完成边界。
   - 验证：根仓21项、NDP 11项测试通过；JSON解析与 `git diff --check` 通过。
   - 精确回退：revert本commit；改动前根状态为 `8e3f7db…`，配套NDP状态为 `deee41f…`。
6. `d85a1576ba01d9caa5ae7784344b5e685af4da2f`，父提交 `7ca487b5da2be273dcef435c474c6d6ef45ec99d`，`docs: add precise Git recovery ledger`。
   - 范围：建立完整提交台账和恢复规则；该提交当时记录的“保留子仓库副本”策略后来被操作者进一步澄清，现行规则已由 `f0cfd3b…` 改为“保留提交、减少副本、优先GitHub”。
   - 验证：三个文档差异通过 `git diff --check`；逐项对照根仓 `git log` 与NDP `origin/conv_func..HEAD` 的完整hash/父提交。
   - 精确回退：revert本commit；改动前根状态为 `7ca487b…`。revert只撤销文档策略，不会删除任何代码或子仓库提交。
7. `8d21d736435b88ef98ea205b5d0236fbf8d56208`，父提交 `d85a1576ba01d9caa5ae7784344b5e685af4da2f`，`chore: sync Git recovery ledger`。
   - 范围：把 `d85a157…` 的完整hash、父提交、验证和回退位置同步到本台账。
   - 验证：`git diff --cached --check`通过，提交后工作树干净。
   - 精确回退：revert本commit；改动前根状态为 `d85a157…`，只影响台账登记。
8. `f0cfd3bc08abf0acc1d0aa5f01c505745a93cc1a`，父提交 `8d21d736435b88ef98ea205b5d0236fbf8d56208`，`docs: prefer GitHub over local repository copies`。
   - 范围：最终澄清“永久保留提交而非副本”，建立少副本/GitHub优先规则；审计主仓、三个参考仓、linked worktree、artifact和依赖环境的实际空间与远端状态。
   - 验证：逐仓运行 `git worktree list`、`remote -v`、`branch -vv`、`status`、`count-objects -vH`并统计目录大小；三个文档通过 `git diff --check`。
   - 精确回退：revert本commit；改动前根状态为 `8d21d73…`。该回退只撤销最终策略/审计文档，不删除提交、副本或artifact。
9. `677b0b45538f352f75377333b6fc32234a4006ee`，父提交 `f0cfd3bc08abf0acc1d0aa5f01c505745a93cc1a`，`chore: sync GitHub backup policy ledger`。
   - 范围：登记 `f0cfd3b…` 的完整hash、父提交、验证和回退位置，并注明旧副本策略已被GitHub优先策略取代。
   - 验证：`git diff --cached --check`通过，提交后工作树干净。
   - 精确回退：revert本commit；改动前根状态为 `f0cfd3b…`，只影响台账内容。
10. `2f480ccfca4bc17d5fb153e6e4f3e1f6626cc797`，父提交 `677b0b45538f352f75377333b6fc32234a4006ee`，`docs: record redundant worktree removal`。
    - 范围：记录已批准删除 `artifacts/smoke/NDPFuncModel` linked worktree、实际释放空间、删除后验证，以及主仓/NDP建立可写GitHub远端所需信息。
    - 验证：目标路径不存在；NDP `git worktree list`只剩主工作树；NDP工作树干净；artifact总量约33.90 MiB；文档通过 `git diff --check`。
    - 精确回退：revert本commit只撤销记录，不能也不应恢复已删除的冗余worktree；如确需重现烟测现场，可从记录的 `89d1655…` 临时创建新的可删除worktree。
11. `38c6c0a2152f833a50d05cb00678a9d0b4c15679`，父提交 `2f480ccfca4bc17d5fb153e6e4f3e1f6626cc797`，`chore: sync worktree removal ledger`。
    - 范围：登记 `2f480cc…` 的完整hash、父提交、删除验证和重现方式。
    - 验证：`git diff --cached --check`通过，提交后主仓工作树干净。
    - 精确回退：revert本commit；改动前根状态为 `2f480cc…`，只影响台账内容。
12. `4b7d7e1b4475c0763c936abc80489ab676711a86`，父提交 `38c6c0a2152f833a50d05cb00678a9d0b4c15679`，`docs: record private GitHub remotes`。
    - 范围：记录GitHub owner、repository-local提交身份、两个Private空仓、主仓/NDP远端配置和CGRA剩余云端任务。
    - 验证：主仓 `origin`、NDP `origin/private` URL正确；GitHub页面确认两仓均为Private且创建时为空；`git diff --cached --check`通过。
    - 精确回退：revert本commit；改动前根状态为 `38c6c0a…`。远端和本地Git配置位于`.git/config`，不随文档revert改变。

### 子仓库 `NDPFuncModel/conv_func`

上游共同基线为 `89d1655ce6450477cdcc04965d8b4866f12066e5`。以下提交均为当前本机独有提交，尚未推送到 `origin/conv_func`：

1. `789d121327d8e855d33f16c2103a6422a521fa25`，父提交 `89d1655ce6450477cdcc04965d8b4866f12066e5`，`fix: correct slice and strided AG addressing`。
   - 范围：修复DRAM `per_slice`漏bank、slice AG基址、RDAG/WRAG跨transaction物理地址；新增physical image probe和寻址测试。
   - 验证：4项寻址回归通过，覆盖4-slice独立读写及跨16-byte transaction。
   - 精确回退：revert本commit；纯上游状态为父提交 `89d1655…`。旧trace/`.npy`不得因此恢复为真值。
2. `deee41fdb1d2f344a283df757bfbc8f0b6dd27af`，父提交 `789d121327d8e855d33f16c2103a6422a521fa25`，`fix: keep INT8 PEA accumulation integer`。
   - 范围：固定uint8 activation A×int8 weight B、int32 psum/int64检查中间值、branch lane清零和显式overflow；扩展物理地址dot probe。
   - 验证：NDP累计8项测试通过；单坐标物理地址dot可由根adapter与golden核验。
   - 精确回退：revert本commit；保留寻址修复的上一状态为 `789d121…`。
3. `86cd3e328b45c37a1c8a133c650eb1f756b0c233`，父提交 `deee41fdb1d2f344a283df757bfbc8f0b6dd27af`，`fix: preserve psums through final reduction`。
   - 范围：用LC `last/last_index`替代错误乘积末态；将psum清零移到完整C/S/R与ring reduction之后；新增reduction调度测试。
   - 验证：NDP累计11项测试通过，覆盖词典序末态、非零start、非单位step和非法状态；完整D仍未跑通，G2未通过。
   - 精确回退：revert本commit；保留寻址和整数PEA的上一状态为 `deee41f…`。

## 当前本地副本与空间审计（2026-07-11）

- 父目录中只有当前主仓 `resnet50_int8`，没有第二份主仓clone、额外worktree或项目zip/bundle备份；主仓 `.git` 约0.64 MiB。
- 主仓内有三个必要的独立参考仓工作树：`CGRA_SIM`约347.14 MiB、`ndp-sim-ref`约390.35 MiB、`NDPFuncModel`约266.95 MiB。它们不是主仓Git历史中的重复内容，而是各自独立仓库。
- 操作者批准后，冗余linked worktree `artifacts/smoke/NDPFuncModel` 已通过 `git worktree remove --force` 删除并执行 `git worktree prune`，释放约130.68 MiB。删除前确认其没有独有提交或源码改动，仅有运行生成的跟踪 `.pyc` 变化；删除后NDP worktree列表只剩 `NDPFuncModel@86cd3e3`，主NDP工作树干净，artifact总量降至约33.90 MiB。
- `.venv`约917.41 MiB，是共享依赖环境而非仓库副本；`artifacts/reference_model`约33.87 MiB，是ONNX/输入/输出基线而非仓库副本。三份W0小artifact合计不足0.03 MiB。
- `CGRA_SIM/.git`另报告约113.98 MiB临时pack垃圾；这不是有效提交副本，可在确认仓库状态后用Git维护方式清理，但本轮未删除。
- GitHub owner确认为 `crithbo`；后续提交作者名配置为 `crithbo`，提交邮箱使用操作者确认的Gmail。身份写入四个仓库的repository-local Git配置，不改写任何既有commit，也不在项目文档重复保存私人邮箱明文。
- 已创建并由GitHub页面确认两个空Private仓库：主仓 `https://github.com/crithbo/resnet50_int8.git`，NDP独立私有镜像 `https://github.com/crithbo/NDPFuncModel-private.git`；均未初始化README、LICENSE或`.gitignore`。
- 主仓 `main` 已推送到Private `origin/main`，NDP `conv_func` 已推送到Private `private/conv_func`；两次push均成功并建立tracking。已在登录后的GitHub提交页独立确认主仓 `4b7d7e1b4475c0763c936abc80489ab676711a86` 和NDP `86cd3e328b45c37a1c8a133c650eb1f756b0c233` 可访问，云端备份状态为完成。
- `CGRA_SIM`仍没有可写remote且有4个进入任务前已有的未提交修改；`ndp-sim-ref`干净并跟踪上游 `origin/main`。CGRA需先审核既有修改，再按同一策略建立Private镜像。
- NDP的3个独有提交不能跟随主仓一起推送，因为它是独立Git仓库；已为其建立独立Private镜像。`CGRA_SIM`需先审查4个既有未提交修改，再决定是否提交到单独Private镜像；干净的 `ndp-sim-ref` 暂可继续以固定上游hash恢复。

## 2026-07-05～2026-07-09：确认原始ResNet参考链

- 克隆 `CGRA_SIM`，基线commit为 `53c41e0`；确认其中已有ONNXRuntime golden、QNN软件算子、DDR辅助、旧手写execution plan和Python functional simulator。
- 确认旧 `.cu` 功能模拟链不等于目标JSON/bitstream链；golden dump不完整、路径硬编码、checkpoint数量不足。
- 将项目协作文档统一迁到根目录 `.agents/`：`agent.md`负责接手入口，`plan.md`是唯一执行计划，`history.md`只记事实。

## 2026-07-10：引入NDP工具链并完成两仓审计

- 拉取 `ndp-sim-ref`，基线commit为 `e299b2804448242d1589b3e58ed7c5a9a5eca09f`；完整工作树413个跟踪文件。
- 定位目标主线：42个单算子JSON、JSON→bitstream、`model_execplan`、DeepSeek golden/relayout和address-remapping；将计算到配置的规则整理为 `.agents/rules/算子配置规则.md`。
- 固定seed批量测试42个JSON：38个模板曾成功生成完整bitstream，4个仍受placement约束失败；bitstream成功只证明编码/placement，不证明数值正确。
- 确认现有JSON只局部覆盖ResNet：核心INT8 Conv/MatMul、完整Add/AvgPool requant和逐层qparams传递仍缺失；`model_execplan`仍含28-slice假设和unresolved constant风险。
- 从旧ResNet计划还原77个模型级原语：2 Quantize、53 Conv、1 MaxPool、17 Add、1 AvgPool、1 MatMul、2 Dequantize；确认Conv首/中/末K tile分别执行bias初始化、int32 psum累加和requant。
- 操作者确认目标硬件为16个PE/slice阵列；仓库中的28-slice DeepSeek约定改为待适配参考。不同版本的资源数、字段位宽、opcode和DDR row存在冲突，不能混用。
- 全量审计 `CGRA_SIM` 275个、`ndp-sim-ref` 413个跟踪文件；唯一Python语法错误为 `CGRA_SIM/cgra_python/layout/layout_buffer.py:201`。

## 2026-07-11：引入Conv模型、建立环境和端到端计划

- 克隆 `NDPFuncModel/conv_func`，commit为 `89d1655ce6450477cdcc04965d8b4866f12066e5`；完整历史47个提交，1232个跟踪文件。
- 确认其提供硬编码Conv DRAM→AG→Buffer→8×8 PEA→ring通路和旧固定配置，但不读取目标JSON/bitstream；`config_nse.py`的NSE count=15是16个PE间15次邻居传递的候选证据。
- 确认关键缺陷：`hex_data`缺失；slice跨度漏bank；逻辑slice0～3实际都读物理slice0；RDAG/WRAG遗漏multi-transaction偏移；A/B符号与ResNet参考相反；int32 psum经过浮点；最后reduction判定错误；requant和真实DRAM writeback未完成。
- 当前 `extracted_*.npy` 和 `verify_pe` psum由错误链路生成，不得作为golden。
- 创建根目录持久化 `.venv`（CPython 3.12.13），安装并锁定NumPy、ONNX、ONNX Runtime、PyTorch CPU、OpenCV等依赖；`pip check`通过。`model_execplan --help`可启动；Conv入口运行到缺 `hex_data`；golden入口运行到既有语法错误。
- 将最终目标确定为：正式ONNX→全节点/硬件子步骤golden→16-slice relayout→全算子JSON/bitstream→目标simulator→execplan/Bank_data→RTL/硬件→三方逐算子和整网一致。
- 将执行计划统一为W0～W9工作包和G0～G9验收门；W0先建立根集成层、manifest、contract、adapter、artifact和mock状态机，W1外部规格并行，W2以小Conv建立第一条真实纵向闭环。
- 审核计划并补齐根repo/`repos.lock.json`、architecture/quantization/backend contract、不可变attempt、resume失效、adapter能力探测、memory地址安全、分层CI和operator coverage matrix。
- 删除临时独立阻塞报告，其有效结论已合并进 `plan.md`，避免重复文档漂移。

## 2026-07-11：W1暂定模型基线

- 操作者暂定接受官方ONNX Model Zoo `resnet50-v1-12-int8.onnx`作为正式模型；已下载并通过checker，SHA-256为 `c234f30975989788b4405f25253275aae247ab6dbdd34aaa69ab0a59ff76f6d0`。
- 预处理暂定复现旧 `golden.py`：RGB输入直接缩放到256×256、中心裁剪224×224、除以255后使用ImageNet mean/std归一化、HWC→CHW。复核后确认ONNX本身不规定resize；旧脚本明确加载同名模型且检查节点与当前图匹配，是旧功能模拟链的实验性golden基线。此前“官方必然保持宽高比、与旧脚本冲突”的表述证据不足，撤回为待官方评测源码核验。
- 旧ONNX、DDR、golden和原 `hex_data`降级为兼容性回归资料，不再作为软件工作开工前置。
- 模型IR 4、opset 12、78节点、366 initializer；算子数量与旧77原语计划完全一致。53层Conv全部为UINT8 activation、INT8 weight、INT32 bias、per-output-channel weight scale，weight zero point全为0，但input/output zero point并非全部为0。
- 使用仓库 `cat.jpg` 生成 `[16,3,224,224]` 输入并以ONNX Runtime 1.27 CPU得到 `[16,1000]` 输出；第二次执行与保存输出bit-exact。模型、图片、输入和输出hash已写入 `contracts/model_baseline.json`，同时建立quantization/architecture candidate contract和ADR-001。
- 按操作者要求统一根集成层说明文档：将 `算子配置规则.md` 迁入 `.agents/rules/`，将ADR-001迁入 `.agents/decisions/`；requirements和contracts因分别属于环境清单和机器契约留在根目录。未发现可明确删除的过时说明文档。
- 迁移校验发现大型规则文档读取时曾受工具输出长度限制；已重建受影响的6.5～15.1中段并复核1～16章标题、UTF-8和截断标记，最终规则文档完整且较原版更紧凑。

## 2026-07-11：W0骨架完成并开始W2

- 操作者提供本地正式模型文件；大小和SHA-256与项目缓存的Model Zoo模型一致。出于后续GitHub发布隐私考虑，历史不记录含个人账号标识的本机绝对路径。
- 完成根集成层W0：建立 `resnet50_pipeline`、CLI、稳定Node/Tensor/HwOp/Layout/Config/Execution/Result记录、run manifest、contract/backend能力探测、artifact原子写入、阶段DAG、失败阻断、cache key、resume和旧schema拒绝/跳过规则。
- 建立 `pyproject.toml`、`repos.lock.json`、backend candidate contract、run manifest schema、mock fixture和operator coverage矩阵；根 `.gitignore` 排除虚拟环境、运行产物、生成目录及三个独立参考仓库，避免首版误生成gitlink或提交大文件。
- W0共11项单元测试通过；可安装CLI的probe、contract验证、完整mock run、resume复用、缺输入、能力不支持和backend失败路径均验证通过，G0判定通过。三个参考仓库未因W0发生新修改。
- 开始W2并完成独立QLinearConv软件golden：标量循环和im2col/einsum两条实现均覆盖UINT8 activation×INT8 weight、INT32 bias/psum、per-channel weight scale、非零zero-point、group/stride/padding/dilation、nearest-even和UINT8饱和，并输出bias初值、reduction tile psum、最终accumulator和requant结果。
- QLinearConv两条实现与ONNX Runtime在小型确定样例上逐元素bit-exact；连同W0当前共15项测试通过。下一步是小Conv物理partition/layout、地址provenance和正逆round-trip，再接入修复后的NDP功能模型。
- 操作者规定版本策略：现在建立根本地Git仓库并做首个提交；此后每个验证有效的小步骤做原子提交，W1/W2等大步骤完成后推送GitHub。任何删除、压缩或改写历史必须先询问确认。
- 根本地Git仓库已建立，首个提交为 `5bf423f`；首版排除了模型、虚拟环境、运行产物和三个参考仓库，提交后根工作树干净。
- W2小Conv候选物理布局已实现：严格复现NDP DRAM的slice/bank/row以及反向col/subword字节坐标，修正 `bytes_per_slice` 必须包含bank数；提供16-byte边界拆分、显式byte-stride transaction和稀疏physical image。
- 布局合同 `w2_ndp_ring_candidate_v1` 按NDP ring意图将activation沿C连续分片并存为NHWC，将weight/bias/qparams/output沿K连续分片，weight存为RSKC、output存为NHWK；C/K tail分别用zero-point填充，所有region对齐到16字节。
- 每个physical byte均记录tensor、逻辑坐标、element byte、data/tensor-padding/alignment语义和DRAM五维坐标；实现统一 `forward/inverse/explain_coordinate/validate`，1-slice与4-slice含C/K tail样例均bit-exact round-trip。
- 当前共20项测试通过。此步骤只完成raw↔physical和provenance，仍是candidate；NDP functional model尚未消费该image，G2尚未通过，16-slice扩展仍按计划留到G2之后。
- 在 `NDPFuncModel` 子仓库完成并提交 `789d121`：修复 `per_slice` 漏bank、`run_dram_to_ag` 未应用slice基址，以及RDAG/WRAG跨transaction物理地址丢失；逻辑counter与物理transaction offset现已分离。
- NDP侧新增4项寻址回归，覆盖4-slice独立DRAM写读、slice AG读取、跨16-byte边界的strided RDAG和WRAG对称顺序；全部通过。测试运行禁止写 `.pyc`，避免污染该仓错误跟踪的缓存文件。
- 根集成层新增显式 `NdpFunctionalAdapter`，通过独立子进程把同一W2 physical bundle载入NDP DRAM，并逐region读回校验SHA-256和slice坐标；根侧当前21项测试全部通过。
- 当前闭环边界推进为“raw↔physical↔NDP DRAM bit-exact”；尚未经过Buffer/PEA/reduction/requant/writeback，G2仍未通过。
- 在 `NDPFuncModel` 子仓库完成并提交 `deee41f`：INT8 PEA按uint8 activation A×int8 weight B执行，psum保持int32、乘加使用int64检查中间值；branch屏蔽lane先清零，越界暂显式报错，等待硬件溢出规则确认。
- NDP侧新增4项INT8 PEA回归，连同寻址测试共8项通过。根adapter新增physical-address dot probe：从4个activation slice和所属K slice读取字节，以折叠输入zero-point后的有效bias启动累加，单输出坐标accumulator与独立QLinearConv golden逐值相同；根侧21项测试通过。
- 当前闭环边界推进为“raw↔physical↔NDP DRAM↔单坐标整数PEA accumulator bit-exact”。尚未覆盖全部输出坐标、跨slice reduction结束、requant、INT8 packing和真实writeback，故G2仍未通过。
- 在 `NDPFuncModel` 子仓库完成并提交 `86cd3e3`：删除错误的 `r*s*cc_shared` reduction末态判定，统一使用LC `last/last_index`；同时把PEA psum清零从每个R迭代后移到完整C/S/R及ring reduction结束后，避免3×3/C累加被中途丢弃。
- NDP侧新增3项reduction调度回归，覆盖词典序末态、非零start/非单位step及非法状态，连同既有测试共11项通过。该提交修复控制与生命周期，但完整输出坐标尚未实际跑通，不能据此宣布G2通过。
