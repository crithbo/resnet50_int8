from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tools.audit_node0004_v65_final_zip as base


PACKAGE = "r5_n4_hw_v66_epoch_owner_diag"
SOURCE = "r5_n4_hw_v65_branchcatch_diag"
SOURCE_SHA = "b78e3c7257a34e23fab6cf046922a488c8e1f17356d6dfa6df11234e882a3816"


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    known, _ = parser.parse_known_args()

    base.PACKAGE = PACKAGE
    base.SOURCE = SOURCE
    base.SOURCE_SHA = SOURCE_SHA
    rc = base.main()

    report = json.loads(known.output.read_text(encoding="utf-8"))
    with zipfile.ZipFile(known.zip) as archive:
        root = archive.namelist()[0].split("/", 1)[0]
        manifest = json.loads(
            archive.read(f"{root}/package_manifest.json").decode("utf-8")
        )
        runner = archive.read(f"{root}/PREPARE_AND_RUN.sh").decode("utf-8")
        provenance = json.loads(
            archive.read(
                f"{root}/provenance/v65_to_v66_epoch_owner.json"
            ).decode("utf-8")
        )

    feature = manifest["diagnostic_features"]["RETURN_OBS_EPOCH_OWNER"]
    checks = {
        "epoch_owner_feature_contract": (
            feature["runtime_enable_parameter"] == "+RETURN_OBS_EPOCH_OWNER"
            and feature["limit_parameter"]
            == "+RETURN_OBS_EPOCH_OWNER_LIMIT=128"
            and feature["edge_schema"] == "EPOCH_OWNER_V1"
            and feature["boundary_schema"] == "EPOCH_OWNER_V1"
        ),
        "epoch_owner_actual_argv": (
            runner.count(
                " +RETURN_OBS_EPOCH_OWNER "
                "+RETURN_OBS_EPOCH_OWNER_LIMIT=128"
            )
            == 2
        ),
        "fresh_v65_to_v66_provenance": (
            provenance["source_v65_sha256"] == SOURCE_SHA
            and provenance["v65_return_sha256"]
            == "55aa22054535bfe032b62639c36f67cf058b09e84752fe3eeef13a0d186dacd3"
            and "numeric/W3/qparams/tail/workload/config/golden"
            in provenance["frozen"]
            and "functional RTL/ISA/hardware/active ndp-sim"
            in provenance["frozen"]
        ),
    }
    report["checks"].update(checks)
    for key, value in checks.items():
        if not value and key not in report["errors"]:
            report["errors"].append(key)
    report["package_id"] = PACKAGE
    report["schema"] = "node0004-v66-final-zip-audit-v1"
    report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"] = not report["errors"]
    report["claim_boundary"] = (
        "Local exact package/runner/install layout and the changed bounded "
        "per-input epoch-owner observer only. No DUT natural terminal, "
        "formal 320D, E4, or E5 claim."
    )
    known.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "pass": report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"],
                "errors": report["errors"],
                "sha": report["zip"]["sha256"],
            }
        )
    )
    return 0 if report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"] and rc == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
