# ResNet50 INT8

本仓库保存 ResNet50 INT8 到 28-slice NDP 配置、执行计划与验证证据的根编排代码。外部工具仓库不作为 submodule 嵌入，而由 `repos.lock.json` 固定到完整提交哈希。

## 全新克隆后的恢复

需要 Python 3 和 Git。在根目录执行：

```powershell
python bootstrap.py
```

该命令会恢复并验证：

- `CGRA_SIM`：历史 ResNet/QNN 语义参考；
- `ndp-sim-ref`：冻结的旧配置/编码参考，只读；
- `NDPFuncModel`：配置绑定功能模型；
- `ndp-sim`：当前活动的原生 golden、relayout、bitstream 与 execplan 工具。

恢复始终使用 `repos.lock.json` 中的完整提交，不跟随分支 tip。命令还会检查仓库 HEAD、工作树状态、远端 URL，以及根仓所跟踪外部证据的 SHA-256。任何缺失或不一致均返回非零退出码。

只验证已有 checkout、不下载：

```powershell
python tools\sync_repositories.py verify
```

只恢复一个仓库：

```powershell
python tools\sync_repositories.py sync --repo ndp-sim
```

`NDPFuncModel` 的锁定提交当前通过 `repos.lock.json` 中登记的 mirror 获取；协作者需要该仓库的读取权限。其余登记 URL 为公开上游。

## Python 环境

推荐使用项目虚拟环境：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-resnet50.lock.txt
.\.venv\Scripts\python.exe bootstrap.py
```

后续测试必须使用 `.venv`；其他 Python 环境缺少原生 encoder 依赖时可能产生假失败。

## Git 未包含的大型生成物

约 951 MiB 的 W3 tensor/golden 不进入 Git。新机器首次缺失时才运行：

```powershell
.\.venv\Scripts\python.exe tools\prepare_reference_model.py
.\.venv\Scripts\python.exe tools\run_onnx_golden.py artifacts\reference_model\resnet50-v1-12-int8.onnx artifacts\reference_model\input_batch16.npy artifacts\w3\golden_batch16
.\.venv\Scripts\python.exe tools\run_subop_golden.py artifacts\reference_model\resnet50-v1-12-int8.onnx artifacts\w3\golden_batch16 artifacts\w3\subop_batch16
```

两个输出目录必须在生成前不存在；禁止把新旧结果混写。已有产物只做验证，不因普通测试或文档更新重建。`artifacts/w3/model_graph.json`、`legacy77_mapping.json` 和小型 R3 mapping evidence bundle 会由 Git 保存。

本地 `NDP_copy01` RTL/VCS 镜像不进入 Git；它不是 Windows 上可执行的 VCS 环境。服务器 RTL 身份和运行/回读命令必须按 `.agents/agent.md` 与 `.agents/plan.md` 的当前边界另行核验。

当前更新后的 testbench 在未传 `+SCA_CFG_D` 时会默认寻找 `sca_cfg_D_softmax.json`。所有手动原生包运行必须同时显式传入本包的 `+SCA_CFG=.../sca_cfg.json` 和 `+SCA_CFG_D=.../sca_cfg_D.json`，并检查日志没有 `Cannot open` 或 `skip matrix readback`；仅有 `Simulation completed successfully!` 不能代替正式回读成功。实测案例见 `server_returns/decode_max_fp32_simresults_1/ANALYSIS.md`。

服务器返回目录或 ZIP 统一使用 `tools/analyze_native_ndp_server_return.py` 验收；它从本轮
两份 SCA 推导预加载、execplan、slice 和 D 回读合同，并定位最远硬件 checkpoint。
GAP 的哈希绑定 profile、建议观测 plusarg、必须返回的日志/矩阵以及完整命令见
`contracts/native_ndp_server_return_acceptance.md`。

服务器返回目录或 ZIP 统一使用 `tools/analyze_native_ndp_server_return.py` 验收；它从本轮
两份 SCA 推导预加载、execplan、slice 和 D 回读合同，并定位最远硬件 checkpoint。
GAP 的哈希绑定 profile、建议观测 plusarg、必须返回的日志/矩阵以及完整命令见
`contracts/native_ndp_server_return_acceptance.md`。

## R5 哈希绑定补丁工具链

活动 `ndp-sim` 固定版本保持只读。项目需要的 6144-row 地址规划和 mapper 修复由
`contracts/ndp_patch_toolchain_v1.json` 锁定，并且只应用到临时或显式物化的副本：

```powershell
.\.venv\Scripts\python.exe tools\materialize_patched_ndp_toolchain.py outputs\ndp-toolchain-6144-v1
```

mapping/execplan 证据生成器通过 `--patchset-manifest contracts/ndp_patch_toolchain_v1.json`
启用该身份。仓库保存了一条小型 patched Decode 双运行证据，可直接验证：

```powershell
.\.venv\Scripts\python.exe -m unittest `
  tests.test_ndp_patch_toolchain `
  tests.test_operator_config_evidence_bundle `
  tests.test_operator_config_execplan_evidence -v
```

ResNet50 当前全量状态由下列命令机械重建：

```powershell
.\.venv\Scripts\python.exe tools\build_r5_lowering_bundle.py
.\.venv\Scripts\python.exe tools\build_project_closure.py
.\.venv\Scripts\python.exe tools\build_e4e5_handoff_readiness.py
.\.venv\Scripts\python.exe -m unittest tests.test_project_closure -v
```

报告 `contracts/resnet50_project_closure.json` 已覆盖 78 个 ONNX 节点、133 个 lowering stage、93 条运行边和 W3 的 78/78 独立公式结果。它是 fail-closed 状态表：当前正式 target config 仍为 0/133，正式服务器 E4/E5 仍为 0；历史候选文件不能代替 RTL 数值证据。

当前 9/9 legacy 规范化配置已取得 zero-penalty、无 fallback mapping。MaxPool 的 `null→0` 只由哈希绑定的 UINT8 零 padding 合同授权；固定参考 cache 只在隔离副本中使用，并由当前原生 mapper 重新验算 exact cost=0。重建命令和边界见 `.agents/agent.md`，不得覆盖已发布 evidence 目录。

`contracts/resnet50_r5_lowering_bundle.json` 将 133 个 stage 固化为可消费的 typed request；每个 request 都绑定 dtype、shape、axis、值哈希、stage DAG、目标 profile、补丁身份和独立 request SHA-256。它不会越过 unresolved blocker 输出正式配置。

`contracts/resnet50_e4e5_handoff_readiness.json` 列出 10 种硬件 stage 的代表测试及 E4/E5 双跑要求。服务器命令模板位于 `contracts/server_execution_protocol.template.json`；模板本身故意不可执行。用户填入并批准真实的 load/start/wait/readback argv、服务器 RTL commit/filelist hash 后，统一入口为：

```powershell
python tools\run_e4e5_server_protocol.py `
  --protocol <approved.json> `
  --package <formal-package> `
  --output <fresh-return-dir> `
  --run-id run1
```

该入口使用 `shell=False` 按固定四阶段顺序执行，保存逐阶段 stdout/stderr、协议/RTL 身份、包执行前后文件树和原始回读；`run2` 必须输出到另一个新目录。它不会自行猜测服务器命令。

当前完整本地回归命令及已验证结果：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

2026-07-23 本轮最终结果为共 460 项，443 项通过、17 项按环境条件跳过、0 失败，测试框架耗时 999.012 秒。完整通过不代表服务器 RTL 数值通过；正式 E4/E5 仍需已批准配置、真实服务器入口与两次原始回读。

## 当前 R5 本地闭合

`contracts/resnet50_r5_resolution_overlay.json` 与 `contracts/resnet50_r5_lowering_bundle.json` 当前记录 133/133 typed request，其中 2/133 已本地消解：node-0002 MaxPool 可生成候选配置，Flatten/View 是零拷贝且不生成算子配置。正式 target config 仍为 0/133。

两个可交给已批准服务器协议的本地完整候选由下列命令重建：

```powershell
.\.venv\Scripts\python.exe tools\build_maxpool_node0002_server_candidate.py
.\.venv\Scripts\python.exe tools\build_node0004_nopp_r1_server_candidate.py
.\.venv\Scripts\python.exe tools\build_project_closure.py
.\.venv\Scripts\python.exe tools\build_e4e5_handoff_readiness.py
```

候选目录较大并继续由 Git 忽略；新 clone 必须先按 `.agents/agent.md` 生成 W3、mapping/execplan 及 companion tensors，再运行上述封包命令。MaxPool 候选只覆盖 node-0002 wave0；node-0004 候选只验证零 ping-pong 单阶段活性。两者都不等于正式 E4/E5。
