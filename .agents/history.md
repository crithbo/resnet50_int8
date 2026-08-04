# ResNet50 INT8 压缩历史与证据台账

最后更新：2026-08-02（活动 plan 改为覆盖式当前快照，旧状态归档到本文件）

本文件只用于追溯。当前任务和命令看`.agents/plan.md`，稳定入口看`.agents/agent.md`；`.agents/rules/`保存从活动实现和实证提炼的配置/服务器检查清单，不是独立事实源。历史细节优先通过版本表、关键身份和archive引用压缩；本文件必须保持少于1000行。

## 0. 2026-07-31 活动计划压缩

- 原 `.agents/plan.md` 共1,734行、120,688字节，包含2026-07-27至2026-07-31的
  逐版本 return、隔离包、规则门和执行叙事；原 SHA256 为
  `bd0d1c03d7c25533253547aa82e380a30358eb090a57e9014fc374c6c0705ad2`。
- 原文迁入 `.agents/history/plan_pre_current_compaction_20260731.md`。
- 新 `.agents/plan.md` 只保留当前三只可运行诊断包、其他算子族当前阻塞、当前执行顺序、
  服务器硬门和开放 blocker；历史包身份不再作为活动命令来源。

## 1. 2026-07-19 文档收敛与服务器制品清理

### 1.1 文档职责重构

- `agent.md`删除v7～v10r8逐版本叙事，只保留稳定项目地图、工具入口、证据边界和长期协作规则。
- `plan.md`删除v1～v10r8旧决策树、旧执行命令和已完成计划，只保留当前freeze、三个非HDL阻塞、实现顺序、两轮自检和服务器验收门。
- 本文件吸收上述历史，并把原1042行的逐日/提交叙事压缩为里程碑、服务器版本表、结果ZIP台账和关键恢复点。
- 由服务器错误提炼、且仍有当前证据支持的防复发检查保留在`.agents/rules/服务器测试包生成规则.md`，不会随旧package删除；后续事实若推翻其必要性，应精简或更正规则。

### 1.2 Artifact清理策略与结果

用户确认新的保留策略：从未上服务器的旧revision在错误进入规则/history后删除全部生成包；真实上过服务器的revision只保留原始返回结果ZIP，不同时保留package、overlay、展开结果或派生分析树；只允许最新工作revision暂留生成物。typed request、preflight、官方encoder合同和数值freeze不属于服务器生成包。

本次对`artifacts/w5/hwop-0004-00`执行精确清理：

- 删除76个旧生成/展开对象，删除前合计2,629,233,400字节。
- 删除范围包括旧`hardware_execplan`、`hardware_execplan_server_v2～v10r7`、`server_overlay_v5～v10r7`及其package ZIP/sidecar/preparation/selfcheck，以及`hardware_server_run_*`展开/派生分析目录。
- 未删除任何`hardware_freeze*`、typed request、preflight、`v4～v10`小型数值身份目录、根目录原始`sim_result*.zip`或最新v10r8工作revision。
- 旧package/overlay删除后不再能从本地直接恢复，但它们都是可再生产物；需要时只能按当前规则从相应freeze重新生成新revision，禁止恢复旧runner继续执行。派生分析可从原始结果ZIP重新计算。
- v12接替后，已按同一策略删除从未上服务器的v10r8 `hardware_execplan_server_v10r8`、`server_overlay_v10r8`、ZIP、sidecar及两份旧selfcheck，共602个文件、139,323,345字节；v10r8数值freeze和历史身份保留。
- 2026-07-20复审确认v12/v13虽已撤权但生成物仍在工作区；v15接替并完成终审后，按精确清单删除两版package/overlay/ZIP/sidecar及v12旧selfcheck，共10个目标、1,204个文件、279,594,366字节。两版typed request相关输入、candidate、preflight、hardware freeze和server-profile输入均保留。
- 2026-07-21 v18接替后，按精确清单删除v14诊断package/overlay/ZIP/sidecar/selfcheck以及从未上服务器的v15～v17完整生成目录，共2,415个文件、559,255,614字节。v14 typed request、candidate、preflight、hardware freeze和server-profile输入全部保留；v14服务器失败返回仅保留已核验的外部SHA/reason/detail，不用输入ZIP冒充结果证据。

## 2. 最新数值恢复点与服务器状态

| 类别 | 身份/位置 | 结论 |
|---|---|---|
| 根仓W0～W3封版 | `35a4fde106d102b0e165e7eb13d60f7dd980db71` | 编排、模型图、lowering和golden早期恢复点 |
| 根仓历史硬件交付 | `e9b6492098c2101aa86afd83bf95e8024fa6e8df` | 旧硬件交付恢复点，不代表当前服务器候选 |
| 根仓数值闭环 | `1388dede4aac53a77d02dec0b24db0ad2d35ef1f` | 首例配置绑定数值闭环恢复点 |
| NDPFuncModel v19功能基线 | `cb262bb9cef35107776c802e624736a279f288e3` | 已清理tracked pyc并推送private mirror `conv_func`；v19继续绑定此身份 |
| 当前本地参考仓恢复点 | `ndp-sim-ref@d4ffc32c9b29a858d83e13706cd837c5549521a4`；`NDPFuncModel@a1d975ee2d6d9200b8df0deea3e2ffc13ce0d05e` | 2026-07-21本地提交，已回填`repos.lock.json`；未推送，不反写v19冻结身份 |
| v14历史typed request | `artifacts/w5/hwop-0004-00/v14/execplan_request.json`，SHA=`a4d6e56ab85271cae8870a3ed667f3c7aa24dee9bc5bc9b4ffefe97c553e4990` | v14/v18历史只读输入，不是current |
| v14原生生成身份 | commit=`056b1c3c08b24e098636615d9001e8a974beb09f`；source-tree SHA=`ce7fcb683f2b816ec3bbc06dd4ac0f982c3b3dfcd5f52bee893625b88ac190e6` | 已冻结candidate的历史输入；不是当前工作树摘要，也不是服务器Git依赖 |
| v14 candidate | ID=`d7d1f57d9f113ad500cf2008fe93f773a751e5f31f07f01b19b29b4b247984ad`；manifest SHA=`2b6e3f12639da0f9551faa005cf207247c5ea9d660c3d69c5d623fd47eea2c47` | `v14-candidate-02`，9个bitstream record，A/B一致 |
| v14 preflight | SHA=`fed3d9f2f986b5d8d0b4da1138dec2e58aab0c2602d7b2aa3ee334f4b9c66cb7` | Golden/NDP P/D mismatch=0，绑定v14 candidate |
| v14 freeze | ID=`052270e61d7e8adf7216e807b34cb612bd3ddb543ca755a9d9d294aee6cbbb7a`；manifest SHA=`83d0b05bec72f10ab5356ca3d47cd1e39c72173f21ff3d8b317735b05140408c` | 511个声明文件、exact-set/ID重算通过 |
| v14诊断输入ZIP | 历史路径`artifacts/w5/hwop-0004-00/v14/server_overlay.zip`；SHA=`c95435f01d4a6c1b719334d80762ee7a137efd76fb2dd5e370d07e314ab1ae1a` | 两轮本地审计曾PASS；后续复审发现runner/审计缺口，正式发布资格撤销，已用于一次诊断性run1；本地生成副本已按归档规则删除 |
| v14服务器返回 | 服务器路径`run/sim_results_v14_run1.zip`；外部回传SHA=`6c103919c1258e241751dc8e4331f63ef35694c5a664b4c5c174451db337fb72` | preflight失败、未进入编译/仿真；reason=`server_filelist_member_outside_root`，detail为活动filelist物理路径在服务器根外，run2未执行 |
| v15历史输入ZIP | 历史SHA=`d81ed87db41d5c64c8d0a44209c4d2cc08baaa6f24962da2f00b37e7dad1fc27`；runner SHA=`4680f1409769fdc26821927835630fe1e67a3a350d97a0fba04379682354eeb7` | 复用v14只读数值freeze；后续复审发现runner顺序、双跑provenance和实文件不变性缺口，已撤权、从未上服务器且生成副本已删除 |
| v16历史输入ZIP | 历史SHA=`3d4fe99866aa00a0b85caf208fc57db61793d709e7b3a033697f8fb6baefd031`；runner SHA=`28eea621b304add4867fb773f7b05817ee849dfcd60fa681b4f13d0a734cbf11` | 后续故障注入发现清理异常收口、合并态exact-set、Make环境、`DIR_HOME`provenance和报告不可覆盖缺口，已撤权、从未上服务器且生成副本已删除 |
| v17历史输入ZIP | 历史SHA=`0c786f39848bd97e26a32aad747444ca3451527ad7cca6667a6217b4d32c5357`；runner SHA=`1b1cff49a858042b5ebccff72d3e834a980d3c3e2dbddf53272d8669e2ac169c` | 修复v16缺口并完成两轮审计；最终总览发现包内README口径未覆盖新增合同，未上传、已撤权且生成副本已删除 |
| v18历史输入ZIP | `artifacts/w5/hwop-0004-00/v18/server_overlay.zip`；SHA=`2e669527ccf426c6f940f9f706b41406eb93257f9b722d4af927503e656c25ad`；runner SHA=`db744be4f84d4b105e5f10838d7980d9725c612f5aef3a04935017859df398ae` | 真实run1完成preload后停在首个accumulate，手工终止；已撤权，禁止run2 |
| v19历史typed request | `artifacts/w5/hwop-0004-00/v19/execplan_request.json`，SHA=`105f2bc78556f7ae8a33cd2c20bb3b6e63a4acc40e1138ba90a125b12a577e06` | bias tile修复后的独立数值/硬件身份；只用于复现分析 |
| v19历史candidate/preflight/freeze | candidate ID=`d5f6af19413919a72d761f99b61d35afdee5278e172a363f28055d937dd37898`；preflight SHA=`98febe58038352eefff14b2c88c19e332cdf3fdcf1531a16e91137c5ab0debbc`；freeze ID=`71686cf225194fbe6f9a0db73e7adf515a02ce252598ac58f6e5090793470b27` | A/B、parsed/mapping/placement和Golden/NDP P/D通过；512文件freeze；服务器失败不撤销这些本地事实 |
| v19历史输入ZIP | `artifacts/w5/hwop-0004-00/v19/server_overlay.zip`；SHA=`0874e8eeb8495ca46e3ddda54e1273c05e5c9a10b78c468e4584ba33398f06b2`；runner SHA=`1ae95b832c4273513c152ae453164346563fb2064c15c23255da44b5a7d9d8ee` | Round 1/2本地PASS；真实run1首stage停滞，永久撤权并禁止run2 |

### 2.1 v11 原生重生成、复审撤权与清理（2026-07-20）

- `ndp-sim-ref/model_execplan` 新增默认关闭的 server profile、隔离 mapping cache、A/B candidate validator 与原生同-mask barrier helper；clean commit=`ff3e083d620eaef5711e99ecaad2c0d97a89bc27`。
- DeepSeek RMSNorm/Rope/Softmax 默认输出文件数、总字节数和语义树 SHA 与改动前一致；原生6项定向测试通过。
- candidate ID=`ad1f1a24a1d42338d7743514f384762f40e1996ca1968eb9d512095dea6e8a77`，manifest SHA=`a4a48779c30940f64d65a4a0860c778bd922233f0c222066d20aa44c02f31aeb`，161文件、9配置、A/B一致、dirty=false。
- 新preflight绑定candidate且P/D mismatch=0；新freeze ID=`6741e2a8ac34e597897f02be21b4bcb9608b4b92c4c4ce0d020c4ab3259dafde`，不沿用v10r5身份。
- v11 package重新推导出12 stage、314行execplan、28 Bank、434 preload段、168 readback段；4 KiB报告确认433个语义对象中169个真实触发、264个未触发，最终SCA/SCA_D重算一致。
- 最终`server_overlay.zip`为2,984,689字节，SHA=`e4840fd26e04cf7e2a62a6b8490d92172b8f4b23f8b17a54ee25d0b16e72433e`；当时记录为生成链和独立解包审计PASS，但后续复审证明该结论不足以授权执行。
- 复审确认runner的3个GNU awk程序使用内建函数名`index`作为变量，在GNU Awk 5.3.2中语法失败；目录不存在独立落盘的`selfcheck_round1`。同时freeze可接受额外文件/伪造ID，candidate ID包含本机绝对路径。
- v11从未上服务器，ZIP SHA、candidate和freeze身份仅保留在本历史用于追溯；上传/运行资格永久撤销。修复完成并由v12接替后，`artifacts/w5/hwop-0004-00/v11`生成树按保留策略删除（1,600个文件、192,333,759字节），不得恢复旧runner继续执行。

### 2.2 v12 修复后本地双审计闭环（2026-07-20）

- 原生server profile升级为candidate schema 0.2；clean commit=`b1fa9c86304b8341a78db0d4e34ad66810d65a76`，candidate命令身份用仓内相对/占位路径表示，跨输出根ID稳定；原生server/typed transport 8项测试PASS。
- candidate ID=`63833c64cc4a76ffd8e9ce24339a1838872211b5778a97f5ac354aaaccb1c460`，manifest SHA=`f9db6d085b9c1c5f7d91b3a3230f6b48ba18135e529d6e125b9f1065b39a5000`；config-bound preflight SHA=`e777fadbdc60f64b5d942d3b23e84e661ffa1e19bc94cc7fb4bf61695f71c828`且P/D mismatch=0。
- 新freeze ID=`0df3dddf2e0db3493aee7d62bd3d8c0849fdafbcddfca2b3dc78a5f115e885fb`，manifest SHA=`f6008620b8b0a04bd79d8805097f8dc5aaef228fab3205607159f55479ace448`；导出要求新/空目录，验证重算ID并要求511个声明文件exact-set，额外文件、symlink和伪造ID均fail closed。
- package manifest SHA=`a3eac3676dfa4f9bbc504c8042c0588da66c4b0246810c0a50a190eb92c14819`；重新推导12 stage、5对fixed observer、314行execplan、28 Bank、434 preload段、168 readback段。4 KiB报告仍为433个语义对象中169个触发、264个未触发，维持“可能存在且当前按存在处理”的条件风险边界。
- runner修正3处awk变量名；正式Round 1在GNU Awk 5.3.2上覆盖272个预装文件、0/合法/额外/缺末尾LF/final-console行为并PASS。Round 2仅从最终ZIP全新解包独立重算并PASS；两轮共同绑定runner SHA=`0c7072b2514237ff7af88686c6970e0d7821198c9aa00400ed8881996f937a99`。
- 最终ZIP为2,984,699字节、289文件、0 HDL，SHA=`5a21035b09d9a0998217fee74a7ebbb4650a21358aece7f652b5cc64c28af4bd`。它当时曾被记录为唯一获准上传候选，但尚未在服务器运行，G6/G8仍为false；本地PASS不能替代VCS自然完成和Golden/NDP/RTL三方P/D bit-exact。

v12后续复审发现服务器源码闭包、失败归档、run-ID隔离和两次回传稳定性合同仍不完整，因此上述“当前唯一候选”结论已撤销。该句仅保留为当时事实，不再授权执行。

### 2.3 v13中间撤权、v14本地闭环与诊断性run1（2026-07-20）

- v13仅是修复过程中的中间revision，从未获准上传；它暴露并推动修复递归活动filelist/source inventory、统一失败归档、run1/run2隔离、返回物理region稳定性门与正式launch argv绑定。
- 首个v14 candidate因沿用错误的requant encoder合同而作废，未从该candidate继续生成可发布freeze/package；随后从修正后的原生工具重新建立`v14-candidate-02`，candidate ID=`d7d1f57d9f113ad500cf2008fe93f773a751e5f31f07f01b19b29b4b247984ad`，manifest SHA=`2b6e3f12639da0f9551faa005cf207247c5ea9d660c3d69c5d623fd47eea2c47`。
- 原生本地生成commit=`056b1c3c08b24e098636615d9001e8a974beb09f`，source-tree SHA=`ce7fcb683f2b816ec3bbc06dd4ac0f982c3b3dfcd5f52bee893625b88ac190e6`。commit只用于本地内容追溯，服务器没有Git且不依赖该身份。
- config-bound preflight SHA=`fed3d9f2f986b5d8d0b4da1138dec2e58aab0c2602d7b2aa3ee334f4b9c66cb7`且P/D mismatch=0；新freeze ID=`052270e61d7e8adf7216e807b34cb612bd3ddb543ca755a9d9d294aee6cbbb7a`，manifest SHA=`83d0b05bec72f10ab5356ca3d47cd1e39c72173f21ff3d8b317735b05140408c`。
- v14 package manifest SHA=`0608c74065cad019119aa73de33a1b5ef137210b86d977f53020130a53da6c78`；重新推导12 stage、`Repeat_Num=5`、314行execplan、28 Bank、434 preload transport、168 readback transport和84 semantic readback region。
- 发布前复审先后发现并修复：`${DIR_HOME}`受限NIC include被通用路径门误拒、Windows本地Bash适配、通用fixture外部include计数假设、Round 2读取runner contract路径错误，以及服务器无Git约束未完全写入README/审计器、实际使用的`basename`/`mktemp`/`xargs`未全部进入命令能力门。每次影响最终制品的修复后均重新生成ZIP并从Round 1开始。
- runner递归解析30个filelist、846个source与1个受限外部vendor include；外部树必须与in-tree活动NIC副本逐文件同构。该检查只用普通文件枚举与SHA-256，不调用Git。
- 最终runner SHA=`d5a4b65e65b0644dc0a63189fe9619fc2d244120ac087c30be839f11601b383b`；最终ZIP为2,989,930字节、289个entry、0 HDL，SHA=`c95435f01d4a6c1b719334d80762ee7a137efd76fb2dd5e370d07e314ab1ae1a`。
- Round 1报告SHA=`1bf7d6c04e607bed2dec68cf058788677ff691c3d158f8be4231fdead066c67f`，Round 2报告SHA=`00ebaef039f30c3a0bd62b2a7da614bd4829cc9dd6fcbf7bfea3b2f6c7d85b8d`；两轮均PASS并绑定同一ZIP/runner身份。
- v14本地闭环后再次静态复审，确认正式runner仍有三项缺口：外部include期望数量受环境变量影响、Python模板中的CR文件名判断被LF归一化破坏、正式run ID未限制为run1/run2；独立审计未覆盖这些语义。旧v12/v13生成物也尚未按归档规则清理。因此v14正式发布资格撤销，仅保留诊断用途。
- 用户随后在服务器执行v14 run1；runner在preflight阶段生成`run/sim_results_v14_run1.zip`并退出，未进入VCS编译或仿真。回传摘录确认`preflight_report.json`为`status=failed`、`reason=server_filelist_member_outside_root`，`preflight_error.txt`显示`/home/liuyk/Documents/Trassic2.0_RTL/code/NDP_rtl/filelists/NDP_Top_phy_filelist.f is outside /home/panqs/ndp/NDP_copy01`，外部回传SHA-256=`6c103919c1258e241751dc8e4331f63ef35694c5a664b4c5c174451db337fb72`。该问题属于v14新增源码闭包物理前缀校验过严；run2未执行，G6/G8保持false。

### 2.4 v15过度校验精简与正式本地闭环（2026-07-20）

- runner删除递归filelist/source/include解析、物理路径根内门、外部vendor数量/树同构、TB源码字符串和`make -n`文本匹配；只要求Makefile、TB、顶层filelist三个逻辑入口可读，并记录逻辑/物理路径、大小和SHA。真实HDL问题交由Make/VCS自然报错并归档。
- capability/source provenance升级为0.8/0.3；`SERVER_RUN_ID`在创建目录前只接受`run1|run2`，CR/LF使用原始十六进制字节判断，服务器runner/README均无Git依赖。独立ZIP审计将旧递归解析和过严reason列为禁止片段。
- 原生candidate生成入口新增同级内容寻址validation sidecar；preflight/freeze只复验sidecar、manifest和当前exact-set/SHA，不再重复完整candidate语义验证。freeze删除整个仓库`dirty=false`硬拒绝并冻结validation report；公共Conv身份检查保留固定HEAD/祖先关系，dirty仅作provenance。DeepSeek默认入口未改。
- v15只读复用v14 freeze ID=`052270e61d7e8adf7216e807b34cb612bd3ddb543ca755a9d9d294aee6cbbb7a`和manifest SHA=`83d0b05bec72f10ab5356ca3d47cd1e39c72173f21ff3d8b317735b05140408c`。v15 package manifest SHA仍为`0608c74065cad019119aa73de33a1b5ef137210b86d977f53020130a53da6c78`；数值不变性报告SHA=`6cbb05727a379e546fe728e59073729bdd642acc5d687b71a7c6a80501e59f12`，结论为完整manifest和声明文件身份一致。4 KiB仍为433个语义对象、169个触发。
- Round 1首次暴露overlay manifest未顶层携带package preflight摘要，修复后又暴露Windows无symlink权限；fixture改为优先真实symlink、无权限时仅probe使用`readlink` shim。1037 sink自检改为完整唯一路径dry-run，避免Windows本地低价值symlink耗时；正式Linux runner仍创建真实`/dev/null` symlink。所有中止overlay均精确清理后重建。
- 最终runner SHA=`4680f1409769fdc26821927835630fe1e67a3a350d97a0fba04379682354eeb7`；ZIP为2,986,153字节、289个entry、0 HDL，SHA=`d81ed87db41d5c64c8d0a44209c4d2cc08baaa6f24962da2f00b37e7dad1fc27`。Round 1报告SHA=`34f7ff1a21ed6c9369293f25958c197760ef9a0995f291d18d47708f54e00917`，Round 2报告SHA=`3f4f4211b5af16555f3b7b4a602b0e9b88ce6e4df9de79ba3c8be757737ada63`；两轮均PASS并绑定同一ZIP SHA。
- 最终相关根仓测试43项通过、15项历史制品按设计skip；原生server-profile/typed-transport 8项通过；完整Conv package/return端到端关键用例通过。v15尚未在服务器运行，G6/G8仍为false。
- 发布前终审再次以当前验证器分别检查v14参考package和v15候选package的实际文件树，均为`hardware_execplan_package_validated`；最终v15 ZIP从sidecar全新解包的独立审计再次PASS，关键SHA、289 entry、0 HDL及28/314/12/5/434/168/9计数均未变化。
- 终审发现并修复一个只影响未来原生candidate生成的晚失败问题：候选旁已有validation sidecar时，旧实现会先完成A/B生成再在报告写入处冲突；新实现于任何candidate目录写入前拒绝并由单测证明零残留。该入口未参与v15只读freeze复用链，因此未修改v15 package/overlay/runner/ZIP或自检报告；下一原生candidate仍须刷新source-tree合同并建立新身份。

### 2.5 v16/v17复审撤权与v18最终本地闭环（2026-07-21）

- v16先修复v15的runner自身份顺序、双跑入口provenance、实文件不变性和readback重复扫描；后续直接故障注入仍证明清理异常可能在删除旧return后无归档退出，并发现静态install未拒绝额外文件、Make控制变量可改变实际行为、`DIR_HOME`未进入双跑provenance和报告冲突处理过晚，故永久撤权。
- v17把失败函数/ERR trap和完整命令门放到清理前；具备证据原语后的清理异常统一归档，永久缺少`rm/mkdir`时stderr-only且旧证据不变；同时增加静态install actual exact-set、Make环境清除、`DIR_HOME`/vendor provenance、manifest原始字节比较和报告不可覆盖。两轮本地审计通过，但包内README没有完整表述新增运行合同，规则/实现/交付说明不一致，因此未上传并撤权。
- v18从同一v14批准freeze重新生成，package manifest SHA=`0608c74065cad019119aa73de33a1b5ef137210b86d977f53020130a53da6c78`；不变性报告SHA=`c8ce8d40411bcbf77d82128ca07cfeef68059ba0e35f77927f338ed12ac8a23d`。包内README与runner口径统一，服务器不依赖Git。
- v18最终runner SHA=`db744be4f84d4b105e5f10838d7980d9725c612f5aef3a04935017859df398ae`；ZIP为2,989,114字节、289个entry、0 HDL，SHA=`2e669527ccf426c6f940f9f706b41406eb93257f9b722d4af927503e656c25ad`。Round 1共20个行为用例，报告SHA=`5013282e87972d2b407481b1fe909727666176c32d75f839d3acfc74be1c922f`；Round 2独立解包报告SHA=`d344bb00a8fe4ede4b3e7574e367e2a85f6b6a3cd9d73e32751a988b8b8f54d0`；两轮均PASS并绑定同一ZIP。
- 发布前最终回归：原生server-profile/typed-transport 8项PASS，合并transport/freeze/preflight/overlay 45项PASS、15项历史skip，完整`tests.test_conv_execplan_hardware` 11项PASS；权威package检查和最终ZIP无报告独立复审再次PASS。

### 2.6 v18真实停滞、bias修复、v19本地闭环与真实失败（2026-07-21）

- v18真实run1完成434个preload后进入首个accumulate，fixed observer长期停在`0/5`。手工终止返回`sim_results_v18_run1.zip`（86,794 B，SHA=`2f33f34f626b2b1fe71502da5fe10e87eb67fb21d3a13404c528fbc130dbfeca`）和补充诊断`v18_run1_deadlock_extra_1784611151.zip`（217,860 B，SHA=`6b833a69ae92e9fb9c9147d783d01ece803e7c4f98c3c0d62721b8824c574dc7`）均不是自然完成证据。
- RTL/encoder静态反查确认：v18 stream3只按两个Kblock触发，buffer4 lifetime=1只产生一次SA读取；`SA_PE_Outbuffer`每个Q8×K8 tile需要四次bias握手初始化完整16项psum组。生成器改为LC10 Kblock→LC11 H→LC12 Qblock分支、stream3 stride=`[32,0,0]`、GROUP2同源且buffer4 lifetime=4。
- 原生server-profile prepare工具在配置变化时只从typed semantic evidence刷新config SHA/connection count和mapping seed；缺证据即失败。DeepSeek默认入口未改。v19 candidate ID=`d5f6af19413919a72d761f99b61d35afdee5278e172a363f28055d937dd37898`，manifest SHA=`5146329288431fb970b26e35b70a93c2955515753430026327f36d76fe37589f`，validation SHA=`7ddd85d4b3afa9ce08385d588031ff9881fb1a79e7982a753d97a1db9dcc0764`。
- v19 accumulate JSON SHA=`f26a3346859601055abc9cb88dd0b7c3650e5fcc4fae6d1f85d2562aba0ad8ed`；正式码流为29行×128-bit，LF规范化逻辑SHA=`7d85938215a1d5a5622c38938b5adb64b982c631170604a4ba8285fb5397b255`。config-bound preflight SHA=`98febe58038352eefff14b2c88c19e332cdf3fdcf1531a16e91137c5ab0debbc`且P/D mismatch=0；freeze ID=`71686cf225194fbe6f9a0db73e7adf515a02ce252598ac58f6e5090793470b27`。
- v19 package manifest SHA=`5d118970d4831074da8c8dfee57abdadb48d6bc402bf4aea93864b5dcffef636`；schema 0.3不变性报告SHA=`08a6457ee3c8f8f0fa179feb06f81f3df22b6009ea6be771571efcdd303ad1de`证明264个数值payload/runtime文件保持不变，同时明确允许配置/bitstream/execplan/身份文件变化，不把v19冒充v18。
- v19最终runner SHA=`1ae95b832c4273513c152ae453164346563fb2064c15c23255da44b5a7d9d8ee`；ZIP为2,989,053字节、289个entry、0 HDL，SHA=`0874e8eeb8495ca46e3ddda54e1273c05e5c9a10b78c468e4584ba33398f06b2`。Round 1报告SHA=`164a13a7b8fda7dd0e09799e9d3d4e441ec407658a8280a8db516ef48f5df6b8`，20个行为用例PASS；Round 2报告SHA=`eec85fbd1cc2a5fe98e57a028108c1dac73b8f52545f26607c562670f4683dc2`，最终ZIP独立解包审计PASS。
- 本地回归额外修复了“current overlay/package测试仍硬编码v18/v14”的口径漂移，并以v19 request/freeze重新完成28-bank端到端重建（492秒）和当前overlay行为测试。服务器运行前v19只达到`overlay_ready`，G6/G8仍为false。
- v19正式链闭合后精确删除9个失败/探针生成目录（`v19-work`、首个失败server-profile/candidate及6个手工bias探针），共78个文件、4,101,888字节；正式`server_profile_input_02`、`encoder_candidate_native_02`、preflight、freeze、package、overlay、ZIP和两轮报告均保留且身份未变。
- v19真实run1完成434/434 preload、`Exec_Length=314`和首波28个slice的`Start_Comp`，随后fixed observer保持`0/5 pending=1`约7202秒并由watchdog以`phase_watchdog_stalled`终止；没有stage完成、自然退出或readback。主返回`sim_results_v19_run1.zip`为86,784 B，SHA=`89bd374c3f357e32857d90bfe511b628fdbe3d2166d09b789165722d95b8501b`。
- 补充`v19_run1_gexec_actual_1784631030.zip`为2,845 B，SHA=`b9b58afabb55f7166417aead35acdb6550ed6d992fec9310f185c6bf09c6be7c`。其中279条gexec命令与本地v19首波execplan按slice mask展开后的279条逐条相等：28 Clock Enable、28 Load Config、195 WREG、28 Start Compute。
- v18→v19的56处命令差异全部是预期变化并出现在服务器记录中：28条Load Config由28行变29行，28条READ_STREAM3寄存器17写入切换到新bias tile配置。由此排除旧码流混装、首波命令漏发和global executor未启动作为v19最早断点；bias修复是已送达的必要静态修复，但不是已证实的唯一/充分根因。
- 当前断点缩小为首波Start之后、任一slice completion之前；现有日志不能在READ_STREAM3、buffer4、SA输入/outbuffer、buffer5和WR_MSE0最终写数据之间唯一定位。v19永久撤权、禁止run2；当前没有服务器候选，不在服务器资源可能被其他算子占用期间生成或执行下一包。

## 3. 服务器revision历史与防复发结论

下表记录“最早可证实断点”，不是当前执行入口。由这些证据提炼的当前运行/验收约束见服务器包规则第5～13节；规则若与新实证冲突应及时修正。

| revision | 是否上服务器 | 最早断点/确认错误 | 固化结论 |
|---|---|---|---|
| v1 | 是 | raw `.bin`被逐行文本loader误读 | payload必须满足TB parser文本ABI并校验行数/位宽/字符集 |
| v2 | 是 | P/staged-D scratch未初始化，读改写读到X/旧值 | 所有scratch显式零初始化并进入manifest |
| v3 | 是 | `buffer5.dst_port=1`使SA结果不能进入buffer5；但v4反事实证明它不是唯一充分根因 | SA/GA producer route必须由配置、encoder和RTL交叉验证 |
| v4 | 是 | route位已到硬件但仍0 write-data/0 completion；SA outport编码语义冲突 | route必要但不充分，outport和消费端必须同时闭合 |
| v5 | 未形成可信结果 | 曾尝试诊断RTL插桩；随后服务器明确全部`.v/.sv`不可修改 | RTL/TB永久只读，诊断只走既有非HDL能力；旧v5包已清理 |
| v6 | 是 | 只完成1/11 stage，MSE4有请求/地址但无write-data；289.543 ms仿真时刻被SIGHUP | batch扩为3 accumulate+8 requant；信号/timeout/make/sim状态分开保存 |
| v7/v7r1/v7r2 | 是/诊断变体 | UCLI最初因多file id/对象不存在停住；修正后12 ms诊断显示group1 token缺失，HIGH-4 buffer对和neighbor count错误 | UCLI对象必须预验；neighbor双buffer和`buffer_nbr_cnt=N-1`成为生成门；诊断退出不等于算子完成 |
| v8 | 是 | 修正HIGH-4后VCD与v7相同；weight stream只有4B有效数据，无法形成128B循环terminal-tag；physical pack/stride和bias extent也冲突 | 统一A/B/bias/P/D physical合同、事务字节、terminal-tag和inverse；停止继续试探波形 |
| v9 | 是 | 首个`0x00104800/256` AXI burst跨4 KiB并卡死；SCA缺`Repeat_Num`且服务器手填9，与11 stage冲突；无正式readback | preload/readback逐段4 KiB安全；observer count生成器推导；运行SCA和返回身份fail closed |
| v10 | 是，两次预检 | 先要求服务器Git HEAD，后要求完整Makefile/RTL/TB内容一致，均在compile前退出；新RTL另有未连接`m_axi_reserved_clk` | 服务器源码只对入口/能力，不锁Git或整树SHA；窄范围UCLI驱动reserved clock |
| v10r1 | 是，compile前 | package/overlay含CRLF，预检以`invalid_reserved_clock_ucli`笼统退出 | package/overlay/ZIP三层原始字节LF-only审计并报告实际文件 |
| v10r2 | 否 | runner模板中`\015`先成为真实CR又被归一化，CR检查实际统计LF | 字节门使用`od`十六进制扫描，并用真实Bash纯LF/单CR样本测试 |
| v10r3 | 是 | 运行约7小时后首stage功能死锁；JSON/physical staging混入旧`e0-rebuild`35行accumulate码流 | JSON→official encoder→parsed evidence→freeze→安装bitstream强绑定；当时修复身份为28行，后续调度变化必须建立新行数/SHA身份 |
| v10r4 | 否 | fixed observer返回解析仍要求不存在的11条runtime marker；最终slice1事件不能证明其他slice完成；requant来源和physical比较不完整 | 返回按observer mode分支；最终mask全slice完成先于readback；每个requant独立来源合同；比较完整physical padding/tail |
| v10r5 | 否 | 数值和最终12-stage合同闭合，但高频日志、reserved-clock假成功、仅24h总timeout和全量结果归档仍有风险 | 数值freeze保留；runner必须抑制非判定高频日志、证明时钟翻转、分阶段watchdog、最小回传 |
| v10r6 | 否 | start-only宏未覆盖112个MC日志；Make仍全量归档；watchdog把重复/乱序当进度；诊断无界；整体返回和argv未绑定 | no-archive附加Make、有序状态机、诊断限额、返回exact-set和argv内容寻址 |
| v10r7 | 否 | 未终检console、半行竞态、readback创建即完成、额外路径伪进度、VCD默认、Make展开未验证、异常无归档 | 完整行快照+终检；完整普通文件进度；显式关闭波形；有效Make展开和统一失败归档 |
| v10r8 | 否，最新撤权 | watchdog扫描整个install，把272个合法preload当unexpected readback，首次轮询必失败；终检/离线端接受无末尾LF；旧默认和显式exit仍不安全 | 分离preload/readback命名空间；live/final/offline统一`128bit+LF`及精确大小；真实完整install行为测试；显式参数和统一归档 |
| v11 | 否，永久撤权 | 3个GNU awk程序把内建`index`用作变量而语法失败；缺独立Round 1；freeze exact-set/ID和candidate路径中性存在缺口 | 真实GNU awk行为必须进入正式Round 1；freeze重算ID+exact-set；candidate身份路径中性；用新revision全链重跑 |
| v12 | 否，永久撤权 | 当时两轮本地审计PASS，但后续发现源码闭包、失败归档、run-ID隔离与双回传稳定性合同不完整 | 旧ZIP不得执行；修复后必须新建revision并全链重跑 |
| v13 | 否，中间撤权 | 递归filelist/source provenance、统一失败归档和双回传合同的修复中间态 | 从未获得上传资格，不得改名复用 |
| v14 | 是，run1止于preflight | 全链重生成和两轮本地审计后作为诊断包运行；`server_filelist_member_outside_root`在compile前阻断，活动filelist物理路径位于服务器根外；本地另发现环境常量、CR路径判断和正式run-ID审计缺口 | 不得重跑或执行run2；v15删除source物理根内/外部include树同构等过度启动硬门，只保留必要入口可读性、包身份和实际Make/VCS失败归档；G6/G8保持false |
| v15 | 否，永久撤权 | 删除v14过度source硬门并修复run ID/CR/审计缺口；后续发现runner身份顺序、双跑provenance和实文件不变性缺口 | 从未上服务器；不得执行 |
| v16 | 否，永久撤权 | 修复v15缺口并完成两轮审计；后续故障注入发现清理异常收口、合并态exact-set、Make环境、`DIR_HOME`provenance和报告覆盖问题 | 从未上服务器；不得执行；v17只读复用同一数值freeze修复非数值链 |
| v17 | 否，永久撤权 | 修复v16缺口并完成两轮审计；包内README未完整表述新增运行合同 | 从未上服务器；不得执行或原地改写；v18重新生成并统一交付说明 |
| v18 | 是，run1手工终止 | 全部preload后首accumulate固定observer停在`0/5`；静态确认bias tile握手不足 | 永久撤权，禁止run2；修复必须建立新JSON/candidate/preflight/freeze/package身份 |
| v19 | 是，run1由watchdog终止 | bias修复已被实际加载，279条首波gexec与冻结execplan逐条一致；仍在首stage `0/5`停滞 | 永久撤权、禁止run2；bias静态错误不是已证实的唯一/充分根因；G6/G8=false |
| Decode FP32 max | 是，自然完成 | 30个preload、57个gexec握手、28 slice在66 cycles后完成且各有1个MSE4写数据；有效最低32-bit与本地D Golden 28/28一致 | 公共FP32 max写回链可完成；遗漏`+SCA_CFG_D`导致默认寻找`sca_cfg_D_softmax.json`并跳过正式回读，只记E3；后续SCA_D参数必须显式绑定 |
| native DeepSeek FP32 max control r1 | 是，自然完成 | `sim5.zip`正确绑定两份SCA；30个矩阵装载、65-cycle完成、28项正式D回读、自然成功结束 | 最新零违规LC placement的FP32对照运行/回读流程通过；ZIP未含回写D文件，不新增数值正确性结论 |
| native INT8 MaxPool16 r1 首轮 | 否，未启动 | `sim4.zip`实际指向旧`maxpool_node0002_guarded_wave0_v1`；主SCA不存在，在JSON装载前`Cannot open` | 部署/PLUSARGS路径错误；不是INT8停滞证据，必须用正确双SCA参数重跑 |
| native INT8 MaxPool16 r1 有效重跑 | 是，启动后停滞 | `sim4(2).zip`正确绑定两份SCA；30矩阵、29行execplan、138次GEXEC握手完成；28 slice各47读请求/33读返回/2写地址/0写数据 | 小尺寸零ping-pong原生`int8_max`动态复现；4.977 ms后SIGHUP，强力支持GA INT8专属链路问题，精确RTL根因仍待身份和修复反事实 |

## 4. 原始服务器结果ZIP台账

以下记录对应已核验的原始或补充运行ZIP；文件可位于工作区，也可位于只读外部回传目录。不得改写或与完整展开目录长期并存。

| 对应运行 | 文件 | 字节数 | SHA-256 | 证据边界 |
|---|---|---:|---|---|
| v1 | `sim_results.zip` | 227,106,496 | `919f24c7f9bfacb5b90d5a9abaff043046378dfb9a2dd194ed5ccca63d9882c2` | 首轮原始返回 |
| v2 | `sim_results_v2.zip` | 235,545,013 | `9f6bba9ddcbdb75c553da9464d3d1af98b4d06a50cc27d3758cf596989e8c872` | scratch问题返回 |
| v3 | `sim_results_v3.zip` | 266,186,788 | `9b0b15b7c351228f3f3b4d6163ba6da8391f5d1cddff04a22293eed442f172aa` | 170/170 preload通过，0 write-data |
| v4 | `sim_results_v4.zip` | 266,186,780 | `eb573db4b8cd7b9dd5981bf7fde6db40823d5e8274cbb9c5f58731948208cd00` | route反事实，仍0 write-data |
| v6 | `sim_results_v6.zip` | 671,985,880 | `931122cef89e526878c9fe18088fa3240ad07d529c879f9eefb4c56dae168984` | 1/11 stage，SIGHUP终止 |
| v7 | `sim_results_v7.zip` | 43,887,846 | `ae569f738cfa2e0eef65a50b816507057682eadcef3a9f4d1ac0733e8cea518c` | 12 ms定向诊断，不是完成运行 |
| v8 | `sim_results_v8.zip` | 43,887,510 | `0424c9e80d6541f6d8e7bb2e2a9a6c38a4b76621a6796b950bc710e063b48528` | 12 ms诊断，静态根因闭合 |
| v9 | `sim_results_v9.zip` | 77,615 | `0d05b8959ebf1d724232902b2fa4a24ccfbfcd2c9c28585da64661aae09e4dd4` | 首个非法4 KiB burst内停止，0 stage |
| v10r3 | `sim_resultsv10r3.zip` | 42,851,373 | `8487c07b4d385b74b3668ebe9a56a217631c53b5b66f80e64c9417e3ea999ed5` | 旧35行accumulate混装后的首stage死锁 |
| v18 run1 | `sim_results_v18_run1.zip` | 86,794 | `2f33f34f626b2b1fe71502da5fe10e87eb67fb21d3a13404c528fbc130dbfeca` | 手工终止后的最小失败返回，434/434 preload、首stage 0/5 |
| v18补充 | `v18_run1_deadlock_extra_1784611151.zip` | 217,860 | `6b833a69ae92e9fb9c9147d783d01ece803e7c4f98c3c0d62721b8824c574dc7` | 首断点补充日志，不是自然完成证据 |
| v19 run1 | `sim_results_v19_run1.zip` | 86,784 | `89bd374c3f357e32857d90bfe511b628fdbe3d2166d09b789165722d95b8501b` | watchdog终止，434/434 preload、首stage 0/5、0 readback |
| v19 gexec补充 | `v19_run1_gexec_actual_1784631030.zip` | 2,845 | `b9b58afabb55f7166417aead35acdb6550ed6d992fec9310f185c6bf09c6be7c` | 279条首波gexec与冻结execplan逐条一致 |
| Decode FP32 max | `simresults(1).zip` | 23,148,389 | `3d8fecf803a64e2a6f378e82ceeb7b4099d66f28c7f2c70be2743cb53d1cb33a` | 自然完成并产生28/28匹配的内部MSE4有效写数据；命令漏传`+SCA_CFG_D`，正式matrix readback被跳过，保持E3 |
| native INT8 MaxPool16 r1无效启动 | `sim4.zip` | 8,217,861 | `298ecbeb28034e914e8913a9dc8230178ff0957af09f561e5b06e33627e970ca` | 实际加载旧路径且主SCA不存在；0矩阵装载、0计算、0回读 |
| native DeepSeek FP32 max control r1 | `sim5.zip` | 23,195,880 | `4ed061b59aaef08c4e805b357b8c63b64b0c197cd9322954085529ecfa44e721` | 30矩阵装载、65-cycle完成、28项正式D回读并自然结束；ZIP未含D结果文件 |
| native INT8 MaxPool16 r1有效重跑 | `sim4(2).zip` | 31,055,057 | `c383700af40032406c54def625f1300242497d62d7ca837f9cc20fd1a8a7f2f2` | 正确装载/启动；28 slice有读返回和写地址、0写数据、无完成/回读，4.977 ms后SIGHUP |

工作区当前没有v10/v10r1原始返回ZIP。已核验的外部记录仍保留：v10错误ZIP SHA=`98f13b364ab4970c64e4a9480130c14146ef1790787fda79fb4b5478ab897fb5`，reason=`server_rtl_identity_mismatch`、make/sim=-1；v10r1由服务器报告`invalid_reserved_clock_ucli / CRLF is not allowed`，但本地无可重新hash的原始ZIP。v14失败ZIP仍在服务器，外部回传SHA和错误字段已记录，但本地尚未保存原始ZIP，不进入长期ZIP台账。不得用任何overlay输入ZIP冒充服务器结果。

## 5. 数值与physical合同演进

### 5.1 W5首例

- 首个真实算子为`node-0004 / hwop-0004-00~01`，1×1、stride1、N=16、C=64、K=64、H=W=56。
- 配置绑定NDP对28个slice产生两份staged-D并inverse；完整P和D各3,211,264元素与Golden 0 mismatch。
- public W4布局继续使用稳定v1；新SA Q8/K8 packing隔离为hardware-private/v2，避免Add/network误继承。

### 5.2 v8静态反查后的统一合同

- A=`[storage-N,H,Qblock,Cquartet,Q8,C4]`。
- B=`[R,S,ring-PREV,Cquartet,Kblock,K8,C4]`。
- bias=`[Kblock,K8]`。
- P/D=`[storage-N,H,Qblock,Q8,Kblock,K8]`。
- activation/weight/bias分别绑定READ_STREAM0/1/3；terminal-tag固定为stream0/LC3、stream1/LC7、stream3/LC13。
- v9正式encoder双跑24/24节点、29连接、placement cost 0，产生正确28行accumulate码流。

### 5.3 v10r5历史结构及v14沿用的数值形状

- 12个stage：3 accumulate、7个完整requant shard、最后一个shard拆成`non_observer_slices`与`finish_slice_only`。
- fixed observer为5对：`(0→0),(1→1),(2→2),(3→8),(9→11)`。
- 最后两个mask为`0x4444220`和`0x0000002`，确保不可变TB最后观察到slice1前其他slice已经过barrier。
- 314行execplan、434个preload段、168个readback运输文件、84个完整语义region、28个Bank、272个数值安装payload。

## 6. W0～W5里程碑压缩

| 阶段 | 完成结论 | 未批准边界 |
|---|---|---|
| 2026-07-05～09 原始参考链 | 确认正式候选ResNet50 INT8模型、预处理和ORT输出 | 尚无目标架构/硬件合同 |
| W0/G0 | 根集成包、CLI、schema、artifact原子发布、DAG、失败阻断、cache/resume与mock测试 | 不证明真实算子或硬件 |
| W1/G1 | 固定ONNX、输入、量化事实和hash | G1未整体通过，架构事实仍有候选边界 |
| W2/G2 | 小Conv 1/4-slice布局、ring/requant/writeback功能链，多参考84坐标一致 | 不是正式28-slice硬件 |
| W3/G3 | 78节点/617 tensor正式图，133个语义hw_op，全部节点独立公式重放 | 未生成目标配置/运行包 |
| W4/G4 | 从16-slice切换28-slice；Conv/Pool/Add/GAP/MatMul及整网transition/lifetime/cost审计；正式配置继承与G4通过 | 不等于逐周期执行 |
| W5首例 | 正式1×1 accumulate/requant配置、NDP config-bound P/D、freeze与freeze-bound单算子运行包，`node-0004`范围G5=true | 其他shape/算子族G5未闭合；G6/G8仍需目标执行证据 |
| E1/E2 | 128→512与512→128等多K实例，覆盖8/16/32/64 requant shard | candidate，未硬件实测 |
| E3/E4-A | ConvInstanceSpec驱动freeze/execplan，另两shape完成配置绑定和运行包候选 | 不批量发布，等待首例硬件通过 |

## 7. 工程与仓库事件

- 参考仓不使用submodule，由`repos.lock.json`和`tools/sync_repositories.py`恢复；`NDPFuncModel`锁定提交已推送private mirror。
- `artifacts/w3/golden_batch16`曾因权限不可读；已对精确目录执行ownership恢复并恢复递归只读/执行权限，未改golden payload。
- managed worktree曾因junction共享Local依赖造成取证/恢复风险；此后`.venv`、参考仓和大型artifact不通过junction/symlink共享，详细经验见`.agents/archive/engineering-lessons/managed-worktree.md`。
- 本机`NDP_copy01`曾清除VCS/Verdi缓存、展开结果、FSDB和冗余源码，只保留主Makefile、主TB、活动filelist闭包、RTL只读镜像和入口说明；真实VCS只在Linux服务器运行。
- 服务器快照`NDP_copy_0718.zip`曾用于机械同步有效活动闭包；服务器源码允许继续更新，runner不锁整树内容。
- 只有用户明确要求推送时才执行远端操作；默认回退使用`git revert`，禁止自行reset/rebase/filter/force push。
- 2026-07-23 完成算子配置规则 R0～R4：55 份活动 JSON 裁决为 46 strict-valid、9 intentional-reject；建立独立 JSON/bitstream/mapping/execplan/SCA/逐请求地址/语义合同验证链。最终两 stage Decode 本地证据双跑 25 个确定性文件一致，113 条 64-bit 指令、1848 次请求、504 个唯一地址全部通过；详细证据与 E4/E5 边界见 ADR-015。活动规则已切换，原生 `ndp-sim` 和现有候选未修改。

## 8. 历史文档索引

- v1～v4原始服务器报告与交接：`.agents/archive/server-simulation/v1-v4/`。
- W4方案切换、28-slice裁决与事故：`.agents/archive/milestones/w4/W4_ARCHIVE.md`。
- worktree事故与恢复经验：`.agents/archive/engineering-lessons/managed-worktree.md`。
- 归档分类总索引：`.agents/archive/README.md`。
- 当前服务器防复发总结：`.agents/rules/服务器测试包生成规则.md`比本文件记录得更完整，但同样是从实现和实证中提炼的派生文档，不高于活动入口、包内合同或真实返回。

## 9. 历史记录维护规则

- 新实测结果只追加原始ZIP文件名、大小、SHA、最早断点和门状态；不粘贴完整日志。
- 新确认错误若能推广为当前不变量，应同步对应派生rule或定向测试；仅属于单个历史revision的事实留在本文件，不把每次故障都升级为长期硬门。
- 完成工作从`plan.md`移入本文件时压缩为表格或5～10条摘要，删除旧命令和已经失效的“当前/下一步”措辞。
- 精确提交台账只保留阶段恢复点；普通微小提交可由Git历史查询，不在本文逐条复制。
- 本文件接近900行时先合并重复条目并引用archive，禁止超过1000行。

## 2026-07-23 GAP、Conv、Requant 原生包里程碑

- GAP `hwop-0071-00` 完成原生 mapping/bitstream/execplan/SCA、143392 次逐请求地址
  校验及 32 个矩阵文件，成为第二个本地只待 E4/E5 的算子。
- node-0004 Requant 完成 3 wave×8 shard、24 个精确原生实例、1003520 次请求和
  256 个矩阵；独立 W3 重放 3211264 元素 mismatch=0，本地只待 E4/E5。
- node-0004 Conv 完成 `[28,28,8]` 三波、3 个精确原生实例、1710080 次请求和
  256 个矩阵；三份 mapping 均零 penalty，execplan 双跑一致。
- Conv 当前仍是项目派生配置，SA signedness/bias-psum 语义与硬件 E4/E5 未批准；
  Conv HWC16 D 到 Requant HWC8 A 的子通道偏移/stride 也尚未形成同一 execplan
  物理交接合同。详细状态与后续顺序见 `.agents/plan.md` 第 15 节。

## 2026-07-23 GAP 硬件启动预检

- 精确 `hwop-0071-00` GAP-sum 不走已知缺陷 `int8_max` pipeline；UINT8→INT32、
  8 路 `int32_sum`、49→56 的零补齐及 INT32 范围均未发现已知阻断。
- GAP 专项 6 项回归及候选整树复验通过；payload tree SHA-256 保持
  `87f78f547f89bd6b7b8840dd36e7bc0464719e2b73d7a6198528981b86a64c8b`。
- 实际 E4 未启动：唯一服务器协议仍为 `template_not_approved`，runner 在执行命令前
  正确拒绝。当前没有真实 server id、RTL 身份、load/start/wait/readback argv 或回传路径。
- 本次结论仅覆盖 GAP sum；完整 GAP 的除以 49 与 UINT8 requant 仍未闭合。

## 2026-07-23 GAP 服务器消费文件夹

- 用户明确本轮只需按 NDP-Sim 及先前本地生成、服务器跑通的算子目录格式形成消费
  文件夹，不要求在本地补写服务器 runner 或协议。
- 新目录
  `artifacts/operator_config_validation/r5-server-workloads/gap_hwop0071_sum_graph`
  与 `decode_summac_fp32N_fp32N_graph` 具有相同顶层文件类别：根级双 SCA、
  `config/install/jsons`、带基地址 graph、解释文件与来源 manifest。
- GAP 真实启用 16 个 slice，而不是参考算子的 28 个；每个 slice 均补齐 A/D 的
  `.bin`、128-bit `.txt` 和 decimal 视图，共 96 个矩阵伴随文件。所有内容从已验证
  GAP candidate 机械装配，没有复制参考 payload。
- 34 条 SCA 引用全部落在本目录；execplan 17/17 行一致；服务器读取的 128-bit 文件
  均为 LF；二进制、位文本及 typed decimal 三种表示逐元素一致。整树哈希为
  `8f644eaac10f0994cc657a23a44604de5aa1c55bbbf4371f26f3802a55d18c56`。
- 本地交接门已通过，服务器 E4/E5 仍为空；运行时必须显式同时绑定目录根部的
  `sca_cfg.json` 和 `sca_cfg_D.json`。

## 2026-07-23 通用服务器返回验收与观测器

- 新增通用 `tools/analyze_native_ndp_server_return.py`：直接读取原生 NDP 返回目录或
  ZIP，从冻结工作负载的双 SCA 推导运行/回读合同，按 14 个 checkpoint 定位最远进度，
  并逐字节比较正式 D 与独立 Golden。
- GAP profile 固定本轮 manifest、双 SCA、17 条 execplan、18 个 preload、16 个活动
  slice 和 512×128-bit/片回读；输出仍明确区分 E4 candidate 与正式服务器身份门。
- 历史回归分别重现 FP32 完成但未带回 D、错误 SCA/缺 SCA_D、INT8 MaxPool
  “写地址无写数据”；ZIP、安全路径、数值 mismatch 和 synthetic GAP pass 也已覆盖。
- 本地 TB 只新增 plusarg 门控的只读 observer include；观测 CONFIG/exec/completion、
  MSE/bank、buffer4/5、SA 两侧 tag/backpressure 和八个 GA PE pipeline0，低频输出
  heartbeat/STALL。它补上历史 Conv 在 READ_STREAM3→buffer4→SA→buffer5 区间的
  观测缺口；analyzer 对 STALL fail closed，避免主日志或碰巧匹配的 D 掩盖内部停顿。

## 2026-07-24 活动 agent/plan 精简

- 精简前 `.agents/agent.md` 全文迁入
  `.agents/history/agent_pre_active_compaction_20260724.md`：112 行、5,862 bytes、
  SHA-256 `27f2e3a567d39e01abe176289bcffb3bc28fd6a4c39ffb0dd17c79784154b966`。
- 精简前 `.agents/plan.md` 全文迁入
  `.agents/history/plan_pre_active_compaction_20260724.md`：2,008 行、153,778 bytes、
  SHA-256 `d4bc08ec44017a1d438961391577fdb74584b6b203daa66978706b07d95d515b`。
- 旧 plan 中的 GAP probe/repair/onecmd 逐版本结果、Decode/MaxPool/node-0004
  服务器身份、R0～R7 已完成过程、旧生成命令、旧包 SHA 和已被后续证据取代的
  “当前候选/下一步”全部保留在上述快照，不再进入活动派工。
- 新 `.agents/agent.md` 只保留文档归属、事实优先级、工作区边界和协作纪律；新
  `.agents/plan.md` 只保留全局计数、DequantizeLinear 当前任务、冻结 blocker、
  后续顺序和执行门。
- 本次没有修改 `rtl/`，没有生成、上传或运行服务器测试包。

## 2026-08-01 活动 plan 再精简

- 精简前 `.agents/plan.md` 全文迁入
  `.agents/history/plan_pre_active_20260801.md`：177 行、10,172 bytes、
  SHA-256 `78ea5582bd124f1b6f6139d0b391ce3deefa0e869dfc2b1331575e12818bee3c`。
- 新活动 plan 只保留 Conv v22、QAdd v16、GAP v15 三条当前服务器主线、唯一可运行
  包、当前执行顺序、生成/验收硬门和开放 blocker。
- v20/v21 Conv、v14/v15 QAdd、v13/v14 GAP 等已被取代包不再作为当前命令；精确过程
  和收据继续由 `.agents/task_records/` 与上述快照保存。
- 本次同步把 QAdd v14 已实证的 32B transaction/16B Buffer5 supply 反例固化为
  `CDA-QADD-D-BUFFER-TRANSACTION-SUPPLY-CONSERVATION-001`；没有修改功能 RTL。

## 2026-08-01 QAdd v16 与 GAP v15 返回更新

- QAdd v16 已真实越过 D-buffer 修复路径：两通道各有至少64次 qualified MSE4
  request/write-data。人工 INT 发生在首个262144-cycle heartbeat前约642 cycles；
  因此该return既不通过动态门，也不证明新卡死根因。原v16保持可运行，不生成新包。
- GAP v15 的 Buffer→GA feature 已真实启用。动态证据与RTL方程共同确认旧stage1
  `COL=0,4,8,...`把bank空间偏移误当bank内byte-lane序列，低2位恒0，无法形成全有效
  Buffer row。
- GAP typed materializer改为GROUP0/GROUP1 `COL=0,1,2,3`，完成四叶配置修复、完整
  物理重建和v16最终ZIP自检。过时的GAP v15诊断包由v16功能修复包取代。

## 2026-08-01 QAdd v17 后端进度摘要

- QAdd v16最后一次有效输出侧事务为MSE4两通道各64次request/write-data accept
  （16128787000 ps），最后一次有效输入侧事务为MSE0→Buffer0第64次accept
  （16129301000 ps）；最后文本行是16129338000 ps的MSE4 index状态，不是新事务。
- v16从slice start到人工INT仅推进261501.9 cycles，尚未到262144-cycle首个heartbeat；
  日志量不是约70分钟walltime主因，但摘要周期过稀造成最后约260655 cycles不可见。
- fresh v17仅把后端heartbeat降至32768 cycles，并保留累计qualified握手、outstanding、
  stage completion与first-request链；不增加前端逐事务日志，不改功能配置/workload/RTL。

## 2026-08-02 活动 plan 覆盖式更新归档

- 被替换的 `.agents/plan.md` 共170行、8,402 bytes，SHA256=
  `7fd915afa1bd150e55c1a4f2e5a3db3af406d06574868ce0b66f412c8b5ba703`。其活动内容为
  Conv v22 `WAIT_RTL_FIX`、QAdd v17、GAP v17 待运行身份、旧执行顺序、生成/验收硬门和
  当时的开放 blocker。
- 旧 QAdd v17
  `r5_qadd_n7_backend_progress_v17.zip`（SHA256=
  `524325a3dd78aa7e7f699f3b23809cc9f1f432698ab671db30640e031b64b462`）
  已由 v18 column-pair 功能配置修复包取代，不再是活动运行命令。
- GAP v17 源包身份保持不变，但状态由 `PACKAGE_READY_NOT_RUN` 更新为 return 已收集、
  owner 分析中；旧 blocker `B_GAP_NODE0071_V17_STAGE1_FLOW_RETURN_PENDING` 已退出活动
  plan。
- MaxPool node0002 v4 作为新的 exact native JSON reuse 诊断候选加入活动快照；
  `B_GA_INT8_MAX_NUMERIC`、`B_GA_INT8_MAX_FLOW` 和服务器 E4/E5 仍开放。
- Conv v22 的 SA_PE_Outbuffer occupancy 根因继续有效，状态保持 `WAIT_RTL_FIX`；
  未经用户授权不修改功能 RTL。
- QuantizeLinear node0074 的首个 blocker 收敛为精确 binary32 RN-even divide 能力缺失；
  不生成 placeholder target 或服务器包。
- 主线控制面由旧会话切换为
  `019fbec2-fe93-7e03-9314-cff6f222f33d`；旧主线停止修改 plan/rules 和分发任务。
- 新 `.agents/plan.md` 明确采用覆盖式维护：只保留最新状态和最新短期计划，不追加版本
  叙事；后续被取代状态继续先归档到本文件，精确收据留在 `.agents/task_records/`。
- 本次只更新 `.agents/plan.md` 与 `.agents/history.md`；没有上传或运行服务器包，没有
  生成新包，也没有修改 `rtl/**` 或公共规则。

## 2026-08-02 GAP node0071 v17 RETURN_ANALYSIS 完成

- 被取代的活动 plan SHA256=
  `6401c8f26704480de0fa3ca915ff5b5cd3b07bd5515ea78c7dc78cd48d537c2f`；其中 GAP
  `RETURN_ANALYSIS_IN_PROGRESS`、分析待完成短期步骤及其临时 blocker 已退出活动 plan。
- v17 return 身份为 155,635 bytes、SHA256=
  `9c8f25bd7f889d047487e7f5687808fefe4525fce401dbc408a70484713c66dd`。内部 identity、
  exact-set、allowlist、源包/config/preflight/observer/STAGE1_FLOW 绑定闭合；外部 sidecar
  缺失仅由用户传输担保替代。
- compile=0，但 simulation/runner=125、signal=INT、natural terminal=false，
  formal D=0/48；E3/E4/E5 均未通过。
- 最后可信边界为 MSE3 Buffer-AG index queue enqueue；首分歧为 MSE3 queue dequeue 与
  WR_Buffer_AG address write 全缺。`buf_ag_ob_full` 已排除，read-data readiness 与 request
  barrier 两个叶因仍无法区分。
- 原 machine report SHA `7f26ab...` 与 task record SHA `35b986...` 因
  `analysis_owner_thread` 误写旧主线而被取代；纠正后的 report SHA256=
  `79380595960c61cf6610d5ebd5968a51a49c1ac688a1b780af5c75a16d67faca`，task record
  SHA256=`85ee8dd46441affe423571a09572f37954177ab59e8b6e8eecf0b5169cdb08e0`。
- 主线接受 `CDA-GAP-HANDSHAKE-CONJUNCTION-FACTOR-OBSERVABILITY-001` 到 GAP 专项规则：
  conjunction output 为 0 不得越界指认叶因，缺逐因子证据时必须保留析取。
- `PACKAGE_RELEASE=NONE`；本轮未生成 successor、未修改功能 RTL、未上传或运行服务器。

## 2026-08-02 GAP v18 授权与 QAdd v18 return 到达

- 被取代的活动 plan SHA256=
  `07196fe91d362f6379681fe21bf7ef3a9a6a7661048dfe0284680d16c4529f68`。其中 GAP
  `ADJUDICATED / PACKAGE_RELEASE=NONE` 的“未授权 successor”状态，以及 QAdd v18
  `PACKAGE_READY_NOT_RUN` 的“服务器 return pending”状态已退出活动 plan。
- 用户明确授权 GAP node0071 fresh 窄诊断 successor。新任务只允许冻结 v17 的 73 个
  numeric、sum/tail/workload/config/golden/functional RTL，并补充 `buf_ag_bp_pre`
  readiness-vs-barrier 逐因子只读证据；当前仅本地构建和自检，不含上传或服务器运行。
- QAdd v18 return 到达路径为
  `r5_qadd_n7_dbuf_colpair_v18_return(1).zip`，bytes=`278142`，SHA256=
  `ee21c207e9e3244eaea4993ab0b05bc3907af6dbe633f904ad0a1088118cd7aa`；
  外部 `(1)` 不参与内部 identity 裁决，相邻 sidecar 缺失仅按用户担保替代外部收据。
- QAdd return 已交原 owner 做正式 identity、dynamic D-buffer byte-window、natural
  terminal、28 项 formal D 与 E3/E4/E5 裁决；分析完成前不生成后继包或预判结果。
- 两项任务均未修改功能 RTL，未取得 `SERVER_RUNNING` lease。

## 2026-08-02 QLinearAdd node0007 v18 RETURN_ANALYSIS 完成

- 被取代的活动 plan SHA256=
  `31c46e4e5086f51c6514fc5633057bd906b6fda9c0dcdd3895c316f9f14f77de`；其中 QAdd
  `RETURN_COLLECTED / ANALYZING`、分析待完成短期步骤与临时 blocker 已退出活动 plan。
- v18 return 的内部 exact-set、allowlist、manifest、源包/preflight、SCA 与 observer
  四向绑定均闭合；compile=0，但 simulation=125、signal=INT、natural terminal=false，
  formal D=0/28，E3/E4/E5 均未通过。
- `op_a_dequant`、`op_b_dequant` 和 `op_relocation_pad` 已完成；relocation 的 MSE4
  双通道 request/write-data 均达到 4224/4224，旧
  `B_QADD_NODE0007_STAGE3_RELOCATION_D_BUFFER_ROW_ONLY_SUPPLY` 被动态关闭。
- 新的最后可信边界为 `OP_RELOCATION_PAD_COMP_FINISH`；首分歧为
  `OP_FP32_ADD_AFTER_FINITE_READ_ACTIVITY_BEFORE_GA_INPUT_ACCEPT`。第 4 阶段在
  MSE0+MSE1/Buffer0+2 到首个 qualified GA input accept 的区间内持续 189 个完整
  stall window 不变；缺失配对 consumer witness，不能越界裁成 CONFIG 或 RTL leaf。
- v18 的 canonical parser 还错误地把任一早期 `COMP_FINISH` 当作全任务结束。主线将
  expected ordered stage list、同 stage start/finish 配对和 final-stage scope 条件并入
  既有 `CDA-SERVER-DIAGNOSTIC-DECISION-CANONICAL-RECORD-001`，没有新增同义规则。
- source v18 状态更新为
  `QUARANTINED_DYNAMIC_OP_FP32_ADD_HANG_AND_CANONICAL_CONFLICT`；
  `PACKAGE_RELEASE=NONE`，本轮未授权也未生成 successor。
- provenance correction 后 machine report SHA256=
  `a32a6023b930de3c25c1072d6692e11b36b012cbebed721b8f6fa890be66fdf8`，
  task record SHA256=`0469bce83c9782b554075356af578b1930a517bafac0fc4f24b6b8dad81a3801`。
- 本轮未修改功能 RTL，未上传或运行服务器包。

## 2026-08-02 GAP v20 发布与 MaxPool v4 RETURN_ANALYSIS

- 被取代的活动 plan SHA256=
  `11d8a61ae403ad223fe1ab35cd6250d24aafecc0b7c8dab4fc6770aa0d845c94`；其中 GAP
  `PACKAGE_BUILDING` 与 MaxPool `PACKAGE_READY_NOT_RUN` 状态已退出活动 plan。
- GAP 授权 successor 先后形成 v18、v19、v20 三个 fresh identity。v18 因冻结 workload
  实为 8-stage、但 canonical parser 未绑定 expected ordered stage/final-stage scope 而
  隔离；v19 因 EXIT finalizer 在 `set -u` 下引用函数局部 manifest 变量而隔离。
- GAP v20 仅修 package-local stage scope、runner finalizer 与身份元数据，73 个
  numeric/workload 文件和 119 个非允许语义文件保持逐字节一致。最终 ZIP SHA256=
  `a82ac187b46dac4f26a8545bf14bebf5bc5481308791be062ce581a30429bbe3`。
- 主线把 finalizer artifact/stderr/signal-stub 条件并入既有 runner 正控规则后，以冻结
  v20 fresh extract 补做安全 TERM 动态正控：finalize 恰好一次、stderr 为空、partial
  return/sidecar/manifest/allowlist/identity 自洽且 natural terminal=false。外部重验证
  裁为 `RULE_DRIFT_CONTENT_NEUTRAL_REVALIDATION_PASS`，v20 恢复
  `PACKAGE_READY_NOT_RUN`，未生成 v21。
- MaxPool v4 return 身份为 71,129 bytes、SHA256=
  `350be6952bdb0135c9fd3c428494abf5461f9c7195cba662726923be3c1cbce6`；
  内部 exact-set、allowlist、source/preflight、observer 与 return trap 绑定均闭合。
- MaxPool compile=0，但 simulation=125、signal=INT、natural terminal=false，
  formal D=0/4。stage0 的 MSE read 与 GA pipeline0 capture 已发生，GA outbuffer
  write、D write-data 和 slice finish 始终为 0；最窄错误区间为
  `GA_PIPELINE0_CAPTURE_TO_GA_OUTBUFFER_WRITE`，不能越界指认 CONFIG 或 RTL leaf。
- MaxPool v4 还暴露 two-stage canonical identity、重复 capture progress 和 finalizer
  shell status 三项诊断合同缺口；既有 current 规则已覆盖。v4 更新为
  `RETURN_CONSUMED_FAIL_CLOSED_DO_NOT_RERUN`，`PACKAGE_RELEASE=NONE`，未生成 successor。
- 本轮未上传或运行服务器、无 lease、未修改功能 RTL。

## 2026-08-03 return 驱动连续闭环规则启用

- 被取代的活动 plan SHA256=
  `01e68787dd5342bdbc070cc40f84766a237028076db1084e9d135d8aca6fecb2`。其中 QAdd
  “另行授权后再生成”和 MaxPool“下一步若继续再决定”的等待式 successor 语义已退出活动
  plan。
- 主线稳定入口新增正式 return 连续闭环：用户提交 return 后自动分发给对应算子 owner；
  本地 receipt-only 分析、fresh successor 生成和 final-ZIP 自检不再要求用户再次授权。
- 服务器规则新增 `CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001`：根因已知则
  自动生成 config/runner/package 修正包；根因未唯一化则生成围绕
  `LAST_PROVEN_GOOD → FIRST_DIVERGENCE` 的最窄诊断包。
- 允许不生成 successor 的终态仅为 `CLOSED`、`WAIT_RTL_FIX`、
  `HARDWARE_CAPABILITY_BLOCKED` 或 `WAIT_USER_DECISION`。上传、服务器运行和功能 RTL
  repair 的既有授权门保持不变。
- 默认低开销定位规则同时强化：successor 保留有效 qualified checkpoint，并在当前首分歧
  两侧及直接 consumer 边界增加最小观测；根因已知的修正包也必须证明越过旧停点。
- QLinearAdd node0007 与 MaxPool node0002 已按新规则回到原 owner 并进入 successor
  audit/build；GAP v20 保持当前唯一已验收 `PACKAGE_READY_NOT_RUN` 身份。

## 2026-08-03 MaxPool 用户原生复用特例

- 被取代的活动 plan SHA256=
  `450d175e178a9166056614635e319bb2f2e80a5823dbdcb73d8eefd4aba9c525`；其中 MaxPool
  capture→outbuffer 通用 successor audit/build 状态已退出活动 plan。
- 用户明确转述学长确认：MaxPool 已完整测试。本轮对 MaxPool 不应用通用
  return-to-successor observer 路线，停止继续审计 v4 的 capture→outbuffer 首分歧，也不
  生成通用窄诊断包。
- MaxPool 原 owner 改为按 ndp-sim 原生 MaxPool 配置、mapper/encoder/execplan/SCA 与
  服务器入口生成 fresh 资产，目标结构与项目 `jsons/` 现有原生目录同构；不得混入 v4
  observer、canonical 或 package workaround。
- 学长确认只作为 `EXACT_FULL_OPERATOR` 原生复用 authority，不自动伪造本轮 E4/E5。
  旧 `B_GA_INT8_MAX_NUMERIC`、`B_GA_INT8_MAX_FLOW` 和
  `B_MAXPOOL_SERVER_E4_E5` 在该特例路线中 deferred，不以旧 v4 return 关闭。
- 该覆盖只适用于 MaxPool，不修改公共连续闭环规则，不外推到其他算子族。

## 2026-08-03 MaxPool ndp-sim 原生 v5 包完成

- 被取代的活动 plan SHA256=
  `0bb1f851d2397b00eadb737a2234831cf1f4b4c2e54e45f2131d95f9b261f921`；MaxPool
  `USER_OVERRIDE_NATIVE_NDP_SIM_PACKAGE_BUILDING` 已更新为
  `PACKAGE_READY_NOT_RUN`。
- 直接消费者确认原生同构结构为标准单算子目录：`jsons/`、`config/`、`install/`、
  `sca_cfg.json`、`sca_cfg_D.json` 与 `*_withbaseaddr.json`，结构样本为
  `jsons/gemv_local`，权威生成树为 `node0002_maxpool_wave0_graph` 186 files。
- fresh 身份 `r5_n2_maxpool_ndpsim_native_v5` 的 ZIP 为 14,718,654 bytes，SHA256=
  `9a193d8f97d7b43d7e43886a2bc42dffee74e585832f5360a13a8ead2fa7269e`。
  权威 MaxPool source JSON SHA `a0091f...60cb1` 保持逐字节不变；物化 JSON 只发生两个
  planner-owned base-address 变化。
- 28 项 D 从 runtime target 移至独立 golden 命名空间，SCA_D 仍指向启动前不存在的正式
  readback 目标；配置 JSON、bitstream、execplan 和地址语义未改变。
- 双构建确定性一致，final-ZIP audit PASS/errors=0，安全 compile+sim、EXIT/TERM
  finalizer 正控通过，错误 source JSON 与缺失原生 op JSON 在 compile 前 fail closed，
  focused tests 4/4。
- 包内没有通用 observer、canonical diagnostic schema 或 v4 workaround；未上传、未运行
  服务器、未修改功能 RTL。本包只声明
  `NATIVE_NDPSIM_REUSE_SERVER_TEST_NOT_E4_E5`。

## 2026-08-03 QLinearAdd v19 return-driven successor 完成

- 被取代的活动 plan SHA256=
  `91f8b8142fe858277b92fc14f9acbbbb3aa71688562b84142f784336542ffe52`；其中 QAdd
  `SUCCESSOR_PACKAGE_BUILDING` 已更新为 `PACKAGE_READY_NOT_RUN`。
- v18 的最后可信边界保持 `OP_RELOCATION_PAD_COMP_FINISH`，首分歧保持
  `OP_FP32_ADD_AFTER_FINITE_READ_ACTIVITY_BEFORE_GA_INPUT_ACCEPT`。只读复核确认两条
  静态路由为 MSE0→Buffer0→GA inport0 与 MSE1→Buffer2→GA inport1，但 v18 缺少
  paired consumer 的动态证据，不能唯一指认 CONFIG 或 RTL leaf。
- fresh successor `r5_qadd_n7_fp32_ingress_diag_v19` 的 ZIP 为 38,038,498 bytes，
  SHA256=`f32abc4b2b91bf5e854ab113aa98fd1f7925e68a3bd8958f2454762a524709ba`；
  class=`DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX / E2_LOCAL_ONLY`。
- v19 冻结 numeric/W3/qparam/tail/workload/config/golden/functional RTL，只新增围绕
  MSE0+MSE1、Buffer0/2、GA 双输入配对与 consumer 的低开销 qualified observer，并修复
  ordered final-stage canonical scope 与 EXIT/TERM trap-safe finalizer。
- final-ZIP audit PASS、errors=0，双构建一致且全部规定负控 fail closed。post-report
  只读复验后的 current audit SHA256=
  `82876de5bfb32367a9441f496c052df94f2bc11e358e180c1a1baf3b08808fef`，
  build validation SHA256=
  `deb1be92a773e6f55be5dccb6dfa72474a7905470dbea0899ca8e0e745067b38`。
- provenance/receipt correction 后 machine report SHA256=
  `f8aee42cd063a495bc5a5afa025cd6cfc5c8894066abcb0813a389ac2edc1c6b`，
  task record SHA256=
  `a3b3b89689fc76cee9cc1e5819ab80b063213f26026d6aa95b00d1f108992efb`。
- 当前唯一功能 blocker 为
  `B_QADD_NODE0007_FP32_DUAL_INGRESS_FIRST_ACCEPT_UNRESOLVED`；v18 的宽 blocker 和
  canonical scope blocker 已分别被取代与本地关闭。未上传、未运行服务器、未修改功能 RTL。

## 2026-08-03 GAP v20 正式 return 到达

- 被取代的活动 plan SHA256=
  `6e20ab4c60fff5f7939562b47c0baac837bc2909f02121a3a237755261de867b`；GAP v20
  `PACKAGE_READY_NOT_RUN` 已更新为 `RETURN_COLLECTED / ANALYZING`。
- 正式 return 为 113,340 bytes，SHA256=
  `59cef2d1051f9f4d38f65c473b8ed2e421d4f603fcdee7faef9844a2b6e603e5`；冻结 source
  ZIP 仍为 SHA256=`a82ac187b46dac4f26a8545bf14bebf5bc5481308791be062ce581a30429bbe3`。
- 相邻 return sidecar 未发现；只能按 current 传输规则裁决，不能替代包内 identity、
  manifest、exact-set、allowlist 或 source-package binding。
- 主线已自动派发给 GAP owner；按 return-driven 连续闭环，同一任务完成 receipt-only
  分析、readiness-vs-barrier 逐因子裁决及 fresh successor。未授权上传、服务器运行或
  功能 RTL 修改。

## 2026-08-03 GAP v20 return 裁决与 v23 successor 完成

- 被取代的活动 plan SHA256=
  `4aecafb0bd4c76ad21fdf670a9774b4860a7efef23fb0ad8b73e47f2178f9b56`；GAP
  `RETURN_COLLECTED / ANALYZING` 已更新为 v23 `PACKAGE_READY_NOT_RUN`。
- v20 return 的内部 exact-set/identity/manifest/source/SCA/observer 绑定通过，但
  simulation/runner=`125/125`、signal=`INT`、无自然终态且 48 项 formal D 全部缺失，
  因此 E3/E4/E5 均为 false。
- v20 逐因子动态证据排除了 `buf_ag_ob_full`、`rd_data_chl_ob_full` 和
  `nse2mse_req_barrier`，把原
  `rd_data_chl_data_ready==0 OR nse2mse_req_barrier==1` 收窄为
  `rd_data_chl_data_vld==0`。更早的 memory return、RD inbuffer、queue pairing 与
  prepared-data write 仍不能唯一。
- v21 ZIP SHA256=
  `898fc7ab72a062722c13fefa60a232e1bf361b6b799cd9cb1f8c248709b4bde2`
  因 finalizer 在 `set -u` 下引用未初始化 `rd_data_path_ok` 被正控隔离；v22 ZIP
  SHA256=`5e9bf8ae98833a967ae5c9c8a41fb06ac91b691afa34dc1cf795f86857d2e821`
  因 manifest 漏列连续闭环规则 ID 被 final-ZIP 审计隔离。
- 唯一可运行身份收敛为 `r5_n71_gap_v23_rd_data_vld_path_rulefix`；ZIP 为
  1,810,719 bytes，SHA256=
  `07ea69a9b647542751c3e47b192d5d1ddb497dad97801e75c9fe002331244c19`。
- v23 冻结 73 个 numeric/workload 与 119 个其它非作用域文件，只增加四个
  RD_Data_Channel 边界的 package-local 只读诊断；final-ZIP audit PASS、errors=0，
  双构建、safe runner、wrong identity、39 项 feature 负控和 TERM finalizer 正控均通过。
- return report SHA256=
  `d14c7c2c07bd83cb09b723a6839978286d5e9fda2fded344a6e30d97c832bf94`；
  closure report SHA256=
  `c9c4daa5a23dc365b526295be8af3d1cca3735f7edf0112f8925d24cbf97915f`；
  task record SHA256=
  `4439d431b9c2ad85b1d69643172ee4973d46897c40bf6107287a4aaac5262d84`。
- 未上传、未运行服务器、未取得 lease、未修改功能 RTL；`RULE_DELTA_PROPOSAL=NONE`。

## 2026-08-03 Quantize node0074 从能力阻塞转入实例级旁路裁决

- 被取代的活动 plan SHA256=
  `76f02ddcfaef307041f0266945cdda07a51003031b0103e698121bc90af7aa69`；其中
  QuantizeLinear node0074 的活动状态由
  `HARDWARE_CAPABILITY_BLOCKED / PACKAGE_RELEASE=NONE` 更新为
  `BYPASS_ADJUDICATION_IN_PROGRESS / APPROVED_EQUIVALENT_CANDIDATE`。
- 通用能力事实未变化：current 硬件仍缺少 `EXACT_BINARY32_DIVIDE_RNE`，REC/MUL
  仍被同 scale 的 `159 vs 158` 反例否决，通用
  `B_QUANT_NODE0074_EXACT_DIVISION` 与 `B_QUANT_TAIL_EXACT_FP32_DIVISION`
  均未关闭。
- 用户明确授权审计冻结链
  `node0072 DequantizeLinear → node0073 metadata View → node0074 QuantizeLinear`
  的成对消除。候选依据是 node0072 输入 qdomain 与 node0074 输出 qdomain 的 scale bits
  同为 `0x3cbf57ec`、zero-point 同为 `0`；只有完整 UINT8 域的 binary32 操作顺序与
  真实 storage/layout/lifetime/downstream qdomain 全部证明后，才能对该实例裁为
  `APPROVED_EQUIVALENT`。
- 候选旁路必须绑定 node0071 D/node0072 A 的原始 UINT8 storage，不能复用或改名当前
  node0072 D 的 FP32 131,072-byte endpoint；禁止 host precompute、REC/MUL 除法替代、
  provisional address 或跨 owner 修改 Dequant/Flatten 既有资产。
- Quantize owner `019fa2c0-572b-7f21-ac5a-96e773dde534` 已接收
  `r5-quantize-node0074-dq-view-q-identity-fusion-v1`；只允许本族合同、validator、
  tests、报告和 task record，本轮不授权服务器动作或功能 RTL 修改。
- 高代价 Conv/SA scalar-product→scratch→GA 复合旁路不启动；其现有 RTL blocker
  继续保留。

## 2026-08-03 Quantize node0074 实例级 identity fusion 通过

- 被取代的活动 plan SHA256=
  `918b43a8ff1333f6535806cda5c75d2273fe2663ebbc5370e4ff53c4784a17b4`；其中
  `BYPASS_ADJUDICATION_IN_PROGRESS / APPROVED_EQUIVALENT_CANDIDATE` 已更新为
  `APPROVED_EQUIVALENT_WAIT_INTEGRATION_OWNER / PACKAGE_RELEASE=NONE`。
- 冻结 node0072 Dequant→node0073 View→node0074 Quant 链的 scale bits 均为
  `0x3cbf57ec`、zero-point 均为 0、per-tensor/axis=null。独立 exact-rational
  binary32 验证覆盖 `u=0..255`，最终 mismatch=`0/256`；50 个最终 binary32 商非整数，
  最坏误差=`1/65536`，距错误 RNE 边界最小为 `32767/65536`。
- 实例级 reuse class 正式升为 `APPROVED_EQUIVALENT`：同时移除 node0072/node0074
  算术，用 node0071 D/node0072 A 原始 UINT8 storage 做 metadata-only reshape alias 到
  node0075 A。无 host precompute、scaled/rounded/final replay 或 REC/MUL-as-DIV。
- producer 已证明 16 slices、每片 2,048 bytes、64 个 32-byte transactions，总
  coverage 32,768 bytes；旧 FP32 131,072-byte endpoint 明确排除。
- 通用 `B_QUANT_NODE0074_EXACT_DIVISION` 与
  `B_QUANT_TAIL_EXACT_FP32_DIVISION` 继续开放，但已移出这条冻结链执行路径。
- 六个最终 consumer endpoint 字段保持 null；首个活动阻断转为
  `B_QUANT_NODE0074_IDENTITY_FUSION_NODE0075_BINDING`，需 QLinearMatMul/integration
  owner 物化 node0075 A 地址、read coverage、allocator alias、visibility barrier 与
  accepted lifetime。
- machine report SHA256=
  `213ff272db06229451f2ccd5ca53c5533698dcfc8c28b14bf2cc189fe60ea8f8`；
  task record SHA256=
  `3a63fd8b9403d35d5e8f76a89fd4faf812649f91767cfc71ebe59ffc3b0167f0`。
- 未生成 target/mapping/bitstream/execplan/SCA/server package，未修改功能 RTL，未执行
  服务器动作。

## 2026-08-03 Conv node0004 v22 occupancy 根因撤销与重开

- 硬件组明确 `outbuffer_group_count` 只在 initial population 与 final output
  consumption 改变；ALU 结果通过 `alu2ob_wr_ptr` 回写既有 psum 槽位。
- 主线逐行复核 `SA_PE_Outbuffer.sv` 和 `SA_PE_Control_Block.sv` 后确认该语义与 RTL
  一致：initial write 建立四个 live 槽位，ALU write 替换既有槽位，final output read
  才释放一个槽位。旧 `+1*alu_accept` occupancy 方程错误。
- 旧 blocker `B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED` 与
  `WAIT_RTL_FIX` 裁决撤销；旧 task record/report 保留为历史资产但根因和 repair
  proposal 已被新纠偏记录取代。
- v22 的停滞事实仍成立：SA ingress、ALU accept 与 `alu2ob_wr_handshake` 已发生，而 PE
  output/Buffer5/formal D/terminal 均未发生。其 LAST_PROVEN_GOOD 改为
  `SA_ALU_RESULT_ACCEPT_AND_OUTBUFFER_WRITE`，FIRST_DIVERGENCE 重开为
  `SA_ALU_RESULT_WRITE_TO_FINAL_RESULT_RELEASE_AND_PE_OUTPUT_VALID`。
- v22 observer 未回收 last/matched、`ob_out_rd_ready`、ping-pong select 与四类 ptr
  对齐，不能指认 config 或 RTL leaf。新 blocker 为
  `B_CONV_NODE0004_SA_FINAL_RESULT_RELEASE_PATH_UNOBSERVED`，
  class=`RETURN_REANALYSIS_OPEN`。
- 下一 successor 只允许增加上述终态/指针链的低开销 qualified 观测，冻结
  numeric/W3/qparam/workload/config/golden/functional RTL；未授权 RTL 修改、上传或服务器运行。

## 2026-08-03 QAdd v19 return 到达、Conv 恢复测试与 node0075 集成收敛

- QLinearAdd v19 正式 return 为 45,494 bytes，SHA256=
  `548bb94b570f80878d6b45305b69a4f6a51df7e1ea9157a1788c123b35ca610c`；
  相邻 sidecar 不存在，仅按用户担保处理外部传输层。活动状态由
  `PACKAGE_READY_NOT_RUN` 更新为 `RETURN_COLLECTED / ANALYZING_RETURN_TO_SUCCESSOR`，
  并已交回 QLinearAdd 原 owner 连续闭环。
- 用户明确要求 Conv 从阻塞状态回到测试状态。主线将
  `RETURN_REANALYSIS_OPEN` 更新为
  `SUCCESSOR_PACKAGE_BUILDING / DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`；新包只观测
  last/matched、`ob_out_rd_ready`、ping-pong 与 ptr 对齐，不改功能 RTL。
- node0071→node0075 integration 已物化 metadata alias overlay，验证 9/9 通过；但真实
  node0075 A consumer materializer、MatMul/QLinearMatMul handler、最终
  mapping/bitstream/execplan/SCA 均不存在。首缺口收敛为
  `B_MATMUL_NODE0075_FINAL_A_CONSUMER_MATERIALIZER_MISSING`，
  状态 `WAIT_NODE0075_MATERIALIZER_CAPABILITY`，不是 RTL bug。
- 本轮只更新活动 plan/history 并分发 owner 任务；未上传或运行服务器，未修改功能 RTL。

## 2026-08-03 GAP v23 return 到达

- GAP v23 正式 return 为 112,916 bytes，SHA256=
  `b00dd10f4710509a5a7701182a6fdd09309e5e50a3a9debbadd44a688612b0a6`；
  相邻 sidecar 不存在，仅按用户担保处理外部传输层。
- 冻结 source v23 ZIP 保持 1,810,719 bytes，SHA256=
  `07ea69a9b647542751c3e47b192d5d1ddb497dad97801e75c9fe002331244c19`。
- 活动状态由 `PACKAGE_READY_NOT_RUN` 更新为
  `RETURN_COLLECTED / ANALYZING_RETURN_TO_SUCCESSOR`，并交回 GAP 原 owner；不得重跑
  v23 source，也不得在 return 正式裁决前预判 terminal、formal D 或 E3/E4/E5。
- QAdd v20 与 Conv successor 的本地构包任务继续，不中断；没有上传、服务器运行、lease
  或功能 RTL 修改。

## 2026-08-03 QAdd v19、Conv v22 与 GAP v23 连续闭环完成

- 被取代的活动 plan SHA256=
  `171a904dd7b24a9836943fdf64a2851525f81bae3a99ca13e0c7b0cf99b63951`；其中
  QAdd/GAP 的 `RETURN_COLLECTED / ANALYZING_RETURN_TO_SUCCESSOR` 与 Conv 的
  `SUCCESSOR_PACKAGE_BUILDING` 已退出活动快照。
- QAdd v19 return 的包内身份与 manifest 均通过，但 observer 在 VCS 编译期引用未声明
  `return_obs_ga_operand_capture_mon`，simulation 未启动，不能沿用旧功能 hang。
  v19 已隔离；fresh v20 只补 declaration 与 GA0/GA2 qualified binding，当前唯一包
  SHA256=`13aabd82d62eb1fa25145919c08aa3402de648ac42e401f21e3199f91d53da51`。
- Conv v22 的 occupancy 根因继续保持 `INVALIDATED_NOT_RTL_BUG`；fresh v23 只观察
  terminal/tag、ready、ping-pong/ptr 与 PE output release，当前未证明 RTL defect。
  唯一包 SHA256=`9ec61dda9d1d1729b1896b94e86c92747fbec4b2077a7d779a75d186329e2a27`。
- GAP v23 已证明 MSE0/MSE3 均收到 memory return 并形成 prepared write；MSE3 在
  10 次 qualified prepared write 后 count 仍为 0、`data_vld` 从未成立，而 MSE0
  正常形成并消费 4 次。旧宽 blocker 已关闭，新 blocker 收敛到 MSE3 local reset/
  clear、count update/priority 或 XMR/sampling；fresh v24 唯一包 SHA256=
  `ad71f6d6ab75f0992505d9d4656c058aa4011776bfc9b7c1c14bd78ec9b428ab`。
- 三个 fresh 包均为 `PACKAGE_READY_NOT_RUN / DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`，
  本地双构建与 current-rule final audit 通过；未上传、未运行服务器、未取 lease、
  未修改功能 RTL。

## 2026-08-03 Conv v23 return 到达

- 被取代的活动 plan SHA256=
  `79971afee8e6465ea560518f5c130a76a93d762673ea1bf71d70b59c83b81891`；Conv v23 的
  `PACKAGE_READY_NOT_RUN` 状态已退出活动快照。
- 正式 return 路径为
  `C:/Users/15383/xwechat_files/wxid_vwpfpfs4fgyk22_29b7/msg/file/2026-08/r5_n4_hw_v23_final_release_diag_return.zip`，
  bytes=`29,867`，SHA256=
  `e8efef64b095f5d6cc2b5e4d734b6d1a94a14741d3b608dfc008ef6894905842`。
- 相邻 sidecar 不存在，仅按用户担保替代外部传输层收据；源 v23 ZIP 保持
  `5,826,256` bytes、SHA256=
  `9ec61dda9d1d1729b1896b94e86c92747fbec4b2077a7d779a75d186329e2a27`。
- return 已交回 Conv 原 owner
  `019fa2c1-17df-7122-bcbd-a727aaf173f5` 做 receipt-only 分析并连续生成 successor；
  v23 source 禁止重跑。旧 occupancy blocker 与 `WAIT_RTL_FIX` 继续保持
  `INVALIDATED_NOT_RTL_BUG`，不得在新证据裁决前复活。
- 本次只更新活动 plan/history 并分发任务；未上传或运行服务器，未修改功能 RTL。

## 2026-08-03 MaxPool 原生 v5 return 到达

- 被取代的活动 plan SHA256=
  `ff9a254262b66cde100c1b8d13fc4539f2e10d9a137203ab6c20d8a4c0ca134d`；MaxPool v5 的
  `PACKAGE_READY_NOT_RUN` 状态已退出活动快照。
- 正式 return 路径为
  `C:/Users/15383/xwechat_files/wxid_vwpfpfs4fgyk22_29b7/msg/file/2026-08/r5_n2_maxpool_ndpsim_native_v5_return.zip`，
  bytes=`35,166`，SHA256=
  `68265ded27f981d3ac448848baae2658ee15710c947155c8ed69dd9fa78fb1dc`；
  相邻 sidecar 不存在，仅按用户担保替代外部传输层收据。
- 冻结 source v5 ZIP 保持 `14,718,654` bytes、SHA256=
  `9a193d8f97d7b43d7e43886a2bc42dffee74e585832f5360a13a8ead2fa7269e`。
- return 已交回 MaxPool 原 owner
  `019fbe9f-3f2d-7071-806c-1ae72ae96391` 做用户特例验收。学长已测和
  ndp-sim 原生结构 authority 继续有效：不恢复 v4 capture→outbuffer 通用诊断、
  observer/canonical、numeric/NumPy/GeneralPEA/W3 或 RTL 复测。
- 本次只更新活动 plan/history 并分发任务；未上传或运行服务器，未修改功能 RTL。

## 2026-08-03 Conv v23 与 MaxPool 原生 v5 return 裁决完成

- 被取代的活动 plan SHA256=
  `1fcefd012f3771003954cd8a64c9856c4fc557a502618d1dac95485bd7a6df7c`；Conv 与
  MaxPool 的 `RETURN_COLLECTED` 状态已退出活动快照。
- Conv v23 的正式 return 在 package-local observer 编译期失败：文件
  `native_return_observer.svh:3926` 使用未声明
  `return_obs_buf45_wr_edge_count`，simulation 未启动，formal D=`0/320`。这不是
  Conv 数值、配置或 RTL hang；v23 已隔离。
- v23 的规则读取收据完整且 current-match，漏检根因不是未读规则，而是旧 validator
  只要求错误 token 存在，safe compile stub 从未执行 HDL syntax/name resolution。
  v23 旧 final-audit PASS 作为 release 充分条件及 `PACKAGE_READY_NOT_RUN` 已撤销。
- Conv fresh v24 只修正 qualified Buffer5 write counter 的 declaration/reset/update
  与 return manifest identity；新增 Icarus focused compile、exact declaration/use
  closure，以及删声明、拼错 use、删 update 三类负控。唯一包 SHA256=
  `3701226c52de41a6982dd0ac9a111ade26c26ed088eee53d62fcc038cd5980fc`。
- MaxPool v5 的内部身份、manifest、SCA/SCA_D、preflight、compile 与 native start 均
  通过，但在 slice start 后被 INT 中断，formal D=`0/28`。无 package infrastructure
  defect；按用户特例裁决为 `DEFERRED_BY_USER_NATIVE_REUSE_OVERRIDE`，
  `PACKAGE_RELEASE=NONE`，不生成通用 successor。
- 本轮未上传、未运行服务器、未取 lease、未修改功能 RTL；公共 observer HDL
  syntax/scope 正控仅形成规则提案，尚未修改公共规则。

## 2026-08-03 当前 observer 包横向暂缓

- 被取代的活动 plan SHA256=
  `1998f257e1841b048b8307eea2b69f3360af708e715fb20f24a489b420453ac5`。
- Conv v23 的 audit escape 证明 safe compile stub、token presence 和 XMR constant
  scan 不能替代 HDL syntax/scope/name-resolution。横向复核确认 GAP v24 与 QAdd v20
  的 current final audit 同样没有调用兼容 HDL frontend。
- GAP v24 主要依赖 token/feature/runner stub 验收；QAdd v20 虽有目标 declaration/use
  文本负控，但仍未对 exact final observer 执行 HDL frontend 正控，不能证明其它局部
  identifier 全部闭合。
- 主线暂时撤销 GAP v24 与 QAdd v20 的运行队列资格，状态改为
  `PACKAGE_HELD / HDL_SCOPE_REVALIDATION_REQUIRED`。包字节和既有诊断裁决保持不变；
  原 owner 只做包外同门复验，失败时才 fresh 修包。
- Conv v24 已通过 Icarus focused compile、exact declaration/use closure 及三项负控，
  不受该暂缓影响。MaxPool v5 无通用 observer 且已按用户特例消费，不适用。

## 2026-08-03 package-local HDL 公共放行门正式合并

- 被取代的活动 plan SHA256=
  `c30ab3ba244386c704e0826ad7beba4e77b960ee52dd2a9920122518dc557681`。
- 旧服务器规则 SHA256=
  `7a5383b7881b71043bb99d997c92524cb8c25df304179b53f364219fd7c1b141`；
  它已经要求本地可发现语法错误不得带到服务器，也明确 safe runner stub 不能替代
  production compile，但没有单独规定 exact final package-local HDL 的 executable
  syntax/scope/name-resolution 正控。
- 主线正式合并
  `CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001`：
  最终 ZIP exact bytes 必须通过兼容 HDL frontend、identifier/state ownership closure
  和删除 declaration、拼错 consumer use、删除 reset/update 三类负控；token presence、
  XMR constant scan、四向绑定和 safe stub 均不能替代。final audit 还必须输出单一
  `package_local_hdl_gate` 机器记录；缺 exact members、frontend/closure/negative
  receipts、claim boundary 或 `pass=true` 时主线不得排入服务器队列。主 manifest
  还必须内联或哈希绑定 ZIP exact-set 内唯一 HDL scope contract，覆盖 HDL members、
  compile profile 和 feature state leaves；外部 report 不得补包内合同。
- 新门不增加服务器源码树预检，也不要求 Windows 本地拥有完整 VCS/vendor/DUT 依赖。
  完整依赖不可用时，允许 focused compatible frontend，但必须绑定 exact final HDL 的
  机器 closure、限制 wrapper/stub 只能提供外部依赖，并记录全部 specialization 与
  claim boundary。production VCS 仍是全设计最终 elaboration 证据。
- QLinearAdd v20 对冻结 ZIP 完成包外只读 HDL 正控并通过；ZIP SHA256 保持
  `13aabd82d62eb1fa25145919c08aa3402de648ac42e401f21e3199f91d53da51`，
  `return_obs` used/declared/unresolved=`121/121/0`，Icarus focused compile exit=`0`，
  三类负控 fail closed。该证据继续有效；但随后统一 manifest 审计确认 v20 的 4 个
  HDL member 虽有 files SHA/feature 摘要，却没有完整包内 state-leaf contract。
  因此短暂的 `PACKAGE_READY_NOT_RUN` 中间裁决被撤销，v20 隔离并进入 fresh 最小重建。
  复验报告 SHA256=
  `114893b15ebb90f6c4440ef82f38b60815fbe319f5a44f024c10fc0ed902e402`。
- GAP v24 随后的同门复验确认 exact observer HDL 正控和三类负控本身通过，但 package
  manifest 缺新规则要求的完整 HDL members、compile profile 与 feature state leaves。
  该缺口不能由外部 receipt 补齐，旧 `PACKAGE_HELD` 已进一步收敛为
  `QUARANTINED_PACKAGE_LOCAL_HDL_MANIFEST_CONTRACT_MISSING`；原 owner 进入 fresh 最小
  重建，observer 与 numeric/config/workload/golden 保持冻结。
- Conv v24 的 exact observer declaration/use closure、Icarus focused compile 和三类
  负控同样保留为有效证据；统一 manifest 审计发现其旧 manifest 只有 observer SHA、
  四向绑定和 feature 摘要，也没有完整包内 state-leaf contract。v24 同样隔离，由
  Conv owner 使用 fresh identity 仅补 manifest/contract/validator；Conv 数值、配置和
  功能 RTL blocker 不变。

## 2026-08-03 用户纠正本地 HDL 自检边界

- 用户重申原始原则：严格错误检查尽量在本地完成，避免浪费服务器时间；但本地自检不得
  过度严格，只需要保证包能正常进入服务器 compile/run，并能可靠回收本轮目标错误。
- 上一阶段要求“所有 feature state leaves 必须内联/绑定到包内 manifest，否则 fresh
  重建”的裁决被认定过严并撤销。它会因非运行依赖的审计形式隔离已经通过 scoped HDL
  正控的包，不符合服务器最小预检原则。
- 公共规则收窄为：兼容 frontend 只需实际覆盖本轮新增/修改，或进入必需 canonical/
  result decision 的 package-local identifier/state leaf；相关 declaration/use/update
  负控必须 fail closed。无关历史 observer state、完整本地 DUT/vendor 依赖和
  full-design elaboration 不要求穷举，production-only 差异由服务器真实 compile 自然
  发现。
- HDL gate 的机器收据允许作为绑定 exact ZIP/member SHA 的包外 final-audit/
  revalidation report；服务器运行不依赖它。仅缺包外审计 inventory 不得强制重打包，
  也不得新增服务器源码树/Make/TB/filelist/Git 预检。
- QLinearAdd v20 的 manifest-only successor 在物化前停止；未生成新 identity，冻结 ZIP
  SHA256=`13aabd82d62eb1fa25145919c08aa3402de648ac42e401f21e3199f91d53da51`
  不变，并恢复 `HDL_SCOPE_REVALIDATION_PASS / PACKAGE_READY_NOT_RUN`。
- GAP v24 与 Conv v24 已各自取得正式服务器 return，旧 manifest-only 隔离裁决不影响
  raw return 有效性；两份 return 已交原 owner 按 return-to-successor 规则分析。

## 2026-08-03 GAP v24 与 Conv v24 return 消费完成

- 被取代的活动 plan SHA256=
  `24ca593e1be4ae1c16b70ba60762f3c096559ac0904932010a9e75b9a5088dbe`。
- GAP v24 关闭旧
  `B_GAP_NODE0071_MSE3_PREPARED_COUNT_UPDATE_PENDING_LOCAL_RESET_OR_UPDATE_CAUSE`：
  MSE0/MSE3 prepared-count 均实际形成 7 write、3 read、`0→8→0`，且无 reset edge。
  旧不对称外观属于采样可见性限制。新首分歧移到 GA 最后一批结果与 MSE4 第 9 个
  request/write-data 配对；唯一后继为 `r5_n71_gap_v28_ga_mse4_final_pair_diag`，
  ZIP SHA256=`7b34ef0b592ebfd86d3e75a0983a91c8d87271454139e609174cdce8afc7d422`。
- GAP v25 是过严 manifest-only 路线的未发布中间资产；v26 因生成器参数错误中止，
  v27 亦未发布。以上身份均保留但不得运行或复用。
- Conv v24 已越过旧 observer 编译错误并进入真实仿真：raw terminal edge=`256`，
  但 qualified terminal matched/out=`0/0`，320 项 formal D 全缺。旧 occupancy
  blocker 与 `WAIT_RTL_FIX` 继续标为 `INVALIDATED_NOT_RTL_BUG`。
- Conv 首分歧收窄为 raw input terminal→qualified transout match/out；唯一后继为
  `r5_n4_hw_v25_terminal_match_diag`，ZIP SHA256=
  `e4aaf762a3b434a78dfc4af276b48405f84b6dbaee1dad224282ac7b14fb1eab`。
- 两个后继均只增加当前首分歧所需的低开销只读观测；focused HDL 正控只覆盖本轮新增/
  必需裁决叶，不声称 full-design elaboration。两包的双构建、runner/finalizer、
  相关负控和最终 ZIP 审计均通过；未修改功能 RTL，未上传或运行服务器。

## 2026-08-03 return owner 完成通知与规则反馈闭环

- 被取代的活动 plan SHA256=
  `2a956e62f76ff2f0fd84c331a40077a608b7ce498cc7eacc67a42ab9f5d29577`。
- 用户明确服务器包运行期间无需主线持续盯守；控制点改为用户提交正式 return 后自动
  分发给对应持久 owner。
- 旧规则已经要求 RETURN→successor 连续闭环和 `RULE_DELTA_PROPOSAL`，但没有明确
  “owner 完成后必须主动通知当前主线”，也允许无证据的
  `RULE_DELTA_PROPOSAL=NONE` 形成形式回传。
- 新增
  `CDA-SERVER-RETURN-OWNER-COMPLETION-NOTIFY-RULE-FEEDBACK-001`：分发单必须绑定当前
  主线 ID；owner 完成后主动发送结构化通知，并二选一提交有证据的规则修改提案或规则
  确证。分支不得直接修改 plan/rules；主线负责正式修改、记录确证或拒绝同义/过严提案。

## 2026-08-03 完成通知范围扩展到服务器包生成

- 用户进一步明确：分支在本地完成服务器测试包时，也必须主动回传主线，不能等包运行后
  收到 return 才形成完成通知。
- 上一条仅命名 return owner 的规则 ID 被扩大并替换为
  `CDA-SERVER-PACKAGE-OR-RETURN-OWNER-COMPLETION-NOTIFY-RULE-FEEDBACK-001`，没有新增
  同义规则。
- package owner 达到 `PACKAGE_READY_NOT_RUN` 或明确终止状态时，必须主动回传
  ZIP/sidecar 身份、唯一命令、预期 return、final-ZIP 自检、blocker 和规则反馈；
  return owner 仍按原门回传完整 RETURN→successor 结果。两者都绑定派发单中的当前
  主线 ID。

## 2026-08-03 Conv v25 与 QAdd v20 return 转入分析

- 被取代的活动 plan SHA256=
  `c319da9ca373c0a8f72702cd57cd61d651e5de73af7a5a03f88ddab0f5040eed`。
- Conv v25 的 `PACKAGE_READY_NOT_RUN` 状态退出活动运行队列；正式 return bytes=`96603`，
  SHA256=`e6b35bc2f311b9cdf184c65bdd6f8ad834ededf6888ffb390943b83d87d1ac5f`，
  已交 Conv/SA 持久 owner 按新完成通知/规则反馈门闭合。
- QAdd v20 的 `PACKAGE_READY_NOT_RUN` 状态同样退出活动运行队列；正式 return
  bytes=`179242`，SHA256=
  `fd874e7d0f2ded42a31288bfa273c9fe32323c15455d256fb2cb01e66d0563d7`，
  原 owner 已开始分析。用户批准 A/B/C/D 分段诊断，但分段只作定位/局部证据，最终
  六阶段+28 D 端到端 E4/E5 仍保留。

## 2026-08-03 Conv v25 根因闭合为配置阈值错误并发布 v26

- 被取代的活动 plan SHA256=
  `ea465e54afb96968fdcb5c8d373f585ad94747a00a95796bbe860ddbc0246cb6`。
- Conv v25 的 256 条 terminal 全部是 qualified A/B accept，accepted
  `last_index` 只取 4/5；最终配置却把 `special_array.transout_last_index` 物化为 2，
  因而 256/256 条 terminal 全部落入 ignore，matched/out 与后续 release 均为 0。
- 旧活动 blocker
  `B_CONV_NODE0004_RAW_TERMINAL_TO_QUALIFIED_TRANSOUT_MATCH_UNOBSERVED` 已关闭；
  根因确定为 `B_CONV_NODE0004_TRANSOUT_THRESHOLD_BELOW_ACCEPTED_TERMINAL`，
  属于 deterministic config error，不是功能 RTL defect。旧 occupancy blocker 继续
  `INVALIDATED_NOT_RTL_BUG`。
- fresh v26 只把 `transout_last_index` 从 2 改为 5；mapper 编码
  `0010→0101`，bitstream 仅 3 个 byte offset 变化，execplan/SCA 与 84 个矩阵不变。
  当前唯一 Conv 可运行包为
  `r5_n4_hw_v26_transout_threshold_fix.zip`，SHA256=
  `94beb61460e033fbf8ec7afd4cd64e38cd23681fb894df9960bd3cb4be962ddb`。
- v26 等待验证 DUT natural terminal 和 320 项 formal D；E3/E4/E5 尚未形成。主线
  接受 owner 的证据化 `RULE_CONFIRMATION`：现有 hang-first、结果联合门、
  return→successor、package-local HDL 和主动完成通知规则已经覆盖本轮，不新增同义规则。

## 2026-08-03 QAdd v20 B-stage 首轮分段证据

- v20 return 身份、source binding 与 preflight 已闭合；compile=`0`，simulation=`125`、
  signal=`INT`、natural terminal=false，formal D=`0/28`，E3/E4/E5=false。
- A dequant 完成后，B dequant 出现 VCS zero-delay warning。v18 同配置曾完成 B
  dequant 与 relocation，且 v18→v20 没有 config/bitstream/execplan/golden 变化；
  当前优先怀疑 v20 新增 observer instrumentation/event amplification。
- 返回 canonical 把 stage2 B-dequant 错归为 FP32 add，并消费单边 MSE0 activity，
  已按 ordered-stage/qualified-event 规则拒绝。继承同一 observer 的 v21 B-isolated
  中间候选同时未通过 final audit，已隔离且不得运行。
- QAdd owner 正在以 v18/proven base observer、原始 B 输入和硬件产生的 B scratch
  重建 fresh B-only control；本条是阶段性状态，不构成 `PACKAGE_RELEASE`。

## 2026-08-03 QAdd v22 B-only 包被主线 final-audit 复核驳回

- 被取代的活动 plan SHA256=
  `29c98580925a2932c6db62ec679272cad644bc1bc16a7f43bba22c46ce82c0e2`。
- QAdd owner 生成 `r5_qadd_n7_b_dequant_control_v22.zip`，SHA256=
  `4a51be0ab59b0ff8c0754de68f11d7f3d1328b6fe012b3945468b787d2b11fd5`，
  其 B-only 设计选择有效：保留 v18 base observer、原始 B 输入和硬件产出 B scratch，
  移除 v20 FP32 tail 与 GA-capture shim。
- 主线复核发现 exact ZIP 含 package-local `.svh`，但 final audit 没有 compatible HDL
  frontend、exact-member scoped declaration/use/update closure 或删除 declaration、
  拼错 use、删除 update 三类负控；与 current
  `CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001` 不符。
- safe compile-stub 正控的 `stderr_tail` 同时出现 3 条
  `grep: ... No such file or directory`，却被 validator 标记为 PASS；这不满足
  runner/finalizer 正控的无 shell diagnostic 要求。
- 因 runner 字节需要修正，v22 不能通过包外 content-neutral receipt 恢复，状态改为
  `QUARANTINED_FINAL_AUDIT_NONCOMPLIANT_DO_NOT_RUN`。主线已把 fresh 修正任务退回原
  QAdd owner；v20 return 分析、LPG/FD 和 observer-leading 假设仍有效。
- owner 的 `RULE_CONFIRMATION=CURRENT_RULES_SUFFICIENT` 只在规则充分性层面成立：
  current 规则确实足以拒绝本包；其 `PACKAGE_READY_NOT_RUN` 与 final-audit PASS claim
  被驳回。公共规则无需新增同义条款，需修 validator/runner 并重新封包。

## 2026-08-03 QAdd v22→v24 包侧审计连续闭环

- 被取代的活动 plan SHA256=
  `f403d52bb4cd049c1dec193057007be6108d8764625f42d8eb098378c8f8493d`。
- v22 保持
  `QUARANTINED_FINAL_AUDIT_NONCOMPLIANT_DO_NOT_RUN`；fresh v23 已关闭 grep stderr
  diagnostics 并补齐 package-local HDL gate，但 compile-failure return 除 28 项
  formal D 外仍缺 `sim.log`、actual simulator argv 和 observer log 三项必需占位收据，
  因此同样隔离，SHA256=
  `cabc6682be6ca0aa913b5ea3d3d719d88770e0548cf5bf4eb2ec1e4774ecd70f`。
- fresh v24 只继续修正 runner/finalizer 与 final-ZIP 自检；B-only control、v18 base
  observer、原始 B 输入、硬件 B scratch、numeric/W3/qparam/tail/workload/config/
  golden/functional RTL 均冻结。
- exact package-local HDL preprocess/focused compile 均 exit=`0`；identifier closure
  unresolved=`0`，删除声明、拼错 consumer use、删除 qualified update 三类负控均
  fail closed。safe compile-stub exit=`86`、stderr 为空、finalizer artifacts 完整，
  `required_missing` 精确只有 28 项 formal D；EXIT/TERM 与其余负控闭合。
- 唯一可运行身份更新为 `r5_qadd_n7_bctrl_v24.zip`，bytes=`38032104`，SHA256=
  `71e14695c3025340987dba2fc0ffedd23e8e61d9bcb6eaec704de74c8e6928da`，
  状态 `PACKAGE_READY_NOT_RUN / DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX /
  E2_LOCAL_ONLY`。它只用于动态区分 v20 observer event storm 与真实 B-stage 停点，
  不形成 E3/E4/E5。
- 主线接受 owner 的证据化规则确证：现行 package-local HDL syntax/scope 与 runner
  preflight-to-compile 正控规则均必要且有效；本轮无需新增同义规则。

## 2026-08-03 GAP v28 与 Conv v26 正式 return 到达

- 被取代的活动 plan SHA256=
  `e37ee58cf9a4ac98423b066516ee610054f940505c00a8e3fb2bc921a412c583`。
- GAP v28 return bytes=`129696`，SHA256=
  `875a9ec0ade4f1957025e0b7cefb0e843830f6dca57db8c078d462c5df40b0ff`，
  已交 GAP 持久 owner `019fa366-cb1f-7ae2-880c-f527be0680cd` 做
  RETURN→successor 连续闭环；v28 source 退出运行队列并禁止重跑。
- Conv v26 return bytes=`96874`，SHA256=
  `2a3e041737376a8afdfcb70d85e30c9f4c7fbc12d5bdad94c9ec2c9b7fa78d68`，
  已交 Conv/SA 持久 owner `019fa2c1-17df-7122-bcbd-a727aaf173f5` 验证
  threshold 修正、natural terminal 与 320 项 formal D，并连续生成必要后继；
  v26 source 退出运行队列并禁止重跑。
- 两项分发均要求根因唯一则生成修正包，否则生成更窄低开销诊断包；完成后主动回传
  当前主线并提交有证据的规则确证或规则增量提案。
- 主线同步纠正活动 plan 中两处 `33-stage assembly` 笔误：typed lowering、复用策略
  合同和生命周期合同均要求最终 `133-stage` 整网 assembly。
- node0074 实例旁路本身已批准，但不能生成无 consumer 的独立 Quantize 假包；真正首
  缺口是 node0075 QLinearMatMul handler/materializer。该后续任务已排队给
  Conv/SA/MatMul owner，在 v26 return 闭环后尝试物化本地 E2，成功后才允许生成待测包。

## 2026-08-03 QAdd 真拆分物化启动

- 可拆性合同确认 v24 最终 SCA 本来就是 B-dequant 单 stage：
  `Repeat_Num=1`、`Exec_Length=29`、
  `ExecutionPlan=execplan_op_b_dequant.txt`；ZIP 中携带六 stage 资产不代表实际执行
  六阶段。v24 字节和运行资格不变。
- A 采用原始 typed A/B 的双 dequant 独立 workload；B 的 relocation 输入是冻结 graph
  external 非计算性 FP32 零 spacer，可合法独立运行。
- C 没有逐字节硬件 A/B-scaled checkpoint，故按主线门退化为
  A+B+relocation+fp32_add 累计前缀；D 没有逐字节 FP32 SUM checkpoint，退化为完整
  六阶段+28 formal D。没有使用 host 内部 tensor replay。
- machine contract SHA256=
  `9943f6ae67587d5e522378b1cbae212e52fa745fb67b6dcce6574eeb9b07b38f`；
  start task record SHA256=
  `10a386eb93bb15c3697c74e42509b58be4f45dbf867fe5f8b1f2eb41aedf4ea0`。

## 2026-08-03 GAP v28→v29 与 Conv v26→v28 连续闭环

- 被取代的活动 plan SHA256=
  `441d70933a7985a40135ed3e4a6ebe1c94190fac0c61952360ce7e258218c466`。
- GAP v28 证明 48 次 GA accept 全部 retire 且 MSE4 消费全部 12 个可用 paired
  wdata，关闭旧 GA final pipeline→MSE4 pairing blocker；首分歧转为 MSE0 的
  Buffer accept 13→prepared write 8→GA group0 capture 6，相比 MSE3 的
  13→13→8 不对称。fresh v29 仅围绕该边界诊断，ZIP SHA256=
  `15833d826872e118a9be834b082351ae2b31862da0b138a2a4f271269108e164`。
- Conv v26 动态证明 `transout_last_index: 2→5` 修正确实越过旧 terminal-ignore
  停点，并产生 28 次 D request/data accept；随后停在 D write accept→Buffer5
  next read/last-index0→slice finish。fresh v28 仅补齐该 required boundary，
  ZIP SHA256=
  `a3b2be33d395356b06c96e8311c017544cbdcc7b3e553006ae582acea176101f`。
- Conv v27 因 return collector 未绑定新 feature receipt 被现行规则捕获并隔离；
  fresh v28 修复该包侧绑定后 final audit errors=`0`。现行规则已得到确证，无需新增
  同义条款。
- 两个 fresh 包均为 `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX /
  PACKAGE_READY_NOT_RUN / E2_LOCAL_ONLY`；未修改功能 RTL，未上传或运行服务器。
- Conv/SA owner 完成 v26→v28 后，已按用户授权立即转入 node0075
  QLinearMatMul backend/materializer 补齐；其余 52 个 Conv 暂不扩展。

## 2026-08-03 node0075 从 Conv owner 拆分为独立算子族

- 被取代的活动 plan SHA256=
  `6b82860af88b991cb4401fa2f3b36bbda5a2d04ff2e247addb4a5daeaf3375b8`。
- 主线纠正了按共享 SA 后端而非按算子族分发的所有权混淆。node0075 不再属于 Conv
  owner，独立 QLinearMatMul owner 为
  `019fc775-8de0-7f10-bc4a-026a4673776f`。
- 原 Conv owner `019fa2c1-17df-7122-bcbd-a727aaf173f5` 已收到停止 node0075、
  保留只读审计并恢复 Conv-only 的通知；不得删除或回滚共享工作区内容。
- node0075 的至少 8-pass A qualified reload 授权、完整 backend/E2 目标和所有
  no-copy/traffic/lifetime 门完整转交新 owner。
- Conv 保持原 serialized correctness baseline：compute/weight/activation occurrence
  约 4 倍、最高 25% useful-lane 利用率、candidate_release=false；当前只继续 node0004
  v28 与 320 formal D 联合门，不作性能通过声明。

## 2026-08-03 Conv node0004 原生四-lane 性能路线独立启动

- 被取代的活动 plan SHA256=
  `5f5715b1cb3d7649b36dc79736eb2da1038ef8ea94acd1884bf17092033f8654`。
- 用户决定保留 serialized one-product 为独立正确性基线，同时新开
  `019fc783-1146-7901-9e40-64d0ed8e052d` 专门物化 native four-lane 性能候选。
- 新任务目标是把 compute/weight/activation occurrence 从约 4 倍降至接近 1 倍，把
  useful product-lane utilization 从最多 25% 提升至接近 100%；通过前不宣称性能或
  production。
- 新任务必须先绑定修复后 RTL identity，保留历史 stock 负控和 serialized 独立
  oracle，并处理 `SA_PE_Float_CSA` 的负 psum 边界可达性；命中即停止且不得自行改
  RTL，不命中也只能形成冻结模型范围的正确性声明。
- E2 闭合后才允许生成 candidate_release=false 待测包；服务器上传、运行和 lease
  仍由主线/用户另行控制。

## 2026-08-03 QAdd 真拆分原生物化阶段性闭合

- A/B/C 的原生 execplan/request 已闭合；D 保持冻结六阶段 full+28D。合同 SHA256
  更新为 `37dc6c2a0b0f4176a8e9372a29f10db8f3b6e2c630203487b3ea6041c521c9e1`，
  progress report SHA256=
  `b0a8257a143e070a7284c3877cc5e1334e4d1047c64c6cacd478719870691eee`。
- runner/observer/manifest/ZIP/final audit 尚未完成，状态仍为
  `PACKAGE_RELEASE=NONE_IN_PROGRESS`；v24 保持唯一可运行 QAdd 身份。

## 2026-08-03 node0075 独立 owner 在首个 RTL 语法叶终止

- 独立 owner `019fc775-8de0-7f10-bc4a-026a4673776f` 完整读取启动规则并确认旧
  Conv owner 未新增 node0075 materializer 资产。
- 首个不可表达叶为 active `SA_PE_Float_Control.v` final ANSI port 的多余逗号；
  source SHA256=`c6018e762411e14346bfec672b273b826f893b11c5de0cfb38fca674f9d33c4b`，
  focused Icarus compile exit=`1`。非 RTL handler/mapper 无法绕过该硬门。
- owner 按边界以
  `TERMINATED_AT_FIRST_NONEXPRESSIBLE_HARDWARE_LEAF / PACKAGE_RELEASE=NONE`
  停止，未生成 target/handler/mapping/bitstream/execplan/SCA/E2/package，未修改
  plan/rules/RTL/Conv 资产。
- 8-pass A reload 的实际 pass/read/traffic 全为 0；预算不冒充 acceptance。下一动作
  需要 RTL owner 删除逗号并完成 current full VCS NDP top compile。

## 2026-08-03 活动 RTL 同步云端 master 并关闭 node0075 逗号叶

- 被取代的活动 plan SHA256=
  `8bde3e23b345853d4058099eb8215b4a710ce9adbf182fcbabf14fea8f6d4aec`。
- 用户确认硬件侧已经修复 `SA_PE_Float_Control.v` 末端端口逗号。主线核对发现本地
  活动文件仍为旧 SHA256=
  `c6018e762411e14346bfec672b273b826f893b11c5de0cfb38fca674f9d33c4b`，
  focused compile exit=`1`，确属漏同步。
- 主线从权威私有 GitHub master
  `8f2f3181c1103d705cdf9b9722959e7315f8b875` 精确同步 18 个变更/新增
  source/filelist 路径。同步后相关 2011 个源文件逐字节 zero-diff；
  `SA_PE_Float_Control.v` current SHA256=
  `4214262e12ab80bf3be867f558d762e134c3122f16df4f7d08063e383242c4e6`。
- exact 单模块以及 `SA_ALU/SA_PE_ALU/SA_PE/SA_PE_Group` focused compile 全部
  exit=`0`；旧文件负控仍精确 exit=`1`。因此
  `SA_FLOAT_CONTROL_ANSI_PORT_TRAILING_COMMA` 正式关闭，node0075 owner 恢复。
- Conv native-four-lane owner 同期证明真实 W3 在 19 个实例存在 528 个
  `(-5,+5)→0` occurrence。云端 current `SA_PE_Float_CSA` 虽 SHA 变化，但
  full-width assignment 仍被注释、live split reconstruction 未修，故性能任务仍为
  `HARDWARE_CAPABILITY_BLOCKED / PACKAGE_RELEASE=NONE`；不得因本次同步误恢复 E2。
- machine report SHA256=
  `4a798e2257ece9d49d64ff8fc00acc826fef3d4dbd35291e26e88f141c273e18`；
  task record SHA256=
  `3a401af64c1742580c3955eaebdf211fa4c6235038f35e9ed9e1ac7327fe019f`。

## 2026-08-03 node0075 恢复后命中冻结实例 negative-psum 硬门

- 被取代的活动 plan SHA256=
  `af733b60e539263b3be449dbcfdd77442db9a530c612041e29b6df9263495772`。
- node0075 owner 在 current `8f2f3181` RTL 上关闭逗号语法门后，没有直接生成
  materializer，而是按公共 INT8-SA 兼容性门扫描完整中间 recurrence。
- 冻结 `M16×N1000×K2048` 实例共 8,192,000 个 dot4 recurrence，其中
  negative psum 4,343,952 次、negative→exact-zero 272 次。首例为
  `psum=-19, dot4=+19`，数学结果 0；current RTL focused 仿真实际输出
  `INT32_MIN`。
- 因此旧“冻结 final acc 没有错误即可避开该边界”的状态被撤销。16,000 个最终
  acc mismatch=0 不足以证明中间 recurrence avoidance。
- owner 以
  `B_MATMUL_NODE0075_SA_NEGATIVE_PSUM_ZERO_BOUNDARY_REACHABLE /
  HARDWARE_CAPABILITY_BLOCKED / PACKAGE_RELEASE=NONE` 终止，未进入 materializer、
  E2 或构包；至少 8-pass A reload 仍只是修复后的预算。
- task record SHA256=
  `45b344dec217f5224675f4bae43edc20d25e9e6a836c3b8bf8a6f871bffb6d82`；
  contract SHA256=
  `a1fb5f8656a8ad5f79be91e1b1f0aaede3dae87da66d271ee7a7345a371025d8`；
  validator report SHA256=
  `1d8c9c69ec5126e2be46532961e6efb2639b20847ae7326f93fa7cf5903a248b`。

## 2026-08-03 node0075 主线独立排除误报与 QAdd v24 control 闭合

- 被取代的活动 plan SHA256=
  `2561cf5ac251310ecab125ce37a8b8739c60070705c374723284d4776e6781cc`。
- 用户质疑 node0075 negative-psum 是否可能重演 occupancy 误报。主线没有复用 owner
  testbench 判定，而是新建数学期望驱动的 current-RTL testbench，并加入
  `-20+19`、`-18+19`、零/正 psum 相邻正控；只有 `-19+19=0` 得到
  `0x80000000`，其余相邻点正确。
- 主线另以不 import owner 模块的 fresh NumPy/ONNX 程序复算全部 8,192,000 次
  recurrence，独立得到 negative psum 4,343,952、exact cancellation 272 和同一首例。
  stale source、packing、operand direction、latency、self-confirming TB、owner
  enumerator 与 synthetic-unreachable 假设均被排除，硬件缺陷裁决保持。
- independent report SHA256=
  `bcfaa5047b4b5aa1845fc253f0c5da4b7ea1c6f9b221f54cf2a2173899fda10d`；
  task record SHA256=
  `6b698a4e099311555494c6e0893ce82eaf4f5304a870458adab402a63bd40487`。
- QAdd v24 B-only control 同期自然完成：compile/simulation=`0/0`、B-dequant
  543,212 active cycles、32/32 qualified windows；证明 v20 停点来自 package-local
  observer 路径，不是冻结 B 配置/RTL。28 D 均为 X，E3/E4/E5 仍 false；v24 退出
  运行队列，A/B/C/D split packaging 继续。

## 2026-08-03 Conv native-four-lane negative-psum 主线独立复核

- 被取代的活动 plan SHA256=
  `7b1f670e5d12c9bb8ad6d04a00f8a49e8bbd476362790bc7751c08012e62ae5a`。
- 主线没有复用 Conv owner 的首例或扫描器作为计算输入，而是直接从冻结 ONNX
  weight/bias/wzp、W3 activation 与 typed request 重建 node0003 /
  `hwop-0003-00` 的一条真实 recurrence：
  `bias=5687`、前 14 组 dot4 和=`-5692`、进入 group14 时 `psum=-5`；
  当前 lane 为 weight `[-1,0,0,1]`、activation `[21,24,24,26]`，
  因而 `dot4=+5`、数学 next=`0`。
- fresh current-RTL testbench 对同一 packed operands 得到
  `0x80000000`；`-6+5=-1`、`-4+5=1`、零/正 psum 相邻正控均通过。
  current `SA_PE_Float_CSA` 在精确抵消时把低 31 位重建为 0，却独立复制 raw
  bit31=1，是可动态复现的功能错误，不是 occupancy/count 语义误读。
- node0004 代表实例自身仍不命中；硬门来自 native-four-lane 计划扩展的 node0003。
  owner 报告的 `528 hits / 19 instances` 本轮未重枚举，但一个真实可达 mismatch
  已足以保持 `HARDWARE_CAPABILITY_BLOCKED / PACKAGE_RELEASE=NONE`。
- machine report SHA256=
  `64bea88f857ce13d63b5e8567550fc056f2cab48ca6812b4d83cd497046fa480`；
  task record SHA256=
  `c2968673b231ee84c93ba2136967af49e3228d18adc8a179eb50a90b9b6a55ec`。

## 2026-08-03 serialized Conv node0004 v28 return → v29 DataHub drain

- 被取代的活动 plan SHA256=
  `c494e827f23ee064aec0158504baacd58015de880953078f82d6bed476a6a84d`。
- v28 return 的包/安装/observer/feature identity 与完整性门通过；compile/run=`0/0`，
  simulation 启动但由诊断预算结束，不是 DUT natural terminal；formal D=`0/320`，
  E3/E4/E5=false。
- 128 个 accepted terminal 全部 last_index=`5`、ignore=`0`。MSE4 source
  prepared 16 chunks；DataHub ch0/ch1 各接受 7 address+7 data 且 outstanding=0，
  随后 local write queue full、wr_ready=0、slice_finish=0。
- 首分歧从 D-write ingress 收窄到 DataHub local write queue head→bank/crossbar
  drain；当前不能区分 head X/无 bank match、write arbiter 未呈现 queued write，
  或 bank match 后 ready 不来，不宣称功能 RTL 缺陷。旧 occupancy blocker继续
  `INVALIDATED_NOT_RTL_BUG`。
- fresh v29：
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v29_datahub_drain_diag.zip`，
  bytes=`5833915`，SHA256=
  `4537f98ea18b281aa0f42f8355d7961594bbe0d3cd5991e906d708d9273173bc`；
  sidecar SHA256=
  `a41a2620e0fffeaf17209aeebcc24568aa97d1084e958896b971d97ab4f25128`。
  状态=`PACKAGE_READY_NOT_RUN / DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`。
- final-ZIP audit SHA256=
  `d6002657a83740fd9031d5ef41b7460cdc8a41de07d2ea60a27a0f62c864db64`；
  return report SHA256=
  `e6cffd8d7cdb2d260a78c541c5107580d98e06f175f5e79749c5a64b99477b33`；
  task record SHA256=
  `789223c7fda00fa800163be49057efc15f28582754b75d02e3d6d6f4d9bd3a9a`。
- current continuous-closure/hang-first/default-progress/feature-binding/focused-HDL/
  runner-positive/final-ZIP-audit 规则均被本轮确证，无规则增量；功能 RTL 未改，
  无服务器动作。

## 2026-08-03 QLinearAdd v24 return → split v26 四包发布

- 被取代的活动 plan SHA256=
  `4571f36b55cd8ce8d8fd523ae40c240ed462ba429de550879ca66258660e7b04`。
- v24 B-control compile/simulation=`0/0`、signal=`NONE`、natural terminal=true；
  `op_b_dequant` 用 543,212 active cycles 完成，32 个 qualified windows 全部递增。
  因此旧 v20 停点正式归因 package-local observer 路径，不是冻结 B 配置或功能 RTL。
- v24 返回的 28 项 full-chain D 因 tail 未执行而全为 X，不可评价 mismatch；
  SERVER_RESULT_GATE=false，E3/E4/E5 不增加。
- v25 在交付前因 C/D 非法或缺失内部 preload、compile-stub placeholder 和 validator
  matcher 缺陷隔离。fresh v26 物化四个真实执行范围：
  A=双 dequant，B=独立 relocation 零 spacer，C=累计前缀至 FP32 add 且移除 56 个
  host internal preload，D=冻结六阶段 full chain+28D。
- 四包状态=`A_B_C_D_PACKAGE_READY_NOT_RUN`，推荐顺序=`B→A→C→D`：
  A SHA256=`d9fa3eb8d94ec83382c5be79150a9ea0d9a04903227405d243edb82dcb5e3978`；
  B SHA256=`fb3f248bf4031db9f9d7d8168149ece1a80dbeda50843c8bb20834ab3fc58f05`；
  C SHA256=`e4c16585707b37170d04311f91c038c37b3c95330ffceed17a23687d913f5d50`；
  D SHA256=`b73b13b95f01ea95919cd2eae29415dd04e8a1fff7bc67307099b4c67871d49c`。
- 四包双构建、final-ZIP self-audit、HDL frontend/负控、runner safe-stub、
  wrong identity、EXIT/TERM、stage/event/feature/output 负控均闭合。
- machine report SHA256=
  `04b8e736aae54e0c7372d8d39b4e94aa03ba283babfb75c25b533273a7f47c44`；
  task record SHA256=
  `733ab584bb8c42b19ee6a547be2e72f7e5bbeaed888a6ffb6e4583d62b16ef75`。
- current ordered-stage/minimal-runtime/package-local-HDL/result-conjunction/
  continuous-closure 规则均被确证，无规则增量；功能 RTL 未改，无服务器动作。

## 2026-08-03 Trassic master d0aa87f 同步与功能门复验

- 被取代的活动 plan SHA256=
  `7e576abb1d965450886480eb604dbd887c06a2989d30ac90ec9ec2639ddf1af8`。
- 已通过登录态 GitHub 浏览器确认私有仓库 `xlsjdjdk/Trassic2.0_RTL` 的 `master`
  从 `8f2f3181c1103d705cdf9b9722959e7315f8b875` 前进到
  `d0aa87f682880a260fb792aaac88f70a23aba414`；功能提交为
  `cb11353d4196b4af26aac18b4dcc39ba0027e8bc`。
- GitHub compare 只有两处 RTL 变化。三方门确认本地同步前两文件逐字节等于旧权威，
  没有并行/用户冲突；同步后 `SA_PE_Float_CSA.v` SHA256=
  `429a29a929a508f7562f9c78d4ab2cd4095961296d0e6f65e8419a4444a6145a`，
  `SA_PE_Float_Control.v` SHA256=
  `00107da5137ada324407ba7dbf3e74d6e32428a42631aa23f44c5077ea7b7eeb`，
  均与新上游成员逐字节相同。
- 新提交启用了 `raw_sign XOR signC` 并修正负 INT32 magnitude 的 32-bit 输入，
  但冻结 node0075 `-19+19` 和 Conv node0003 `-5+5` 仍得到
  `0x80000000`。精确抵消时 raw sum 为 0、旧 psum signC 为 1，XOR 符号仍为 1，
  因而形成非规范负零；source sync 不能冒充功能修复。
- sync report SHA256=
  `fb104ea11c9a5ad2d3b83998cec331fb7b0440b781cd2beb690de915ed8c2771`；
  task record SHA256=
  `9ecce80032be2d9573512928d806fecdbdb31caf7344b516ae88c7762b8409d6`。

## 2026-08-03 GAP node0071 v29 return → v30 ARM-ready factor

- v29 return SHA256=
  `2b990565c41da4984bb1293ccbaf135a0f92ccee955e11653f25c60fd0c1a0bd`；
  compile/simulation/runner=`0/125/125`、signal=`INT`、natural terminal=false，
  formal D=`0/48`，E3/E4/E5=false。
- 8/8 MSE0 Buffer0 accepts 到达 prepared write，2/2 ARM accepted reads clear，
  5/5 prepared reads 产生 data_vld；下游 GA 48/48 与 MSE4 12/12 保持无丢失。
- 首分歧更新为 Buffer0 `arm_req=0xff` 持有而复合 ready 在两次接受后为 0。
  当前只能收窄到 selected-bank readiness 或 `nrm2buf_rd_barrier`，未猜测功能修复。
- v29 的稳定 whole-tag level 被错误按周期累计为 15,597,566，已从进度证据中排除；
  v30 以 valid tag bit 修正，并只增加 ready 合取因子的有界观测。
- fresh v30 ZIP SHA256=
  `f0606ebeab52391856a7fb939b6f8c6d02984ae8384117d53d906ba1a9c4a931`，
  状态=`PACKAGE_READY_NOT_RUN / DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`。
- machine report SHA256=
  `9891750ea46fdef880eb687e00cd7bc7720fe74171c31f60a50f66ea129e4d77`；
  task record SHA256=
  `748ebfe2a7fa13ad0ae187305413bc4d1cd2e07954e0d4621e4a023fb134e097`。

## 2026-08-03 serialized Conv node0004 v29 return → v30 MSE4 descriptor

- v29 return SHA256=
  `80bc305d70106952a15887e9e72b275d8572126d5dd46d17087523c37656d069`；
  compile/run=`0/0`，simulation 启动后由诊断预算结束，不是 DUT natural terminal；
  formal D=`0/320`，E3/E4/E5=false。
- 两个 DataHub local channel 均把 7 对 address/data 经 bank crossbar 正式接受并排空，
  因而旧 DataHub queue→bank drain 假设已动态关闭。
- MSE4 有 16 个 prepared group，但只有 14 个 WR_Data_Channel write 与 14 个
  sink accept；最终 prepared_count=32、RD_Buffer_AG queue_count=2/full=1。
  现有 return 不能区分 AG 少发 descriptor、FIFO 丢失/提前 pop，或 descriptor
  已在但 prepared/output-buffer eligibility 阻断。
- fresh v30 只增加 descriptor FIFO 与 prepared-data release 的 qualified 握手诊断。
  ZIP SHA256=
  `0c358f254cac4128a7a320a4201a50f266f1620105fd9b859cf26ac84aa6ad81`，
  状态=`PACKAGE_READY_NOT_RUN / DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`。
- return report SHA256=
  `9adb19b9a64684aa3741f45c879c3e0fbb4a47fdf3b032ba1117362807a19826`；
  release SHA256=
  `6c407bae73c7c864c158b3dee81901cb18276afd915534878d8e584306921f72`；
  task record SHA256=
  `cf84f408b46ac795cb356150aa5a57fd14518c519e746fd71d35e95591c47ce7`。

## 2026-08-03 d0aa87f 下 node0075 与 native four-lane 终止复验

- node0075 fresh 全 recurrence 仍为 planned/enumerated=`8,192,000/8,192,000`、
  negative psum=`4,343,952`、negative→exact-zero=`272`；首例仍为
  `-19+19`，current RTL 返回 `0x80000000`。状态保持
  `HARDWARE_CAPABILITY_BLOCKED / PACKAGE_RELEASE=NONE`，未进入 materializer/E2/构包。
  task record SHA256=
  `aa7193ae031014b13bcf0899a56d9bc66c18911e57a6292d6e903a2e4e02f03a`。
- Conv native-four-lane 只重跑真实 `hwop-0003-00` 必要门，未重跑 53-Conv：
  在已枚举 6,291,456 个 occurrence 后 fail-fast 命中同一
  `-5+5→0`，current RTL 返回 `0x80000000`。状态保持
  `HARDWARE_CAPABILITY_BLOCKED / PACKAGE_RELEASE=NONE`，serialized baseline 未变。
  machine report SHA256=
  `3020f79c46338c8148c8d86f3e481e92fe368f64d703b775cf27090d46634081`；
  task record SHA256=
  `f05c10e557d3f041a4a4ee7a817eb7350df0f6467ac35ca38fabf7528efac10c`。
- 两支均确证现有 INT8-SA/current-identity/fail-fast 规则充分，无公共规则增量。

## 2026-08-04 QLinearAdd split B v26 正式 return 收集

- B relocation source 包由 `PACKAGE_READY_NOT_RUN` 转为已回传、禁止重跑；source ZIP
  SHA256=`fb3f248bf4031db9f9d7d8168149ece1a80dbeda50843c8bb20834ab3fc58f05`。
- 正式 return bytes=`214518`，SHA256=
  `7571a4d58f65406525537fdae29dd3443114bfb7cbe1c3d4168ad9b984c58aa7`；
  相邻 sidecar 缺失仅由用户提交担保替代外部传输收据。
- return 已交给既有 QLinearAdd owner
  `019fa2c0-b647-7a91-93bf-d21a173487e3`，按 RETURN→successor 连续闭环规则分析；
  A/C/D 包继续保持 `PACKAGE_READY_NOT_RUN`。

## 2026-08-04 QLinearAdd split B v26 return 正式闭合

- return 完整性、内部 source/manifest 身份与 exact-set/allowlist 均通过；
  compile/simulation/canonical=`0/0/0`、signal=`NONE`、自然 `$finish`。
- relocation stage 在 `42969` active cycles 完成；GA input/output=`64/64`，
  MSE4 双通道 request/write-data=`4224/4224`，outstanding=`0/0`。
- 28/28 stage-local readback 存在且可解码，B 的局部结构门通过；它们不是 full-chain
  formal D，因此 E3/E4/E5 仍为 false。
- 关闭 `B_QADD_SPLIT_B_RELOCATION_DYNAMIC_COMPLETION_UNPROVEN` 与
  `B_QADD_SPLIT_B_STAGE_LOCAL_28_READBACK_GATE_UNPROVEN`；下一唯一运行身份为
  split A dual-dequant v26，ZIP SHA256=
  `d9fa3eb8d94ec83382c5be79150a9ea0d9a04903227405d243edb82dcb5e3978`。
- machine report SHA256=
  `d65685987a2613b0b4fb41046b6f37e6a2c45cd88aba667503d6525b3376e41d`；
  task record SHA256=
  `d27a714ea765584a9425e53329ed69d08b94600fbc0628d1967ac972f7e61b8c`。
- 本轮确证 no-sidecar 外部传输豁免、局部结果门和禁止过度扩大 E3/E4/E5 的 current
  规则均有效，无公共规则增量。

## 2026-08-04 QLinearAdd split A/C v26 正式 return 收集

- split A dual-dequant return bytes=`23450357`，SHA256=
  `eca32cce8d181167ed15e18358ee7c060a85e42098bc5940e2ad351431806b97`。
- split C FP32-prefix return bytes=`792370`，SHA256=
  `6ed8c25dd3aec5e3caf5322271a113ba6213c47d541975a76f3322e8ce041eaa`。
- 两个 return 均无相邻 sidecar；只按用户提交担保替代外部传输收据，内部 identity、
  exact-set、allowlist、数值门和 stage scope 仍须分别正式核验。
- 两者已同时交给既有 QLinearAdd owner
  `019fa2c0-b647-7a91-93bf-d21a173487e3`；要求分别生成机器报告，严格区分结构完成和
  exact 数值正确。D full-chain v26 在 A/C 裁决完成前保持顺序门。

## 2026-08-04 GAP/serialized Conv v30 正式 return 收集

- GAP v30 return bytes=`355886`，SHA256=
  `b72a3baa7468aa6a09254c90a7d488aa949b37045b1dad83670cc8a9dc2239f6`；
  已交给 GAP owner `019fa366-cb1f-7ae2-880c-f527be0680cd`，继续唯一化
  selected-bank readiness 与 NRM read barrier。
- serialized Conv v30 return bytes=`101341`，SHA256=
  `cad26c94a8f16ee290b8dfd519f4eabad76873b933f3193e281fedd0b061b94f`；
  已交给 serialized Conv owner `019fa2c1-17df-7122-bcbd-a727aaf173f5`，继续唯一化
  MSE4 descriptor 产生、FIFO push/pop 与 prepared/output-buffer eligibility。
- 两份 return 均缺相邻 sidecar，只由用户提交担保替代外部传输收据；两支均按
  RETURN→successor 连续闭环执行，并须在 return 分析及 package 完成时主动通知主线。

## 2026-08-04 GAP v30 return 阶段裁决

- v30 已唯一排除 NRM read barrier：前两次完整行读在 8 个 selected bank ready 且
  barrier=0 时接受；第三次 request/mask=`0xff` 保持时 selected ready=0、barrier=0。
- 最终 `valid_at_addr=0x11111111`，8 个 bank 均仅 byte-lane0 valid；冻结配置声明
  COL 0/1/2/3，停点收窄到 IGA COL 接受→Buffer-AG col/tag→MRM strobe/write→
  memory-return exhaustion。
- 关闭旧 ARM-ready 合取 blocker，打开
  `B_GAP_NODE0071_BUFFER0_SELECTED_BANK_READINESS_PARTIAL_ROW_FILL_PENDING_COL_AG_OR_MRM_STROBE_LEAF`；
  GAP owner 正在构建最窄只读 successor。
- machine report SHA256=
  `0d95f3704436164fe66a172e78ce4a2eaa6125cb7d451664d5899cdd0ed9fe76`；
  E3/E4/E5=false，无公共规则增量。

## 2026-08-04 QLinearAdd split A/C v26 裁决与 C-ingress v28

- A 双 dequant 自然完成，ordered stages=`2/2`，28/28 结构回读存在；结构门通过，
  但未绑定 independent golden，`numeric_mismatch_evaluable=false`，不能宣称数值通过。
- C 前三段完成，FP32-add 启动后在 MSE0/MSE1→Buffer0/2→GA 首次成对输入前超时；
  旧 observer 缺 active MSE1 且 LC binding 不匹配，无法唯一化。
- D full-chain 继续冻结；fresh C-ingress v28 只补 paired ingress qualified 观测，
  ZIP SHA256=`f552f2a24ae62b1e4e11c1a69ddff6663ffa2ea4fa177b923d0298c15a739f50`，
  状态=`PACKAGE_READY_NOT_RUN`。
- A/C report SHA256=
  `13a4e859a33a65ee85661161d7973ac5e52f64efbf06ebafb5486dd66005709a` /
  `f1e1053c1e4ac58bfd5975f516ac20ed2bccfcede41ac2bef5692fc2534f64f5`；
  v28 audit/release SHA256=
  `6cdc70fecb3473c8fbfb35dfcc6ba802a695ac50a010a15a2dcf3a8fa4b8bca2` /
  `60f70fe41b869ddca7ac62ace71193e4fb9a538485273154c447edd3e3701574`。
- current 规则正确强制结构/数值分离、paired progress 与 fresh identity，无公共规则增量。

## 2026-08-04 serialized Conv v30 裁决与 v32 successor

- v30 证明 14 个已生成 descriptor 全部守恒通过 FIFO、两路 memory request、
  prepared read 与交替 output buffer；最后两个 prepared group 未进入 descriptor 生成。
- 停点收窄到 Memory_AG_Idx_Queue accept/match/push/pop→WR_Memory_AG
  bias/transaction/finish/descriptor；不宣称功能 RTL 缺陷。
- v31 因 final audit 缺 current common/NDP receipt 被隔离；fresh v32 ZIP SHA256=
  `87a3e3474c3c1fbd28a8a4220919a8249c310c915da87bba58c28a7e6d8eb835`，
  状态=`PACKAGE_READY_NOT_RUN / DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`。
- v32 final audit/release/task record SHA256=
  `d223e77f76676a0658d0d41c1dc7700f5a89dc201134cbc53a8cf66ef6e64e63` /
  `a1dd8e5129e852c218ed55e0f50d42b1ee35d88a308a2ef9fa66f99db173545b` /
  `6054ce25bf25731d159079224623e33019244518d28a2f46b73b493d4a4175c1`。
- current final-ZIP audit 规则实际隔离 v31 并放行 v32，无公共规则增量。

## 2026-08-04 GAP v32 外部收据校正

- GAP v32 ZIP/sidecar、运行身份、RETURN_ANALYSIS、LPG/FD/root cause、blocker 与命令
  全部不变；ZIP SHA256 仍为
  `c974125f0b3e913f733ad4c2341b922ea3551a62144b1062c6dd433d82e369a1`。
- schema/test_id 规范化后，current final audit SHA256=
  `2ccd9a92c4a1088d74b60326908b85b401216698044f47ed111a670bbb8fc0e5`，
  signal-stub SHA256=
  `a16f4ae4688b971ec08a5701b9160f8d7087ee2741607c84bdb2bde725907b08`。
- current machine report/task record SHA256=
  `27c2728f2912a170762a6d6817561b25cf4b87ee908a0c237993ca5510a895fc` /
  `687d57fdd46f6b02382dae2b5b6820fa37c387a0c553eb879b1b47f502618784`；
  仅旧外部收据哈希被取代。

## 2026-08-04 serialized Conv v32 正式 return 收集

- v32 return bytes=`102741`，SHA256=
  `757c64ad8232e6dbad311eb29864c4c20f692c7585eec7e8d6156bbc100bfbed`；
  无相邻 sidecar，只由用户提交担保替代外部传输收据。
- 冻结 source ZIP SHA256=
  `87a3e3474c3c1fbd28a8a4220919a8249c310c915da87bba58c28a7e6d8eb835`，
  已消费且禁止重跑。
- return 已交给 serialized Conv owner
  `019fa2c1-17df-7122-bcbd-a727aaf173f5`，按 Memory_AG_Idx_Queue→WR_Memory_AG
  descriptor 唯一边界连续闭环；旧 occupancy 误判继续禁止复活。

## 2026-08-04 serialized Conv v32 return 阶段裁决

- Memory_AG_Idx_Queue input1 仅接受 7 个 fresh buffer index；全部 7 个均完整经过
  match/push/pop、WR_AG bias/transaction/finish，并各生成 2 个 descriptor，共 14 个。
- queue 与 WR_AG 最终空闲，排除 accepted tuple 之后的 queue/WR_AG/descriptor 丢失。
- 首个缺口前移为第 8 个 physical PE7 buffer-index output 未到 MSE4 input1 accept；
  仍需区分 LC18 未发、PE7 未接/未发，或 PE7→MSE4 未接。
- 打开
  `B_CONV_NODE0004_PHYSICAL_LC18_PE7_TO_MSE4_EIGHTH_BUFFER_INDEX_ACCEPT_UNOBSERVED`；
  v33 窄诊断 successor 正在构建，不改 end/keep/config/RTL。
- return report SHA256=
  `a1566c23a2399206f94e468d4913d7752a6e0665fa84f48ec68c1bb88a1799c8`；
  E3/E4/E5=false。

## 2026-08-04 serialized Conv v33 successor

- v32 已证明 7 个进入 MSE4 的 buffer index 全部守恒生成 14 个 descriptor；
  首个缺口为第 8 个 physical LC18→PE7→MSE4 input1 accept 未发生。
- v33 只增加 physical LC17/LC18/PE7→MSE4 qualified 边界观测，不改
  end/keep/config/workload/timeout/backpressure/功能 RTL。
- v33 ZIP SHA256=
  `5094fc3e01a04c1931b81c4db3a67bf2f6b82f424124d0311866d03004997c90`，
  状态=`PACKAGE_READY_NOT_RUN / DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`。
- scope/runner/final-audit/release/task SHA256=
  `1a832a5d1feb921f7e6392cee151cef9b1d75ff41ef79493d3dcc064ada18e46` /
  `72a82d83e7825b99c552f4119db0ca53649ecc5eb7138f59b43dba1cf417c451` /
  `8882b55f9b3840b6ff6ab11a265ad9d61c7c01c0ba8d1e5e286b6441b409714e` /
  `828ba157c597c5ca4308d4390025e3f5450e8d1724b0d47ed74fcc476ce6d83b` /
  `9d1786b342d6c986332521c2ce1a3995551e92c9f945a36f414788804593a9e9`。
- current rules sufficient；旧 occupancy 误判继续保持 INVALIDATED_NOT_RTL_BUG。

## 2026-08-04 node0075 materializer/E2 旧活动状态归档

- 旧活动状态 `ARITHMETIC_GATE_CLOSED / MATERIALIZER_CONFIG_E2_RUNNING` 已由
  node0075 owner 的 df23e4d 完成收据取代。
- handler/materializer、最小 8-pass A reload 与 config-bound compositional E2
  已闭合；旧 blocker `B_MATMUL_NODE0075_FINAL_A_CONSUMER_MATERIALIZER_MISSING`
  不再是 current。
- current 首个阻塞改为 fresh-memory 执行流缺少 node0071 true-producer prefix 与
  producer-final→node0075-first-read visibility barrier；详情见
  `.agents/task_records/20260804_node0075_df23e4d_compositional_e2_server_barrier_blocker.md`。

## 2026-08-04 serialized Conv v33 后继构建状态归档

- 旧活动状态 `RETURN_ANALYSIS_COMPLETE / HIGH_INFORMATION_SUCCESSOR_BUILDING`
  已由 v35 正式包收据取代。
- v34 因 package 内 generation-read receipt 陈旧被 final audit 隔离；唯一 current
  runnable identity 改为 `r5_n4_hw_v35_rowlc4_bufag_diag`。
- v33 的 LPG/FD 与
  `B_CONV_NODE0004_LC18_TO_ROW_LC4_BUFFER5_FINAL_FLUSH_PATH_UNOBSERVED`
  保持 current；v35 只增加五类候选×观察矩阵，不是功能修复。

## 2026-08-04 Conv native-four-lane W3/E2 复验状态归档

- 旧活动状态 `RTL_REPAIR_DIRECTED_PASS / OWNER_W3_E2_REVALIDATION_RUNNING`
  已被 df23e4d performance package 完成收据取代。
- `B_CONV_NATIVE_FOUR_LANE_CURRENT_IDENTITY_W3_AND_E2_PENDING` 已关闭；
  current 只保留服务器 natural terminal、320 formal D 与 production RTL identity 三门。
- serialized single-nonzero-product correctness baseline 保持独立，不因 native
  performance candidate 的本地 E2 或包完成而宣称通过。

## 2026-08-04 Conv native-four-lane v1 首次服务器 preflight 状态归档

- 旧活动状态 `PACKAGE_READY_NOT_RUN / DF23E4D_PERF_V1` 已被首次现场 preflight
  收据取代；canonical ZIP 字节和本地放行结论没有失效。
- 现场 extraction tree 同时包含合法顶层包内容与一个同名嵌套副本，exact-set 在
  compile 前 fail closed；dynamic attempt=`0`。
- current 状态改为 `RETRY_READY_NO_DYNAMIC_ATTEMPT / FRESH_EXTRACTION_REQUIRED`；
  不生成 successor，不删除服务器目录，使用空 extraction parent 与 fresh namespace 重试。

## 2026-08-04 Conv native-four-lane v1 重试状态由 p4 取代

- v1 首次现场树因同名嵌套副本触发 extra-member preflight；后续用户提交的不完整
  extraction 又缺少三个 runtime member。两次都没有形成有效 workload/RTL 动态结论。
- p2/p3 是失败且未发布的本地候选；均不得运行。
- fresh p4 以短 identity `r5_n4_df23e4d_p4` 重新封装冻结 v1/E2/df23e4d 内容，
  补齐 exact-set，并加入 current internal-path budget 门；ZIP SHA256=
  `c8d42f979b07468e869d077755f987c09c04d017cd1bc6ab50a71a8ee1d0204e`。
- v1 继续作为 source/E2 历史身份保留，但不再是 runnable identity；活动状态改为
  `PACKAGE_READY_NOT_RUN / DF23E4D_P4`。

## 2026-08-04 提交前活动 plan 再压缩

- 按“只保留最新状态和最新短期计划”的文件职责，将 383 行活动 plan 压缩为 145 行；
  当前 GAP v33、serialized Conv v35、QAdd v29、native Conv p4 与 node0075
  producer/barrier 边界保持不变。
- 压缩前 plan 精确快照：
  `.agents/history/plan_pre_checkpoint_compaction_20260804.md`，
  SHA256=`82dd50270bf697954c7b7a054fe7ce47d3ac62fdf2993b7bb1fa20d0b7c2b82d`。
- 同时保存未改写的稳定入口快照：
  `.agents/history/agent_pre_checkpoint_compaction_20260804.md`，
  SHA256=`32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f`。
- 活动 plan 不再携带旧 `probe_v7` 收据；详细 return、包审计与历史过程继续由
  task record、机器报告和上述快照承载。
