# Conv native-four-lane p20 formal return and p21 epoch-owner successor

## Formal identities

- Formal p20 return:
  `C:/Users/15383/Downloads/r5_n4_0cc_p20_obsbindfix_r1786159986792917726_3954624_return.zip`,
  bytes `2068706`, SHA256
  `67441ee6c11d67cf4dec6159f5dca5ae4b3d0e7a96048793e6dadc95f451076d`.
- Frozen p20 source: `r5_n4_0cc_p20_obsbindfix.zip`, bytes `5874994`,
  SHA256 `68e2fc8f98fa1c6c95fa8eb56a7d5a46e9ac132719cf252be5748b3da2dca208`.
- Execution identity: `r1786159986792917726_3954624`.
- Canonical machine analysis:
  `outputs/conv_native_four_lane_0ccae916_p20_return_analysis/report_v3.json`,
  bytes `18364`, SHA256
  `97c4606303825ead0eb8c7d8c1fe5b5d678e780477bbcdeaa1fe0f7b8dbcb6e5`.
  The immutable earlier `report_v2.json` remains a noncanonical audit receipt: its
  summary incorrectly set `E3=true` despite `signal=INT` and no natural terminal.
  v3 corrects that record-only adjudication field and normalizes the already
  rotated source location from `pending` to `tested`; all source bytes, parsed
  evidence and successor-causal conclusions are unchanged.

## RETURN_ANALYSIS

- ZIP CRC, single safe root, member exact-set/allowlist, per-file receipt, source
  identity, repeat-execution identity, install-only runtime layout, NDP-root
  direct-child exact-set, path budget and all package-local preflights pass.
- Production compile is `0`; VCS elaboration reports zero errors. This is the
  production proof that the p20 lexical observer binding repair is valid and it
  closes the p19b package-local observer compile escape.
- Simulation really started. The simulator argv, simulator log, observer log and
  all fourteen exact feature markers jointly contradict the stale
  `dut_simulation_started=false` bookkeeping bit in the partial status file.
- The execution ended with `run=125`, `signal=INT`. It did not reach a natural
  terminal, c0 `slice_finish`, 27/27 natural runs, or formal 320D. Therefore
  `E3/E4/E5=false/false/false`, result conjunction is false, and no production
  performance claim is permitted.
- Production RTL identity is complete. Actual/local/cloud differences are
  nonblocking provenance after successful compile; the exact SA CSA/ALU leaves
  match, while the captured Buffer/ARM/MRM cone limits cross-version E4/E5 until
  a natural formal result exists.

## Qualified causal adjudication

- Public qualified counts are `SA_IN=30`, `SA_OUT=5`, `MSE4_INDEX_ACCEPT=3`.
- At the third descriptor terminal, `desc=18`, `desc_pop=18`, `prepared=19`.
  Afterwards prepared reaches `20`, while descriptor/address issuance remains
  `18`; source push/pop reaches `27/23`, tag/tag-pop `23/21`, and the final skew
  is `prepared-desc=2`.
- Buffer5 last qualified totals are ARM accept `5`, MRM accept/clear `10/10`, SA
  accept `5`, followed by stable SA-valid/ready-low backpressure. Held levels and
  the legacy generic progress counter are explicitly noncanonical transactions.
- LAST_PROVEN_GOOD: the third descriptor terminal reaches
  `desc=18/pop=18/prepared=19`, then the Buffer data branch accepts one further
  prepared group.
- FIRST_DIVERGENCE: descriptor/address remains at `18` while prepared becomes
  `20`; MSE4 address-side raw/same/gotten/masked is `1/1/7/0`, match remains
  zero and its queue is empty.
- HANG_ROOT_CAUSE is not yet unique. The remaining same-output equivalents are
  shared-LC partial capture, physical-LC terminal/keep stop, Memory_AG
  same/gotten suppression, and Buffer next-epoch early acceptance. No config
  leaf or functional RTL repair is authorized by p20.

Blocker delta:

- closed: `B_CONV_NATIVE_P20_FORMAL_RETURN_RECEIPT`,
  `B_CONV_NATIVE_P19B_PACKAGE_LOCAL_OBSERVER_SCOPE_COMPILE_ESCAPE`,
  `B_CONV_NATIVE_POST_PEKEEP3_COARSE_DFLOW_BOUNDARY`;
- opened: `B_CONV_NATIVE_MSE4_PER_INPUT_EPOCH_OWNERSHIP_UNOBSERVED`;
- preserved: c0 slice finish, 27 natural terminals, formal 320D and E4/E5.

## Fresh p21 successor

`r5_n4_0cc_p21_epochowner` is the single highest-information successor. It adds
one bounded, same-clock per-input epoch-owner ledger equivalent to the already
validated serialized-v66 discriminator. The partial-INT finalizer now writes
feature binding before analysis when logs exist and derives simulation start
from the exact simulator argv plus simulator/observer logs.

All p20 workload, numeric/W3/qparams, target config, mapping, bitstream,
execplan, SCA semantics, golden, timeout, functional RTL, ISA, hardware and
active ndp-sim are frozen. Eighty-seven installed payload members are byte-equal;
only the package-local observer/runner/identity/receipts change. The p21 package
manifest itself explicitly records `c0_natural_terminal=false` and
`formal_D_claimed=false`; consequently the record-only v2→v3 E3 correction does
not change p21 executable bytes or release eligibility and does not justify a
redundant rebuild.

- pickup:
  `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p21_epochowner.zip`
- bytes `5876983`
- SHA256 `cd78dd1aa2234bc12e4588b957fa900e71030486bd6eca4c315155451f631c8d`
- command: `bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02`
- expected unique return:
  `/home/panqs/ndp/simresult/r5_n4_0cc_p21_epochowner_r<execution-id>_return.zip`
- classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`
- candidate release: `false`
- PACKAGE_RELEASE: `PACKAGE_READY_NOT_RUN`

Exact final audits:

- family audit PASS/errors0 SHA256
  `2a0b5df65ef3644f343e8bc6127f89812be82db47f5d4f8c34400ff0046899b4`;
- shared install-only runtime audit PASS/errors0 SHA256
  `757f2a6f2209f4038fa0e2e0dbb7d16bc20081d0c521c9cd81891f580e79ddf4`;
- normal/preflight-fail/compile-fail/HUP/INT/TERM runner harness PASS SHA256
  `591b30e306080b84fa9debdeb02c679f0c04117bb50c5e745b547d4a651b97a8`;
- final ZIP audit valid SHA256
  `eeccbbdc24c9dbaa7c55e74779e3a0d256c82ab9547139025d9019853f46b0cd`;
- build profile SHA256
  `42228fd11d5543a56a5b270bd2638f12ec65fc8c8dd9a5e54a4d67a86713a2da`.

Storage rotation is complete: p20 is archived under `tested`, p21 is the only
native-four-lane pending ZIP, and storage index SHA256 is
`e74bfe07626f5fc8ea722a393a0f2bd9158e07b804798d98f0477025a3e98453`.
No upload, server run, lease, functional RTL, public rule or plan action occurred.

## Rule feedback

`RULE_CONFIRMATION`: current continuous-closure, manual-interrupt
classification, qualified-event, cloud-RTL nonblocking-diff, result-conjunction,
install-only-v2, repeat-execution owned-reset, unique fixed-simresult return and
storage-rotation rules are sufficient. No non-synonymous `RULE_DELTA` is needed.
