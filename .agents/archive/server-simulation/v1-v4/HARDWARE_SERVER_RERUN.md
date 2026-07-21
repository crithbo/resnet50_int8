# 首个 Conv 硬件服务器重跑说明

最后更新：2026-07-16

本文件只说明 `node-0004/hwop-0004-00~01` 首轮服务器仿真失败的根因、修复包和重跑门禁。项目总览见 `.agents/agent.md`，当前工作状态见 `.agents/plan.md`。

> **历史说明：当时执行版本已经升级为v4。** v1/v2/v3及前三轮返回只作历史诊断证据，禁止覆盖。v4完整身份、ZIP哈希和返回合同见`.agents/archive/server-simulation/v1-v4/I2_HARDWARE_EXECPLAN_V4_HANDOFF_2026-07-16.md`。以下章节只用于解释运输、scratch与170点门禁的形成过程；当前运行命令不得从本文取得。

## 1. 结论

首轮结果不是 Conv 数值不一致，也不是 execplan 地址或配置流错误。直接根因是：

> 服务器 SCA preload 按“逐行 0/1 文本”读取输入文件，但旧运行包在 `sca_cfg.json` 中把 A/B/bias 等输入指向原始二进制 `.bin`。loader 把原始数据中的 `0x0A` 当成换行，只装载少量无效行，并把数据写成 0/X。

直接证据：

| 对象 | 旧包格式 | 源文件中的 LF 数 | 服务器实际装载 | 结果 |
|---|---|---:|---:|---|
| B/slice-00 | 1024 B raw `.bin` | 13 | 地址 `0x24c0..0x24cc` 共13行 | 全0 |
| bias/slice-00 | 64 B raw `.bin` | 1 | 地址 `0x2500`共1行 | 0/X |
| accumulate config | 128-bit `0/1`文本 | 正常文本行 | 70个64-bit字，28/28 slice精确 | 正确 |
| execplan | 128-bit `0/1`文本 | 正常文本行 | 首阶段命令完整 | 正确 |

trace中的局部地址也正确：`0x24c0`是16-byte行地址，左移4位即B的byte地址`0x24c00`；A为`0x0`，bias为`0x25000`。所以不应修改Conv地址、A/B角色、selector、requant或freeze数值。

只看到1个accumulate、没有8个requant，是上述问题的后果：command engine在第一阶段等待slice完成握手；输入为0/X后第一阶段没有完成，因此后续命令没有获得执行机会。这不是execplan只生成了一个stage。

### 1.1 第二轮更新（2026-07-16）

`sim_results_v2.zip`证明输入运输修复已经生效：86/86个A/B/bias/config/execplan目标写入正确，86/86个预期值在写入后的MC read-data中出现。完整展开28个slice的local trace后，最早阻塞已定位到首次输出RMW：P的两个128-bit line在每个slice都返回X，合计56次X；随后有56个输出写请求，但0个write-data握手、0个slice完成。command engine停在1/9是等不到stage-complete的后果。详细机器证据见`artifacts/w5/hwop-0004-00/hardware_server_run_v2_deep_diagnosis/comparison.json`，解释见`.agents/archive/server-simulation/v1-v4/I2_SIM_RESULTS_V2_DEEP_DIAGNOSIS_2026-07-16.md`。

注意：`bank*_frame.log`读请求行的`Data`字段不是MC实际返回值，返回数据必须读取`bank*_mc_rdata.log`。第三轮先用v3显式初始化P/staged-D runtime scratch，并在输出RMW和write-data链加断言；只有28个slice均完成后仍停在1/9，才检查command engine聚合和下一exec beat。

## 2. 历史v3修复包（不得再作为下一轮输入）

第三轮服务器曾使用：

```text
artifacts/w5/hwop-0004-00/hardware_execplan_server_v3/
```

服务器传输归档为`artifacts/w5/hwop-0004-00/hardware_execplan_server_v3.zip`，大小6,620,258字节，SHA-256为`1aa7f79f1534df45aeea9d208bbd401fa3055156bb8fa5667eff572d98344bde`。解压后必须保留包内相对路径，并先核对该归档SHA；不要把内容覆盖到旧`hardware_execplan/`或v2目录。

旧目录`hardware_execplan/`、v2包、`sim_results.zip`与`sim_results_v2.zip`只保留失败审计，不再用于第三轮重跑。

v3没有修改freeze v1：

- freeze ID：`f687debd0215f1d29b6ca94176c4e9cbcf20434d58bce57c430129edb8922d5f`
- freeze manifest SHA-256：`72e17cb52c2948f86fe6b0e9b2715de57c5404a72a04f9514247f174e8a95550`
- v3 package manifest SHA-256：`4be4a4aa824545dfff3bf1fcb0f06e0cd86e38a81f9d19e25c271550c3e73e63`
- P/D Golden、配置语义、地址local offset与9个runtime stage均不变。

v3在v2正确运输表示上增加确定性scratch初始化和门禁：

1. `sca_cfg.json` 的输入文件改为128-bit binary-text，每行严格匹配 `^[01]{128}$`。
2. `Bank_data/*.txt` 改为32-bit binary-text，每行严格匹配 `^[01]{32}$`。
3. 新增84个runtime scratch zero payload：28个P、56个staged-D half；它们是RAM初值，不是Golden/output预装。
4. 启动前readback门扩为170个：原86个输入/配置探针加84个scratch探针。
5. 保持9阶段完成门：必须观察9次`Start_Comp`、阶段完成握手、`slice completed`和`Total handshakes`，不能用固定sleep替代。

本地包准备验证：

```text
artifacts/w5/hwop-0004-00/hardware_execplan_server_v3_preparation.json
```

准备报告确认28个Bank、350条命令、9个stage和84个scratch payload。170/170 readback必须使用服务器启动前的真实Bank镜像验证；不能用本地稀疏Bank_data直接冒充已清零的服务器RAM。负向检查`hardware_execplan_server_v3_bankdata_without_zero_init_negative_check.json`预期失败，专门证明Bank_data路径必须先清零。

## 3. 服务器预装方式

两种方式只能完整选择一种，不要混用或在执行后重新预装。

### 3.1 方式A：SCA manifest【当前服务器优先】

读取 `hardware_execplan_server_v3/sca_cfg.json`，遍历所有同时包含 `base_addr` 与 `path` 的条目：

- `install/data/**/*.txt`：128-bit binary-text；每行是一个little-endian内存字的数值位串。
- `install/runtime_scratch/*.txt`：P/staged-D的全零128-bit binary-text；这些条目不可跳过。
- `install/cfg_pkg/*`：128-bit binary-text。
- `install/execplan.txt`：128-bit binary-text。
- 禁止把 `.txt` 当raw bytes写入；禁止再使用旧包的raw `install/data/**/*.bin`。

v3共有346个带`base_addr/path`的SCA payload（v2的262个加84个scratch）。终端应报告`JSON config: 346 matrices loaded`；若仍为262，说明服务器实际加载了v2或跳过了scratch条目，必须在`Start_Comp`前停止。

### 3.2 方式B：直接加载 Bank_data

读取全部28个：

```text
Bank_data/slice00_Bank00_data.txt
...
Bank_data/slice27_Bank00_data.txt
```

规则：

- 每行32个`0/1`字符，无`0x`前缀；
- 使用binary parser或SystemVerilog `$readmemb`，不能使用`$readmemh`；
- 每4行组成一个128-bit字：line0 → bits[31:0]，line3 → bits[127:96]；
- 文件第0行对应该slice的Bank0 offset 0；
- **在 `$readmemb` 前先清零整个Bank RAM，或至少清零`runner_contract.json`列出的全部runtime scratch range**；Bank_data是稀疏有效载荷，不是RAM上电初始化镜像；
- 所有28个文件必须加载完成后才能启动command engine。

## 4. 启动前硬门

完成预装后、启动command engine前，按 `runner_contract.json -> preload.readback_gate.probes` 读取全部170个地址，并用四态比较检查“不含X且等于expected”。

slice0最小人工检查值：

| 对象 | byte地址 | 预期128-bit |
|---|---:|---|
| A | `0x00000000` | `0x00000E0C1F000F11120000091C091B11` |
| B | `0x00024C00` | `0x000081E0E800FC1CF6071310E6EB8202` |
| bias | `0x00025000` | `0xFFEE347AFFFFFBD500000D0F00006ADC` |
| P scratch | `0x000250D0` | `0x00000000000000000000000000000000` |
| staged-D 0 | `0x000DCCD0` | `0x00000000000000000000000000000000` |
| staged-D 1 | `0x000EF2D0` | `0x00000000000000000000000000000000` |
| accumulate config | `0x00101C00` | `0x4170000000020002FF21000000004000` |
| execplan | `0x00104000` | `0x4600101C7FFFFFF800000007FFFFFFF9` |

任一probe不一致时必须在`Start_Comp`之前退出，并回传地址、expected、observed。不能继续运行并把结果解释为算子数值失败。

如果服务器能在启动前导出28份Bank镜像，使用：

```bash
python tools/verify_hardware_server_preload.py \
  --package artifacts/w5/hwop-0004-00/hardware_execplan_server_v3 \
  --readback-root <pre-start-bank-dump-root> \
  --output <preload-readback-report.json>
```

只有退出码0且报告中 `execution_authorized=true` 才能继续。

## 5. 执行与完成门

启动参数：

- Exec_Base：`0x00104000`
- Exec_Length：175个128-bit beat
- runtime stage：9（1 accumulate + 8 requant）

runner必须按command engine完成状态推进，不能在第一次`Start_Comp`后结束，也不能用固定等待时间直接dump。在等待stage完成前先加两级局部诊断：输出RMW read-return不得含X；写请求接受后必须在有限周期内出现write-data握手。完成条件：

1. 9个stage按 `runner_contract.json` 中 `expected_runtime_sequence` 顺序启动；
2. 每个stage完成后才允许进入下一stage；
3. 观察到slice完成与总握手统计；
4. command engine报告全部175 beat消费完成；
5. 退出状态为0。

若超时，必须回传最后完成stage、当前stage、command index和完成握手状态；此时仍为`returned_incomplete`，不能进行P/D数值判定。

## 6. 运行后dump与三方比较

完成后导出28份Bank0镜像：

```text
slice00_Bank00_data.bin/.txt
...
slice27_Bank00_data.bin/.txt
```

每份至少1,054,928字节。dump必须发生在执行完成之后，并且不能重新加载初始Bank_data覆盖P/D区域。

比较命令：

```bash
python tools/compare_conv_hardware_execplan_dump.py \
  --package artifacts/w5/hwop-0004-00/hardware_execplan_server_v3 \
  --sim-bank-root <post-run-bank-root> \
  --evidence-root <comparison-evidence-root>
```

最终通过条件：

- P元素数3,211,264，mismatch=0，canonical SHA-256命中冻结值；
- D元素数3,211,264，mismatch=0，canonical SHA-256命中冻结值；
- Golden ↔ NDPFuncModel ↔ hardware三方均可比较且一致。

## 7. 必须回传的运行元数据

除原始日志和28份post-run Bank dump外，必须回传：

- simulator/RTL/firmware版本；
- 完整运行命令、退出码、wall time；
- freeze ID、freeze manifest SHA、package manifest SHA；
- preload readback报告；
- 已完成runtime stage数量及顺序；
- timeout/首错时的command与stage位置。

缺任一身份或完成证据时，只能记录为不完整运行，不能升级G6/G8。
