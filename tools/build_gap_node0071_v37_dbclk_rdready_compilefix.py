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
from tools import build_gap_node0071_dbclk_rdready_v34_package as source_builder


PACKAGE_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_NAME = "r5_n71_gap_v36_dbclk_rdready_diag"
INSTALL_NAME = "r5_n71_gap_v37_dbclk_rdready_compilefix"
TEST_ID = "r5-gap-node0071-v37-dbclk-rdready-observer-compile-correction"
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_SHA256 = (
    "8835bcad4b54f6c0ec5ad225976d71631492477430e73e77f838df1d76cbf1dd"
)
TRIGGER_RETURN_SHA256 = (
    "2f8a425164bfb4dbe193e644b3a5c040a8b15b92feb62e5edc197902599852ff"
)
TRIGGER_ANALYSIS = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-gap-node0071-v36-return-analysis/report.json"
)
OBSERVER = "tb_probe/native_return_observer.svh"
BAD_IDENTIFIER = "return_obs_rd_spatial_mon"
GOOD_IDENTIFIER = "return_obs_rd_spatial_size_mon"
ALLOWED_CHANGED = {
    "TEST_PACKAGE_MANIFEST.json",
    "README.md",
    "PREPARE_AND_RUN.sh",
    OBSERVER,
    "workload/sca_cfg.json",
    "workload/sca_cfg_D.json",
}
CURRENT_RECEIPTS = {
    "agent_sha256":
        "32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f",
    "plan_sha256_mutable_provenance_only":
        "cdae8da828a4dbd08078325f959dd0acebcc69335c4918064d764709e9a45677",
    "generation_index_sha256":
        "93b66e7986beeaddb01f237710af6874bb4bbfcc4c6c6929563c5e98d8397eb2",
    "server_rule_sha256":
        "14b7e5fa45e5985f9c8bc849acf0a9e768ab4617f3c249addaeb7b5d291a47d1",
    "common_operator_rule_sha256":
        "cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171",
    "ndp_field_rule_sha256":
        "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055",
    "gap_int32_rule_sha256":
        "4c3a88b8c6967812b0b64a550bb92a45117106f34996102335dc26fa1a211f8b",
    "gap_probe_rule_sha256":
        "db377ee2eb7ecc381a44a169a875ccecf2c46711399a4bdabcaef4ba164653d1",
    "exact_uint8_tail_rule_sha256":
        "1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e",
    "server_entry_sha256":
        "e82f51c73f658fa567d47c8ab277c1cfb2cdf6d7cd2b4debefb3d0543e2228ba",
}


class BuildError(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def replace_identity(value: Any) -> Any:
    if isinstance(value, str):
        return value.replace(SOURCE_NAME, INSTALL_NAME)
    if isinstance(value, list):
        return [replace_identity(item) for item in value]
    if isinstance(value, dict):
        return {key: replace_identity(item) for key, item in value.items()}
    return value


def configure_source() -> Any:
    source_builder.SOURCE_NAME = SOURCE_NAME
    source_builder.INSTALL_NAME = INSTALL_NAME
    source_builder.TEST_ID = TEST_ID
    source_builder.SOURCE_ZIP = SOURCE_ZIP
    source_builder.SOURCE_SHA256 = SOURCE_SHA256
    source_builder.TRIGGER_RETURN_SHA256 = TRIGGER_RETURN_SHA256
    source_builder.TRIGGER_ANALYSIS = TRIGGER_ANALYSIS
    root = source_builder.configure_source()
    root.SOURCE_NAME = SOURCE_NAME
    root.INSTALL_NAME = INSTALL_NAME
    root.SOURCE_ZIP = SOURCE_ZIP
    root.SOURCE_SHA256 = SOURCE_SHA256
    return root


def fix_observer(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    before_bad = text.count(BAD_IDENTIFIER)
    before_good = text.count(GOOD_IDENTIFIER)
    if before_bad != 1 or before_good < 4:
        raise BuildError(
            f"observer identifier precondition differs: bad={before_bad} "
            f"good={before_good}"
        )
    text = text.replace(BAD_IDENTIFIER, GOOD_IDENTIFIER, 1)
    path.write_text(text, encoding="utf-8", newline="\n")
    fixed = path.read_text(encoding="utf-8")
    after_bad = fixed.count(BAD_IDENTIFIER)
    after_good = fixed.count(GOOD_IDENTIFIER)
    if after_bad != 0 or after_good != before_good + 1:
        raise BuildError("observer identifier correction did not close")
    return {
        "old_identifier": BAD_IDENTIFIER,
        "new_identifier": GOOD_IDENTIFIER,
        "old_hit_count_before": before_bad,
        "new_hit_count_before": before_good,
        "old_hit_count_after": after_bad,
        "new_hit_count_after": after_good,
    }


def update_manifest(
    package: Path,
    source_manifest: dict[str, Any],
    correction: dict[str, Any],
) -> None:
    path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = replace_identity(source_manifest)
    manifest.update(
        {
            "schema":
                "gap-node0071-dbclk-rdready-observer-compilefix-package-v37",
            "test_id": TEST_ID,
            "package_name": INSTALL_NAME,
            "install_name": INSTALL_NAME,
            "run_name": f"run_{INSTALL_NAME}",
            "return_name": f"{INSTALL_NAME}_return",
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "candidate_release": False,
            "evidence_ceiling": "E2_LOCAL_ONLY",
            "supersedes_package_sha256": SOURCE_SHA256,
            "trigger_return_sha256": TRIGGER_RETURN_SHA256,
            "rule_receipts": {
                **manifest.get("rule_receipts", {}),
                **CURRENT_RECEIPTS,
                "current_match": True,
            },
        }
    )
    manifest["observer_compile_correction_contract"] = {
        "classification":
            "PACKAGE_LOCAL_DELIVERY_SELF_AUDIT_ESCAPE_BEFORE_SIMULATION",
        "trigger_return_sha256": TRIGGER_RETURN_SHA256,
        "trigger_analysis_sha256": sha256(TRIGGER_ANALYSIS),
        "source_package_sha256": SOURCE_SHA256,
        "source_member": OBSERVER,
        "server_compile_error": {
            "tool": "VCS",
            "code": "Error-[IND]",
            "line_in_source_package": 4614,
            "identifier": BAD_IDENTIFIER,
        },
        "minimal_correction": correction,
        "diagnostic_algorithm_changed": False,
        "owner_clock_changed": False,
        "runtime_feature_contract_changed": False,
        "return_schema_changed": False,
        "config_changed": False,
        "timeout_or_backpressure_changed": False,
        "functional_rtl_modified": False,
        "claim_boundary": (
            "The correction only makes the frozen v36 package-local observer "
            "compile. Queue/WR/RD factors remain dynamically unadjudicated."
        ),
    }
    manifest["path_length_budget"] = source_builder.path_budget(package)
    manifest["generation_provenance"].update(
        {
            "tool":
                "tools/build_gap_node0071_v37_dbclk_rdready_compilefix.py",
            "bound_source_package_sha256": SOURCE_SHA256,
            "trigger_return_sha256": TRIGGER_RETURN_SHA256,
            "trigger_analysis_sha256": sha256(TRIGGER_ANALYSIS),
            "package_side_change": (
                "fresh identity and the single package-local observer "
                "identifier correction required by VCS Error-[IND]"
            ),
            "numeric_payload_rebuilt": False,
            "config_semantics_rebuilt": False,
            "functional_rtl_modified": False,
        }
    )
    manifest["applicable_rule_ids"] = sorted(
        set(manifest.get("applicable_rule_ids") or [])
        | {
            "CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001",
            "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
        }
    )
    manifest["files"] = file_records(package)
    write_json(path, manifest)


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    root = configure_source()
    package = root.extract_source(destination)
    source_records = file_records(package, exclude_manifest=False)
    numeric_before = {
        name: record
        for name, record in file_records(
            package / "workload", exclude_manifest=False
        ).items()
        if name not in {"sca_cfg.json", "sca_cfg_D.json"}
    }
    source_manifest = json.loads(
        (package / "TEST_PACKAGE_MANIFEST.json").read_text(encoding="utf-8")
    )
    root.rewrite_identity(package)
    correction = fix_observer(package / OBSERVER)
    (package / "README.md").write_text(
        "# GAP node0071 v37 clk_db RD-readiness observer compile correction\n\n"
        f"Test ID: `{TEST_ID}`.\n\n"
        "This is `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`. It preserves the exact "
        "v36 diagnostic algorithm, clk_db owner-clock sampling, runtime feature "
        "contract, frozen 73-file numeric/workload/config/golden payload, "
        "timeout, backpressure and functional RTL inputs. The only observer "
        "semantic edit replaces the undeclared consumer token "
        f"`{BAD_IDENTIFIER}` with its existing declared monitor "
        f"`{GOOD_IDENTIFIER}`.\n\n"
        "Run exactly:\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX\n"
        "```\n",
        encoding="utf-8",
        newline="\n",
    )
    update_manifest(package, source_manifest, correction)
    numeric_after = {
        name: record
        for name, record in file_records(
            package / "workload", exclude_manifest=False
        ).items()
        if name not in {"sca_cfg.json", "sca_cfg_D.json"}
    }
    if numeric_before != numeric_after or len(numeric_after) != 73:
        raise BuildError("frozen 73-file numeric/workload set drifted")
    final_records = file_records(package, exclude_manifest=False)
    if set(source_records) != set(final_records):
        raise BuildError("package file exact-set changed")
    changed = {
        name for name in source_records
        if source_records[name] != final_records[name]
    }
    if changed != ALLOWED_CHANGED:
        raise BuildError(f"changed path allowlist differs: {sorted(changed)}")
    budget = source_builder.path_budget(package)
    if (
        budget["measured_max_inner_suffix_chars"]
        > budget["max_inner_suffix_chars"]
        or budget["measured_max_inner_depth"] > budget["max_inner_depth"]
        or budget["measured_max_component_chars"]
        > budget["max_component_chars"]
        or budget["identity_repeated_in_inner_path"]
    ):
        raise BuildError(f"path budget failed: {budget}")
    return package, {
        "source_zip_sha256": SOURCE_SHA256,
        "changed_paths": sorted(changed),
        "changed_paths_exact_allowlist": True,
        "observer_correction": correction,
        "frozen_numeric_workload_file_count": 73,
        "frozen_numeric_workload_tree_equal": True,
        "frozen_other_tree_equal": all(
            source_records[name] == final_records[name]
            for name in set(source_records) - ALLOWED_CHANGED
        ),
        "path_length_budget": budget,
    }


def build_zip(output_root: Path) -> dict[str, Any]:
    package, proof = build_directory(output_root)
    zip_path = output_root / f"{INSTALL_NAME}.zip"
    deterministic_zip(package, zip_path, archive_root=INSTALL_NAME)
    digest = sha256(zip_path)
    with tempfile.TemporaryDirectory(
        prefix="gap-node0071-v37-repeat-"
    ) as temporary:
        repeated, _ = build_directory(Path(temporary))
        repeated_zip = Path(temporary) / f"{INSTALL_NAME}.zip"
        deterministic_zip(
            repeated, repeated_zip, archive_root=INSTALL_NAME
        )
        if sha256(repeated_zip) != digest:
            raise BuildError("deterministic second ZIP differs")
        if (
            file_records(repeated, exclude_manifest=False)
            != file_records(package, exclude_manifest=False)
        ):
            raise BuildError("deterministic second tree differs")
    sidecar = Path(str(zip_path) + ".sha256")
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    return {
        "schema": "gap-node0071-dbclk-rdready-v37-build-v1",
        "status": "PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
        "test_id": TEST_ID,
        "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "package": str(package),
        "zip": str(zip_path),
        "zip_size_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "sidecar_sha256": sha256(sidecar),
        **proof,
        "repeat_build": {
            "package_tree_equal": True,
            "zip_equal": True,
            "repeat_zip_sha256": digest,
        },
        "numeric_analysis_repeated": False,
        "workload_rebuilt": False,
        "config_semantics_rebuilt": False,
        "functional_rtl_modified": False,
        "server_action": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=PACKAGE_ROOT)
    args = parser.parse_args()
    output_root = args.output_root.resolve()
    targets = (
        output_root / INSTALL_NAME,
        output_root / f"{INSTALL_NAME}.zip",
        output_root / f"{INSTALL_NAME}.zip.sha256",
        output_root / f"{INSTALL_NAME}.validation.json",
    )
    for path in targets:
        if path.exists():
            print(f"refusing to overwrite: {path}", file=sys.stderr)
            return 1
    try:
        result = build_zip(output_root)
        write_json(targets[-1], result)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except Exception as error:
        import traceback

        traceback.print_exc()
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
