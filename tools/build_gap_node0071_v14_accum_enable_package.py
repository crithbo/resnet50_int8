from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_gap_node0071_complete_server_package import (
    deterministic_zip,
    write_json,
)
from tools.gap_node0071_complete_server_runtime import file_records
from tools import build_gap_node0071_v13_buffer_to_ga_diag_package as v13


PACKAGE_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_NAME = "r5_n71_gap_v13_buffer_to_ga_diag"
INSTALL_NAME = "r5_n71_gap_v14_accum_enable"
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_SHA256 = "88715902dd818b488990521bcdfa9d9be24f3195e0371c9c25a664a17fc76131"
TRIGGER_RETURN_SHA256 = (
    "69e8fb4f318d649740ecf111e9ce57664e80eec9c1247e8663f17d663aef7816"
)
SERVER_RULE_SHA256 = (
    "88fcc7e87da9d92d281b8096389e31f1735b0e99ce3b13dd37635a8b96c0a7c6"
)
TRANSPORT_RULE_ID = "CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001"
OBSERVER_RELATIVE = "tb_probe/native_return_observer.svh"
ALLOWED_CHANGED = {
    "TEST_PACKAGE_MANIFEST.json",
    "README.md",
    "PREPARE_AND_RUN.sh",
    "workload/sca_cfg.json",
    "workload/sca_cfg_D.json",
}


class BuildError(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def configure_source() -> None:
    v13.SOURCE_NAME = SOURCE_NAME
    v13.INSTALL_NAME = INSTALL_NAME
    v13.SOURCE_ZIP = SOURCE_ZIP
    v13.SOURCE_SHA256 = SOURCE_SHA256
    v13.SERVER_RULE_SHA256 = SERVER_RULE_SHA256


def patch_runner(package: Path) -> None:
    path = package / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    old_server = (
        "+RETURN_OBSERVER +RETURN_OBS_FILE=<run>/sim_results/"
        "return_observer/return_observer.log"
    )
    new_server = (
        "+RETURN_OBSERVER +RETURN_OBS_ACCUM_STATE "
        "+RETURN_OBS_ACCUM_LIMIT=512 +RETURN_OBS_FILE=<run>/sim_results/"
        "return_observer/return_observer.log"
    )
    if text.count(old_server) != 1:
        raise BuildError("server command accumulator marker differs")
    text = text.replace(old_server, new_server, 1)
    old_args = "  +RETURN_OBS_DEEP_LIMIT=64\n"
    new_args = (
        "  +RETURN_OBS_DEEP_LIMIT=64\n"
        "  +RETURN_OBS_ACCUM_STATE\n"
        "  +RETURN_OBS_ACCUM_LIMIT=512\n"
    )
    if text.count(old_args) != 1:
        raise BuildError("sim_args accumulator marker differs")
    text = text.replace(old_args, new_args, 1)
    old_binding = (
        "grep -q 'Native NDP return observer' \"$observer_log\"; then\n"
        "    printf 'observer_enabled_and_returned=true\n"
        "'       >\"$evidence_root/observer_binding.txt\""
    )
    new_binding = (
        "grep -q 'Native NDP return observer' \"$observer_log\" && "
        "grep -Fq 'accum_state=1' \"$observer_log\"; then\n"
        "    printf 'observer_enabled_and_returned=true\\n"
        "buffer_to_ga_accum_state_enabled=true\\n"
        "'       >\"$evidence_root/observer_binding.txt\""
    )
    if text.count(old_binding) != 1:
        raise BuildError("runtime binding accumulator marker differs")
    text = text.replace(old_binding, new_binding, 1)
    path.write_text(text, encoding="utf-8", newline="\n")


def update_manifest(
    package: Path, source_manifest: dict[str, Any]
) -> None:
    manifest = v13.replace_identity(source_manifest)
    plan_sha = sha256(ROOT / ".agents/plan.md")
    receipts = v13.current_rule_receipts()
    manifest.update(
        {
            "schema": "gap-node0071-progress-server-package-v14",
            "status": "PACKAGE_READY_NOT_RUN",
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "package_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "claim_boundary": (
                "package-side enable repair for the existing read-only "
                "Buffer-to-GA diagnostic; frozen GAP sum/tail/config/golden, "
                "observer algorithm and 73-file numeric workload unchanged; "
                "no E3/E4/E5"
            ),
            "install_name": INSTALL_NAME,
            "package_name": INSTALL_NAME,
            "run_name": f"run_{INSTALL_NAME}",
            "return_name": f"{INSTALL_NAME}_return",
            "supersedes_package_sha256": SOURCE_SHA256,
            "quarantines_package_sha256": SOURCE_SHA256,
            "numeric_analysis_repeated": False,
            "sum_or_tail_numeric_reexecuted": False,
            "source_numeric_payload_reused_without_rebuild": True,
            "functional_fix": False,
            "candidate_release": False,
            "functional_rtl_modified": False,
            "server_run_performed": False,
            "uploaded": False,
            "lease_acquired": False,
        }
    )
    contract = manifest["final_zip_rule_self_audit_contract"]
    applicable = list(contract["applicable_rule_ids"])
    if TRANSPORT_RULE_ID not in applicable:
        applicable.append(TRANSPORT_RULE_ID)
    contract.update(
        {
            "read_receipt": receipts,
            "applicable_rule_ids": applicable,
            "all_current_match": True,
            "plan_sha256_mutable_provenance_only": plan_sha,
            "final_zip_independent_validator_required": True,
            "final_zip_rule_self_audit_pass":
                "PENDING_EXTERNAL_RELEASE_REPORT",
        }
    )
    manifest["rule_receipts"].update(
        {
            "server_rule_sha256": SERVER_RULE_SHA256,
            "current_match": True,
            "plan_sha256_mutable_provenance_only": plan_sha,
        }
    )
    manifest["buffer_to_ga_diagnostic"].update(
        {
            "runtime_accum_state_enable_required": True,
            "runtime_accum_state_enable_plusarg":
                "+RETURN_OBS_ACCUM_STATE",
            "runtime_accum_state_limit": 512,
            "observer_algorithm_changed": False,
            "numeric_workload_changed": False,
            "config_changed": False,
        }
    )
    manifest["accum_state_enable_repair"] = {
        "trigger_return_zip_sha256": TRIGGER_RETURN_SHA256,
        "source_v13_zip_sha256": SOURCE_SHA256,
        "first_divergence":
            "BUFFER_TO_GA_DIAGNOSTIC_RUNTIME_ENABLE_ABSENT",
        "source_observer_header": "accum_state=0",
        "source_actual_simulator_argv_missing":
            "+RETURN_OBS_ACCUM_STATE",
        "successor_required_actual_simulator_argv": [
            "+RETURN_OBS_ACCUM_STATE",
            "+RETURN_OBS_ACCUM_LIMIT=512",
        ],
        "successor_runtime_marker":
            "buffer_to_ga_accum_state_enabled=true",
        "observer_algorithm_changed": False,
        "numeric_workload_changed": False,
        "config_changed": False,
        "golden_changed": False,
        "allowed_changed_paths": sorted(ALLOWED_CHANGED),
    }
    manifest["generation_provenance"].update(
        {
            "tool":
                "tools/build_gap_node0071_v14_accum_enable_package.py",
            "bound_source_package_sha256": SOURCE_SHA256,
            "numeric_payload_rebuilt": False,
            "diagnostic_only": True,
            "package_side_change": (
                "fresh identity/SCA namespace/manifest/README and runner-only "
                "activation of the already packaged accumulator-state probe"
            ),
        }
    )
    manifest["files"] = file_records(package)
    write_json(package / "TEST_PACKAGE_MANIFEST.json", manifest)


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    configure_source()
    package = v13.extract_source(destination)
    source_manifest = json.loads(
        (package / "TEST_PACKAGE_MANIFEST.json").read_text(encoding="utf-8")
    )
    source_records = file_records(package, exclude_manifest=False)
    numeric_before = {
        path: receipt
        for path, receipt in file_records(
            package / "workload", exclude_manifest=False
        ).items()
        if path not in {"sca_cfg.json", "sca_cfg_D.json"}
    }
    v13.rewrite_identity(package)
    patch_runner(package)
    (package / "README.md").write_text(
        "# GAP node0071 v14 accumulator-enable diagnostic package\n\n"
        "This package is `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`. It keeps the "
        "v13 observer source and all 73 frozen numeric workload files "
        "byte-for-byte. The package-side repair adds "
        "`+RETURN_OBS_ACCUM_STATE +RETURN_OBS_ACCUM_LIMIT=512` to the real "
        "simulator argv and fail-closes the runtime observer binding unless "
        "the returned header says `accum_state=1`. No DUT signal is driven "
        "and no functional RTL, configuration, golden, sum or tail numeric "
        "payload changes.\n\nRun once with:\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX\n"
        "```\n",
        encoding="utf-8",
        newline="\n",
    )
    update_manifest(package, source_manifest)
    numeric_after = {
        path: receipt
        for path, receipt in file_records(
            package / "workload", exclude_manifest=False
        ).items()
        if path not in {"sca_cfg.json", "sca_cfg_D.json"}
    }
    if numeric_before != numeric_after or len(numeric_after) != 73:
        raise BuildError("frozen 73-file numeric workload drifted")
    final_records = file_records(package, exclude_manifest=False)
    changed = {
        path
        for path in set(source_records) & set(final_records)
        if source_records[path] != final_records[path]
    }
    if changed != ALLOWED_CHANGED:
        raise BuildError(f"changed path set differs: {sorted(changed)}")
    if (
        source_records[OBSERVER_RELATIVE]
        != final_records[OBSERVER_RELATIVE]
    ):
        raise BuildError("observer algorithm drifted")
    return package, {
        "source_v13_zip_sha256": SOURCE_SHA256,
        "observer_sha256": final_records[OBSERVER_RELATIVE]["sha256"],
        "numeric_workload_file_count": len(numeric_after),
        "numeric_workload_tree_equal": True,
        "observer_tree_equal": True,
        "changed_paths": sorted(changed),
        "changed_paths_exact_allowlist": True,
    }


def repeat_build(package: Path, zip_path: Path) -> dict[str, Any]:
    deterministic_zip(package, zip_path, archive_root=INSTALL_NAME)
    first_sha = sha256(zip_path)
    first_tree = file_records(package, exclude_manifest=False)
    with tempfile.TemporaryDirectory(
        prefix="gap-node0071-v14-repeat-"
    ) as temporary:
        repeated, _ = build_directory(Path(temporary))
        repeated_zip = Path(temporary) / f"{INSTALL_NAME}.zip"
        deterministic_zip(repeated, repeated_zip, archive_root=INSTALL_NAME)
        if (
            sha256(repeated_zip) != first_sha
            or file_records(repeated, exclude_manifest=False) != first_tree
        ):
            raise BuildError("repeat build differs")
    return {
        "package_tree_equal": True,
        "zip_equal": True,
        "repeat_zip_sha256": first_sha,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=PACKAGE_ROOT)
    args = parser.parse_args()
    output_root = args.output_root.resolve()
    package = output_root / INSTALL_NAME
    zip_path = output_root / f"{INSTALL_NAME}.zip"
    sidecar = Path(str(zip_path) + ".sha256")
    validation_path = output_root / f"{INSTALL_NAME}.validation.json"
    for path in (package, zip_path, sidecar, validation_path):
        if path.exists():
            print(f"refusing to overwrite: {path}")
            return 1
    try:
        package, proof = build_directory(output_root)
        repeated = repeat_build(package, zip_path)
        digest = sha256(zip_path)
        sidecar.write_text(
            f"{digest}  {zip_path.name}\n",
            encoding="ascii",
            newline="\n",
        )
        result = {
            "schema": "gap-node0071-accum-enable-validation-v14",
            "status": "PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "package": str(package),
            "zip": str(zip_path),
            "zip_sha256": digest,
            "zip_size_bytes": zip_path.stat().st_size,
            "sidecar": str(sidecar),
            "bound_source_zip": str(SOURCE_ZIP),
            "bound_source_zip_sha256": SOURCE_SHA256,
            "source_v13_quarantined": True,
            **proof,
            "repeated_build": repeated,
            "functional_rtl_modified": False,
            "numeric_analysis_repeated": False,
            "sum_or_tail_numeric_reexecuted": False,
            "config_rebuilt": False,
            "server_action": False,
        }
        write_json(validation_path, result)
    except Exception as error:
        print(f"GAP v14 build failed: {error}")
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
