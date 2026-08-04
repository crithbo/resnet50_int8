# ADR-010：算子配置规则分支 R0 身份与证据冻结

日期：2026-07-22

状态：R0 已完成；用户确认服务器 RTL 当前应与 GitHub 仓库和本地 `NDP_copy01` 一致，暂以本地快照作为目标 profile，但尚未取得服务器侧 SHA 机械核验。允许进入 R1 草案；该身份假设将来由服务器 SHA 补强，不写成跨版本永久事实。

## 1. 目的与边界

本记录冻结规则修正分支开始时实际使用的工具、RTL 参考、候选和证据等级。它是审计输入，不是新的算子配置规则，也不授权修改活动 ndp-sim、生成新静态 JSON 或改写现有候选。

冻结采用双重身份：Git 仓库记录 commit 和工作树状态；所有直接参与结论或候选的关键文件另记大小与 SHA-256。这样可避免干净 commit 叙述掩盖工作树差异，也避免无 Git 的本地 RTL 快照失去身份。

## 2. 仓库与运行时身份

| 对象 | 身份 | 工作树/限制 |
|---|---|---|
| 根仓 | HEAD 0e5f9aaab254ba7d783652662f80bbd8d36e8c8e | 工作树已有大量用户改动；本分支只追加决策记录并更新 plan，不清理无关改动 |
| 活动 ndp-sim | HEAD ec12424516ae0304228dd2321d4e604fe225e04e | 非纯净：M .gitignore；?? README_SERVER_PACKAGE_LOCAL.md；?? jsons/node0004_accumulate_wave0.json |
| 本地 NDP_copy01 | 无 Git 元数据 | 只作为本地服务器/RTL 参考快照，身份由关键文件 SHA 冻结 |
| 服务器活动 RTL/loader | server_rtl_identity=user-confirmed-expected-equal-local-unverified | 2026-07-22 用户确认服务器 RTL 应与 GitHub 仓库和本地一致；未取得服务器 commit/关键入口 SHA，当前按本地快照执行，后续以服务器 SHA 补强 |
| W3 模型图 | artifacts/w3/model_graph.json | 只读模型事实入口，SHA 见候选与数据表 |

本轮 Python 入口为 C:/Users/15383/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe，版本 3.12.13。普通 python 不在当前 PATH。生成候选时使用的临时依赖目录为 C:/Users/15383/AppData/Local/Temp/codex_ndp_sim_pydeps_20260722；其中 numpy=2.5.1、matplotlib=3.11.1、Pillow=12.3.0、contourpy=1.3.3。该目录是临时环境，不可当作长期可复现依赖锁；R2 必须把所需依赖和版本写入正式环境合同。

## 3. 活动生成链关键文件

| 路径 | bytes | SHA-256 |
|---|---:|---|
| ndp-sim/model_execplan/main.py | 7346 | 661623ebf37f0c2fe31a530fc53c756e58408000a371d7cc528301314a4dac7e |
| ndp-sim/model_execplan/src/execution_plan_generator/address_planner.py | 30150 | 2208ffa925c509d2479e2763f323551a36e1b6c1680a112e7519f6356a312ea0 |
| ndp-sim/model_execplan/src/execution_plan_generator/control_registers.py | 85486 | b173e86bd0a8c005ab869923865d82d3a77e119c4e916d1aa1238a9fb3025fb7 |
| ndp-sim/model_execplan/src/execution_plan_generator/json_loader.py | 19576 | f1f6e0316812ebc8382f445b780e3143383ea0c034485d4393711302ab691ffc |
| ndp-sim/model_execplan/config/operator_base_info.json | 15890 | e408606006e5778997b015f6cf90608dad93ef45efe60d73c5a0b675eab096e0 |
| ndp-sim/bitstream/parse.py | 22540 | a6bd0f9dc288b518389a677570cf34a08ebec72a430e9a85c085570d3be869f0 |
| ndp-sim/bitstream/bit.py | 8145 | 6ba6b9b3a0a8f4baed9daa89af8c781db92a3f84b575a1e97126e7a5c9029fad |
| ndp-sim/bitstream/index.py | 20443 | 2b71290671cef1c137e31fdf7e35e89454e3614a3e620f1f5f387f193a128306 |
| ndp-sim/bitstream/config/base.py | 8754 | 100d44403386f17327da1938888156291891f1d564d151c8eb02127e829459cc |
| ndp-sim/bitstream/config/stream.py | 14083 | 00e0610719670f24e22139ee0a3a453ae6e90f90e5d572f578c5f489f5a813d1 |
| ndp-sim/bitstream/config/special.py | 3436 | 0c989cf657eaa429f9b2b37848105abe3448b3926e22e09ae98c42ddd4f8447a |
| ndp-sim/bitstream/config/general.py | 11738 | eb9d5ee9ef273182e05b718aca378f87d0a1ccb5366ae463d8482c8c94c3482f |
| ndp-sim/bitstream/config/mapper.py | 68924 | 104da1e761a02af0074384dfb67e0dc0f07fad3f18fe7ed49537a841cda4867e |

## 4. 本地目标 RTL/服务器入口快照

| 路径 | bytes | SHA-256 |
|---|---:|---|
| NDP_copy01/Makefile.tb_NDP_Top_new_phy | 17662 | 223fbd91f5264d3d7c82ddd77676ae14aa8829e6d1a81c3de9b7b59b1669c203 |
| NDP_copy01/tb_NDP_Top_new_phy.sv | 342393 | 3592ad2b5ff4f631d2cc76402d7ca9979b3e6d6fc2712f9619034d1d6c6e86ba |
| NDP_copy01/rtl/filelists/NDP_Top_phy_filelist.f | 357 | b6720607b2757d50d13de6efc109e240aa32e56b51c7dd7e30ec0150a34e4b6a |
| NDP_copy01/rtl/includes/NDP_Parameters.svh | 37397 | c7b2d96445f3351637ef611d5c03b23c006ebb9bb2a2e4d1212a09872ce5d767 |
| NDP_copy01/rtl/Slice/Slice_Config_Manager.sv | 51314 | ccd999a1e839615ad10e856b7d75e104fcaebafc4e68b14746404430f61ca3c5 |
| NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer_Manager_Cluster_Connect.sv | 24900 | fcdf9372b846a7c51cf968d4cd3e2b4234443ae93c8c22af35724efaef3e611f |
| NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/SA_PE_Control_Block.sv | 15092 | e254af41c5354d93d31cd9196d79a0a365ea880b86286ea0c15e3a4f41122ca6 |
| NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_PE_Float_Control.v | 11857 | 3b52be953e7ac212156218c5448b343f98ebca8dd7ed07849964a25588db465b |
| NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/GA_PE_ALU.sv | 2085 | 8a73c66755df0897034d7bdbc7183f663aeba630d16ccae07e8e879d689eb9aa |
| NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/GA_ALU/GA_PE_Float_CSA.v | 2818 | 5bcc09111624f403cc2aab291f79fd32a6dd40ce7d9624db6306f8cde94906dc |

由该本地参数快照可确认的 profile 是 28 slices、每 slice 4 banks、64 columns、6144 rows、5 个读 buffer 加 1 个写 buffer、4 个 memory read stream、1 个 memory write stream、2 个 neighbor stream、8x8 SA 和 4x4 GA。按用户确认，当前将这些值同时作为 provisional-server-target-profile；服务器侧 SHA 尚未核验，因此 profile 身份为用户确认假设而不是机械证明。

## 5. 候选和模型身份

| 对象 | bytes | SHA-256 |
|---|---:|---|
| W3 model_graph.json | 339932 | f030c5d4e43f63fbbcce771e4c4ea9e88b042be0a2c988e7f51de2c0e17ac410 |
| Decode decode_package_manifest.json | 8300 | 56621f68a59d0962ab627c689982c566e571c54eb278846ff3ffcc6b2c9dfd1f |
| Decode install/execplan.txt | 3770 | a0d8d9ac24b2277ff0a7222605992bb6a3c81e00882daf2197d94fcbe6aaa87e |
| Decode cfg bitstream | 2340 | c8a94efcac7ea7a8a564f25426d03c8886ce91d1003539186307a3dc0cd1e141 |
| MaxPool maxpool_wave0_input_manifest.json | 73803 | a20efd533765a0e2111f7921e2a1c4012d7f41d77af9975bd42db77d6975c0b3 |
| MaxPool install/execplan.txt | 3770 | cf6fb01495acc50c913745bba6f436325f9708e16376f2dc44c98c1d444592bb |
| MaxPool cfg bitstream | 3900 | 13931520925a6a10ccd821340a2fab39db8bbd44be7cf99394d0fc562001dcb3 |
| node0004 validation.json | 1601 | f7ed652a50d2cd1a61159dd547dbd2f5448d0706324856a7483b47bda489cbf2 |
| node0004 input_manifest.json | 139919 | 6c4fb1230e96c4ceac056767eee3bcdb1cd743d3a988820b742be396f6e206de |
| node0004 install/execplan.txt | 8970 | d61253c090d812e7ecb22e2520c840165d880e49ac300d20a4b2058b8cac3c57 |
| node0004 cfg bitstream | 4550 | a7296e83dee267c0ad23f8d914dd02af39f3a7ad2e732e15636d9ab033088992 |
| 根目录 conv_1x1_real.json | 16013 | df73611d0b3141b50a029c002c7ab0e61e8fa5a47bc0a74dcb3446be69e79c16 |
| 活动别名 node0004_accumulate_wave0.json | 16013 | df73611d0b3141b50a029c002c7ab0e61e8fa5a47bc0a74dcb3446be69e79c16 |

## 6. 证据等级台账

| 样例/集合 | 结构或编码 | 软件数值 | 服务器自然完成 | 服务器数值 | 当前允许结论 |
|---|---|---|---|---|---|
| jsons/* 参考目录 | 来源版本不等于当前 HEAD | 未逐项归档 | 用户确认可运行，原始日志未逐目录归档 | 未证明 | E3-reported 参考类别；不能作为配置来源或 E4 数值基准 |
| decode_summac 当前候选 | E1，通过本地来源/结构/重复生成 | 未做 | 用户确认完整跑通，原始命令/日志未归档 | 未做 | E3-reported 当前格式基线 |
| node0002 MaxPool wave0 | E1，当前格式自洽 | E2-data：桥接脚本直接用独立 NumPy 公式对 W3 A/D，28 tile mismatch=0 | 待测 | 待测 | 只能证明数据/layout 入口；不能证明静态 JSON 已执行正确 |
| node0004 accumulate wave0 | E1，来源/结构/重复生成通过 | 无数值通过声明 | 待测 | 待测 | 单 stage 冒烟候选；无 requant、无完整 Conv 结论 |
| Conv v18 | 历史本地候选曾通过当时交付检查 | 历史局部证据，不属于当前链 | 进入首 accumulate 后停滞，未自然完成 | 无 | 强负向活性证据，不达到 E3 |
| Conv v19 | 历史本地 placement/P/D 等通过 | 历史局部证据，不属于当前链 | 434/434 preload 和首波 Start 后停滞，未自然完成 | 无 | 强负向活性证据，不达到 E3；排除漏发首波命令等部分原因 |
| configs/conv 旧候选 | 历史 official encoder 候选 | 无当前硬件数值 | 未通过 | 未通过 | E0-history；可作负例/诊断，不可作活动配置真值 |
| ndp-sim/jsons 54 份活动 JSON | 已完成只读结构/位宽初筛 | 未逐项证明 | 未逐项证明 | 未逐项证明 | R3 前不得整体宣称 E0/E1；编码器本身存在 fail-open |

## 7. R0 初始问题裁定

1. TGT-001：address planner 的 MAX_ROWS=8192 与当前 local/provisional-server target profile 的 DDR_ROW_SIZE=6144 矛盾已确认。外围验证一律采用 row<6144；服务器 SHA 到位后只复核 profile 身份，若服务器文件与本地不一致则重新裁定受影响结论。
2. ENC-001/002：非零 mapping penalty 被接受、未知字段被忽略、位宽值取模、无效连接/地址可 fallback 的实现事实已确认；R3 必须在原生 encoder 外 fail closed。
3. SA-001：row/col 映射仍是阻塞歧义，不能通过重命名或直接翻转解决。
4. CFG-001：CONFIG enable/update/clear 的跨 stage 语义已由本地 RTL 证明，但仍需最小两阶段数值/状态微测才能获得 E4/E5。
5. LIVE-001：旧 Conv 缺 B-prime/READ2 生产者与 v19 停滞相关，但不能宣称是 v19 唯一根因；只能升级为生产者闭包必须检查。
6. QNT-001/COV-001：量化参数未完整进入 handler、ResNet 算子族和 Conv 变体不全，属于已确认能力缺口。

## 8. R0 退出判定

R0 退出门已满足：活动 commit 与工作树差异已记录；本地 RTL/入口和候选由 SHA 冻结；服务器身份记录为用户确认的 expected-equal-local、SHA 未核验；证据等级没有把运行、自然完成和数值正确混淆。下一步允许进入 R1 真值表草案和只读字段审计。
