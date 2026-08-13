# NDP_copy01 硬件仿真入口

最后更新：2026-08-13（observer-only 宽因果回传与原生 production flow）

本文件只说明活动 Make/TB/filelist 的实际消费接口。包结构、runner、回传和预算看
`.agents/rules/服务器测试包生成规则.md`；算子语义看专项规则；版本状态看
`.agents/plan.md`。若本说明与活动源码或真实日志冲突，以活动实现为准并修正文档。

## 1. 活动入口与只读边界

| 文件 | 作用 |
|---|---|
| `Makefile.tb_NDP_Top_new_phy` | VCS compile/sim、参数和历史 archive target |
| `tb_NDP_Top_new_phy.sv` | 时钟/复位、SCA loader、AXI preload/readback、启动和完成观察 |
| `rtl/filelists/NDP_Top_phy_filelist.f` | 顶层 PHY 编译源集合 |

`NDP_copy01/rtl/**` 默认只读。普通服务器包不得携带、覆盖、patch、安装、恢复或间接
替换任何功能 RTL。当前本地 `rtl/` 与
`Trassic2.0_RTL/code/NDP_rtl` commit
`0ccae916ef61904a64d6cf8ec1d1931b45e428d8` 精确一致：2262 files，
tree receipt `c6902de6fabfce81ee10af02cec238e5b11d2fdece9454041415c455556e1093`。
旧 `rtl_pre_*` 备份目录已删除，不再采用保留副本作为活动源。

云端 GitHub `xlsjdjdk/Trassic2.0_RTL/master` 是功能 RTL 权威；本地和服务器实际源码差异
本身不阻止 compile 成功后的 simulation。正式包回传仍须记录 actual compile identity，
对照云端 commit 做算子 causal-cone 影响裁决；不能把本地同步冒充 production compile
receipt。旧包名或旧构建 provenance（例如 `df23e4d`）不表示服务器仍在使用旧 RTL。

真实 VCS 只在具备 Synopsys compile/simulation 依赖和 license 的 Linux 服务器运行；Verdi只用于
历史波形，不是 current observer-only 路径依赖。Windows 本机负责 package/manifest、event return
解析、返回分析和回归验证。

## 2. 工作目录和 Make 语义

服务器执行 cwd 必须是目标 `NDP_copyXX` 根目录，因为 SCA 内 payload 路径从该目录解析。
历史 Make 入口是：

```bash
make -f Makefile.tb_NDP_Top_new_phy compile sim \
  SCA_CFG=/absolute/path/to/sca_cfg.json
```

正式测试应由包内唯一 runner 调用当前 Make 或隔离 simv；用户不直接拼接复杂参数。

runner 在 arm partial-return finalizer 后，应直接执行 production `cd`、package-owned install、compile
与 sim。在唯一 `# CODEX_PRODUCTION_LAUNCH` 之前，禁止以 `test/stat/find/readlink/realpath`、hash/tree、
Git identity、`command -v/which`、Make dry-run 或 module/provider 短探针证明服务器已有文件、目录、
RTL、TB、filelist、library 或工具存在；环境完整性只由真实命令的 cwd/argv/log/exit 裁决。

真实命令失败后，先与 `ndp-sim/README_SERVER_PACKAGE_LOCAL.md`、generate_python_golden/model_execplan
README 与 `main.py`、活动 Make/TB/filelist 做差分，核对 cwd、`../model_execplan/main.py`、明确的
regenerated-op 日志、真实 bitstream、同包 `SCA_CFG/SCA_CFG_D`、TB path echo、`Repeat_Num` 和 actual
consumer path。仓库未保存的 server loader/start/wait/readback 命令固定标为 `SERVER_RUNTIME_UNKNOWN`，
不得猜测，也不得据此新增 preflight。

- `compile`：VCS compile/elaboration，产生临时 simv/csrc；
- `sim`：运行 simv，历史 target 可能归档完整结果树；
- 正式 runner 默认使用 no-archive 路径，避免复制 build tree；
- `SCA_CFG`/`+SCA_CFG`：主 SCA；
- `+SCA_CFG_D`：D readback SCA；
- `DUMP_VCD/DUMP_FSDB/TB_DUMP_FSDB`：current next-fresh 固定为 `0/0/0`。VPD、FSDB、VCD、FST、
  dump Tcl、PLI waveform writer、Verdi/WaveUtils query 及其 shard/lock 都不是新包输入或回传成员；
  NDP 根目录已有 `inter.fsdb`/`novas.fsdb` 也永远不是本轮证据。
- 动态证据由 package-local、source-bound、只读 observer 产生，并写入本次 attempt 的
  signal-id catalog、分块 4-state event、end-state、sim-time heartbeat 与 canonical decision。
  actual compile/sim argv、observer plan/source、parser 和 formal return allowlist 必须绑定同一
  package/execution/attempt 与实际 source identity。
- 共享实现入口为 `contracts/server_observer_only_wide_causal_dispatch_v1.json`，由
  `tools/validate_server_observer_only_wide_causal.py` 和
  `tools/server_observer_runtime_supervision.py` 分别验证 exact package/return 与监督 simulator tree；
  package 不得自行恢复已退休的 waveform gate。

## 3. SCA loader 和 payload ABI

TB 使用逐行字符串匹配，不是完整 JSON parser。生成器必须输出 TB 可读的 pretty JSON，
并提供：

- `Exec_Base`；
- `Exec_Length`；
- `Repeat_Num`；
- 每个对象的 `base_addr` 和 `path`；
- 每个 D 对象的 `length`。

`Repeat_Num` 必须等于本轮 execplan 中 `Start_Comp` 数量。SCA_D `length` 单位为
128-bit word；缺失时 TB 可能静默跳过 readback。

payload 每行恰好 128 个 `0/1` 字符并以 LF 结束。短行、非法字符、CRLF、缺文件或额外
空行必须由 package preflight 在启动前拒绝；“matrices loaded”计数不能替代格式校验。

TB 预装后写：

```text
0x8000_0000 <- {96'd0, exec_length, exec_base}
0x8000_0010 <- 1
```

执行内容来自 SCA 引用的 `install/execplan.txt`；历史 `+BITSTREAM` 不是主 execplan 来源。

## 4. 两份 SCA 必须显式绑定

每次运行必须同时传：

```text
+SCA_CFG=<本轮 package>/sca_cfg.json
+SCA_CFG_D=<本轮 package>/sca_cfg_D.json
```

两条路径必须属于同一 package。当前 TB 缺 `+SCA_CFG_D` 时会尝试
`sca_cfg_D_softmax.json`；非 softmax 包不得依赖、复制、改名或链接该默认文件。

仿真开始后立即核对：

```text
Using SCA cfg file:
Using SCA cfg D file:
```

出现错误 package、`Cannot open`、`skip matrix readback` 或意外 softmax 路径时，正式
readback 失败；即使随后打印 `Simulation completed successfully!` 也只能说明计算流程
结束，不能升级 E4。

## 5. 完成观察

TB 按 `Repeat_Num` 重复观察：

1. 物理 slice0 收到 `Start_Comp`；
2. 物理 slice1 出现 `slice_cmpt_finish`；
3. 达到次数后进入 readback。

该观察不是 mask-aware。多 slice/stage 包必须通过 execplan、barrier/lifecycle 和只读
observer 证明所有目标完成，不能把 slice1 单事件外推为全局完成。

若服务器接口需要 UCLI force 未连接 clock，必须由受审计命令证明 force/get 和相位翻转；
不能在包内改 HDL。

## 6. Readback

1. SCA_D 声明 base、path 和 128-bit word 数。
2. 每个目标在运行前必须不存在，运行后必须是普通文件且非 symlink。
3. 行数精确为 `length`，bytes 精确为 `length×129`，每行 128 bit + LF。
4. exact-set、地址覆盖和逐行 golden 由算子专项门决定。
5. preload、内部 MSE write、文件存在、Make 返回 0、单 slice 完成或成功文本均不能替代
   正式 readback。

## 7. Mandatory source-bound 只读 observer

所有可能进入 DUT simulation 的 next-fresh 包都必须启用 observer，并且必须：

- 位于 `rtl/` 外，不驱动 DUT；
- 使用全新 compile 身份；
- 由 plusarg 显式开启，记录真实 DUT net，不用 observer 重算的 expected equation 代替 actual net；
- 以足够宽的因果 catalog 覆盖 clock/reset/stage、producer、queue、request/accept/backpressure、
  selected port/bank/lane、internal match/state/clear、output/wdata、terminal/finish/formal-D；
- 用本机可读 signal-id catalog 与分块 JSONL/TSV 记录每个选中信号的有序 0/1/X/Z transition、
  exact time/sequence/width 与 end state；timeout/HUP/INT/TERM 时 `fflush` 已有 chunk；
- 不改变 ready/valid、数据、时序、完成或 timeout。

100,000,000 bytes 是 observer evidence aggregate 的软偏好，不是 hard cap。超出只记录 warning，
不得截断、采样、按大小删除或阻止 formal return。simulation_started=true 时缺 required catalog/
chunk/index/parser/decision receipt 必须标记 `DIAGNOSTIC_EVIDENCE_INCOMPLETE`。

## 8. 环境和成功边界

需要 Linux x86_64、bash/GNU make/coreutils、VCS/license，以及 filelist 所需 DesignWare、VIP、
DDR/PHY 库；observer-only 回传不要求 Verdi、DVE、WaveUtils 或本机 Synopsys decoder。

normal/timeout/HUP/INT/TERM 都须回收已 close/flush 的 observer chunks 与 core。compile 未成功或
simulation 未启动时允许无 event，但 compile-core return 仍是必需。同一 bash/package 顺序重复
运行时，只清除 exact package-owned cfg/attempt leaf（包括 stale observer chunks），
不得触碰 foreign sibling 或根目录直接项；每轮使用新 execution identity 和唯一 return 名，历史
return 必须保留且不得覆盖。process-tree supervisor 仍须完成 child-subreaper、PGID、内部 timeout、
TERM→wait→KILL/reap 与 sim-time heartbeat；无需等待不存在的 waveform writer。

一次结果只有在 package/argv/入口身份、compile、preload、目标完成、各层退出状态、
readback exact-set/格式、独立 golden 和算子专项动态门全部通过后，才能进入相应 E4。
重复 E5 必须使用全新身份。
