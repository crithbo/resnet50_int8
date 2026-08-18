# TB-VCD predecessor semantic compatibility v7 activation

The user explicitly authorized the narrow shared compatibility repair after QAdd v71 exposed that the semantic-v6 validator recursively revalidated a byte-exact semantic-v5 predecessor as v6.

The current successor is still validated under the current semantic gate. A predecessor may use its declared published semantic version or an exact published PASS receipt, while contract/receipt SHA, package/family, immediate round, pinned RTL/catalog identity, signal diff and candidate preservation remain blocking. Legacy semantic versions 5 and 6 are accepted only with an exact identity/status-bound PASS receipt. Altered receipt SHA and source identity controls fail closed.

Gate versions are now TB-VCD `7`, first-fresh `6`, runtime-layout `5`. Focused/control-plane validation passed 168/168; the active-rule audit passed 14/14 with 164 definitions and no duplicate, error or warning.

Activation receipt: `outputs/qadd_predecessor_semantic_compatibility_v7/CANONICAL_PREDECESSOR_SEMANTIC_COMPATIBILITY_ACTIVATION_RECEIPT.json`.

QAdd v71 remains frozen and nonpublishable. The next attempt must use a fresh identity and rerun every current gate. No managed-storage or server action occurred.
