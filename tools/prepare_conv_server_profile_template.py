from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ENCODABLE_ROLES = {"accumulate_config", "requant_shard"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _prepare_empty(path: Path) -> None:
    if path.exists():
        if not path.is_dir() or any(path.iterdir()):
            raise ValueError(f"output directory must be new or empty: {path}")
        return
    path.mkdir(parents=True)


def _semantic_connection_counts(typed: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for operator in typed.get("operators", []):
        for artifact in operator.get("config_artifacts", []):
            if artifact.get("role") != "semantic_contract":
                continue
            semantic = json.loads(artifact["raw_text"])
            config_sha = semantic.get("config", {}).get("sha256")
            connection_count = semantic.get("official_encoder", {}).get(
                "connection_count"
            )
            if (
                isinstance(config_sha, str)
                and isinstance(connection_count, int)
                and connection_count > 0
            ):
                counts[config_sha] = connection_count
    return counts


def build_template(
    *,
    typed_request_path: Path,
    address_plan_path: Path,
    reference_contract_path: Path,
    output_dir: Path,
    node_id: str,
    candidate_revision: str,
    accumulate_mapping_key: str,
    requant_mapping_key: str,
) -> dict[str, Any]:
    typed_request_path = typed_request_path.resolve()
    address_plan_path = address_plan_path.resolve()
    reference_contract_path = reference_contract_path.resolve()
    output_dir = output_dir.resolve()
    typed = _load_object(typed_request_path)
    reference = _load_object(reference_contract_path)
    _prepare_empty(output_dir)
    semantic_counts = _semantic_connection_counts(typed)
    reference_counts: dict[str, int] = {}
    for binding in reference.get("config_bindings", []):
        role = binding.get("role")
        count = binding.get("expected_connection_count")
        if isinstance(role, str) and isinstance(count, int) and count > 0:
            previous = reference_counts.setdefault(role, count)
            if previous != count:
                raise ValueError(f"reference profile has mixed counts for role {role}")

    profile_keys = {
        "accumulate": accumulate_mapping_key,
        "requant": requant_mapping_key,
    }
    encoder_profiles: dict[str, Any] = {}
    for profile_name, cache_key in profile_keys.items():
        reference_profile = reference.get("encoder_profiles", {}).get(profile_name)
        if not isinstance(reference_profile, dict):
            raise ValueError(f"reference contract lacks {profile_name} profile")
        source = (
            ROOT
            / "ndp-sim-ref"
            / "bitstream"
            / "config"
            / "mapping_cache"
            / f"{cache_key}.json"
        )
        if not source.is_file():
            raise FileNotFoundError(f"mapping seed is missing: {source}")
        destination_name = f"{profile_name}_mapping_seed.json"
        shutil.copyfile(source, output_dir / destination_name)
        encoder_profiles[profile_name] = {
            key: reference_profile[key]
            for key in (
                "heuristic_iterations",
                "heuristic_restarts",
                "seed",
                "visualize_placement",
            )
        }
        encoder_profiles[profile_name]["mapping_seed"] = {
            "cache_key": cache_key,
            "path": destination_name,
            "sha256": _sha256(output_dir / destination_name),
        }

    bindings: list[dict[str, Any]] = []
    for operator in typed.get("operators", []):
        operator_id = operator.get("id")
        if not isinstance(operator_id, str) or not operator_id:
            raise ValueError("typed operator id is missing")
        for artifact in operator.get("config_artifacts", []):
            role = artifact.get("role")
            if role not in ENCODABLE_ROLES:
                continue
            artifact_id = artifact.get("artifact_id")
            if not isinstance(artifact_id, str) or not artifact_id:
                raise ValueError("typed artifact id is missing")
            if role == "accumulate_config":
                binding_id = "accumulate"
                profile = "accumulate"
            else:
                suffix = artifact_id.rsplit(".", 1)[-1]
                binding_id = f"requant-{suffix}"
                profile = "requant"
            bindings.append(
                {
                    "binding_id": binding_id,
                    "operator_id": operator_id,
                    "artifact_id": artifact_id,
                    "role": role,
                    "config_sha256": artifact["sha256"],
                    "encoder_profile": profile,
                    "expected_connection_count": semantic_counts.get(
                        artifact["sha256"], reference_counts.get(role, 0)
                    ),
                }
            )
            if bindings[-1]["expected_connection_count"] <= 0:
                raise ValueError(
                    f"connection count evidence is missing: {artifact_id}"
                )
    if not bindings:
        raise ValueError("typed request has no encodable config artifacts")

    shutil.copyfile(address_plan_path, output_dir / "address_plan.json")
    contract = {
        "schema_version": "model-execplan-server-profile-request-0.1",
        "candidate_revision": candidate_revision,
        "typed_request_sha256": _sha256(typed_request_path),
        "node_id": node_id,
        "expected_encoder_repository_commit": reference[
            "expected_encoder_repository_commit"
        ],
        "native_source_tree_sha256": reference["native_source_tree_sha256"],
        "address_plan": {
            "path": "address_plan.json",
            "sha256": _sha256(output_dir / "address_plan.json"),
        },
        "encoder_profiles": encoder_profiles,
        "config_bindings": bindings,
        "description": (
            "Deterministic initial native server-profile template derived from the "
            f"typed Conv request for {node_id}; native prepare-contract must refresh it."
        ),
    }
    contract_path = output_dir / "server_profile_request.json"
    contract_path.write_text(
        json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return {
        "output": str(contract_path),
        "node_id": node_id,
        "binding_count": len(bindings),
        "typed_request_sha256": contract["typed_request_sha256"],
        "address_plan_sha256": contract["address_plan"]["sha256"],
        "status": "initial_template_generated_native_prepare_required",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Initialize a typed Conv native server-profile contract template"
    )
    parser.add_argument("--node-id", required=True)
    parser.add_argument("--typed-request", type=Path, required=True)
    parser.add_argument("--address-plan", type=Path, required=True)
    parser.add_argument("--reference-contract", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--candidate-revision", required=True)
    parser.add_argument("--accumulate-mapping-key", required=True)
    parser.add_argument("--requant-mapping-key", default="9d12e681247ecaa7")
    args = parser.parse_args()
    result = build_template(
        typed_request_path=args.typed_request,
        address_plan_path=args.address_plan,
        reference_contract_path=args.reference_contract,
        output_dir=args.output_dir,
        node_id=args.node_id,
        candidate_revision=args.candidate_revision,
        accumulate_mapping_key=args.accumulate_mapping_key,
        requant_mapping_key=args.requant_mapping_key,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
