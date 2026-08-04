# Dequant node0077 full-v6 stock-RTL E4 包就绪

日期：2026-07-27

状态：`E4_PACKAGE_READY_NOT_RUN`。本记录只证明包生成与本地包级验收，
不证明服务器 E4；`candidate_release=false`，`B_DEQUANT_SERVER_E4_E5`
保持未解除，E4 正式回传通过前禁止生成 E5。

## 身份

- package/install：`dequant_node0077_stockrtl_e4_onecmd_v2`
- ZIP：`artifacts/operator_config_validation/r5-server-test-packages/dequant_node0077_stockrtl_e4_onecmd_v2.zip`
- ZIP bytes：147148
- ZIP SHA-256：`2ac27a4856b36bb660c0293ff53f84794464283712f20fe0d84dabfa16b699e0`
- sidecar：`dequant_node0077_stockrtl_e4_onecmd_v2.zip.sha256`
- manifest SHA-256：`5916ccd3c4999daa49368d61dd80a19ab09d3a501bbbcd43c92b0a3a77e61f10`
- payload：82 files；tree SHA-256
  `e967bb42019b4b28d9bc97ba9d2a90d9a99773d3d5a5295768e8f947c07fc354`
- 唯一服务器命令：
  `bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX`

## 冻结 v6 链

- strict config SHA-256：
  `72c871e3bb4583302961ead62cabefa8b125281be97b5df61b45a190f18998bb`
- bitstream SHA-256：
  `c8ff24957d847df9b5f191b257567fec123605e24d1083fd6fdedc5375e674d3`
- execplan SHA-256：
  `5caf5840264c8b93a28fb72f8fb3666a936b5df54b509928e919484ba608ddcd`
- 28 slice；每片 A=47 行；SCA 不 preload D；SCA_D 每片 188 行，
  共 5264 行，D 地址逐 slice 唯一。
- 正式 D 先逐片对 v6 physical golden，再按冻结 HIGH4 layout inverse
  重建 `float32[16,1000]`，对独立 W3 full-output golden 逐 bit 比较。

## observer 与身份边界

- 包内 `rtl/` entry=0；不修改或打包任何 `rtl/**`。
- 只读 observer 位于 `rtl/` 外，编译前事务式安装到
  `native_return_observer.svh`，编译后立即逐字节恢复。
- raw MSE4 request 与 raw write-data 按 28 个物理 slice、2 个 channel
  独立记录和计数，不做 request/wdata 配对，不因地址证据缺失丢弃 wdata。
- slice-local、加 stream base 后的 global-linear、raw post-remap 地址分栏；
  post-remap 不与前两域直接比较。
- observer temporal receipt 与 formal D 数值门正交；formal D 满足唯一、
  未预置、全覆盖、逐 bit 正确和自然完成时，observer 漏记只能分类为
  `OBSERVER_EVIDENCE_INCOMPLETE`。

## 本地验收

- 两个全新目录独立构建：ZIP、entry、mode、payload、manifest 与最终
  SHA-256 逐字节一致。
- exact ZIP + sidecar validator：PASS。
- fresh-extract bootstrap immutability：PASS；83/83 files、
  1,194,151 bytes，执行包内 preflight 前后 exact path/size/SHA 不变，
  无 pyc/pycache。
- fresh-extract observer install/verify/restore：PASS；最终拼接 observer
  扫描 335 个 generated-instance reference，运行期 XMR 下标 0；
  preimage 恢复逐字节一致。
- 定向单元测试：
  `python -m unittest tests.test_build_dequant_node0077_onecmd_server_test`
  为 4/4 PASS。
- 完整包级自检次数：1。

## 成功回传 exact-set

成功路径固定为 106 entries，完整列表在包内
`validation/EXPECTED_RETURN_EXACT_SET.json`。包括：

- `RETURN_RECEIPT.json`、package manifest、SCA/SCA_D；
- 16 个身份/状态/结果 receipt；
- 28 份 formal D、28 份 lifecycle、28 份 raw observer log；
- bounded compile-driver/sim log tail。

部分失败仍生成 allowlist-only return，并在 `RETURN_RECEIPT.required_missing`
中 fail closed；只有 compute、identity、formal D/layout inverse 和成功回传
exact-set 全部通过后，`SERVER_RESULT_GATE.status` 才能最终成为 `E4_PASS`。
