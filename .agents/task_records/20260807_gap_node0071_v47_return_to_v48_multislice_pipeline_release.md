# GAP node0071 v47 return → v48 multislice pipeline diagnostic release

- owner: `019fa366-cb1f-7ae2-880c-f527be0680cd`
- return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- date: `2026-08-07`
- status: `PACKAGE_READY_NOT_RUN`
- class: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`
- evidence ceiling: `E2_LOCAL_ONLY`

## Trigger and boundary

The accepted v47 analysis is
`artifacts/operator_config_validation/r5-gap-node0071-v47-return-analysis/report.json`
(SHA256
`8b8bbcf9b8f332d90aad3fc39ecf47db90b65e028365fe8a83387bd92151bb6d`).
Its last proven good is shared sum_s1 EXEC_START across all selected slices plus
the complete slice0 MSE0/MSE3→GA→MSE4 path. Its first divergence is that
selected slices1–15 remain active after slice0 completes. Natural terminal and
48 formal D remain absent; E3/E4/E5 are all false.

v48 observes all remaining slices in one information-gain package:
cfg start/finish → MSE0/MSE3 accepted → GA input/output accepted → MSE4
request/write-data → slice finish. Only qualified edges are monotonic progress.
HEARTBEAT records state and count as zero progress. The observer emits at most
256 records.

## Frozen set

- numeric: `73/73` byte-equal to v47;
- config/mapping/bitstream/execplan/tail mapping: `134/134` byte-equal;
- total unchanged members: `220`;
- removed members: `0`;
- no numeric, sum, tail, workload, config or golden recomputation;
- timeout, backpressure and functional RTL are unchanged.

The only common members changed are runner, README, manifest, package runtime,
observer and the two SCA transport JSONs. Four package-local runtime/diagnostic
members were added. No functional configuration semantics changed.

## Validation

- deterministic double build: identical ZIP SHA256
  `122257a3b7441e9af2a036f8d8fff1bb7339f014f9c6177f607587525ef359d3`;
- family validation:
  `beddd64537095313b3f17edc3ad3c225f5f4560a48856f41832a4aa3fc59c5b5`,
  `valid=true`, `errors=[]`;
- focused package-local HDL positive passed; declaration deletion, actual-use
  typo and critical-update removal controls all fail closed;
- exact parser trace passed, including stable-level=zero-progress and nearest
  escape;
- shared install-only V2 exact-ZIP validation:
  `33bb517e3f3acaeceade898882570ce5b83b1692ba697d25a2995899569f17f7`,
  `pass=true`, `errors=[]`;
- shared six-control-flow receipt reused from
  `ca6f8c2ed7f9f2873f62c9c5342c8a63cc1dd99f352ed12591aff93f7a5877c1`
  / V2 profile
  `e698b79c98355cbfd58710bc03c648e27c4feb5d649ad47f6d094843c02052a3`;
- shadow profile:
  `be2edaff1c40b62f8f2602aec4e470ff97e3d932ecdd63e9b116b977b8f3ac16`,
  `contract_valid=true`, errors=0;
- final-ZIP rule self-audit:
  `44104d8dd744a5d6ac3971c0fa81ba4ed4419c55b46f102e960ea84c858a154d`,
  `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`, errors=0.

An intermediate exact ZIP
`3e20248336d7b3187436ee5650707a39452a2a1c2e929f50403b7eeec6202c30`
was rejected and preserved after the shared validator detected a coalesced
`cfg_root`/`run_root`/`evidence_root`/`compile_root` assignment. It was never
published. The final runner uses one assignment per line.

## Release and storage

- pickup:
  `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n71_gap_v48_multislice_pipeline_diag.zip`
- bytes: `1952375`
- SHA256:
  `122257a3b7441e9af2a036f8d8fff1bb7339f014f9c6177f607587525ef359d3`
- command:
  `bash r5_n71_gap_v48_multislice_pipeline_diag/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`
- fixed return:
  `/home/panqs/ndp/simresult/r5_n71_gap_v48_multislice_pipeline_diag_return.zip`
- fixed sidecar:
  `/home/panqs/ndp/simresult/r5_n71_gap_v48_multislice_pipeline_diag_return.zip.sha256`

Storage rotation moved the consumed v47 package to `tested` and published v48
as the sole GAP pending identity. No parallel family was moved. Final storage
index SHA256 is
`edf9c11d9265f398ae46c67f2d12b07276eb50b800d5a859710dbd121485f4c0`;
storage audit passed with pending/tested/superseded=`4/51/30`.

## Blockers and rule feedback

Open blockers remain:

- selected slices1–15 first missing accepted checkpoint;
- dynamic natural terminal;
- formal D `48/48`;
- actual compiled production commit binding.

`RULE_CONFIRMATION`: current install-subtree, root-direct-exact-set, fixed
simresult, predicate-trace, final-ZIP and storage-rotation rules caught both
local defects. No non-synonymous rule delta is proposed.

No server upload/run/lease occurred. No plan, public rule or functional RTL was
modified.

Machine report:
`artifacts/operator_config_validation/r5-gap-node0071-v48-package-release/report.json`,
bytes=`8353`, SHA256=
`4fecf9fcb7232ed4aaee2c663f1c890af36db84104b905104a281f1bfddb7e4b`.
