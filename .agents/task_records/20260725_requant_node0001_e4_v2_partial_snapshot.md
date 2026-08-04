# RequantizeUint8 node0001 E4 v2 非权威中途快照

日期：2026-07-25

## 裁决

`12.zip` 是运行目录中途快照，不是 runner/finalizer 产生的正式回传：

```text
return_kind = RETURN_SNAPSHOT_NONAUTHORITATIVE
e4_status = SERVER_INCOMPLETE
dynamic_baseline = NO_DYNAMIC_BASELINE
counts_as_formal_e4_attempt = false
candidate_release = false
remaining_blocker = B_REQUANT_SERVER_E4_E5
E5_generation_allowed = false
```

原始快照：

- size：`193281` bytes
- SHA256：`5a11aee769a35879e488597f8f10743f4b12738f973db97c145ebc73a9ae8721`
- entries：14
- 分析：
  `server_returns/requant_node0001_e4_v2_partial_12_analysis_20260725.json`
- 分析 SHA256：
  `1231225ed3f62049b923d20c43f4940880dd4ccfe1029c53454cbbce7365b80f`

## 新增的有效证据

- VCS 已解析 NDP 根目录中的 `native_return_observer.svh`；
- compile、elaboration、link 均完成；
- precompile observer 身份门通过，compile 后 observer 逐字节恢复；
- package manifest/payload、RTL tree、11 focused RTL 和 installed namespace
  至少稳定到 post_compile；
- SCA/SCA_D 路径、`Repeat_Num=48` 正确；
- 178/178 preload 写入并读回一致；
- `RequantGuard` 只加载一次；
- 仿真已经启动。

因此 v1 的 observer include 编译问题已被 v2 修复。

## 不能从快照推出的结论

快照只有 1 次 `slice start`、0 completion、0 formal D；没有 error、fatal 或
timeout marker。`sim.log` 在 stock TB monitor 文件初始化尾端中途截断且无 LF，
finalizer 的 exit/status/post-run/post-restore/result/return receipts 全缺失。

所以不能声称：

- 硬件 hang；
- RTL、配置或数值错误；
- 自然完成或正式 E4；
- 第三次正式 E4 attempt。

## 唯一下一检查

先确认服务器现有 v2 `simv/PREPARE_AND_RUN` 是否仍存活：

- 存活：禁止重跑，等待自然结束或 12 小时 timeout；
- 已死：先记录终止方式，再决定是否生成全新身份。

本次未生成新包，未修改任何 `rtl/` 文件。v2 包生成记录见
`.agents/task_records/20260725_requant_node0001_e4_v2_compilefix_package_generation.md`。

## 长运行规模与 I/O 风险

冻结包内 `TEST_PACKAGE_MANIFEST.json`、SCA/SCA_D、execplan 和 Dequant E4
参考包逐文件复核得到：

- Requant v2 是完整 two-stage W3 E4，不是原子烟测：
  `Repeat_Num=48`、execplan 317 行、178 个文件型 preload；
- 逻辑输入为 `51,380,224` bytes，即 `12,845,056` 个 int32 元素；
- guard 与 round 两阶段合计约 `25,690,112` element-stage operations；
- formal D 为 `1,505,280` 个 128-bit 行，即 `24,084,480` bytes；
- Dequant E4 参考规模是 `Repeat_Num=1`、execplan 29 行、SCA 共 33
  个顶层字段（其中 30 个文件型 preload）、输入 `28×752=21,056`
  bytes、formal D `5,264` 行即 `84,224` bytes；
- 因而 Requant 输入约为 Dequant 的 `2440.170×`，formal D 约
  `285.957×`，Start Comp 次数为 `48×`。

stock TB 在首次 start 后仍创建 420 个 local 文本 monitor 文件和预期
336 个 bank 文本 monitor 文件；v2 runner 虽设置
`DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0`，快照仍观察到这些文本 monitor
被创建。因此文件 I/O、逐握手文本输出、48 个串行完成 fence 是合理的长运行
风险，但目前仅分类为：

```text
PLAUSIBLE_TEXT_IO_AND_SERIAL_FENCE_DOMINANCE_NOT_PROVEN_ROOT_CAUSE
```

该风险不能替代进程状态、自然退出收据或 formal D，也不改变正式 E4 attempt
计数。`12.zip` 仍然不证明 hang。
