# Native NDP 服务器返回通用验收

最后更新：2026-07-23

## 1. 工具边界

`tools/analyze_native_ndp_server_return.py` 是通用的原生 NDP-Sim 返回验收入口。
它不按算子名写死判断，而是从待测工作负载中唯一的 `sca_cfg.json` 和
`sca_cfg_D.json` 推导本轮应装载的对象、`Exec_Length`、活动 slice、正式 D 回读路径
和长度，再检查服务器返回目录或 ZIP。

GAP 使用额外的严格 profile：

```text
contracts/server_return_profiles/gap_hwop0071_sum_v1.json
```

该 profile 将本轮 GAP-sum 的 manifest、两份 SCA、17 条 execplan、18 个 preload
对象、16 个活动 slice 和每片 512 行 D 固定到哈希。其他原生算子可不传 profile
自动推导，也可以新增同 schema 的算子专用 profile。

工具只读服务器返回和冻结工作负载。输出必须是新路径；它不会改写原始 ZIP、工作负载
或回读矩阵。

## 2. 服务器必须返回的内容

至少保留：

```text
sim_results/sim.log
install/op*/slice*/matrix_D_linearized_128bit.txt
```

第二类文件必须是仿真执行正式 `sca_cfg_D.json` 回读后写入的实际内容，不能只返回运行
前包内的占位/Golden 文件。为定位未跑通场景，还应一并返回：

```text
sim_results/gexec2slice/slice_all/gexec2slice.log
sim_results/local/slice*/local_mse*_req.log
sim_results/local/slice*/local_mse*_rdata.log
sim_results/local/slice*/local_mse*_wdata.log
sim_results/sem_events/slice*/sem_events.log
sim_results/return_observer/return_observer.log
sim_results/compile.log
```

若仿真超时或被外部终止，也要立即打包这些已经落盘的部分日志；不要只返回 FSDB。
目录外层可以任意再包一层，ZIP 也可以，验收器按安全 suffix 发现文件。

## 3. GAP 运行与低开销观测

本地 testbench 已通过 `native_return_observer.svh` 增加只读、plusarg 门控的观测器。
它不驱动 DUT 信号，不启用时只增加 elaboration 中的监测连线；启用后只写一份低频文本
日志。修改后的 testbench 必须先重新 `compile`，旧 `simv` 不会自动获得观测能力。

GAP 首跑建议：

```bash
make -f Makefile.tb_NDP_Top_new_phy compile sim DUMP_FSDB=1 \
  PLUSARGS='+SCA_CFG=install/cfg_pkg/gap_hwop0071_sum_graph/sca_cfg.json +SCA_CFG_D=install/cfg_pkg/gap_hwop0071_sum_graph/sca_cfg_D.json +RETURN_OBSERVER +RETURN_OBS_SLICE=0 +RETURN_OBS_DEEP +RETURN_OBS_DEEP_LIMIT=256 +RETURN_OBS_STALL_CYCLES=4096 +RETURN_OBS_HEARTBEAT_CYCLES=4096'
```

`DUMP_FSDB=1` 只用于本轮需要波形时，可改为 `0` 以降低磁盘和运行开销；两份 SCA
plusarg 不可省略。观测器缺省选择 slice 0，并覆盖：

1. CONFIG start/finish、exec start、slice finish；
2. global exec/config 下发计数；
3. 每个 MSE 的 request、read-data、write-data 握手计数；
4. 四个 bank 的 frame 握手计数；
5. Buffer4/5 的实际读写使能及累计活动次数；
6. SA 输入 tag、buffer→SA tag/backpressure、SA 输出 tag 和 SA→buffer
   tag/backpressure；这些点覆盖此前 Conv 在 READ_STREAM3、buffer4、SA、
   buffer5 之间无法唯一定位的区间；
7. GA 的 PE00、PE02、PE10、PE12、PE20、PE22、PE30、PE32；
8. 各 PE 的 enable、opcode、input-valid、pipeline0-valid、下游反压、
   pipeline0-enable 和上游 backpressure；
9. 每 4096 个活动周期一条 heartbeat；同一 pipeline0 反压状态持续 4096 周期时立即
   写 `STALL` 并 `fflush`。

如 slice 0 没有进入目标 stage，可只改 `+RETURN_OBS_SLICE=<0..27>` 重跑，不需要增加
全量高频打印。`STALL` 是诊断硬门：即使主日志和回读看似成功，验收器也不会把该轮
判为 passed。

## 4. 本地验收命令

在根目录运行：

```powershell
.\.venv\Scripts\python.exe tools\analyze_native_ndp_server_return.py `
  <服务器返回目录或ZIP> `
  --workload artifacts\operator_config_validation\r5-server-workloads\gap_hwop0071_sum_graph `
  --profile contracts\server_return_profiles\gap_hwop0071_sum_v1.json `
  --run-id run1 `
  --output server_returns\gap_hwop0071_sum_run1_acceptance.json
```

退出码：

- `0`：运行证据闭合，且所有正式 D 回读与冻结 Golden 逐字节一致；
- `2`：返回可解析，但失败、停滞、数值不一致或证据不完整；
- `1`：输入、profile、路径、ZIP 或 JSON 本身无效，未形成可信验收报告。

`run2` 必须使用另一份原始返回和新的输出路径。run1 通过只形成 E4 candidate；还要绑定
经批准的服务器/RTL identity 才能正式记 E4，独立 run2 才能支持 E5。

## 5. 判定顺序和卡点定位

报告按以下顺序给出 `furthest_direct_checkpoint`：

```text
invocation -> sca_binding -> preload -> execplan -> dispatch
-> slice_start -> read_request -> read_return -> compute_finish
-> write_address -> write_data -> global_complete -> readback
-> numeric_compare
```

重点分类：

- `setup_or_binding_failure`：漏传/错传 SCA_D、softmax fallback、文件打不开、
  preload 或 Exec_Length 不符；
- `dispatch_observed_slice_not_started`：global exec 已下发，目标 slice 未开始；
- `read_request_without_return`：MSE 已发出读请求/地址但没有任何读数据返回；
- `compute_started_not_completed`：slice 已开始但未完成；
- `write_address_without_write_data`：已到写地址但无写数据，是已有 INT8 MaxPool
  失败的主要外部特征；
- `internal_pipeline_stall_observed`：新观测器捕获 GA pipeline0 持续反压；
- `runtime_and_readback_logged_return_payload_missing`：日志声称完成回读，但没有把实际
  D 文件带回；
- `numeric_mismatch`：正式回读与工作负载中独立 Golden 不一致；
- `numeric_readback_pass_e4_candidate`：运行、回读和逐字节数值三者均闭合。

完整机器报告还保存 SCA 回显、错误命中、各 slice/MSE 活动计数、观测器原始 STALL
行、最后一条 buffer4/5/SA/GA 内部状态、最多 32 条观测器尾记录，以及每个 D 的长度
与首批 mismatch offset，供人工复核。
