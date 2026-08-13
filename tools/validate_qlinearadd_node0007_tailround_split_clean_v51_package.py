"""Validate fresh-identity QAdd isolated tail_round v51."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import validate_qlinearadd_node0007_tailround_split_v50_package as validator


ROOT = Path(__file__).resolve().parents[1]
SOURCE_NAME = "r5_qadd_n7_tailround_split_v50"
NAME = "r5_qadd_n7_tailround_split_clean_v51"
SOURCE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE_NAME}.zip"
OUT = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-split-clean-v51-package"
ZIP = OUT / f"{NAME}.zip"


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def members(path: Path, root: str) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        return {name.split("/", 1)[1]: archive.read(name) for name in archive.namelist() if not name.endswith("/") and name.startswith(root + "/")}


def normalize(value: bytes) -> bytes:
    try:
        return value.decode("utf-8").replace(NAME, SOURCE_NAME).encode("utf-8")
    except UnicodeDecodeError:
        return value


def main() -> int:
    validator.NAME = NAME
    validator.OUT = OUT
    validator.ZIP = ZIP
    validator.REPORT = OUT / "family_validation.json"
    validator.HARNESS = OUT / "runtime_layout_harness.json"
    rc = validator.main()
    report = json.loads(validator.REPORT.read_text(encoding="utf-8"))
    source = members(SOURCE, SOURCE_NAME)
    target = members(ZIP, NAME)
    normalized_changed = sorted(
        key for key in set(source) | set(target)
        if key not in source or key not in target or normalize(target[key]) != source[key]
    )
    expected = ["SERVER_RUNTIME_LAYOUT_CONTRACT.json", "TEST_PACKAGE_MANIFEST.json"]
    identity_equivalence = normalized_changed == expected
    report["identity_only_equivalence"] = {
        "source_zip": {"path": SOURCE.relative_to(ROOT).as_posix(), "sha256": "c8d1b3c4d43e1a4ec2360226d882881413de6da4739b20a08df43aa70fa6cad3"},
        "normalized_changed_members": normalized_changed,
        "expected_normalized_changed_members": expected,
        "all_other_members_byte_equal_after_identity_normalization": identity_equivalence,
        "runtime_layout_contract_change": "identity-length-derived path budget only"
    }
    report["checks"]["identity_only_byte_equivalence"] = identity_equivalence
    if not identity_equivalence and "identity_only_byte_equivalence" not in report["errors"]:
        report["errors"].append("identity_only_byte_equivalence")
    report["valid"] = not report["errors"]
    validator.write_json(validator.REPORT, report)
    print(json.dumps({"valid": report["valid"], "errors": report["errors"], "report": str(validator.REPORT)}, sort_keys=True))
    return 0 if report["valid"] and rc == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
