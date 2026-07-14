from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from resnet50_pipeline.network28_audit import (
    audit_network28_candidates,
    cost_evidence,
    edge_evidence,
)
from resnet50_pipeline.w4_evidence import (
    architecture_evidence_basis_sha256,
    canonical_json_bytes,
    current_evidence_path,
)


EDGE_EVIDENCE_ID = "w4_rtl28_network_physical_edges_v1"
COST_EVIDENCE_ID = "w4_rtl28_network_profile_cost_v1"


def build_evidence(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    architecture = json.loads(
        (root / "contracts/architecture.json").read_text(encoding="utf-8")
    )
    catalog = json.loads(
        (root / "artifacts/w3/model_graph.json").read_text(encoding="utf-8")
    )
    basis_sha256 = architecture_evidence_basis_sha256(architecture)
    combined = audit_network28_candidates(catalog)
    reports = {
        EDGE_EVIDENCE_ID: edge_evidence(combined),
        COST_EVIDENCE_ID: cost_evidence(combined),
    }
    path_kinds = {
        EDGE_EVIDENCE_ID: "network-physical-edge-audit",
        COST_EVIDENCE_ID: "network-profile-cost",
    }
    outputs: dict[str, dict[str, Any]] = {}
    for evidence_id, report in reports.items():
        report["architecture_basis_sha256"] = basis_sha256
        payload = canonical_json_bytes(report)
        path = current_evidence_path(
            root, basis_sha256, path_kinds[evidence_id], payload
        )
        outputs[evidence_id] = {
            "report": report,
            "payload": payload,
            "path": path,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "size_bytes": len(payload),
        }
    return {
        "architecture_basis_sha256": basis_sha256,
        "combined_report": combined,
        "outputs": outputs,
    }


def evidence_records(project_root: Path, built: dict[str, Any]) -> dict[str, Any]:
    root = project_root.resolve()
    records: dict[str, dict[str, Any]] = {}
    for evidence_id, output in built["outputs"].items():
        report = output["report"]
        record = {
            "target_family": report["target_family"],
            "slice_count": report["slice_count"],
            "status": report["status"],
            "current_gate_eligible": report["current_gate_eligible"],
            "evidence_kind": report["evidence_kind"],
            "architecture_basis_sha256": report["architecture_basis_sha256"],
            "path": output["path"].relative_to(root).as_posix(),
            "sha256": output["sha256"],
            "size_bytes": output["size_bytes"],
            "all_scenarios_pass": report["all_scenarios_pass"],
            "hardware_approval": report["hardware_approval"],
            "g4_passed": report["g4_passed"],
            "w5_authorized": report["w5_authorized"],
        }
        if report["evidence_kind"] == "network_physical_edge_audit":
            record.update(
                {
                    "edge_count": report["edge_count"],
                    "qparam_edge_count": report["qparam_edge_count"],
                    "residual_add_count": report["residual_add_count"],
                }
            )
        else:
            record["scenario_count"] = report["scenario_count"]
        records[evidence_id] = record
    return records


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit RTL28 W4 93-edge compatibility, lifetimes, aliases, and "
            "static profile costs without reading W3 tensor payloads"
        )
    )
    parser.add_argument(
        "--project-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument(
        "--write-current-evidence",
        action="store_true",
        help="Write both reports to their content-addressed RTL28 W4 paths",
    )
    args = parser.parse_args()
    built = build_evidence(args.project_root)
    if args.write_current_evidence:
        for output in built["outputs"].values():
            output["path"].parent.mkdir(parents=True, exist_ok=True)
            output["path"].write_bytes(output["payload"])
    manifest = {
        "architecture_basis_sha256": built["architecture_basis_sha256"],
        "all_scenarios_pass": built["combined_report"]["all_scenarios_pass"],
        "hardware_approval": built["combined_report"]["hardware_approval"],
        "g4_passed": built["combined_report"]["g4_passed"],
        "w5_authorized": built["combined_report"]["w5_authorized"],
        "written": args.write_current_evidence,
        "evidence_records": evidence_records(args.project_root, built),
    }
    print(canonical_json_bytes(manifest).decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
