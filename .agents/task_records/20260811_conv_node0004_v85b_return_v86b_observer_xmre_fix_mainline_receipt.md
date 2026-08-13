# Conv node0004 serialized v85b return / v86b observer XMRE fix 主线验收

日期：2026-08-11  
role：`family.conv.serialized`  
owner：`019ff02d-901b-7f70-a9da-f54e268b5bbe` / owner epoch `2`  
mainline：`019ff027-e7db-72a3-b282-cfad8708da05` / registry epoch `6`

## 1. 上一版本进展与当前版本目的

- v84b 已到达 production compile，exit=`2`；simulation 未启动，natural terminal=false，
  formal D=`0/320`，E3/E4/E5=false。其回传保留了 package/execution identity，但缺 actual
  compile argv、selected source identity、bounded compile log 与 first-error。
- v85b 的目的，是回收七项 bootstrap-safe compile-rootcause 文件并唯一定位 production
  compile exit `2`；该目的已完成。
- v86b 的目的，是只修已证实的 package-local observer XMRE 和相关首错/source binding，
  重新验证 production compile；它不宣称动态目标已通过。

## 2. Formal return 分析

正式 return：
`C:/Users/15383/Downloads/r5_n4_hw_v85b_compile_rootcause_r1786447856031491701_1116783_return.zip`，
bytes=`60848`，SHA-256=`a2de42f82e288f5c0739649bbeb3995446d644ff2950ff2c18f9f1ac2a3ea59d`。

分析：`outputs/conv_node0004_v85b_return_analysis/return_analysis.json`，bytes=`6776`，
SHA-256=`e276f4437c4f6c4f4be3f2cb1608a295f865f9504bd3ef0b951f72a5949ad837`。

integrity、source manifest、exact-set、逐文件收据与七项 core evidence 全部 PASS。正式状态为
compile=`2`、run=`125`、signal=`NONE`、simulation_started=false。

根因裁定为 `PACKAGE_LOCAL_OBSERVER_HIERARCHY_COMPILE_DEFECT`，不是 functional RTL：生产
VCS 在 package-local `tb_probe/native_return_observer.svh:4816` 与 `:4821` 报出两个 XMRE，
两处均解引用 channels 8/9 的 `arb_req_ready[0]`。optional source-bound plugin 缺 `sim.log`
是 compile failure 的下游结果。v85b 的 first-error selector 错把 warning prose 当首错，但 bounded
tail 保留了两个精确 XMRE。

## 3. Fresh successor

status=`PACKAGE_READY_NOT_RUN`  
package=`r5_n4_hw_v86b_observer_xmre_fix`  
pickup=`artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_hw_v86b_observer_xmre_fix.zip`  
bytes=`5274779`  
SHA-256=`70deb1846226b353a22916891c2ce7de18ff32cd748b4206d4495c38ba929865`

唯一命令：

```text
bash r5_n4_hw_v86b_observer_xmre_fix/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x
```

预期 return：
`/home/panqs/ndp/simresult/r5_n4_hw_v86b_observer_xmre_fix_r<UTC-ns>_<pid>_return.zip`。

changed surface 仅为 fresh identity、两个 package-local observer XMR、anchored first-error
优先级、transitive native observer compile-source binding 与对应 root/pre/post/gate receipts。
config、numeric、workload、functional RTL 均冻结。

## 4. Gates 与主线复核

- shared prebuild aggregate、runner definition-before-use、七项 compile-core return：PASS；
- source-bound exact-ZIP、post-sim 四场景、NDP root exact-set 正负控：PASS；
- scoped observer/first-error negatives：PASS；
- waveform=`not_applicable`，VCD/FSDB 均关闭；
- final-ZIP audit：
  `artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/conv_serialized_node0004/r5_n4_hw_v86b_observer_xmre_fix/r5_n4_hw_v86b_observer_xmre_fix.final_zip_audit.json`，
  bytes=`2794`，SHA-256=`eaf4c0f9eb636e67830187606a047725d882bc8493349ea9c1e5c37620421042`，
  errors=`[]`、self-audit PASS；
- first-fresh exact ZIP：同目录 `r5_n4_hw_v86b_observer_xmre_fix.first_fresh.json`，
  bytes=`2286`，SHA-256=`8b0907b3f33c4cf311bfdce50a6f5cfaf143defccf0b47743c23942c0af1a331`，
  pass=true、upload_authorized=true；
- runner resilience unittest 6/6 PASS；两个 optional schema unittest 因 bundled Python 缺
  `jsonschema` 未导入，但 exact final-ZIP validator 已由 build 直接执行并 PASS，未安装依赖。

主线复核 return analysis、mainline receipt、pending ZIP、final/first-fresh receipts 的机器身份与
family 回执一致；pending exact-set 中 v86b 为唯一 serialized ZIP。

## 5. Storage、blocker 与边界

storage 原子轮转完成：v85b→tested，v86b→唯一 serialized pending；family 回执时全局
pending/tested/superseded=`3/112/41`，index bytes=`381402`，
SHA-256=`be888674b9a347f6cc776305d9b11971305ae6be341da1d8811f319eca113d9f`。

已关闭：compile root 未观测、compile log 缺失、package-local `arb_req_ready` XMRE、first-error
warning false-positive。保留：ACK output-vs-inline RHS 因果差异、natural terminal、formal D
`320/320`、E3/E4/E5。

server_authorized=false；未 upload/run/lease。v86b 的本地工作流只闭合到
`PACKAGE_READY_NOT_RUN`，production compile success 与全部动态目标仍未证明。

`RULE_CONFIRMATION`：
`CDA-SERVER-COMPILEFAIL-CORE-RETURN-ROOT-CAUSE-001`、return manifest allowlist、current root
top-level 与 first-fresh 规则均由本轮证据确证。first-error 问题属于实现局部缺陷，不提 public
rule delta。

conflicts=`[]`
