# Observer-only / post-sim core conjunction fix v1

Date: 2026-08-13  
Role: `optimizer.whole-network`  
Proposed activation: `observer-only-post-sim-conjunction-fix-v1`

## Finding

QAdd v61 correctly stopped before package publication because two current next-fresh gates had an empty conjunction. `post_sim_return_core` requires a byte-exact packaged copy of canonical `tools/server_post_sim_return.py`; that helper retains historical VPD/FSDB compatibility branches. The observer-only validator scanned every packaged Python file for `.vpd/.fsdb` literals and therefore rejected the helper despite the actual observer-only request having no active waveform discovery.

This is a validator applicability/conjunction escape, not a QAdd package, DUT, config, numeric or workload defect. Existing public semantics already require both no-wave execution and independent post-sim core publication; no new public rule ID is needed.

## Narrow implementation

The observer contract now contains `observer-only-post-sim-helper-exemption-v1`. Eligibility requires all of the following simultaneously:

1. Exact package-relative helper path `package_tools/server_post_sim_return.py` and request path `contracts/server_post_sim_return_request.json`.
2. Packaged helper bytes equal the current local canonical `tools/server_post_sim_return.py`; the contract binds its exact bytes, SHA and the exact inert literal token set.
3. The post-sim request belongs to the same package and `waveform_discovery` is omitted or null.
4. Active core-entry and plugin argv paths contain no waveform/query/writer controls.
5. The runner invokes the exact helper/request pair through `finalize --request`.

Only literal-suffix rejection is exempted for that single exact helper. Writer/control scanning remains active even for it. Every other Python/HDL/runner/manifest/allowlist member remains fully scanned, so renamed helpers, unknown helpers and active waveform surfaces fail closed.

Canonical helper identity used by the target mainline is bytes `68148`, SHA `91111090ec15dd0226175d4d7a4fc32f304d7f4a87047e51b665565d1ace6939`; it contains three `.vpd` and three `.fsdb` inert literal occurrences and no `.vcd/.fst` occurrence.

## Validation

The focused observer-only, runtime supervision and post-sim return conjunction suite passed 59/59. Negative controls cover wrong helper SHA/path, renamed helper, active `waveform_discovery`, unknown Python helper containing waveform literals, active waveform argv, waveform members/allowlist and dump writer/control. Python compile, JSON parse and scoped diff check passed.

Machine report: `outputs/observer_only_post_sim_conjunction_fix_v1/report.json`.

## Mainline merge recommendation

Keep `observer_only_wide_causal_final_zip` and `post_sim_return_core` conjunctive. Refresh only the observer gate implementation receipt/epoch and narrowly clarify the existing three public rules; do not add a synonymous rule. The clarification is that byte-exact canonical post-sim compatibility literals are inert source text only when the exact no-wave request proves those branches inactive.

## Claim boundary

No family package was rebuilt, rotated or changed. No plan, owner registry, public rule, RTL, config, numeric, workload or server state was modified. This closes only the shared final-ZIP gate conjunction; family build/release and server execution remain with the family owner and mainline.
