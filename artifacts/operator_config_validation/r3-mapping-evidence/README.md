# R3 mapping evidence bundles

These directories are small, portable validation evidence. They are not server execution results and do not prove numerical correctness.

Each bundle contains the copied strict source JSON, the exact native bitstream artifacts, final native mapping state, initially-empty/same-run cache evidence, encoder source manifest, raw stdout/stderr, mapping evidence v2, an independent artifact-validation report, and a bundle manifest.

Generate a new bundle from the pinned active `ndp-sim` commit:

```powershell
$py = '.venv\Scripts\python.exe'
& $py tools\generate_operator_config_mapping_evidence.py `
  <strict-config.json> `
  artifacts\operator_config_validation\r3-mapping-evidence\<new-bundle-name>
```

The output directory must not already exist. The generator uses a disposable copy of `ndp-sim/bitstream`, requires an exact zero mapping penalty and no fallback nodes, and publishes only after the independent JSON-to-bit mirror passes.

Revalidate an existing bundle:

```powershell
$bundle = 'artifacts\operator_config_validation\r3-mapping-evidence\decode_summac-seed42-v1'
& $py tools\validate_operator_config_artifacts.py `
  "$bundle\source_config.json" `
  $bundle `
  "$bundle\mapping_evidence.json"
```

Current bundles:

- `decode_summac-seed42-v1`
- `decode_max-seed42-v1`
- `silu-seed42-v1`

Do not edit a bundle in place. Generate a new versioned directory and retain the previous bundle for comparison.
