# ResNet50 INT8 压缩历史与证据台账

最后更新：2026-07-21（v15～v17均已撤权并清理生成制品；v18真实run1停在首个accumulate并已撤权；v19完成新数值身份和两轮本地审计，是当前唯一允许上传的服务器包；G6/G8仍为false）

本文件只用于追溯。当前任务和命令看`.agents/plan.md`，稳定入口看`.agents/agent.md`；`.agents/rules/`保存从活动实现和实证提炼的配置/服务器检查清单，不是独立事实源。历史细节优先通过版本表、关键身份和archive引用压缩；本文件必须保持少于1000行。

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
| v19当前typed request | `artifacts/w5/hwop-0004-00/v19/execplan_request.json`，SHA=`105f2bc78556f7ae8a33cd2c20bb3b6e63a4acc40e1138ba90a125b12a577e06` | bias tile修复后的全新数值/硬件身份 |
| v19当前candidate/preflight/freeze | candidate ID=`d5f6af19413919a72d761f99b61d35afdee5278e172a363f28055d937dd37898`；preflight SHA=`98febe58038352eefff14b2c88c19e332cdf3fdcf1531a16e91137c5ab0debbc`；freeze ID=`71686cf225194fbe6f9a0db73e7adf515a02ce252598ac58f6e5090793470b27` | A/B、parsed/mapping/placement和Golden/NDP P/D通过；512文件freeze |
| v19当前输入ZIP | `artifacts/w5/hwop-0004-00/v19/server_overlay.zip`；SHA=`0874e8eeb8495ca46e3ddda54e1273c05e5c9a10b78c468e4584ba33398f06b2`；runner SHA=`1ae95b832c4273513c152ae453164346563fb2064c15c23255da44b5a7d9d8ee` | Round 1/2本地PASS；只允许先执行run1，服务器自然完成和三方P/D尚无 |

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

### 2.6 v18真实停滞、bias修复与v19本地闭环（2026-07-21）

- v18真实run1完成434个preload后进入首个accumulate，fixed observer长期停在`0/5`。手工终止返回`sim_results_v18_run1.zip`（86,794 B，SHA=`2f33f34f626b2b1fe71502da5fe10e87eb67fb21d3a13404c528fbc130dbfeca`）和补充诊断`v18_run1_deadlock_extra_1784611151.zip`（217,860 B，SHA=`6b833a69ae92e9fb9c9147d783d01ece803e7c4f98c3c0d62721b8824c574dc7`）均不是自然完成证据。
- RTL/encoder静态反查确认：v18 stream3只按两个Kblock触发，buffer4 lifetime=1只产生一次SA读取；`SA_PE_Outbuffer`每个Q8×K8 tile需要四次bias握手初始化完整16项psum组。生成器改为LC10 Kblock→LC11 H→LC12 Qblock分支、stream3 stride=`[32,0,0]`、GROUP2同源且buffer4 lifetime=4。
- 原生server-profile prepare工具在配置变化时只从typed semantic evidence刷新config SHA/connection count和mapping seed；缺证据即失败。DeepSeek默认入口未改。v19 candidate ID=`d5f6af19413919a72d761f99b61d35afdee5278e172a363f28055d937dd37898`，manifest SHA=`5146329288431fb970b26e35b70a93c2955515753430026327f36d76fe37589f`，validation SHA=`7ddd85d4b3afa9ce08385d588031ff9881fb1a79e7982a753d97a1db9dcc0764`。
- v19 accumulate JSON SHA=`f26a3346859601055abc9cb88dd0b7c3650e5fcc4fae6d1f85d2562aba0ad8ed`；正式码流为29行×128-bit，LF规范化逻辑SHA=`7d85938215a1d5a5622c38938b5adb64b982c631170604a4ba8285fb5397b255`。config-bound preflight SHA=`98febe58038352eefff14b2c88c19e332cdf3fdcf1531a16e91137c5ab0debbc`且P/D mismatch=0；freeze ID=`71686cf225194fbe6f9a0db73e7adf515a02ce252598ac58f6e5090793470b27`。
- v19 package manifest SHA=`5d118970d4831074da8c8dfee57abdadb48d6bc402bf4aea93864b5dcffef636`；schema 0.3不变性报告SHA=`08a6457ee3c8f8f0fa179feb06f81f3df22b6009ea6be771571efcdd303ad1de`证明264个数值payload/runtime文件保持不变，同时明确允许配置/bitstream/execplan/身份文件变化，不把v19冒充v18。
- v19最终runner SHA=`1ae95b832c4273513c152ae453164346563fb2064c15c23255da44b5a7d9d8ee`；ZIP为2,989,053字节、289个entry、0 HDL，SHA=`0874e8eeb8495ca46e3ddda54e1273c05e5c9a10b78c468e4584ba33398f06b2`。Round 1报告SHA=`164a13a7b8fda7dd0e09799e9d3d4e441ec407658a8280a8db516ef48f5df6b8`，20个行为用例PASS；Round 2报告SHA=`eec85fbd1cc2a5fe98e57a028108c1dac73b8f52545f26607c562670f4683dc2`，最终ZIP独立解包审计PASS。
- 本地回归额外修复了“current overlay/package测试仍硬编码v18/v14”的口径漂移，并以v19 request/freeze重新完成28-bank端到端重建（492秒）和当前overlay行为测试。v19当前只达到`overlay_ready`，G6/G8仍为false。
- v19正式链闭合后精确删除9个失败/探针生成目录（`v19-work`、首个失败server-profile/candidate及6个手工bias探针），共78个文件、4,101,888字节；正式`server_profile_input_02`、`encoder_candidate_native_02`、preflight、freeze、package、overlay、ZIP和两轮报告均保留且身份未变。

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
| v19 | 否，当前唯一候选 | bias tile修复、新数值身份、config-bound P/D、package和两轮本地审计通过 | 允许先上传并执行run1；run1返回验收通过后才能执行run2；G6/G8=false |

## 4. 原始服务器结果ZIP台账

以下文件是本地唯一长期运行证据；不得改写或与完整展开目录并存。

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
