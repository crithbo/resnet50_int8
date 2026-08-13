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

import tools.build_node0004_v71_token_origin_accept_successor_v72 as previous


SOURCE = "r5_n4_hw_v72_token_origin_accept_diag"
INSTALL = "r5_n4_hw_v73_sourcebound_epoch_diag"
SOURCE_SHA = "1cd8c9f55f8120e0c40599c54f6f385fbf159957bf74eafa0055c0ad4feed585"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE}.zip"
RETURN_SHA = "d645137a8fb4e099061dd5591a1024c3bedff8749b15636d526c8f0d2bd24696"
ANALYSIS = ROOT / "outputs/conv_node0004_v72_return_analysis/report.json"
SB = ROOT / "outputs/conv_node0004_v72_return_v73_successor/source_bound"
DEFAULT_OUTPUT = ROOT / "outputs/conv_node0004_v72_return_v73_successor/build"
base = previous.base


class BuildError(RuntimeError):
    pass


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def configure() -> None:
    previous.SOURCE = SOURCE
    previous.INSTALL = INSTALL
    previous.SOURCE_SHA = SOURCE_SHA
    previous.SOURCE_ZIP = SOURCE_ZIP
    previous.DEFAULT_OUTPUT = DEFAULT_OUTPUT
    previous.configure()


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise BuildError(f"{label} replacement count={text.count(old)}")
    return text.replace(old, new, 1)


def patch_runner(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        'VCS_EXTRA_OPTS="+define+NATIVE_RETURN_OBSERVER_ENABLE +incdir+$package_root/tb_probe"',
        'VCS_EXTRA_OPTS="+define+NATIVE_RETURN_OBSERVER_ENABLE +incdir+$package_root/tb_probe $package_root/tb_probe/source_bound_causal_observer.svh"',
        "compile source binding",
    )
    marker = "+RETURN_OBS_TOKEN_ORIGIN_ACCEPT_LIMIT=128"
    if text.count(marker) != 2:
        raise BuildError(f"sim argv insertion anchor count={text.count(marker)}")
    text = text.replace(marker, marker + " +CODEX_CAUSAL_OBSERVER")
    # These variables are consumed by the package-local collector and make the
    # two required return products explicit in the exact final runner.
    anchor = 'simv="$compile_root/sim_results/simv"\n'
    insertion = (
        anchor
        + 'source_bound_causal_log="$run_root/c0/source_bound_causal.log"\n'
        + 'source_bound_causal_decision="$run_root/c0/source_bound_causal_decision.json"\n'
    )
    text = replace_once(text, anchor, insertion, "source-bound return products")
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_runtime(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = replace_once(text, "import shutil\nimport zipfile\n", "import shutil\nimport subprocess\nimport sys\nimport zipfile\n", "runtime imports")
    collect_anchor = "\ndef collect(\n"
    helper = r'''
def _prepare_source_bound_products(run_root: Path) -> dict[str, Any]:
    c0 = run_root / "c0"
    c0.mkdir(parents=True, exist_ok=True)
    sim_log = c0 / "sim.log"
    causal_log = c0 / "source_bound_causal.log"
    decision = c0 / "source_bound_causal_decision.json"
    records: list[str] = []
    if sim_log.is_file():
        for line in sim_log.read_text(encoding="utf-8", errors="replace").splitlines():
            offset = line.find("CODEX_PROBE_V1 ")
            if offset >= 0:
                records.append(line[offset:])
    causal_log.write_text("\n".join(records) + ("\n" if records else ""), encoding="utf-8", newline="\n")
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
    return {
        "source_bound_record_count": len(records),
        "parser_exit_status": completed.returncode,
        "parser_stdout": completed.stdout.strip(),
        "parser_stderr": completed.stderr.strip(),
    }

'''
    if text.count(collect_anchor) != 1:
        raise BuildError("runtime collect anchor differs")
    text = text.replace(collect_anchor, "\n" + helper + "def collect(\n", 1)
    items_anchor = "    records: list[dict[str, Any]] = []\n    items = (\n"
    replacement = (
        "    source_bound = _prepare_source_bound_products(run_root)\n"
        "    write_json(evidence_root / \"source_bound_parser_receipt.json\", source_bound)\n"
        "    records: list[dict[str, Any]] = []\n"
        "    items = (\n"
        "        (evidence_root / \"source_bound_parser_receipt.json\", \"evidence/source_bound_parser_receipt.json\", True),\n"
        "        (run_root / \"c0/source_bound_causal.log\", \"runs/c0/source_bound_causal.log\", True),\n"
        "        (run_root / \"c0/source_bound_causal_decision.json\", \"runs/c0/source_bound_causal_decision.json\", True),\n"
    )
    text = replace_once(text, items_anchor, replacement, "runtime return allowlist")
    path.write_text(text, encoding="utf-8", newline="\n")


def copy_source_bound_assets(package: Path) -> None:
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
        if not source.is_file():
            raise BuildError(f"source-bound input missing: {source}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    write_json(package / "diagnostics/source_bound_final_zip_contract.json", {
        "schema": "server-source-bound-final-zip-contract-v1",
        "rule_id": "CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001",
        "enforcement": "required_next_fresh",
        "members": {
            "catalog": "diagnostics/source_bound_probe_catalog.json",
            "plan": "diagnostics/source_bound_probe_plan.json",
            "observer": "tb_probe/source_bound_causal_observer.svh",
            "parser": "package_tools/source_bound_causal_parser.py",
            "binding": "diagnostics/source_bound_probe_binding.json",
            "generation_report": "diagnostics/source_bound_observer_generation_report.json",
            "runner": "PREPARE_AND_RUN.sh",
        },
        "compile_observer_token": "source_bound_causal_observer.svh",
        "runtime_plusarg": "+CODEX_CAUSAL_OBSERVER",
        "return_log_token": "source_bound_causal.log",
        "return_decision_token": "source_bound_causal_decision.json",
        "claim_boundary": "Generated source-bound Memory_AG/Buffer_AG chronology only; unchanged legacy observer remains corroboration and does not define this changed decision path.",
    })


def refresh_path_budget(package: Path, manifest: dict) -> None:
    relatives = [p.relative_to(package).as_posix() for p in package.rglob("*") if p.is_file()]
    longest = max(relatives, key=len)
    budget = manifest["path_length_budget"]
    limit = budget["absolute_path_limit_chars"]
    contract = json.loads((package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json").read_text(encoding="utf-8"))
    root_chars = contract["path_budget"]["declared_target_root_max_chars"]
    projected = root_chars + 1 + len(longest)
    budget.update({
        "longest_projected_relative_path": longest,
        "longest_projected_relative_path_chars": len(longest),
        "max_projected_absolute_path_chars": projected,
        "pass": projected <= limit,
    })
    contract["path_budget"]["max_projected_absolute_path_chars"] = projected
    write_json(package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json", contract)


def build_directory(output: Path) -> Path:
    configure()
    with tempfile.TemporaryDirectory(prefix="node0004-v73-source-") as td:
        source = base.extract_source(Path(td))
        package = output / INSTALL
        if package.exists():
            raise BuildError(f"refusing to overwrite {package}")
        shutil.copytree(source, package)
    base.replace_identity(package)
    copy_source_bound_assets(package)
    patch_runner(package / "PREPARE_AND_RUN.sh")
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
        "configuration_rebuilt_in_this_successor": False,
        "mapping_rebuilt": False,
        "bitstream_rebuilt": False,
        "execplan_rebuilt": False,
        "sca_semantics_rebuilt": False,
        "functional_rtl_modified": False,
        "server_action": False,
    })
    manifest.setdefault("diagnostic_features", {})["CODEX_CAUSAL_OBSERVER"] = {
        "runtime_enable_parameter": "+CODEX_CAUSAL_OBSERVER",
        "observer": "tb_probe/source_bound_causal_observer.svh",
        "parser": "package_tools/source_bound_causal_parser.py",
        "log": "runs/c0/source_bound_causal.log",
        "decision": "runs/c0/source_bound_causal_decision.json",
        "generation_mode": "SOURCE_BOUND_SYMBOL_ID_EXACT_REGENERATION",
        "rule_id": "CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001",
        "changed_decision_path": True,
    }
    receipts = manifest.setdefault("active_receipts", {})
    receipts["source_bound_generator_sha256"] = "efbd5a18cf214bc06aac1bbf096a0cb61b9dd27858f32b25e0d0c71feaca0a6b"
    receipts["source_bound_schema_catalog_sha256"] = "a03cda5c890e25583fc8411befff1b47e1724fbc739d1e060e9b489b808071b4"
    receipts["source_bound_schema_plan_sha256"] = "4396cf7c89bbcf5b2a2909dedf484be58495ec9cda5dc7c0d61732ef37e55c2f"
    receipts["source_bound_final_zip_schema_sha256"] = "992b105e68cd3c429815b6019e72c98bc81b0aaed8bc1b887774dde9a0f79059"
    rules = receipts.setdefault("rules", [])
    if "CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001" not in rules:
        rules.append("CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001")
    base.write_json(package / "provenance/v72_to_source_bound_successor.json", {
        "schema": "node0004-v72-to-source-bound-successor-v1",
        "successor_install_name": INSTALL,
        "source_v72_sha256": SOURCE_SHA,
        "v72_return_sha256": RETURN_SHA,
        "v72_analysis_sha256": base.sha256(ANALYSIS),
        "last_proven_good": "V72_ACCEPTED_WRITE_QUALIFICATION_CLOSES_V71_ESCAPE_AND_MEMORY_QUEUE_DRAINS_9_OF_9",
        "first_divergence": "POST_DESCRIPTOR18_MEMORY_QUEUE_EMPTY_AT_INPUT1_INDEX7_WHILE_BUFFER_QUEUE_HAS_27_ACCEPTS_23_POPS_AND_FOUR_RESIDENT_TOKENS",
        "root_cause": "UNRESOLVED_EXACT_SOURCE_TO_CONSUMER_TOKEN_OWNERSHIP",
        "changed_surface": ["fresh identity", "generated source-bound observer", "generated parser", "return products"],
        "frozen": ["numeric/W3/qparams/tail/workload/config/golden", "timeout/backpressure", "functional RTL/ISA/hardware/active ndp-sim"],
    })
    base.refresh_receipts(manifest)
    refresh_path_budget(package, manifest)
    write_json(manifest_path, manifest)
    manifest["files"] = base.package_records(package)
    write_json(manifest_path, manifest)
    manifest["files"] = base.package_records(package)
    write_json(manifest_path, manifest)
    return package


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output_root.resolve()
    output.mkdir(parents=True, exist_ok=True)
    package = build_directory(output)
    archive = output / f"{INSTALL}.zip"
    base.deterministic_zip(package, archive)
    digest = base.sha256(archive)
    with tempfile.TemporaryDirectory(prefix="node0004-v73-repeat-") as td:
        repeat = build_directory(Path(td))
        repeat_zip = Path(td) / f"{INSTALL}.zip"
        base.deterministic_zip(repeat, repeat_zip)
        deterministic = base.sha256(repeat_zip) == digest
    if not deterministic:
        raise BuildError("deterministic rebuild differs")
    sidecar = output / f"{INSTALL}.zip.sha256"
    sidecar.write_text(f"{digest}  {archive.name}\n", encoding="ascii", newline="\n")
    report = {
        "schema": "node0004-v72-to-source-bound-successor-build-v1",
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_AUDITS",
        "zip": str(archive),
        "zip_bytes": archive.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "deterministic_rebuild_equal": deterministic,
        "source_v72_sha256": SOURCE_SHA,
        "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": False,
        "functional_rtl_modified": False,
        "server_action": False,
    }
    write_json(output / f"{INSTALL}.build.json", report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
