# Codex managed worktree 关键经验

最后更新：2026-07-13

本文记录本项目解决 Codex managed worktree“项目文件不完整、依赖不可用、频繁许可”问题时得到的可复用经验。目标不是复制本项目的绝对路径，而是让下一个包含大产物、虚拟环境和多个参考仓库的项目可以直接按同一方法设计。

> **2026-07-13事故更正**：本文早期版本把“junction创建成功、即时测试通过”误写成最终可靠方案。真实managed worktree稍后被桌面宿主回收时，清理过程穿透四个junction，依次清空了Local的`.venv`、`CGRA_SIM`、`ndp-sim-ref`和`NDPFuncModel`，损失约1.88 GiB。后续所有junction正面描述只作为失败方案的历史记录；当前规则是禁止把Local依赖或产物junction/symlink到managed worktree，并把“worktree销毁后Local源保持不变”列为任何替代方案的强制验收项。

## 一、结论先行

可靠的工作树方案不是“把 Local 目录完整复制一遍”，而是把项目内容分成四类分别处理：

| 内容 | 推荐交付方式 | 原因 |
|---|---|---|
| Git 已跟踪源码、测试、合同和小型固定快照 | 正常 Git checkout | worktree 天然具备，最稳定、可审计 |
| 少量 ignored 配置或元数据 | 根目录 `.worktreeinclude` | Codex managed worktree 官方支持，创建时一次性复制 |
| 深层 ignored 小文件，且当前桌面版本复制不可靠 | Git 跟踪的固定快照，由 setup 在 worktree 内恢复 | 不依赖 Local 跨目录读取，可校验 hash，可复现 |
| 大型、只读、不可重复复制的依赖或参考仓库 | 留在Local；依赖任务回Local，或使用独立、可恢复、可删除的副本 | managed worktree回收可能穿透junction，“逻辑只读”不能保护目标 |
| 大型运行产物、正式 golden、硬件 dump | 只留在 Local，由最终集成任务使用 | 避免放大磁盘、并行任务误写和昂贵重算 |

权限方面采用：

```toml
approval_policy = "on-request"
approvals_reviewer = "auto_review"
sandbox_mode = "workspace-write"

[sandbox_workspace_write]
network_access = true
```

这会让符合策略的常规操作由自动审查处理，但不会取消沙箱，也不会允许任意越界写入、破坏性命令或高风险操作。不要为了减少弹窗使用 `danger-full-access` 或 `never` 作为日常默认值。

## 二、问题的根因

### 2.1 managed worktree 不是 Local 目录镜像

Git worktree 首先是另一个 Git checkout。已跟踪文件会存在，但 `.venv`、被忽略的参考仓库、模型、golden、构建缓存和运行产物不会天然出现。

因此，“Local 可以运行、worktree 找不到文件”通常不是仓库损坏，而是依赖没有被纳入 worktree 的交付设计。

### 2.2 不能把所有 ignored 内容都塞进 `.worktreeinclude`

`.worktreeinclude`适合小文件，不适合以下内容：

- 整个虚拟环境；
- 多个完整参考仓库；
- 数百 MB 或数 GB 的 tensor、trace、dump；
- 会被并行任务修改的共享目录；
- 密钥等不应扩散到每个任务副本的内容。

复制大目录会让每个 worktree 都增加相同成本，也会显著延长任务创建时间。

### 2.3 Windows 沙箱身份和文件 ACL 可能不同

Codex 的普通沙箱命令、自动审查后的命令和用户桌面会话不一定以完全相同的 Windows 身份访问文件。一个路径在 Local 用户下可读，不代表另一个执行身份一定可读。

本项目实测出现过两类问题：

- setup 试图从 Local 跨工作区读取 ignored manifest，普通身份可读而提升后的身份被 ACL 拒绝；
- 在提升身份下运行测试，反而失去对部分现有文件的读取权限。

所以应把“测试执行”和“确实需要的 Git/越界写操作”分开，不要把整套流程都放到提升权限下运行。

### 2.4 junction 不只是路径校验问题，还会扩大清理边界

worktree 内的 `CGRA_SIM` 看起来在项目根下，但解析 junction 后真实目标位于 Local checkout。即使业务代码只读、HEAD/dirty校验和路径白名单全部正确，宿主回收worktree时仍可能把目标当成目录内容递归清理。

本项目曾实现以下五项保护，但仍发生了数据丢失：

1. 先由当前 worktree 的 Git common directory 找到唯一 Local checkout；
2. junction 目标必须精确等于该 Local 下同名的锁定仓库；
3. 仓库 HEAD 必须匹配锁文件；
4. 仓库必须干净；
5. 共享 junction 只允许 `verify`，禁止 `sync` 或修改。

这些检查只能约束项目脚本，不能约束桌面宿主的GC/回收器。当前直接禁止这类共享；未来若平台声明修复，也必须创建一次性fixture，完成setup、任务归档/回收后，再核对Local源的逐文件hash，不能只验收setup当下。

## 三、本项目历史方案与事故后的落地

以下3.1～3.4记录事故前方案，不能再作为推荐模板。当前落地是：`.worktreeinclude`和Git跟踪小快照仍可用；setup只允许Local自检，非Local硬失败；需要`.venv`、三个参考仓或正式产物的任务回Local执行。

### 3.1 项目级文件

- `.codex/config.toml`：项目审批和沙箱默认值；
- `.worktreeinclude`：只包含两个约定的小型 W3 JSON；
- `tools/setup_codex_worktree.ps1`：Local自检；非Local在创建链接/恢复内容前硬失败；
- `contracts/w3_metadata/*.base64`：两个深层 manifest 的固定快照；
- `tools/sync_repositories.py`：识别受控 junction 的只读验证；
- `tests/test_worktree_environment.py`：验证 Local 与 worktree 两种状态。

### 3.2 内容分层

本项目没有把约 951 MB W3 tensor 复制进工作树，也没有重新运行 W3：

- `artifacts/w3/legacy77_mapping.json`：由 `.worktreeinclude` 复制；
- `artifacts/w3/model_graph.json`：由 `.worktreeinclude` 复制；
- `artifacts/w3/golden_batch16/manifest.json`：由跟踪快照恢复；
- `artifacts/w3/subop_batch16/manifest.json`：由跟踪快照恢复；
- `.venv`：只留在Local，不交付给managed worktree；
- `CGRA_SIM`、`ndp-sim-ref`、`NDPFuncModel`：只留在Local；需要它们的任务回Local；
- W3 `.npy`、完整 golden、其他大型产物：只在 Local 使用。

### 3.3 事故前setup条件为何仍不安全

事故前`tools/setup_codex_worktree.ps1`遵循以下约束：

1. 不联网；
2. 不安装依赖；
3. 不覆盖已有普通目录或文件；
4. 从 Git common directory 推导 Local 源，不硬编码用户绝对路径；
5. `.venv`不存在时立即失败；
6. 参考仓缺失、dirty 或 HEAD 与 `repos.lock.json` 不一致时立即失败；
7. 已存在的 junction 必须只指向预期源；
8. 恢复的小元数据必须同时匹配固定 size 和 SHA-256；
9. 恢复只发生在当前 worktree 内；
10. 完成后自动执行三参考仓只读 verify；
11. 支持 `-CheckOnly`，便于在 Local 或 CI 中无副作用检查。

### 3.4 事故前即时验收结果（已证明不充分）

当时真实 Codex managed worktree 的即时验收结果是：

- `.venv`和三个参考仓共四个路径全部为 `linked`；
- 两个小型 W3 JSON 为 `included`；
- 两个深层 manifest 为 `restored`；
- setup 内置仓库校验通过；
- 独立三仓 lock 校验通过；
- Local/worktree 环境聚焦测试 5/5 通过；
- 工作树 Git 状态干净；
- 没有联网、安装、复制或重跑 W3 tensor；
- 整个终验没有用户手工许可中断。

但这些检查没有覆盖“任务归档/managed worktree被宿主销毁”这一生命周期阶段。约33分钟后四个Local目标被依次清空，所以即时5/5通过不能再称为最终验收。

## 四、曾经失败的方法及原因

| 尝试 | 结果 | 应吸取的经验 |
|---|---|---|
| 认为 worktree 会自动拥有 Local 的 ignored 文件 | 失败 | worktree 必须显式设计依赖交付 |
| 用 `.worktreeinclude` 的深层精确路径或递归 glob 复制两个 manifest | 当前桌面版本实测不可靠 | 官方语义可用，但必须在真实 managed worktree 验收；必要时用小型跟踪快照兜底 |
| setup 从 Local 跨目录复制 manifest | 在不同 Windows 身份/ACL 下失败 | setup 最好只依赖 worktree 内已跟踪或已包含的输入 |
| 把 ignored 深层 manifest 直接强制加入 Git | 当时写入身份仍受 ACL 影响 | 与其依赖特殊 ACL，不如生成小型、固定 hash 的仓内快照 |
| 用 `Resolve-Path` 判断 junction 的真实目标 | 不能可靠得到 junction target | 用 `Get-Item -Force` 的 `Target`，再规范化和精确比较 |
| 让原仓库验证器拒绝所有 root 外路径 | worktree junction 被误拒 | 保留默认拒绝，只增加 Git common directory 推导出的精确白名单 |
| 允许 `sync` 通过共享 junction | 风险过高 | 共享依赖只能 verify；要修改依赖就创建独立正式工作树 |
| 把Local `.venv`和参考仓以junction挂进managed worktree | **严重失败：宿主回收穿透链接并清空约1.88 GiB Local源** | 禁止跨managed worktree共享目录链接；替代方案必须通过销毁后hash验证 |
| 所有命令都用提升身份运行 | 部分读取反而失败 | 普通测试留在正常沙箱；只对确实需要的动作单独审批 |
| 为减少弹窗关闭沙箱或设置永久无审批 | 不安全 | 使用 `on-request + auto_review + workspace-write`，保留风险边界 |

这里要特别区分“官方能力”和“当前版本实测”：官方文档说明 `.worktreeinclude` 支持 ignored 路径和 `.gitignore` 风格 pattern；本项目的深层 manifest 问题是当前桌面宿主上的实测兼容性问题，不应写成所有版本永远都不支持嵌套路径。下个项目仍应先做最小真实 worktree 试验，再决定是否需要快照兜底。

## 五、下一个项目的推荐实施顺序

### 第一步：盘点，不要先写脚本

对项目根目录列出：

- Git 已跟踪文件；
- ignored 但任务必须读取的文件；
- 虚拟环境或包缓存；
- 嵌套仓库及其 commit/dirty 状态；
- 大模型、golden、trace、硬件 dump；
- 哪些内容会被任务修改；
- 哪些验证必须使用正式大数据。

先按“小而固定 / 大而只读 / 大而可再生 / 必须可写”分类。没有这一步，后面很容易把不该共享的内容做成 junction。

### 第二步：定义恢复合同

至少建立以下事实：

- 依赖仓库锁文件：路径、remote、branch、完整 commit、dirty 要求；
- 小型元数据：相对路径、size、SHA-256、交付方式；
- 大产物：Local-only 标记、生成命令、输入 hash 和失效条件；
- setup 版本和验收命令；
- 哪些任务允许在 worktree 做，哪些必须回 Local。

### 第三步：先做最小 `.worktreeinclude`

根目录示例：

```gitignore
# 只列创建工作树时真正需要的小型 ignored 文件。
config/local-test.json
artifacts/index.json
```

不要一开始就写 `artifacts/**`、`.venv/**` 或整个依赖仓目录。先在一个真实 Codex managed worktree 中验证每个条目是否出现。

### 第四步：编写幂等 setup

推荐入口：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\setup_codex_worktree.ps1
```

脚本输出应为稳定 JSON，至少包含：

- 当前模式：`local` 或 `worktree`；
- 推导出的 Local source root；
- 每个依赖路径的状态：`source`、`unavailable`或`isolated_copy`；
- 每个元数据的状态：`source`、`included`、`restored`、`would_restore`；
- 实际 size 和 SHA-256；
- 依赖仓 verify 结果。

脚本要可以重复运行。重复运行不应创建指向Local的目录链接、覆盖正确文件或改变 Git 状态。

### 第五步：验证器保持路径边界

若已有工具要求依赖必须在project root内，不要删掉这个保护。managed worktree不得为Local目标增加junction/symlink白名单；确需依赖时回Local，或给任务提供独立且可由lock恢复的副本。UNC路径、路径穿越或名字相同但位置不同的仓库仍应失败。

### 第六步：分别测试 Local 和真实 managed worktree

至少覆盖：

1. Local `-CheckOnly` 不创建任何目录链接；
2. worktree setup只处理本工作树内的小型输入，外部依赖不可用时明确失败；
3. worktree 第二次 setup 幂等；
4. 任意指向Local的junction/symlink被拒绝；
5. dirty 参考仓被拒绝；
6. commit 不匹配被拒绝；
7. 快照 hash 或 size 被破坏时失败；
8. managed worktree对Local依赖的`verify`、`sync`和写操作均被拒绝；
9. worktree Git 状态仍干净；
10. 归档并触发managed worktree回收后，Local fixture的逐文件hash和目录结构完全不变。

不要只在手工创建的 `git worktree` 里测；`.worktreeinclude` 的复制行为和宿主GC只适用于 Codex managed worktree，必须完成一次真实桌面任务从创建到归档/回收的全生命周期验收。

### 第七步：划分并行任务边界

- 先区分执行模型：Local任务内派生的协作子代理共享同一Local目录，可以看到当前源码、`.venv`、参考仓和Local-only产物，但也共享未提交改动，必须按互不重叠文件分工，并由Local主任务统一Git与集成；独立managed worktree只看到创建时commit的tracked快照和显式交付的小型元数据，默认没有`.venv`和参考仓，旧detached worktree还可能落后于当前HEAD；
- 只读审查：优先 Local；
- 只依赖Git跟踪文件且互不重叠的代码修改：从已冻结当前基线新建独立worktree；
- 需要`.venv`、参考仓或Local-only产物：回Local或使用共享Local目录的协作子代理，不做目录链接共享；
- 必须修改参考仓：为该仓创建独立可写工作树并单独提交；
- 正式大数据、整网回归和最终集成：回 Local；
- 并行任务达到本地提交门槛时，在结束时集中做一次暂存/提交，减少重复许可；纯微小改动不强制单独提交；
- 每个任务报告 commit、父 commit、修改文件、聚焦测试和回退命令。

## 六、哪些能配置到全局

Codex 用户级配置位于 `~/.codex/config.toml`。以下通用安全默认值适合全局配置：

```toml
approval_policy = "on-request"
approvals_reviewer = "auto_review"
sandbox_mode = "workspace-write"

[sandbox_workspace_write]
network_access = true
```

全局设置的效果是让新项目默认采用相同审批和沙箱策略；受信任项目仍可用自己的 `.codex/config.toml` 做项目级覆盖。

以下内容不能做成一份通用全局配置，必须逐项目存在：

| 内容 | 必须项目级的原因 |
|---|---|
| `.worktreeinclude` | 每个仓库需要的 ignored 路径不同，且文件必须位于仓库根目录 |
| setup 脚本 | 依赖名称、锁文件、元数据和恢复逻辑不同 |
| 依赖交付边界 | 必须逐项目决定哪些任务回Local、哪些可用隔离副本 |
| 参考仓 commit/hash | 属于项目恢复合同，不能跨项目复用 |
| W3/模型/golden 的 Local-only 边界 | 取决于项目数据规模和验证流程 |
| Codex Desktop local environment 的 setup action | 应绑定该项目的脚本和平台 |

因此最佳组合是：

1. 全局只保存安全的审批/沙箱默认值；
2. 每个项目提交自己的 `.worktreeinclude`、setup、lock 和测试；
3. 若多个项目结构相似，再把“生成上述文件的流程”做成个人模板或 Codex skill，而不是把具体路径写进全局 config。

### 本机当前状态

截至 2026-07-13，本机用户级 `~/.codex/config.toml` 已有：

```toml
sandbox_mode = "workspace-write"

[sandbox_workspace_write]
network_access = true
```

尚未设置 `approval_policy` 和 `approvals_reviewer`。因此若要把本项目的许可策略提升为全局，只需在用户级 TOML 的顶层补上：

```toml
approval_policy = "on-request"
approvals_reviewer = "auto_review"
```

这项全局修改会影响以后所有默认使用用户配置的项目，应该作为单独的用户级选择执行；它不会自动替代每个项目的工作树 setup。

## 七、改动分级、提交与推送规则

下一个项目默认使用三级Git规则。这里的“提交云端”指先形成可验证的本地Git提交，再执行`git push`到操作者控制的GitHub仓库；不能用上传未提交文件代替Git历史。

### 7.1 微小改动：不单独提交

只有同时满足以下条件，才属于微小改动：

- 仅修正错字、措辞、注释、空白、Markdown排版或同类机械格式；
- 不改变程序行为、命令参数、公开接口、测试语义或错误处理；
- 不改变schema、合同、ADR裁决、layout、qparams、地址、依赖锁或产物hash；
- 可以通过直接查看diff确认风险极低。

这类改动无需创建独立commit，可以保留到下一次相关的较小改动一起提交，但必须在当前任务报告中说明。若即将切换/删除工作树、执行可能覆盖现场的操作、跨人交接，或存在丢失风险，应先把它合并到一个相关本地提交中，不能为了“微小不提交”而丢失工作。

### 7.2 较小改动：只提交本地Git

以下通常属于较小改动：

- 单一模块内的明确bug修复或小功能；
- 聚焦测试、setup、验证脚本的小范围更新；
- 会改变执行规则、文档语义、schema校验或接口行为，但范围有限；
- 可以用聚焦测试或静态检查独立验收，不构成W0～W9阶段门。

较小改动应做本地原子提交并登记完整hash、父提交、范围、验证和回退点，但不因每个小提交都打扰用户或立即推送GitHub。可以等到同一工作包形成重大检查点后批量推送。

### 7.3 重大改动：本地提交后推送GitHub

出现以下任一情况，通常达到云端推送门槛：

- W0～W9工作包或G0～G9验收门形成新恢复点；
- 跨多个核心模块、多个仓库或大规模重构；
- 正式模型、硬件合同、ISA/register-map、layout或execplan关键口径获批；
- 多个本地提交共同构成已经验证的重要功能闭环；
- 即将清理本地副本，必须确认云端可恢复；
- 操作者明确要求推送或建立云端备份。

推送后必须核对目标仓库、branch、完整远端hash和ahead/behind状态。重大改动也不允许把模型、golden、trace、硬件dump或其他可再生大文件直接塞进普通Git历史；这些内容继续按artifact/hash合同管理。

### 7.4 判定与例外

- 看风险和恢复价值，不单纯按文件数量或代码行数判断；
- 用户对某次改动明确指定“不提交、本地提交或推送GitHub”时，以用户要求为准；
- 安全修复、可能丢失的唯一工作、跨设备交接可提前提升到云端检查点；
- 不得通过reset、rebase、强推或改写历史来把多个小提交伪装成一个大提交；
- 未推送的本地commit不是云端备份，必须如实说明状态。

## 八、安全红线

- 不把 `danger-full-access` 设为常规全局默认；
- 不把审批策略全局设为 `never` 来换取少弹窗；
- 不给任意 Python、PowerShell 或 shell 建立过宽永久许可前缀；
- 不把密钥、token、私有配置无差别加入 `.worktreeinclude`；
- 不把数据库、包环境、依赖仓或产物通过junction/symlink挂进managed worktree，无论逻辑上是否只读；
- 不在共享 `.venv` 中安装或升级包；
- 不在共享参考仓中切分支、提交或生成产物；
- 不为Local目录链接关闭路径越界检查；
- 不因setup成功就跳过lock、dirty、hash和“归档/回收后Local不变”的生命周期验收。

## 九、交接检查表

下一个项目只有同时满足以下条件，才可以宣称工作树方案完成：

- [ ] tracked 源码完整；
- [ ] 必要的小型 ignored 文件存在且 hash 正确；
- [ ] 大型依赖没有不受控重复复制，也没有通过目录链接暴露给宿主清理；
- [ ] 大型正式产物没有被工作树任务误读、误写或重算；
- [ ] Local/隔离仓库 clean 且 commit 与 lock 一致；
- [ ] setup 首次运行和重复运行都成功；
- [ ] Local 与 managed worktree 两种模式均有测试；
- [ ] 指向Local的目录链接、dirty仓、hash破坏均会硬失败；
- [ ] Local的`verify`可用，managed worktree对Local依赖的访问被边界拒绝；
- [ ] 真实managed worktree归档/回收后，Local fixture逐文件hash不变；
- [ ] Git 状态干净；
- [ ] 常规安全动作不再频繁阻塞用户；
- [ ] 高风险、破坏性和越界动作仍保留人工许可；
- [ ] 文档明确哪些任务留在 Local，哪些任务可并行；
- [ ] 有精确提交、验证记录和回退点。

## 十、回退原则

工作树支持层应保持独立提交，便于分别回退：

1. 项目级审批/沙箱配置；
2. `.worktreeinclude`；
3. setup 脚本；
4. 小型元数据快照；
5. Local-only依赖边界验证；
6. Local/worktree 环境测试；
7. 文档和历史台账。

不要用真实Local大产物测试恢复能力；销毁安全测试必须使用一次性小fixture。若发现任何旧junction，先核对其精确目标并只删除链接对象，再恢复Local内容，避免恢复后再次被宿主清空。

## 十一、官方参考

- [Codex Worktrees](https://learn.chatgpt.com/docs/environments/git-worktrees)：managed worktree、Local/Worktree/Handoff、`.worktreeinclude`及其边界；
- [Codex Local environments](https://learn.chatgpt.com/docs/environments/local-environment)：按项目/平台配置 setup script 和 actions；
- [Codex Configuration Reference](https://learn.chatgpt.com/docs/config-file/config-reference)：用户级与项目级配置、`approval_policy`、`approvals_reviewer`和沙箱字段；
- [Agent approvals & security](https://learn.chatgpt.com/docs/agent-approvals-security)：auto-review 的适用范围和安全边界。
