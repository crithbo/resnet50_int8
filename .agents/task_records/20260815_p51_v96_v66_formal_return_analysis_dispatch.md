# p51 / v96 / v66 正式 return 分析派发

日期：2026-08-15  
主线角色：`mainline.control`  
registry epoch：`6`

用户返回三份 exact formal return，已分别派发至原 family owner：

- Serialized Conv v96：
  `C:/Users/15383/Downloads/r5_n4_hw_v96b_tbvcd_memtuple_r1786770065727401255_2781777_return.zip`
  bytes=`134063`，SHA256=`16186084172a1c731b4db4ef625768e71218b7168b3a5fd71dfe541f119882fe`。
- Native Conv p51：
  `C:/Users/15383/Downloads/r5_n4_0cc_p51_metaidxcone_r1786770085722684994_2783486_return.zip`
  bytes=`37802431`，SHA256=`ad29550482d561d69ed3be5b14f16669539e7cf381e49de435b32d84aec9369f`。
- QAdd v66：
  `C:/Users/15383/Downloads/r5_qadd_n7_tailround_lanephase_v66_cfg42_r1786770100877714671_2785121_return.zip`
  bytes=`92180270`，SHA256=`9da70fe32efcdaa00c50945f9a2f9985f8ccc9ed08c98d68d6cc507455194203`。

派发要求：严格 bounded streaming/resume；直接对齐配置、actual compiled RTL 与动态证据；运行成功但未唯一
闭合时执行 `RULE_GAP_AUDIT`，package-local 失败则构建 fresh 修复包。三个 family 在正式回执前不得调用
storage manager；主线后续只按单写者顺序发布/退休。无 upload、lease、connect、server run 或功能面改动授权。
