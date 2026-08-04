# Human MAC corrected-v3 package release

## Scope and authority

- Human-authored source remains immutable and bound to `mac.zip` SHA256 `7b6770dfe038d5e92b810c20fb4a8a620472afd1dc1e3d6837d4e3af54755a55`.
- User authorized continuation of the repair and server-package generation.
- The sole v2→v3 JSON change is `general_array.outport.src_id: 1 -> 0`.
- `LC2.last_index` remains `1`.
- No server upload or execution was performed; group-C has no `NDP_copy03` lease.

## RETURN_ANALYSIS

The preceding rerun reached a deterministic first dynamic failure: 28/28 slices each completed the MSE0 read side (128 requests and 128 returns), while MSE4 issued two write requests and produced zero write-data. The active one-stage GA output belongs to source group 0; corrected-v2 selected inactive source group 1. corrected-v3 applies only the dynamically supported `src_id` change.

## Corrected candidate and rebuild

- corrected-v3: `artifacts/human_mac_int32_uint8_20260727_v1/mac_int32_uint8.corrected_v3.json`
- bytes: `13941`
- SHA256: `b7087828cf6235147d1c61a40835ed4a38ed437abc14ad6871708ad487becc26`
- Single-file structural validation: pass.
- Two isolated native planner/mapper/encoder/execplan/SCA rebuilds: byte-identical for the delivered artifacts.
- Fixed seed: PCG64 `20260727`; 28 independent `int32[32,32]` slices in `[0,254]`.
- Golden: `(A + 1).astype(uint8)`.

## PACKAGE_RELEASE

- Install name: `human_mac_int32_uint8_v3_stock_rtl_fd2`
- ZIP: `artifacts/human_mac_int32_uint8_20260727_v1/server_package/human_mac_int32_uint8_v3_stock_rtl_fd2.zip`
- ZIP bytes: `140663`
- ZIP SHA256: `5bcc26c80a995063b6b8c071eea4962426dd0547d782df771c61cf1fa3024e52`
- Manifest SHA256: `ad4040eab6456b7548e6bc02635b7aa61a2b1dfb87334f784e48dc62f8d5b92b`
- `candidate_release=false`
- Package RTL entries: `0`
- Only authorized server root: `NDP_copy03`
- Unique command: `bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy03`
- Expected return: `human_mac_int32_uint8_v3_stock_rtl_fd2_return.zip` plus `.sha256`

The single delivery preflight passed: runtime preflight, manifest/file identity, ZIP/directory byte identity, zero RTL entries, all 28 input/golden payloads, double-native rebuild equality, candidate hash, root restriction, and release flag.

## BLOCKER_DELTA

- Resolved locally: the inactive GA output-group selection is removed from the candidate and freshly encoded.
- Still open: stock-RTL dynamic completion and all 28 formal D comparisons require a valid group-C lease and returned ZIP/sidecar.
- Evidence remains `E2_LOCAL_ONLY`; this is not a dynamic pass.

## RULE_DELTA_PROPOSAL

No additional public-rule edit is proposed in this round. The already recorded lesson remains applicable: derive `last_index` from the realized LC connection list, and audit GA `outport.src_id` independently against the active output group; do not infer either field from stale logical names.
