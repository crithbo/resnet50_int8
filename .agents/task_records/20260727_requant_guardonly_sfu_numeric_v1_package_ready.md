# Requant node0001 guard-only SFU numeric capture-edge v1 package-ready record

- 日期：2026-07-27
- 状态：`PACKAGE_READY_NOT_RUN`
- 身份：`rq_node0001_guardonly_sfu_numeric_stock_v1`
- 目的：在 SFU readiness v1 已证明 `SFU_PREPROCESS0_VALID`、但 MSE4/formal D 仍全零之后，仅观察真实 SFU 数值 payload 的 capture-edge 路径。
- 发布边界：`candidate_release=false`，不计 node0001 E4/E5，未上传、未运行。

## 生成前收据

- 收据：`.agents/task_records/20260727_requant_guardonly_sfu_numeric_v1_read_receipt.json`
- SHA256：`887a03eec02f884a4f05ae8e377949e046cb1d49fce36cca34376d0bd33315f4`
- 公共服务器规则 SHA256：`0fec7a4f72246c9e802fb2e91e972c2f636e2721aaeef1194c2d4d3fba103fbc`
- Requant 专项规则 SHA256：`5f7bc1fc7087d3aafce0b74982588df9c68abeea583a7ea501c87031c3ef9e52`
- 权威前代回传分析 SHA256：`47f91b2cb25b2e81e1385b35fe0cc6739709717c69a22f3b383bfbbf81be584a`
- 规则：`CDA-SERVER-OBSERVER-CAPTURE-EDGE-WITNESS-001`、XMR elaboration 常量门、解耦 MSE4 handshake 门、证据支配门和 Requant guard-only 动态证据边界。

## 语义冻结

- 直接前代：`rq_node0001_guardonly_sfu_ready_stock_v1`，ZIP SHA256=`8cb224163271e0ed9166831bf434c88ce10e1f76ed78a42344724f8b5126c2ac`。
- JSON、mapping、bitstream、execplan、input、RequantGuard、golden、formal D、expected writes 共 22 个语义文件逐字节一致。
- 语义树 SHA256：`71f75503eae94dfb5c7c2b92f0c0bb173bb863da023eca666f18cc79feb720a9`。
- SCA 仅按新 install identity 归一化后相等；`semantic_change=false`。

## 只读诊断边界

- 保留一个 last-good `PE_SELECTED_INPUT`、lifecycle、16 个解耦 MSE4 raw request/write-data 和两份 formal guard D。
- 新增 capture-edge 数值 witness：
  `SFU_PREPROCESS_INPUT_CAPTURE → SFU_BST_RESULT_CAPTURE →
  SFU_COEFF_CAPTURE → SFU_ALU_INPUT_CAPTURE →
  SFU_ALU_RESULT_ACCEPTED → SFU_POSTPROCESS_RESULT_ACCEPTED →
  NORMAL_OUTBUFFER_INPUT_ACCEPTED → NORMAL_OUTBUFFER_WRITE_COMMIT →
  NORMAL_OUTPORT_ACCEPTED → MSE4_WDATA`。
- 每项 `data` 均为捕获使能或 accepted handshake 边沿上的真实数值 payload；opcode、
  enable、valid 等状态位不再拼接并冒充 `data`。
- generated hierarchy 全部经 `genvar` 常量代理；无 force/deposit/driver、无 TB/RTL
  完成条件或 timeout 修改。

## 最终包与本地验收

- ZIP：`artifacts/operator_config_validation/r5-server-test-packages/rq_node0001_guardonly_sfu_numeric_stock_v1.zip`
- 大小：66,563 bytes
- SHA256：`8e96d1bbd6e0379b8d33fca251b27bbc40bb32fc56d82418a3ae85e0515e1a1b`
- sidecar：`artifacts/operator_config_validation/r5-server-test-packages/rq_node0001_guardonly_sfu_numeric_stock_v1.zip.sha256`
- manifest SHA256：`d4b7ccf7ca24f0c4a940fb863ada3dc5c367797f71dfa04822aba400adbdf4ae`
- payload tree SHA256：`62d4a08e1cf254f6a8d698c989b4309a76bcc44ae9338f08c4cd55a53f6a411e`
- 两次全新确定性构建：ZIP byte-identical。
- ZIP exact-set：33 entries，unsafe=0，duplicate=0，`rtl/` entries=0。
- 唯一一次 fresh-extract 完整自检：33 files、303,048 bytes；执行前后 tree SHA256
  均为 `6b8a41639c6f13723adb7731ab6e5f88b826910a56e27d566cd52f194e3c6597`。
- packaged runtime preflight、bootstrap pyc immutability、observer install/precompile
  verify/restore、最终拼接 XMR constant gate 全部通过；拼接 observer 检查 463 个
  generated XMR，运行期实例路径下标为 0，恢复逐字节一致。
- 定向测试：`tests.test_build_requant_guard_only_onecmd_server_test`，12/12 PASS。

服务器唯一命令：

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

预期回传：

- `rq_node0001_guardonly_sfu_numeric_stock_v1_return.zip`
- `rq_node0001_guardonly_sfu_numeric_stock_v1_return.zip.sha256`

## 未解除 blocker

- `B_REQUANT_GUARD_DYNAMIC_DATA_PATH`
- `B_REQUANT_SERVER_E4_E5`

本地生成与验收无 blocker；下一项只允许服务器 FIRST_DYNAMIC 运行及正式回传分析，
不得启用 round-only、alias/lifetime 或完整 E4。
