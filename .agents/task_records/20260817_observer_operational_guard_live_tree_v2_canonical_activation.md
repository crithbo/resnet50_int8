# Observer operational guard live-tree v2 canonical activation

- Epoch: `observer-operational-guard-live-tree-v2`
- Existing semantic owner: `CDA-SERVER-WAVEFORM-DEFAULT-RETURN-UNBOUNDED-CAUSAL-COVERAGE-001`
- New public rule ID: none
- Activation: required for the next fresh observer-only package; consumed v99 is not rebuilt.

The v99 return proved that production VCS reached elaboration/link preparation before the package guard exited 2 without a guard receipt. The former blanket live-tree symlink rule was therefore narrowed: returned evidence remains strictly no-symlink, while an exact-owned live VCS internal symlink may be counted and later unlinked with no-follow metadata only when its lexical target stays within declared owned roots. Root/ancestor links, lexical escape, target traversal and special entries remain blocking.

The v2 helper uses no-follow `lstat/scandir`, three bounded create/delete resamples, and a one-shot emergency path after child start. A monitor exception must TERM, wait, KILL and reap the complete owned tree, atomically publish its receipt and stderr, and remain infrastructure failure. Exit 2 without a valid guard receipt cannot be classified as a production compile error.

Canonical validation passed: four Python modules compiled; focused guard/boundary tests 23/23; related observer, return, first-fresh, pipeline and registry suite 152 run with 151 pass, one environment-only skip and no failures; active-rule audit reports 14/14 active rules, 164 unique definitions, zero duplicates/errors/warnings. No family storage or server action occurred.

Machine receipt: `outputs/observer_operational_guard_live_tree_v2/CANONICAL_ACTIVATION_RECEIPT.json`.
