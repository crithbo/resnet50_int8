# ResNet50 INT8 项目地图与协作约束

最后更新：2026-07-15

本文件只保存相对稳定的项目地图、证据边界和协作规则，**不是当前任务清单，也不是新对话接手入口**。新任务只从`.agents/plan.md`开始；需要定位实现时再按需读取本文件。

> `.agents/history.md`是历史台账。除非需要定位历史问题、追溯旧结论/提交/父提交或确认回退点，否则不要加载它。不要用历史条目覆盖`.agents/plan.md`中的现行状态。

## 1. 文档职责

- `.agents/plan.md`：唯一接手入口和当前执行计划，含接手检查、恢复点、门状态、阻塞和下一工作包。
- `.agents/agent.md`：本文件；稳定代码地图、仓库职责、证据边界和协作规则。
- `.agents/rules/算子配置规则.md`：模型语义到LC/PE/stream、layout与数值比较的现行规则。它会随真实证据修订，不是不可修改的先验规格。
- `.agents/history.md`：已发生事实与完成计划归档；只有追溯时加载。
- `.agents/W4_ARCHIVE.md`：W4方案切换、事故和裁决的专项历史索引，不是当前入口。
- `.agents/decisions/`、`contracts/`：ADR、机器合同和审批证据；被hash绑定的合同不能只为整理措辞改写。
- `.agents/经验.md`：通用工作经验，不承担当前状态说明。

不再维护独立W5接手文件。接手、冻结交付和人员拆分均直接写在`plan.md`。

## 2. 当前事实快照

- W0/G0、W2/G2、W3/G3、W4/G4已经通过；W1只冻结当前可取得的模型、输入、量化和架构事实，G1未整体通过。
- 首个真实ResNet50算子是`node-0004`的`hwop-0004-00~01`：1×1、stride 1、`[16,64,56,56] -> [16,64,56,56]`。
- 累加JSON与8份64通道requant JSON已由正式`ndp-sim-ref` encoder解析、placement并生成128/64位bitstream；HIGH-4 selector为`mem/src/dst=4/1/1`，`ping_pong=0`。
- `NDPFuncModel` request schema 0.3实际携带requant manifest、8份JSON原文及SHA，并验证GA常量、HIGH-ring slice、16B地址、LC `1/9408/2352`和唯一UINT8 flush。
- NDP对28个slice各生成两个staging D并inverse回canonical D；单坐标、首tile和全算子INT32 P/UINT8 D均与W3 golden bit-exact。
- 以上证明“配置绑定的软件功能模型”和golden一致；不证明逐周期LC/stream/buffer、bitstream解释器或真实硬件通过。因此G5/G6/G8仍为false。
- 首例唯一配置侧阻塞是`B_EXECPLAN_TYPED_TRANSPORT`，只影响自动重建/扩展和整网执行，不妨碍硬件组手工加载冻结包。
- 根仓硬件交付业务冻结为`e9b6492098c2101aa86afd83bf95e8024fa6e8df`；数值闭环为`1388dede4aac53a77d02dec0b24db0ad2d35ef1f`；NDP冻结为`1d3181d832d7a409af779215e4aa590d03bd8ed3`。其后的纯文档提交不是新数值冻结。

冻结包`artifacts/w5/hwop-0004-00/hardware_freeze/`：

- freeze ID：`f687debd0215f1d29b6ca94176c4e9cbcf20434d58bce57c430129edb8922d5f`；
- manifest SHA-256：`72e17cb52c2948f86fe6b0e9b2715de57c5404a72a04f9514247f174e8a95550`；
- preflight SHA-256：`8dd0d61bacd0f840f09b038a16180dac4d7408878857d5b10143f684bf2f0c80`；
- canonical P/D SHA-256：`1ec864892d82279beff561927500f55ebec636daf2fb7c624a1e153dd5e17532` / `2793bbe64e2b3289657f1c77bad61ebc54a4672791093d5c19a66ca742e7376e`。

## 3. 仓库与权威边界

根仓负责编排、合同、lowering、golden、28-slice layout、target配置审计、W5 preflight、硬件冻结导出和比较。参考仓由`repos.lock.json`锁定：

| 仓库 | 锁定版本 | 本项目职责 | 不能误称为 |
|---|---|---|---|
| `ndp-sim-ref` | `e299b2804448242d1589b3e58ed7c5a9a5eca09f` | 正式JSON schema/parser、placement、128/64位bitstream encoder、execplan参考 | 数值功能模拟器或硬件执行器 |
| `NDPFuncModel` `conv_func` | `1d3181d832d7a409af779215e4aa590d03bd8ed3` | Conv功能模型、target-config request适配、physical staging/inverse与P/D比较 | 逐周期目标机、bitstream解释器或RTL |
| `CGRA_SIM` | `53c41e02c294bcc54379e686dc9d25bbb93919fa` | 旧ResNet计划、ONNX/QNN语义、软件算子和性能参考 | 当前28-slice配置真值 |

目标RTL静态证据来自`Trassic2.0_RTL@e3bdebba95dec36ee8eba43caa92a326a88392cd`。当前只冻结静态审计与W4物理基线，`clean_elaboration_claimed=false`，没有精确首例硬件P/D证据。

ADR-008裁决正式配置来自`ndp-sim-ref`；ADR-009与`contracts/hardware_approval.json`按hash批准DeepSeek公共物理基线。旧16-slice代码、CSV、注释和学长伪代码都是解释证据，不能单独覆盖正式parser与真实数值结果。

## 4. 根仓代码地图

### 模型、lowering与golden

- `resnet50_pipeline/model/onnx_graph.py`：正式ONNX图和initializer读取。
- `resnet50_pipeline/lowering/`：模型节点到硬件原子算子的一对多映射。
- `resnet50_pipeline/golden/`：ORT节点golden及Conv accumulate/requant等子步骤golden。
- `resnet50_pipeline/manifest.py`、`records.py`：稳定ID、shape、dtype、layout与provenance。

### 28-slice layout与合同

- `topology28.py`、`profile28.py`、`layout.py`：28-slice拓扑、profile和公共入口。
- `conv28_layout.py`、`pool28_layout.py`、`add28_layout.py`、`matmul28_layout.py`、`simple_layout.py`：七族physical bundle及inverse。
- `contracts/architecture.json`、`deepseek_rtl28_physical_baseline.json`、`resnet50_rtl28_w4_delta.json`：W4机器合同。
- 文件名含`16`的layout和旧network dry-run只作历史/fixture，不能进入RTL28正式链。

### 首个真实1×1闭环

- `contracts/conv_1x1_lc_pe_stream_semantics.{md,json}`：逐LC/PE/stream/port语义裁决。
- `conv_1x1_real.json`；生成/编码入口为`tools/generate_conv_1x1_real.py`、`tools/run_conv_1x1_encoder.py`。
- `conv_1x1_requant_real/manifest.json`和`shard-00~07.json`；生成/编码入口为`tools/generate_conv_1x1_requant_real.py`、`tools/run_conv_1x1_requant_encoder.py`。
- `contracts/typed_config_parameter_contract.json`：W3 `hw_op/tensor/qparams`到目标字段的typed合同。
- `target_config_audit.py`：正式配置解析和fail-closed字段/资源/连接审计。
- `w5_conv_preflight.py`、`tools/run_w5_conv_preflight.py`：绑定配置、physical bundle、NDP request和三档P/D。
- `adapters/ndp_rtl28_functional.py`：根仓到NDP config-bound入口的适配。
- `conv_1x1_hardware_freeze.py`、`tools/export_conv_1x1_hardware_freeze.py`：确定导出硬件输入/golden、配置、bitstream和地址表。
- `tools/compare_conv_1x1_hardware_dump.py`：读`P|D/slice-XX.bin`，inverse到canonical NCHW并报告首错。

### 管线与校验

- `pipeline.py`、`backends.py`、`artifacts.py`、`cli.py`：阶段DAG、backend、产物、cache/resume和CLI。
- `tools/sync_repositories.py`：锁定仓库与RTL证据校验，不能用普通`git status`替代。
- `tools/validate_hardware_approval.py`、`w4_audit.py`：批准合同与G4证据校验。
- `tests/`：根仓回归；固定测试数量只是历史快照，验收以零失败为准。

## 5. 两个参考入口怎样使用

### `ndp-sim-ref`

- `jsons/`：DeepSeek单算子模板；
- `bitstream/`：正式解析、字段映射、placement、mapping review和编码；
- `model_execplan/`：多算子handler、地址规划和网络配置入口；
- `generate_python_golden/`、`address_remapping/`：DeepSeek数据布局和地址参考。

判定顺序：parser接受 -> 范围/资源校验 -> placement零违规 -> parsed dump/mapping review -> 两种bitstream确定性 -> 数值链实际消费同一配置。前五项不能替代最后一项。

### `NDPFuncModel`

真实Conv功能入口位于`conv_func`分支。根仓adapter构造request并调用其功能链；首例已从旧固定3×3调用扩为配置绑定的1×1、28-slice、64-channel requant路径。

旧`main_CONV_N2N.py`围绕3×3邻域、旧输入组织和固定循环。它过去能正确跑3×3，是因为数据尺寸、padding、weight索引和循环边界共同满足写死假设，不代表任意Conv已参数化。扩第二个1×1、3×3或53层Conv前，必须由统一request/schema驱动shape、stride、padding、channel、tile、qparams和flush；禁止复制旧main常量形成正式结果。

## 6. 本地执行入口

```powershell
.\.venv\Scripts\python.exe tools\sync_repositories.py verify
$env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe tools\run_w5_conv_preflight.py
.\.venv\Scripts\python.exe tools\export_conv_1x1_hardware_freeze.py
.\.venv\Scripts\python.exe tools\compare_conv_1x1_hardware_dump.py --freeze-root artifacts\w5\hwop-0004-00\hardware_freeze --dump-root <hardware-dump-root> --output <comparison.json>
```

编码器参数以对应`tools/run_conv_1x1*_encoder.py --help`为准；禁止手写位串或绕过正式parser。除非模型/hash/合同失效，不为文档检查重建约951 MB的W3数据。硬件冻结目录是可再生产物，通常不进入普通Git历史。

## 7. 证据边界

- JSON可解析、placement成功、bitstream确定，只证明配置编码链成立。
- NDP与golden P/D bit-exact，证明当前request、JSON原文/SHA、physical bundle和数学实现对首例一致；不证明bitstream逐周期执行。
- DeepSeek JSON曾被硬件执行，只证明通用字段/加载能力存在；不证明当前1×1精确配置、地址、qparams和P/D已在硬件通过。
- 硬件验收必须记录版本、freeze ID、命令/协议、退出状态、原始dump、inverse和首错，否则G8不升级。
- 第二个1×1和shape-family在硬件证据前统一标`candidate`。

## 8. 协作与Git规则

- 公共schema、合同、selector/ping-pong规则、Git集成和全量回归串行维护；硬件反馈与扩展不得同时改写真值文件。
- 硬件负责人只消费冻结包并产生dump/比较记录；扩展负责人从同一冻结提交派生第二实例。
- managed worktree只保证tracked文件和`.worktreeinclude`的小元数据；不以junction/symlink共享Local `.venv`、参考仓或大产物。正式W3、参考仓或全量回归在Local执行。
- 不覆盖、移动或改写未跟踪的`.agents/conv_full(2).json`和`.agents/conv_full(2).txt`。它们是未测试伪代码原件，不是正式配置源。
- 修改前检查`git status --short`，保留无关用户改动；禁止无批准使用`git reset --hard`、`git checkout --`或删除恢复点。
- 业务/合同/规则变更须聚焦测试和原子提交；台账记录完整hash、父提交、范围、验证与回退。
- **只有操作者明确要求“推送”“发布到GitHub”或“同步云端”时才允许执行远端推送。** 本地提交、阶段完成、用户要求“保存”或普通任务结束都不自动授权`git push`；不得为了备份或方便自行推送。
- 根仓既有直接推送远端为`origin=https://github.com/crithbo/resnet50_int8.git`。普通推送使用现有Git凭据，不把GitHub插件或`gh`当作前置；只有用户明确要求PR、Issue、Review或插件操作时才使用对应GitHub工具。
- 用户授权直接推送后，固定执行：`git status -sb`核对范围；`git fetch origin`刷新远端；用`git rev-list --left-right --count origin/main...HEAD`确认远端独有提交数为0；只执行非强制`git push origin HEAD:main`；最后用`git ls-remote origin refs/heads/main`确认远端SHA与`git rev-parse HEAD`一致。若远端分叉、仓库URL异常、认证失败或需要force，立即停止并报告，不自动改写远端历史。
- 推送只传递已提交对象。工作树中的未跟踪/未暂存文件不得为“顺便上传”而加入提交；本项目尤其要继续排除`.agents/conv_full(2).json/.txt`，除非操作者另行明确授权。

## 9. 文档更新规则

- 当前任务、阻塞、负责人或接手命令变化：更新`plan.md`。
- 稳定代码入口、仓库职责或长期边界变化：更新`agent.md`。
- 真实配置/数值证据修正规则：更新`rules/算子配置规则.md`并补测试。
- 工作包完成或结论被替代：追加`history.md`，从`plan.md`移除详细完成步骤，只留状态摘要。
- W4历史只在需要时查`W4_ARCHIVE.md`；不再建立独立接手文件。
