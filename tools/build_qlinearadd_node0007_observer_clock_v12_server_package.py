from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_qlinearadd_node0007_server_package import deterministic_zip
from tools.qlinearadd_node0007_server_runtime import file_records, preflight, write_json
from tools import build_qlinearadd_node0007_minimal_preflight_v11_server_package as v11


INSTALL_NAME = "r5_qadd_n7_obsclk_v12"
SOURCE_NAME = "r5_qadd_n7_minpre_v11"
PACKAGE_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_ZIP_SHA256 = "d8a20d54ca83d0607a79740be79f632fce6115f9d1b6e58fb1e9f40d60c828d1"
INDEX = v11.INDEX
INDEX_SHA256 = v11.INDEX_SHA256
SERVER_RULE = v11.SERVER_RULE
SERVER_RULE_SHA256 = v11.SERVER_RULE_SHA256
QADD_RULE = v11.QADD_RULE
QADD_RULE_SHA256 = v11.QADD_RULE_SHA256
TAIL_REL = Path("tb_probe/qlinearadd_node0007_first_request_observer_tail_v9.svh")
VALIDATION_PATH = PACKAGE_ROOT / f"{INSTALL_NAME}.validation.json"
REPORT_REL = (
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-observer-clock-v12/report.json"
)


class BuildError(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _rule_ids(path: Path) -> list[str]:
    return re.findall(r"规则 ID：`([^`]+)`", path.read_text(encoding="utf-8"))


def _assert_receipts() -> None:
    expected = {
        SOURCE_ZIP: SOURCE_ZIP_SHA256,
        INDEX: INDEX_SHA256,
        SERVER_RULE: SERVER_RULE_SHA256,
        QADD_RULE: QADD_RULE_SHA256,
    }
    drift = {
        str(path): {"expected": wanted, "actual": sha256(path)}
        for path, wanted in expected.items()
        if not path.is_file() or sha256(path) != wanted
    }
    if drift:
        raise BuildError(f"immutable receipt drift: {drift}")


def _extract(destination: Path) -> Path:
    package = destination / INSTALL_NAME
    with tempfile.TemporaryDirectory(prefix="q12-source-") as raw:
        staging = Path(raw)
        with zipfile.ZipFile(SOURCE_ZIP) as archive:
            bad = archive.testzip()
            if bad is not None:
                raise BuildError(f"source ZIP CRC failure: {bad}")
            archive.extractall(staging)
        source = staging / SOURCE_NAME
        if not source.is_dir():
            raise BuildError("source ZIP root differs")
        shutil.move(str(source), str(package))
    return package


def _replace_namespace(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    path.write_text(
        text.replace(SOURCE_NAME, INSTALL_NAME),
        encoding="utf-8",
        newline="\n",
    )


def _fix_tail_clock_binding(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    declaration = "    longint unsigned qadd_fr_slice_start_count;\n"
    if text.count(declaration) != 1:
        raise BuildError("tail counter declaration anchor differs")
    text = text.replace(
        declaration,
        declaration + "    longint unsigned qadd_fr_clk_sg_edge_count;\n",
    )
    initial = "        qadd_fr_slice_start_count = 0;\n"
    if text.count(initial) != 1:
        raise BuildError("tail initial anchor differs")
    text = text.replace(
        initial,
        initial + "        qadd_fr_clk_sg_edge_count = 0;\n",
    )
    active_anchor = (
        "        ) begin\n"
        "            if (\n"
        "                qadd_fr_slice_start_run_mon\n"
    )
    if text.count(active_anchor) != 1:
        raise BuildError("tail clk_sg active anchor differs")
    text = text.replace(
        active_anchor,
        "        ) begin\n"
        "            qadd_fr_clk_sg_edge_count++;\n"
        "            if (\n"
        "                qadd_fr_slice_start_run_mon\n",
    )

    print_start = text.index(
        "            if (\n"
        "                return_obs_active_cycles != 0 &&\n"
        "                (return_obs_active_cycles %\n"
    )
    print_end_marker = "                $fflush(return_obs_fd);\n            end\n"
    print_end = text.index(print_end_marker, print_start) + len(print_end_marker)
    print_block = text[print_start:print_end]
    text = text[:print_start] + text[print_end:]

    logging_block = print_block.replace(
        '                    "%0t | FIRST_REQUEST_CHAIN |',
        '                    "%0t | FIRST_REQUEST_CHAIN |',
        1,
    )
    logging_block += (
        "            $fdisplay(\n"
        "                return_obs_fd,\n"
        '                "%0t | FIRST_REQUEST_CLOCK | slice=%0d '
        'active_cycles=%0d clk_sg_edges=%0d clk_sg_level=%0b",\n'
        "                $time,\n"
        "                return_obs_slice_id,\n"
        "                return_obs_active_cycles,\n"
        "                qadd_fr_clk_sg_edge_count,\n"
        "                u_NDP_Top_new.clk_sg\n"
        "            );\n"
        "            $fflush(return_obs_fd);\n"
    )
    text += (
        "\n"
        "    // Print from the ungated base-observer clock. Qualified counters\n"
        "    // remain owned by clk_sg; this block only snapshots them and also\n"
        "    // proves whether clk_sg itself has produced an edge after EXEC_START.\n"
        "    always @(negedge u_NDP_Top_new.clk_db) begin\n"
        "        if (\n"
        "            u_NDP_Top_new.rst_n_db &&\n"
        "            return_obs_enabled &&\n"
        "            return_obs_active &&\n"
        "            return_obs_fd != 0\n"
        "        ) begin\n"
        + logging_block
        + "        end\n"
        "    end\n"
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def build_directory(destination: Path) -> Path:
    _assert_receipts()
    package = _extract(destination)
    for relative in (
        Path("TEST_PACKAGE_MANIFEST.json"),
        Path("workload/runtime/sca_cfg.json"),
        Path("workload/runtime/sca_cfg_D.json"),
    ):
        _replace_namespace(package / relative)
    _fix_tail_clock_binding(package / TAIL_REL)

    (package / "README.md").write_text(
        "# QLinearAdd node0007 first-request observer clock fix v12\n\n"
        "Run exactly once:\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX\n"
        "```\n\n"
        "This diagnostic-only successor preserves the frozen workload and "
        "configuration from v11. Qualified LC/MSE counters remain sampled in "
        "clk_sg, while rate-limited snapshots are emitted on the ungated clk_db "
        "observer clock. FIRST_REQUEST_CLOCK reports clk_sg edge count so a "
        "stopped gated clock cannot suppress the diagnostic stream.\n",
        encoding="utf-8",
        newline="\n",
    )

    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema": "qlinearadd-node0007-first-request-observer-clock-server-package-v12",
            "install_name": INSTALL_NAME,
            "source_package": {
                "path": SOURCE_ZIP.relative_to(ROOT).as_posix(),
                "sha256": SOURCE_ZIP_SHA256,
                "status": "QUARANTINED_FIRST_REQUEST_OBSERVER_CLOCK_DOMAIN_BINDING",
                "numeric_and_workload_semantics_unchanged": True,
            },
            "observer_clock_binding_fix": {
                "functional_fix": False,
                "qualified_counter_clock": "u_NDP_Top_new.clk_sg",
                "snapshot_clock": "negedge u_NDP_Top_new.clk_db",
                "cross_domain_modulo_trigger_removed": True,
                "clk_sg_edge_counter_returned": True,
                "first_request_clock_record": "FIRST_REQUEST_CLOCK",
                "frozen_workload_and_configuration_unchanged": True,
            },
        }
    )
    manifest["first_request_internal_observability"][
        "tail_sha256"
    ] = sha256(package / TAIL_REL)
    manifest["final_zip_rule_self_audit"] = {
        "rule_id": "CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001",
        "rule_receipts": {
            "generation_index": {
                "path": INDEX.relative_to(ROOT).as_posix(),
                "sha256": INDEX_SHA256,
                "current_match": True,
            },
            "server_package_rule": {
                "path": SERVER_RULE.relative_to(ROOT).as_posix(),
                "sha256": SERVER_RULE_SHA256,
                "current_match": True,
            },
            "qlinearadd_rule": {
                "path": QADD_RULE.relative_to(ROOT).as_posix(),
                "sha256": QADD_RULE_SHA256,
                "current_match": True,
            },
        },
        "applicable_server_rule_ids": _rule_ids(SERVER_RULE),
        "applicable_qlinearadd_rule_ids": _rule_ids(QADD_RULE),
        "direct_final_zip_and_sidecar_validation_required": True,
        "all_required_negative_controls_required": True,
        "pass_field": "FINAL_ZIP_RULE_SELF_AUDIT_PASS",
        "errors_must_equal": 0,
        "validator": "tools/validate_qlinearadd_node0007_observer_clock_v12.py",
        "report": REPORT_REL,
    }
    manifest["provenance"]["generation_index"] = {
        "path": INDEX.relative_to(ROOT).as_posix(),
        "sha256": INDEX_SHA256,
    }
    manifest["provenance"]["server_package_rule"] = {
        "path": SERVER_RULE.relative_to(ROOT).as_posix(),
        "sha256": SERVER_RULE_SHA256,
    }
    manifest["provenance"]["qlinearadd_rule"] = {
        "path": QADD_RULE.relative_to(ROOT).as_posix(),
        "sha256": QADD_RULE_SHA256,
    }
    manifest["files"] = file_records(package)
    write_json(manifest_path, manifest)
    preflight(package)
    return package


def _build_once(destination: Path) -> tuple[Path, Path, dict[str, Any]]:
    package = build_directory(destination)
    output = destination / f"{INSTALL_NAME}.zip"
    deterministic_zip(package, output)
    return package, output, file_records(package, exclude_manifest=False)


def main() -> int:
    package = PACKAGE_ROOT / INSTALL_NAME
    output = PACKAGE_ROOT / f"{INSTALL_NAME}.zip"
    sidecar = Path(str(output) + ".sha256")
    for path in (package, output, sidecar, VALIDATION_PATH):
        if path.exists():
            print(f"refusing to overwrite: {path}", file=sys.stderr)
            return 1
    try:
        package, built, records = _build_once(PACKAGE_ROOT)
        if built != output:
            raise BuildError("unexpected output path")
        with tempfile.TemporaryDirectory(prefix="qadd-v12-repeat-") as raw:
            _, repeat_zip, repeat_records = _build_once(Path(raw))
            repeated = {
                "package_tree_equal": records == repeat_records,
                "zip_equal": sha256(output) == sha256(repeat_zip),
                "repeat_zip_sha256": sha256(repeat_zip),
            }
        if not repeated["package_tree_equal"] or not repeated["zip_equal"]:
            raise BuildError("deterministic rebuild differs")
        digest = sha256(output)
        sidecar.write_text(f"{digest}  {output.name}\n", encoding="ascii", newline="\n")
        receipt: dict[str, Any] = {
            "schema": "qlinearadd-node0007-observer-clock-build-v1",
            "status": "PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
            "package": package.relative_to(ROOT).as_posix(),
            "zip": output.relative_to(ROOT).as_posix(),
            "zip_sha256": digest,
            "sidecar": sidecar.relative_to(ROOT).as_posix(),
            "sidecar_sha256": sha256(sidecar),
            "source_zip": SOURCE_ZIP.relative_to(ROOT).as_posix(),
            "source_zip_sha256": SOURCE_ZIP_SHA256,
            "file_count": len(records),
            "repeated_build": repeated,
            "numeric_analysis_repeated": False,
            "workload_analysis_repeated": False,
            "consumed_reuse_assets": True,
            "functional_rtl_modified": False,
            "server_action": False,
        }
        write_json(VALIDATION_PATH, receipt)
    except Exception as exc:
        print(f"package build failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
