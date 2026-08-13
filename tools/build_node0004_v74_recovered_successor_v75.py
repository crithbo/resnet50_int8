from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.build_node0004_v72_sourcebound_successor_v73 as legacy
import tools.generate_server_source_bound_observer as sourcegen


SOURCE = "r5_n4_hw_v74_sourcebound_epoch_diag"
INSTALL = "r5_n4_hw_v75_sourcebound_collectfix"
SOURCE_SHA = "3a780d8e75768ee241c4cfca0ed738a97b691f6329d8ff247e5f5d4c96ef5400"
RETURN_SHA = "19fbfa3a341a2179dbf35e71ae94938d042fdf05d0b510f95b2b8d3efb728403"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/tested/conv_serialized_node0004" / SOURCE / f"{SOURCE}.zip"
ANALYSIS = ROOT / "outputs/conv_node0004_v74_recovered_return_analysis/report.json"
SB = ROOT / "outputs/conv_node0004_v74_recovered_return_v75_successor/source_bound"
DEFAULT_OUTPUT = ROOT / "outputs/conv_node0004_v74_recovered_return_v75_successor/build"
base = legacy.base


class BuildError(RuntimeError):
    pass


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def configure_legacy() -> None:
    legacy.SOURCE = SOURCE
    legacy.INSTALL = INSTALL
    legacy.SOURCE_SHA = SOURCE_SHA
    legacy.SOURCE_ZIP = SOURCE_ZIP
    legacy.DEFAULT_OUTPUT = DEFAULT_OUTPUT
    legacy.configure()


def prepare_source_bound_assets() -> None:
    prior = ROOT / "outputs/conv_node0004_v72_return_v74_successor/source_bound"
    SB.mkdir(parents=True, exist_ok=True)
    shutil.copy2(prior / "probe_catalog.json", SB / "probe_catalog.json")
    plan = json.loads((prior / "probe_plan.json").read_text(encoding="utf-8"))
    plan["package_id"] = INSTALL
    write_json(SB / "probe_plan.json", plan)
    report = sourcegen.materialize(SB / "probe_catalog.json", SB / "probe_plan.json", SB / "generated")
    write_json(SB / "generation_report.json", report)
    if report.get("pass") is not True:
        raise BuildError(f"source-bound exact generation failed: {report.get('errors')}")
    write_json(SB / "source_bound_observer_generation.json", {
        "schema": "conv-node0004-v75-source-bound-generation-v1",
        "status": "PASS",
        "package_id": INSTALL,
        "generator_sha256": base.sha256(ROOT / "tools/generate_server_source_bound_observer.py"),
        "generation_report_sha256": base.sha256(SB / "generation_report.json"),
        "v74_plan_semantics_reused": True,
        "changed_surface": ["package identity", "generated parser instance token alphabet"],
    })


def replace_function(text: str, name: str, replacement: str) -> str:
    start = text.index(f"def {name}(")
    next_def = text.index("\ndef ", start + 5)
    return text[:start] + replacement.rstrip() + "\n\n" + text[next_def + 1:]


BOUNDED_PREPARE = r'''def _prepare_source_bound_products(run_root: Path) -> dict[str, Any]:
    c0 = run_root / "c0"
    c0.mkdir(parents=True, exist_ok=True)
    sim_log = c0 / "sim.log"
    causal_log = c0 / "source_bound_causal.log"
    decision = c0 / "source_bound_causal_decision.json"
    original_bytes = sim_log.stat().st_size if sim_log.is_file() else 0
    original_sha256 = sha256(sim_log) if sim_log.is_file() else None
    permitted = {
        "ENABLED", "SUMMARY", "CLASS", "TRIGGER", "STALL",
        "RING_PROGRESS", "RING_STATE", "RING_POST",
    }
    records: list[str] = []
    kind_counts: dict[str, int] = {}
    if sim_log.is_file():
        with sim_log.open("r", encoding="utf-8", errors="replace") as stream:
            for raw in stream:
                offset = raw.find("CODEX_PROBE_V1 ")
                if offset < 0:
                    continue
                line = raw[offset:].rstrip("\r\n")
                fields = {}
                for token in line.split(" ")[1:]:
                    if "=" in token:
                        key, value = token.split("=", 1)
                        fields[key] = value
                kind = fields.get("kind")
                if kind not in permitted:
                    continue
                records.append(line)
                kind_counts[kind] = kind_counts.get(kind, 0) + 1
    compact = ("\n".join(records) + ("\n" if records else "")).encode("utf-8")
    # Leave headroom below the shared 8-MiB text-member hard limit.  The
    # generated logger is already event/ring bounded; this projection removes
    # unbounded simulator chatter and the redundant per-event stream.
    if len(compact) > 7 * 1024 * 1024:
        raise DiagnosticRuntimeError("bounded source-bound causal projection exceeds 7 MiB")
    causal_log.write_bytes(compact)
    # The formal return carries the same bounded projection as sim.log.  Full
    # simulator chatter remains execution-local and is summarized by this
    # receipt; it is not required for the causal or result decision.
    sim_log.write_bytes(compact)
    package_root = Path(__file__).resolve().parents[1]
    parser = package_root / "package_tools/source_bound_causal_parser.py"
    completed = subprocess.run(
        [sys.executable, str(parser), "--log", str(causal_log), "--output", str(decision)],
        text=True,
        capture_output=True,
        check=False,
    )
    if not decision.is_file():
        raise DiagnosticRuntimeError("source-bound parser did not produce canonical decision")
    parsed = load_json(decision)
    return {
        "schema": "source-bound-bounded-collector-receipt-v1",
        "source_bound_record_count": len(records),
        "kind_counts": kind_counts,
        "original_sim_log_bytes": original_bytes,
        "original_sim_log_sha256": original_sha256,
        "bounded_log_bytes": len(compact),
        "bounded_log_sha256": hashlib.sha256(compact).hexdigest(),
        "bounded_log_limit_bytes": 7 * 1024 * 1024,
        "sim_log_equals_causal_log": True,
        "parser_exit_status": completed.returncode,
        "parser_stdout": completed.stdout.strip(),
        "parser_stderr": completed.stderr.strip(),
        "parser_decision": parsed.get("decision"),
    }'''


def patch_runtime(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "import hashlib\n" not in text:
        text = text.replace("import argparse\n", "import argparse\nimport hashlib\n", 1)
    text = replace_function(text, "_prepare_source_bound_products", BOUNDED_PREPARE)
    path.write_text(text, encoding="utf-8", newline="\n")


def copy_generated_assets(package: Path) -> None:
    mapping = {
        SB / "probe_catalog.json": package / "diagnostics/source_bound_probe_catalog.json",
        SB / "probe_plan.json": package / "diagnostics/source_bound_probe_plan.json",
        SB / "generated/source_bound_causal_observer.svh": package / "tb_probe/source_bound_causal_observer.svh",
        SB / "generated/source_bound_causal_parser.py": package / "package_tools/source_bound_causal_parser.py",
        SB / "generated/source_bound_probe_binding.json": package / "diagnostics/source_bound_probe_binding.json",
        SB / "generation_report.json": package / "diagnostics/source_bound_observer_generation_report.json",
        SB / "source_bound_observer_generation.json": package / "diagnostics/source_bound_observer_generation.json",
    }
    for source, target in mapping.items():
        shutil.copy2(source, target)


def build_directory(output: Path) -> Path:
    configure_legacy()
    with tempfile.TemporaryDirectory(prefix="node0004-v75-source-") as td:
        source = base.extract_source(Path(td))
        package = output / INSTALL
        if package.exists():
            raise BuildError(f"refusing to overwrite {package}")
        shutil.copytree(source, package)
    base.replace_identity(package)
    copy_generated_assets(package)
    patch_runtime(package / "package_tools/node0004_hang_localization_runtime_v7.py")
    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update({
        "install_name": INSTALL,
        "source_package_sha256": SOURCE_SHA,
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
        "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "candidate_release": False,
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": False,
        "mapping_rebuilt": False,
        "bitstream_rebuilt": False,
        "execplan_rebuilt": False,
        "sca_semantics_rebuilt": False,
        "functional_rtl_modified": False,
        "server_action": False,
    })
    receipts = manifest.setdefault("active_receipts", {})
    receipts["source_bound_generator_sha256"] = base.sha256(ROOT / "tools/generate_server_source_bound_observer.py")
    receipts["server_rule_sha256"] = "b26241ac581b7b8d1fc97692ef11c40e8fd2e8af42b80233ff0d6839b44d2957"
    receipts["generation_index_sha256"] = "5f59b4f5d79b4f605617843d06706caf83b5acd781fb11ce9f5c9b27f243a60a"
    rules = receipts.setdefault("rules", [])
    for rule in (
        "CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001",
        "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
        "CDA-SERVER-RETURN-FIXED-SIMRESULT-ATOMIC-PUBLISH-001",
    ):
        if rule not in rules:
            rules.append(rule)
    write_json(package / "provenance/v74_recovered_to_v75_collectfix.json", {
        "schema": "conv-node0004-v74-recovered-to-v75-v1",
        "source_package_sha256": SOURCE_SHA,
        "recovered_return_sha256": RETURN_SHA,
        "return_analysis_sha256": base.sha256(ANALYSIS),
        "fresh_execution": False,
        "last_proven_good": "D_WRITE_DATA_ACCEPTED_WITH_21_DETAILED_NONTERMINAL_ACCEPTS_AND_CANONICAL_D_WDATA_36",
        "first_divergence": "FIRST_TERMINAL_D_WRITE_DATA_AND_SLICE_FINISH_ABSENT_AFTER_LAST_TAG_INDEX4_AND_BUFFER_LAST_INDEX5_STATE",
        "functional_root_cause": "UNRESOLVED",
        "package_local_escape_fixed": [
            "generated parser accepts []$ in SystemVerilog percent-m instance values",
            "collector publishes an automatic bounded causal projection rather than the full simulator log",
        ],
        "frozen": ["numeric/W3/qparams/tail/workload/config/golden", "timeout/backpressure", "functional RTL/ISA/hardware/active ndp-sim"],
    })
    base.refresh_receipts(manifest)
    legacy.refresh_path_budget(package, manifest)
    write_json(manifest_path, manifest)
    manifest["files"] = base.package_records(package)
    write_json(manifest_path, manifest)
    manifest["files"] = base.package_records(package)
    write_json(manifest_path, manifest)
    return package


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    ns = ap.parse_args()
    prepare_source_bound_assets()
    output = ns.output_root.resolve()
    output.mkdir(parents=True, exist_ok=True)
    package = build_directory(output)
    archive = output / f"{INSTALL}.zip"
    base.deterministic_zip(package, archive)
    digest = base.sha256(archive)
    with tempfile.TemporaryDirectory(prefix="node0004-v75-repeat-") as td:
        repeat = build_directory(Path(td))
        repeat_zip = Path(td) / f"{INSTALL}.zip"
        base.deterministic_zip(repeat, repeat_zip)
        deterministic = base.sha256(repeat_zip) == digest
    if not deterministic:
        raise BuildError("deterministic rebuild differs")
    sidecar = output / f"{INSTALL}.zip.sha256"
    sidecar.write_text(f"{digest}  {archive.name}\n", encoding="ascii", newline="\n")
    report = {
        "schema": "conv-node0004-v75-build-v1",
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_AUDITS",
        "zip": str(archive), "zip_bytes": archive.stat().st_size, "zip_sha256": digest,
        "sidecar": str(sidecar), "deterministic_rebuild_equal": deterministic,
        "source_v74_sha256": SOURCE_SHA, "recovered_return_sha256": RETURN_SHA,
        "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "numeric_analysis_repeated": False, "node0004_workload_rebuilt": False,
        "configuration_rebuilt": False, "functional_rtl_modified": False, "server_action": False,
    }
    write_json(output / f"{INSTALL}.build.json", report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
