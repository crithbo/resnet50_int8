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

import tools.build_node0004_v74_recovered_successor_v75 as prior
import tools.generate_server_source_bound_observer as sourcegen


SOURCE = "r5_n4_hw_v75_sourcebound_collectfix"
INSTALL = "r5_n4_hw_v76_sourcebound_boundfix"
SOURCE_SHA = "322214d94af5bdfe75e509612da190a205e7cf4324f9e31dcc6e052bb9b3126c"
RETURN_SHA = "1797f0f684a3e8c69b141167139aa22829b94a8dcc3be01119da1085dba91710"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE}.zip"
ANALYSIS = ROOT / "outputs/conv_node0004_v75_return_analysis/report.json"
OUT = ROOT / "outputs/conv_node0004_v75_return_v76_successor"
SB = OUT / "source_bound"
DEFAULT_OUTPUT = OUT / "build"
base = prior.base

SERVER_RULE = ROOT / ".agents/rules/服务器测试包生成规则.md"
INDEX_RULE = ROOT / ".agents/rules/生成前必读索引.md"
README = ROOT / "NDP_copy01/README_HARDWARE_SIM_ENTRY.md"


class BuildError(RuntimeError):
    pass


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def configure_prior() -> None:
    prior.SOURCE = SOURCE
    prior.INSTALL = INSTALL
    prior.SOURCE_SHA = SOURCE_SHA
    prior.SOURCE_ZIP = SOURCE_ZIP
    prior.DEFAULT_OUTPUT = DEFAULT_OUTPUT
    prior.configure_legacy()


def replace_function(text: str, name: str, replacement: str) -> str:
    start = text.index(f"def {name}(")
    next_def = text.index("\ndef ", start + 5)
    return text[:start] + replacement.rstrip() + "\n\n" + text[next_def + 1 :]


BOUNDED_PREPARE_V2 = r'''def _prepare_source_bound_products(run_root: Path) -> dict[str, Any]:
    from collections import defaultdict, deque

    c0 = run_root / "c0"
    c0.mkdir(parents=True, exist_ok=True)
    sim_log = c0 / "sim.log"
    causal_log = c0 / "source_bound_causal.log"
    decision = c0 / "source_bound_causal_decision.json"
    original_bytes = sim_log.stat().st_size if sim_log.is_file() else 0
    original_sha256 = sha256(sim_log) if sim_log.is_file() else None
    core_kinds = {"ENABLED", "SUMMARY", "CLASS", "TRIGGER", "STALL"}
    ring_kinds = {"RING_PROGRESS", "RING_STATE", "RING_POST"}
    core_records: list[tuple[int, str]] = []
    ring_heads: dict[tuple[str, str, str], list[tuple[int, str]]] = defaultdict(list)
    ring_tails: dict[tuple[str, str, str], deque[tuple[int, str]]] = defaultdict(lambda: deque(maxlen=4))
    input_kind_counts: dict[str, int] = {}
    ordinal = 0
    if sim_log.is_file():
        with sim_log.open("r", encoding="utf-8", errors="replace") as stream:
            for raw in stream:
                offset = raw.find("CODEX_PROBE_V1 ")
                if offset < 0:
                    continue
                line = raw[offset:].rstrip("\r\n")
                parsed = {}
                for token in line.split(" ")[1:]:
                    if "=" in token:
                        key, value = token.split("=", 1)
                        parsed[key] = value
                kind = parsed.get("kind")
                if kind not in core_kinds | ring_kinds:
                    continue
                input_kind_counts[kind] = input_kind_counts.get(kind, 0) + 1
                item = (ordinal, line)
                ordinal += 1
                if kind in core_kinds:
                    core_records.append(item)
                    continue
                key = (kind, parsed.get("boundary", "<none>"), parsed.get("instance", "<none>"))
                if len(ring_heads[key]) < 2:
                    ring_heads[key].append(item)
                ring_tails[key].append(item)

    def materialize(head_count: int, tail_count: int) -> tuple[bytes, list[tuple[int, str]]]:
        selected: dict[int, str] = {index: line for index, line in core_records}
        for key in sorted(ring_heads):
            for index, line in ring_heads[key][:head_count]:
                selected[index] = line
            for index, line in list(ring_tails[key])[-tail_count:] if tail_count else []:
                selected[index] = line
        ordered = sorted(selected.items())
        payload = ("\n".join(line for _, line in ordered) + ("\n" if ordered else "")).encode("utf-8")
        return payload, ordered

    limit = 7 * 1024 * 1024
    policy = None
    compact = b""
    retained: list[tuple[int, str]] = []
    for head_count, tail_count in ((2, 4), (1, 2), (0, 1)):
        compact, retained = materialize(head_count, tail_count)
        if len(compact) <= limit:
            policy = {"ring_head_per_instance_boundary_kind": head_count, "ring_tail_per_instance_boundary_kind": tail_count}
            break
    if policy is None:
        raise DiagnosticRuntimeError("source-bound causal projection exceeds 7 MiB after deterministic ring reduction")
    retained_kind_counts: dict[str, int] = {}
    for _, line in retained:
        parsed = {}
        for token in line.split(" ")[1:]:
            if "=" in token:
                key, value = token.split("=", 1)
                parsed[key] = value
        kind = parsed.get("kind", "UNKNOWN")
        retained_kind_counts[kind] = retained_kind_counts.get(kind, 0) + 1
    causal_log.write_bytes(compact)
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
    parsed_decision = load_json(decision)
    if completed.returncode != 0 or parsed_decision.get("decision") == "EVIDENCE_INCOMPLETE":
        raise DiagnosticRuntimeError("bounded source-bound parser result remains incomplete")
    return {
        "schema": "source-bound-bounded-collector-receipt-v2",
        "source_bound_input_record_count": sum(input_kind_counts.values()),
        "source_bound_retained_record_count": len(retained),
        "source_bound_dropped_ring_record_count": sum(input_kind_counts.get(kind, 0) for kind in ring_kinds) - sum(retained_kind_counts.get(kind, 0) for kind in ring_kinds),
        "input_kind_counts": input_kind_counts,
        "retained_kind_counts": retained_kind_counts,
        "ring_group_count": len(ring_heads),
        "ring_retention_policy": policy,
        "original_sim_log_bytes": original_bytes,
        "original_sim_log_sha256": original_sha256,
        "bounded_log_bytes": len(compact),
        "bounded_log_sha256": hashlib.sha256(compact).hexdigest(),
        "bounded_log_limit_bytes": limit,
        "sim_log_equals_causal_log": True,
        "parser_exit_status": completed.returncode,
        "parser_stdout": completed.stdout.strip(),
        "parser_stderr": completed.stderr.strip(),
        "parser_decision": parsed_decision.get("decision"),
        "matching_candidate_ids": parsed_decision.get("matching_candidate_ids", []),
    }'''


def regenerate_source_bound(package: Path) -> dict:
    SB.mkdir(parents=True, exist_ok=True)
    catalog = package / "diagnostics/source_bound_probe_catalog.json"
    plan_path = package / "diagnostics/source_bound_probe_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["package_id"] = INSTALL
    write_json(SB / "probe_catalog.json", json.loads(catalog.read_text(encoding="utf-8")))
    write_json(SB / "probe_plan.json", plan)
    report = sourcegen.materialize(
        SB / "probe_catalog.json", SB / "probe_plan.json", SB / "generated"
    )
    write_json(SB / "generation_report.json", report)
    if report.get("pass") is not True:
        raise BuildError(f"current source-bound generation failed: {report.get('errors')}")
    mapping = {
        SB / "probe_catalog.json": package / "diagnostics/source_bound_probe_catalog.json",
        SB / "probe_plan.json": package / "diagnostics/source_bound_probe_plan.json",
        SB / "generated/source_bound_causal_observer.svh": package / "tb_probe/source_bound_causal_observer.svh",
        SB / "generated/source_bound_causal_parser.py": package / "package_tools/source_bound_causal_parser.py",
        SB / "generated/source_bound_probe_binding.json": package / "diagnostics/source_bound_probe_binding.json",
        SB / "generation_report.json": package / "diagnostics/source_bound_observer_generation_report.json",
    }
    for source, target in mapping.items():
        shutil.copy2(source, target)
    generation = {
        "schema": "conv-node0004-v76-source-bound-generation-v1",
        "status": "PASS",
        "package_id": INSTALL,
        "generator_sha256": base.sha256(ROOT / "tools/generate_server_source_bound_observer.py"),
        "generation_report_sha256": base.sha256(SB / "generation_report.json"),
        "v75_catalog_and_plan_semantics_reused": True,
        "changed_surface": ["fresh package identity", "current exact source-bound regeneration"],
    }
    write_json(package / "diagnostics/source_bound_observer_generation.json", generation)
    return report


def patch_runtime(package: Path) -> None:
    path = package / "package_tools/node0004_hang_localization_runtime_v7.py"
    text = path.read_text(encoding="utf-8")
    text = replace_function(text, "_prepare_source_bound_products", BOUNDED_PREPARE_V2)
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_plugin(package: Path) -> None:
    old = package / "package_tools/node0004_v75_post_sim_plugin.py"
    new = package / "package_tools/node0004_v76_post_sim_plugin.py"
    old.rename(new)
    request_path = package / "contracts/server_post_sim_return_request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    argv = request["plugins"][0]["argv"]
    request["plugins"][0]["argv"] = [
        item.replace("node0004_v75_post_sim_plugin.py", "node0004_v76_post_sim_plugin.py")
        for item in argv
    ]
    write_json(request_path, request)
    contract_path = package / "contracts/server_post_sim_return_contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["request_sha256"] = base.sha256(request_path)
    write_json(contract_path, contract)


def build_directory(output: Path) -> Path:
    configure_prior()
    with tempfile.TemporaryDirectory(prefix="node0004-v76-source-") as temp:
        extracted = base.extract_source(Path(temp))
        package = output / INSTALL
        if package.exists():
            raise BuildError(f"refusing overwrite: {package}")
        shutil.copytree(extracted, package)
    base.replace_identity(package)
    regenerate_source_bound(package)
    patch_runtime(package)
    patch_plugin(package)

    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
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
        }
    )
    receipts = manifest.setdefault("active_receipts", {})
    receipts.update(
        {
            "source_bound_generator_sha256": base.sha256(
                ROOT / "tools/generate_server_source_bound_observer.py"
            ),
            "server_post_sim_return_helper_sha256": base.sha256(
                ROOT / "tools/server_post_sim_return.py"
            ),
            "server_package_rule_sha256": base.sha256(SERVER_RULE),
            "server_rule_sha256": base.sha256(SERVER_RULE),
            "generation_index_sha256": base.sha256(INDEX_RULE),
            "hardware_readme_sha256": base.sha256(README),
        }
    )
    rules = receipts.setdefault("rules", [])
    for rule in (
        "CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001",
        "CDA-SERVER-POST-SIM-CORE-RETURN-INDEPENDENT-PUBLISH-001",
        "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
        "CDA-SERVER-RETURN-FIXED-SIMRESULT-ATOMIC-PUBLISH-001",
        "CDA-SERVER-PACKAGE-STORAGE-ROTATION-001",
    ):
        if rule not in rules:
            rules.append(rule)
    write_json(
        package / "provenance/v75_return_to_v76_boundfix.json",
        {
            "schema": "conv-node0004-v75-return-to-v76-boundfix-v1",
            "source_package_sha256": SOURCE_SHA,
            "formal_return_sha256": RETURN_SHA,
            "return_analysis_sha256": base.sha256(ANALYSIS),
            "last_proven_good": "POST_SIM_CORE_RETURN_PUBLISHED_WITH_RECEIPTED_FULL_SIM_LOG",
            "first_divergence": "POST_SIM_SOURCE_BOUND_BOUNDED_PROJECTION_SIZE_GATE_BEFORE_PARSER_PRODUCTS",
            "unique_package_local_root_cause": "57142 accepted source-bound records expand to 21096256 bytes, exceeding the 7-MiB projection gate by 13756224 bytes",
            "fix": "retain every ENABLED/SUMMARY/CLASS/TRIGGER/STALL record and deterministic first/tail ring samples per exact instance+boundary+kind",
            "frozen": [
                "numeric/W3/qparams/tail/workload/config/golden",
                "timeout/backpressure",
                "functional RTL/ISA/hardware/active ndp-sim",
            ],
        },
    )
    base.refresh_receipts(manifest)
    prior.legacy.refresh_path_budget(package, manifest)
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
    with tempfile.TemporaryDirectory(prefix="node0004-v76-repeat-") as temp:
        repeat = build_directory(Path(temp))
        repeat_zip = Path(temp) / f"{INSTALL}.zip"
        base.deterministic_zip(repeat, repeat_zip)
        repeat_digest = base.sha256(repeat_zip)
    if digest != repeat_digest:
        raise BuildError("deterministic rebuild differs")
    sidecar = output / f"{INSTALL}.zip.sha256"
    sidecar.write_text(f"{digest}  {archive.name}\n", encoding="ascii", newline="\n")
    report = {
        "schema": "conv-node0004-v76-build-v1",
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_AUDITS",
        "zip": str(archive),
        "zip_bytes": archive.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "deterministic_rebuild_equal": True,
        "source_v75_sha256": SOURCE_SHA,
        "formal_return_sha256": RETURN_SHA,
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
