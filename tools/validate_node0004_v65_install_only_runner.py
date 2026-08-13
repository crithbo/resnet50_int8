from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tools.validate_node0004_v60_install_only_runner as validator


validator.INSTALL = "r5_n4_hw_v65_branchcatch_diag"
_base_map_harness = validator.map_harness
_base_run_case = validator.run_case


def _refresh_manifest(package: Path) -> None:
    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = {
        path.relative_to(package).as_posix(): validator.base.sha256(path)
        for path in sorted(item for item in package.rglob("*") if item.is_file())
        if path != manifest_path
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def map_unique_return_harness(package: Path, result_root: Path) -> None:
    """Map the production-fixed result root only inside the isolated harness.

    The v60 harness predates the repeatable runner's per-execution return tag.
    Its generic mapping already rewrites the production runner and runtime, but
    only normalizes the old ``${install_name}_return.zip`` JSON spelling.  The
    exact v65 runner uses ``${install_name}_${return_tag}_return.zip``; normalize
    those two publication-receipt fields as well so Windows Python and Git Bash
    compare the same isolated path.  Final ZIP bytes are never modified.
    """

    _base_map_harness(package, result_root)
    runner_path = package / "PREPARE_AND_RUN.sh"
    runner = runner_path.read_text(encoding="utf-8")
    temp_root = Path(__import__("tempfile").gettempdir()).resolve()
    relative = result_root.resolve().relative_to(temp_root)
    bash_root = "/tmp/" + relative.as_posix()
    native_root = result_root.resolve().as_posix()
    new_zip = (
        f'"return_zip": "{native_root}/'
        '${install_name}_${return_tag}_return.zip"'
    )
    new_sidecar = (
        f'"return_sidecar": "{native_root}/'
        '${install_name}_${return_tag}_return.zip.sha256"'
    )
    old_zip = '"return_zip": "${return_zip}"'
    old_sidecar = '"return_sidecar": "${return_sha}"'
    if runner.count(old_zip) != 1 or runner.count(old_sidecar) != 1:
        raise ValueError("unique return publication receipt mapping differs")
    runner_path.write_text(
        runner.replace(old_zip, new_zip, 1).replace(
            old_sidecar, new_sidecar, 1
        ),
        encoding="utf-8",
        newline="\n",
    )
    runtime_path = (
        package
        / "package_tools/node0004_hang_localization_runtime_v7.py"
    )
    runtime = runtime_path.read_text(encoding="utf-8")
    old_zip_compare = (
        'Path(publication.get("return_zip")) != final_zip'
    )
    old_sidecar_compare = (
        'Path(publication.get("return_sidecar")) != final_sha'
    )
    if (
        runtime.count(old_zip_compare) != 1
        or runtime.count(old_sidecar_compare) != 1
    ):
        raise ValueError("mapped publication comparison differs")
    runtime_path.write_text(
        runtime.replace(
            old_zip_compare,
            'Path(publication.get("return_zip")).name != final_zip.name',
            1,
        ).replace(
            old_sidecar_compare,
            'Path(publication.get("return_sidecar")).name != final_sha.name',
            1,
        ),
        encoding="utf-8",
        newline="\n",
    )
    _refresh_manifest(package)


validator.map_harness = map_unique_return_harness


def run_case_unique_return(*args, **kwargs):
    row = _base_run_case(*args, **kwargs)
    root = Path(args[1])
    result_root = root / "isolated_simresult"
    returns = sorted(
        result_root.glob(
            f"{validator.INSTALL}_r*_return.zip"
        )
    )
    return_zip = returns[0] if len(returns) == 1 else None
    if return_zip is not None:
        return_sidecar = Path(str(return_zip) + ".sha256")
        sidecar = (
            return_sidecar.read_text(encoding="ascii").split()
            if return_sidecar.is_file()
            else []
        )
        row["finalizer_reached"] = True
        row["fixed_result_return_published"] = True
        row["partial_return_published"] = row["mode"] != "normal"
        row["sidecar_valid"] = (
            len(sidecar) == 2
            and sidecar[1] == return_zip.name
            and sidecar[0] == validator.base.sha256(return_zip)
        )
        row["returned_gate"] = validator.returned_gate(return_zip)
        row["return_zip"] = (
            f"{validator.FIXED_ROOT}/{return_zip.name}"
        )
        row["return_sidecar"] = (
            f"{validator.FIXED_ROOT}/{return_sidecar.name}"
        )
    attempts_root = (
        root
        / "server/install/codex_runs"
        / validator.INSTALL
    )
    row["run_attempt_count"] = (
        sum(1 for path in attempts_root.iterdir() if path.is_dir())
        if attempts_root.is_dir()
        else 0
    )
    return row


validator.run_case = run_case_unique_return


if __name__ == "__main__":
    raise SystemExit(validator.main())
