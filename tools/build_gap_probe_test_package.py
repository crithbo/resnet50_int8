#!/usr/bin/env python3
"""Build a self-contained GAP workload plus read-only TB-probe test ZIP."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.gap_server_workload import (  # noqa: E402
    validate_gap_server_workload,
)
from tools.capture_gap_probe_server_identity import (  # noqa: E402
    FOCUS_RTL_RELS,
    file_identity,
    text_file_identity,
    tree_identity,
)


SCHEMA = "resnet50-gap-probe-test-package-v7"
INSTALL_NAME = "gap_hwop0071_sum_probe_v7"
SOURCE_WORKLOAD_REL = Path(
    "artifacts/operator_config_validation/r5-server-workloads/"
    "gap_hwop0071_sum_graph"
)
GITHUB_REFERENCE_REL = Path(
    "contracts/gap_probe_rtl_three_way_reference_v1.json"
)
DEFAULT_OUTPUT_REL = Path(
    "artifacts/operator_config_validation/r5-server-test-packages/"
    + INSTALL_NAME
)
MANIFEST_NAME = "TEST_PACKAGE_MANIFEST.json"


class GapProbePackageError(ValueError):
    """Raised when a probe test package cannot be built safely."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _records(root: Path, *, exclude_manifest: bool = False) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if exclude_manifest and relative == MANIFEST_NAME:
            continue
        if path.is_symlink():
            raise GapProbePackageError(f"package contains symlink: {relative}")
        result[relative] = {
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
    return result


def _tree_sha256(records: Mapping[str, Mapping[str, Any]]) -> str:
    digest = hashlib.sha256()
    for relative, item in sorted(records.items()):
        digest.update(
            f"{relative}\0{item['size_bytes']}\0{item['sha256']}\n".encode()
        )
    return digest.hexdigest()


def _reference_server_identity(root: Path) -> dict[str, Any]:
    rtl_tree = tree_identity(root / "NDP_copy01" / "rtl")
    rtl_tree["path"] = "NDP_copy01/rtl"
    makefile = file_identity(root / "NDP_copy01" / "Makefile.tb_NDP_Top_new_phy")
    makefile["path"] = "NDP_copy01/Makefile.tb_NDP_Top_new_phy"
    active_filelist = file_identity(
        root
        / "NDP_copy01"
        / "rtl"
        / "filelists"
        / "NDP_Top_phy_filelist.f"
    )
    active_filelist["path"] = (
        "NDP_copy01/rtl/filelists/NDP_Top_phy_filelist.f"
    )
    return {
        "assumption_only_until_server_hash_match": True,
        "source": "NDP_copy01",
        "rtl_tree": rtl_tree,
        "makefile": makefile,
        "active_filelist": active_filelist,
        "focus_rtl_files": {
            relative.as_posix(): {
                **text_file_identity(root / "NDP_copy01" / relative),
                "path": f"NDP_copy01/{relative.as_posix()}",
            }
            for relative in FOCUS_RTL_RELS
        },
    }


def _github_reference_identity(root: Path) -> dict[str, Any]:
    path = root / GITHUB_REFERENCE_REL
    reference = json.loads(path.read_text(encoding="utf-8"))
    expected_paths = {relative.as_posix() for relative in FOCUS_RTL_RELS}
    actual_paths = set(reference.get("files", {}))
    if actual_paths != expected_paths:
        raise GapProbePackageError(
            "GitHub three-way reference focused file set differs"
        )
    if reference.get("github", {}).get("locked_commit_matches_master") is not True:
        raise GapProbePackageError(
            "GitHub three-way reference does not bind master to the locked commit"
        )
    for relative in FOCUS_RTL_RELS:
        key = relative.as_posix()
        local_identity = text_file_identity(root / "NDP_copy01" / relative)
        expected_local = reference["files"][key].get(
            "local_canonical_text_sha256"
        )
        if (
            local_identity["canonical_text_sha256"] is None
            or local_identity["canonical_text_sha256"] != expected_local
        ):
            raise GapProbePackageError(
                f"local focused RTL changed after GitHub comparison: {key}"
            )
    return {
        **reference,
        "source_path": GITHUB_REFERENCE_REL.as_posix(),
        "source_sha256": _sha256(path),
    }


def _copy_lf(source: Path, destination: Path) -> None:
    text = source.read_text(encoding="utf-8")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        text.replace("\r\n", "\n").replace("\r", "\n"),
        encoding="utf-8",
        newline="\n",
    )


def _write_lf(destination: Path, text: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        text.replace("\r\n", "\n").replace("\r", "\n"),
        encoding="utf-8",
        newline="\n",
    )


def _run_script(install_name: str) -> str:
    return f"""#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "Usage: bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX" >&2
  exit 2
fi

package_root="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
workload_root="${{package_root}}/workload"
ndp_root="$(cd "$1" && pwd)"
tb="${{ndp_root}}/tb_NDP_Top_new_phy.sv"
cfg_root="${{ndp_root}}/install/cfg_pkg/{install_name}"
probe_run_dir="${{ndp_root}}/run_{install_name}"
evidence_root="${{ndp_root}}/probe_evidence_{install_name}"
package_manifest="${{package_root}}/{MANIFEST_NAME}"
return_zip="${{ndp_root}}/{install_name}_return.zip"
return_sha="${{return_zip}}.sha256"

if [ ! -f "${{tb}}" ]; then
  echo "Missing server testbench: ${{tb}}" >&2
  exit 3
fi
if [ ! -f "${{ndp_root}}/Makefile.tb_NDP_Top_new_phy" ]; then
  echo "Missing server Makefile under: ${{ndp_root}}" >&2
  exit 3
fi
if [ ! -d "${{ndp_root}}/rtl" ]; then
  echo "Missing existing server RTL directory: ${{ndp_root}}/rtl" >&2
  exit 3
fi
if ! grep -Fq '$(VCS_EXTRA_OPTS)' "${{ndp_root}}/Makefile.tb_NDP_Top_new_phy"; then
  echo "Server Makefile does not forward VCS_EXTRA_OPTS" >&2
  exit 3
fi
for fresh_target in \
  "${{cfg_root}}" \
  "${{probe_run_dir}}" \
  "${{evidence_root}}" \
  "${{ndp_root}}/{install_name}_return" \
  "${{return_zip}}" \
  "${{return_sha}}"; do
  if [ -e "${{fresh_target}}" ]; then
    echo "Fresh v7 target already exists; refusing reuse: ${{fresh_target}}" >&2
    exit 4
  fi
done

vcs_extra_opts="${{VCS_EXTRA_OPTS:-}}"
vcs_extra_opts="${{vcs_extra_opts}} +incdir+${{ndp_root}}"
server_command="make -f Makefile.tb_NDP_Top_new_phy compile sim DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 RUN_DIR=${{probe_run_dir}} VCS_EXTRA_OPTS=${{vcs_extra_opts# }} PLUSARGS='+SCA_CFG=install/cfg_pkg/{install_name}/sca_cfg.json +SCA_CFG_D=install/cfg_pkg/{install_name}/sca_cfg_D.json +RETURN_OBSERVER +RETURN_OBS_FILE=${{evidence_root}}/return_observer.log +RETURN_OBS_SLICE=0 +RETURN_OBS_ACCUM_STATE +RETURN_OBS_ACCUM_LIMIT=512 +RETURN_OBS_STALL_CYCLES=4096 +RETURN_OBS_HEARTBEAT_CYCLES=4096'"
mkdir "${{evidence_root}}"
printf '%s\\n' "${{server_command}}" > "${{evidence_root}}/server_command.txt"
python3 "${{package_root}}/tb_probe/capture_gap_probe_server_identity.py" \
  --ndp-root "${{ndp_root}}" \
  --package-manifest "${{package_manifest}}" \
  --install-name "{install_name}" \
  --phase pre_install \
  --server-command "${{server_command}}" \
  --output "${{evidence_root}}/server_identity_pre_install.json"

mkdir -p "${{ndp_root}}/install"
cp -a "${{workload_root}}/install/." "${{ndp_root}}/install/"
mkdir "${{cfg_root}}"
cp "${{workload_root}}/sca_cfg.json" "${{cfg_root}}/sca_cfg.json"
cp "${{workload_root}}/sca_cfg_D.json" "${{cfg_root}}/sca_cfg_D.json"

python3 "${{package_root}}/tb_probe/install_native_return_observer.py" \
  --tb "${{tb}}" \
  --observer "${{package_root}}/tb_probe/native_return_observer.svh" \
  --fix-run-time \
  > "${{evidence_root}}/observer_install_report.json"

installed_observer="${{ndp_root}}/native_return_observer.svh"
test -s "${{installed_observer}}"
cmp -s \
  "${{package_root}}/tb_probe/native_return_observer.svh" \
  "${{installed_observer}}"
grep -Fq '`include "native_return_observer.svh"' "${{tb}}"
grep -Fq "longint unsigned RUN_TIME = 64'd100000000000000;" "${{tb}}"

python3 "${{package_root}}/tb_probe/capture_gap_probe_server_identity.py" \
  --ndp-root "${{ndp_root}}" \
  --package-manifest "${{package_manifest}}" \
  --install-name "{install_name}" \
  --phase post_install \
  --server-command "${{server_command}}" \
  --output "${{evidence_root}}/server_identity_post_install.json"

cd "${{ndp_root}}"
set +e
make -f Makefile.tb_NDP_Top_new_phy compile sim \
  DUMP_VCD=0 \
  DUMP_FSDB=0 \
  TB_DUMP_FSDB=0 \
  RUN_DIR="${{probe_run_dir}}" \
  VCS_EXTRA_OPTS="${{vcs_extra_opts# }}" \
  PLUSARGS="+SCA_CFG=install/cfg_pkg/{install_name}/sca_cfg.json +SCA_CFG_D=install/cfg_pkg/{install_name}/sca_cfg_D.json +RETURN_OBSERVER +RETURN_OBS_FILE=${{evidence_root}}/return_observer.log +RETURN_OBS_SLICE=0 +RETURN_OBS_ACCUM_STATE +RETURN_OBS_ACCUM_LIMIT=512 +RETURN_OBS_STALL_CYCLES=4096 +RETURN_OBS_HEARTBEAT_CYCLES=4096"
run_status=$?
set -e
printf '%s\\n' "${{run_status}}" > "${{evidence_root}}/run_exit_status.txt"

set +e
python3 "${{package_root}}/tb_probe/capture_gap_probe_server_identity.py" \
  --ndp-root "${{ndp_root}}" \
  --package-manifest "${{package_manifest}}" \
  --install-name "{install_name}" \
  --phase post_run \
  --server-command "${{server_command}}" \
  --exit-status "${{run_status}}" \
  --output "${{evidence_root}}/server_identity_post_run.json"
identity_status=$?

python3 "${{package_root}}/tb_probe/build_gap_probe_return.py" \
  --ndp-root "${{ndp_root}}" \
  --run-dir "${{probe_run_dir}}" \
  --evidence-root "${{evidence_root}}" \
  --package-root "${{package_root}}" \
  --install-name "{install_name}" \
  --output-dir "${{ndp_root}}" \
  --run-status "${{run_status}}" \
  --server-command "${{server_command}}"
package_status=$?
set -e

if [ -f "${{return_zip}}" ] && [ -f "${{return_sha}}" ]; then
  echo "Return ZIP: ${{return_zip}}"
  echo "Return SHA256: ${{return_sha}}"
fi
if [ "${{run_status}}" -ne 0 ]; then
  exit "${{run_status}}"
fi
if [ "${{identity_status}}" -ne 0 ]; then
  exit "${{identity_status}}"
fi
exit "${{package_status}}"
"""


def _readme(install_name: str) -> str:
    return f"""# GAP HWOP0071 int32 SUM boundary probe v7

This ZIP contains the unchanged validated GAP workload under `workload/` and a
read-only testbench observer under `tb_probe/`.

It contains no functional RTL `.v` or `.sv` file. The installer only:

1. copies `native_return_observer.svh` next to the existing server testbench;
2. inserts one include before the final `endmodule` in
   `tb_NDP_Top_new_phy.sv`;
3. changes the known unsafe unsized `RUN_TIME` TB constant to an explicit
   64-bit constant;
4. records the server RTL tree, active filelist, makefile, SCA paths and TB
   hashes before/after installation and after the run;
5. refuses any testbench path below an `rtl/` directory;
6. creates a bounded allowlist-only return ZIP without waveforms or build
   trees.

The functional RTL is neither included nor modified. The v5 return already
localized the mismatch to the GA int32 SUM boundary: the next block receives
an old outbuffer value as input C. v7 records the minimum control/data state
needed to distinguish invalid-slot data reuse from incomplete transout state
reset. Each accepted PE input records `trans_init`, calculate state/counter,
outbuffer valid/count/pointers, both tags, both data slots and the actual three
ALU operands. The global event limit is 512, which covers all 392 accepted
regular-PE inputs in block 0 and the first failing inputs in block 1.

## Run

Unzip the package anywhere on the Linux server, then run:

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

The script merges `workload/install/` into the existing server `install/`,
installs both SCA files as:

```text
install/cfg_pkg/{install_name}/sca_cfg.json
install/cfg_pkg/{install_name}/sca_cfg_D.json
```

and performs `compile sim` with only the targeted accumulator-state probe
enabled. The command explicitly adds the server testbench root to the VCS
include path and uses the isolated compile directory:

```text
run_{install_name}
```

It does not reuse the default `run/simv`. All waveform controls are explicitly
disabled:

```text
DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0
```

The identity capture still treats GitHub, local `NDP_copy01`, and the active
server RTL as three independent identities. The argument must be the exact
tree being compiled and executed.

## Return

The script directly creates:

```text
{install_name}_return.zip
{install_name}_return.zip.sha256
```

Return only those two files. Do not compress the whole run directory. The ZIP
contains only the observer log, three identities, install report, exit status,
compile/simulation logs, both SCA files, formal SCA_D readback files and up to
four slice-0 target logs. It rejects waveform formats, `csrc`, `simv.daidir`,
work/archive trees, nested archives, ZIPs above 16 MiB, extracted content above
32 MiB and individual text logs above 8 MiB.
"""


def _write_deterministic_zip(root: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(
        zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            relative = f"{root.name}/{path.relative_to(root).as_posix()}"
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            mode = 0o100755 if path.name == "PREPARE_AND_RUN.sh" else 0o100644
            info.external_attr = (mode & 0xFFFF) << 16
            archive.writestr(
                info,
                path.read_bytes(),
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            )


def _audit_zip(root: Path, zip_path: Path) -> dict:
    expected = {
        f"{root.name}/{path.relative_to(root).as_posix()}": _sha256(path)
        for path in root.rglob("*")
        if path.is_file()
    }
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or set(names) != set(expected):
            raise GapProbePackageError("ZIP exact file set differs from directory")
        for name, expected_hash in expected.items():
            if hashlib.sha256(archive.read(name)).hexdigest() != expected_hash:
                raise GapProbePackageError(f"ZIP payload hash differs: {name}")
    return {"entry_count": len(expected), "exact_file_set": True}


def validate_package(project_root: Path, output: Path) -> dict:
    root = project_root.resolve()
    output = output.resolve()
    zip_path = output.with_suffix(".zip")
    sha_path = Path(f"{zip_path}.sha256")
    manifest_path = output / MANIFEST_NAME
    for required in (output, zip_path, sha_path, manifest_path):
        if not required.exists():
            raise GapProbePackageError(
                f"checked package input is missing: {required}"
            )
    if not output.is_dir():
        raise GapProbePackageError("checked package root is not a directory")
    for path in output.rglob("*"):
        if path.is_symlink():
            raise GapProbePackageError(
                f"checked package contains symlink: "
                f"{path.relative_to(output).as_posix()}"
            )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise GapProbePackageError("checked package manifest is not an object")
    if (
        manifest.get("schema") != SCHEMA
        or manifest.get("status") != "server_test_package_ready"
        or manifest.get("install_name") != INSTALL_NAME
        or output.name != INSTALL_NAME
    ):
        raise GapProbePackageError("checked package identity differs")

    source_validation = validate_gap_server_workload(
        root, root / SOURCE_WORKLOAD_REL
    )
    copied_validation = validate_gap_server_workload(
        root, output / "workload"
    )
    if copied_validation != source_validation:
        raise GapProbePackageError("checked workload copy differs from source")
    expected_source = {
        "path": SOURCE_WORKLOAD_REL.as_posix(),
        "file_count": source_validation["file_count"],
        "tree_sha256": source_validation["tree_sha256"],
        "manifest_sha256": _sha256(
            root / SOURCE_WORKLOAD_REL / "gap_package_manifest.json"
        ),
    }
    if manifest.get("source_workload") != expected_source:
        raise GapProbePackageError("checked source workload binding differs")

    payload_records = _records(output, exclude_manifest=True)
    if (
        manifest.get("files") != payload_records
        or manifest.get("payload_file_count") != len(payload_records)
        or manifest.get("payload_tree_sha256")
        != _tree_sha256(payload_records)
    ):
        raise GapProbePackageError(
            "checked package payload records differ from manifest"
        )
    forbidden_rtl = sorted(
        relative
        for relative in payload_records
        if Path(relative).suffix.lower() in {".v", ".sv"}
    )
    nested_archives = sorted(
        relative
        for relative in payload_records
        if Path(relative).suffix.lower()
        in {".zip", ".tar", ".tgz", ".gz", ".bz2", ".xz", ".7z", ".rar"}
    )
    if forbidden_rtl:
        raise GapProbePackageError(
            f"checked package contains functional RTL: {forbidden_rtl[0]}"
        )
    if nested_archives:
        raise GapProbePackageError(
            f"checked package contains nested archive: {nested_archives[0]}"
        )

    if (
        (output / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
        != _run_script(INSTALL_NAME)
        or (output / "README.md").read_text(encoding="utf-8")
        != _readme(INSTALL_NAME)
    ):
        raise GapProbePackageError(
            "checked package generated control text differs"
        )
    if manifest.get("reference_server_identity") != _reference_server_identity(
        root
    ):
        raise GapProbePackageError(
            "checked package local RTL reference identity differs"
        )
    if manifest.get("github_reference_identity") != _github_reference_identity(
        root
    ):
        raise GapProbePackageError(
            "checked package GitHub reference identity differs"
        )
    policy = manifest.get("probe_policy", {})
    return_policy = manifest.get("return_policy", {})
    if (
        policy.get("functional_rtl_v_or_sv_included") is not False
        or policy.get("functional_rtl_modified_by_installer") is not False
        or policy.get("observer_is_read_only") is not True
        or policy.get("same_clk_sg_ga_accumulator_state_events") is not True
        or policy.get("ga_accumulator_event_limit") != 512
        or policy.get("waveforms_explicitly_disabled")
        != {"DUMP_VCD": 0, "DUMP_FSDB": 0, "TB_DUMP_FSDB": 0}
        or return_policy.get("allowlist_only") is not True
        or return_policy.get("waveforms_forbidden") is not True
        or return_policy.get("nested_archives_forbidden") is not True
    ):
        raise GapProbePackageError("checked package safety policy differs")

    zip_audit = _audit_zip(output, zip_path)
    zip_sha256 = _sha256(zip_path)
    expected_sidecar = f"{zip_sha256}  {zip_path.name}\n"
    if sha_path.read_text(encoding="ascii") != expected_sidecar:
        raise GapProbePackageError("checked package SHA256 sidecar differs")
    return {
        "schema": SCHEMA,
        "status": "server_test_package_validated",
        "directory": output.as_posix(),
        "manifest_sha256": _sha256(manifest_path),
        "payload_file_count": len(payload_records),
        "payload_tree_sha256": _tree_sha256(payload_records),
        "zip": zip_path.as_posix(),
        "zip_size_bytes": zip_path.stat().st_size,
        "zip_sha256": zip_sha256,
        "zip_audit": zip_audit,
        "functional_rtl_v_or_sv_included": False,
        "server_execution_required": True,
        "expected_return_zip": f"{INSTALL_NAME}_return.zip",
        "expected_return_sha256": f"{INSTALL_NAME}_return.zip.sha256",
    }


def build_package(project_root: Path, output: Path) -> dict:
    root = project_root.resolve()
    source = root / SOURCE_WORKLOAD_REL
    output = output.resolve()
    zip_path = output.with_suffix(".zip")
    sha_path = Path(f"{zip_path}.sha256")
    for target in (output, zip_path, sha_path):
        if target.exists():
            raise GapProbePackageError(f"output must be fresh: {target}")

    source_validation = validate_gap_server_workload(root, source)
    github_reference_identity = _github_reference_identity(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, output / "workload")
    copied_validation = validate_gap_server_workload(root, output / "workload")
    if copied_validation != source_validation:
        raise GapProbePackageError("copied workload validation differs")

    _copy_lf(
        root / "NDP_copy01" / "native_return_observer.svh",
        output / "tb_probe" / "native_return_observer.svh",
    )
    _copy_lf(
        root / "tools" / "install_native_return_observer.py",
        output / "tb_probe" / "install_native_return_observer.py",
    )
    _copy_lf(
        root / "tools" / "capture_gap_probe_server_identity.py",
        output / "tb_probe" / "capture_gap_probe_server_identity.py",
    )
    _copy_lf(
        root / "tools" / "build_gap_probe_return.py",
        output / "tb_probe" / "build_gap_probe_return.py",
    )
    _write_lf(output / "PREPARE_AND_RUN.sh", _run_script(INSTALL_NAME))
    _write_lf(output / "README.md", _readme(INSTALL_NAME))

    payload_records = _records(output, exclude_manifest=True)
    manifest = {
        "schema": SCHEMA,
        "status": "server_test_package_ready",
        "install_name": INSTALL_NAME,
        "source_workload": {
            "path": SOURCE_WORKLOAD_REL.as_posix(),
            "file_count": source_validation["file_count"],
            "tree_sha256": source_validation["tree_sha256"],
            "manifest_sha256": _sha256(source / "gap_package_manifest.json"),
        },
        "probe_policy": {
            "functional_rtl_v_or_sv_included": False,
            "functional_rtl_modified_by_installer": False,
            "testbench_sv_may_be_modified": True,
            "observer_is_read_only": True,
            "vcs_tb_include_dir_explicit": True,
            "tb_run_time_sized_64bit": True,
            "isolated_vcs_run_dir": f"run_{INSTALL_NAME}",
            "waveforms_explicitly_disabled": {
                "DUMP_VCD": 0,
                "DUMP_FSDB": 0,
                "TB_DUMP_FSDB": 0,
            },
            "ga_accumulator_event_limit": 512,
            "same_clk_sg_ga_accumulator_state_events": True,
            "functional_rtl_repair_included": False,
            "diagnostic_hypothesis": (
                "int32 SUM block boundary reuses stale outbuffer slot data "
                "as ALU input C; distinguish invalid-slot reuse from "
                "incomplete transout control reset"
            ),
        },
        "identity_policy": {
            "capture_phases": ["pre_install", "post_install", "post_run"],
            "functional_rtl_tree_hashed": True,
            "active_filelist_hashed": True,
            "testbench_before_after_hashed": True,
            "server_git_identity_best_effort": True,
            "focused_read_buffer_ga_write_rtl_files_hashed": True,
            "focused_rtl_canonical_text_hashes": True,
            "resolved_server_rtl_git_identity": True,
            "github_local_server_three_way_comparison": True,
        },
        "return_policy": {
            "direct_zip_and_sha256": True,
            "allowlist_only": True,
            "zip_limit_bytes": 16 * 1024 * 1024,
            "extracted_limit_bytes": 32 * 1024 * 1024,
            "individual_text_limit_bytes": 8 * 1024 * 1024,
            "waveforms_forbidden": True,
            "build_trees_forbidden": True,
            "nested_archives_forbidden": True,
        },
        "reference_server_identity": _reference_server_identity(root),
        "github_reference_identity": github_reference_identity,
        "run_entry": "PREPARE_AND_RUN.sh",
        "payload_file_count": len(payload_records),
        "payload_tree_sha256": _tree_sha256(payload_records),
        "files": payload_records,
    }
    _write_lf(
        output / MANIFEST_NAME,
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    )

    _write_deterministic_zip(output, zip_path)
    zip_audit = _audit_zip(output, zip_path)
    zip_sha256 = _sha256(zip_path)
    _write_lf(sha_path, f"{zip_sha256}  {zip_path.name}\n")
    return {
        **manifest,
        "directory": output.as_posix(),
        "zip": zip_path.as_posix(),
        "zip_size_bytes": zip_path.stat().st_size,
        "zip_sha256": zip_sha256,
        "zip_audit": zip_audit,
        "sha256_file": sha_path.as_posix(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / DEFAULT_OUTPUT_REL)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    try:
        report = build_package(ROOT, output)
    except Exception as error:
        print(f"GAP probe test package generation failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
