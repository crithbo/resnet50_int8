# ResNet50 INT8 工作日志

最后更新：2026-07-12

本文件只保留已经发生的关键决策、验证和状态变化。当前任务看 `.agents/plan.md`，代码和仓库细节看 `.agents/agent.md`，单算子推导看 `.agents/rules/算子配置规则.md`。

## Git提交、GitHub备份与本地空间规则（2026-07-11最终修正）

- 每个有效小步骤都要提交；`history.md` 必须记录仓库、完整40位commit、直接父commit、改动范围、验证结果和精确回退位置。短hash只用于正文易读，不能替代本节台账。
- 回退默认使用 `git revert <commit>` 生成保留历史的新提交；不得自行使用reset、rebase、filter、强推或删除提交。任何改写历史仍须操作者单独确认。
- 操作者最终澄清：真正需要永久保留的是提交，不是仓库目录副本。项目应尽量只保留一份必要工作树，不为备份目的额外创建clone、worktree、zip或目录复制；云端恢复以GitHub已推送提交为主。
- 主仓和发生修改的子仓都必须先做本地原子提交并在history登记；小进度不逐次推送。W1/W2等大步骤通过验收门、形成明确恢复检查点，或操作者明确要求时，再批量推送到操作者控制的GitHub仓库或fork并核对远端hash。不得把未推送的本地提交或对上游仓库可能无权限的 `origin` 当成已经完成云端备份。
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
