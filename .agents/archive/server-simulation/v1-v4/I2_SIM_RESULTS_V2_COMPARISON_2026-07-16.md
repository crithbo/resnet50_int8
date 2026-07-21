# I2 第二轮服务器仿真提取与三方比较报告

日期：2026-07-16

## 结论

第二轮修复了第一轮输入运输问题，但没有完成整条硬件执行链。当前机器结论是：

```text
status = returned_incomplete
comparison_verdict = three_way_not_comparable
```

不能报告硬件数值mismatch，也不能报告三方通过。Golden与config-bound NDP仍全量一致；硬件侧只启动了1/9个runtime stage，没有形成可比较的P/D。

> 后续完整展开 28 个 slice 的 local trace 后，首个卡点已进一步前移到输出读改写：56 次 P scratch 读取全部返回 X，造成 56 个写请求但 0 个写数据握手、0 个 slice 完成；1/9 是其后果。精确证据、v3 修复包和服务器插桩位置见 `.agents/archive/server-simulation/v1-v4/I2_SIM_RESULTS_V2_DEEP_DIAGNOSIS_2026-07-16.md`。本报告以下关于“只修 command engine”的旧判断由该深度报告取代。

## 证据身份

- 原始压缩包：`sim_results_v2.zip`
- 压缩包SHA-256：`9f6bba9ddcbdb75c553da9464d3d1af98b4d06a50cc27d3758cf596989e8c872`
- v2 package manifest SHA-256：`967bedebe150cdbe5b315d4ae82cbcaf7eaec59e38d5d1a84b2c679c5cefb7ab`
- freeze ID：`f687debd0215f1d29b6ca94176c4e9cbcf20434d58bce57c430129edb8922d5f`
- freeze manifest SHA-256：`72e17cb52c2948f86fe6b0e9b2715de57c5404a72a04f9514247f174e8a95550`
- 机器报告：`artifacts/w5/hwop-0004-00/hardware_server_run_v2_comparison/comparison.json`

## 输入预装结果

v2的运输修复已被服务器trace直接确认：

- 86/86个mandatory probe都在目标Bank line观察到正确128-bit写入；
- 86/86个预期值都在对应slice/bank的MC read-data日志中，于预装写入之后再次出现；
- slice0的A、B、bias、accumulate config和execplan首字均命中runner合同；
- `strict_readback_status=passed`。

重要解释：`bank*_frame.log`中读请求行的`Data`字段是请求时占位信号，不能作为真实返回值。真实Bank返回必须读取`bank*_mc_rdata.log`。第一轮MC日志没有命中冻结A/B/bias且有大量零返回；第二轮MC日志已命中全部86个探针。因此第一轮的运输故障成立，但后续诊断不得再把frame请求侧零值当作MC返回值。

## runtime完成度

`gexec2slice.log`共307条分发记录，其中：

- 只在`1916987000 ns`观察到一次runtime `Start_Comp`广播；
- 该次广播覆盖28个slice，所以原始opcode记录为28条，但只代表1个stage；
- runner合同要求9个stage：1个accumulate和8个requant；
- 实际完成度为1/9，后续8个requant没有获得`Start_Comp`；
- `terminal_output.txt`只记录加载过程，没有绑定本次execplan的9-stage完成序列。

压缩包中的`local_*`、`local_layer*`和`nrm_buf_*`日志没有与9-stage runtime序列及最终Bank dump建立唯一身份绑定，不能替代post-run Bank镜像进入正式P/D比较。

## P/D可比性

- `dump_contract.json`规定的P目标区：Bank frame中0次写事务；
- 两个staged-D目标区：Bank frame中0次写事务；
- 压缩包中不存在`sliceXX_BankYY_data.bin/.txt`形式的28份post-run Bank dump；
- 因此硬件P与D的元素数、SHA、mismatch和首错坐标均不可计算。

三方状态：

| 比较 | 状态 | 结果 |
|---|---|---|
| Golden ↔ config-bound NDP | passed | P/D各3,211,264元素，0 mismatch；SHA分别为`1ec864...`与`2793bbe...` |
| Golden ↔ hardware | not_comparable | 无完整硬件P/D |
| config-bound NDP ↔ hardware | not_comparable | 无完整硬件P/D |

## 下一轮修复目标（经深度诊断更新）

无需修改Conv数学、A/B角色、地址公式或已声明的输入数值。下一轮先解决运行时 scratch 初始化，再判断 command engine：

1. 使用 `hardware_execplan_server_v3` 的 SCA manifest，显式加载 28 个 P 和 56 个 staged-D zero payload；若改用稀疏 Bank_data，必须先清零 Bank RAM；
2. `Start_Comp` 前真实回读全部 170 个 probe，任一 X/mismatch 都禁止启动；
3. 在输出 RMW read-return 和 write-request→write-data 之间加断言/watchdog；
4. 先确认 28 个 slice 均产生写数据并完成，再检查 command engine 是否获取后续 8 个 stage；
5. 第9个stage完成后导出28份Bank0镜像，dump前不得重新加载初始Bank_data；
6. 回传完整gexec/local/completion日志和`sliceXX_Bank00_data.bin/.txt`，再运行正式P/D比较器。
