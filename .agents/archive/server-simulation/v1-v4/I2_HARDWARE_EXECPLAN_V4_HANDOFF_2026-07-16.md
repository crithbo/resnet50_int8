# node-0004 硬件仿真 v4 交付说明

最后更新：2026-07-16

> **历史交付，已被实跑结果取代。** 操作者运行了身份刷新前的旧v4；
> `sim_results_v4.zip`已返回但仍为1/9 stage、0 write-data、0 slice完成和无post-run P/D。
> route修复位已证明到达28-slice配置广播，因此不能继续复跑v4。现行结论、身份边界、
> SA插桩和v5方案见`.agents/archive/server-simulation/v1-v4/I2_SIM_RESULTS_V4_ANALYSIS_2026-07-16.md`。

## 1. 结论与边界

v4 已从生成器源头修正 SA accumulate 输出路由：`buffer5.dst_port=0`，即由
SpecArray 向 buffer5 生产数据。修复同时进入通用 Conv 实例生成入口和消费前不变量，
不是对 v3 JSON、bitstream、freeze 或运行包做原地手改。

本节以下内容记录v4交付时状态，不再是当前执行指令。v4已经运行但没有运行后Bank dump，
不能宣称硬件数值或三方比对已经通过；v1～v4包和结果ZIP均作为只读历史证据保存。

## 2. 权威交付物

| 对象 | 路径 | 身份/SHA-256 |
|---|---|---|
| accumulate JSON | `conv_1x1_real.json` | `8535fd06afbdc8ff3ea26f0ec64c179c3fda853a3ebe0b9824720fc9fa10b8be` |
| 语义合同 | `contracts/conv_1x1_lc_pe_stream_semantics.json` | `e6765dad4c0b693f1968c062aefa34078c99f01eff83a6c434cec0a9d4fb21e2` |
| v4 typed request | `artifacts/w5/hwop-0004-00/v4/execplan_request.json` | `eb2609c456f416cb9c92f1268749b7daf23866e0c1421b0e01b3857d3d9c3fb4` |
| v4 preflight | `artifacts/w5/hwop-0004-00/v4/preflight.json` | `796163961d0903516c35db25cbd36de50fb86ff7a10cb8e9d47d16ac9d00c40a` |
| v4 freeze | `artifacts/w5/hwop-0004-00/hardware_freeze_v4/` | freeze ID `dde767638a26dc4bf81cb92c598c1a8def64594544f62679ce41befb924db59a` |
| v4 freeze manifest | 上述目录的`manifest.json` | `651c764b2aab6cb9d985ca9a631587aac6e9fe4d8fef04a600132c324dfd1a2f` |
| v4服务器运行目录 | `artifacts/w5/hwop-0004-00/hardware_execplan_server_v4/` | manifest `48bfe832c7c19392c05b088f060467d02a90c814e48a225620bcfd108be0bd01` |
| v4服务器传输包 | `artifacts/w5/hwop-0004-00/hardware_execplan_server_v4.zip` | 6,662,421 B；`aedbdc5991f8840d6feec3211d640425ea9a52beb58f8ff9d3ef48b2f836458e` |

运行包 manifest 状态为`hardware_execplan_package_validated`，包含9个runtime operator、
175行128-bit execplan、28份Bank_data、252个输入payload、84个runtime scratch payload，
且`preloaded_golden_or_output_count=0`。freeze包含340个受控文件和18份bitstream。

## 3. 修复证据

- 受控源模板`conv_full.json`和通用生成器均把SA accumulate的
  `buffer5.dst_port`设为0；GA-only requant固定为1，然后执行按生产者类型区分的路由不变量。
- 全量可变配置审计已覆盖6份accumulate和128份requant；历史v1/v2/v3 freeze明确排除。
  把SA值负向改回1或把GA值改成0都会在encoder/freeze/execplan消费前失败。
- 首算子正式encoder双跑输出逐文件一致，46条连接、placement cost 0；v4 accumulate
  128-bit bitstream SHA为`d1075bab921356b7f8778da8d00e4af7f581fa116c447c2cecac80b97cc7d1f0`。
- 旧v1与v4 accumulate 128-bit bitstream长度均相同，仅有1个字符位变化：零基第33行、
  从左第4位由1变0。这与唯一字段`dst_port: 1 -> 0`一致；8份requant bitstream未重定义。
- v4 preflight继续得到config-bound P/D全量0 mismatch；这证明配置绑定的软件数值链未
  漂移，但不能替代RTL执行。

## 4. v3不可变性

- v3 package manifest仍为
  `4be4a4aa824545dfff3bf1fcb0f06e0cd86e38a81f9d19e25c271550c3e73e63`。
- 原始`sim_results_v3.zip`仍为
  `9b0b15b7c351228f3f3b4d6163ba6da8391f5d1cddff04a22293eed442f172aa`。
- v4全部使用新目录、新request、新freeze ID和新ZIP；虚拟机不得把v4内容覆盖进v3目录
  后继续沿用v3身份。

## 5. 虚拟机运行与返回要求

解压v4 ZIP后保留顶层`hardware_execplan_server_v4/`及其相对路径。按
`runner_contract.json`预装全部346个SCA payload，在第一个`Start_Comp`前完成170/170
readback且不得含X。然后运行：

ZIP已用POSIX `/`条目名打包，并审计到317个目录/文件条目；包内`manifest.json` SHA-256
与运行目录一致为`48bfe832...0bd01`，可直接在Linux解压。

```bash
make -f Makefile.tb_NDP_Top_new_phy compile sim DUMP_FSDB=1 \
  PLUSARGS='+SCA_CFG=install/cfg_pkg/##########/sca_cfg.json'
```

`##########`必须替换为审计后的v4安装目录；安装/重定位后应另存安装态manifest和SHA，
不能改写根仓包内受控文件。成功返回至少包含：真实命令、退出码、VCS/RTL版本、加载统计、
170点回读、9个stage完成、28份post-run Bank镜像或受合同校验的84个输出区域、完整日志和
必要波形。返回后使用：

```powershell
.\.venv\Scripts\python.exe tools\compare_conv_hardware_execplan_dump.py `
  --package artifacts\w5\hwop-0004-00\hardware_execplan_server_v4 `
  --sim-bank-root <post-run-bank-root> `
  --evidence-root <v4-comparison-evidence>
```

只有P、D各3,211,264元素均0 mismatch，并保存Golden↔NDPFuncModel、Golden↔RTL、
NDPFuncModel↔RTL三份比较，才可把首算子升级为三方通过。
