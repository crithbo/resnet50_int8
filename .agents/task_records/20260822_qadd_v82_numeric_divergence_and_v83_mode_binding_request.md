# QAdd v82 corrected numeric analysis and v83 mode-binding request

- Role: `family.qlinearadd`, owner epoch `6`, registry epoch `43`.
- Exact source package: `outputs/qadd_v82_successor/r5_qadd_n7_tr_v82_w15kqf.zip`, SHA-256 `7163ffb24a1af6c7de68d0886d653e2092cdb64ef67bf4898005cdeba6d15ed8`.
- Exact formal return: `outputs/qadd_v82_return_r1787114185788058566_198658/r5_qadd_n7_tr_v82_w15kqf_r1787114185788058566_198658_return.zip`, SHA-256 `9392f41cb14be1ecf7140228f05ca0f4899ea72d0ee59ac5e6e227ef20cdd1fa`.
- v82 production compile, simulation, target entry and natural terminal passed. All 28 structural Formal-D/readback artifacts were returned.
- The manifest-required exact stage-local comparison fails: `802816/1053696` lines and `8601520/16859136` uint8 elements differ. Slices `00..07` mismatch all `37632` lines; slices `08..27` mismatch `25088` lines each. Operator E3 and E4/E5 remain unproven.
- Streaming decode of every package boundary input reproduces every golden byte under the declared layout, RNE and uint8 saturation: zero formula mismatches. The validated 4/2 config/bitstream/SCA lineage and its ordered `0x33333333` then `0xcccccccc` acceptance/clear remain proven.
- The source-bound VCD contains `18816` complete Buffer5 producer writes for physical slice0. The unique bank/spatial lane mapping reproduces the returned `602112` bytes exactly. The first producer payload already differs at returned byte index `1` (`0` versus golden `6`), so Buffer5 write/store/readback and the return parser are closed. The first dynamic divergence is upstream in the GA numeric pipeline.
- The current cone has no GA inport, even-PE magic MAC, even-to-odd link, odd-PE INT32 subtraction or GA outport numeric internals. The same-attempt compile log binds their production paths but does not return their functional-source SHA identities. Local read-only RTL is therefore static supporting evidence, not an exact same-attempt root proof.
- Root disposition: `OPEN_UNVALIDATED_MECHANISM / GA_NUMERIC_PIPELINE_PRE_BUFFER5_OPEN`.
- Rule audit: `RULE_CONFIRMATION_NO_CHANGE`. Shared causal-cone/matrix semantics are sufficient; the family cone still targeted the prior Buffer readiness boundary, and the prior formal analysis omitted its required exact comparator. `PACKAGE_BUILD_FAILURE_RULE_AUDIT` is not triggered because the package executed the target and returned complete evidence.
- Minimal fresh proposal: `r5_qadd_n7_tr_v83_ga_numeric`, proposed `TB_VCD_BOUNDED_CAUSAL_CONE`, adding same-attempt GA functional-source hashes, the eight active input→magic-MAC→PE-link→INT32-sub→outport chains, and automatic streaming exact comparison. Construction is stopped until mainline issues the exact `server-family-dispatch-mode-binding-v1` authority for v83.

Machine records:

- `outputs/qadd_v82_return_r1787114185788058566_198658/formal_return_analysis.json`, SHA-256 `8a8cd6a4bf9a1bc50c4f5cd69bd67b7c72a2a5592027a6a18ebee91aa55d7eeb`.
- `outputs/qadd_v82_return_r1787114185788058566_198658/mainline_receipt.json`, SHA-256 `a2bfc81bc1f11c3e51818ae37bcf452cccb8ba1ff765827bcbfe419d0e220977`.
- `outputs/qadd_v82_return_r1787114185788058566_198658/numeric_compare_machine_report.json`, SHA-256 `8a786e512a5df6ef0c6b2eb7e76bdc305210ca2fffc0ddff0a3a4e7171b47249`.
- `outputs/qadd_v82_return_r1787114185788058566_198658/vcd_causal_machine_report.json`, SHA-256 `cffc5564e55b9bd9c2a94acbbe27fb4def6ff2bbb839819249909a8f6663736c`.
- `outputs/qadd_v82_return_r1787114185788058566_198658/RULE_GAP_AUDIT.json`, SHA-256 `96cc1763a2fea943699624dfca0c3ba3e8315145b583b19e83280a31a1126686`.
- `outputs/qadd_v82_return_r1787114185788058566_198658/v83_successor_proposal.json`, SHA-256 `34403bc898ec105bd3b15242a0f180706f88f5270d7ea1e4ecb976fb8ca9b878`.

The original return ZIP was not modified. No package was built, no managed storage was written, and no server, functional RTL, config, numeric, workload, golden, plan, rule or registry action occurred.
