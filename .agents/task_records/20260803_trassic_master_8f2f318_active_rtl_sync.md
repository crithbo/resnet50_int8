# 2026-08-03 Trassic master 8f2f318 活动 RTL 同步与任务恢复

## 裁决

- 主线：`019fbec2-fe93-7e03-9314-cff6f222f33d`。
- 用户明确确认硬件侧已修复 `SA_PE_Float_Control.v` 末端端口逗号，并授权主线核对、
  同步本地活动 RTL 后通知相关 owner 继续。
- 权威源：私有 GitHub 仓库 `xlsjdjdk/Trassic2.0_RTL`，branch=`master`，
  commit=`8f2f3181c1103d705cdf9b9722959e7315f8b875`。
- 裁决：
  `AUTHORITATIVE_MASTER_SYNC_AND_FOCUSED_COMPILE_PASS`。
- 本轮只是把云端权威源精确同步到 `NDP_copy01/rtl`；没有自行设计功能 RTL，
  没有生成服务器包，没有上传、服务器运行或取得 lease。

## 漂移与同步

- 同步前活动
  `NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_PE_Float_Control.v`
  SHA256=`c6018e762411e14346bfec672b273b826f893b11c5de0cfb38fca674f9d33c4b`，
  line 50 为 `output[1:0] o_Config,`。
- 上述旧字节 focused Icarus compile exit=`1`，明确诊断
  `Superfluous comma in port declaration list.`。
- 云端 current 文件及同步后活动文件 SHA256=
  `4214262e12ab80bf3be867f558d762e134c3122f16df4f7d08063e383242c4e6`，
  line 50 为无逗号的 `output[1:0] o_Config`。
- 旧 `b7acbe5` 同步收据曾把仍含逗号的旧字节标成该源身份；本记录以 current
  master archive、逐文件 hash 与实际编译证据正式取代该错误来源归属，不回写或删除旧
  task record。
- 共精确同步 18 个源/文件表路径：15 个变更、3 个新增；完整 before/after SHA
  见 machine report。未删除任何路径，也未复制 15 个云端 VCS `csrc/*.so` 生成物。
- 同步后 `.v/.sv/.vh/.svh/.f/.bak` 共 `2011/2011` 文件，活动树与云端树
  different/missing=`0`。全文件差异仅为上述 15 个未复制的 generated `.so`。

## 来源收据

- 下载归档：
  `C:/Users/15383/Downloads/Trassic2.0_RTL-master (2).zip`。
- bytes=`76546459`。
- SHA256=`8947ee990100b68f8ae082bc1934d2f9b296ee225a4f8d12e4bf4c428810dcab`。
- 归档解压：
  `artifacts/rtl_sync/trassic_master_8f2f318_20260803/Trassic2.0_RTL-master`。
- machine report：
  `artifacts/rtl_sync/trassic_master_8f2f318_20260803/report.json`。
- machine report bytes=`8488`。
- machine report SHA256=
  `4a798e2257ece9d49d64ff8fc00acc826fef3d4dbd35291e26e88f141c273e18`。
- machine report JSON parse、18-path receipt 与 relevant tree zero-diff 均通过。

## 本地 HDL 正控与负控

- frontend：
  `Icarus Verilog 12.0 (devel) (s20150603-1539-g2693dd32b)`。
- 同步后的 exact `SA_PE_Float_Control` focused compile exit=`0`。
- 以活动 SA_PE 子树及 utils 的 34 个 `.v/.sv` 源分别 elaboration：
  `SA_ALU=0`、`SA_PE_ALU=0`、`SA_PE=0`、`SA_PE_Group=0`。
- 同步前旧文件作为相关负控，compile exit=`1` 且精确复现末端逗号诊断。
- claim boundary：这关闭本地 exact source identity 与 focused syntax/elaboration 门；
  不替代服务器/production full-design VCS、DUT natural terminal、formal D 或 E3/E4/E5。

## blocker delta

- closed：
  `SA_FLOAT_CONTROL_ANSI_PORT_TRAILING_COMMA`。
- node0075 可从 current 磁盘恢复 owner 审计与 handler/materializer/E2 工作；旧
  `TERMINATED_AT_FIRST_NONEXPRESSIBLE_HARDWARE_LEAF` 状态被本记录取代。
- 保持开放：
  `B_MATMUL_NODE0075_FINAL_A_CONSUMER_MATERIALIZER_MISSING`、
  `SA_INT32_NEGATIVE_PSUM_FULL_WIDTH_RECONSTRUCTION`、
  `B_QUANT_TAIL_SIGNED_INT32_INGRESS`。
- 云端 current `SA_PE_Float_CSA.v` SHA256=
  `ea24759841d990f230f9c33a111f934e107c996a85b2f5ea00c9408ca73d0223`。
  full-width 修复语句仍被注释，活动逻辑仍分别赋值 `[30:0]` 与 `[31]`，所以不得把
  端口逗号修复扩大为 negative-psum 修复。
- Conv native-four-lane owner 已证明真实 W3 存在 `(-5,+5)→0` occurrence，而该
  旧活动逻辑输出 `INT32_MIN`；current master 仍保留同一 live 语义。因此性能路线继续
  `HARDWARE_CAPABILITY_BLOCKED`，只需做 current identity 的 receipt-only 复验，
  不重做 53-Conv 枚举、不进入 E2 或构包。

## owner 回传要求

- node0075 owner：
  `019fc775-8de0-7f10-bc4a-026a4673776f`。收到本收据后从 current 磁盘重新读取
  plan/rules/RTL，关闭旧逗号叶并继续到下一个精确 blocker；完成 materializer/E2/包
  或再次终止时主动回传主线并提交 RULE_CONFIRMATION/RULE_DELTA。
- Conv native-four-lane owner：
  `019fc783-1146-7901-9e40-64d0ed8e052d`。只做 current identity 与既有
  `(-5,+5)` 反例的内容中性复验，保持 fail-fast、PACKAGE_RELEASE=NONE；禁止把
  current 文件 SHA 变化误作功能修复。

## current 规则收据

- `.agents/agent.md` SHA256=
  `d9fe95839c2c92a83083d956392a66876c1007fbb7922522c6a8920babab6721`。
- 生成前必读索引 SHA256=
  `db339fb8f47105b76deef85cdd43cfc85af6358a0c8155571fde54c2006f26c5`。
- 算子配置规则 SHA256=
  `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171`。
- NDP 硬件字段语义 SHA256=
  `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055`。
- INT8-SA 专项规则 SHA256=
  `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`。
- 服务器包规则 SHA256=
  `5761987d07f425a316bd845e390405c0c64d78c9a371b9cce22cc491c8f25f48`。
- 硬件仿真入口 README SHA256=
  `4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7`。
- plan start SHA256=
  `8bde3e23b345853d4058099eb8215b4a710ce9adbf182fcbabf14fea8f6d4aec`
  （mutable provenance only）。
