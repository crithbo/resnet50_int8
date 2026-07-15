# ResNet50 INT8 工作日志

最后更新：2026-07-15

本文件只保存已经发生的关键决策、验证、提交和状态变化，**不是接手入口，也不是当前任务清单**。除非需要定位历史问题、追溯旧结论、查完整提交/父提交或回退点，否则不要加载本文件；当前任务只读`.agents/plan.md`，代码地图按需读`.agents/agent.md`，单算子推导规则按需读`.agents/rules/算子配置规则.md`，W4专项追溯读`.agents/W4_ARCHIVE.md`。

> 当前口径提示（2026-07-14）：ADR-009已经完成DeepSeek公共物理基线继承，正式profile为`w4_deepseek_hybrid28_resnet50_v1`，G4 v2的12项条件全部为true，W4结束且W5已授权；同时`clean_elaboration_claimed=false`，尚无目标simulator、硬件或三方数值通过。本文旧条目中的16-slice方案、group/global二选一、“等待clean elaboration”“G4未通过”“下一步C8”等均是当时事实，不能作为当前任务。W4业务闭环为`952a96b...`，精确追溯见`.agents/W4_ARCHIVE.md`。

## Git提交、GitHub备份与本地空间规则（2026-07-13现行修正）

- Git采用三级规则：微小的错字、措辞、注释、空白或格式修正，只要不改变行为、接口、schema/合同、layout/qparams、依赖锁和产物hash，就不单独提交，可合并到下一次相关提交；范围明确且能聚焦验证的较小代码、测试、规则或文档语义改动做本地原子提交；阶段门、跨模块/跨仓重大集成、关键硬件合同、重要恢复检查点，或操作者明确要求时，才把相关本地提交批量推送GitHub并核对远端hash。
- 凡形成提交，`history.md` 必须记录仓库、完整40位commit、直接父commit、改动范围、验证结果和精确回退位置；微小未提交改动在任务报告中说明。短hash只用于正文易读，不能替代本节台账。
- 回退默认使用 `git revert <commit>` 生成保留历史的新提交；不得自行使用reset、rebase、filter、强推或删除提交。任何改写历史仍须操作者单独确认。
- 操作者最终澄清：真正需要永久保留的是提交，不是仓库目录副本。项目应尽量只保留一份必要工作树，不为备份目的额外创建clone、worktree、zip或目录复制；云端恢复以GitHub已推送提交为主。
- 主仓和发生较小或重大修改的子仓先做本地原子提交并在history登记；微小改动不要求独立提交。只有达到重大改动/里程碑门槛或操作者明确要求时，才批量推送到操作者控制的GitHub仓库或fork并核对远端hash。不得把未推送的本地提交或对上游仓库可能无权限的 `origin` 当成已经完成云端备份。
- 冗余本地副本只有在其中没有唯一未提交内容、所有需保留提交已经推送并核对远端hash、且操作者批准具体路径后才能删除。删除副本不等于删除提交；不得通过reset/rebase/filter/强推或裁剪历史来节省空间。
- `.venv`、模型、golden、trace和运行artifact不是仓库副本，也不会由普通GitHub提交自动备份；它们按可重建性和大文件策略另行管理，不能混入普通Git历史。
- Git commit hash由提交内容决定，提交无法在自身文件内容中稳定写入自己的hash。因此业务/代码提交在同一次或紧随其后的history同步提交中登记；最新一笔“只更新台账”的提交以当前 `HEAD` 和 `git log -1 --format=fuller` 精确定位，并在下一次台账同步时补入。不得借此漏记任何业务提交。

## W0～W3交接封版（2026-07-12）

本节是新对话判断“哪些已经完成、哪些不得误判”的首要历史快照；后面的精确提交台账和逐日记录保留证据细节。封版前根仓本地与Private `origin/main`均为`35a4fde106d102b0e165e7eb13d60f7dd980db71`，ahead/behind为0/0，三个参考仓由`repos.lock.json`锁定并通过verify。

| 工作包 | 结论 | 已完成内容 | 未批准边界 |
|---|---|---|---|
| W0/G0 | 通过 | 根集成包、CLI、稳定manifest对象、contracts/backend能力、artifact原子发布、阶段DAG、失败阻断、cache/resume、schema和mock测试 | 只证明框架和mock生命周期，不证明真实算子/hardware |
| W1/G1 | 部分完成，G1未通过 | 正式候选ONNX、固定图片与batch16输入、旧脚本预处理、ORT环境、模型/输入/输出hash、UINT8×INT8×INT32量化事实 | 正式16-slice layout、RTL/ISA、SA/GA/qparams、目标emulator和硬件协议仍为candidate/unknown |
| W2/G2 | 通过 | 小Conv 1/4-slice候选物理layout、地址/provenance、正逆round-trip、DRAM/Buffer/PEA/ring/requant/writeback功能链；NumPy、im2col、ORT、CGRA QNN与NDP全部84坐标一致 | 不是正式16-slice layout，不消费目标JSON/bitstream，不是硬件通过 |
| W3/G3 | 通过 | 78节点/617 tensor正式图，133语义hw_op，79运行时tensor，55个INT32内部tensor，全部78节点独立公式重放，旧77原语稳定映射 | 未生成正式逐K-tile快照、layout、JSON、execplan、target simulator或hardware结果 |

### W0封版证据

- G0最初以11项W0单测通过；后续功能加入后，封版全量根测试为42项且继续覆盖W0的成功、失败、resume、cache失效、schema和引用完整性。
- 根仓边界明确：集成源码、测试、schema、合同和小fixture入Git；ONNX、`.venv`、golden/trace/hardware dump和普通artifact不入普通Git。
- 三参考仓保持独立工作树；`repos.lock.json`和`tools/sync_repositories.py`提供只读verify及显式恢复路径。

### W1已完成与未完成

- 模型位于`artifacts/reference_model/resnet50-v1-12-int8.onnx`，SHA-256 `c234f30975989788b4405f25253275aae247ab6dbdd34aaa69ab0a59ff76f6d0`；IR 4、opset 12、78节点、366 initializer。
- 预处理暂定复现旧脚本：RGB、除255、直接缩放256×256、中心裁剪224×224、ImageNet mean/std、HWC→CHW、float32、复制batch=16。输入SHA-256为`6661a1671a07256fa7b4792851bc8bee41409495a7b5b705fbb3fe0976601a9c`，最终输出SHA-256为`2c6c5fabc1d41fceee35f06221efb4c64b94fabfe7a0b4680d2acf2186ca0894`。
- 53层Conv均确认是UINT8 activation、INT8 weight、INT32 bias、per-output-channel weight scale；weight zero point为0，输入/输出zero point不保证为0。
- G1没有通过。后续取得正式layout/RTL/ISA/量化常量/runner资料时必须更新对应contract，而不能把W2 candidate当作硬件批准结论。

### W2封版证据

- `w2_ndp_ring_candidate_v1`实现activation沿C、weight/output沿K分片，RSKC/NHWK物理顺序、bias/qparams、C/K tail、16-byte对齐、DRAM slice/bank/row/col/subword坐标和逐字节data/padding/alignment provenance。
- 1-slice和4-slice均完成raw→physical→raw bit-exact；参数化NDP runner实际经过DRAM→input Buffer→SpecialPEA→ActivationUnit→output Buffer→DRAM。
- 带padding及C/K tail的小Conv共84个输出坐标，其INT32 accumulator、physical UINT8 D和inverse logical D逐项匹配独立golden；G2通过时根28项、NDP14项回归通过。
- NDP修复封版为`35eab40e5314bf603481dd6268bc96ab2ca514a6`并已推送Private镜像。该结论只批准候选软件闭环，不批准目标JSON、bitstream、16-slice硬件layout或真实hardware。

### W3封版证据

- 模型解析通过SHA/checker、ONNX shape inference和受控补充传播，得到78节点/617 tensor；366 initializer均有内容hash，所有node output dtype/shape已知。
- 8类插件把78节点lower为133个语义hw_op和55个内部tensor。`artifacts/w3/golden_batch16`保存1个图输入+78个node output并引用366个initializer；运行manifest SHA-256为`f7e90cf1f087acf255e93d98d1788e0fb0b4c77bbe935ea9addb17feea583180`。
- `artifacts/w3/subop_batch16`中的55个内部INT32 tensor为53个Conv accumulator、1个GlobalAveragePool centered sum和1个MatMul accumulator；subop manifest SHA-256为`8bfdd042570408c1df793044407a8e6262bfa261b3cc6f02f64b94ad47d9c1c2`，目录大小677,828,490字节。
- 全部78节点独立公式重放匹配ORT：55个内部累加/求和后requant、17个QLinearAdd、2个Quantize、2个Dequantize、1个MaxPool、1个Flatten。第二次运行79个runtime tensor和55个内部tensor的文件hash分别全部一致。
- 旧计划索引0..76的77个模型级原语全部映射到当前稳定node/hw_op；Flatten作为zero-copy明确排除。映射SHA-256为`b6507dec2b564a0b5a06b185a4ce5070909194d5cf164edc503d840740b94ed3`。

### 新旧对话分工与返工规则

- 新对话读取`agent.md`后从W4开始推进；本对话保留用于W1～W3查验、复现、审计和返工，除非操作者明确更改分工。
- W1～W3返工前先确定是否改变模型hash、预处理、ORT设置、量化公式、稳定ID或lowering。任何一项改变都必须列出失效的runtime/subop manifest、artifact、W2 fixture和后续依赖，不能静默覆盖。
- 正常接手只需运行`git status --short`、`.venv\Scripts\python.exe tools\sync_repositories.py verify`和`.venv\Scripts\python.exe -m unittest discover -s tests -v`。约951 MB的W3正式artifact不应无理由重复生成；先按合同检查路径、大小和manifest hash。

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
13. `7216691f038bf4a71569daab90973d239f26df24`，父提交 `4b7d7e1b4475c0763c936abc80489ab676711a86`，`docs: record verified GitHub backups`。
    - 范围：把主仓/NDP push成功、tracking关系和GitHub完整commit页面核验结果写回agent/history/plan。
    - 验证：GitHub登录页面可访问主仓完整commit `4b7d7e1…` 和NDP完整commit `86cd3e3…`；本commit随后成功推送到 `origin/main`。
    - 精确回退：revert本commit；改动前根状态为 `4b7d7e1…`。revert只改变状态记录，不删除远端提交或tracking配置。
14. `6a729fe6d578c763b7e6f524e7d278abbbbf3fd7`，父提交 `7216691f038bf4a71569daab90973d239f26df24`，`chore: sync verified backup ledger`。
    - 范围：登记 `7216691…` 的完整hash、父提交、GitHub核验和回退位置。
    - 验证：提交成功推送到 `origin/main`；GitHub登录页面可访问完整commit `6a729fe…`；本地HEAD与tracking ref一致且ahead/behind为0/0。
    - 精确回退：revert本commit；改动前根状态为 `7216691…`，只影响台账内容。
15. `d98d91f7ae61e82f885def7239cde593410a5477`，父提交 `6a729fe6d578c763b7e6f524e7d278abbbbf3fd7`，`feat: add reproducible reference repository sync`。
    - 范围：升级`repos.lock.json`到0.2，加入三仓upstream/private mirror/branch/commit；新增lock schema、安全的verify/sync工具、6项恢复测试并同步agent/history/plan。
    - 验证：根仓27项测试全部通过；三仓实际verify通过；lock/schema JSON解析和`git diff --check`通过；CGRA、ndp-sim-ref、NDP工作树均干净且HEAD/remote与lock一致。
    - 精确回退：revert本commit；改动前根状态为 `6a729fe…`。revert会恢复旧lock并删除恢复工具/schema/测试，但不会删除三个本地仓或修改其Git配置。
16. `f4f71f1c8c6c109382d4127a24994dcfa9324279`，父提交 `d98d91f7ae61e82f885def7239cde593410a5477`，`chore: sync repository recovery ledger`。
    - 范围：把仓库恢复工具业务提交 `d98d91f…` 的完整hash、父提交、验证和回退位置补入精确台账。
    - 验证：提交已推送到 `origin/main`；本地HEAD与远端一致，仓库恢复工具对三仓verify通过。
    - 精确回退：revert本commit；改动前根状态为 `d98d91f…`，只影响台账登记。
17. `758a7c5b5eed8415a184380f2fab227ecea58dfa`，父提交 `f4f71f1c8c6c109382d4127a24994dcfa9324279`，`feat: validate all Conv ring accumulators`。
    - 范围：根adapter从physical provenance构造全部QLinearConv输出坐标的4-slice ring probe，处理padding/空段/奇数lane、activation zero point折叠和分段partial sum；新增全坐标差分测试，锁定NDP `d212225…`，同步W2状态及新的“小进度只做本地提交”规则，并禁止adapter子进程重写NDP `.pyc`。
    - 验证：带3×3/padding/C-K tail的84个int32 accumulator与独立QLinearConv golden逐元素相同；根仓28项、NDP 11项测试通过；三参考仓verify和`git diff --check`通过，测试后NDP工作树保持干净。
    - 精确回退：revert本commit；根仓回到 `f4f71f…` 的单坐标probe状态，配套NDP `d212225…` 可继续保留但不会被旧lock引用。本commit按新规则仅保留本地，尚未推送 `origin/main`。
18. `c21a5346616bde3e2ed6cda0713c6c252a9d2a07`，父提交 `758a7c5b5eed8415a184380f2fab227ecea58dfa`，`chore: sync Conv accumulator ledger`。
    - 范围：把全坐标ring accumulator业务提交 `758a7c5…` 的完整hash、验证和精确回退点补入台账。
    - 验证：提交后根工作树干净，三参考仓verify通过；按小进度策略仅本地提交。
    - 精确回退：revert本commit；改动前根状态为 `758a7c5…`，只影响台账登记。
19. `56ccf5e2cdcecb80918b12bed74363daaca26d21`，父提交 `c21a5346616bde3e2ed6cda0713c6c252a9d2a07`，`feat: close candidate Conv output writeback`。
    - 范围：根adapter从physical x/w/y qparams推导per-channel候选multiplier，将84个probe输出绑定D provenance地址；验证NDP ActivationUnit requant及真实DRAM字节覆盖，并把返回写回根物理镜像后执行既有inverse layout。新增安全overwrite API及provenance保持测试，锁定NDP `3cb0ef9…`，同步quantization contract和W2文档边界。
    - 验证：根仓28项、NDP 14项测试全部通过；84个int32 accumulator、physical UINT8 D和inverse logical D均与独立QLinearConv golden逐元素一致；三仓verify、JSON解析和`git diff --check`通过。
    - 精确回退：revert本commit；根仓回到 `c21a534…` 的全坐标accumulator状态，配套NDP `7a47701…`/`3cb0ef9…`可保留但不会被旧lock引用。本commit仅本地、未推送。
20. `b1126f4a9fd013bcea9d58f8da3443fa41e6cecb`，父提交 `5d7f1a348f8af9a8402dfb5931bd753ebd6ed93a`，`feat: validate buffered Conv functional path`。
    - 范围：根adapter强制验证NDP执行路径包含input/output Buffer、SpecialPEA、ActivationUnit和DRAM，并检查每坐标ring LC末态；锁定NDP `35eab40…`。
    - 验证：4-slice 84坐标聚焦及根28/NDP14项回归通过。
    - 精确回退：revert本commit；回到 `5d7f1a3…` 的直接PE probe验证。本commit仅本地、未推送。
21. `d77a076ff62f48dc1e8aaf687d82834091e481ef`，父提交 `b1126f4a9fd013bcea9d58f8da3443fa41e6cecb`，`test: approve W2 small Conv G2 gate`。
    - 范围：把完整runner测试参数化为同fixture 1/4-slice；直接执行CGRA QNN rounding；逐字节审核全部region provenance；将G2通过写入plan、backend/quantization contract和coverage matrix。
    - 验证：根28项、NDP14项回归通过；1/4-slice各84个accumulator、physical/logical D一致；聚焦测试连续执行两次结果一致；三仓verify、JSON和diff检查通过。
    - 精确回退：revert本commit；回到 `b1126f4…` 的4-slice buffered runner状态，G2恢复未通过。本提交为W2/G2里程碑。
22. `5f25526b731bd19a5f29276b6f726d29240154c3`，父提交 `e01adc0c1ef71e431f223358348f428ddac11e17`，`docs: record W2 G2 GitHub milestone`。
    - 范围：记录W2/G2根仓与NDP里程碑推送完成状态。
    - 验证：主仓与NDP tracking均为0/0，三仓verify通过；该提交已推送Private `origin/main`。
    - 精确回退：revert本commit只撤销云端状态记录，不删除远端提交。
23. `4f2828b1a2c2a57aadc85f8a686742f4831055c2`，父提交 `5f25526b731bd19a5f29276b6f726d29240154c3`，`feat: catalog formal ONNX graph`。
    - 范围：新增W3 ONNX目录模块和CLI，校验正式模型hash/checker，执行标准及补充shape推断，生成稳定node/tensor ID、initializer hash、原名、属性和producer/consumer关系。
    - 验证：78节点、617张量、366 initializer；185个ONNX inference、66个supplemental shape，未知shape/dtype为0；重复解析canonical JSON一致；根32项测试通过。
    - 精确回退：revert本commit；回到 `5f25526…` 时不存在正式图目录。本提交仅本地、未推送。
24. `060d3c84c7c68845c782c12e21bd00ae328be8be`，父提交 `4f2828b1a2c2a57aadc85f8a686742f4831055c2`，`feat: lower formal ResNet graph to semantic hw ops`。
    - 范围：建立8类lowering插件；Conv/GAP/MatMul拆成两阶段，其他算子单阶段；生成稳定hw_op ID、显式内部tensor和拓扑依赖。
    - 验证：78节点全部映射为133个hw_op、55个内部tensor；任一node可查hw_op且末阶段回写原ONNX tensor；根35项测试通过。
    - 精确回退：revert本commit；保留 `4f2828b…` 图目录但移除lowering。本提交仅本地、未推送。
25. `42b65198231928ec5d49309718c3f21032ea5db3`，父提交 `060d3c84c7c68845c782c12e21bd00ae328be8be`，`docs: record W3 graph and lowering progress`。
    - 范围：同步W3图目录/lowering状态及提交台账。
    - 验证：文档diff检查通过。
    - 精确回退：revert本commit只撤销状态记录。
26. `80b95fe3be5e5f1fd3cdfc06f8f7bdcb3e4b5e09`，父提交 `42b65198231928ec5d49309718c3f21032ea5db3`，`feat: dump all ONNX node outputs reproducibly`。
    - 范围：新增固定ORT选项的全node output runner、原子artifact发布、initializer hash引用、node input/output manifest及CLI。
    - 验证：正式batch16保存79个运行时tensor/366 initializer引用，最终输出hash与W1相同，临时目录第二次运行全部79个hash一致；根36项测试通过。
    - 精确回退：revert本commit；保留图目录/lowering但删除运行时golden runner。
27. `d88ea2fba78225a8f1e04cc23360bb2efa7cc674`，父提交 `80b95fe3be5e5f1fd3cdfc06f8f7bdcb3e4b5e09`，`docs: record formal all-node golden baseline`。
    - 范围：批准正式全节点ORT运行合同，记录模型/input、79个运行时tensor、366个initializer引用、最终输出和manifest hash，并同步W3状态文档。
    - 验证：合同JSON可解析；正式manifest SHA-256为`f7e90cf1f087acf255e93d98d1788e0fb0b4c77bbe935ea9addb17feea583180`，最终输出文件SHA-256为`2c6c5fabc1d41fceee35f06221efb4c64b94fabfe7a0b4680d2acf2186ca0894`。
    - 精确回退：revert本commit只撤销运行合同和对应状态记录；`80b95fe…`的runner代码与被Git忽略的可再生产物仍保留。本提交仅本地、未单独推送。
28. `096efc347bec1932102103b0cec5092bb7684d13`，父提交 `d88ea2fba78225a8f1e04cc23360bb2efa7cc674`，`feat: generate ResNet subop golden tensors`。
    - 范围：新增Conv/MatMul INT32 accumulator、GlobalAveragePool centered INT32 sum及其requant参考实现和CLI；建立旧77原语稳定映射，明确排除zero-copy Flatten。
    - 验证：正式batch16生成55个内部tensor（53 Conv、1 GAP、1 MatMul），每个对应requant输出均匹配ORT；第二次临时运行55个文件hash全部一致；旧索引0..76共77项无缺失映射；相关单测及根仓回归通过。
    - 精确回退：revert本commit；保留ORT全节点golden，但删除subop生成器、旧77映射器和相关测试。被Git忽略的`artifacts/w3/subop_batch16`需手动再生或清理，不属于Git回退范围。本提交仅本地、未单独推送。
29. `c5de5e66c24e252be19d911b05ab37acbc75cb84`，父提交 `096efc347bec1932102103b0cec5092bb7684d13`，`test: replay every ResNet node formula`。
    - 范围：把独立公式重放扩展到全部78节点，覆盖17个QLinearAdd affine requant、2个Quantize nearest-even、2个Dequantize、1个MaxPool和1个Flatten，并保留55个多阶段内部结果验证。
    - 验证：全部78个节点输出逐项等于ORT；公式分类计数55+17+2+2+1+1=78；正式subop manifest SHA-256为`8bfdd042570408c1df793044407a8e6262bfa261b3cc6f02f64b94ad47d9c1c2`；根仓42项测试通过。
    - 精确回退：revert本commit；回到`096efc3…`时仍有55个内部tensor及其requant验证，但不再宣称其余23个单阶段节点已独立重放。本提交仅本地、未单独推送。
30. `aa6ee26e78e90f9c5b68f8a62899d40663abfd76`，父提交 `c5de5e66c24e252be19d911b05ab37acbc75cb84`，`docs: approve W3 G3 golden milestone`。
    - 范围：新增机器可读`subop_golden`合同；把7类真实算子的raw/subop覆盖标记为`w3_g3`；同步agent/plan/history并正式批准G3。
    - 验证：根仓42项测试、三参考仓verify、合同JSON解析、Git diff检查通过；subop manifest和旧77映射的实际SHA及677,828,490字节目录大小均与合同一致。
    - 精确回退：revert本commit；代码仍停在`c5de5e6…`且计算结果不变，但G3批准合同、覆盖状态与里程碑文档被撤销。本提交将在本次W3批量推送中进入Private `origin/main`。
31. `35a4fde106d102b0e165e7eb13d60f7dd980db71`，父提交 `aa6ee26e78e90f9c5b68f8a62899d40663abfd76`，`chore: sync W3 G3 milestone ledger`。
    - 范围：登记W3/G3批准提交`aa6ee26…`的完整hash、父提交、验证和回退边界，形成W3云端封版HEAD。
    - 验证：从`5f25526…`到本提交的9个W3提交已批量推送Private `origin/main`；本地HEAD与tracking ref均为本提交，ahead/behind为0/0，工作树干净。
    - 精确回退：revert本commit只撤销`aa6ee26…`的台账登记，不撤销W3代码、合同或云端提交；W3业务回退应按第23～30项从后向前逐项revert。
32. `e3142bf0d5b03d891c13a4670e83d10b0862c1fc`，父提交 `35a4fde106d102b0e165e7eb13d60f7dd980db71`，`docs: seal W0-W3 handoff`。
    - 范围：新增W0～W3交接封版总账；把`agent.md`重构为新对话接手控制台；把`plan.md`中W2/W3开始前的过时状态替换为当前门状态，并明确新对话推进W4、本对话返工/查验W1～W3。
    - 验证：根仓42项测试、三参考仓verify、`git diff --check`通过；W3 runtime/subop/旧77映射三个artifact的实际SHA-256均与封版记录一致。
    - 精确回退：revert本commit；恢复`35a4fde…`时W0～W3业务代码和合同不变，只撤销本次交接重构与过时状态修订。

## 2026-07-12：W3正式图目录与语义lowering启动

- 旧golden脚本的硬编码输出名、伪四维ValueInfo和个人绝对路径不再作为W3接口；正式解析从model contract的SHA开始。
- ONNX标准shape inference在首个QLinearAdd后停止传播，新增仅覆盖当前8类已知算子的补充规则，并为每个tensor记录`initializer/onnx_inference/supplemental`来源，禁止静默猜shape。
- 核心解析层不导入`cgra_python`，因此不受`layout_buffer.py:201`语法错误和顶层`import *`影响；该子仓错误仍需单独修复，不能宣称源码已正确。
- 正式batch16已运行全部78个node output，落盘约273.56 MB且由Git忽略；最终输出`.npy` hash为`2c6c5f…`，与W1基线文件完全相同。第二次运行使用临时目录，79个tensor文件hash全部一致并自动删除临时副本。

## 2026-07-12：W3/G3全图subop golden通过

- 正式batch16已生成55个lowering内部INT32 tensor：53个QLinearConv accumulator、1个QLinearGlobalAveragePool centered sum、1个QLinearMatMul accumulator；逻辑数据量677,771,776字节，包含manifest的artifact目录占677,828,490字节，均由Git忽略且可由正式模型/input重建。
- 每个多阶段算子的内部结果均经过独立requant公式恢复为对应ORT node output；另外对QuantizeLinear、QLinearAdd、MaxPool、DequantizeLinear和Flatten独立重放，最终全部78个ONNX节点逐项匹配ORT。
- 旧脚本的77个模型级原语已按原索引0..76逐项对应当前稳定node ID、旧generator名称和1或2个语义hw_op ID；当前图多出的Flatten明确标记为zero-copy而不是遗漏。映射artifact为`artifacts/w3/legacy77_mapping.json`，SHA-256为`b6507dec2b564a0b5a06b185a4ce5070909194d5cf164edc503d840740b94ed3`。
- G3据此通过。这里批准的是模型语义、lowering边界和软件golden；尚未批准16-slice物理layout、逐K-tile psum快照、目标JSON/bitstream或硬件数值链。完整reduction的INT32边界将在W4/W5取得tile/layout合同后细化为首/中/末K tile。

### 子仓库 `NDPFuncModel/conv_func`

上游共同基线为 `89d1655ce6450477cdcc04965d8b4866f12066e5`。以下提交均不在公开 `origin/conv_func`；第1～7项已随W2/G2里程碑批量推送操作者Private镜像，最终封版为`35eab40e5314bf603481dd6268bc96ab2ca514a6`。各条中“仅本地、未推送”描述的是提交当时状态，已由本句和后续G2记录取代：

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
4. `d212225bb466bb1d46a6b5c9ba528e5d6c28e34d`，父提交 `86cd3e328b45c37a1c8a133c650eb1f756b0c233`，`feat: expose segmented INT8 dot reductions`。
   - 范围：physical image probe接收branch mask与ring segment边界，把logical output coordinate、各段partial accumulator和最终accumulator返回根adapter。
   - 验证：NDP 11项测试通过；根集成测试进一步以84个实际输出坐标验证4段ring结果。提交已成功推送到Private `conv_func`。
   - 精确回退：revert本commit；上一NDP状态为 `86cd3e3…`，仍保留寻址、整数PEA及LC reduction控制，但根adapter的分段probe将不兼容。
5. `7a4770178eb7788dad5211102bd3a2f17591d753`，父提交 `d212225bb466bb1d46a6b5c9ba528e5d6c28e34d`，`fix: implement candidate INT8 requantization`。
   - 范围：修复ActivationUnit缺失round函数和标量维度错误；新增int32输入检查、scalar/per-channel float32 multiplier、nearest-even、output zero-point及uint8 saturation。
   - 验证：新增3项requant测试，覆盖tie、负值、饱和、NCHW逐通道广播和非法dtype；NDP累计14项测试通过。
   - 精确回退：revert本commit；回到 `d212225…` 时仅保留整数accumulator，ActivationUnit requant不可用。本commit仅本地、未推送。
6. `3cb0ef91c1bd7117ebda5004519f22ff227a22e5`，父提交 `7a4770178eb7788dad5211102bd3a2f17591d753`，`feat: requantize and write probe outputs`。
   - 范围：physical probe接收D物理地址、per-channel multiplier和output zero-point；对最终int32 accumulator调用ActivationUnit，真实写入NDP DRAM并立即读回before/after。
   - 验证：根聚焦测试覆盖84个输出地址，physical和inverse logical UINT8 D均与golden一致；配套NDP 14项测试通过。
   - 精确回退：revert本commit；保留 `7a47701…` 的候选requant单元，但probe不再执行物理D写回。本commit仅本地、未推送。
7. `35eab40e5314bf603481dd6268bc96ab2ca514a6`，父提交 `3cb0ef91c1bd7117ebda5004519f22ff227a22e5`，`feat: route Conv probes through functional buffers`。
   - 范围：单算子runner不再直接调用PE；每个dot实际经过input Buffer、SpecialPEA，ring分段记录LC last/last_index，requant结果经过output Buffer再写DRAM。
   - 验证：84坐标聚焦测试通过，执行路径和4步ring末态均由根adapter强校验。
   - 精确回退：revert本commit；回到 `3cb0ef9…` 的直接PE probe。本commit仅本地、未推送。

## 当前本地副本与空间审计（2026-07-11）

- 父目录中只有当前主仓 `resnet50_int8`，没有第二份主仓clone、额外worktree或项目zip/bundle备份；主仓 `.git` 约0.64 MiB。
- 主仓内有三个必要的独立参考仓工作树：`CGRA_SIM`约347.14 MiB、`ndp-sim-ref`约390.35 MiB、`NDPFuncModel`约266.95 MiB。它们不是主仓Git历史中的重复内容，而是各自独立仓库。
- 操作者批准后，冗余linked worktree `artifacts/smoke/NDPFuncModel` 已通过 `git worktree remove --force` 删除并执行 `git worktree prune`，释放约130.68 MiB。删除前确认其没有独有提交或源码改动，仅有运行生成的跟踪 `.pyc` 变化；删除后NDP worktree列表只剩 `NDPFuncModel@86cd3e3`，主NDP工作树干净，artifact总量降至约33.90 MiB。
- `.venv`约917.41 MiB，是共享依赖环境而非仓库副本；`artifacts/reference_model`约33.87 MiB，是ONNX/输入/输出基线而非仓库副本。三份W0小artifact合计不足0.03 MiB。
- `CGRA_SIM/.git`另报告约113.98 MiB临时pack垃圾；这不是有效提交副本，可在确认仓库状态后用Git维护方式清理，但本轮未删除。
- GitHub owner确认为 `crithbo`；后续提交作者名配置为 `crithbo`，提交邮箱使用操作者确认的Gmail。身份写入四个仓库的repository-local Git配置，不改写任何既有commit，也不在项目文档重复保存私人邮箱明文。
- 已创建并由GitHub页面确认两个空Private仓库：主仓 `https://github.com/crithbo/resnet50_int8.git`，NDP独立私有镜像 `https://github.com/crithbo/NDPFuncModel-private.git`；均未初始化README、LICENSE或`.gitignore`。
- 主仓 `main` 已推送到Private `origin/main`，NDP `conv_func` 已推送到Private `private/conv_func`；两次push均成功并建立tracking。已在登录后的GitHub提交页独立确认主仓 `4b7d7e1b4475c0763c936abc80489ab676711a86` 和NDP `86cd3e328b45c37a1c8a133c650eb1f756b0c233` 可访问，云端备份状态为完成。
- 在该次空间审计时，`CGRA_SIM`仍显示4个未提交项且没有remote；此状态后来已在2026-07-12复审为纯Windows权限位噪声并解决，不能再作为当前阻塞。
- NDP的3个独有提交不能跟随主仓一起推送，因此为其建立了独立Private镜像；干净的 `ndp-sim-ref` 和复审后干净的CGRA均可通过固定upstream hash恢复。

## 2026-07-12：主仓可定位并自动恢复三个参考仓

- 复审CGRA的4个所谓修改，确认全部仅为Windows权限位将4个文件显示为`755→644`，内容0行变化；设置该仓repository-local `core.filemode=false` 后工作树干净，并补回 `https://github.com/KingICCrab/CGRA_SIM.git` 为 `origin`。没有业务修改，因此不建立无意义Private镜像。
- `repos.lock.json` 升级到0.2：CGRA、ndp-sim-ref、NDPFuncModel均记录upstream、可选private mirror、branch、完整commit和dirty状态；NDP明确指向 `crithbo/NDPFuncModel-private`。
- 新增 `schemas/repositories_lock.schema.json` 和 `tools/sync_repositories.py`。`verify`只读核验HEAD、dirty paths和remote URL；`sync`对缺失仓使用partial clone并检出固定commit，优先Private镜像，拒绝路径越界、非Git目录和既有脏工作树。
- 新增6项仓库恢复测试，覆盖lock/schema一致性、版本/路径越界、HEAD/dirty/remote验证、缺失仓固定commit恢复、Private镜像优先和脏仓拒绝；当前三个实际仓库均通过verify。
- 根仓完整回归由21项增至27项并全部通过；lock与schema JSON解析、`git diff --check`及三仓clean/remote/HEAD复核均通过。

## 2026-07-12：W2全输出坐标ring accumulator闭环

- NDP `d212225…` 为physical-address probe加入branch mask、ring segment边界、逻辑输出坐标和分段partial sum回传，并已推送Private镜像。
- 根adapter不从raw数组旁路取值：它通过provenance取得activation/weight/bias/qparams物理地址，按输出K-owner开始的4-slice ring顺序组织reduction；越界padding不伪造逻辑坐标，空段和奇数lane统一用branch mask补齐PE dot size。
- 确定性小Conv覆盖非零activation zero point、3×3 kernel、padding、C/K tail和7个输出通道，共84个输出坐标；每坐标回传4个partial sum，最终int32 accumulator与独立QLinearConv golden逐元素bit-exact。
- 根仓28项、NDP 11项测试全部通过。当前闭环边界是raw↔physical↔NDP DRAM↔全部坐标4-slice ring整数accumulator；probe仍未执行主入口完整LC/Buffer调度，requant、INT8 packing、真实D writeback和inverse D未完成，因此G2仍未通过。
- 后续本地提交 `7a47701…` 修复ActivationUnit候选requant，`3cb0ef9…` 让probe对每个输出坐标真实覆盖D物理字节。根镜像用新增overwrite保留原provenance，再由既有inverse layout恢复logical D；84个physical/logical UINT8 D与golden一致。
- 该进展只关闭probe候选路径：主入口仍未调用ActivationUnit，SpecialPEA仍按FP16打包，`run_buffer_writeback_to_dram()`的实际stream write仍被注释，JSON/LC/Buffer/WRAG唯一flush尚未验证；因此G2继续保持未通过。

## 2026-07-12：W2/G2正式通过

- 同一确定性小Conv新增1-slice执行，并与4-slice共用同一physical runner；两者全部84个accumulator、physical D、inverse logical D一致。
- runner路径为DRAM→input Buffer→SpecialPEA→ActivationUnit→output Buffer→DRAM；ring LC在1-slice为`[1]`、4-slice为`[0,0,0,1]`，每坐标仅最终ring状态结束。
- 直接加载CGRA `qnn_round.py`执行同一accumulator/multiplier/zp，输出与标量NumPy、im2col、ORT及NDP一致；每个region全部物理字节均可反查正确slice及data/tensor-padding/alignment语义。
- 根28项、NDP14项回归通过，故按原G2门槛判定W2/G2通过。此批准仅限小Conv软件候选合同；目标JSON/bitstream、正式layout、旧固定主入口和硬件三方一致仍未批准。
- W2/G2作为大步骤里程碑已云端备份：NDP `35eab40e5314bf603481dd6268bc96ab2ca514a6` 推送到Private `conv_func`，根台账 `e01adc0…` 推送到Private `origin/main`；两仓tracking均应保持0/0，后续由仓库verify持续核验。

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

## 2026-07-12：W4简单算子16-slice candidate relayout

- 根仓提交 `c375c368f861b0e374f3ee61f90fb2beaf1eff28`，父提交 `b695dcaa18633dea2b553f8060c8c5823a855986`，`feat: add W4 simple-op relayouts`。
- 范围：新增`w4_batch_slice_candidate_v1`，为QuantizeLinear/DequantizeLinear的A、scale、zero_point和D实现16-slice `forward/inverse/explain_coordinate/validate`；batch按一项一slice，标量qparams逐slice复制，端口C-order/little-endian并按16 byte对齐。布局使用紧凑per-region payload和可计算坐标映射，避免为正式`[16,3,224,224]`逐字节建立高内存provenance字典。
- 新增`w4_zero_copy_view_candidate_v1`：仅在axis=1、元素数不变、batch partition和C-order字节序兼容时，证明正式Flatten `[16,2048,1,1]→[16,2048]`共用producer D的16个base address；非法axis/shape提前失败。
- `LayoutRecord`扩展端口、logical shape/dtype、partition、packing、base address、inverse状态和alias字段；新记录可经`ObjectManifest.to_dict/from_dict`无损往返。候选合同已登记到`contracts/architecture.json`，未升级为硬件approved。
- 验证：新增4项测试，覆盖最小shape、N<16的inactive slice、正式Quantize输入`[16,3,224,224]`、Dequantize dense 1000类tail、正式Flatten、逐元素地址解释、manifest往返、padding破坏和非法View；根仓全量46项测试通过，`contracts/architecture.json`严格JSON解析和`git diff --check`通过。
- 边界：本提交没有读取或重跑约951 MB的W3 tensor产物，只消费已有`artifacts/w3/model_graph.json`的小型图目录确认正式shape。Conv、MaxPool、QLinearAdd、GlobalAveragePool、MatMul/dense尚未进入W4实现，目标硬件layout仍缺approved合同，故G4保持未通过。
- 精确回退：revert `c375c368f861b0e374f3ee61f90fb2beaf1eff28`；上一根仓恢复点为`b695dcaa18633dea2b553f8060c8c5823a855986`。

## 2026-07-12：W4 batch-parallel Conv0 candidate relayout

- 根仓提交 `299290de9de07a442fcb6be4779880e3cf08c63b`，父提交 `ccaf43b8230edcfcf78109676998cc48f614af3f`，`feat: add W4 batch16 Conv relayout`。
- 范围：新增`w4_conv_batch16_candidate_v1`，明确一张batch样本归属一个slice；A从NCHW显式重排为HWC并按C=8补`x_zero_point`，im2col不物化而由AG窗口坐标解释；B从OIHW重排为逐slice复制的RSKC并按C/K=8补tail；bias、weight qparams、x/y qparams和effective multiplier逐slice复制；int32 P及uint8 D按HWK存放并补K tail。全部12类对象提供forward、inverse、coordinate/window explain、validate和LayoutRecord。
- 实现隔离在`resnet50_pipeline/conv16_layout.py`，未修改W2 `SmallConvPhysicalLayout`的C/K ring语义；因此batch-parallel与ring-parallel不会再由同一个隐式`slice_count`混用。
- 正式Conv0定向验证工具`tools/verify_w4_conv0_layout.py`只读取已有W3 activation、ONNX initializer、int32 accumulator和D，不执行ORT或重建W3。报告`artifacts/w4/conv0_batch16_report.json`为6,281 bytes，SHA-256 `c91ae0ddbc17b41121d832a16d4a3de3706a9eaccfc59faf834de45b9e6f23b5`；12类逻辑对象inverse均bit-exact，physical逻辑总量71,063,552 bytes，每slice使用4,441,472/25,165,824 bytes。
- 验证：新增3项聚焦测试，覆盖N<16、C/K tail、per-channel qparams、AG padding/data窗口、logical/physical坐标、Conv0正式shape规划及单slice等价round-trip、tail破坏、非法group和错误output shape；根仓全量49项测试通过，architecture合同严格JSON解析、Python编译和`git diff --check`通过。
- 边界：该profile是软件candidate，不声明目标硬件采用batch并行；ring16 profile、其余19类Conv shape、目标JSON/simulator/hardware均未接入，G4保持未通过。下一原子步骤是实现`w4_conv_ring16_candidate_v1`并与本profile在同一logical tensor上比较。
- 精确回退：revert `299290de9de07a442fcb6be4779880e3cf08c63b`；上一根仓恢复点为`ccaf43b8230edcfcf78109676998cc48f614af3f`。

## 2026-07-12：W4 ring16 Conv0 profile与双profile一致性

- 根仓提交 `08d863ab89c184ea5c2ba18801c336737da14789`，父提交 `16377fa143bdd16571446839d6f337355894dcdb`，`feat: add W4 ring16 Conv relayout`。
- 范围：新增`w4_conv_ring16_candidate_v1`，A按连续C chunk归属16个slice，B/bias/per-channel qparams/multiplier/P/D按连续K-owner归属slice，x/y标量qparams逐slice复制；物理轴分别为NHWC-local、RSK-local/global-C、NHWK-local。每个K owner的候选ring顺序显式为`(owner+step)%16`，共16步/15次neighbor transfer。
- 实现独立于W2 `SmallConvPhysicalLayout`和batch profile；提供forward/inverse、logical/physical coordinate、AG window、ring step解释、tail/replica/activity/address校验及LayoutRecord。微型C=5/K=7用同一golden同时生成batch/ring bundle，两侧恢复的A/B/qparams/P/D逐对象bit-exact。
- 正式双profile报告`artifacts/w4/conv0_profiles_report.json`为11,840 bytes，SHA-256 `11ba322444c624a5ab1f6b4f7797b96b84eb45692d6b2c0b92eb1e44105f4e67`。现有W3 Conv0的12类对象在batch/ring下inverse hash均等于logical hash且彼此相同；batch使用71,063,552 physical bytes、每slice 4,441,472 bytes，ring使用77,122,560 physical bytes、每slice 4,820,160 bytes，均低于25,165,824-byte slice容量。Conv0 ring为`c_tile=1`、`k_tile=4`，step0～2携带C=0～2，step3～15为空贡献且last只在step15。
- 验证：Conv聚焦测试增至5项，新增非零K owner环回、batch/ring logical一致、formal Conv0 ring capacity、C/K tail、scalar replica破坏等；根仓全量51项测试通过。原batch-only报告重跑后SHA-256仍为`c91ae0ddbc17b41121d832a16d4a3de3706a9eaccfc59faf834de45b9e6f23b5`，证明验证工具重构未改变既有证据。
- 边界：本提交只证明两种软件物理合同可逆且logical等价，不证明ring数据在NDP/目标simulator中完成数值执行，也不批准`(owner+step)%16`为硬件真值。下一原子步骤是自动覆盖正式20类Conv shape并形成profile裁决包；G4保持未通过。
- 精确回退：revert `08d863ab89c184ea5c2ba18801c336737da14789`；上一根仓恢复点为`16377fa143bdd16571446839d6f337355894dcdb`。

## 2026-07-12：W4正式Conv 53节点/20类shape覆盖矩阵

- 根仓提交 `274d6c6db55c3912cf4c111b98a95abb1d863723`，父提交 `c4eb3b3e4e65c55b52480c7192285553e4d43380`，`feat: verify all W4 Conv shape families`。
- 新增稳定family提取：从现有`artifacts/w3/model_graph.json`按A/B/D shape、kernel、stride、padding、dilation和group归并QLinearConv，得到20个内容hash ID family，覆盖53/53节点且无重复；重复运行family ID和成员顺序一致。
- 每个family用N=16正式shape同时执行batch/ring `plan()`：输出shape匹配图目录，per-slice容量均小于25,165,824 bytes；C/K逻辑坐标各归属唯一slice，所有16个K owner的`(owner+step)%16`均为slice 0～15排列。最大占用仍是Conv0 family `conv-family-a3194a82fe78`：batch 4,441,472 bytes、ring 4,820,160 bytes。
- 每类再生成N=1非零坐标模式，覆盖A、B、bias、w_scale/w_zp、x/y qparams、multiplier、int32 P和uint8 D；两profile分别forward/inverse并逐端口对logical hash，20类全部bit-exact且batch/ring hash一致。N=16 batch维不在此重复放大，已由正式Conv0真实W3报告覆盖。
- 机器报告`artifacts/w4/conv_shape_coverage.json`为116,635 bytes，SHA-256 `307f54bd55330270de1cb90fe42a8ee4433d6de66e23f9291c46148f1d2b30b3`；`contracts/architecture.json`登记为candidate software evidence。
- 新增3项普通回归，验证53→20稳定归并、全部formal plan容量/owner/ring排列及一个确定性family双profile完整round-trip；根仓全量54项测试通过，coverage工具全20类显式运行通过。
- 新增ADR-002候选裁决文档：不批准任何profile，集中请求硬件侧确认slice含义、B/qparams归属、ring方向/起点、im2col/AG、psum和requant位置及适用RTL/ISA版本。等待回复不阻塞W4内部继续MaxPool。
- 边界：除Conv0外，其余family使用N=1确定性layout模式而非重新加载全部W3 runtime tensor；该证据证明shape/layout可逆，不证明目标simulator或硬件数值执行。G4保持未通过。
- 精确回退：revert `274d6c6db55c3912cf4c111b98a95abb1d863723`；上一根仓恢复点为`c4eb3b3e4e65c55b52480c7192285553e4d43380`。

## 2026-07-12：W4 MaxPool双profile与Conv D零拷贝

- 根仓提交 `eef252d5d0d0cd2eb56a651a83882cb5d604a943`，父提交 `393965720c06d9cf0e875829d0ae2fb547a5207d`，`feat: add W4 MaxPool relayouts`。
- 新增`w4_maxpool_batch16_candidate_v1`和`w4_maxpool_channel16_candidate_v1`：前者一张样本一个slice，A/D为HWC并按C=8补tail；后者按连续C chunk分16 slice，A/D为NHWC-local。两者都不物化窗口，由AG坐标解释；正式软件语义的空间padding固定uint8 0，channel tail使用显式producer tail值，二者不得混用。
- 支持forward/inverse、logical/physical coordinate、window data/padding解释、tail/activity/address校验和LayoutRecord。仅支持正式路径需要的`ceil_mode=0`、`storage_order=0`，其他值执行前硬失败。
- 引入可审计零拷贝证明：consumer A可显式复用producer Conv D的16个base address；证明同时检查稳定tensor ID、logical shape、每slice physical shape、payload大小和全部物理字节。微型C=5用非零tail验证batch Conv→batch Pool及ring Conv→channel Pool均成立。
- 正式node-0002属性为kernel 3×3、stride 2×2、pads 1、ceil/storage 0，shape `[16,64,112,112]→[16,64,56,56]`。工具只读取现有W3输入/输出并复用Conv0 initializer；batch/channel两profileinverse均bit-exact，两个Conv D→Pool A零拷贝证明均通过。含alias地址时每slice使用4,642,176/5,020,864 bytes，均小于25,165,824-byte容量。
- 机器报告`artifacts/w4/maxpool_profiles_report.json`为3,882 bytes，SHA-256 `97373125f62ba29c47981bb7e05e1ccd3862060f6275fe4ee34418b6c16f9cfc`；architecture合同登记两profile和正式证据。
- 新增3项聚焦测试，覆盖双profile round-trip、坐标/window、channel tail、Conv alias、正式shape、非法ceil/storage/base和故意破坏tail；根仓全量57项测试通过。
- 边界：当前只证明layout、正式raw inverse和producer/consumer零拷贝兼容，不证明目标MaxPool JSON/GA/simulator/hardware数值执行；candidate未获硬件批准，G4保持未通过。下一原子步骤是QLinearAdd。
- 精确回退：revert `eef252d5d0d0cd2eb56a651a83882cb5d604a943`；上一根仓恢复点为`393965720c06d9cf0e875829d0ae2fb547a5207d`。

## 2026-07-12：W4 QLinearAdd双profile、残差兼容与dense广播

- 根仓提交 `63f5eb5437057f6aa032feaceb9a0af7adaea7b6`，父提交 `ff1f49bb22c9de548420e4220e19204c19e9cb26`，`feat: add W4 QLinearAdd relayouts`。
- 新增`w4_qlinearadd_batch16_candidate_v1`和`w4_qlinearadd_channel16_candidate_v1`。正式广播范围冻结为同shape rank-4/rank-2及dense `[N,F]+[F]`；batch profile按样本归属slice并把feature补到8，channel profile按连续C/F chunk归属16 slice。A、B、D的tail分别使用`a_zero_point`、`b_zero_point`、`y_zero_point`，六个独立标量qparams逐slice复制。
- 两残差分支可独立执行producer兼容证明：检查producer合同、稳定tensor ID、logical shape/dtype、每slice physical shape、payload大小及全部物理字节。基址也相等时才标记exact alias；默认独立producer常使用相同相对D offset，不能同时占用Add A/B，因此双分支同时零拷贝明确留给W7分配互不重叠的producer基址，不把布局兼容误报成已完成内存计划。
- 正式图17个QLinearAdd归为5类shape-broadcast：16个残差节点覆盖`[16,256,56,56]`、`[16,512,28,28]`、`[16,1024,14,14]`、`[16,2048,7,7]`，另有node-0076 `[16,1000]+[1000]`。32条残差输入中20条来自QLinearConv、12条来自前一QLinearAdd；每条producer输出zero-point tensor ID均与consumer对应输入zero-point ID一致，batch/channel physical shape和payload公式也逐条相等。
- 验证工具只读取现有W3图、subop manifest、node-0007/node-0076的既有tensor及ONNX initializer，不运行ORT、不重建W3。两代表节点的A/B、六个qparams和D共9端口在batch/channel profile下inverse均bit-exact；W3记录的`qlinear_add_affine_requant`仍匹配ORT。机器报告`artifacts/w4/add_profiles_report.json`为74,305 bytes，SHA-256 `9769589a14cc281968925e49645715010db634a8f722093e3ba106d47ae03108`；最大每slice占用2,408,544/25,165,824 bytes。
- 新增4项聚焦测试，覆盖残差与dense广播正逆、D/标量坐标、两类producer profile、单输入exact alias、双输入offset冲突、feature tail、inactive slice、qparam副本、非法广播和越slice地址；根仓全量61项测试通过，正式报告重复生成hash稳定，architecture严格JSON解析及`git diff --check`通过。
- 边界：当前证明软件candidate布局、正式W3 inverse、残差producer/consumer物理兼容及qparam链；不证明目标Add JSON/GA/simulator/hardware数值执行，也不批准双输入同时零拷贝。dense A来自QLinearMatMul，其D兼容待W4 MatMul布局完成；G4保持未通过，下一原子步骤是GlobalAveragePool。
- 精确回退：revert `63f5eb5437057f6aa032feaceb9a0af7adaea7b6`；上一根仓恢复点为`ff1f49bb22c9de548420e4220e19204c19e9cb26`。

## 2026-07-12：W4 GlobalAveragePool双profile与上下游零拷贝

- 根仓提交 `164bc6c09ffa15e333e7a2e8196355369fdea4a6`，父提交 `b0ec7112e41ecde312ecae3c84c569ede02d00db`，`feat: add W4 GlobalAveragePool relayouts`。
- 新增`w4_globalavgpool_batch16_candidate_v1`和`w4_globalavgpool_channel16_candidate_v1`。batch profile按样本归属slice，A为HWC-padded、P/D为11C-padded；channel profile按连续C chunk归属16 slice，A为NHWC-local、P/D为N11C-local。A/P/D tail分别为`x_zero_point`、0、`y_zero_point`；x/y四个qparams及`x_scale/(y_scale*H*W)`派生multiplier逐slice复制。
- reduction责任明确：batch profile在每个样本slice内对各channel执行H×W centered sum；channel profile在每个channel-owner slice内对全部batch分别执行H×W centered sum，二者都不需要跨slice reduction。`explain_reduction()`可列出每个输入逻辑坐标、物理地址、owner slice和INT32 P地址。
- 正式node-0071为`[16,2048,7,7]→[16,2048,1,1]`，spatial size 49。工具只读取既有W3 A、INT32 sum、D和ONNX initializer，并复用node-0070 Add输入构造producer物理包；两profile的A、四个qparams、multiplier、P、D共8端口inverse均bit-exact，W3 `int32_internal_then_requant`证据仍匹配ORT。
- 正式上下游兼容同时闭合：batch/channel的Add node-0070 D→GAP A均满足tensor ID、shape、payload、物理字节和16个base完全一致，exact alias成立；GAP D的singleton H/W在Flatten axis=1时可分别从11C→F或N11C→NF而不改变逐slice字节序和base，零拷贝成立。含输入alias地址时两profile每slice均使用311,472/25,165,824 bytes。
- 机器报告`artifacts/w4/avgpool_profiles_report.json`为13,910 bytes，SHA-256 `cb8ccd709616a851bed109a2a47a70706f9c8ecc0ba76f47eafa0ba3fbb4d3f8`。新增3项聚焦测试，覆盖正逆、reduction地址、P/D坐标、qparam副本、tail/inactive slice、Add exact alias、Flatten零拷贝、正式shape、非法channels_last/dtype/base；根仓全量64项测试通过，报告重复生成hash稳定，architecture严格JSON解析及`git diff --check`通过。
- 边界：当前证明软件candidate布局、正式W3 sum/requant结果的可逆装载及上下游零拷贝，不证明目标AvgPool JSON/GA/simulator/hardware数值执行；G4保持未通过，下一原子步骤是MatMul/dense。
- 精确回退：revert `164bc6c09ffa15e333e7a2e8196355369fdea4a6`；上一根仓恢复点为`b0ec7112e41ecde312ecae3c84c569ede02d00db`。

## 2026-07-12：W4 MatMul/dense双profile与head边界闭合

- 根仓提交 `e0be1cf848850af317e1cb6f120b1c1c2adba3e8`，父提交 `2c4b9ad0361fb039dd4f4845865d2cf68d59e055`，`feat: add W4 QLinearMatMul relayouts`。
- 新增`w4_qlinearmatmul_batch16_candidate_v1`和`w4_qlinearmatmul_ring16_candidate_v1`。batch profile按样本行归属slice，A按K=8补tail，B按K/O=8补tail并逐slice复制，P/D按O=8补tail；ring profile按连续K chunk归属A slice，按连续O owner归属B/P/D，B保存K-global-padded/O-local。六个标量qparams及`x_scale*w_scale/y_scale` multiplier逐slice复制。
- ring候选为每个O owner显式执行16步，activation slice顺序`(owner+step)%16`、15次neighbor transfer；P合同只记录完整K reduction后的INT32 accumulator，逐K tile/逐ring step psum物理保存位置仍明确留到W5取得目标tile合同后确定。
- 正式node-0075为`[16,2048] uint8 × [2048,1000] int8 → [16,1000] int32 P → [16,1000] uint8 D`。batch为K tile 2048/O tile 1000，每slice 2,063,392 bytes；ring为K tile 128/O tile 63、O padded 1008，每slice136,224 bytes；均低于25,165,824-byte容量。两profile的A/B、六qparams、multiplier、P/D共11端口inverse全部bit-exact，W3 `int32_internal_then_requant`及最终Dequantize仍匹配既有证据。
- head转换责任已闭合：正式batch Quantize node-0074 D→MatMul A逐slice字节和base完全一致，exact alias成立；ring输入必须执行batch→K-partition relayout。batch/ring MatMul D→dense Add node-0076 A均exact alias，bias `[1000]`分别逐slice复制或按O owner分片。batch dense Add D与最终Dequantize A物理字节一致但独立bundle基址不同，留W7统一；ring/channel D必须显式O-owner→batch relayout。
- 微型测试额外确认零拷贝需要inactive padding也一致：正式x_zero_point=0与当前Quantize padding相符；若N<16且x_zero_point非零，不得仅比较有效样本后宣称alias。机器报告`artifacts/w4/matmul_profiles_report.json`为16,816 bytes，SHA-256 `c561f4f23e5f5f7e1e5c5a556237fef4266b2b3a99f62ababc0f205a36e565ea`。
- 新增3项聚焦测试，覆盖双profile正逆、K/O tail、inactive slice、scalar副本、坐标、ring step、正式shape/capacity、Quantize alias、dense Add alias和非法shape/dtype；根仓全量67项测试通过，报告重复生成hash稳定，architecture严格JSON解析及`git diff --check`通过。
- W4计划内全部算子族至此均有软件candidate，但G4仍未通过：Conv/整体profile及正式硬件layout未获批准，部分channel↔batch边界需要显式relayout，逐K tile psum属于W5目标合同。下一原子步骤应为全W4 profile/transition矩阵与G4综合门审计，而不是直接把candidate升级为approved。
- 精确回退：revert `e0be1cf848850af317e1cb6f120b1c1c2adba3e8`；上一根仓恢复点为`2c4b9ad0361fb039dd4f4845865d2cf68d59e055`。

## 2026-07-12：全W4 profile/transition综合审计与G4门裁决

- 根仓提交 `f569a1d134f20ec7a1286b4230d86f2fca3f0485`，父提交 `73120e9246cf24e5fd02449c6dbdd55b74fc881f`，`audit: evaluate W4 G4 gate`。
- 新增可重放`resnet50_pipeline.w4_audit.audit_w4_gate()`、CLI `tools/audit_w4_gate.py`和门测试。审计严格使用正式W3图目录、`contracts/architecture.json`及已登记W4报告，不执行ORT、不重建约951 MB W3产物。
- 节点覆盖为78/78：2 Quantize、53 QLinearConv、1 MaxPool、17 QLinearAdd、1 QLinearGlobalAveragePool、1 Flatten、1 QLinearMatMul、2 Dequantize。12个W4 candidate的实现接口均含`forward/inverse/explain_coordinate/validate`；5份算子族报告及2份Conv0报告共7份证据的文件大小和SHA-256全部匹配。
- 正式图93条runtime tensor边均对batch和ring/channel给出责任，91条量化边的producer输出与consumer输入scale/zero-point稳定tensor ID全部一致。batch分类为4 exact alias、1 explicit relayout、87 layout-compatible/W7 rebase、1 zero-copy；ring/channel分类为3、4、85、1。
- 审计纠正GAP边界表述：GAP D→Flatten只是一项singleton存储视图性质，正式图实际为`GAP→Dequantize→Flatten`；batch GAP D与Dequantize A布局兼容并需W7统一base，channel需要显式转batch，真正zero-copy是Dequantize D→Flatten。
- 机器报告`artifacts/w4/g4_gate_audit.json`为100,609 bytes，SHA-256 `f4bd5d3e84ad6c022729179fe2ce01643792c9fedb792bf61c58b83684e32a5a`。新增ADR-003固定结论：software candidate readiness通过，但G4=`not_passed`、`w5_authorized=false`。
- G4三项阻塞标准为：没有approved target profile、没有冻结的RTL/ISA/register-map版本、没有approved activation/weight/bias/qparams/psum/D物理layout合同。其余资源数、opcode、DDR地址单位、instruction mask和硬件load/dump协议继续留在architecture unresolved账本。
- 根仓全量68项测试通过，审计报告重复生成hash稳定，architecture严格JSON解析及`git diff --check`通过。当前按操作者要求等待正式硬件布局与拓扑裁决，暂不进入W5。
- 精确回退：revert `f569a1d134f20ec7a1286b4230d86f2fca3f0485`；上一根仓恢复点为`73120e9246cf24e5fd02449c6dbdd55b74fc881f`。

## 2026-07-13：版本化硬件批准合同与G4自动重审

- 根仓提交 `c839143bbc8d4909a3eb40bbcb32d53de4eaa3f2`，父提交 `b7e645b40669635e5d68958c7d89319ddc2c6eab`，`feat: validate versioned hardware approvals`。
- 新增严格`hardware_approval` schema、加载/校验器、CLI与ADR-004；合同必须同时给出批准人/日期、完整RTL commit、ISA/register-map版本、整网profile、各算子layout、A/B/bias/qparams/psum/D物理对象、数值语义、opcode/字段位宽、runtime协议和带SHA证据，未知或多余字段均拒绝。
- G4审计默认只读`contracts/hardware_approval.json`：文件缺失或无效时三个硬件criteria保持false；测试fixture证明合法batch/ring合同可自动重审并打开G4，但仓库没有伪造真实批准文件，因此正式状态仍为`not_passed`、`w5_authorized=false`。
- 新增硬件批准及G4正反路径回归；本步骤不生成JSON/bitstream、不修改candidate为approved。
- 精确回退：revert `c839143bbc8d4909a3eb40bbcb32d53de4eaa3f2`；上一根仓恢复点为`b7e645b40669635e5d68958c7d89319ddc2c6eab`。

## 2026-07-13：W4等待期整网物理审计与通用逻辑比较器

- 根仓提交 `bfafbe61a0a96f47851d6f67101483f6a9f61383`，父提交 `c839143bbc8d4909a3eb40bbcb32d53de4eaa3f2`，`feat: complete W4 pre-hardware readiness`。
- 对正式图93条runtime边在batch和ring/channel两个profile下逐边构造producer/consumer物理签名并验证；batch 92条直接兼容、1条显式relayout，ring/channel 89条直接兼容、4条显式relayout，91条量化边qparam身份全部一致。
- 新增双profile整网dry-run成本报告和candidate activation内存计划：报告`artifacts/w4/network_candidate_dry_run.json`为615,520 bytes，SHA-256 `852ea566112a92fd1965b6a2c2525449462e2b716db0941b368f87abc5d1eb18`；两profile的standalone节点容量均通过，生命周期重叠地址互斥，alias动作无冲突，16组残差双分支均为不同且不重叠的活跃对象。报告只估算layout字节，不声称cycle/带宽/能耗。
- 新增通用逻辑tensor比较器、请求/报告schema和`compare-results` CLI：支持任意两方/默认三方配对，整数bit-exact、浮点显式`atol/rtol`，区分missing/load/inverse/shape/dtype/value失败，并按拓扑报告首错坐标、数值与可扩展物理provenance；`.npy`采用mmap分块，稳定报告无时间戳。
- G4机器报告更新为103,311 bytes、SHA-256 `c4679a1bc44d0eac35de3035a4627895223140c22f560dcf19d21a06b37a298e`。software candidate readiness通过；真实hardware结果仍不存在，三个原硬件阻塞criteria不变，G4仍未通过且W5未授权。
- 验证：根仓全量89项测试通过；三参考仓`sync_repositories.py verify`全部匹配lock；schema和architecture严格JSON解析、审计报告重复生成hash稳定、`git diff --check`通过。未读取或重算约951 MB W3产物。
- 精确回退：revert `bfafbe61a0a96f47851d6f67101483f6a9f61383`；上一根仓恢复点为`c839143bbc8d4909a3eb40bbcb32d53de4eaa3f2`。

## 2026-07-13：目标RTL与28-slice性能布局裁决

- 根仓提交 `6626d916534d0fbd8cb0ee16b67bedc72e3caeea`，父提交 `5494c7e2d5925da114bf2e4b924e5bfe1394e1c3`，`docs: adopt 28-slice hardware plan`。
- 操作者确认放弃把旧16-slice布局直接套到28-slice硬件的方案。新增ADR-007，将RTL候选固定为`xlsjdjdk/Trassic2.0_RTL@e3bdebba95dec36ee8eba43caa92a326a88392cd`；在功能完整性相近时选择较新的`master`，不采用旧16-slice `xilinx`分支。
- ResNet50主体首选`w4_group4x7_batch_channel28_candidate_v1`：七个RTL真实4-slice HIGH小环并行分担batch，样本组为`[3,3,2,2,2,2,2]`，环内按C/K owner执行。`w4_global_ring28_candidate_v1`只作代表层比较候选，第一版整网最多允许在GAP后显式转换一次。
- `.agents/agent.md`、`.agents/plan.md`和算子配置规则已切换到28-slice口径；ADR-002标为废止，ADR-003/005标为旧16-slice历史审计，ADR-004升级为28-slice批准合同要求，ADR-006比较器继续有效。旧文档未删除，以保留实验来源和精确回退能力，但已明确禁止把旧物理签名、容量、成本、modulo ring和15-hop结论用于新目标。
- W0～W3模型、lowering、量化语义和约951 MB golden不失效；W4按真实HIGH/LOW拓扑重开，下一步先实现28-slice topology mapper，再按算子顺序重建布局和93边审计。G4=`not_passed`、`w5_authorized=false`，本步骤未生成正式W5 JSON/bitstream。
- 仍需硬件/权威工具链闭合：目标commit的顶层/filelist和clean elaboration、正式端口layout、ISA/register-map及字段编码、INT8 SA/GA/requant/qparams、目标emulator关系和load/start/wait/dump协议。
- 验证：三个参考仓全部匹配`repos.lock.json`；根仓89项测试通过；新旧口径检索和`git diff --check`通过。没有重跑或重算约951 MB W3产物。
- 精确回退：revert `6626d916534d0fbd8cb0ee16b67bedc72e3caeea`；上一根仓恢复点为`5494c7e2d5925da114bf2e4b924e5bfe1394e1c3`。

## 2026-07-13：Codex worktree环境、RTL28必要审计与W4-28底座

- 根仓提交 `29da59346509c11c6bfe6ec168537f278aa7c50b`，父提交 `a887f1f91181e6a46cf91293e321939a7492c22d`，`chore: prepare Codex worktree environments`。新增安全的项目级`on-request + auto_review + workspace-write`配置、轻量`.worktreeinclude`、Windows worktree setup脚本和环境回归；不启用`danger-full-access`。setup只共享Local `.venv`及三个锁定参考仓，不安装、不联网、不复制W3 tensor。主工作区当时93项测试通过。
- 根仓提交 `20351e8aaab1d27d95203ae8dd1c05a9fe707c74`，父提交 `29da59346509c11c6bfe6ec168537f278aa7c50b`，`fix: include nested W3 manifests in worktrees`。真实Codex worktree验收证明当前桌面宿主不会可靠复制ignored目录的更深层manifest，因此递归pattern尝试被后续方案取代；保留该提交以记录失败假设，不把失败包装成已解决。
- 根仓提交 `acd85e9e1d49b86ff952d31eb808cab3888cbfa4`，父提交 `20351e8aaab1d27d95203ae8dd1c05a9fe707c74`，`docs: audit RTL28 hardware contract candidate`；来源worktree提交为`522f501`。新增`contracts/rtl28_candidate_audit.{json,md}`，固定`Trassic2.0_RTL@e3bdebba95dec36ee8eba43caa92a326a88392cd`的权威filelist/top=`NDP_Top_new`、64-bit命令与28-bit mask、WREG字段、HIGH/LOW map、每slice DRAM参数、SA/GA原语和load/start/wait/read路径。报告明确：clean elaboration仍被工具/受保护DDR模型/供应商库阻塞；GA的INT32→UINT8只有截断，不是requant；量化、正式端口layout和板级dump仍需批准。文件只是`candidate_unapproved`，没有创建`hardware_approval.json`，G1/G4不通过。
- 根仓提交 `8ffbec2b97d3292e245352243d43aaf1bf2bd608`，父提交 `acd85e9e1d49b86ff952d31eb808cab3888cbfa4`，`W4-28A add authoritative 28-slice topology`；来源worktree提交为`06880e0cc1b6ea98d32ee71cfd952e9f95ab6cbd`。新增`topology28.py`，以显式RTL lookup table表达七个4-slice HIGH环和一个28-slice LOW环，提供next/prev/walk/traverse/group查询与完整置换/逆映射校验，禁止旧`(owner+step)%28`或连续编号假设。
- 根仓提交 `84d5f06c29c3911d2e52bb84edcef6a92db946e4`，父提交 `8ffbec2b97d3292e245352243d43aaf1bf2bd608`，`feat: add 28-slice profile scheduling contract`；来源worktree提交为`03f521b3a0f17ff4352396009d09b3d2f8f4743c`。新增与物理map解耦的七组batch调度`[3,3,2,2,2,2,2]`、两个candidate profile名和转换策略：主体默认七小环、残差块内禁止转换、整网最多一次、只允许在GAP后到MatMul前评估小环→大环。
- 根仓提交 `d4aef4ff8a51e2a1e232b2a908516fd441275ab1`，父提交 `84d5f06c29c3911d2e52bb84edcef6a92db946e4`，`fix: restore W3 metadata in Codex worktrees`。`.worktreeinclude`只保留能可靠复制的两个W3顶层JSON；两个嵌套manifest以合计约293 KiB的base64跟踪快照保存，setup在worktree内部解码并按原始size/SHA-256恢复约220 KiB JSON，不从Local跨工作区复制，也不包含任何`.npy`。主工作区107项测试通过。
- 根仓提交 `34f83209ea8327cd8577ac6514fd403d117db2f8`，父提交 `d4aef4ff8a51e2a1e232b2a908516fd441275ab1`，`fix: verify locked repositories through worktree links`。`sync_repositories.py verify`只允许junction目标精确等于Git common directory对应Local根下的同名锁定仓；任意其他越界目标仍拒绝，`sync`对共享链接继续硬拒绝。新增RTL审计map↔`topology28`逐slice回归及profile七组数量一致性，主工作区109项测试通过。
- 根仓提交 `ed06c3e1752952614ae345503b8b2e941ada51ee`，父提交 `34f83209ea8327cd8577ac6514fd403d117db2f8`，`test: validate setup in local and worktree modes`。环境测试不再把worktree误判为Local，分别严格检查`source`与`linked/included/restored`状态。
- 最终真实Codex managed worktree `de44`只读终验通过：HEAD=`ed06c3e1752952614ae345503b8b2e941ada51ee`，Git状态干净；`.venv`和三参考仓4/4=`linked`；`legacy77_mapping.json`、`model_graph.json`=`included`，两个manifest=`restored`；setup内置`repository_verify=passed`，独立三仓verify为3/3 `[ok]`，环境测试5/5通过。全程没有用户手工许可中断，没有联网/安装，没有读取、复制或重跑约951 MB W3 tensor。
- 当前W4-28只完成拓扑与调度底座，尚未完成任何28-slice算子物理布局、93边重审或正式硬件数值执行；G4=`not_passed`、`w5_authorized=false`，没有生成W5 JSON/bitstream。下一原子步骤是Quantize/Dequantize 28-slice布局。
- 精确回退：仅回退W4调度可revert `84d5f06c29c3911d2e52bb84edcef6a92db946e4`，仅回退拓扑可在其后revert `8ffbec2b97d3292e245352243d43aaf1bf2bd608`；回退RTL审计可revert `acd85e9e1d49b86ff952d31eb808cab3888cbfa4`。若完整撤销本轮线性序列，按`ed06c3e`、`34f8320`、`d4aef4f`、`84d5f06`、`8ffbec2`、`acd85e9`、`20351e8`、`29da593`逆序revert；上一完整恢复点为`a887f1f91181e6a46cf91293e321939a7492c22d`。

## 2026-07-13：Codex worktree经验固化与全局化边界

- 根仓提交 `e4d57d6488b511355d6ef69a67e0cff42a85d2e2`，父提交 `2fdc2da5d20bbb4e5cf6248c250cf47e392c02e3`，`docs: record reusable worktree lessons`。
- 新增`.agents/经验.md`并加入`agent.md`文件入口；文档把tracked源码、小型ignored元数据、深层小型快照、只读大依赖和Local-only大产物分层，记录最终junction/setup方案、真实managed worktree验收、Windows身份/ACL与junction路径校验问题、失败尝试、安全红线、下项目实施顺序和交接检查表。
- 官方能力与本机实测已明确分开：`.worktreeinclude`按官方说明支持ignored路径和gitignore风格pattern；深层manifest改用快照只是当前桌面宿主的实测兼容性兜底，下个项目仍须先做最小真实worktree试验。
- 全局配置只建议承载通用`on-request + auto_review + workspace-write`默认值；`.worktreeinclude`、setup、junction目标、依赖commit/hash和Local-only产物边界继续逐项目提交。本机用户级配置已存在`workspace-write`和workspace网络设置，缺少`approval_policy`与`approvals_reviewer`；本步骤只读审计，没有修改用户级全局文件。
- 验证：`git diff --check`通过；Local setup `-CheckOnly`通过并确认四项共享源、四项固定元数据；三参考仓全部匹配`repos.lock.json`；`tests.test_worktree_environment` 5/5通过。没有联网、安装、读取或重跑W3 tensor。
- 后续根仓提交 `26cb73fd0c0c64083fa16facd46d140683fccdee`，父提交 `b586eb05d9bafbac2baaecbae3ff3d99c8711271`，`docs: normalize worktree experience markdown`；只移除文档末尾多余空白行，使提交级`git show --check`无提示，不改变任何方案或结论。
- 精确回退：先revert `26cb73fd0c0c64083fa16facd46d140683fccdee`，再revert `e4d57d6488b511355d6ef69a67e0cff42a85d2e2`；上一根仓恢复点为`2fdc2da5d20bbb4e5cf6248c250cf47e392c02e3`。

## 2026-07-13：三级Git提交与云端推送规则

- 根仓提交 `c7e077d82a6a2e5f8a067ae13c4b2c69471549d1`，父提交 `834b54ca7056f54b4a2d4a2745f3ae02e059bce0`，`docs: adopt tiered git change policy`。
- 现行规则改为三级：不改变行为/接口/schema合同/layout-qparams/依赖锁/产物hash的微小文字、注释和格式修正不单独提交；范围明确、可聚焦验证的较小代码、测试、规则或文档语义改动做本地原子提交；阶段门、跨模块/跨仓重大集成、关键硬件合同、重要恢复点或操作者明确要求时，才批量推送GitHub并核对远端hash。
- `.agents/agent.md`、`.agents/plan.md`、本文件顶部现行总则和`.agents/经验.md`已同步；经验文档额外给出微小/较小/重大的判定标准、交接例外和云端验收要求。旧history条目继续作为当时事实，不再覆盖2026-07-13现行规则。
- 本次自身属于较小规则改动，只提交本地Git，没有推送GitHub。验证使用`git diff --check`和现行文档旧口径冲突检索；未运行代码测试，未触碰W3产物。
- 精确回退：revert `c7e077d82a6a2e5f8a067ae13c4b2c69471549d1`；上一根仓恢复点为`834b54ca7056f54b4a2d4a2745f3ae02e059bce0`。

## 2026-07-13：W4-28下一阶段与并行判定计划

- 根仓提交 `1fdff87bdcfb1c424e217fbc51230e54ed44fe2d`，父提交 `9a11be90867d55805ae06585be390e13b06a9444`，`docs: plan W4-28 contract migration and parallel waves`。
- `agent.md`新增现行并行判定规则：只有共享合同/API冻结、无前后依赖、主要文件不重叠且可独立测试/提交时才并行；共享schema/contract/公共基类、producer-consumer依赖、正式W3/93边/全量集成和同一硬件裁决默认单线程。Local负责冻结基线/接口/文件范围并顺序集成。
- 审查确认`architecture.json`仍把slice写为16，`hardware_approval.schema.json`、`hardware_approval.py`和fixture也硬编码16；因此下一执行包C0必须先单线程迁移整条机器合同/批准校验链到28-slice candidate，并显式保留旧16证据为legacy。C1再单线程冻结Quantize/Dequantize/View公共布局。
- 只有C0/C1全量回归通过才开启并行门P4；建议第一波三个互不编辑共享文件的任务为Conv、MaxPool/GAP、MatMul/head。之后Local顺序集成并实现依赖producer布局的QLinearAdd，最终单线程重跑28-slice transition、93边、91 qparam链、16残差Add、生命周期/alias和成本报告。
- 当前仍为`G4=not_passed`、`w5_authorized=false`；本步骤只修改规则和计划，没有生成28-slice算子layout、批准合同或W5产物。验证：`git diff --check`通过，旧“直接从Quantize开始”口径已从现行摘要/队列替换；未运行代码测试，未触碰W3产物。
- 精确回退：revert `1fdff87bdcfb1c424e217fbc51230e54ed44fe2d`；上一根仓恢复点为`9a11be90867d55805ae06585be390e13b06a9444`。

## 2026-07-13：16→28方案切换全工作文件夹遗留审计

- 根仓提交 `37109ca25086bd39b318ebdc839c329323102583`，父提交 `4b2d4cebf93410a9a51f897f23e80325799e3834`，`docs: audit stale W4 plan content`。三路只读复核现行文档/ADR、合同/schema/代码/测试、W4小报告/工具/恢复配置；主线程交叉核对后把14组修改项、明确保留项、执行顺序和验收条件写入`plan.md`。没有读取或重跑W3 `.npy`大产物。
- 最高风险不是文字残留，而是活动机器路径：`architecture.json`仍把旧16-slice条目放在现行candidate空间，批准schema/validator只接受16，`w4_audit.py`继续消费旧报告且存在无条件True，测试还要求虚构旧批准直接打开G4/W5。计划因此改为先fail-closed，再迁移architecture/approval/contract validator和legacy证据空间；合成fixture以后只能测结构，永远不能授权W5。
- 旧16报告、通用名称工具、默认`DramGeometry()`、公共layout导出和network dry-run均列入分阶段隔离/重建清单；模型`batch16`、W3冻结产物、W0 mock16、W2 1/4-slice fixture、明确命名的`*16_layout`回归和已标历史ADR继续保留，不做机械16→28替换。
- 文档漂移已列入C0同批清理：ADR-004旧三条件门、`agent.md`错误下一步/参考工具权威性、算子规则把W3写成未完成、阶段I把通用比较器写成不存在。`plan.md`自身的并行门、28资源候选、阶段A和比较器状态已同步纠正。
- 现场新增独立环境阻断：Local根目录`.venv`、`CGRA_SIM`、`ndp-sim-ref`、`NDPFuncModel`均为空目录，与先前验收记录不一致。ENV-01被置于C0之前；只恢复Python和三个锁定参考仓，不触碰W3正式tensor。由于当前无可用项目Python，本轮只执行`git diff --check`和文本冲突检索，没有运行unittest。
- 当前仍为`G4=not_passed`、`w5_authorized=false`，没有生成正式W5 JSON/bitstream。下一原子步骤是ENV-01环境溯源/恢复；随后单线程执行C0-01现行G4 fail-closed，不直接开始28-slice算子layout。
- 精确回退：revert `37109ca25086bd39b318ebdc839c329323102583`；上一根仓恢复点为`4b2d4cebf93410a9a51f897f23e80325799e3834`。

## 2026-07-13：managed worktree junction事故取证、环境恢复与防复发

- 事故根因定位到根仓提交`29da59346509c11c6bfe6ec168537f278aa7c50b`引入的依赖junction设计。会话记录证明15:52时`de44` managed worktree的`.venv`与三参考仓4/4链接及校验仍通过；Local四个目标随后在16:25:01～16:25:04依次被清空，`C:\Users\15383\.codex\worktrees`在16:25:05变化并且`de44`消失。7月可访问任务记录中没有手工删除四目录的命令，因此结论是“桌面宿主回收managed worktree时穿透junction清理Local目标”的高置信因果推断；宿主内部删除没有作为agent shell调用记录，不能表述为捕获到的绝对命令证据。
- 已核对主会话16:25窗口：`4b2d4ce...`只提交`history.md`，相邻agent命令只有状态/文档/Git操作，不会按该顺序清空四项；更早删除smoke worktree和单文件ADR也与本事故无关。错误不在W4-28业务代码，而在“只验证setup即时成功，没有验证worktree归档/销毁安全”的环境交付设计。
- 恢复源为事故前生成的`C:\Users\15383\Desktop\Codex\project\resnet50_int8.zip`，900,437,181 bytes，SHA-256 `f51ba6fff4ed36579b5a35c122ef959da9b603e8cc177deb55bdfbd90ecc2d2e`。先只删除`e49c`中四个已核验junction对象并确认managed worktree无残留同类reparse point，再校验压缩包43,077个选定条目均位于四个指定前缀、无路径越界，最后只恢复`.venv`、`CGRA_SIM`、`ndp-sim-ref`和`NDPFuncModel`；没有整包覆盖主仓、根`.git`或W3。
- 恢复后Python为3.12.13，`pip check`无损坏依赖；`tools/sync_repositories.py verify`确认CGRA=`53c41e02c294bcc54379e686dc9d25bbb93919fa`、ndp=`e299b2804448242d1589b3e58ed7c5a9a5eca09f`、NDP=`35eab40e5314bf603481dd6268bc96ab2ca514a6`，三仓均clean且匹配`repos.lock.json`。ZIP内根仓HEAD较旧，所以该ZIP只作为四项离线恢复源，不能整体还原当前项目。
- 根仓提交`6d74a15669bb07281d31e2044380cdcd1c4775d8`，父提交`91d8577c3131681cbf9360d03e9c99b18da2ffb6`，`fix: disable unsafe worktree junction sharing`。setup删除创建/复用junction的代码并对非Local调用在任何恢复/链接前硬失败；环境测试同步验证Local与fail-closed语义；`agent.md`、`plan.md`和`经验.md`改为“Local集中集成+tracked-only worktree”，并把旧junction结论标为严重失败历史。
- 验证：Local setup `-CheckOnly`核对四项source及四个W3小元数据；对真实`e49c` worktree调用明确失败且未写入；环境测试5/5、根仓全量109/109通过；`pip check`、三仓lock/dirty核验及`git diff --check`通过。没有读取、复制或重跑约951 MB W3 tensor。
- ENV-01完成，下一步恢复权威顺序为C0-01：让现行G4先fail-closed；G4仍为`not_passed`、`w5_authorized=false`，未生成正式W5 JSON/bitstream。
- 精确回退：如只需撤销防复发代码和现行规则，可revert `6d74a15669bb07281d31e2044380cdcd1c4775d8`，但这会重新开放已证明危险的junction路径，不应在当前桌面宿主使用。忽略目录恢复内容不在Git中；若再次丢失，只能按上述ZIP hash或`repos.lock.json`/requirements lock恢复，不能靠Git revert恢复。

## 2026-07-13：W4-28 C0-01现行G4 fail-closed

- 根仓提交`f897882711114ed9f93c5fc35470dea8cbd55092`，父提交`e0f9fca2dad0bf6db57de99fa96a4f828c3d3e80`，`fix: make current W4 gate fail closed`。
- `w4_audit.py`不再把旧16-slice插件、93边、容量、生命周期/alias和成本证据混入current gate；这些结果进入`legacy16_evidence`且固定`current_gate_eligible=false`。两个原先无条件为True的roundtrip/capacity项改为从登记报告的实际布尔声明推导。
- current gate显式要求：architecture声明28 slice、28-slice七算子族布局证据、28-slice 93边物理审计、28-slice profile成本证据、clean elaboration批准，以及目标profile/RTL-ISA-register-map/物理layout批准。缺任一项均保持`G4=not_passed`、`w5_authorized=false`。
- 硬件批准结构校验与G4授权已分离：旧fixture仍可得到`valid=true`，但只标`validation_scope=structure_only`且`current_gate_eligible=false`，不会再打开W5；无效批准仍给出原校验错误。当前无真实`hardware_approval.json`。
- 聚焦11项hardware approval/G4测试与根仓全量109/109通过，`py_compile`和`git diff --check`通过。新current报告在临时生成时两次SHA-256均为`222f73709afe439e3f7179bbb503c1b318dbf5bef230b91f7138d71852fe3e83`、106,034 bytes；为避免覆盖仍待C0-05归档的tracked legacy16报告，本提交没有改写`artifacts/w4/g4_gate_audit.json`。没有读取或重跑W3大tensor。
- C0-01完成；下一步按顺序单线程执行C0-02/03/04，迁移architecture、批准schema/validator和合同语义校验到28-slice candidate。精确回退：revert `f897882711114ed9f93c5fc35470dea8cbd55092`；上一恢复点为`e0f9fca2dad0bf6db57de99fa96a4f828c3d3e80`。

## 2026-07-13：W4-28 C0-02/03/04机器合同迁移

- 根仓提交`448c21c746bb76b271d21f0e9ae43806cab15185`，父提交`f897882711114ed9f93c5fc35470dea8cbd55092`，`feat: migrate W4 contracts to rtl28`。`architecture.json`升级为0.2并唯一登记`Trassic2.0_RTL@e3bdebba95dec36ee8eba43caa92a326a88392cd`、28 slice、SA 8×8、GA 4×4、28-bit mask、显式七条HIGH小环/一条LOW大环、两个精确profile ID和14个planned layout ID；静态RTL审计及地址解释仍为`candidate_unapproved`，没有伪造硬件批准。
- 旧16-slice布局和九份软件证据从current candidate空间移入`legacy_layouts/legacy_evidence`；W2的1/4-slice软件fixture独立放入`fixture_layouts`。审批validator只从planned/current RTL28 registry选择精确profile布局，完全不能选择legacy16条目；planned布局能用于schema结构测试，但固定`layout_evidence_complete=false`。
- `hardware_approval.schema.json`、手写validator和合成fixture统一到0.2/RTL28，交叉校验RTL仓库、完整commit、top/filelist、architecture ID/version、clean elaboration、拓扑、SA/GA、DRAM、mask、精确profile/layout、物理对象、数值语义、ISA、runtime和证据。合成fixture仅证明结构；旧16、`mixed`、错误commit、错误profile布局和未批准elaboration均明确失败。没有创建真实`contracts/hardware_approval.json`。
- `contracts.py`按contract type管理版本，并增加architecture语义校验：旧16活动target、算术/损坏拓扑、含混profile、legacy泄漏、错误RTL入口、错误DRAM address order、planned/current状态和RTL审计文件hash任一不一致均fail-closed。W0临时合同测试只复制20,794-byte RTL审计小证据，不读取正式W3 tensor。`validate-contracts`通过，合同集合digest为`1f138e3bbaad764c3e9756dfabef918dff8f1d34df2b86412bff3977aadea2db`。
- G4另补一层旁路回归：即使candidate registry人为凑齐七个算子族、93边和成本报告，审批所选profile布局若未达到`layout_evidence_complete`也不能授权。根仓全量122/122、聚焦35/35、`py_compile`、JSON解析和`git diff --check`通过。当前报告只在内存生成两次，均为102,285 bytes、SHA-256 `6d1358778222a4348a7f46c255ff5d17423f4e37c36df58c1a59a168256f7403`；没有覆盖仍待C0-05归档的旧tracked报告。
- 当前仍为`software_candidate_readiness=fail`、`G4=not_passed`、`w5_authorized=false`；阻断项为28算子layout、28物理93边、28 profile成本、clean elaboration以及正式profile/ISA/register-map/layout批准。下一原子包是C0-05/06/07与DOC-01～04：归档旧报告、隔离旧工具入口、版本化RTL证据来源并清理现行文档漂移；不直接进入C1/W5。精确回退：revert `448c21c746bb76b271d21f0e9ae43806cab15185`；上一恢复点为`f897882711114ed9f93c5fc35470dea8cbd55092`。

## 2026-07-13：W4-28 C0-05/06/07与现行文档清理完成

- 根仓提交`e23ac8abaf4531969fab23ff758d017eaf39117d`，父提交`bf6f6311c62a16cb43fcce339c0c932c2e65ed9e`，`fix: isolate legacy W4 evidence and lock rtl28 source`。本提交完成C0剩余三项及DOC-01～04；只做本地Git提交，没有推送GitHub。
- C0-05把九份旧16-slice报告全部固定为`target_family=legacy16`、`slice_count=16`、`status=superseded_by_adr_007`、`current_gate_eligible=false`，并新建不可变索引`artifacts/w4/legacy16_index.json`。索引为2,499 bytes、SHA-256 `69aba8760ce3250b5a826a03babbfa37e986d4ec563c8770ba95bcd351d08a15`；九份报告的规范LF字节身份如下：
  - `conv0_batch16_report.json`：6,267 bytes，`a2ed9e6c4c6b66d47b4f90f29eef048878bba41e4fdec12edb46b8e3ff212fb8`；`conv0_profiles_report.json`：11,608 bytes，`1d56fad355fa8592e0bdf742a28324a5b43abbf3ff70ba4a6a27a0fa147635eb`。
  - `conv_shape_coverage.json`：113,988 bytes，`89887948a158f2660e02bcd3e9d411ca42a2e7b86bc05a44fe71e7105da21ea8`；`maxpool_profiles_report.json`：3,910 bytes，`1b9a9085f89cce57c329bc1c308dd28319e28a9d04d282a60e49f86b121bf97b`。
  - `add_profiles_report.json`：72,046 bytes，`502b34dfbbc0f38d7ea5b1d7dc46e709b3f2676463109b59f67d68e29dadc3b9`；`avgpool_profiles_report.json`：13,625 bytes，`0b9aaabe7e9b68651a630b2196c49ced5673f08c03b5690dab3d4aabe2c04bf2`。
  - `matmul_profiles_report.json`：16,505 bytes，`380a900f6974b3d925252463fb768ceec79843dc50819fe2a5359820844c77a4`；`network_candidate_dry_run.json`：596,856 bytes，`efcc3f921c6d4f8488ebe90716119a1461c5f13c50dccc5ea120ae47c394076f`；旧`g4_gate_audit.json`：99,993 bytes，`b0d5fc55e164250b4729cc0228d39d050ffcf5d2b235256e404e1a2aa73c0546`。
- C0-06为八个旧生成器加入必需的`--legacy16`确认，并把输出限制在`artifacts/w4/legacy16/`；注册历史快照不能原地覆盖。当前RTL28 G4输出只能采用`artifacts/w4/rtl28/<architecture_sha256>/<evidence_kind>-<content_sha256>.json`，工具直接写入用于计算内容地址的规范UTF-8/LF字节。暂存区逐blob回查确认索引及九份报告的size/hash与合同完全一致，避免Windows CRLF使fresh checkout失效。
- C0-07把`repos.lock.json`升级为0.3并登记`Trassic2.0_RTL@e3bdebba95dec36ee8eba43caa92a326a88392cd`的20,794-byte静态审计快照，SHA-256 `69505a527a53c25b0bb828b192aba991fba78e838a2429f9cb99d251b8a815aa`；`verify --evidence-only`可在没有外部仓目录的fresh checkout核对该证据。`backend.json`明确：`NDPFuncModel`仅是W2功能参考，RTL28快照仅是不可执行的candidate evidence，目标simulator和hardware仍未批准且实现不可用；快照锁只证明跟踪字节和内嵌来源声明，不替代远端可达性、clean elaboration或真实硬件批准。
- DOC-01～04同步修正`agent.md`、`plan.md`、算子规则、ADR-004、RTL28审计说明和算子覆盖表：当前权威事实是W3/G3已完成、C0-01～07已完成，下一步为C1的28-slice几何及Quantize/Dequantize/View公共布局；旧一sample一slice、16-slice成本和W2 simulator结论只保留为历史/fixture，不再充当current目标。
- 验证：根仓全量133/133通过，相关聚焦40/40通过；`validate-contracts`摘要为`a0b60b3f215349cf8c9df6569b21a72952454aab2ae038eb926028f488ac50b3`；外部证据单验和三个本地锁定参考仓全验通过；`py_compile`、JSON解析、工作树/暂存区`diff --check`通过。最终current G4报告在内存生成两次均为102,622 bytes、SHA-256 `9d5edc41e553f8b42bfa012579381c2619e76d5edbde495c04a831f08e94d130`，对应architecture SHA-256 `ca0c4ba7a261258b9dfc4009d3db963c9aac4bd921f3bb4815b4f5da8080899a`。
- 当前门状态保持`software_candidate_readiness=fail`、`G4=not_passed`、`w5_authorized=false`、`current_gate_eligible=false`；没有生成正式RTL28 G4文件、W5 JSON/bitstream或真实`hardware_approval.json`，没有读取、复制或重跑约951 MB W3 tensor。C0到此全部完成，下一原子步骤是单线程C1；只有C1公共接口冻结并全量回归通过后，才按并行门评估Conv、Pool和MatMul三个独立布局包。
- 精确回退：revert `e23ac8abaf4531969fab23ff758d017eaf39117d`；上一恢复点为`bf6f6311c62a16cb43fcce339c0c932c2e65ed9e`。该回退会重新暴露旧报告/工具混入current路径和未锁定外部证据的风险，不应在继续W4-28时使用。

## 2026-07-13：W4-28 C1公共geometry与Quantize/Dequantize/View布局完成

- 根仓提交`c2443f7dbc33acb36ffb69e4b492d9cf0ed6a1bc`，父提交`29e2de616b6ef4037a2d67cdccdc45f7e53ee5d8`，`feat: freeze rtl28 simple layout contracts`；本步骤按计划单线程完成，只做本地Git提交，没有推送GitHub。
- 协作安全口径同步写入`agent.md`和`经验.md`：Local任务内派生的协作子代理共享同一Local目录，可见`.venv`、三个参考仓和Local-only产物，但必须分配互不重叠文件，Git/公共合同/最终集成由主任务串行；独立managed worktree只拥有创建时tracked快照和显式小型元数据，禁止把Local依赖以junction/symlink交付，旧detached worktree也不能假定包含当前HEAD。
- `memory.py`取消无参数`DramGeometry()`的隐式16-slice默认，冻结`TARGET_DRAM_GEOMETRY28`与`LEGACY_DRAM_GEOMETRY16`两个命名常量；所有旧16模块和工具显式申请legacy geometry。DRAM bank/row/column解释与地址顺序继续标为`candidate_unapproved`，本步骤不把RTL静态证据伪装成硬件批准。
- current `simple_layout.py`实现RTL28 QuantizeLinear、DequantizeLinear和singleton-spatial zero-copy View的`forward/inverse/explain_coordinate/validate`。默认profile按七个真实HIGH环和`[3,3,2,2,2,2,2]`分样本，每owner固定3个sample存储槽并显式验证2-sample组inactive tail；global profile按真实LOW 28-owner顺序切F/C。逻辑`N,F,...`写成local `N,...,F-local`，端口区16-byte对齐、元素小端；scale/zp在28 slice逐字节复制，Quantize/Dequantize的A/D tail分别使用0、0.0或对应zero point。
- View只允许`axis=1`且输入为`[N,F,1,...,1]`，输出与来源共享全部28个base address和physical bytes；非singleton空间、错误profile、错误batch/geometry、tail破坏、qparam副本不一致均fail-closed。旧实现移至`simple16_layout.py`并由显式legacy测试导入，公共`resnet50_pipeline.layout`不再导出旧16算子类。
- `architecture.json`把group4x7/global的simple和view共4个layout从planned提升为current RTL28 candidate；planned剩10项。合同校验要求planned/candidate互斥且并集精确等于两个profile的14个冻结layout ID。G4插件表同时保留legacy16接口诊断和6个current simple/view接口，合成批准fixture额外固定为structure-only，不能取得gate authority。
- 回归结果：C1/legacy/memory/contract/approval/G4聚焦45/45通过；根仓全量141/141通过。`validate-contracts` digest为`9672bd530f29b2b1aa3f65e1cf1c0931d878818a175b5404701e638f2baffe28`；RTL28 external evidence与CGRA_SIM、ndp-sim-ref、NDPFuncModel三个本地仓全部匹配lock。current G4报告内存生成两次逐字节相同，105,995 bytes、SHA-256 `a60476efd2324d64560b186c08337bfa29a2177b4d57eabcfaceb4c9a8d9a486`，architecture SHA-256 `1b5491802744203f4a68a8fa9d9a924f903211ff850a6fd3d1f21875c38205c9`。
- 当前仅simple/view两个算子族进入candidate；仍缺Conv、MaxPool、QLinearAdd、GAP、MatMul、RTL28全93边/成本、clean elaboration和正式布局/ISA批准，所以`software_candidate_readiness=fail`、`G4=not_passed`、`w5_authorized=false`、`current_gate_eligible=false`。没有写入正式G4证据文件，没有生成W5 JSON/bitstream或真实`hardware_approval.json`，没有读取、复制或重跑约951 MB W3 tensor。
- P4判定通过：下一波可在同一Local工作目录用最多三个协作子任务分别实现Conv、Pool（MaxPool+GAP）和MatMul；三者只能编辑各自实现、测试和证据生成器，不得修改`.agents`、architecture/approval schema、`memory.py`、`profile28.py`、`topology28.py`、公共layout模块或自行Git操作。主任务顺序审阅、更新全局合同、跑全量回归和提交；若任一实现要求改变C1公共API，立即关闭并行门回到单线程。
- 精确回退：revert `c2443f7dbc33acb36ffb69e4b492d9cf0ed6a1bc`；上一恢复点为`29e2de616b6ef4037a2d67cdccdc45f7e53ee5d8`。该回退会同时移除C1 current布局、显式geometry隔离和P4放行记录，不应在继续RTL28布局波次时使用。

## 2026-07-13：并行波次前16-slice泄漏终审

- 根仓提交`13b9c4a4620f7709aa1e01e1faeaa9c7e1a56b05`，父提交`d905a74ac22db090a2cb023451a5298b5f6f1096`，`test: guard rtl28 from legacy16 leakage`；本步骤单线程完成并作为Conv/Pool/MatMul三路共享Local任务的共同基线。
- 终审覆盖活动公共API、current architecture registry、hardware approval/G4、默认geometry、通用命名模块、旧工具入口和现行计划。结论：current planned/candidate registry的14个ID全部为`rtl28/28`，公共layout不导出旧16类，目标geometry无隐式16默认；剩余数字16只属于模型batch16、W0 mock、W2 1/4-slice fixture或显式legacy16代码/证据。
- 修复了`plan.md`顶部仍停在C0/C1前的错误当前主线、进度表、执行队列和“Local环境为空”旧事故状态；`conv_coverage.py`、`network_dry_run.py`、`w4_profiles.py`增加`legacy16`/gate-ineligible模块标识，避免后续RTL28实现误用旧物理公式。新增`test_rtl28_legacy_isolation.py`固定current registry、公共API、current模块导入和三个历史模块的隔离边界。
- 聚焦隔离/合同/G4/legacy证据回归32/32通过，根仓全量145/145通过，`validate-contracts` digest保持`9672bd530f29b2b1aa3f65e1cf1c0931d878818a175b5404701e638f2baffe28`；没有读取或重跑W3大tensor，没有改变G4/W5状态或生成正式W5产物。
- 精确回退：revert `13b9c4a4620f7709aa1e01e1faeaa9c7e1a56b05`；上一恢复点为`d905a74ac22db090a2cb023451a5298b5f6f1096`。回退会移除自动泄漏防线并恢复错误现行计划，不应作为并行RTL28波次基线。

## 2026-07-13：W4-28 C2第一波Conv、Pool与MatMul布局完成

- 根仓提交`3d55bd3b769eff853ddc4e0266ae904f1b68899d`，父提交`77e1c15afa5edbf227cefe7ea2dc96d2682c0102`，`feat: add rtl28 conv pool and matmul layouts`；本步骤按P4使用三个共享Local协作子任务并行实现，主任务串行审阅、公共集成、全量回归和Git，只做本地提交，没有推送GitHub。
- 三个子任务严格隔离文件：Conv只修改`conv28_layout.py`、对应测试和候选报告工具；Pool只修改`pool28_layout.py`、对应测试和候选报告工具；MatMul只修改`matmul28_layout.py`、对应测试和候选报告工具。子任务未编辑公共`layout.py`、合同、`.agents`、geometry/profile/topology或Git，主任务最终核对工作树只有约定的九个新增文件后才开始集成。
- Conv在group4x7中把A按HIGH环内C owner切分，把B/bias/weight qparams按K owner切分并在七组复制，P/D同时遵循sample group与K owner；global候选在显式LOW顺序上分别切C/K。A采用NHWC-local，B采用RSKC且全局C padding，P/D采用NHWK-local；per-K weight zero-point、inactive sample、C/K tail、16-byte对齐、反向恢复和坐标/ring step均可验证。正式Conv0、downsample 1×1和terminal 1×1两profile的per-slice容量计划全部落在25,165,824 bytes以内。
- MaxPool两profile保持producer的sample/channel owner和NHWC-local字节兼容，明确分离空间padding与inactive sample/channel tail；GAP让A、最终int32 centered sum P和D保持同一owner，在各channel owner本地完成H×W归约且不跨batch group，scalar qparams与derived multiplier在28 slice复制。正式MaxPool与`[16,2048,7,7]→[16,2048,1,1]/[16,2048]` GAP计划、window坐标和破坏性负例通过。
- MatMul group4x7候选把A按K切分、B按O切分并跨七组复制、最终int32 P与D按sample group/O切分；global候选在LOW环分别切K/O。A/B/Y qparams和requant multiplier为28份scalar副本；P明确只表示完整K归约后的最终int32值。相同profile的Quantize D可证明byte-compatible并在base相同时exact-alias；GAP后若从group4x7切到global MatMul，必须进行一次显式relayout。
- 主任务把Conv、MaxPool、GAP、MatMul的8个layout从planned提升为current RTL28 candidate，并加入公共layout API和G4插件接口；current registry现为12个candidate、2个planned，覆盖`simple/view/conv/maxpool/global_average_pool/matmul`六个家族，剩余planned只属于QLinearAdd。合同集合digest为`0a408abf4d8173118aebf8bcfe761b789dd952da227971e2d6df40d360365751`，architecture SHA-256为`46851ea8b2679254120a0fee4a4a189077dbf1dc3a9cf1dc031c6413d48e2cf0`。
- 验证：三路独立测试分别6/6、9/9、7/7通过；公共合同/G4/legacy隔离及三路布局聚焦42/42通过；根仓全量167/167通过。`sync_repositories.py verify`确认RTL28静态证据和CGRA_SIM、ndp-sim-ref、NDPFuncModel全部匹配lock；`validate-contracts`、`py_compile`和`git diff --check`通过。三份小型报告重复生成完全一致，紧凑JSON SHA-256/bytes分别为Conv `d8bae8e6066a671d439b354d120167b8b24be9873739ca53ce5b4540ddb15677`/26,382，Pool `98ce6afe2949213361d91ada21eef769be405e41793e65c176e5dbd2595e8be5`/2,248，MatMul `141e8755f2370e4466fb8bddcb8d384afd0f975274e5fcda6a8927f8731d27ae`/1,839。
- current G4报告只在内存重复生成，两次规范字节相同，109,690 bytes、SHA-256 `083ecf6800f0afdd94f4be341c4de105141404c26180cec710c3e05e4a792067`。状态保持`G4=not_passed`、`w5_authorized=false`：当前仍缺QLinearAdd布局、RTL28全93边物理审计、RTL28 profile成本、clean elaboration，以及正式profile/ISA/register-map/物理layout批准。没有写入正式G4证据、W5 JSON/bitstream或真实`hardware_approval.json`，没有读取、复制或重跑约951 MB W3 tensor。
- 下一原子步骤按producer依赖关系单线程实现QLinearAdd两profile，重点验证双残差分支各自qparams、owner/tail/轴序兼容、广播、D布局和两输入同时活跃的alias/地址冲突；完成后才进入C3整网审计。精确回退：revert `3d55bd3b769eff853ddc4e0266ae904f1b68899d`；上一恢复点为`77e1c15afa5edbf227cefe7ea2dc96d2682c0102`。

## 2026-07-14：W4-28 C2 QLinearAdd两profile布局完成

- 根仓提交`e67e05b9f373a4fb71777fbc6a11784869f06d4a`，父提交`0a41bbe6a9ed65d35b9ef7662b6b8f4502c3bca4`，`feat: add rtl28 qlinearadd layout`；本步骤按要求由主任务单线程完成，只做本地提交，没有推送GitHub。
- 新增`QLinearAddPhysicalLayout`的group4x7和global LOW候选。正式支持范围冻结为同shape rank-2/rank-4残差加，以及dense `[N,F]+[F]`；其他广播在规划阶段fail-closed。A/B/D均为uint8且分别用`a_zero_point`、`b_zero_point`、`y_zero_point`填充inactive sample/feature tail；A/B/Y的三组scale/zp保持六个独立scalar端口并在28 slice逐字节复制。
- group4x7让同shapeA/B/D共享`[3,3,2,2,2,2,2]` sample group和每条显式HIGH环的feature owner；dense `[F]` B按feature owner切分并跨七组复制。global候选保留全部16个样本并沿显式LOW owner切feature。两profile均提供`forward/inverse/inverse_port/explain_coordinate/validate/capacity_report/layout_records`，端口按16-byte小端对齐，17个正式Add节点的5组shape全部能规划：16个同shape残差Add及1个`[16,1000]+[1000]` dense bias Add。
- producer兼容证明支持Conv、既有Add和MatMul的D端口，逐slice核对profile、tensor ID、logical shape/dtype、sample/feature ownership、physical shape、payload及base address。A/B精确alias必须分别与producer D完全同址同字节；两个输入同时活跃时，每个slice的地址区间必须互斥。测试确认两条默认Conv D虽然字节兼容，但因默认base相撞会拒绝双alias；为两条producer分配不同对齐区间后，28个slice的双alias证明全部通过。
- `architecture.json`把两个Add布局从planned提升为current candidate，现为14个candidate、0个planned并覆盖七个必需家族；公共layout API和G4插件表加入Add，current接口共16个。合同集合digest为`f870d129a9438b908e39e3ff668ef9ae37ee5a547ec5875aed9081a3c147e37d`，architecture SHA-256为`e87ae2df983d405403e10808046e91b08da5355616efa2f8f25f7ca938114eff`。七族registry现在完整，但只代表软件candidate登记完整，批准后的profile layout证据仍不完整。
- 验证：Add定向9/9、合同/G4/legacy隔离聚焦29/29、根仓全量176/176通过；`py_compile`、`validate-contracts`、`git diff --check`及RTL28静态证据和CGRA_SIM、ndp-sim-ref、NDPFuncModel三仓lock核验通过。Add候选报告只在内存重复生成，两次规范字节相同，13,450 bytes、SHA-256 `a87eb1c50e189c8b19a35907fb7f205042dad6bf8eb71ff8ad73201bd9d55a27`；current G4报告同样只在内存生成，两次为110,604 bytes、SHA-256 `c9f3e6afa480484aa27190721807944cff30b29ad9546fd02acdd450ca4b5f3f`。
- 当前仍为`software_candidate_readiness=fail`、`G4=not_passed`、`w5_authorized=false`：缺少RTL28全93边物理验证、RTL28 profile成本、正式hardware approval/clean elaboration、ISA/register-map与物理layout批准。没有写入正式G4证据、W5 JSON/bitstream或真实`hardware_approval.json`，没有读取、复制或重跑约951 MB W3 tensor。
- QLinearAdd提交暂存期间，另一并发工作流陆续写入未跟踪的`resnet50_pipeline/adapters/ndp_rtl28_functional.py`（首次观察为2026-07-14 11:38:03，20,761 bytes）和`tests/test_ndp_rtl28_adapter.py`；二者不属于本步骤且已明确排除，主任务未运行、修改或删除它们。下一原子步骤为单线程C3整网transition、93边、91 qparam链、16个残差Add、生命周期/alias与成本审计。精确回退：revert `e67e05b9f373a4fb71777fbc6a11784869f06d4a`；上一恢复点为`0a41bbe6a9ed65d35b9ef7662b6b8f4502c3bca4`。

## 2026-07-14：采用并行B/C——外部批准请求包与RTL28→NDP候选探针

- 并行B根仓提交`4b1b578796e9b4f11b0fe2fef68021391559b175`，父提交`227822fb34ef1c067607a7a5551de07315332b59`，`docs: add rtl28 hardware approval request`。新增`contracts/rtl28_hardware_approval_request.md`，固定`Trassic2.0_RTL@e3bdebba95dec36ee8eba43caa92a326a88392cd`、`NDP_Top_new`和权威filelist，把八个`APR_*`问题分派给RTL/集成、RTL+量化/编译、板级/固件三类责任方，并逐项要求原始证据、稳定URI、SHA-256和具名签署。请求包SHA-256为`5b9af5654549f8ef77e2bb54123038cfe979d120420fe267e08e071729f54a87`；candidate audit、schema和validator四个引用hash均与当前文件一致，schema 0.2的15个根必填字段都有回填来源。该文件状态是`approval_request`，未外发、未生成或伪造`hardware_approval.json`，G1不变。
- 并行C根仓提交`8634695cfd7c964735338351990f9ad4c459c4c7`，父提交`4b1b578796e9b4f11b0fe2fef68021391559b175`，`feat: add rtl28 ndp functional probe`。新增`NdpRtl28FunctionalAdapter`和三项测试：复用现有`QLinearConvPhysicalLayout`及W2 `NdpFunctionalAdapter`，以可逆紧凑shadow地址映射保留RTL28 slice owner和slice内offset，在受控内存上完成physical bundle→NDP functional→int32 accumulator/UINT8 D→Conv28 inverse。group4x7实际遍历七条HIGH环，global profile走显式LOW代表路径；fixture覆盖batch16、C/K tail、padding、负weight、独立x/y scale和per-K weight scale。非零weight zero-point在没有硬件批准规则时fail-closed；adapter固定`status=candidate_only`、`target_simulator_validated=false`、`g6_validated=false`。
- 主任务独立验证：新增探针3/3、连同原W2 NDP及Conv28布局聚焦11/11、根仓全量179/179通过；`validate-contracts`返回digest `f870d129a9438b908e39e3ff668ef9ae37ee5a547ec5875aed9081a3c147e37d`；`sync_repositories.py verify`确认RTL28静态证据及CGRA_SIM、ndp-sim-ref、NDPFuncModel全部匹配lock；两次提交前`git diff --cached --check`通过。全量测试仅保留既有NumPy标量转换DeprecationWarning，没有失败。
- 当前完成位置：并行B完成“请求材料可直接转发”，等待外部责任方返回原始证据与签署；并行C完成W2→W4/W6之间的candidate-only接线探针，但没有目标simulator/JSON/ISA/RTL执行，因此不计入G6。W4仍停在C2完成、C3未开始，`software_candidate_readiness=fail`、`G4=not_passed`、`w5_authorized=false`；没有读取或重跑W3大tensor，没有生成W5 JSON/bitstream、正式G4证据或真实批准合同。
- 下一步建议：主线按依赖单线程执行C3，重建RTL28 transition、93边、91 qparam链、16个残差Add、生命周期/alias和成本审计；并行B转为低本地开销的外部等待，收到答复后只做hash/schema/权威性验收。C3验收要求真实HIGH/LOW owner、转换、地址与成本报告全部确定且全量回归通过；禁止把本探针或请求包提升为target simulator/hardware/门通过证据。工作树中另有本轮开始前即存在的`.agents/agent.md`规则补充，本轮原样保留并排除在提交外。
- 精确回退：先revert `8634695cfd7c964735338351990f9ad4c459c4c7`移除并行C，再revert `4b1b578796e9b4f11b0fe2fef68021391559b175`移除并行B；两项之前的恢复点为`227822fb34ef1c067607a7a5551de07315332b59`。两提交均只在本地，未推送GitHub。

## 2026-07-14：W4-28 C3整网物理兼容、生命周期和静态成本审计完成

- 根仓提交`496a592d54bfefdb53a107e929e034ebff36a1b1`，父提交`739d8da80ce80938c12a915d0916556c8a9cf034`，`feat: audit rtl28 whole-network layouts`；本步骤按计划由主任务单线程完成，只做本地提交，没有推送GitHub。开始前对并行B/C三个提交做了只读简审：父链连续，批准请求包固定八项APR且不冒充批准，NDP探针保持`candidate_only`并明确不计入目标simulator/G6；聚焦19/19、合同及四项lock核验通过。
- 新增`network28_audit.py`及CLI，且只读取小型`artifacts/w3/model_graph.json`目录，不读取或重算约951 MB W3 `.npy`。审计器对78个正式节点的两种profile都调用现行RTL28布局计划API，展开真实七条HIGH 4-owner小环和显式LOW 28-owner顺序，为每条运行边生成包含logical shape/dtype、profile、partition、tile、存储样本数、physical shape、逐slice sample/feature区域、payload/alignment、tail语义、端序和owner顺序的物理签名。
- 两种整网调度均通过：`group4x7_only`全78节点保持group4x7，无profile转换；`group4x7_to_global_head`前75节点为group4x7，MatMul及其后3节点为global，只在`node-0074` Quantize→`node-0075` MatMul发生一次UINT8显式relayout，残差块内无转换。每种调度均覆盖93条producer→consumer运行边、91条量化qparam身份链和16个双分支残差Add；全group分类为34条exact-alias接口、57条rebase和2条zero-copy view，global-head分类为33/57/2外加1条显式转换。
- 生命周期审计包含1个图输入与78个节点输出，共79个运行时tensor；最终网络输出和图输入都有独立物理签名。按slice对称的确定性16-byte first-fit候选分配检查全部93条alias动作及16组同时活跃残差分支，范围冲突为0；两调度high-water均为2,558,976 bytes/slice，低于25,165,824-byte候选容量。静态成本来自实际节点计划，登记lane利用率、ring byte-hop、weight和dense broadcast跨组复制、operator bundle/INT32/qparam字节、3/2 sample barrier尾部和转换读写量；head转换静态读写量为76,160 bytes，明确不宣称cycle、带宽、能耗或硬件性能。
- edge/cost证据以architecture语义基线`c5d57f5a2a5a684f6175a43dbd8b860494be6a930573ebbcc61c47c763e45543`和内容hash双重寻址。物理边报告为2,205,439 bytes、SHA-256 `75c9c2f94b04e1d7ecb1b945cd1efd48d8016642cc058f268c4e74fdffcc1a02`；成本报告为152,987 bytes、SHA-256 `a8d795b58e31bfa70f931218ea27bd1aa4700d247c7ef357cb1c84b969087c3c`。`architecture.json`登记两项`candidate_software_evidence`；合同validator和G4入口逐文件校验basis/path/hash/size/语义，架构/profile/layout变化会自动使旧证据失效，登记本身不形成自引用hash循环。
- 验证：新增整网测试8项，C3/合同/G4聚焦32/32通过；根仓全量190/190通过，仅保留既有NumPy标量转换DeprecationWarning。`validate-contracts` digest为`beae788edb470c4565232e3216de971adaca77923f135b8f7ff66394ce7947c8`；`sync_repositories.py verify`确认RTL28静态证据以及CGRA_SIM、ndp-sim-ref、NDPFuncModel全部匹配lock；CLI重复生成证据路径/hash/size一致，`py_compile`和`git diff --check`通过。W0临时合同fixture同步复制登记证据，生产校验没有放宽。
- 当前完成位置：W4-28 C0/C1/C2/C3软件候选工作全部完成，G4的`target28_all_93_edges_physically_verified`和`target28_profile_cost_evidence_complete`现为true；但`target28_operator_layout_evidence_complete`仍需硬件方批准，clean elaboration、approved profile、ISA/register-map及物理layout合同仍缺，因此`software_candidate_readiness=fail`、`G4=not_passed`、`w5_authorized=false`。没有生成正式W5 JSON/bitstream、真实hardware approval、目标simulator或硬件结果。
- 下一步建议：本地主线停止重复C3，等待并收集三类责任方对批准请求包的原始证据与签署合同；收到后用单线程最小包执行approved合同导入、版本/hash/权威性检查和G4自动重审。只有合同与clean elaboration等五项剩余门全部满足才考虑进入W5；若架构、profile、布局、模型、量化或lowering发生变化，先让basis/hash失效并列出所有需重建的下游证据。精确回退：revert `496a592d54bfefdb53a107e929e034ebff36a1b1`；上一恢复点为`739d8da80ce80938c12a915d0916556c8a9cf034`。

## 2026-07-14：W4-28 C4正式配置来源冻结与MaxPool首条审计

- 根仓提交`543bb59254f27b8560d93728ca65fed1f1c00121`，父提交`4ab95323e75fc8e751ec805d4e0591107a6615dc`，`feat: freeze official target config source`；按操作者确认新增ADR-008，把`ndp-sim-ref@e299b2804448242d1589b3e58ed7c5a9a5eca09f`的`jsons/`、`bitstream/`和`model_execplan/`固定为正式28-slice硬件配置来源。backend合同升级到0.2并登记独立`target_config_toolchain`角色，明确`can_execute_numerical_model=false`、ResNet覆盖未完成，因此没有把配置来源批准误写成target simulator或hardware批准。
- 新增`target_config_audit.py`和CLI，盘点42个静态JSON：7个ResNet/共享模板、35个DeepSeek/Transformer模板、0个命名Conv模板。审计直接读取正式`register_map_with_groups1.csv`并执行同commit的`register_mapping.py`；后者生成739个字段绑定。历史规则把CSV方括号范围当成真值而推导“总宽冲突”的结论已纠正：正式消费者实际采用`Nbit`宽度前缀和行顺序，MaxPool涉及10类模块的CSV声明位数加显式padding后全部与当前`FIELD_MAP`总位数一致。CSV仍有13处说明性方括号范围错误，只能忽略，不能另写解析器使用。
- MaxPool模板通过结构、资源上限、字段范围和未知字段fail-closed检查。在`PYTHONHASHSEED=0`、`PYTHONUTF8=1`、seed 42、10000 iterations、10 restarts下两次独立生成的7个输出逐字节一致；128-bit bitstream为3900 bytes、SHA-256 `2e4096f261adb67296116929d94b691b7e27bf3ff2d327a4bb9db8b017900353`。把read stream base从1024改成1040后hash变为`a35fd35fbc33fa85a506df733e9c0a012c79d6fd52ee3eb3b888aa144a0d7d36`；把17-bit LC end设为131072会在官方`Bit`静默取模前被根审计器拒绝。
- 内容寻址报告`contracts/target_config_authority_audit.json`为66,103 bytes、SHA-256 `fee1faa7b4b32f8bf98140d72f1f2e5800e8ebecc8955bc860663adddfa1cca2`，重复生成逐字节相同。合同集合digest更新为`d868fa3d65ded80ba77629b93c49e0859eb62c8361a9592402ea2fb33dda77b4`；`sync_repositories.py verify`确认RTL28静态证据和三个参考仓全部匹配lock。
- 验证：配置审计6/6、合同/审计聚焦23/23、根仓全量199/199通过；`py_compile`、`git diff --check`、合同校验、报告重复生成和仓库lock校验通过。全量只保留既有NumPy标量转换DeprecationWarning。没有读取或重跑约951 MB W3 tensor，没有生成正式W5网络JSON/bitstream、execplan/Bank_data、目标模拟器或硬件结果。
- 当前完成位置：W4-28 C4的“正式配置来源冻结+MaxPool第一条方法闭环”完成；原“目标JSON/bitstream来源版本未知”阻塞消除。G1/G4仍未通过、`w5_authorized=false`，因为clean elaboration、批准物理layout/profile、INT8 requant/qparams数值合同、目标数值模拟器、6144/8192 row地址裁决和板级load/start/wait/dump仍缺。
- 下一步建议：单线程先把同一审计扩展到第二个MaxPool和AvgPool，借此抽取Pool共享shape→LC/stream/buffer/GA规则；公共crosswalk稳定后，再评估并行Quantize/Add-Dequant与GEMV/sum两组。只生成小型审计/hash并保持preflight身份；禁止生成正式W5实例或宣称任何数值/硬件门通过。精确回退：revert `543bb59254f27b8560d93728ca65fed1f1c00121`；上一恢复点为`4ab95323e75fc8e751ec805d4e0591107a6615dc`。

## 2026-07-14：G4门读取正式配置源合同

- 根仓提交`3407a20c86fcf8ea72add5d115fed66d7f7d4c86`，父提交`7cb8ff1c61a5373bb0fd7f8f6de6aaedb41ad666`，`fix: bind g4 to official config source`。收尾审计发现backend已冻结正式配置源，但G4仍把`target_rtl_isa_register_map_version_frozen`机械绑定到尚不存在的完整hardware approval，导致口径不一致；现改为逐项校验backend来源/commit/能力边界、内容寻址审计hash/size及MaxPool/register-map语义后单独判定。
- 验证后该项由false变为true且无失败原因；G4阻塞项从5项减为4项：批准算子物理layout证据、clean elaboration、批准target profile、批准物理layout合同。`g4_status=not_passed`、`w5_authorized=false`保持不变，target config仍明确`can_execute_numerical_model=false`、ResNet覆盖未完成。W4门聚焦4/4、根仓全量199/199通过；精确回退：revert `3407a20c86fcf8ea72add5d115fed66d7f7d4c86`，其父恢复点为`7cb8ff1c61a5373bb0fd7f8f6de6aaedb41ad666`。

## 2026-07-14：W4-28 C4 Pool族三模板配置联动审计完成

- 根仓提交`0518d2fc6e026be70139129eb84fdebb4d9c4946`，父提交`b43c7526620e7adc889710e8779111c6b8880d9b`，`feat: audit rtl28 pool config linkage`；本步骤按操作者要求由主任务单线程完成，只做本地提交，没有推送GitHub。开工前工作树干净，RTL28静态证据与CGRA_SIM、ndp-sim-ref、NDPFuncModel全部匹配lock，根仓基线199/199通过；全程没有读取、复制或重跑约951 MB W3 tensor。
- 根前置校验扩展为Pool共用结构/资源/字段路由：既接受30-bit整数地址，也接受官方模板使用的精确30-bit二进制字符串并强制16-byte对齐；MaxPool GA限定`int8_max`，AvgPool GA限定`int32_sum`。第二个MaxPool和AvgPool原先会被整数地址/固定opcode校验误拒绝，这一审计缺口已关闭；未知字段、错误opcode、畸形地址和17-bit LC溢出均在官方`Bit`静默取模前fail-closed。
- 两个MaxPool模板的全部18个叶差异已逐项归因：16项属于shape/调度联动，2项`stream0/stream1.base_addr`属于memory planner，不是shape公式。当前精确规则只覆盖两个官方非tail样例：`LC0.end=C/4`、`LC1=[0,H) step 2`、`LC2.end=W/16`、`LC3/LC4.end=3`、`LC5=[0,16) step 2`、`LC6.end=Hout`、`LC7.end=Wout/8`；LC-PE形成`row=LC1+LC3`、`col=LC2*16+LC4+LC5`，read/write byte stride分别为`[4,4W,4HW]`和`[4HoutWout,4Wout,32]`。当`W/16`由7缩为1时，A-buffer完成事件从last-index 6整体前移到5，ROW/COL LC、read stream和buffer0同步前移。
- AvgPool静态模板确认`C=2048,H=W=7`时由`LC0.end=C/8`分组，49个空间元素padding到56，read transaction为8×4、byte stride为`[392,8]`、有效范围为包含端点的`[0,48]`；GA输入开启`uint8toint32`，八个PE执行`int32_sum`并输出int32。该模板没有除以49、`x_scale/y_scale` requant、nearest-even或uint8 saturation，因此只批准“uint8输入到int32空间和”的静态链；`round_up(H*W,8)`也仅是一模板候选公式，必须由第二shape验证后才能参数化。
- 三模板由此冻结共用`shape→LC/LC-PE→read/write stream→ROW/COL LC与buffer→GA`五段关系和跨段不变量：stream A/D target与buffer target/destination一致，read stream与buffer0引用同一full事件，buffer/GA保持同一八lane mask，transaction维度按真实长度减一编码，dim stride按byte记录，base address只由统一memory planner分配。MaxPool的UINT8 padding/`int8_max`符号语义和AvgPool的完整requant仍明确未验证。
- 三模板均在`PYTHONHASHSEED=0`、`PYTHONUTF8=1`、seed 42、10000 iterations、10 restarts下两次独立生成完全相同的全部输出，并通过read base+16差分和LC溢出拒绝。128-bit bitstream SHA-256/bytes分别为MaxPool 112：`2e4096f261adb67296116929d94b691b7e27bf3ff2d327a4bb9db8b017900353`/3900，MaxPool 16：`4ff6e89b560d84ef4e1757a6994a1a1980e87d41ec347f7cf6b94c8f19f6bcd1`/3900，AvgPool：`a9c20dc9050cda992c1ca759b4575c12eec33846cb1b33f079158db9f68c73bd`/3120；对应差分hash分别为`a35fd35fbc33fa85a506df733e9c0a012c79d6fd52ee3eb3b888aa144a0d7d36`、`9e7200cd163f551ac0f716e420bd250cf888fc138dfd9e19655c919efcdc9a83`和`d76340833baf06e57f2b5784306b7102f47e45da2d8437445db70fc472557ac9`。
- 权威报告升级为schema 0.2，并修正Windows文本写入为显式UTF-8 LF字节，避免Git归一化使内容hash在fresh checkout后失效。`contracts/target_config_authority_audit.json`重复生成逐字节相同，96,404 bytes、SHA-256 `be45117995208657d97b5589adf8fe05d0ad1c796b84472194ec4a814c56c004`、CRLF计数0；backend合同新增`pool_family_encoder_probe_validated=true`并逐模板绑定确定性/差分/fail-closed、MaxPool差异全解释和数值范围未验证状态。合同集合digest为`976b96771866c6a3118dc3ada9dace061453b1269796bc30438fe98d450ba21d`。
- 验证：配置/合同/G4聚焦33/33通过；根仓最终全量205/205通过，仅保留既有NumPy标量转换DeprecationWarning；`py_compile`、`validate-contracts`、`git diff --check`、报告跨路径重复生成、LF检查和四项lock核验全部通过。G4仍为`not_passed`、`w5_authorized=false`，阻塞项仍是批准算子物理layout证据、clean elaboration、批准target profile和批准物理layout合同；没有生成正式W5网络JSON/bitstream、execplan/Bank_data、目标simulator输出、硬件结果或真实`hardware_approval.json`。
- 当前完成位置：W4-28 C4的Pool族三个正式模板静态配置审计完成，但不等于MaxPool/AvgPool数值或硬件闭环；ResNet配置覆盖仍未完成。下一步建议保持单线程，审计`quant_from_buffer_int32MN_uint8MN.json`和`add_dequant_uint8CWH_uint8CWH_fp32CWH.json`，重点确认GA dtype转换、固定constant、真实ResNet scale/zp和输出dtype的差距；公共GA crosswalk稳定后，再评估是否并行GEMV/MatMul与sum组。禁止生成正式W5实例或把静态bitstream成功写成G4/G5/G6通过。
- 精确回退：revert `0518d2fc6e026be70139129eb84fdebb4d9c4946`；其父恢复点为`b43c7526620e7adc889710e8779111c6b8880d9b`。

## 2026-07-14：W4-28 C5 Quant与Add-Dequant公共GA crosswalk完成

- 根仓提交`cb882328f8a1f67dda73eceea19f0a83df0ea8d7`，父提交`f11a8d59b2f4d44439dff96573adb871961e1cc1`，`feat: audit rtl28 quant and add dequant configs`；本步骤按操作者要求由主任务单线程完成，只做本地提交，没有推送GitHub。开工前工作树干净，RTL28静态证据与CGRA_SIM、ndp-sim-ref、NDPFuncModel全部匹配lock，根仓基线205/205通过；全程没有读取、复制或重跑约951 MB W3 `.npy`，只读取锁定ONNX的scalar initializer和小型W3 model graph。
- `quant_from_buffer_int32MN_uint8MN`的实际链已冻结为`INT32 buffer→int32tofp32→FP32 MAC→raw INT32_SUB→int32touint8→UINT8 D`，并明确不能按文件名直接映射ONNX FP32 `QuantizeLinear`。八个MAC的固定multiplier为0.06375（FP32 bits `0x3d828f5c`）；JSON字面量`12582975.75`编码后为`12582976.0/0x4b400040`，八个SUB减raw `1262485504/0x4b400000`，因此静态样例导出output zero point 64。RTL快照已确认末端负值夹0、任一`[30:8]`位非零夹255，否则取低8位；魔数序列表明nearest-even配方，但没有目标数值执行，保持`recipe_identified_but_not_target_executed`。
- `add_dequant_uint8CWH_uint8CWH_fp32CWH`确认两路输入各自`uint8tofp32`，四组lane执行两支MAC再ADD；当前固定计算是`(A*1+1)+(B*1+1)`，输出FP32，无rounding/saturation。正式FP32反量化和应逐支patch `scale`与`-zero_point*scale`；由于模板不读取`y_scale/y_zero_point`且不输出UINT8，它不是完整QLinearAdd，也不能在没有误差证明时冒充QLinearAdd+Dequantize融合。
- 审计从SHA-256锁定的正式ONNX只读提取2个Quantize、2个Dequantize、17个QLinearAdd的全部scalar qparams；scale范围`[0.0003060092858504504,0.12644046545028687]`、zero point范围`[0,157]`。两个Quantize所需`1/y_scale`为约53.5950和42.8131，output zero point为114和0；静态Quant直连匹配0/2，两个Dequant固定branch匹配0/2，34条QLinearAdd输入branch仿射匹配0/34。正式规则因此冻结为模型initializer→typed qparam→派生constant→八/四lane一致patch→官方编码，禁止把样例constant当默认值。
- AST审计确认正式execplan的Quant handler只写3个LC end和2个stream stride字段，Add-Dequant handler只写5个LC end和3个stream stride字段；两者都不写GA constant，当前`OperatorSpec`也不承载typed qparams/attributes。该缺口已写入backend限制和权威报告，未被静默补0。两个模板均通过结构/资源/字段、两次确定编码、GA constant差分和17-bit LC溢出前置拒绝；Quant/Add-Dequant 128-bit bitstream SHA-256/bytes分别为`85880ee66b853369f67114df32d006873fadf03193d4558e016c707ed9da04cf`/4420与`3f350bbc2d8be73237af594466bb0473026a5b4f829cfe1c0766fa7d96c0e0a3`/4680，constant差分hash分别为`bc0d52a32f6331945f9b00d4a711482a9c89f656cf82e585343494244619dea0`与`0fca3891bccc8e77f8995675a0f197e10ee56264f55655a28f51d5a2bece3303`。
- 权威报告升级为schema 0.3，重复生成逐字节相同，133,659 bytes、SHA-256 `6f303218d166117a84cde44afdce0ab6993d672c8f776e8c4cfe47d77d7d495d`、CRLF计数0；backend新增`ga_quant_add_dequant_probe_validated=true`并显式保留target numerical simulator、硬件执行、rounding动态确认、完整QLinearAdd requant和execplan qparam binding缺失。合同集合digest为`f5d202e5d4116cf2e3d632e1a02d56cdc6839f05fa1ef9785cd77ca6378d2142`。
- 验证：配置/合同/G4聚焦40/40通过，根仓最终全量212/212通过，仅保留既有NumPy标量转换DeprecationWarning；`py_compile`、`validate-contracts`、`git diff --check`、报告跨路径重复生成、LF检查和四项lock核验全部通过。G4仍为`not_passed`、`w5_authorized=false`，阻塞项保持批准算子物理layout证据、clean elaboration、批准target profile和批准物理layout合同；没有生成正式W5网络JSON/bitstream、execplan/Bank_data、目标simulator输出、硬件结果或真实`hardware_approval.json`。
- 当前完成位置：W4-28 C5公共GA crosswalk完成，配置来源、字段、constant编码和qparam注入位置已静态闭环，但Quant目标rounding执行、Add-Dequant完整QLinearAdd语义及execplan typed qparam transport仍未闭环。下一步建议进入C6：GEMV/MatMul和sum组主要文件与测试边界可隔离，适合两个共享Local并行子任务；公共crosswalk、合同/backend、权威报告、`.agents`、Git和最终集成仍由主任务单线程持有。两组都只做临时审计，不生成正式W5实例或宣称G4/G5/G6通过。
- 精确回退：先revert后续history提交，再revert `cb882328f8a1f67dda73eceea19f0a83df0ea8d7`；其父恢复点为`f11a8d59b2f4d44439dff96573adb871961e1cc1`。

## 2026-07-14：W4-28 C6 GEMV/MatMul与sum族配置审计完成

- 根仓提交`5048b703b97012cfe36a05b3a8fe32aa6ead6f59`，父提交`41caff5c2097f8b7370170ebf32b61fbff38de39`，`feat: audit rtl28 matmul and sum configs`；按操作者授权使用两个共享Local子任务并行，GEMV/MatMul组只新增`matmul_config_audit.py`及其测试，sum组只新增`sum_config_audit.py`及其测试。公共crosswalk、backend、权威报告、`.agents`、Git与最终集成均由主任务单线程完成；只做本地提交，没有推送GitHub。
- GEMV/MatMul组盘点正式配置源中的6个SA模板（3个GEMM、3个GEMV）和5个execplan handler。6/6均为FP16且`bias_enable=0`；两个decode GEMV经buffer5进入GA `sum`并转成FP16 D，其余由SA直接写D。5个handler的docstring全部明示`Placeholder`，只有`prefill_gemm_local`和`prefill_gemm_ring_4slice`登记在`operator_base_info`，主`gemv_config_local_M1N128K32`没有handler。ResNet dense的`M/N/K=16/1000/2048`套入现有local GEMM整块公式会得到`M//32=0`和N余8；现有链没有INT8 SA/INT32 accumulator合同、双输入zero-point correction、typed a/b/y qparams、外部INT32 psum首/中/末K生命周期、tail或UINT8 requant。模型dense bias位于后继QLinearAdd，不能据静态`bias_enable=0`反推硬件融合能力；ring模板只证明SA操作数N2N，不证明跨sliceINT32 psum归约。
- sum组盘点11个模板：1个local sum、4个remote sum、4个summac和2个sum-rec。所有remote名称模板都没有N2N、GA neighbor或neighbor buffer，只能证明对已提前放入A流的数据求和，不能证明跨slice传输。归约PE `transout_last_index=1`、输入full事件2、输入列结束3、输出full/行结束3、输出列结束4只形成静态引用链，不等于硬件完成协议。`summac`是mul结果两路进入summac形成平方累加，面向RMSNorm；`sum-rec`是sum后接REC/SFU，面向softmax，均不是GAP除法/requant。
- `sum_config_32_32`是唯一共享/ResNet候选sum模板，但只到假定FP32 local sum，无base-info、无handler、无除法、qparams或UINT8 requant。10个命名sum模板有handler，但decode四模板没有base-info，所有handler都不使用D维度约束更新、不patch输出stream/buffer几何或requant。`prefill_remote_sum_4slice_fp16MN_fp32MN`的base-info声明A/B/D均为`[1,32,16]`，与JSON只流A/D以及4→1归约意图冲突，现已作为fail-closed阻塞登记。
- 主任务把两组候选审计合入`contracts/target_config_authority_audit.json` schema 0.4。代表GEMV完成两次确定编码、base-address差分和17-bit溢出拒绝；全部11个sum模板均在`TemporaryDirectory`、`PYTHONHASHSEED=0`、`PYTHONUTF8=1`、seed 42下各编码两次且逐文件一致。编码只证明配置编码和零违规placement，不证明数值、跨slice通信或硬件完成语义。报告重复完整生成逐字节相同，240,582 bytes、SHA-256 `b81436245886aaca2c6e2ab26f52d6c70810daa18c835cb6f08ce683f4ffa8d3`、CRLF计数0。
- backend新增`matmul_gemv_config_probe_validated=true`与`sum_family_config_probe_validated=true`，同时新增INT8 MatMul/psum/requant/tail缺失、sum跨slice/完成协议未证实和metadata冲突限制；`resnet50_operator_coverage_complete=false`、`can_execute_numerical_model=false`、target simulator/hardware未批准保持不变。合同集合digest为`f2dff200cfa0f1c46f024df377d028c3194df414a3864f5f63c197e50ff9f6e7`。
- 验证：两组聚焦15/15、配置/合同/G4联合55/55、根仓全量228/228通过，仅保留既有NumPy标量转换DeprecationWarning；`py_compile`、`git diff --check`、报告跨路径重复生成、LF检查和四项lock核验全部通过。曾尝试调用仓库中不存在的`tools/validate_contracts.py`，只得到“文件不存在”且没有写入；实际合同加载、hash/size/语义校验由`load_contracts`、合同测试和G4审计通过。
- 当前完成位置：W4-28 C6完成，公共报告只批准候选preflight记录，`numerical_status=not_validated`、`no_gate_authority=true`。G4仍为`not_passed`、`w5_authorized=false`，阻塞项仍是批准算子物理layout证据、clean elaboration、批准target profile和批准物理layout合同。全程没有读取、复制或重跑约951 MB W3 `.npy`，没有生成正式W5 JSON/bitstream、execplan/Bank_data、目标simulator输出、硬件结果或真实批准合同。
- 下一步建议：单线程进入W4-28 C7，建立W3 `hw_op`/tensor/shape/dtype/qparams到正式配置字段的typed参数合同、字段provenance和严格失败测试；只定义可派生、需外部批准和必须拒绝的参数映射，不复制静态样例constant，不生成patched JSON、bitstream或execplan。外部证据继续并行等待，收到后仍由主任务单线程导入approved合同并重审G4。精确回退：先revert后续history提交，再revert `5048b703b97012cfe36a05b3a8fe32aa6ead6f59`；其父恢复点为`41caff5c2097f8b7370170ebf32b61fbff38de39`。

## 2026-07-14：W4-28 C7 typed配置参数合同完成

- 根仓提交`911cb98a8d4b42fad3e6993363eaa99308311850`，父提交`6f5df92b13d6fce69413fbab9d4e3f9c148ee8b3`，`feat: bind rtl28 typed config parameters`；本步骤按计划由主任务单线程完成，只做本地提交，没有推送GitHub。开工与收尾时根工作树均无无关改动，RTL28静态证据、CGRA_SIM、ndp-sim-ref和NDPFuncModel四项均匹配lock。
- 新增`resnet50_pipeline/typed_config_parameters.py`和`tools/build_typed_config_parameter_contract.py`。构建器先用SHA-256锁定正式ONNX，再证明重建的78节点/617 tensor图与`artifacts/w3/model_graph.json`完全相同，证明batch16 runtime manifest覆盖1个输入+78个节点输出、subop manifest覆盖55个lowering内部INT32 tensor，最后绑定全部133个语义`hw_op`。全程只读取25 MB ONNX、约340 KB model graph和两个约170/50 KB manifest，不调用`numpy.load`，没有读取、复制或重跑约951 MB W3 `.npy`。
- `contracts/typed_config_parameter_contract.json`保存491个按`hw_op`分阶段消费的initializer参数引用，其中438个scale/zero-point和53个Conv bias；159个per-channel原始参数保留原始shape、axis=0、元素数、精确字节SHA-256和最小/最大值，scalar float32同时保存数值与原始bits。53个Conv per-channel requant multiplier、Quant reciprocal scale、Add/Dequant affine offset、GAP空间计数/倍率和MatMul requant倍率等94个参数按W3 QNN同一float32/int32公式派生，不复制任何静态样例constant。
- 757个字段绑定按证据逐项分为359个`derived`、135个`approval_required`和263个`rejected`。`derived`只表示模型事实或公式可确定；三态全部强制`formal_target_write_allowed=false`，全部133个`formal_target_instance_allowed=false`。18类阻塞显式覆盖批准layout、execplan typed transport、Quant FP32输入/rounding、Conv INT8 SA/bias/psum、MaxPool shape泛化/UINT8语义、QLinearAdd输出requant、GAP centered sum/除法requant、sum跨slice/完成协议、MatMul INT8/tail/psum/requant和独立Dequant模板；缺一项都不能生成正式配置。
- backend新增C7合同的path/size/SHA-256和`typed_config_parameter_contract_validated=true`，合同加载器同时检查内容hash、schema语义、三态fail-closed约束及其所绑定的C6配置权威报告hash。G4审计也执行同一校验；C7合同被删除、修改、丢失per-channel axis、减少133 `hw_op`覆盖或把任一参数/字段改成允许target write时均明确失败。报告从不同当前目录重建以及在临时路径重建均逐字节相同，最终为1,619,185 bytes、SHA-256 `abbc87b0b13c92611a90fe1767b32b15fe9c49f23bee616ca2bb51219dd181bd`、CRLF计数0；合同集合digest为`5368c1f54b2071b24f3d4174cf6b627591c6c99eb06336c225ce664d5ab894ff`。
- 验证：C7/合同/G4聚焦33/33通过，根仓最终全量237/237通过；只保留既有NumPy标量转换DeprecationWarning。`py_compile`、`validate-contracts`、`git diff --check`、合同跨路径逐字节重生成、LF检查和四项lock核验全部通过。G4仍为`not_passed`、`w5_authorized=false`；当前四个门阻塞保持批准算子物理layout证据、clean elaboration、批准target profile和批准物理layout合同。没有生成patched JSON、bitstream、execplan/Bank_data、目标simulator输出、硬件结果或真实`hardware_approval.json`。
- 当前完成位置：W4-28 C7完成。模型的shape/dtype/qparams和公式层已经能逐`hw_op`精确追溯，过去“静态样例constant会不会被误当成ResNet参数”以及“per-channel qparams会不会静默丢失”已有机器校验；但这不等于正式寄存器字段、数值执行或硬件layout获批。
- 下一步建议：若硬件批准资料尚未到达，单线程进入C8，只基于C3的93条runtime边/91条qparam链和C7精确参数身份做整网量化域连续性审计，显式处理QLinearAdd双分支、MaxPool/View透明传递和GAP/MatMul head，并把实例级阻塞归并到最小外部批准问题；不猜测寄存器位义、不生成正式W5实例。若批准资料先到，则跳过C8等待，优先单线程导入approved合同、版本检查并重审G4。精确回退：先revert后续history提交，再revert `911cb98a8d4b42fad3e6993363eaa99308311850`；其父恢复点为`6f5df92b13d6fce69413fbab9d4e3f9c148ee8b3`。

## 2026-07-14：W4 DeepSeek基线继承闭环完成，G4通过

- 根仓提交`952a96b48416ed2ea1bd2d3068a541ab3dd43625`，父提交`c7eccc5a664d52f8f00695b7427e673b22743f3c`，`feat: close W4 with DeepSeek RTL28 baseline`；按操作者要求由主任务单线程完成，只做本地提交，没有推送GitHub。全程没有读取、复制或重跑约951 MB W3 `.npy`，只使用小型W3图目录和既有W4审计接口重生成两份内容寻址证据。
- 新增正式整网profile`w4_deepseek_hybrid28_resnet50_v1`：每个网络算子使用全28-bit mask，同时覆盖七个HIGH组；`local/HIGH-4/LOW-28`只表示算子通信域，不再强迫全网group/global二选一。七族绑定为simple/local、view/local、conv/HIGH-4、maxpool/local、add/local、GAP/local、matmul/HIGH-4；当前没有LOW-28族，七个LOW布局实现继续保留为gate-ineligible替代证据。
- ADR-009以权威标识`resnet50_int8_project_operator`记录操作者对已完成DeepSeek整网硬件基线正确性的确认，SHA-256为`bb17837e6878ab9f78676870c46e10ad73f495540b8a21ce984fbb85c00063a1`。合同明确`elaboration_log_claimed=false`，没有伪造工具、版本、日志或hash；原clean-elaboration前置被改为具名已知可用基线，W5数值、W6目标simulator、W7地址规划和W8板级协议继续独立验收。
- 新增`contracts/deepseek_rtl28_physical_baseline.json`与`contracts/resnet50_rtl28_w4_delta.json`，SHA-256分别为`8dbbb440e782e9c43d6e9bb954f93eea74b43406ecd7846124bc39bc46ff6c64`和`cd7a3483f515f2d12c7b8d5dddbef38fc5495c21606b378250a1ff2f0b2efe6f`；schema 0.3批准合同SHA-256为`963b64087351a45d54f52a86fe3536804e4f24427c94ee912c521b3a93fe159b`。validator逐层校验ADR、两合同及其原始本地证据hash，合成fixture仍只能验证结构，不能取得G4权威资格。
- architecture把七个选中group4x7布局登记为W4 approved，把七个LOW-28替代设为current-gate-ineligible；backend只登记`w4_physical_baseline_approved=true`，仍保持target hardware runtime `approved=false`。93边和成本报告按architecture basis `52942e2b42236bbb265244beb271a744a5bdfa00e605a4310f5ad93a54f768be`重生成并纳入Git，报告hash分别为`73f1e4892d7fbc36c9baa8d84e1fb4e15773a4b9d02c7192364477fb56da265d`和`587a302b4f79f744386fb451528d0c2edea8283fbac19c28bf11c332d4daa7f1`。
- 提交前完成方案切换旧口径复审：修正小环只开4-bit mask的错误规则；ADR-003～008、批准请求包、`agent.md`和`plan.md`均标出历史状态或ADR-009覆盖关系；没有删除旧16或LOW比较证据，也没有把旧成本场景冒充正式profile。`git diff --check`通过，未加入W3大文件或其他无关改动。
- 验证：根仓全量238/238通过，仅保留既有NumPy标量转换DeprecationWarning；审批/合同/G4/W0聚焦40/40通过；`validate-contracts`有效，合同集合digest为`c41d9c0abbb5299d61a14d93c08de949b2ea935fd5a0e38e5dbab3f33655fac9`；RTL28静态证据与CGRA_SIM、ndp-sim-ref、NDPFuncModel四项匹配lock。G4 v2的12/12条件全部为true，阻塞列表为空，`g4_status=passed`、`w5_authorized=true`，同时`clean_elaboration_claimed=false`。
- 当前完成位置：W4正式结束，G4通过；已批准的是DeepSeek公共物理载体和ResNet W4布局差异，不是INT8数值、目标simulator或板级结果。下一步建议单线程进入W5最小真实INT8 Conv模板：只选一个真实`hw_op_id`，绑定C7真实activation/weight/bias/qparams，补SA/stream/buffer、INT32 psum、requant、padding/tail和溢出拒绝，要求固定seed的JSON/bitstream逐字节复现与字段provenance完整；不得直接生成整网W5或宣称G5/G6/硬件三方通过。
- 精确回退：先revert本history提交，再revert`952a96b48416ed2ea1bd2d3068a541ab3dd43625`；其父恢复点为`c7eccc5a664d52f8f00695b7427e673b22743f3c`。

## 2026-07-14：W4归档与W5新对话交接重写

- 根仓提交`8e91a5258271bf4d8459ed7f0a4f590c2745b493`，父提交`3b5fff4d2007d2acdd7793bc69988b1d6f98be40`，`docs: prepare W5 handoff and archive W4`；本步骤只整理`.agents`交接与历史边界，没有开始W5实现、生成JSON/bitstream或读取/重跑约951 MB W3 `.npy`。
- 完整读取并审阅当时`.agents`下13个既有说明文件，补读按`Get-Content.Count`确认的`agent.md`、`plan.md`后半部；新增`.agents/W5_HANDOFF.md`作为新对话第一入口，新增`.agents/W4_ARCHIVE.md`作为本W4对话的错误追溯索引。`history.md`继续保存逐时事实，旧条目中的“G4未通过”“等待clean elaboration”“下一步C8”不再被解释为当前任务。
- 修正活动文档中的方案漂移：`agent.md`不再把W4写成C8待办或把28-slice layout/inverse比较器写成未实现；`plan.md`把W1未闭合项分流到W5/W6/W7/W8，并把首个W5包改为“先定位DeepSeek真实JSON/bitstream数值执行入口，再做一个真实1×1 Conv配置与golden比较”；算子规则不再限制为临时W4审计；ADR-006～008明确区分采用时历史和ADR-009后的当前状态。
- 新交接冻结首包为单线程：优先`hwop-0004-00`或经审查更合适的简单真实1×1/stride1 Conv tile，绑定C7真实weight/bias/per-channel qparams；JSON/bitstream确定性属于G5，使用同一physical输入运行目标模拟器并让logical INT32 P/UINT8 D与W3 golden bit-exact属于G6。找不到真正执行目标配置的模拟器时停止横向扩展，不以`NDPFuncModel`、bundle生成或编码成功替代数值验收。
- 验证：`git diff --check`通过；ADR-009 SHA-256保持`bb17837e6878ab9f78676870c46e10ad73f495540b8a21ce984fbb85c00063a1`并与`hardware_approval.json`引用一致；RTL28证据和CGRA_SIM、ndp-sim-ref、NDPFuncModel四项全部匹配lock；合同digest保持`c41d9c0abbb5299d61a14d93c08de949b2ea935fd5a0e38e5dbab3f33655fac9`；G4为12/12、阻塞0、`w5_authorized=true`、`clean_elaboration_claimed=false`；根仓全量238/238通过。
- 当前完成位置：W4归档与新对话交接完成，W4/G4状态未改变，W5尚未开始。下一步建议在新对话读取`W5_HANDOFF.md`并执行其中三条无副作用检查，然后按首个真实Conv纵向闭环继续；本W4对话只用于后续追溯W4错误。
- 精确回退：revert `8e91a5258271bf4d8459ed7f0a4f590c2745b493`；上一恢复点为`3b5fff4d2007d2acdd7793bc69988b1d6f98be40`。该回退只撤销交接文档重写，不撤销W4业务闭环`952a96b...`或任何机器合同。

## 2026-07-14：W5首个真实1×1 Conv preflight与target simulator入口阻塞登记

- 根仓提交`7ba768eea85e6bbaacbd25d554c3ab2322a078d5`，父提交`2b09c9400803be12fbfe9398376153c94a1a5510`，`feat: preflight first real W5 conv`；本步骤严格按交接要求由主任务单线程完成，只做本地提交，没有推送GitHub。开工前三条无副作用检查全部通过：根工作树clean；RTL28静态证据及CGRA_SIM、ndp-sim-ref、NDPFuncModel全部匹配lock；接手基线全量238/238通过。
- DeepSeek实际链路定位到明确边界：`model_execplan/main.py -e`只调用`write_emulator_bundle()`，为每个slice输出patched算子JSON和`dram_data.bin`；`run_all_slices.py`只调用`bitstream/main.py`生成码流。锁定`ndp-sim-ref@e299b2804448242d1589b3e58ed7c5a9a5eca09f`内没有读取`dram_data.bin`并执行LC/stream/buffer/SA/GA的runner，本机`Get-Command *emulator*,*simulator*`也无结果。因此可运行target命令、模拟器版本、输入包合同、退出码及physical D格式均不可取得，登记`B_TARGET_SIMULATOR_ENTRY`，不能把bundle打包或NDP functional adapter称为目标模拟执行。
- 正式配置源42个JSON中具名Conv模板数为0。进一步审查`config_generator_ver2.py/config_nse.py`确认其只提供旧硬编码提示：共享参数固定`SLICE_NUM=16`，SA虽有INT8 selector 0，但`sa_pe_bias_enable=0`，没有typed zero-point/scale/requant通道，也没有nonzero bias、首/中/末K持久INT32 psum、nearest-even UINT8写回语义。该证据被标为`legacy16_reference_only`，不能据此猜测28-slice target字段或生成bitstream。
- 首例按交接推荐固定为正式`node-0004`、`hwop-0004-00` accumulate和`hwop-0004-01` requantize：1×1、stride 1、`[16,64,56,56]→[16,64,56,56]`。新`w5_conv_preflight.py`逐字节验证正式ONNX、W3 runtime/subop manifest、C7 typed合同与W4批准合同，加载真实UINT8 A、INT8 B、INT32 bias/P、per-channel weight scale/zero-point、scalar x/y qparams和UINT8 D；所有11个端口保存tensor ID、shape/dtype、payload hash与来源，per-channel multiplier保持float32精确hash。
- 第一物理tile选择group0、destination slice0、N0～2、K0～15、H/W全56，HIGH环owner为`[0,2,3,1]`，按`[0,1,3,2]`遍历四个16-channel reduction段。每段记录first/middle/middle/last、bias初始化、INT32 psum persist/requant边界、范围和hash；独立整数重算150,528个P与W3 `ConvInt32Accumulate`全部bit-exact，per-channel float32 multiplier+nearest-even+UINT8 saturation重算150,528个D也全部bit-exact。W4 inverse/forward布局的physical P/D字节分别从`0x000250d0`和`0x000b80d0`开始，与logical golden转换后的NHWK-local字节完全一致。
- 新CLI `tools/run_w5_conv_preflight.py`生成18,232-byte证据`artifacts/w5/hwop-0004-00/preflight.json`，SHA-256为`d4a900bb521e3ab6f6e64ba6d240a2241fad55b1fbd597eccc6c01051317b49a`；跨两次运行hash完全一致。报告与validator强制`status=g5_preflight_blocked_before_target_json`、`patched_json_generated=false`、`bitstream_generated=false`、`mapping_review_generated=false`、`G5/G6/G8=false`和`stop_expansion=true`；任何把target JSON或G6改成已完成的篡改测试都会失败。
- 验证：新增W5测试5/5通过，根仓最终全量243/243通过，仅保留既有NumPy标量转换DeprecationWarning；`validate-contracts` digest保持`c41d9c0abbb5299d61a14d93c08de949b2ea935fd5a0e38e5dbab3f33655fac9`；四项lock复核通过；两次报告重生成hash一致；工作树与暂存区`diff --check`通过。没有生成任何target JSON/bitstream、mapping review、execplan/Bank_data、target simulator输出、硬件结果或整网W5产物。
- 当前完成位置：W5已开始，首个真实1×1 Conv的实例选择、typed参数transport到preflight、W4物理tile、四段golden P/D和字段级provenance已完成；G5配置门因无权威Conv模板/字段合同而阻塞，W6/G6因无target simulator入口而阻塞，门状态没有升级。该阻塞是交接单明确停止条件，不回退W4/G4，也不以候选功能模型替代。
- 下一步建议：保持单线程，只在取得两组权威资料后恢复同一tile：其一为真正消费当前JSON/bitstream的target simulator命令、版本、输入包、退出码和physical D格式；其二为28-slice INT8 Conv的LC/stream/buffer/SA/GA字段与寄存器合同，覆盖nonzero bias、首/中/末K psum、per-channel requant、nearest-even、UINT8 saturation和唯一flush。前置满足后先对这一tile做patched JSON两次编码、decoder round-trip、范围/资源/unknown-field拒绝，再用同一physical bundle跑target simulator并比较P/D；验收前禁止整网W5、W7 execplan或G5/G6/G8通过声明。
- 精确回退：revert `7ba768eea85e6bbaacbd25d554c3ab2322a078d5`；上一恢复点为`2b09c9400803be12fbfe9398376153c94a1a5510`。回退会移除本次preflight代码、测试、小型证据和W5当前计划状态，但不会改变W4/G4批准合同。

## 2026-07-14：学长Conv伪配置正式编码与首个真实1×1坐标模拟闭环

- 根仓提交`77da6446fc83e86779d2105b60805afdedae40b4`，父提交`3e73c98491bec8b5aca967b6139b00d4d76d4731`，`feat: encode conv candidate and bind simulator`；本步骤按操作者要求由主任务单线程完成，只做本地提交，没有推送。操作者放入的`.agents/conv_full(2).json/.txt`作为原始只读副本保持未修改、未提交；根目录工作副本纳入版本控制。
- 完整复审`agent.md`的三仓职责后修正旧边界：`ndp-sim-ref@e299b280...`仍是正式28-slice JSON/bitstream/execplan来源，`CGRA_SIM`仍给QNN软件语义；按操作者确认，`NDPFuncModel/conv_func@35eab40`登记为Conv数值模拟器组件。其可运行入口为`NDPFuncModel/tools/physical_image_probe.py`，但不消费ndp-sim target JSON/bitstream，因此旧`B_TARGET_SIMULATOR_ENTRY`解除并替换为`B_CONV_SIMULATOR_CONFIG_ADAPTER`，没有把组件身份确认误写为G6通过。
- 学长原始`conv_full.json`与TXT先暴露三处确定性转录错误：`LC_PE.LC8`改为`DRAM_LC.LC8`，GROUP2/3 COL各自改连本组ROW。正式encoder随后证明原共享LC同时扇出到固定A/C、A/D远端端点，拓扑约束不可同时满足；利用20个LC中空闲资源，新增LC13～15复制`k'/q/p'`链并拆分远端消费者。最终布局使用16/20 LC、7/10 LC-PE、46条连接，正式heuristic mapper重新计算约束代价为0。
- 新增`contracts/conv_full_encoder_evidence.json`和`tools/run_conv_full_encoder.py`。runner按连接图算出cache key `9cdaec339a4e2f01`，把锁定布局写入encoder自带ignored mapping cache，再由正式`bitstream/main.py`验证缓存代价、输出mapping review并生成bitstream。实际命令exit 0；`mapping_review.json`记录46连接，64-bit dump SHA-256 `5171dc60449a4619730c4a8bb8fcb0bead9282b2657d078f2055f1f0f761581f`，128-bit dump SHA-256 `f6991ad5e1da9cc627cf4b16ebd1550d2d9055a1977d5fb519a20fb02983af8c`，parsed bitstream SHA-256 `e9a668056af903923da573d8c218b1aaa5353f3f2eeb416f41d5fd0ed8b21aa1`。生成物可重建而未纳入提交；证据合同SHA-256为`87cc20cef462ec9becadf38c7399e9c4a9ec7e09a71eec10c2474f82f564bee5`。
- 正式encoder detailed dump证明`special_array.data_type=int8`编码`00`、`bias_enable=1`编码`1`，字段、位宽、资源和连接均可接受；因此`B_CONV_TEMPLATE_ABSENT`、`B_CONV_INT8_SA`和placement阻塞解除。但TXT/JSON仍有数值语义冲突：TXT的LC0名字/range自相矛盾，多处LC end/stride与JSON不同，TXT引用PE0～PE7而JSON只有PE0～PE6，且JSON若干`mul`不会执行TXT表达式中的第三项加法。编码成功只证明可编码，不能批准3×3或真实1×1数值。
- `NdpRtl28FunctionalAdapter`新增有界坐标执行接口，只拷贝所需真实RTL28 A/B/D region，不为全输出构造数百万probe。正式`hwop-0004-00`的真实1×1坐标`(0,0,0,0)`按HIGH-4 source顺序`[0,1,3,2]`经过DRAM→input Buffer→SpecialPEA→ActivationUnit→output Buffer→DRAM；四段partial accumulator为`20545,14714,7308,1225`，最终INT32 P=1225、UINT8 D=4、inverse physical D=4，均与W3 golden bit-exact。
- W5报告升级为schema 0.2，状态`g5_candidate_encoded_real_1x1_config_adapter_blocked`；报告24,865 bytes、SHA-256 `d369b96ec80e714558f48305ecb717ce469d747d0168c5edc608d5f9cd899194`。合同把Conv simulator身份与config adapter状态分开，保留`approved=false`、`g6_ready=false`。当前精确阻塞集合为`B_CONV_CANDIDATE_SHAPE_LOWERING`、`B_CONV_SIMULATOR_CONFIG_ADAPTER`、`B_CONV_SA_PSUM_BINDING`、`B_REQUANT_TARGET_NUMERICS`和`B_EXECPLAN_TYPED_TRANSPORT`。
- 验证：正式encoder runner复跑exit 0且全部锁定输出hash相同；W5/NDP/合同聚焦31/31通过；根仓全量244/244通过，仅保留既有NumPy标量转换DeprecationWarning；`validate-contracts` digest为`98db6de149d23b502098795362c1515d847fdcc878a74250b39f6a9c1534d8ae`；`py_compile`和`git diff --check`通过。提交后仅剩操作者原始`.agents/conv_full(2).*`两份untracked副本，没有修改三个参考仓的tracked源码。
- 当前完成位置：W5/G5部分完成。候选Conv的正式parse、零违规placement、INT8/bias bitstream和一个真实1×1 NDPFuncModel坐标P/D闭环已经完成；模拟器入口、Conv模板缺失、INT8字段和布局阻塞已解除。真实1×1 target JSON尚未生成，同一target配置尚未驱动NDPFuncModel，完整tile/整算子的target simulator比较未开始，所以G5/G6保持未通过，W7/W8未开始。
- 下一步建议：继续单线程做一个最小原子包——先把TXT、JSON和register-map整理成逐LC/PE/stream唯一语义表，逐项裁决`k'/q/p'/C/R/S`循环、PE0～PE7算式、stream维序和tail；任何不能唯一裁决的项列为向学长确认的问题。语义表无冲突后才派生`hwop-0004-00`真实1×1 JSON并再次要求正式encoder零违规/稳定bitstream；随后实现该JSON/bitstream到NDPFuncModel request的adapter并比较同一坐标、首tile、全算子P/D。验收前禁止整网W5、execplan扩展或G5/G6/G8通过声明。
- 精确回退：revert后续history提交后，再revert`77da6446fc83e86779d2105b60805afdedae40b4`；其父恢复点为`3e73c98491bec8b5aca967b6139b00d4d76d4731`。运行时encoder mapping cache和`artifacts/w5/conv_full_audit/accepted`均为可再生产物，可直接忽略，不需修改锁定参考仓。

## 2026-07-14：首个真实1×1 Conv配置绑定与全算子P/D候选闭环

- 根仓业务提交`f4e0c1fba567fee672d3b5aafa20873b1054359c`，父提交`b5a2f34ee0030e6c21c9430687fb98b06ceefceb`，`feat: close config-bound real 1x1 conv`；NDPFuncModel提交`e4454f7e12aa38ca94af07e017ae0928b9c839eb`，父提交`35eab40e5314bf603481dd6268bc96ab2ca514a6`，`feat: execute config-bound 1x1 conv request`。全过程按操作者要求单线程完成，只做本地提交，没有推送。操作者提供的`.agents/conv_full(2).json/.txt`原始副本保持未修改、未提交。
- 新增`contracts/conv_1x1_lc_pe_stream_semantics.{json,md}`，从学长伪代码、修复后的`conv_full.json`、正式consumer/register定义和实际encoder结果建立逐16个LC、7个LC-PE、4个stream及N2N语义合同。裁决包括：伪代码顶层`q/k'`名称与range互换；1×1的R/S循环均为`[0,1)`；PE2为`q+s`；输出`p_inner`乘8；PE4/5/6均使用`mac`；最终K使用复制后的LC13；activation/output stream分别采用`[c,w,h]`与`[k,q,p]`维序；target端口`A/B/C/D`分别对应项目weight/activation/bias/INT32 P；UINT8 D由后续ActivationUnit候选产生。规则文件新增第14节，使新实测证据覆盖此前仅从DeepSeek模板概括的旧规则。
- `tools/generate_conv_1x1_real.py`从`conv_full.json`确定性生成`conv_1x1_real.json`，配置SHA-256为`e3e985c8a06e2ff2c672c4a96c04055ebf6c835836c0e589cc265e72cc236037`，语义合同SHA-256为`ab6107ffc3b0379bd97c2e8b61db382d9c747737750b03c186cb28ffa9cac13c`。正式`ndp-sim-ref@e299b280...`两次parser/placement/bitstream重建均为46条连接、constraint cost 0、mapping cache key `66245288c5ee2398`；128-bit dump SHA-256 `074a0787ae774f9cfaf45df158cb8b7b6c02e0920b8199ed5e4864fea3d33744`，64-bit dump SHA-256 `3d5c677437175042fde9e4726b44ce4ecba8e6e20ded5a8f0f267c5548db7e83`，parsed bitstream SHA-256 `17441e46e9d6c20adb9c340a8bbb7d4339f9ed3de5c9a4194d39b41916e9cc2a`。这证明字段、位宽、资源、连接、placement和编码确定性，不等于数值或RTL逐周期证明。
- NDP physical request升级为schema 0.2，传入target JSON和语义合同的原文及SHA-256；`physical_image_probe.py`在计算前逐项核验16个loop range、7个PE source/constant/`mac`、4个stream target/idx/size/stride、INT8+bias SA和N2N `mem_loop=4`。任何配置或合同漂移均在执行前失败。单坐标继续使用DRAM→Buffer→SpecialPEA→ActivationUnit→Buffer→DRAM组件路径；首tile和全算子使用明确标注的`physical_dram_bulk_int8_equivalent`路径，从28-slice physical DRAM重组七个HIGH组的UINT8 activation、INT8 weight、INT32 bias和qparams，执行INT32 1×1矩阵等价计算、ActivationUnit requant及physical P/D writeback。
- 三档比较都使用同一真实`node-0004`/`hwop-0004-00~01`、同一W4 physical bundle和W3 golden。单坐标范围`N0/K0/H0/W0`，P/D各1元素，mismatch均0；首tile范围`N[0,3)×K[0,16)×H[0,56)×W[0,56)`，P/D各150,528元素，mismatch均0；全算子范围`N[0,16)×K[0,64)×H[0,56)×W[0,56)`，P/D各3,211,264元素，mismatch均0。全算子P SHA-256 `1ec864892d82279beff561927500f55ebec636daf2fb7c624a1e153dd5e17532`，D SHA-256 `2793bbe64e2b3289657f1c77bad61ebc54a4672791093d5c19a66ca742e7376e`，与W3 golden逐字节相同。
- 最终报告`artifacts/w5/hwop-0004-00/preflight.json`为30,411 bytes、SHA-256 `b4efdcc45c4110e1a463f9544dce51aa2f05a7ae2cef5d569a0b4b57f1bbfb35`，状态`w5_real_1x1_encoded_config_bound_pd_passed`。门状态仍强制`g5_passed=false`、`g6_passed=false`、`g8_passed=false`、`stop_expansion=true`；保留`B_CONV_TARGET_EXECUTION_SEMANTICS`、`B_N2N_TARGET_SELECTOR`、`B_REQUANT_TARGET_NUMERICS`和`B_EXECPLAN_TYPED_TRANSPORT`。其中bulk比较是物理DRAM等价kernel，不是逐LC/stream/buffer或bitstream解释，不能据此宣称cycle-accurate target simulator或硬件通过。
- 验证：NDPFuncModel 14/14、根仓245/245通过，仅保留既有NumPy标量转换DeprecationWarning；`py_compile`、正式encoder runner、`validate-contracts`、`git diff --check`和四仓lock核验全部通过。合同digest为`cc1bfd7a05c4be53a026771ebfb3bd4aa65b6d5ee610132294c2baacec6d0b19`，NDPFuncModel lock已更新到`e4454f7...`。
- 当前完成位置：真实1×1的伪代码裁决、JSON生成、正式编码、config→request绑定和单坐标/首tile/全算子P/D候选闭环完成；解除shape lowering、config adapter和候选SA psum binding阻塞，但G5/G6未批准。下一步建议继续单线程，仅在同一实例上确认active RTL28 N2N selector、硬件requant/末次reduction/唯一flush，并把等价kernel升级成逐LC/stream/buffer或bitstream执行；新路径三档P/D仍bit-exact且重复稳定后再评估G5/G6。禁止先扩53层Conv、整网execplan或硬件三方声明。
- 精确回退：先revert本history/plan文档提交，再revert根仓`f4e0c1fba567fee672d3b5aafa20873b1054359c`；NDPFuncModel单独revert`e4454f7e12aa38ca94af07e017ae0928b9c839eb`可恢复到`35eab40e5314bf603481dd6268bc96ab2ca514a6`。运行时encoder mapping cache和rebuild artifacts均为可再生产物，不需纳入回退。

## 2026-07-14：DeepSeek JSON硬件执行能力确认与W5阻塞收敛

- 操作者明确确认先前DeepSeek算子JSON可由目标硬件执行，并决定暂不要求本次新1×1候选直接驱动硬件仿真。backend因此把target hardware改为`operator_confirmed_deepseek_json_execution_runtime_interface_deferred`：`implementation_available=true`、`deepseek_json_execution_confirmed=true`，同时保持`approved=false`、项目load/start/wait/dump接口不可用和精确新候选验证`deferred_by_operator`。原`B_CONV_TARGET_EXECUTION_SEMANTICS`从未解决列表移入`operator_confirmed_platform_capability`，不再作为当前配置前置，也不冒充新候选硬件P/D通过。
- 新增fail-closed N2N静态交叉检查。当前`conv_1x1_real.json`为`mem_loop=4, src/dst selector=0, ping_pong=0`；已知可执行`prefill_gemm_ring_4slice.json`为`mem_loop=4, selector=1`，`decode_gemv_ring.json`为`mem_loop=28, selector=0`。正式register map写明selector 1表示jump-4，execplan control同样在slice ratio不等于28时写1。因此`B_N2N_TARGET_SELECTOR`不但保留，而且收敛为候选0与可执行HIGH-4参考1的明确冲突；`ping_pong`仍按Conv数据流单独裁决，未被机械修改。
- W5未解决集合由四项收敛为三项：`B_N2N_TARGET_SELECTOR`；`B_REQUANT_TARGET_NUMERICS`，其含义已收窄为复用可执行DeepSeek Quant路径后仍缺真实64-channel multiplier/qparams、末次reduction与唯一UINT8 flush；`B_EXECPLAN_TYPED_TRANSPORT`，仍缺manifest→OperatorSpec/control/JSON的typed参数写入。精确新JSON硬件运行和dump是延期最终确认，不属于当前配置阻塞。
- 报告升级为schema 0.4并重新完成全算子计算，`artifacts/w5/hwop-0004-00/preflight.json`为32,696 bytes、SHA-256 `90e829457858036a8e6be074813cecbd576ec957398b869f5c04928cbeb3830a`；单坐标、首tile和全算子P/D仍全部零不匹配。更新后的语义合同SHA-256为`ef747ed72f97c64c89487622a03a7013fcb38370ce73e96fa2b67f4bd7d18c54`，配置和bitstream本轮未改；正式encoder重建仍为46连接、cost 0和原五项输出hash。
- 活动`agent.md`、`plan.md`和算子配置规则同步改为三项阻塞；历史W5 handoff和旧history条目继续保留其发生时事实，不反向改写。validator要求resolved former blocker、三项精确集合、候选/可执行HIGH-4/LOW28三个selector tuple和延期硬件边界，任一篡改均失败。
- 验证：根仓246/246通过，仅保留既有NumPy标量转换DeprecationWarning；合同聚焦23/23、`py_compile`、正式1×1 encoder runner、`validate-contracts`、四仓lock和`git diff --check`全部通过。合同digest为`ad2466b1bb5c2b838671910501dd7679c39a81590a714bb29c589b72d0c2553a`。
- 当前完成位置：通用DeepSeek JSON硬件执行能力解除，W5两方P/D闭环保持，剩余真实配置问题从四项变为三项。下一步保持单线程，只改N2N selector并重新正式编码/两方比较；selector闭合后才参数化requant，再接typed execplan。三项完成前不扩53层Conv或整网W5，硬件实跑继续延期。

## 2026-07-15：确认首例真实性并增加全算子扩展前模拟器门

- 根仓计划提交`efb966c9c327e671096e7b1899f59de83d2c891d`，父提交`59ff276747ad65be092a469447f85c45d1d9e95b`，`docs: gate full conv expansion on config runner`；范围仅为`.agents/plan.md`与本历史边界，不修改代码、合同、配置或运行产物。验证为`git diff --check`通过；精确回退使用`git revert efb966c9c327e671096e7b1899f59de83d2c891d`。
- 复核`contracts/typed_config_parameter_contract.json`确认当前首例是锁定ResNet50 INT8 ONNX模型SHA-256 `c234f30975989788b4405f25253275aae247ab6dbdd34aaa69ab0a59ff76f6d0`中的真实`node-0004`，名称`fused resnetv17_stage1_conv0_fwd_quant`、类型`QLinearConv`；lowering为`hwop-0004-00 ConvInt32Accumulate`和`hwop-0004-01 RequantizeUint8`。其`[16,64,56,56]` activation、`[64,64,1,1]` weight、64路INT32 bias、per-channel weight qparams、scalar x/y qparams及P/D golden均来自正式模型和W3产物，不是合成或随机Conv。
- 澄清数值执行边界：旧`NDPFuncModel/main_CONV_N2N.py`仍写死4-slice、3×3 R/S循环、固定shape/`hex_data`和requant，真实1×1未调用该入口。当前根仓adapter通过`python -m tools.physical_image_probe <request.json>`执行；单坐标为地址驱动组件路径，首tile/全算子为`physical_dram_bulk_int8_equivalent`。target JSON/语义合同被校验和绑定，但没有逐LC/stream/buffer/N2N或bitstream解释，因此已有P/D闭环是可靠两方数值证据，不是配置驱动target simulator通过。
- `.agents/plan.md`新增“首个真实Conv到全Conv/全算子扩展前的强制门”：要求参数化旧3×3入口或实现统一runner，使manifest/physical bundle/target JSON实际驱动shape、R/S、地址、N2N、psum和requant；同一入口至少覆盖当前真实1×1和一个正式3×3代表实例，字段变更必须影响执行或fail-closed，P/D必须与W3 bit-exact。该门完成前，单坐标probe和1×1 bulk只作交叉检查，不开放53层Conv或其他算子族横向扩展。
- 本轮仅更新权威计划和历史边界，不修改代码、合同、配置、bitstream、产物或门状态；`B_N2N_TARGET_SELECTOR`、`B_REQUANT_TARGET_NUMERICS`和`B_EXECPLAN_TYPED_TRANSPORT`仍是当前三项配置阻塞。

## 2026-07-15：首个真实1×1 HIGH-4 selector修复包闭合

- 按操作者指定的最小包保持`mem_loop=4`与`ping_pong=0`不变，只把`conv_1x1_real.json`和确定性生成器中的`src_slice_sel/dst_slice_sel`从`0/0`改为`1/1`。新配置SHA-256为`a20641cfcf65068c3ca31d710a0ef45d28a53cbf80d5e246ce54f0de3fe16f2c`。`ping_pong=0`仍明确属于Conv Buffer2邻居接收与stream0双缓冲生命周期的独立裁决，不随selector机械改变。
- `NDPFuncModel`提交`797f099a6b5ef549109eefbafb848c234ce66f73`，父提交`e4454f7e12aa38ca94af07e017ae0928b9c839eb`，`fix: enforce high4 conv selectors`。target-config request现在必须同时满足`mem_loop=4, src_slice_sel=1, dst_slice_sel=1`，旧`4/0/0`组合在任何计算前立即失败；返回binding也显式记录三个字段和独立的`ping_pong`。子仓16/16测试通过。
- 正式`ndp-sim-ref@e299b280...` parser、placement与encoder重复运行成功：parsed dump显示`src=1`、`dst=1`、`ping_pong=0`、`mem_loop=4→00011`，N2N逻辑字段串从`00000011`变为`11000011`。128位bitstream SHA-256变为`2128de615b9b66c8569e3bf3a83f9f6b4ffe4798802ba56be9b21d120e980e6b`，64位变为`baa4d71c8f20f725b572d45386bb855928d020434bbbe55430a979c5f30557df`，parsed dump为`15d16a698c40caa90eaab26fd2c69342e417eba4d6bcf20032715fd09f2eda7d`。mapping review仍为46条连接、constraint cost 0，SHA-256保持`2088dd033e7b92c17bd82b065611015a49ef968fccf86c67269e8b911e3ad272`。
- W5 schema升级到0.5并把`B_N2N_TARGET_SELECTOR`移入resolved capabilities。重新执行单坐标、首tile与全算子比较均为P/D零不匹配；全算子P SHA-256仍为`1ec864892d82279beff561927500f55ebec636daf2fb7c624a1e153dd5e17532`，D仍为`2793bbe64e2b3289657f1c77bad61ebc54a4672791093d5c19a66ca742e7376e`，证明本包只改变控制编码，没有改变数学或physical bundle。最终preflight为32,593 bytes、SHA-256 `83b8edfa74890ffeebb1051c2b553d8288044f90b7d61faceeea6ef5abf3a784`。
- 验证：根仓246/246、NDPFuncModel 16/16通过；合同集合digest为`82e1d41e7c04d705f7b0a3126d2d7bacacd692be43639524549106b9ff189d49`；正式encoder runner、四仓lock、`git diff --check`均通过。操作者原始`.agents/conv_full(2).json/.txt`继续保持未修改、未提交。
- 当前完成位置：`B_N2N_TARGET_SELECTOR`已删除，当前只剩`B_REQUANT_TARGET_NUMERICS`和`B_EXECPLAN_TYPED_TRANSPORT`。G5/G6/G8和`stop_expansion`继续fail-closed；selector字段和静态编码已经闭合，但真实N2N搬运、`ping_pong=0`生命周期以及逐周期调度仍需由延期硬件协作最终确认。
- 下一步建议：继续单线程在同一`node-0004/hwop-0004-00~01`上复用可执行DeepSeek Quant路径，注入真实64-channel qparams，绑定末次reduction与唯一UINT8 flush；完成且三档P/D仍bit-exact后形成单算子配置冻结提交，再交给硬件协作负责人。随后才处理typed execplan transport或shape-family扩展。
- Git冻结点：根仓业务提交`62628ec8f0b710c7d1c9cca5ee1c7e57953ee848`，父提交`641928845d553027048057f9c55fd3ee9271aaad`，`fix: resolve real conv high4 selectors`；NDPFuncModel提交`797f099a6b5ef549109eefbafb848c234ce66f73`，父提交`e4454f7e12aa38ca94af07e017ae0928b9c839eb`。两者均为本地提交、未推送。精确回退顺序为先revert后续history账本提交，再revert根仓`62628ec8f0b710c7d1c9cca5ee1c7e57953ee848`，并在NDPFuncModel中单独revert`797f099a6b5ef549109eefbafb848c234ce66f73`。

## 2026-07-15：真实64-channel requant配置候选与对齐缺口闭合

- 真实`hwop-0004-01`的64个float32 multiplier全部互异，SHA-256为`e83328d8589db8cfc2c5a1ff033d3c0e08d9bd87d8d8fcf52b8cb22189956bb2`，范围`2.7229637e-08~0.017728098`，`y_zero_point=0`。因此不能把DeepSeek Quant模板的单一`0.06375`常量机械复用；新增确定性生成器把8条GA `mac→int32_sub` lane按四个HIGH owner step和两个local K half拆成8个shard，每个shard绑定8个真实multiplier和7个对应slice，64通道无重叠、无遗漏。
- 首轮正式编码发现关键地址问题：canonical NHWK D的第二个8-channel半块地址为`D+8`，不满足16B对齐；encoder exit 0但base字段隐式丢低4位，会与第一个半块别名。修复后保持canonical D不变，增加两个对齐UINT8 staging区，base为`904400/979664`，每区75,264 bytes；比较端显式交织两个`[spatial,8]`半块回`[spatial,16]`。
- 每个shard读取P base `151760/151792`，LC1覆盖9,408个空间点，LC2执行2,352个32B写事务。8个shard均通过正式parser/placement/encoder，连接数21、cost 0；双重重建除mapping review原始列表顺序外，parsed dump、64/128位bitstream和detailed dump逐字节相同，mapping review规范化语义hash相同。全算子magic-round软件重放与nearest-even golden D逐元素一致，64通道flush计数全部为1；新增2/2聚焦测试通过。
- 当前边界：这些结果闭合了真实qparam、GA常量、对齐staging、round/saturation和唯一flush的候选配置，但NDP request adapter尚未消费8份JSON及staging inverse，所以`B_REQUANT_TARGET_NUMERICS`暂不删除；`B_EXECPLAN_TYPED_TRANSPORT`也保持。下一步只需把该bundle绑定进现有config-bound request并重跑三档P/D，随后即可冻结交给硬件组。
- 可复现清单`conv_1x1_requant_real/manifest.json` SHA-256为`4424a6524dcdaaf1933b57875e4f3a1ae7edb11321dd02b692bbed51b82b274f`。根仓候选提交`3360aee92936e90aee143a14f387d29458c6453f`，父提交`347c8dfbbea61bb03bf50e23b2e994f75194a234`，`feat: encode real conv requant shards`；本地提交、未推送。精确回退为先revert后续账本提交，再`git revert 3360aee92936e90aee143a14f387d29458c6453f`。

## 2026-07-15：真实1×1 requant config-bound闭环与单算子冻结

- NDP physical request升级为schema 0.3，根adapter传入`conv_1x1_requant_real/manifest.json`及8份JSON的原文和SHA-256。NDP在任何计算前严格验证64通道恰好覆盖一次、8-shard路径/hash、四组HIGH-ring slice、GA multiplier/magic常量、P/staging地址与16B对齐、stream stride、LC `1/9408/2352`及每个逻辑输出唯一flush；hash、覆盖、flush、loop、地址或GA任一漂移均有fail-closed测试。
- 首tile/全算子路径不再直接把数学输出冒充canonical D：28个slice各把本地16通道拆为两个`[3,56,56,8]` UINT8 staging，写入偏移`904400/979664`，再从DRAM读回、拼接/inverse成canonical D并写回。最终报告保存28组、每组两份staging的base/SHA、所用shard和`staging_inverse_matches_canonical_D=true`；首轮W5门禁把物理写回数误写成16，正式运行暴露后修正为真实28-slice覆盖。
- 三档重新使用同一真实`node-0004/hwop-0004-00~01` physical bundle与W3 golden：单坐标P/D各1元素、首tile各150,528元素、全算子各3,211,264元素，mismatch全部为0，原全算子P/D SHA-256保持`1ec864892d82279beff561927500f55ebec636daf2fb7c624a1e153dd5e17532`/`2793bbe64e2b3289657f1c77bad61ebc54a4672791093d5c19a66ca742e7376e`。最终preflight schema为0.6、request schema为0.3，文件62,329 bytes、SHA-256 `8dd0d61bacd0f840f09b038a16180dac4d7408878857d5b10143f684bf2f0c80`。
- 正式encoder复核：累加JSON SHA-256 `a20641cfcf65068c3ca31d710a0ef45d28a53cbf80d5e246ce54f0de3fe16f2c`仍为46条连接、cost 0；requant manifest SHA-256 `4424a6524dcdaaf1933b57875e4f3a1ae7edb11321dd02b692bbed51b82b274f`的8个shard各为21条连接、cost 0，重复输出逐文件相同。根仓248/248、NDPFuncModel 19/19、四仓lock、`git diff --check`全部通过；只保留既有NumPy DeprecationWarning和操作者原始未跟踪`.agents/conv_full(2).json/.txt`。
- 阻塞裁决：该首例`B_REQUANT_TARGET_NUMERICS`已移入resolved capabilities，当前只剩`B_EXECPLAN_TYPED_TRANSPORT`阻碍自动扩展/整网执行，不妨碍硬件组手工加载冻结镜像。G5/G6/G8仍为false，因为NDP bulk是config-bound物理DRAM等价kernel而不是逐周期LC/stream/buffer或bitstream解释器，精确新配置硬件P/D也尚未取得；不得据此宣称三方一致。
- Git冻结点：NDPFuncModel提交`1d3181d832d7a409af779215e4aa590d03bd8ed3`，父提交`797f099a6b5ef549109eefbafb848c234ce66f73`，`feat: bind real requant config bundle`；根仓业务提交`1388dede4aac53a77d02dec0b24db0ad2d35ef1f`，父提交`010e1e3e6abc93bbf7f4ca6673ebe49d9b416235`，`feat: freeze real 1x1 requant closure`。两者均为本地提交、未推送。精确回退顺序为先revert后续文档台账提交，再在根仓执行`git revert 1388dede4aac53a77d02dec0b24db0ad2d35ef1f`，并在NDPFuncModel中单独执行`git revert 1d3181d832d7a409af779215e4aa590d03bd8ed3`；不要修改或删除操作者未跟踪伪代码原文。
- 人员拆分以该冻结点为边界：硬件负责人只接收冻结JSON/bitstream、physical A/B/bias/qparams、golden P/D、地址与比较证据并记录首错，不修改公共生成器；扩展负责人从同一提交处理第二个代表性1×1和shape-family，未有硬件反馈前标candidate。公共schema/合同、selector/ping-pong规则、Git和全量回归继续串行。
- 冻结交付审计发现此前physical bundle只在W5/NDP请求内存中存在，若直接结束会把“可生成”误报为“硬件组已收到”。因此新增`tools/export_conv_1x1_hardware_freeze.py`：确定导出28-slice全部11个physical port，其中A/B/bias/6类qparam标为load input，P/D标为golden output；另导出canonical P/D、累加+requant共10份配置、18份128/64位bitstream，以及含308个physical region和56个staging输出区的地址表。目录`artifacts/w5/hwop-0004-00/hardware_freeze/`共339个manifest文件、约41.9 MB，freeze ID `f687debd0215f1d29b6ca94176c4e9cbcf20434d58bce57c430129edb8922d5f`，两次导出manifest SHA-256均为`72e17cb52c2948f86fe6b0e9b2715de57c5404a72a04f9514247f174e8a95550`。
- 新增`tools/compare_conv_1x1_hardware_dump.py`，约定硬件dump目录为`P/slice-XX.bin`和`D/slice-XX.bin`，按地址表inverse回canonical NCHW并输出首错坐标/值/hash。使用冻结physical golden作自检时，P/D各3,211,264元素、0 mismatch，SHA-256仍为`1ec864...`/`2793bbe...`；新增变异测试证明D首错`[0,0,0,0]`可报告。根仓全量回归随之增至249/249。
- 真正可交硬件组的根仓冻结提交为`e9b6492098c2101aa86afd83bf95e8024fa6e8df`，父提交`e6c1ed579be5c3d0f583a3b008180c4714e77cb5`，`feat: export real 1x1 hardware freeze`；数值闭环业务提交仍为`1388dede...`，NDP冻结提交仍为`1d3181d...`。精确回退时先revert后续台账，再`git revert e9b6492098c2101aa86afd83bf95e8024fa6e8df`移除交付器，若还需回退数值闭环再按上一条顺序revert`1388dede...`与NDP `1d3181d...`。大体积交付目录是可再生产物，不进入普通Git历史。

## 2026-07-15：说明文档收敛前的完成计划归档索引

- 操作者要求不再维护独立接手文件，把唯一接手入口合并进`plan.md`；`agent.md`只保留稳定代码地图、当前边界和协作规则；本`history.md`明确改为“只有定位历史问题才加载”。因此原`W5_HANDOFF.md`中的三条接手检查、冻结恢复点、硬件交付命令和人员拆分迁入新`plan.md`，其W5首包A～D过程说明归入本节及前述2026-07-14/15 W5条目后删除原文件。
- 原`plan.md`中W0～W5的详细实施步骤、W4 C0～C7并行波次、16→28切换清单、NDPFuncModel第1～9项修复账本和“阶段A～F”的重复计划均已完成或被后续裁决替代，不再作为当前计划加载。追溯位置如下：W0～W3见“W0～W3交接封版”及2026-07-12条目；W4-28 C0～C7见2026-07-13/14连续条目与`W4_ARCHIVE.md`；W5首例入口、伪代码裁决、selector、requant和冻结见2026-07-14“W5首个真实1×1”起至2026-07-15“requant config-bound闭环”各条。
- 原`agent.md`中三个参考仓逐目录文件数、2026-07-11全量源码分类、旧NDP主入口/trace/pyc清点和旧CGRA实验入口的长篇地图属于当时审计证据，不再承担当前状态说明。其历史结论已分别记录在2026-07-10“引入NDP工具链”、2026-07-11“引入Conv模型”、2026-07-13“方案切换全工作文件夹遗留审计”和规则文档第11～17节；后续代码定位以精简后的职责级地图、`rg`和实际源码为准，不依赖旧文件计数。
- 被替换的旧结论包括：“NDP config adapter待完成”“当前缺W5真实Conv JSON”“首例仍缺64-channel requant/唯一flush”“当前只到schema 0.2”“QLinearConv仍无任何项目配置”。现行事实是：首个真实`node-0004/hwop-0004-00~01`已有累加JSON和8份requant JSON，schema 0.3实际消费原文/SHA，28-slice双staging inverse和三档P/D通过，并已形成freeze ID `f687debd...`的硬件交付目录；该首例只剩`B_EXECPLAN_TYPED_TRANSPORT`影响自动重建，精确硬件P/D仍未发生。
- 文档收敛不改变任何代码、JSON、bitstream、合同、freeze manifest或门状态。G0/G2/G3/G4保持通过；W5首例冻结但G5/G6/G8仍为false；第二个1×1/shape-family只能标candidate；硬件负责人和扩展负责人可从同一冻结提交分工，公共schema/合同/Git/全量回归继续串行。

### 从原`plan.md`移出的已完成详细计划摘要

| 原计划块 | 已完成内容与最终边界 | 历史证据入口 |
|---|---|---|
| W0/G0与阶段B骨架 | 根集成包、manifest/contract/backend/artifact、cache/resume、mock DAG、仓库lock与恢复验证均完成；后续不再作为当前实施步骤重载 | “W0空流水线骨架完成”“W0/G0最终封版” |
| W2/G2小Conv | 1/4-slice软件fixture完成physical ingress、uint8×int8/int32 psum、reduction、requant、D写回和inverse；只批准软件候选，不批准目标RTL/bitstream | 2026-07-11连续NDPFuncModel条目 |
| W3/G3与原阶段A～C | 正式模型/输入、78节点、133个`hw_op`、79个runtime tensor、55个internal tensor、491个initializer引用、ORT节点与子步骤golden、旧77原语映射均完成 | “W0～W3交接封版”及2026-07-12条目 |
| W4/G4与原阶段D | 28-slice topology、七族正逆layout、93边、91条qparam链、16个残差Add、79 tensor生命周期/alias、DeepSeek公共基线和ResNet差异合同、12/12 G4批准完成 | 2026-07-13/14 C0～C7条目与`W4_ARCHIVE.md` |
| W5首例与原阶段E | 首个真实`node-0004/hwop-0004-00~01`的LC/PE/stream裁决、1×1累加JSON、selector `4/1/1`、8份requant JSON、正式encoder、parsed dump、placement、bitstream和确定性完成 | 2026-07-14“W5首个真实1×1”起的连续条目 |
| 原阶段F的首例软件数值 | schema 0.3实际消费manifest、JSON原文/SHA，验证64通道/GA/16B/LC/唯一flush，28-slice双staging inverse及三档P/D bit-exact完成；这是config-bound功能闭环，G6仍false | 2026-07-15“requant config-bound闭环”条目 |
| 首例硬件交付准备 | 339文件冻结包、地址表、physical/canonical P/D、10份配置、18份bitstream和硬件dump inverse比较器完成；精确硬件实跑尚未发生，G8仍false | 2026-07-15冻结导出与比较器条目 |

原计划中“当前可立即执行队列”的13项已完成细节不再逐条留在现行入口：16-slice泄漏终审、三路layout候选、Conv探针、C3两种调度、ADR-008配置源审计、Pool三模板、Quant/Add-Dequant、GEMM/GEMV与sum族、C7 typed参数合同、ADR-009继承、首个1×1累加、selector修复、64通道requant与硬件冻结，均由上表及相邻历史提交台账覆盖。未完成的typed execplan、第二实例/shape-family、真实3×3、硬件P/D和全算子/整网工作已重新整理进精简后的`plan.md`，没有被归档成“已完成”。

- 文档实体变更完成：`agent.md`由767行精简为140行，只保留职责级代码地图、当前证据边界和协作规则；`plan.md`由844行精简为180行，成为唯一接手入口并直接包含三条检查、冻结点、门状态、三路人员分工和后续阻塞；独立`W5_HANDOFF.md`删除，`W4_ARCHIVE.md`改指`plan.md`且只在W4追溯时加载。
- 规则文档同步纠错：把“原始42个模板没有QLinearConv”与“项目已生成首个真实1×1”分开；把“量化参数完全没有传递通道”收窄为`B_EXECPLAN_TYPED_TRANSPORT`；将首例状态更新为schema 0.3、64通道requant、双staging inverse和config-bound P/D已通过但硬件未验证；修正14～17章编号并删除重复的Conv requant节。
- 文档收敛后执行`git diff --check`、活动旧引用/重复标题检查和`tools/sync_repositories.py verify`均通过；根仓249/249测试通过，NDPFuncModel 19/19测试通过。测试仅出现既有NumPy弃用告警，没有失败。操作者未跟踪的`.agents/conv_full(2).json/.txt`保持原样。

## 2026-07-15：恢复既有直接Git推送规则

- 操作者澄清此前云端发布一直使用已建立的根仓`origin`直接推送，不要求GitHub插件重新安装仓库权限，也不要求`gh`。先前把完整PR发布流程的前置条件套到普通`git push`属于流程过度；现已在`agent.md`固定区分直接Git推送与插件PR操作。
- 新的长期授权边界是：只有操作者明确要求推送/发布/同步云端时才执行`git push`；本地提交不自动授权远端写入。获授权后必须先fetch并证明`origin/main`是HEAD祖先，只允许非强制fast-forward，推送后核对远端SHA；分叉、认证错误或需要force时停止。
- 当前操作者已明确要求本轮按原方式直接推送。推送范围只包含现有已提交历史以及本条规则提交；未跟踪的`.agents/conv_full(2).json/.txt`保持本地原件状态，不暂存、不提交、不上传。
