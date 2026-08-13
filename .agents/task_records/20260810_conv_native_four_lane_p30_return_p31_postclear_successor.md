# 2026-08-10 native four-lane Conv p30 return → p31 post-clear successor

## Scope

- Family: `conv_native_four_lane`, frozen node0004 c0 diagnostic branch.
- Formal p30 return: `r5_n4_0cc_p30_bankvalid_r1786345801746754550_481017_return.zip`, bytes `148318`, SHA256 `409e0e9264353eac4b883e671b0a0502619257fe6948d0f171dc4c73e9a2e499`.
- Exact p30 source SHA256: `8229b380c9b33f99c8bd27d3eb21ce2ce17aae1b5eb0278926f27307887cbf34`.
- No functional RTL, numeric, W3, workload, config, mapping, bitstream, execplan or golden change.

## Formal p30 adjudication

- Analysis: `outputs/conv_native_four_lane_0ccae916_p30_return_analysis/report.json`, SHA256 `88a629d28ab67cdb223e0e579a59c46928751ca387faab1850df8c5971f6fb39`.
- Status: `P30_PARTIAL_INTERRUPTED_FINAL_BANK_STATE_EVIDENCE_ESCAPE_SUCCESSOR_REQUIRED`.
- Compile passed and c0 simulator started. Actual production Buffer and Memory_Req_Manager identities were collected; their cloud/local differences are nonblocking provenance because compile and simulation passed.
- The execution ended by `INT` (`sim_exit=130`), with qualified c0 progress. It is not a DUT/config/RTL/numeric failure.
- Natural terminal and c0 slice finish were not reached. This diagnostic package had no formal-D payload. Therefore 27/27 natural, 320/320 D, E3, E4, E5, mismatch-zero and performance remain unclaimed.
- LPG: generated source-bound observer active; earlier row2 bank-ready `0x0f` followed by accepted `0xff`; public row2 clear at cycle 150; final same-tag row2 block starts cycle 151.
- FD: the exact current bank vector at the sustained cycle-151 block was not published before INT.
- Root boundary: `PACKAGE_LOCAL_NON_PROGRESS_CURRENT_STATE_NOT_SIGNAL_SAFE`. Sticky mask `0x2b` is lifetime OR, stall payload is hard-coded zero, and final/ring state is absent. Remaining equivalents are final bank-ready `0x0f` versus bank-ready `0xff` with aggregate-ready low.

## p31 materialization

- Package ID: `r5_n4_0cc_p31_postclear`.
- The source-bound observer has six pairwise-distinguishable candidates: final marker absent; final bank-ready `0f`, `00`, `f0`, `ff`, or `other`.
- Candidate state is emitted by immediate trigger, not deferred to `final`, so INT cannot erase the already-observed class.
- One cheap prebuild aggregate: `server_package_build_profile.json`, SHA256 `101c401db92269c2e85c1b2e6816272f3cfb200382932907a2d5424e08f7547a`, contract valid, errors 0.
- One final ZIP only; deterministic double build passed. Frozen installed payloads: 87/87 byte-equal; SCA files identity-normalized equal.
- Exact ZIP bytes `5927263`, SHA256 `d022977daebb1c633d0c4fa32ca58cf5b660a6f4c4dff6cb11d499a21d2345c9`.

## Final and first-fresh gates

- Family audit v2 SHA256 `3e41f5e0c3571cd84796b2103028411ca3ff1c3c18893a4e507bd260c31e3e26`, PASS/errors 0.
- Source-bound exact regeneration, post-sim four scenarios, install-only runtime layout, root direct exact-set and runner normal/preflight-fail/compile-fail/HUP/INT/TERM all PASS.
- Epoch ACK: `20260810-first-fresh-extra-audit-v1`, `first_fresh_after_change=true`.
- Independent clean-extract extra-audit validation SHA256 `48c58b614af0ba1fe311d454e5229d4f000a5b944d711e52a8c43ecc85ab0ec1`, PASS/errors 0/warnings 0, `upload_authorized=true`.
- The prescribed `validate_server_first_fresh_extra_audit.py` final validator ran exactly once.
- A pre-validator receipt-script escape attempted to JSON-serialize a Python set. It is recorded as `AUDIT_RECEIPT_SCRIPT_PAIRWISE_SET_SERIALIZATION_ESCAPE`; ZIP unchanged, final validator invocations before the escape were zero, and recovery reused/reverified the same independent clean tree. No package rebuild occurred.
- Final ZIP audit SHA256 `699a9493c8c273982cb5e19e349d8ad944e91334b7734fd487addfe38d15115e`, `PACKAGE_READY_NOT_RUN`.

## Storage and pickup

- p30 rotated to `tested` with its formal return analysis.
- p31 is the sole `conv_native_four_lane` pending ZIP.
- Pickup: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p31_postclear.zip`.
- Storage release report SHA256 `ad7396c0d3035c0437d785c7b48b998783690d13d9e5368160a4297b17fb942e`.
- Storage index SHA256 `516bf543446c773f1b913789151103389775e2af477cf86c1ff3ec0aebf97111`, audit PASS.
- Server command: `bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02`.
- Expected return: `/home/panqs/ndp/simresult/r5_n4_0cc_p31_postclear_r<epoch-ns>_<pid>_return.zip` plus adjacent `.sha256`; duplicate absent required.
- No upload, server run or lease action was performed.

## Rule feedback

`RULE_CONFIRMATION`: current source-bound generated observer, post-sim independent core publication, first-fresh independent re-audit, install-subtree runtime layout, result conjunction and storage rotation rules are sufficient. No non-synonymous rule delta is proposed.
