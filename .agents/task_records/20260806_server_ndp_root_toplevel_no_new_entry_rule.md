# 2026-08-06 NDP_copy 根目录一级零新增规则

## 用户语义

服务器测试包运行时：

- 不得在 `/home/panqs/ndp/NDP_copy0x/` 根目录直接新增文件或文件夹；
- 可以在运行前已经存在的根内文件夹中存放本次运行产物，并在其中建立隔离
  package/attempt 子目录；
- return ZIP/sidecar 仍只发布到服务器 `/home/panqs/ndp/simresult`。

先前草拟的“整个 NDP_copy 只读且必须使用固定 simwork”解释过严，已在同一轮撤回；最终
规则中不存在该旧 ID 或 `/home/panqs/ndp/simwork` 强制要求。

## 规则

新增：

`CDA-SERVER-NDP-ROOT-TOPLEVEL-NO-NEW-ENTRY-001`

runner 必须：

1. 写操作前记录根目录直接子项的名称/类型排序 exact-set；
2. 每个根内写目标绑定一个 preflight 已存在的一级父目录；
3. 禁止直接创建根级 `run_*`、`evidence_*`、return、临时文件或其它新 basename；
4. finalizer 再次记录 exact-set，任何新增/删除/改名/类型变化均 fail closed；
5. 本机用隔离 stub root 验证 normal/compile-fail/INT/TERM，并对根级目录、根级文件、
   父目录缺失和未阻断漂移做负控。

## 当前 pending 只读盘点

- native p11f、serialized v51：production runner 的显式工作目录位于 NDP 根外，未发现
  直接根级 `mkdir`，但它们在本规则发布前冻结，尚无本门要求的 pre/post exact-set 收据；
- GAP v46：显式创建根级 `run_<id>`、`evidence_<id>`，不满足本门；
- QAdd v36：显式创建根级 `run_<id>`、`evidence_<id>`、`<id>_return`，不满足本门。

用户随后明确要求本轮立即遵守。上述四个 current pending 在具备本门 exact
final-runner pre/post receipt 前全部转为
`PACKAGE_HELD_NDP_ROOT_TOPLEVEL_GATE_REQUIRED`，不得继续人工取用或服务器运行。
owner 只能对无需改 ZIP 的等价机制做 content-neutral revalidation；否则必须生成
fresh runner-only identity，并冻结 config/workload/numeric/golden/timeout/RTL。

## 修改收据

- `.agents/rules/服务器测试包生成规则.md`
  - bytes: 92749
  - SHA256: `3866298fe858c27a89478b0331121c577244ffc6d11b5cc570dae587c4c9ec67`
- `.agents/rules/生成前必读索引.md`
  - bytes: 14654
  - SHA256: `1c4ae30df12efe27ec68c1289eefd933ed9ee3e08c426a7a7a2f19abc957c37b`

`git diff --check` 通过；新规则 ID 唯一，旧过严规则 ID 和强制 `simwork` 路径均为 0 次。

## 边界

没有修改或生成 ZIP、sidecar、mapping、bitstream、execplan、SCA；没有服务器运行、上传
或 lease；没有修改 functional RTL、ISA、hardware、active ndp-sim、numeric、W3 或 golden。
