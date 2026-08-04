from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.build_node0004_v11_return_budget_package_v12 as prior  # noqa: E402


INSTALL_NAME = "r5_n4_hw_v13_abpe_boundary"
SOURCE_INSTALL_NAME = "r5_n4_hw_v12_hangloc_returngate"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n4_hw_v12_hangloc_returngate.zip"
)
SOURCE_ZIP_SHA256 = (
    "80d489798af019b00bba7ee7a7b6060de9f4cf77c2b6e57b11955995803e2e6d"
)
BOUND_RETURN_SHA256 = (
    "4c6913a037b3211fbacb1c6c81bad29ea854b71787969ca6becff40450045efb"
)
PLAN_SHA256 = (
    "e4beaa39dfd5bd3c247d546dc2fc431758e1038cbef806e7b5a8f5b49e09ac6a"
)
SERVER_RULE_SHA256 = (
    "7672b44bbcb7e130792d6b288188caa2509dc72b1ea3962bf44ffb82588009aa"
)
ABPE_TAIL = ROOT / "tools/node0004_abpe_boundary_observer_tail_v13.svh"
OUTPUT_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
BASE_RUNNER = prior.base._runner


def _configure_prior() -> None:
    prior.INSTALL_NAME = INSTALL_NAME
    prior.SOURCE_INSTALL_NAME = SOURCE_INSTALL_NAME
    prior.SOURCE_ZIP = SOURCE_ZIP
    prior.SOURCE_ZIP_SHA256 = SOURCE_ZIP_SHA256
    prior.BOUND_RETURN_SHA256 = BOUND_RETURN_SHA256
    prior.PLAN_SHA256 = PLAN_SHA256
    prior.SERVER_RULE_SHA256 = SERVER_RULE_SHA256
    prior.base.INSTALL_NAME = INSTALL_NAME
    prior.base.SOURCE_INSTALL_NAME = SOURCE_INSTALL_NAME
    prior.base.SOURCE_ZIP = SOURCE_ZIP
    prior.base.SOURCE_ZIP_SHA256 = SOURCE_ZIP_SHA256
    prior.base.RETURN_ZIP_SHA256 = BOUND_RETURN_SHA256
    prior.base.PLAN_SHA256 = PLAN_SHA256
    prior.base.SERVER_RULE_SHA256 = SERVER_RULE_SHA256
    prior.base.SOURCE_PREFIX = f"install/cfg_pkg/{SOURCE_INSTALL_NAME}/"
    prior.base.CURRENT_PREFIX = f"install/cfg_pkg/{INSTALL_NAME}/"


def _install_custom_observer_and_runner() -> None:
    def observer(package: Path) -> str:
        base_text = prior.base.BASE_OBSERVER.read_text(encoding="utf-8")
        canonical_tail = (
            ROOT / "tools/node0004_hang_localization_observer_tail_v10.svh"
        ).read_text(encoding="utf-8")
        needle = 'return_obs_write_internal_state("DIAG_DECISION");'
        if canonical_tail.count(needle) != 1:
            raise prior.base.BuildError("canonical decision hook differs")
        canonical_tail = canonical_tail.replace(
            needle,
            needle + '\n                return_obs_write_abpe_state("DIAG_DECISION");',
        )
        abpe_tail = ABPE_TAIL.read_text(encoding="utf-8")
        target = package / "tb_probe/native_return_observer.svh"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            base_text.rstrip()
            + "\n\n"
            + canonical_tail.rstrip()
            + "\n\n"
            + abpe_tail,
            encoding="utf-8",
            newline="\n",
        )
        return prior.base.sha256(target)

    def runner(observer_sha: str) -> str:
        text = BASE_RUNNER(observer_sha)
        needle = "+RETURN_OBSERVER +RETURN_OBS_SLICE=0"
        replacement = (
            "+RETURN_OBSERVER +RETURN_OBS_DEEP "
            "+RETURN_OBS_DEEP_LIMIT=256 +RETURN_OBS_ABPE "
            "+RETURN_OBS_SLICE=0"
        )
        if text.count(needle) != 2:
            raise prior.base.BuildError("runtime observer argv hook differs")
        return text.replace(needle, replacement)

    prior.base._observer = observer
    prior.base._runner = runner


def _readme() -> str:
    return f"""# node0004 v13 narrow A/B-to-PE boundary package

Classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`.

The v12 return proves a deterministic qualified stall before the first
Buffer5 write, but does not distinguish Buffer0/2-to-SA acceptance, per-PE
masked operand matching, ALU acceptance, PE outbuffer acceptance, and SA
group-output acceptance.  This package reuses the frozen v12 c0 workload
without changing JSON, bitstream, execplan, SCA, golden data, or functional
RTL.  It enables the existing finite MSE0 deep trace and adds one bounded
`ABPE_BOUNDARY_V1` record at the canonical decision.

Server command:

```bash
bash {INSTALL_NAME}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy
```

Expected return: `{INSTALL_NAME}_return.zip` and adjacent `.sha256`.
"""


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    _configure_prior()
    _install_custom_observer_and_runner()
    package, proof = prior.build_directory(destination)
    (package / "README.md").write_text(
        _readme(), encoding="utf-8", newline="\n"
    )
    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["schema"] = "resnet50-node0004-abpe-boundary-package-v13"
    manifest["install_name"] = INSTALL_NAME
    manifest["status"] = "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX_READY_NOT_RUN"
    manifest["evidence_level"] = "E2_LOCAL_PLUS_V12_ABPE_BOUNDARY_GAP"
    manifest["frozen_source_package"] = {
        "path": SOURCE_ZIP.relative_to(ROOT).as_posix(),
        "sha256": SOURCE_ZIP_SHA256,
    }
    manifest["bound_v12_return_sha256"] = BOUND_RETURN_SHA256
    manifest["package_side_repair"] = {
        "classification": "NARROW_DIAGNOSTIC_BOUNDARY_COMPLETION",
        "first_divergence": (
            "v12 proves four consecutive zero-delta qualified windows after "
            "initial A/B/C read data, but only records the coarse "
            "Buffer4-read to Buffer5-write interval"
        ),
        "repair": (
            "enable existing finite MSE0 trace and add qualified/snapshot "
            "boundaries for A/B/C group acceptance, per-PE masked A/B, "
            "ALU acceptance, PE outbuffer acceptance, and SA group output"
        ),
        "functional_semantics_changed": False,
    }
    manifest["unresolved_boundary"] = (
        "A/B/C memory data reached local buffers and Buffer4 was read, while "
        "no Buffer5 write occurred; v13 distinguishes the only remaining "
        "buffer0/2 -> masked operands -> ALU -> PE outbuffer -> SA group "
        "sub-boundaries"
    )
    manifest["narrow_diagnostic_contract"] = {
        "record": "ABPE_BOUNDARY_V1",
        "emission": "exactly once with the canonical decision",
        "counts_are_qualified": [
            "A/B/C group valid with selected-source backpressure acceptance",
            "sa_pe_cb2ob_alu_bp_pre",
            "PE outbuffer valid with outport backpressure acceptance",
            "SA group valid with Buffer5 acceptance",
        ],
        "snapshots_not_progress": [
            "per-PE masked A valid",
            "per-PE masked B valid",
            "per-PE all_operands_matched",
            "per-PE outbuffer valid",
        ],
        "existing_monotonic_progress_unchanged": True,
        "deep_mse0_enabled": True,
        "deep_event_limit": 256,
        "result_partition": [
            "no A/B group accept => buffer0/2 or MSE-to-buffer boundary",
            "A/B accept but no all-matched/ALU accept => tag/same/per-PE match",
            "ALU accept but no PE out accept => PE outbuffer/last boundary",
            "PE out accept but no SA group out => outport serialization/major",
            "SA group out but no Buffer5 write => array-to-buffer5 boundary",
        ],
    }
    manifest["numeric_analysis_repeated"] = False
    manifest["node0004_workload_rebuilt"] = False
    manifest["functional_rtl_modified"] = False
    manifest["server_rtl_entries"] = 0
    manifest["superseded_diagnostic_package"] = {
        "name": "r5_n4_hw_v12_hangloc_returngate.zip",
        "sha256": SOURCE_ZIP_SHA256,
        "status": "CONSUMED_RETURN_BOUND_DIAGNOSTIC_PREDECESSOR",
    }
    manifest["files"] = prior.base.package_records(package)
    prior.base.write_json(manifest_path, manifest)
    proof = prior.base.preflight(package)
    observer_sha = manifest["observer_binding_four_way"]["source"]["sha256"]
    observer = prior.base.observer_precompile_receipt(package, observer_sha)
    if not observer["valid"]:
        raise prior.base.BuildError(f"observer XMR gate failed: {observer['errors']}")
    return package, {"preflight": proof, "observer": observer}


def _repeat(package: Path, zip_path: Path) -> dict[str, Any]:
    prior.base.deterministic_zip(package, zip_path)
    records = prior.base.package_records(package)
    digest = prior.base.sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix="node0004-v13-repeat-") as temporary:
        repeat_root = Path(temporary)
        repeat_package, _ = build_directory(repeat_root)
        repeat_zip = repeat_root / f"{INSTALL_NAME}.zip"
        prior.base.deterministic_zip(repeat_package, repeat_zip)
        if records != prior.base.package_records(repeat_package):
            raise prior.base.BuildError("repeated package trees differ")
        if digest != prior.base.sha256(repeat_zip):
            raise prior.base.BuildError("repeated deterministic ZIPs differ")
    return {
        "package_tree_equal": True,
        "zip_equal": True,
        "repeat_zip_sha256": digest,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()
    output = args.output_root.resolve()
    package_path = output / INSTALL_NAME
    zip_path = output / f"{INSTALL_NAME}.zip"
    sidecar = Path(str(zip_path) + ".sha256")
    validation = output / f"{INSTALL_NAME}.validation.json"
    for path in (package_path, zip_path, sidecar, validation):
        if path.exists():
            print(f"refusing to overwrite: {path}")
            return 1
    output.mkdir(parents=True, exist_ok=True)
    package, proof = build_directory(output)
    repeated = _repeat(package, zip_path)
    digest = prior.base.sha256(zip_path)
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    receipt = {
        "schema": "node0004-abpe-boundary-package-validation-v13",
        "status": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX_READY_NOT_RUN",
        "package": str(package),
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "source_zip_sha256": SOURCE_ZIP_SHA256,
        "bound_return_sha256": BOUND_RETURN_SHA256,
        "package_file_count": proof["preflight"]["package_file_count"],
        "observer_sha256": proof["preflight"]["observer_sha256"],
        "observer_static_gate": proof["observer"]["xmr_static_gate"],
        "observer_runtime_enabled": True,
        "observer_compile_enable_macro_bound": True,
        "observer_return_allowlisted": True,
        "abpe_boundary_enabled": True,
        "deep_mse0_enabled": True,
        "qualified_progress_definition_changed": False,
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "functional_rtl_modified": False,
        "server_rtl_entries": 0,
        "server_action": False,
        "repeated_build": repeated,
        "final_zip_rule_self_audit_pending": True,
    }
    prior.base.write_json(validation, receipt)
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
