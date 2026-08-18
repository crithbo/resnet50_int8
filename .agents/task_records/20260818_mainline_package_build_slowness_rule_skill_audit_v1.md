# 2026-08-18 主线构包慢与多次失败：规则/硬门 vs 子代理/Skill 审计

## 裁决

结论为混合原因，不是二选一。

- 临时子代理没有稳定消费current family owner上下文和项目Skill，造成授权丢失、旧方法复用、重复重建；按用户指令，本轮不改Skill位置、子代理或owner路由。
- 独立v103/v78 final-ZIP审计同时证明共享硬门漏检跨成员和发布时序矛盾，因此本轮只修该部分。

## 规则分类

1. v103第一份return要求包含只能在发布后产生的durable/cleanup receipt，并在return发布后才验证finalization guard：`RULE_SEMANTIC_OMISSION`。在既有return规则下窄幅补齐prepublication/postpublication phase语义，不新增公共ID。
2. v78顶层ready但嵌套final audit仍pending、selected/absolute wall跨成员冲突、held level被计为progress：`IMPLEMENTATION_ESCAPE`。现有规则已覆盖最终状态与qualified progress，不追加同义规则；新增聚合final-ZIP硬门。

两份machine adjudication均通过`tools/validate_rule_maintenance_incident_adjudication.py`。

## 实现

新增`release_cross_member_temporal_consistency_final_zip`共享门：

- release-critical嵌套status必须terminal；
- selected与absolute wall跨package/runtime/finalizer逐pointer一致，且absolute保持86400；
- 每个required in-ZIP member有唯一exact producer/basename；
- guard complete → return publish → durable receipt → cleanup receipt顺序唯一；
- publish后产生的receipt只能为外部immutable sidecar或不同basename后续return；
- progress event绑定actual source span和qualifier/state memory，held-level replay不得反复计progress。

共享入口：`tools/validate_server_release_consistency.py`；schema、dispatch、fixture、tests均同批落盘。现有服务器包规则和生成前索引只做窄幅语义合并，无新公共rule ID。

## 验证

- focused：10/10 PASS；
- release/runtime/TB-VCD/post-sim/runner核心相关：84/84 PASS；含active registry、mandatory compaction与pipeline的扩展回归：115/115 PASS；
- incident adjudication：2/2 PASS；
- active rule audit：14/14 active、164 definitions、0 duplicate/error/warning；
- py_compile、JSON parse、diff-check：PASS。

## 边界

本轮未修改或重建current family ZIP，未改plan/owner registry/storage/RTL/config/numeric/workload/golden，未执行server/upload/lease。新门只建议主线同步后约束next fresh。

机器报告：`outputs/mainline_package_build_slowness_rule_skill_audit_v1/report.json`。
