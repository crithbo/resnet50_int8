# QLinearAdd node0007 v20 package-local observer HDL scope revalidation

- analysis owner thread: `019fa2c0-b647-7a91-93bf-d21a173487e3`
- return target thread: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- operation: receipt-only, package-external, read-only
- server upload/run/lease: none
- functional RTL, plan and public rules modified: false
- numeric/W3/qparam/tail/workload/config/golden repeated: false

## Frozen identity

- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_fp32_ingress_compilefix_v20.zip`
- bytes: `38041268`
- SHA256 before/after:
  `13aabd82d62eb1fa25145919c08aa3402de648ac42e401f21e3199f91d53da51`
- sidecar bytes/SHA256:
  `109` /
  `f713c5c98a30af1aedef08981cc2db5786ff201ee795a88ff67e0f35aa404e5f`
- package bytes modified: false

Current read receipts:

- mutable plan:
  `c30ab3ba244386c704e0826ad7beba4e77b960ee52dd2a9920122518dc557681`
- generation index:
  `f768a870d19699c87b66b735a759d3212db6ad51aace30e3a6305b2521a708c8`
- server rule:
  `7a5383b7881b71043bb99d997c92524cb8c25df304179b53f364219fd7c1b141`
- QLinearAdd rule:
  `aecf9d98136a23a73b3cd5ce8c8ec52f3070a763937373703e6376e3910e730f`
- exact UINT8 tail rule:
  `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e`

## Exact final observer members

- `tb_probe/native_return_observer.svh`: bytes `111955`, SHA256
  `48944e070772ef02dd5bfadbcbae1414161ab30bc714cbc266c31900d673bd00`
- `tb_probe/qlinearadd_node0007_fp32_ingress_compilefix_v20.svh`:
  bytes `1847`, SHA256
  `f66f631546d01199450417815f0c7335794b2507c9b0f49c911b9b471fac78a4`
- `tb_probe/qlinearadd_node0007_fp32_ingress_observer_tail_v19.svh`:
  bytes `17484`, SHA256
  `c0e547930e3c22fa1c574329712550752cb335fbbd613d4bcf75cee096985c9a`

The native observer includes the v20 shim exactly once and the shim includes the
frozen v19 tail exactly once.

## Machine declaration/use/update closure

Over the exact concatenated final observer bytes:

- `return_obs_*`: used `121`, declared `121`, unresolved `0`
- `qadd_ingress_*`: used `29`, declared `29`, unresolved `0`
- `return_obs_ga_operand_capture_mon`: declaration `1`, qualified XMR
  continuous updates `2`, v19 tail uses `4`
- paired capture counter updates: `2`
- physical columns: GA `0` and `2`
- active RTL leaf:
  `GA_PE_Inbuffer.ga_pe_inbuffer_enable`

## Compatible frontend positive

- tool: `C:\iverilog\bin\iverilog.exe`
- version:
  `Icarus Verilog version 12.0 (devel) (s20150603-1539-g2693dd32b)`
- command:
  `C:\iverilog\bin\iverilog.exe -g2012 -s observer_scope_focus -o positive.vvp positive.sv`
- frontend exit: `0`
- focused source SHA256:
  `252ff377f6f4f2ced3d128e95587058c41f2d09917542fdc62d3b148303403d4`

The focused source preserves the exact v20 declaration and both exact
hierarchical XMR assignments. It also preserves the exact v19 critical
identifier, select rank, capture bit and counter update. Only the four runtime
packed-array indices are specialized to zero because Icarus 12.0 rejects
variable selects across this five-dimensional packed monitor; production VCS
remains the final full-design elaboration evidence. This limitation is explicit
and is not replaced by a safe compile stub.

## Negative controls

- delete complete monitor declaration: frontend exit `6`, validator exit `1`
- misspell one tail use: frontend exit `2`, validator exit `1`
- delete key capture counter update: frontend exit `0`, semantic validator
  exit `1`

All three fail closed. The third proves that syntax success alone cannot hide a
missing qualified state update.

## Verdict

- `HDL_SCOPE_REVALIDATION_PASS=true`
- safe compile stub used as HDL evidence: false
- previous hold:
  `PACKAGE_HELD_HDL_SCOPE_REVALIDATION_REQUIRED`
- restored status:
  `PACKAGE_READY_NOT_RUN / PACKAGE_RUN_READY`
- fresh package generated: false
- unique package identity and command remain unchanged

External machine receipt:

- path:
  `artifacts/operator_config_validation/r5-qlinearadd-node0007-fp32-ingress-compilefix-v20/hdl_scope_revalidation.json`
- bytes/SHA256:
  `9408` /
  `114893b15ebb90f6c4440ef82f38b60815fbe319f5a44f024c10fc0ed902e402`
- validator:
  `tools/revalidate_qlinearadd_node0007_v20_observer_hdl_scope.py`
- validator SHA256:
  `208fd9370f843645bf6705d3d2b69fbea901044db3ef0b1fc2693ce0ab1e2329`

Rule delta proposal remains:
`CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001`.
No public rule was modified in this task.
