# NDP_copy01 硬件仿真入口

最后更新：2026-07-24（只保留活动接口事实）

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
替换任何功能 RTL。服务器实际源码可以与本地/GitHub 不同；本轮必须记录实际 Make、TB、
filelist、RTL tree 和 focused RTL 的 pre/post/post-run 身份稳定性。

真实 VCS/Verdi 只在具备 Synopsys 依赖和 license 的 Linux 服务器运行。Windows 本机
只负责 package/manifest、返回分析和回归验证。

## 2. 工作目录和 Make 语义

服务器执行 cwd 必须是目标 `NDP_copyXX` 根目录，因为 SCA 内 payload 路径从该目录解析。
历史 Make 入口是：

```bash
make -f Makefile.tb_NDP_Top_new_phy compile sim \
  SCA_CFG=/absolute/path/to/sca_cfg.json
```

正式测试应由包内唯一 runner 调用当前 Make 或隔离 simv；用户不直接拼接复杂参数。

- `compile`：VCS compile/elaboration，产生临时 simv/csrc；
- `sim`：运行 simv，历史 target 可能归档完整结果树；
- 正式 runner 默认使用 no-archive 路径，避免复制 build tree；
- `SCA_CFG`/`+SCA_CFG`：主 SCA；
- `+SCA_CFG_D`：D readback SCA；
- `DUMP_VCD/DUMP_FSDB/TB_DUMP_FSDB`：普通测试必须显式为 0。

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

## 7. Optional 只读 observer

observer 不是默认依赖。只有专项规则声明时才启用，并且必须：

- 位于 `rtl/` 外，不驱动 DUT；
- 使用全新 compile 身份；
- 由 plusarg 显式开启并限流；
- 记录目标 CONFIG/exec/finish、MSE/buffer/array handshake 或 stall；
- 外部终止时 `fflush` 最远 checkpoint；
- 不改变 ready/valid、数据、时序、完成或 timeout。

缺 observer 时，部分回传只能裁决到最后一个公开日志事件。波形不能替代文本 observer
或正式 readback。

## 8. 环境和成功边界

需要 Linux x86_64、bash/GNU make/coreutils、VCS/license，以及 filelist 所需
DesignWare、VIP、DDR/PHY 库。波形诊断另需 Verdi/PLI，但普通完成包默认不启用。

一次结果只有在 package/argv/入口身份、compile、preload、目标完成、各层退出状态、
readback exact-set/格式、独立 golden 和算子专项动态门全部通过后，才能进入相应 E4。
重复 E5 必须使用全新身份。
