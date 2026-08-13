# GAP v54 diagnostic multiclass edge no-loss 公共门裁决与实现

- 日期：2026-08-08
- 专项 task：`019fd276-14c5-7800-94db-87ebfb9ce632`
- 唯一回传主线：`019fbec2-fe93-7e03-9314-cff6f222f33d`
- 状态：`RULE_DELTA_IMPLEMENTED_SHARED_GATE_PASS`
- 分类：`PACKAGE_LOCAL_DIAGNOSTIC_MULTICLASS_EDGE_LOSS`
- package/server/RTL/config/numeric/plan action：`NONE`

## 1. current只读收据

- `.agents/agent.md` bytes=13174 SHA256=`32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f`
- `.agents/rules/生成前必读索引.md` mainline baseline bytes=21270 SHA256=`7948172704d0b2362066038d8e19faf2a08b20ed4e06978859145d5252913668`
- `.agents/rules/整网测试收敛优化专项规则.md` bytes=13901 SHA256=`e52ab12c78edca3ada0eabf26a323b3da7a9fb6dc0bb07dab594793eee8e87ff`
- `.agents/plan.md` mutable provenance bytes=44636 SHA256=`4f04b3e207a5fd200b6bbc6e66b6c0a312d1e4f24317cd9266d31d2018aecc13`
- `.agents/rules/服务器测试包生成规则.md` mainline baseline bytes=116695 SHA256=`2b45df0cc39821627abad4504b5e6829f1202b24dfdfa931dcf52352b399c8fe`
- `.agents/rules/算子配置规则.md` bytes=37680 SHA256=`dc5243226bacde799b368d37fb9eb656e6b7e3d33a0a2932ae72ab35415ae3e1`

专项worktree规则含此前公共实现但不覆盖mainline并行增量；规则回传固定为
`NARROW_SEMANTIC_MERGE_DO_NOT_OVERWRITE_MAINLINE_PARALLEL_DELTA`。共享schema/tool/test/fixtures/
reports可按exact SHA机械同步。

## 2. direct evidence

- v54 source bytes=1986492 SHA256=`131e9de37698c8e0470db0c42120c0b2d793c84ce0c2ee62a02eb24cefbd87c9`
- formal return bytes=188181 SHA256=`5bbe79edd2a8cfcec03b63207920f8c73166dd78fd57066e30360230c9ba9e5b`
- owner analysis SHA256=`ce469ea17b409cae5f8e51eb18db2fd776c4077652ef0ca009fd42474d5640d9`
- exact observer `tb_probe/native_return_observer.svh` bytes=479523 SHA256=`ddc50b15fecb7e2bc04fd51389284978f5d7cc83e6b33c450438aaaee5573f0d` span=6886-6980。
- exact parser `package_tools/gap_node0071_remote_owner_false_accept_decision.py` bytes=6056 SHA256=`0434b84c1828a68be36d1734a3bf13b54a3a5e43ef9224113a49a66b313c27d9` span=5-12。
- event priority为`pc > vc > fc`，但每个sample末无条件推进progress/violation/factor三个snapshot。
- returned counts：QUALIFIED=20、VIOLATION=0、FACTOR=1、HEARTBEAT=19。
- exact raw sticky violation masks保留`0xfffe`；旧parser只在`VIOLATION_EDGE`label下消费violation，
  所以parser masks全零。sticky semantic replay SHA256=`8f39a1640e33ae2b84f0fec18c96bf75868a8c84d520f952caf3c53f6bcebb77`。

## 3. 裁决

现有predicate trace规则要求同时事件组合，但没有规定priority arbiter未输出class的snapshot所有权；
budget隔离规则不处理class丢失；exact-format规则只处理字节格式，不处理parser按event label漏消费
同record sticky class。故这是窄幅非同义规则缺口。

新增`CDA-SERVER-DIAGNOSTIC-MULTICLASS-EDGE-NO-LOSS-001`，合法闭合二选一：

1. `EMITTED_CLASS_ONLY`：只有实际发出/进入pending的class推进自己的snapshot；
2. `MONOTONIC_STICKY_ALL_REQUIRED_CLASSES_EVERY_RECORD`：允许全部snapshot推进，但parser必须从
   每条exact record消费所有required单调sticky class。

两条路径都必须保持只有`QUALIFIED_EDGE`计progress；violation/factor/sticky state不计progress。
本门只在class参与canonical/progress/first-divergence/required return时blocking，optional class
固定record-only。

## 4. exact implementation receipts

- specialized server rule bytes=108040 SHA256=`d4b542b0978e9f467807a731cc3710befb2a542957b3a13ef8e48a36cb769ed8`
- specialized generation index bytes=17566 SHA256=`d98d6f3ee4c36ff68e7d5d8d3ca4530a3012d91c089163dd18bf278a7538b9ba`
- schema `schemas/server_diagnostic_multiclass_edge_trace_v1.schema.json` bytes=4371 SHA256=`8f0d83cc96b6eb4810da18565425877b69c5a49e897d1c896e6011b21ec17e18`
- shared validator bytes=69239 SHA256=`74da73d1193f1451d9b4ba6ac0d05f97c60f39e1ab51f44bc505b8504cf64629`
- shared tests bytes=23046 SHA256=`88c59658e60200633bd6fc7b32b4f0bef893a19687300dc705b8b50eba069dec`
- per-class fixture bytes=2087 SHA256=`d737a507be32788ce895a794cdb8a67fada530520c5669a82c13101434bbbc26`
- sticky-all fixture bytes=2014 SHA256=`5f8d690ca39b355883675b11636a73234db8fddb0761ff4b3b40a718c6329166`
- v54 negative fixture bytes=1990 SHA256=`a95ce41856aa87950ee4897efbe2d9bb5785345c04721c4acb10618bd2b629b4`
- per-class report bytes=6320 SHA256=`5e81e2bb48ab617b7b71f5607a06cc8f146c7c1ba9b0e6ecc2642ff45fcdaa8a`
- sticky-all report bytes=4779 SHA256=`7ac5c56216ac5ad77764ea438bf451def0653d4b2d6eb414fc01564581e06d1c`
- v54 negative report bytes=4886 SHA256=`7634f830294d74c20dc7b1d504cdf8a34998c4ae194a09838a186fe1c248bf3b`
- adjudication report `artifacts/operator_config_validation/r5-diagnostic-multiclass-edge-no-loss-v1/report.json` bytes=7773 SHA256=`3bc85af88520fc750c98717c0469d919fe4462ed8478bd4a1dbcb7f891133896`

## 5. validation

- py_compile PASS；shared tests `34/34 PASS`；git diff-check PASS。
- per-class正控：同sample三类改变；输出顺序QUALIFIED→VIOLATION→FACTOR；3/3 covered；高优先级
  budget耗尽后低类仍保留；progress count=1。
- sticky-all正控：只输出QUALIFIED label，但parser从同record恢复3/3 class；progress count=1。
- v54历史负控：expected exit1，covered=1/3，missing VIOLATION/FACTOR。
- sticky回退、observer SHA漂移、non-progress计progress均fail closed。

## 6. frozen boundary

v54功能裁决保持`WAIT_RTL_FIX`；根因为
`FUNCTIONAL_RTL_SLICE2HUB_REMOTE_WDATA_READY_NOT_QUALIFIED_BY_PRIORITY_OWNER`。硬件修改被用户禁止，
GAP pending为空，successor=`NONE`。本轮不重建/生成package，不执行服务器，不修改RTL/config/
numeric/workload/plan，不改变natural terminal、正式D或E3/E4/E5结论。
