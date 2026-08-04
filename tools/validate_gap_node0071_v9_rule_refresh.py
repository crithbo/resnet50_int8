from __future__ import annotations

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


SOURCE_NAME = "r5_n71_gap_v8_dual_ingress"
TARGET_NAME = "r5_n71_gap_v9_ingress_rule"
SOURCE_SHA256 = (
    "cb1b43b3e8228951a2c62e8de02b36f17291a2561048cb1b36c0a9ed876b5a0f"
)
CURRENT_GAP_RULE_SHA256 = (
    "4191f12fb19fc301cb323993b9aee0b28057c339adba1af780e9d27ff3068baf"
)
PUBLICATION_SHA256 = (
    "b8f4519c4cd98aec22498b250269e884e69bd893a52db71cd486424651f801c6"
)
OBSERVER_SHA256 = (
    "0a1621d2f09c0c8a074cf992f61deed7b0a3433608b5e0ae9cb53396619eccc8"
)
RULE_ID = "CDA-GAP-DUAL-OPERAND-INGRESS-OBSERVABILITY-001"
ALLOWED_CHANGED = {
    "TEST_PACKAGE_MANIFEST.json",
    "README.md",
    "PREPARE_AND_RUN.sh",
    "workload/sca_cfg.json",
    "workload/sca_cfg_D.json",
}


class ValidationError(ValueError):
    pass


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def read_zip(path: Path, expected_root: str) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise ValidationError(f"ZIP CRC differs: {bad}")
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            mode = info.external_attr >> 16
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or (mode and stat.S_ISLNK(mode))
                or not pure.parts
                or pure.parts[0] != expected_root
            ):
                raise ValidationError(f"unsafe ZIP member: {info.filename}")
            if info.is_dir():
                continue
            relative = PurePosixPath(*pure.parts[1:]).as_posix()
            if relative in files:
                raise ValidationError(f"duplicate ZIP member: {relative}")
            files[relative] = archive.read(info)
    return files


def validate_payload(
    source: dict[str, bytes], target: dict[str, bytes]
) -> dict[str, Any]:
    errors: list[str] = []
    source_set = set(source)
    target_set = set(target)
    exact_relative_set = source_set == target_set
    if not exact_relative_set:
        errors.append("relative file set differs")

    changed = {
        relative
        for relative in source_set & target_set
        if source[relative] != target[relative]
    }
    changed_exact = changed == ALLOWED_CHANGED
    if not changed_exact:
        errors.append("changed-path allowlist differs")

    numeric = sorted(
        relative
        for relative in source_set & target_set
        if relative.startswith("workload/")
        and relative
        not in {"workload/sca_cfg.json", "workload/sca_cfg_D.json"}
    )
    numeric_equal = (
        len(numeric) == 73
        and all(source[path] == target[path] for path in numeric)
    )
    if not numeric_equal:
        errors.append("73-file numeric workload differs")

    immutable = sorted(
        (source_set & target_set) - ALLOWED_CHANGED
    )
    immutable_equal = (
        len(immutable) == 120
        and all(source[path] == target[path] for path in immutable)
    )
    if not immutable_equal:
        errors.append("120-file immutable payload differs")

    observer_relative = "tb_probe/native_return_observer.svh"
    observer_equal = (
        source.get(observer_relative) == target.get(observer_relative)
        and target.get(observer_relative) is not None
        and sha256_bytes(target[observer_relative]) == OBSERVER_SHA256
    )
    if not observer_equal:
        errors.append("observer algorithm differs")

    try:
        manifest = json.loads(
            target["TEST_PACKAGE_MANIFEST.json"].decode("utf-8")
        )
    except (KeyError, UnicodeError, json.JSONDecodeError) as error:
        raise ValidationError("target manifest unavailable") from error
    final_contract = manifest.get("final_zip_rule_self_audit_contract")
    receipts = (
        final_contract.get("read_receipt", [])
        if isinstance(final_contract, dict)
        else []
    )
    gap_receipts = [
        item
        for item in receipts
        if isinstance(item, dict)
        and item.get("path")
        == ".agents/rules/GAP_probe_v7_validator_rules.md"
    ]
    applicable = (
        final_contract.get("applicable_rule_ids", [])
        if isinstance(final_contract, dict)
        else []
    )
    refresh = manifest.get("rule_drift_refresh")
    manifest_current = (
        manifest.get("install_name") == TARGET_NAME
        and manifest.get("package_name") == TARGET_NAME
        and manifest.get("run_name") == f"run_{TARGET_NAME}"
        and manifest.get("return_name") == f"{TARGET_NAME}_return"
        and manifest.get("rule_receipts", {}).get(
            "gap_probe_rule_sha256"
        )
        == CURRENT_GAP_RULE_SHA256
        and len(gap_receipts) == 1
        and gap_receipts[0].get("sha256")
        == CURRENT_GAP_RULE_SHA256
        and gap_receipts[0].get("current_match") is True
        and RULE_ID in applicable
        and isinstance(refresh, dict)
        and refresh.get("trigger_rule_id") == RULE_ID
        and refresh.get("publication_record_sha256")
        == PUBLICATION_SHA256
        and refresh.get("source_v8_zip_sha256") == SOURCE_SHA256
        and refresh.get("source_v8_bytes_unchanged") is True
        and refresh.get("observer_algorithm_changed") is False
        and set(refresh.get("allowed_changed_paths", []))
        == ALLOWED_CHANGED
    )
    if not manifest_current:
        errors.append("current GAP rule receipt/contract differs")

    namespace_equal = True
    for relative in (
        "PREPARE_AND_RUN.sh",
        "workload/sca_cfg.json",
        "workload/sca_cfg_D.json",
    ):
        normalized = target[relative].decode("utf-8").replace(
            TARGET_NAME, SOURCE_NAME
        )
        if normalized.encode("utf-8") != source[relative]:
            namespace_equal = False
    if not namespace_equal:
        errors.append("identity/SCA namespace rewrite is not exact")

    readme = target.get("README.md", b"").decode(
        "utf-8", errors="replace"
    )
    readme_current = (
        RULE_ID in readme
        and "observer byte-for-byte" in readme
        and "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX" in readme
    )
    if not readme_current:
        errors.append("README receipt boundary differs")

    return {
        "valid": not errors,
        "errors": errors,
        "checks": {
            "exact_relative_file_set": exact_relative_set,
            "changed_path_allowlist_exact": changed_exact,
            "numeric_73_file_tree_equal": numeric_equal,
            "immutable_120_file_tree_equal": immutable_equal,
            "observer_byte_equal": observer_equal,
            "current_gap_rule_manifest_contract": manifest_current,
            "identity_sca_namespace_exact_rewrite": namespace_equal,
            "readme_current_rule_boundary": readme_current,
        },
        "changed_paths": sorted(changed),
        "numeric_file_count": len(numeric),
        "immutable_file_count": len(immutable),
        "observer_sha256": (
            sha256_bytes(target[observer_relative])
            if observer_relative in target
            else None
        ),
    }


def mutate_manifest(
    target: dict[str, bytes], mutation: str
) -> dict[str, bytes]:
    mutated = dict(target)
    manifest = json.loads(
        mutated["TEST_PACKAGE_MANIFEST.json"].decode("utf-8")
    )
    if mutation == "delete_new_rule_id":
        applicable = manifest[
            "final_zip_rule_self_audit_contract"
        ]["applicable_rule_ids"]
        manifest["final_zip_rule_self_audit_contract"][
            "applicable_rule_ids"
        ] = [item for item in applicable if item != RULE_ID]
    elif mutation == "restore_old_gap_rule_sha":
        old = (
            "2dee42a883bde9c1650710c8312d23e661aeb3c66ef9d1d4e15524af79c33dc7"
        )
        manifest["rule_receipts"]["gap_probe_rule_sha256"] = old
        for item in manifest[
            "final_zip_rule_self_audit_contract"
        ]["read_receipt"]:
            if item.get("path") == (
                ".agents/rules/GAP_probe_v7_validator_rules.md"
            ):
                item["sha256"] = old
    else:
        raise ValidationError(f"unknown manifest mutation: {mutation}")
    mutated["TEST_PACKAGE_MANIFEST.json"] = (
        json.dumps(manifest, sort_keys=True).encode("utf-8")
    )
    return mutated


def validate(source_zip: Path, target_zip: Path) -> dict[str, Any]:
    if sha256_bytes(source_zip.read_bytes()) != SOURCE_SHA256:
        raise ValidationError("source v8 ZIP identity differs")
    source = read_zip(source_zip, SOURCE_NAME)
    target = read_zip(target_zip, TARGET_NAME)
    positive = validate_payload(source, target)
    if not positive["valid"]:
        raise ValidationError(
            "positive rule-refresh validation failed: "
            + "; ".join(positive["errors"])
        )

    mutations: dict[str, dict[str, bytes]] = {
        "delete_new_rule_id": mutate_manifest(
            target, "delete_new_rule_id"
        ),
        "restore_old_gap_rule_sha": mutate_manifest(
            target, "restore_old_gap_rule_sha"
        ),
        "mutate_observer_algorithm": dict(target),
        "mutate_frozen_numeric_payload": dict(target),
    }
    observer_path = "tb_probe/native_return_observer.svh"
    mutations["mutate_observer_algorithm"][observer_path] = (
        target[observer_path] + b"\n"
    )
    numeric_path = next(
        path
        for path in sorted(target)
        if path.startswith("workload/")
        and path
        not in {"workload/sca_cfg.json", "workload/sca_cfg_D.json"}
    )
    numeric_payload = bytearray(target[numeric_path])
    numeric_payload[0] ^= 1
    mutations["mutate_frozen_numeric_payload"][numeric_path] = bytes(
        numeric_payload
    )

    controls: dict[str, Any] = {}
    for name, mutated in mutations.items():
        result = validate_payload(source, mutated)
        controls[name] = {
            "failed_closed": not result["valid"],
            "errors": result["errors"],
        }
        if result["valid"]:
            raise ValidationError(
                f"negative control did not fail closed: {name}"
            )

    return {
        "schema": "gap-node0071-v9-rule-refresh-validation-v1",
        "status": "PASS",
        "source_zip": str(source_zip.resolve()),
        "source_zip_sha256": sha256_bytes(source_zip.read_bytes()),
        "target_zip": str(target_zip.resolve()),
        "target_zip_sha256": sha256_bytes(target_zip.read_bytes()),
        "positive": positive,
        "negative_controls": controls,
        "negative_control_count": len(controls),
        "all_negative_controls_fail_closed": all(
            item["failed_closed"] for item in controls.values()
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_zip", type=Path)
    parser.add_argument("target_zip", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate(
        args.source_zip.resolve(), args.target_zip.resolve()
    )
    text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8", newline="\n")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
