# Requant node0001 guard-only SFU readiness v1 package-ready record

- 日期：2026-07-27
- 状态：`PACKAGE_READY_NOT_RUN`
- 身份：`rq_node0001_guardonly_sfu_ready_stock_v1`
- 目的：在 direct-signal v1 已证明 `PE_SELECTED_INPUT` 非零、但 MSE4/formal D 全零之后，仅观察 SFU readiness 与 PE post-register 的首分歧。
- 发布边界：`candidate_release=false`，不计 node0001 E4/E5，未上传、未运行。

## 生成前收据

- 收据：`.agents/task_records/20260727_requant_guardonly_sfu_ready_v1_read_receipt.json`
- SHA256：`b29b107e0456d8998889528e4cc3556e1ac2c750327997825750d14023728714`
- 公共服务器规则 SHA256：`b4019910c7ef65f334676a1b3a5679e63b8ac41dcde88b567ada4f096e50fe05`
- Requant 专项规则 SHA256：`20883fad672123f6f6561633d58b5432ed453feb8f2695e5993f9bfe97b0756e`
- 活动 encoder：`ndp-sim-ref/bitstream/config/general.py`，SHA256=`eb9d5ee9ef273182e05b718aca378f87d0a1ccb5366ae463d8482c8c94c3482f`；`sfu_activation=24/0x18`。
- `native_ring4_repro_20260722/bitstream/config/general.py` 仅作为同 SHA、逐字节一致的历史等同性证据。

## 语义冻结

- 直接前代：`rq_node0001_guardonly_directsig_stock_v1`，ZIP SHA256=`715a4b8abdd45b3251c464eba4359cea8af740c75b238a68d956f949524a1939`。
- JSON、mapping、bitstream、execplan、input、RequantGuard、golden、formal D、expected writes 共 22 个语义文件逐字节一致。
- 语义树 SHA256：`71f75503eae94dfb5c7c2b92f0c0bb173bb863da023eca666f18cc79feb720a9`。
- SCA 仅按新 install identity 归一化后相等；`semantic_change=false`。

## 诊断边界

- 保留：`PE_SELECTED_INPUT` 64、lifecycle、16 个原始 MSE4 request/wdata、2 个 formal D。
- 新增只读窄观察：odd PE opcode/SFU valid/compute enable、group compute-valid、LUT init address/end/slice reset、PE post-register valid/matched/output-valid、SFU preprocess0 enable/valid。
- runtime 要求至少采到精确 opcode `24/0x18`；所有非零异常 opcode 按值计数并保留在回传证据中。
- readiness、accepted MSE4 observer、formal D、lifecycle 全通过时，裁决为 `GUARD_ONLY_DIAGNOSTIC_PASS` 且 `first_divergence=null`；不再误报 `OBSERVER_GAP`。
- 未携带 `rtl/`、未修改 TB/RTL、未 force/deposit、未启用 round-only/alias/full-E4。

## 最终包与本地验收

- ZIP：`artifacts/operator_config_validation/r5-server-test-packages/rq_node0001_guardonly_sfu_ready_stock_v1.zip`
- 大小：65,468 bytes
- SHA256：`8cb224163271e0ed9166831bf434c88ce10e1f76ed78a42344724f8b5126c2ac`
- sidecar：`artifacts/operator_config_validation/r5-server-test-packages/rq_node0001_guardonly_sfu_ready_stock_v1.zip.sha256`
- payload tree SHA256：`f1fa6814cd5698c71b80088147303745b87be919026fd27c4e22948d1f3cfec9`
- 两次确定性构建：ZIP byte-identical。
- ZIP exact-set：33 entries，`rtl/` entries=0。
- 唯一一次全新解压完整自检：33 files、294,986 bytes；执行前后 tree SHA256 均为 `1d1ac421072aedcce7010a9beb0c1507a6245d8417c47e5e60eb689307e400e9`。
- bootstrap immutability、真实 packaged runtime preflight、observer install/precompile verify/restore、XMR constant gate 全部通过；observer 恢复逐字节一致。
- 定向测试：`tests.test_build_requant_guard_only_onecmd_server_test`，12/12 PASS。

服务器唯一命令：

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

预期回传：`rq_node0001_guardonly_sfu_ready_stock_v1_return.zip` 及 sidecar。

## 未解除 blocker

- `B_REQUANT_GUARD_DYNAMIC_DATA_PATH`
- `B_REQUANT_SERVER_E4_E5`

本地生成与验收没有 blocker；下一项首个未闭合条件是服务器 FIRST_DYNAMIC 运行及正式回传分析。
