from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
NAME = "r5_n71_gap_v47_stage_transition_rootfix"
RUNNER = "PREPARE_AND_RUN.sh"
MANIFEST = "TEST_PACKAGE_MANIFEST.json"
PRODUCTION_RESULT_ROOT = "/home/panqs/ndp/simresult"


def sha_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def to_bash(path: Path) -> str:
    value = str(path.resolve())
    if len(value) >= 3 and value[1] == ":":
        return "/" + value[0].lower() + value[2:].replace("\\", "/")
    return value.replace("\\", "/")


def read_zip(path: Path) -> tuple[str, dict[str, bytes]]:
    files: dict[str, bytes] = {}
    root: str | None = None
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC differs")
        seen: set[str] = set()
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            mode = info.external_attr >> 16
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or (mode and stat.S_ISLNK(mode))
                or len(pure.parts) < 2
            ):
                raise ValueError(f"unsafe member: {info.filename}")
            root = root or pure.parts[0]
            if pure.parts[0] != root:
                raise ValueError("multiple ZIP roots")
            if info.is_dir():
                continue
            relative = PurePosixPath(*pure.parts[1:]).as_posix()
            if relative in seen:
                raise ValueError(f"duplicate member: {relative}")
            seen.add(relative)
            files[relative] = archive.read(info)
    if root is None:
        raise ValueError("empty ZIP")
    return root, files


def extract(path: Path, destination: Path) -> Path:
    root, _ = read_zip(path)
    with zipfile.ZipFile(path) as archive:
        archive.extractall(destination)
    package = destination / root
    if root != NAME or not package.is_dir():
        raise ValueError("package root identity differs")
    return package


def update_manifest_runner_receipt(package: Path) -> None:
    manifest_path = package / MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    runner = package / RUNNER
    manifest["files"][RUNNER] = {
        "size_bytes": runner.stat().st_size,
        "sha256": sha_path(runner),
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def map_runner_for_harness(
    package: Path,
    mapped_result_root: Path,
    signal_name: str | None = None,
) -> dict[str, Any]:
    runner = package / RUNNER
    before = runner.read_bytes()
    text = before.decode("utf-8")
    old = f'result_root="{PRODUCTION_RESULT_ROOT}"'
    new = f'result_root="{to_bash(mapped_result_root)}"'
    if text.count(old) != 1:
        raise ValueError("production fixed result assignment differs")
    mapped = text.replace(old, new, 1)
    cr_old = 'install_name="${manifest_identity[0]}"'
    cr_new = "install_name=\"${manifest_identity[0]%$'\\r'}\""
    ret_old = 'return_name="${manifest_identity[1]}"'
    ret_new = "return_name=\"${manifest_identity[1]%$'\\r'}\""
    if mapped.count(cr_old) != 1 or mapped.count(ret_old) != 1:
        raise ValueError("identity line-ending harness anchor differs")
    mapped = mapped.replace(cr_old, cr_new, 1).replace(
        ret_old, ret_new, 1
    )
    signal_anchor = 'wait "$sim_pid"\n'
    signal_hook = (
        'if [ -n "${HARNESS_INJECT_SIGNAL:-}" ]; then\n'
        '  (sleep 1; kill -s "$HARNESS_INJECT_SIGNAL" $$) &\n'
        'fi\n'
        'wait "$sim_pid"\n'
    )
    if mapped.count(signal_anchor) != 1:
        raise ValueError("signal-injection harness anchor differs")
    if signal_name:
        mapped = mapped.replace(signal_anchor, signal_hook, 1)
    runner.write_text(
        mapped,
        encoding="utf-8",
        newline="\n",
    )
    runner.chmod(0o755)
    update_manifest_runner_receipt(package)
    after = runner.read_bytes()
    return {
        "production_runner_sha256": sha_bytes(before),
        "harness_runner_sha256": sha_bytes(after),
        "only_allowed_mapping_delta": (
            before.decode("utf-8")
            .replace(old, new, 1)
            .replace(cr_old, cr_new, 1)
            .replace(ret_old, ret_new, 1)
            .replace(
                signal_anchor,
                signal_hook if signal_name else signal_anchor,
                1,
            )
            == after.decode("utf-8")
        ),
        "production_literal": PRODUCTION_RESULT_ROOT,
        "harness_namespace": to_bash(mapped_result_root),
        "mapping_in_final_zip": False,
        "windows_crlf_identity_normalization_harness_only": True,
        "signal_injection_harness_only": signal_name,
    }


def write_mock_tools(root: Path, mode: str) -> tuple[Path, Path]:
    from tools import revalidate_gap_node0071_v40_signal_stub as inherited

    bin_dir, sim_started = inherited.write_mock_tools(root)
    wrapper = bin_dir / "make"
    text = wrapper.read_text(encoding="utf-8")
    text = text.replace(
        "set -u\nrun_dir=''\n",
        "set -u\n"
        f"[ \"${{MOCK_MODE:-}}\" = compile_fail ] && exit 77\n"
        "run_dir=''\n",
        1,
    )
    text = text.replace(
        "lcsc=false\nlcsc_limit=false\n",
        "lcsc=false\nlcsc_limit=false\n"
        "stage_transition=false\nstage_heartbeat=false\n",
        1,
    )
    text = text.replace(
        "    +RETURN_OBS_LC_SUPPLY_CONSERVATION_LIMIT=512) "
        "lcsc_limit=true;;\n",
        "    +RETURN_OBS_LC_SUPPLY_CONSERVATION_LIMIT=512) "
        "lcsc_limit=true;;\n"
        "    +RETURN_OBS_STAGE_TRANSITION) stage_transition=true;;\n"
        "    +RETURN_OBS_STAGE_HEARTBEAT_CYCLES=1048576) "
        "stage_heartbeat=true;;\n",
        1,
    )
    text = text.replace(
        '[ "$lcsc_limit" = true ] || exit 65\n',
        '[ "$lcsc_limit" = true ] || exit 65\n'
        '[ "$stage_transition" = true ] || exit 62\n'
        '[ "$stage_heartbeat" = true ] || exit 63\n',
        1,
    )
    text = text.replace(
        "lc_supply_conservation=1 lc_supply_conservation_limit=512'",
        "lc_supply_conservation=1 lc_supply_conservation_limit=512 "
        "stage_transition=1 owner_clock=global_clk "
        "heartbeat_cycles=1048576 selected_mask_expected=0x0000ffff'",
        1,
    )
    text = text.replace(
        "  '0 | LC_SUPPLY_CONSERVATION_WITNESS_V1 | event=SAFE_STUB "
        "bq_full=0:0/0:0 mem_empty=0:0/0:0' \\\n"
        "  >\"$observer_log\"\n",
        "  '0 | LC_SUPPLY_CONSERVATION_WITNESS_V1 | event=SAFE_STUB "
        "bq_full=0:0/0:0 mem_empty=0:0/0:0' \\\n"
        "  '0 | GEXEC_STAGE_TRANSITION_STATE_V1 | event=EDGE n=1 "
        "edge=1 stage=0 opcode=0x1 mask=0xffff ready=0xffff "
        "valid=0xffff local_empty=0xffff exec_level=0x0 "
        "finish_level=0x0 exec_seen=0x0 finish_seen=0x0 "
        "global_empty=0 global_rd=0 mask_match=1 config_match=1 "
        "gconfig_ready=1 fetch_finish=1' \\\n"
        "  >\"$observer_log\"\n",
        1,
    )
    normal = r"""
case "${MOCK_MODE:-}" in
  root_drift_file)
    : >"$MOCK_SERVER_ROOT/rogue_root_file"
    MOCK_MODE=normal
    ;;
  root_drift_directory)
    mkdir "$MOCK_SERVER_ROOT/rogue_root_directory"
    MOCK_MODE=normal
    ;;
  root_drift_return_directory)
    mkdir "$MOCK_SERVER_ROOT/r5_n71_gap_v47_stage_transition_rootfix_return"
    MOCK_MODE=normal
    ;;
esac
if [ "${MOCK_MODE:-}" = normal ]; then
  printf '%s\n' \
    'Using SCA cfg file: install/cfg_pkg/r5_n71_gap_v47_stage_transition_rootfix/sca_cfg.json' \
    'Using SCA cfg D file: install/cfg_pkg/r5_n71_gap_v47_stage_transition_rootfix/sca_cfg_D.json' \
    'JSON config: 25 matrices loaded' \
    'JSON_D config: 48 matrices dumped' \
    'Simulation completed successfully!' >>"$sim_log"
  exit 0
fi
"""
    text = text.replace(
        "printf 'SAFE_SIM_STUB_STARTED\\n' >\"$MOCK_SIM_STARTED\"\n"
        "trap 'exit 143' TERM INT\n",
        "printf 'SAFE_SIM_STUB_STARTED\\n' >\"$MOCK_SIM_STARTED\"\n"
        + normal
        + "trap 'exit 143' TERM INT HUP\n",
        1,
    )
    wrapper.write_text(text, encoding="utf-8", newline="\n")
    wrapper.chmod(0o755)
    return bin_dir, sim_started


def run_runner(
    package: Path,
    server: Path,
    result_root: Path,
    harness_root: Path,
    bash: Path,
    mode: str,
    signal_name: str | None = None,
    precreate_duplicate: bool = False,
) -> dict[str, Any]:
    bin_dir, sim_started = write_mock_tools(harness_root, mode)
    if precreate_duplicate:
        (server / f"{NAME}_return.zip").write_text(
            "negative duplicate", encoding="ascii"
        )
    stdout_path = harness_root / "runner.stdout"
    stderr_path = harness_root / "runner.stderr"
    status_path = harness_root / "runner.status"
    body = (
        'export PATH="$1:/usr/bin:/bin:/c/Windows/System32"\n'
        'export MOCK_SIM_STARTED="$6"\n'
        'export MOCK_MODE="$8"\n'
        'export HARNESS_INJECT_SIGNAL="$9"\n'
        'export MOCK_SERVER_ROOT="$3"\n'
        'cd "$2"\n'
        'bash PREPARE_AND_RUN.sh "$3" >"$4" 2>"$5"\n'
        'printf "%s\\n" "$?" >"$7"\n'
    )
    process = subprocess.run(
        [
            str(bash),
            "-c",
            body,
            "gap-v47-fixed-result",
            to_bash(bin_dir),
            to_bash(package),
            to_bash(server),
            to_bash(stdout_path),
            to_bash(stderr_path),
            to_bash(sim_started),
            to_bash(status_path),
            mode,
            signal_name or "",
        ],
        cwd=package,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        timeout=180,
    )
    return_zip = result_root / f"{NAME}_return.zip"
    sidecar = Path(str(return_zip) + ".sha256")
    return {
        "mode": mode,
        "signal": signal_name,
        "harness_exit_code": process.returncode,
        "harness_stdout": process.stdout,
        "harness_stderr": process.stderr,
        "runner_exit_code": (
            int(status_path.read_text(encoding="ascii").strip())
            if status_path.is_file()
            else None
        ),
        "runner_stdout": (
            stdout_path.read_text(encoding="utf-8", errors="replace")
            if stdout_path.is_file()
            else ""
        ),
        "runner_stderr": (
            stderr_path.read_text(encoding="utf-8", errors="replace")
            if stderr_path.is_file()
            else ""
        ),
        "safe_sim_stub_started": sim_started.is_file(),
        "return_zip": str(return_zip),
        "return_zip_exists": return_zip.is_file(),
        "return_sidecar_exists": sidecar.is_file(),
    }


def validate_return(
    return_zip: Path,
    package_manifest: dict[str, Any],
) -> dict[str, Any]:
    sidecar = Path(str(return_zip) + ".sha256")
    if not return_zip.is_file() or not sidecar.is_file():
        raise ValueError("fixed result ZIP/sidecar absent")
    digest = sha_path(return_zip)
    if sidecar.read_text(encoding="ascii") != (
        f"{digest}  {return_zip.name}\n"
    ):
        raise ValueError("sidecar binding differs")
    root, files = read_zip(return_zip)
    if root != f"{NAME}_return":
        raise ValueError("return root differs")
    manifest = json.loads(files["RETURN_MANIFEST.json"])
    declared = {
        item["path"]: {
            "size_bytes": item["size_bytes"],
            "sha256": item["sha256"],
        }
        for item in manifest["files"]
    }
    observed = {
        path: {
            "size_bytes": len(payload),
            "sha256": sha_bytes(payload),
        }
        for path, payload in files.items()
        if path != "RETURN_MANIFEST.json"
    }
    if observed != declared:
        raise ValueError("return exact-set differs")
    if json.loads(files["evidence/PACKAGE_MANIFEST.json"]) != package_manifest:
        raise ValueError("harness package identity receipt differs")
    allowlist = {
        item["target_path"]: item
        for item in package_manifest["return_allowlist"]
    }
    if not set(observed) <= set(allowlist):
        raise ValueError("non-allowlisted return member")
    expected_missing = sorted(
        target
        for target, item in allowlist.items()
        if item["required"] and target not in observed
    )
    if sorted(manifest["required_missing"]) != expected_missing:
        raise ValueError("required-missing accounting differs")
    publication = manifest["fixed_result_publication"]
    root_receipt = (
        json.loads(files["evidence/ndp_root_toplevel_exact_set.json"])
        if "evidence/ndp_root_toplevel_exact_set.json" in files
        else None
    )
    return {
        "zip_sha256": digest,
        "sidecar_sha256": sha_path(sidecar),
        "crc_root_path_duplicate_symlink_safe": True,
        "exact_set_allowlist_valid": True,
        "required_missing": expected_missing,
        "publication": publication,
        "root_toplevel_receipt": root_receipt,
        "duplicate_absent_claim":
            publication.get("duplicate_absent") is True,
        "signal_status": (
            files.get("evidence/signal_status.txt", b"").decode(
                "utf-8", errors="replace"
            )
        ),
        "gate": (
            json.loads(files["evidence/SERVER_RESULT_GATE.json"])
            if "evidence/SERVER_RESULT_GATE.json" in files
            else None
        ),
    }


def validate(target_zip: Path, bash: Path) -> dict[str, Any]:
    target_root, target_files = read_zip(target_zip)
    if target_root != NAME:
        raise ValueError("final ZIP identity differs")
    production_runner = target_files[RUNNER].decode("utf-8")
    production_manifest = json.loads(target_files[MANIFEST])
    fixed_static = {
        "literal_exact_once":
            production_runner.count(
                f'result_root="{PRODUCTION_RESULT_ROOT}"'
            )
            == 1,
        "not_configurable":
            "RESULT_ROOT" not in production_runner
            and "${result_root" not in production_runner,
        "shared_finalize_function":
            production_runner.count("finalize() {") == 1,
        "exit_trap": "trap 'finalize $?' EXIT" in production_runner,
        "hup_trap": "signal_name=HUP" in production_runner,
        "int_trap": "signal_name=INT" in production_runner,
        "term_trap": "signal_name=TERM" in production_runner,
        "runtime_collect_fixed_arg":
            '--result-root "$result_root"' in production_runner,
        "no_cwd_return_assignment":
            'result_zip="$result_root/' in production_runner,
    }
    if not all(fixed_static.values()):
        raise ValueError("production fixed-result static contract differs")
    modes: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(
        prefix=".gap-v47-fixed-result-", dir=ROOT
    ) as raw:
        base = Path(raw)
        for mode, signal_name in (
            ("normal", None),
            ("compile_fail", None),
            ("int", "INT"),
            ("term", "TERM"),
            ("hup", "HUP"),
        ):
            case = base / mode
            package = extract(target_zip, case / "fresh")
            result_root = case / "isolated_simresult_namespace"
            mapping = map_runner_for_harness(
                package, result_root, signal_name
            )
            server = case / "server_root"
            server.mkdir(parents=True)
            (server / "install").mkdir()
            root_before = sorted(
                (p.name, "directory" if p.is_dir() else "file")
                for p in server.iterdir()
            )
            run = run_runner(
                package,
                server,
                result_root,
                case / "tools",
                bash,
                mode,
                signal_name,
            )
            harness_manifest = json.loads(
                (package / MANIFEST).read_text(encoding="utf-8")
            )
            if not run["return_zip_exists"] or not run[
                "return_sidecar_exists"
            ]:
                raise ValueError(
                    "fixed result ZIP/sidecar absent: "
                    + json.dumps(run, ensure_ascii=False, sort_keys=True)
                )
            returned = validate_return(
                result_root / f"{NAME}_return.zip",
                harness_manifest,
            )
            duplicates = [
                server / f"{NAME}_return.zip",
                server / f"{NAME}_return.zip.sha256",
                package / f"{NAME}_return.zip",
                package / f"{NAME}_return.zip.sha256",
                server / f"run_{NAME}" / f"{NAME}_return.zip",
                server / f"run_{NAME}" / f"{NAME}_return.zip.sha256",
                server / "install/cfg_pkg" / NAME
                / f"{NAME}_return.zip",
                server / "install/cfg_pkg" / NAME
                / f"{NAME}_return.zip.sha256",
            ]
            root_after = sorted(
                (p.name, "directory" if p.is_dir() else "file")
                for p in server.iterdir()
            )
            run["mapping"] = mapping
            run["ndp_root_toplevel_before"] = root_before
            run["ndp_root_toplevel_after"] = root_after
            run["ndp_root_toplevel_unchanged"] = root_before == root_after
            run["return"] = returned
            run["duplicates_outside_mapped_namespace_absent"] = not any(
                path.exists() for path in duplicates
            )
            run["pass"] = (
                run["return_zip_exists"]
                and run["return_sidecar_exists"]
                and run[
                    "duplicates_outside_mapped_namespace_absent"
                ]
                and mapping["only_allowed_mapping_delta"]
                and run["ndp_root_toplevel_unchanged"]
            )
            if mode == "normal":
                run["pass"] = (
                    run["pass"]
                    and run["runner_exit_code"] == 2
                    and "signal=NONE" in returned["signal_status"]
                    and "simulation_status=0"
                    in returned["signal_status"]
                    and "partial=false" in returned["signal_status"]
                    and returned["gate"]["result_gate_conjunction"][
                        "all_terms_true"
                    ] is False
                    and returned["gate"]["missing_count"] == 48
                )
            elif mode == "compile_fail":
                run["pass"] = (
                    run["pass"]
                    and run["runner_exit_code"] == 77
                    and "compile_status=77" in returned["signal_status"]
                )
            else:
                run["pass"] = (
                    run["pass"]
                    and run["runner_exit_code"] == 125
                    and f"signal={signal_name}"
                    in returned["signal_status"]
                    and returned["gate"]["result_gate_conjunction"][
                        "all_terms_true"
                    ] is False
                )
            modes[mode] = run

        negative_results = []
        for name, mutation in (
            (
                "fixed_target_conflict",
                {"precreate_result": True},
            ),
            (
                "original_location_duplicate",
                {"precreate_duplicate": True},
            ),
        ):
            case = base / f"negative_{name}"
            package = extract(target_zip, case / "fresh")
            result_root = case / "isolated_simresult_namespace"
            mapping = map_runner_for_harness(package, result_root)
            server = case / "server_root"
            server.mkdir(parents=True)
            (server / "install").mkdir()
            if mutation.get("precreate_result"):
                result_root.mkdir(parents=True)
                (result_root / f"{NAME}_return.zip").write_text(
                    "conflict", encoding="ascii"
                )
            run = run_runner(
                package,
                server,
                result_root,
                case / "tools",
                bash,
                "normal",
                precreate_duplicate=mutation.get(
                    "precreate_duplicate", False
                ),
            )
            failed_closed = (
                run["runner_exit_code"] not in (None, 0)
                and not (
                    result_root / f"{NAME}_return.zip.sha256"
                ).exists()
            )
            negative_results.append(
                {
                    "name": name,
                    "runner_exit_code": run["runner_exit_code"],
                    "safe_sim_stub_started": run[
                        "safe_sim_stub_started"
                    ],
                    "failed_closed": failed_closed,
                    "mapping": mapping,
                }
            )

        static_controls = []
        for name, mutated in (
            (
                "result_root_made_configurable",
                production_runner.replace(
                    f'result_root="{PRODUCTION_RESULT_ROOT}"',
                    'result_root="${GAP_RESULT_ROOT:-'
                    + PRODUCTION_RESULT_ROOT
                    + '}"',
                    1,
                ),
            ),
            (
                "collect_fixed_arg_removed",
                production_runner.replace(
                    '--result-root "$result_root"',
                    "--result-root .",
                    1,
                ),
            ),
            (
                "term_shared_path_removed",
                production_runner.replace(
                    "trap 'signal_name=TERM; simulation_status=125; "
                    "finalize 125' TERM",
                    "trap 'exit 125' TERM",
                    1,
                ),
            ),
        ):
            failed_closed = not (
                mutated.count(
                    f'result_root="{PRODUCTION_RESULT_ROOT}"'
                )
                == 1
                and "RESULT_ROOT" not in mutated
                and '--result-root "$result_root"' in mutated
                and "signal_name=TERM; simulation_status=125; "
                "finalize 125" in mutated
            )
            static_controls.append(
                {"name": name, "failed_closed": failed_closed}
            )

        corrupt_case = base / "negative_sidecar_corrupt"
        source_return = Path(modes["normal"]["return_zip"])
        corrupt_return = corrupt_case / source_return.name
        corrupt_case.mkdir()
        shutil.copy2(source_return, corrupt_return)
        corrupt_sidecar = Path(str(corrupt_return) + ".sha256")
        corrupt_sidecar.write_text(
            f"{'0' * 64}  {corrupt_return.name}\n",
            encoding="ascii",
        )
        try:
            validate_return(corrupt_return, production_manifest)
            sidecar_failed_closed = False
        except Exception:
            sidecar_failed_closed = True
        negative_results.append(
            {
                "name": "sidecar_corrupt",
                "failed_closed": sidecar_failed_closed,
            }
        )

        root_gate_negatives = []
        for mode in (
            "root_drift_file",
            "root_drift_directory",
            "root_drift_return_directory",
        ):
            case = base / f"negative_{mode}"
            package = extract(target_zip, case / "fresh")
            result_root = case / "isolated_simresult_namespace"
            mapping = map_runner_for_harness(package, result_root)
            server = case / "server_root"
            server.mkdir(parents=True)
            (server / "install").mkdir()
            before = sorted(
                (p.name, "directory" if p.is_dir() else "file")
                for p in server.iterdir()
            )
            run = run_runner(
                package,
                server,
                result_root,
                case / "tools",
                bash,
                mode,
            )
            after = sorted(
                (p.name, "directory" if p.is_dir() else "file")
                for p in server.iterdir()
            )
            returned = validate_return(
                result_root / f"{NAME}_return.zip",
                json.loads((package / MANIFEST).read_text(encoding="utf-8")),
            )
            receipt = returned["root_toplevel_receipt"]
            failed_closed = (
                run["runner_exit_code"] not in (None, 0)
                and before != after
                and receipt is not None
                and receipt.get("ndp_root_toplevel_unchanged") is False
                and receipt.get("pre_exact_set_sha256")
                != receipt.get("post_exact_set_sha256")
            )
            root_gate_negatives.append(
                {
                    "name": mode,
                    "runner_exit_code": run["runner_exit_code"],
                    "safe_sim_stub_started": run["safe_sim_stub_started"],
                    "before": before,
                    "after": after,
                    "root_receipt": receipt,
                    "failed_closed": failed_closed,
                    "mapping": mapping,
                }
            )

        missing_case = base / "negative_missing_existing_parent"
        package = extract(target_zip, missing_case / "fresh")
        result_root = missing_case / "isolated_simresult_namespace"
        mapping = map_runner_for_harness(package, result_root)
        server = missing_case / "server_root"
        server.mkdir(parents=True)
        before = sorted(
            (p.name, "directory" if p.is_dir() else "file")
            for p in server.iterdir()
        )
        run = run_runner(
            package,
            server,
            result_root,
            missing_case / "tools",
            bash,
            "normal",
        )
        after = sorted(
            (p.name, "directory" if p.is_dir() else "file")
            for p in server.iterdir()
        )
        root_gate_negatives.append(
            {
                "name": "missing_existing_parent",
                "runner_exit_code": run["runner_exit_code"],
                "safe_sim_stub_started": run["safe_sim_stub_started"],
                "before": before,
                "after": after,
                "return_zip_exists": run["return_zip_exists"],
                "failed_closed": (
                    run["runner_exit_code"] not in (None, 0)
                    and not run["safe_sim_stub_started"]
                    and not run["return_zip_exists"]
                    and before == after
                ),
                "mapping": mapping,
            }
        )

        drift_unblocked = production_runner.replace(
            '[ "$final" -ne 0 ] || [ "$root_top_status" -eq 0 ] '
            '|| final="$root_top_status"',
            ": # NEGATIVE: suppress root snapshot failure propagation",
            1,
        )
        drift_unblocked_failed_closed = not (
            '[ "$final" -ne 0 ] || [ "$root_top_status" -eq 0 ] '
            '|| final="$root_top_status"' in drift_unblocked
        )
        root_gate_negatives.append(
            {
                "name": "pre_post_drift_unblocked",
                "mutation_applied": drift_unblocked != production_runner,
                "failed_closed": (
                    drift_unblocked != production_runner
                    and drift_unblocked_failed_closed
                ),
            }
        )

    checks = {
        "production_runner_fixed_static": all(fixed_static.values()),
        "all_execution_modes_pass": all(
            item["pass"] for item in modes.values()
        ),
        "all_dynamic_negatives_fail_closed": all(
            item["failed_closed"] for item in negative_results
        ),
        "all_static_negatives_fail_closed": all(
            item["failed_closed"] for item in static_controls
        ),
        "all_root_toplevel_negatives_fail_closed": all(
            item["failed_closed"] for item in root_gate_negatives
        ),
        "production_zip_unchanged":
            sha_path(target_zip)
            == sha_bytes(
                Path(target_zip).read_bytes()
            ),
        "local_server_absolute_result_root_not_created": not Path(
            PRODUCTION_RESULT_ROOT
        ).exists(),
    }
    return {
        "schema": "gap-node0071-v47-fixed-result-runner-audit-v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "pass": all(checks.values()),
        "target_zip": str(target_zip),
        "target_zip_size_bytes": target_zip.stat().st_size,
        "target_zip_sha256": sha_path(target_zip),
        "production_runner_sha256": sha_bytes(target_files[RUNNER]),
        "production_manifest_sha256": sha_bytes(target_files[MANIFEST]),
        "fixed_static": fixed_static,
        "checks": checks,
        "execution_modes": modes,
        "dynamic_negative_controls": negative_results,
        "static_negative_controls": static_controls,
        "root_toplevel_negative_controls": root_gate_negatives,
        "server_or_real_compile_used": False,
        "production_runner_modified": False,
        "harness_mapping_only": True,
        "claim_boundary": (
            "The exact final runner is parsed byte-for-byte. A fresh-extract "
            "copy changes only the fixed result-root assignment and its "
            "manifest receipt inside an isolated local namespace so normal, "
            "compile-fail, HUP, INT, and TERM paths can exercise the exact "
            "remaining runner/finalizer logic without creating or writing "
            "/home/panqs/ndp/simresult locally. The mapping is absent from "
            "the production ZIP and the production path is not configurable."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-zip", type=Path, required=True)
    parser.add_argument(
        "--bash",
        type=Path,
        default=Path(r"C:\Program Files\Git\bin\bash.exe"),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = validate(
            args.target_zip.resolve(), args.bash.resolve()
        )
        exit_code = 0 if result["pass"] else 1
    except Exception as error:
        result = {
            "schema": "gap-node0071-v47-fixed-result-runner-audit-v1",
            "status": "FAIL",
            "pass": False,
            "error": str(error),
        }
        exit_code = 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    sys.stdout.buffer.write(
        (
            json.dumps(result, indent=2, ensure_ascii=False) + "\n"
        ).encode("utf-8", errors="replace")
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
