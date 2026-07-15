# W5 新对话接手单

最后更新：2026-07-15

状态：**W4/G4已结束；W5首个真实1×1的累加、64通道requant配置与两方P/D闭环已经冻结，可交硬件组手工加载，但G5/G6/G8仍未批准。** 本文件是新对话的最短接手入口；执行口径仍以`.agents/plan.md`为唯一权威计划。本对话及`.agents/W4_ARCHIVE.md`只用于追溯W4事实、错误和裁决。

当前冻结恢复点：根仓`e9b6492098c2101aa86afd83bf95e8024fa6e8df`，NDPFuncModel `1d3181d832d7a409af779215e4aa590d03bd8ed3`；其中数值闭环业务提交为根仓`1388dede4aac53a77d02dec0b24db0ad2d35ef1f`。累加配置`conv_1x1_real.json` SHA-256为`a20641cfcf65068c3ca31d710a0ef45d28a53cbf80d5e246ce54f0de3fe16f2c`；requant manifest SHA-256为`4424a6524dcdaaf1933b57875e4f3a1ae7edb11321dd02b692bbed51b82b274f`；最终preflight SHA-256为`8dd0d61bacd0f840f09b038a16180dac4d7408878857d5b10143f684bf2f0c80`。硬件交付目录`artifacts/w5/hwop-0004-00/hardware_freeze/`由冻结提交确定生成，freeze ID为`f687debd0215f1d29b6ca94176c4e9cbcf20434d58bce57c430129edb8922d5f`。当前首例未解决配置阻塞只有`B_EXECPLAN_TYPED_TRANSPORT`，它不妨碍硬件组手工加载冻结JSON/bitstream与数据。

## 1. 接手时只需读取什么

按以下顺序读取，不需要重新扫描三个参考仓或重跑约951 MB的W3产物：

1. 本文件；
2. `.agents/agent.md`的“五分钟接手摘要、协作原则、当前闭环状态”；
3. `.agents/plan.md`的“当前总体状态、当前可立即执行队列、W5、W6”；
4. `.agents/rules/算子配置规则.md`的第1、8～10、12.6、16.5节；
5. 只有需要追溯W4判断时，才读`.agents/W4_ARCHIVE.md`、ADR-007～009和`history.md`对应日期。

`history.md`是按时间记录的事实，不是当前任务清单。旧条目中的“G4未通过”“等待clean elaboration”“下一步C8”只代表当时状态，不能覆盖2026-07-14的W4闭环结论。

## 2. 三条无副作用接手检查

在Local主工作区依次运行：

```powershell
git status --short
.\.venv\Scripts\python.exe tools\sync_repositories.py verify
$env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

预期结果：

- 根工作树没有未解释改动；
- RTL28静态证据、`CGRA_SIM`、`ndp-sim-ref`和`NDPFuncModel`全部匹配`repos.lock.json`；
- 当前冻结点根仓全量回归为249/249，NDPFuncModel为19/19。若测试数量因后续正常提交增加，应以“零失败”及`history.md`最新台账为准，不要求机械保持固定数量。

若任一检查失败，先定位环境、lock或文档提交差异，不要立即重建W3、重跑ORT或修改W4批准合同。

## 3. 不可混淆的恢复点

- W3业务封版：`35a4fde106d102b0e165e7eb13d60f7dd980db71`。
- W4业务闭环：`952a96b48416ed2ea1bd2d3068a541ab3dd43625`，父提交`c7eccc5a664d52f8f00695b7427e673b22743f3c`。
- W4闭环台账：`3b5fff4d2007d2acdd7793bc69988b1d6f98be40`，父提交`952a96b48416ed2ea1bd2d3068a541ab3dd43625`。
- 新对话实际基线：以接手时`git rev-parse HEAD`为准；本文件之后的纯文档交接提交不会改变W4业务证据。

`ADR-009-deepseek-baseline-inheritance.md`被`contracts/hardware_approval.json`按SHA-256绑定。除非明确执行新版本批准迁移，否则不得为了措辞整理直接修改ADR-009。

## 4. W4已经批准了什么

- 目标为`Trassic2.0_RTL@e3bdebba95dec36ee8eba43caa92a326a88392cd`、28个slice。
- 正式profile为`w4_deepseek_hybrid28_resnet50_v1`，每个网络算子使用完整28-bit mask；算子通信域分别为`local`、`HIGH-4`或未来可能使用的`LOW-28`。
- 当前七族绑定：simple/local、view/local、conv/HIGH-4、maxpool/local、add/local、GAP/local、matmul/HIGH-4；没有选中LOW-28族。
- 七个选中layout、93条runtime边、91条qparam链、16个残差Add、79个runtime tensor生命周期/alias和静态成本均通过W4门。
- DeepSeek公共物理合同、ResNet W4差异合同、正式配置来源和具名批准合同均由版本/hash校验。
- G4 v2为12/12 true，`g4_status=passed`、`w5_authorized=true`，同时明确`clean_elaboration_claimed=false`。

W4没有批准：INT8 SA数值行为、bias/psum/requant寄存器语义、逐实例qparams写入、目标数值模拟器、整网地址计划、板级load/start/wait/dump或任何golden=simulator=hardware结果。

## 5. W5第一个原子工作包【已形成冻结提交】

第一包已按单线程完成。冻结证据如下：

- `conv_1x1_real.json`保持`mem/src/dst=4/1/1`、`ping_pong=0`，正式编码为46条连接、constraint cost 0；128/64位bitstream、parsed dump和mapping review已重建。
- `conv_1x1_requant_real/manifest.json`与8份原始JSON覆盖64个通道；NDP request schema 0.3携带manifest/JSON原文及各自SHA，逐份验证GA常量、HIGH-ring slice、16B地址、LC `1/9408/2352`和每个逻辑输出唯一flush。
- NDP对28个slice各写低/高两个staging D，地址偏移`904400/979664`，读回后inverse为canonical D；单坐标、首tile 150,528元素和全算子3,211,264元素的P/D均为0 mismatch。
- 正式requant encoder的8个shard均为21条连接、constraint cost 0，两次生成逐文件一致；`artifacts/w5/hwop-0004-00/preflight.json`保存配置绑定、28组双staging写回和三档hash证据。
- `tools/export_conv_1x1_hardware_freeze.py`确定导出339个受hash约束的交付文件：28-slice physical A/B/bias/qparams、physical/canonical golden P/D、10份配置、18份128/64位bitstream和含56个staging输出区的地址表；总目录约41.9 MB，重复导出manifest逐字节相同。`tools/compare_conv_1x1_hardware_dump.py`按`P|D/slice-XX.bin`读硬件dump，inverse回canonical NCHW并报告首错。
- `B_REQUANT_TARGET_NUMERICS`已从该首例阻塞清单删除；NDP仍是config-bound功能模型而非逐周期LC/stream/buffer或bitstream解释器，因此G5/G6/G8保持false，不能把两方一致写成硬件通过。

硬件交付与比较命令：

```powershell
.\.venv\Scripts\python.exe tools\export_conv_1x1_hardware_freeze.py
.\.venv\Scripts\python.exe tools\compare_conv_1x1_hardware_dump.py --freeze-root artifacts\w5\hwop-0004-00\hardware_freeze --dump-root <hardware-dump-root> --output <comparison.json>
```

下面A～D保留为首包形成过程与复核口径，不再是待办清单。不要回退到只验证累加JSON，也不要先批量生成53层Conv配置。

### A. 先定位DeepSeek实际数值执行入口

沿已经完成的DeepSeek链追踪：网络/单算子JSON如何被patch、bitstream如何被消费、哪个程序真正执行LC/stream/buffer/SA/GA、D从哪里dump。必须取得可运行命令、版本、输入包、退出码和D输出格式。

- 若找到目标JSON/bitstream数值模拟器，先做最小只读probe并登记能力。
- 若只找到`write_emulator_bundle()`或数据打包脚本，不能称为模拟器执行。
- `NDPFuncModel`仍只是Conv功能参考；除非证明它读取同一目标JSON/bitstream并执行对应配置，否则不能替代目标模拟器。
- 若正式执行入口确实不在当前仓库，明确记录W6阻塞；W5可继续做一个实例的配置preflight，但不得扩展为整网生成器或宣称数值通过。

### B. 选择一个真实但尽量简单的Conv

推荐从`hwop-0004-00`（`node-0004`，1x1、stride 1、`[16,64,56,56]→[16,64,56,56]`）选取一个真实tile作为首例。它比Conv0的7x7/stride2/padding更容易隔离SA、bias、INT32 psum和requant，同时仍直接使用正式模型的weight、bias与per-channel qparams。

如果审查后发现另一个真实1x1实例更符合现有DeepSeek模板接口，可以调整`hw_op_id`，但必须在计划和台账中记录选择理由，不能改用脱离正式模型的纯合成参数冒充W5实例。

### C. 完成配置preflight

从`contracts/typed_config_parameter_contract.json`读取该实例的shape/dtype/weight/bias/qparams，建立字段级provenance，并补齐：

- UINT8 activation × INT8 weight；
- INT32 bias与psum的首/中/末K生命周期；
- per-channel requant、nearest-even、output zero point和UINT8 saturation；
- 1x1 shape到LC、stream、buffer、SA/GA、tail和地址占位的联动；
- 生成前字段范围/资源/未知字段fail-closed；
- 固定环境下patched JSON、mapping review和bitstream逐字节复现。

这一步达到的是G5配置证据，不是G6数值证据。

### D. 尽早做golden+目标模拟器数值验收

第一份配置形成后，不要先横向扩展shape族。用同一physical A/B/bias/qparams和同一JSON/bitstream运行目标模拟器：

1. dump末次requant前的INT32 psum和最终physical UINT8 D；
2. 用W4批准的inverse layout恢复logical P/D；
3. 与W3 `ConvInt32Accumulate`及节点输出golden做整数bit-exact比较；
4. 首错必须回报`hw_op_id`、slice、逻辑坐标、物理地址、配置字段和三方值。

因此，JSON/bitstream确定性是必要的配置门，golden=target simulator才是该算子的数值验收。两者不能互相替代。若模拟器入口尚缺，配置证据只能标`G5-preflight`，不能写成“Conv已通过”。

## 6. 第一包停止条件

出现任一情况即停止扩展并记录阻塞：

- 找不到真正消费目标JSON/bitstream的数值执行器；
- INT8 SA、bias/psum或requant字段只能靠旧16-slice位串猜测；
- typed qparams不能无损进入实例配置；
- 1x1实例出现unresolved control、字段截断或未知tail；
- physical D不能由W4 inverse layout还原；
- simulator与golden不一致。

禁止事项：不生成整网W5 JSON/bitstream，不开始W7 execplan，不宣称G5/G6/G8通过，不修改ADR-009来绕过缺失证据。

## 7. 冻结后的人员拆分

首个Conv闭环已经冻结，可以按两个互不改写真值的角色拆分：

- 硬件协作负责人只使用根仓`e9b6492...`与NDP `1d3181d...`对应镜像，直接接收`artifacts/w5/hwop-0004-00/hardware_freeze/`；运行真实N2N并把dump保存为`P|D/slice-XX.bin`，用冻结比较工具记录首错逻辑坐标，不修改公共生成器。
- 扩展负责人从同一冻结点处理第二个代表性1×1与shape-family测试，继续使用HIGH-4 `4/1/1`、LOW-28 `28/0/0`规则；未有硬件证据的扩展结果统一标candidate。
- `B_EXECPLAN_TYPED_TRANSPORT`留给自动扩展和整网执行，不阻塞上述手工单算子硬件加载。公共schema/合同、selector与ping-pong规则、Git集成和全量回归仍串行维护。
