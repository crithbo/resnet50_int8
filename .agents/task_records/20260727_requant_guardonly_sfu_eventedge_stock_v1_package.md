# Requant node0001 guard-only SFU event-edge stock v1 包记录

日期：2026-07-27

## 结论

已生成并完成本地包级验收，状态为 `PACKAGE_READY_NOT_RUN`。本包只把已冻结的
Requant guard-only 语义资产接到 event-qualified 的只读观察器；不修改 JSON、mapping、
bitstream、execplan、输入、RequantGuard、golden 或 expected writes，不修改 TB driver
和任何 `rtl/**` 文件，也不计 node0001 E4/E5。

独立原生 SiLU control 的动态正证据已进入 manifest、profile 和结果路由：
共同 stock-RTL `SFU coeff → ALU → postprocess → normal outbuffer → MSE4 wdata`
不是普遍失效路径。若本 Requant 包在系数/ALU处出现首分歧，只能继续裁决
Requant 专属配置消费/选择、Requant 模式相关 RTL 控制或 observer 证据，不能退回
“共同 SFU 普遍故障”。

## 包身份

- install/package/run/return 命名空间：
  `rq_node0001_guardonly_sfu_eventedge_stock_v1`
- ZIP：78,068 bytes
- ZIP SHA256：
  `31877dcf0f11a52a0822525e8f49312d25807f81884377f748425693c89b4a53`
- sidecar：
  `rq_node0001_guardonly_sfu_eventedge_stock_v1.zip.sha256`
- manifest SHA256：
  `1c14c62a39a407dac6383f07ce18dc2697c7122351b8603c6c072e7e1d70af48`
- payload tree SHA256：
  `3c1c43c638af836a876b1242496e043937250800e40e638691ecedf623efe026`
- frozen semantic tree SHA256：
  `3f6c7116c72dcebcae9102a3d822c7f4d8f1e26b8005af1432e72e461559e222`
- frozen semantic file count：23
- ZIP entry count：35；`rtl/` entry=0；pyc/`__pycache__` entry=0
- release gate：`candidate_release=false`，不计 E4/E5
- 未解除 blocker：
  `B_REQUANT_GUARD_DYNAMIC_DATA_PATH`、`B_REQUANT_SERVER_E4_E5`

## 唯一服务器命令

在解压后的包根目录执行：

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

预期回传：

- `rq_node0001_guardonly_sfu_eventedge_stock_v1_return.zip`
- `rq_node0001_guardonly_sfu_eventedge_stock_v1_return.zip.sha256`

## 本地门

- 最新公共规则 SHA：
  `f3fe8dd18c9e2009db4a2736c6c1e86841760d8ec023bb7b57562f27f5faff04`
- 最新 Requant 专项规则 SHA：
  `44e8ee38d1361f15d78bf5d7918fa10e4648370153178ad10d044fd5c9d26265`
- mandatory read receipt SHA：
  `77c5d1e3b9b190cb891baa4a64a2d83e1beed8eaa2d65229ddc3c67abe03d61c`
- 两次从新目录确定性构建：ZIP 逐字节一致
- fresh-extract 真实 packaged runtime 入口：通过
- package tree 执行前后 SHA 一致：通过
- `PYTHONDONTWRITEBYTECODE`/pyc 不变门：通过
- observer install/verify/restore：逐字节恢复通过
- TB target 只绑定命令传入根目录下
  `native_return_observer.svh`；candidate target count=1；无
  basename/find/glob/rglob：通过
- XMR 静态门：最终安装态检查 491 个 generated instance reference，
  runtime-indexed generated path=0
- 事件门：64 个真实 Requant transaction，不使用 level qualifier 计数；
  raw/qualified/parseable/XZ/duplicate 分栏
- MSE4 request/write-data 独立握手和独立事务 ID：16/16 预期
- 定向回归：25/25 PASS

额外执行的历史 atomic v2 模块中，唯一旧 source-identity 检查按预期因其绑定旧
Requant 规则 SHA 而 fail-closed；它不是本包 validator 失败，旧 atomic v2 未被重建或
修改。

## 修改范围

- `tools/requant_node0001_server_runtime.py`
- `tools/requant_guard_eventedge_server_runtime.py`
- `tools/build_requant_guard_eventedge_onecmd_server_test.py`
- `tests/test_build_requant_guard_eventedge_onecmd_server_test.py`
- 本读取收据、任务记录和全新 package/ZIP/sidecar/validation receipt

未修改 `.agents/rules/**`、`.agents/plan.md`、`NDP_copy01/rtl/**` 或 TB driver。
