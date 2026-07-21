# I2 首轮硬件仿真错误报告（2026-07-15）

- 报告ID：`I2-SIM-20260715-001`
- 状态：`returned_incomplete`
- 主分类：`input_preload_failure_and_early_termination`
- 数值裁决：**尚不可比较，不是“硬件数值不一致”**。

## 1. 证据身份

- 原始回传：根仓`sim_results.zip`；SHA-256为`919f24c7f9bfacb5b90d5a9abaff043046378dfb9a2dd194ed5ccca63d9882c2`。
- 档案规模：3012个条目，其中2634个文件；解压总字节数1,507,822,077。档案只有日志，没有可绑定本次运行的仿真器/RTL/固件版本、运行命令、退出状态或freeze manifest。
- 目标运行包：`artifacts/w5/hwop-0004-00/hardware_execplan/`。
- freeze ID：`f687debd0215f1d29b6ca94176c4e9cbcf20434d58bce57c430129edb8922d5f`。
- freeze manifest SHA-256：`72e17cb52c2948f86fe6b0e9b2715de57c5404a72a04f9514247f174e8a95550`。
- 预期执行：175个128-bit execplan beat，9个runtime stage（1个accumulate、8个requant），P/D各3,211,264个元素。
- 冻结canonical P/D SHA-256：P为`1ec864892d82279beff561927500f55ebec636daf2fb7c624a1e153dd5e17532`，D为`2793bbe64e2b3289657f1c77bad61ebc54a4672791093d5c19a66ca742e7376e`。

## 2. 三方结论

| 比较 | 结果 | 说明 |
|---|---|---|
| Golden ↔ 配置绑定NDPFuncModel | `pass` | 单坐标、首tile、全算子P/D均bit-exact；首坐标P=`1225`、D=`4` |
| Golden ↔ 本次硬件仿真 | `not_comparable` | 输入未被正确读出，运行未完成，未形成合格P/D dump |
| NDPFuncModel ↔ 本次硬件仿真 | `not_comparable` | 同上 |

因此本报告不能升级G6/G8，也不能据此修改算子数学、selector、requant或freeze真值。

## 3. 日志中的直接证据

### 3.1 配置传输指纹能够对上

- 当前accumulate配置的70个预期64-bit字与70个实际字完全一致，顺序为每个128-bit beat先低64位、后高64位。
- 28/28个slice的配置片段均精确匹配。
- 这说明当前日志至少进入了目标accumulate配置流；它不能证明输入Bank预装、完整stage调度或数值执行正确。

### 3.2 输入Bank首次读取失败

- A的预期首个128-bit字为`00000e0c1f000f11120000091c091b11`，28个slice的首次读取全部为0。
- B的预期首个128-bit字为`000081e0e800fc1cf6071310e6eb8202`，28个slice的首次读取全部为0。
- bias的预期首个128-bit字为`ffee347afffffbd500000d0f00006adc`，首次读取为27个slice取0、1个slice取`x`。
- 所以最早可确认的错误位于“Bank_data加载/保存/读取可见性”一带，尚未到可以裁决卷积P数值的阶段。

### 3.3 执行链不完整

- gexec日志只观察到accumulate阶段在28个slice上的`Start_Comp`，没有8个requant stage的配置/启动证据。
- 当前目标日志中没有`slice completed`，没有`Total handshakes`，也没有完整退出状态。
- `Start_Comp`之后，目标P、D0、D1地址区均未观察到有效Bank write。
- slice 2/6上P区域的614次零写发生在启动前，按时间顺序属于初始化/清零，不能当作P结果。

### 3.4 不纳入本次freeze比较的日志目录

`local_layer0_0-42`、`local_layer0_op0-42_1`、`local_op23-42`包含43次启动、类似浮点的数据或不同工作负载痕迹，但没有当前gexec/config身份和D输出，不能在缺少manifest绑定时拼接成当前freeze证据。

### 3.5 后续取数必须沿用的解释规则

- `bank_frame`记录的是128-bit行地址，转换为字节地址时左移4位，例如`0x250d → 0x250d0`。
- 同一地址按日志时间顺序采用last-write-wins。
- 日志展示的128-bit十六进制字转换为内存时按little-endian字节顺序解释。
- D0/D1是`[sample,H,W,8]`两个half，必须沿最后一个通道轴合成`[sample,H,W,16]`；禁止按两个文件首尾直接拼接。

## 4. 后续修复分流

### 4.1 仿真侧优先处理（当前已有直接证据）

1. `S1_INPUT_PRELOAD`：核对28份Bank_data是否真正加载到与execplan相同的slice/bank/address空间；在`Start_Comp`前增加A/B/bias精确readback，至少首行必须逐字节等于运行包。
2. `S2_RUNNER_COMPLETION`：核对runner为何只进入accumulate而没有跑完8个requant stage；排查timeout、提前停止、完成握手、command engine循环和dump时机。
3. `S3_EVIDENCE_PACKAGING`：回传版本、真实命令、退出码、运行时间、freeze/manifest身份、完整原始日志和运行后28份Bank dump，避免再次只能猜测工作负载身份。

### 4.2 算子侧条件触发（当前没有直接数值失败证据）

只有在S1～S3满足后才进入：

- 若P首先不一致：按input A/B role与地址 → selector/HIGH-ring → bias/K-stage → overflow顺序定位。
- 若P一致而D不一致：按requant shard/channel覆盖 → multiplier/zero-point → rounding/saturation → staging/唯一flush/inverse顺序定位。
- 若配置字段或地址合同确实需要修改，先在软件重现并补负向测试，再创建新的freeze ID；不得覆盖只读v1冻结包。

## 5. 暂停与恢复条件

- 本报告暂存问题，不立即打断另一窗口正在执行的E4 Conv泛化。
- 待该窗口的泛化工作完成、操作者明确要求后，再由指定窗口按本报告恢复I2修复。
- 重新运行前必须先通过输入readback门；运行必须完成全部9个stage，并导出28份满足dump合同的Bank镜像（每份至少1,054,928字节）。
- 使用`tools/compare_conv_hardware_execplan_dump.py`生成machine-readable三方报告。只有P/D各3,211,264元素均0 mismatch且SHA命中冻结值，才把I2从`returned_incomplete`升级为硬件数值通过；否则保存首错坐标并按4.2分流。

配套机器可读记录仍位于：`.agents/I2_SIM_RESULTS_ERROR_REPORT_2026-07-15.json`。
