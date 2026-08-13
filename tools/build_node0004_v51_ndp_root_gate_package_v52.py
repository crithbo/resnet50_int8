from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
SOURCE_NAME = "r5_n4_hw_v51_lc13_lc14_diag"
INSTALL_NAME = "r5_n4_hw_v52_ndproot_gate"
SOURCE_SHA256 = "23d421c38b310bc458c6305fea33d9372a217a3bc2fced6e796e6368510964f0"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{SOURCE_NAME}.zip"
)
DEFAULT_OUTPUT = ROOT / "outputs/conv_node0004_v51_ndp_root_gate_revalidation/v52_build"
SERVER_RULE_SHA256 = "b1a29b114c57a89dadd56dbb293aeba545cd3acfb3200cadc15058126f359724"
INDEX_SHA256 = "1253c18b0008f3a06d509ae15ddaf2c4cd1e95c88f7cd73ec48adaafc7249500"
PLAN_SHA256 = "43fe7b8c5b7d5d8daf1631f1d01cca1450ef13d7a4891722ebc509061e166e70"


class BuildError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def package_records(package: Path) -> dict[str, str]:
    manifest = package / "package_manifest.json"
    return {
        path.relative_to(package).as_posix(): sha256(path)
        for path in sorted(item for item in package.rglob("*") if item.is_file())
        if path != manifest
    }


def extract(destination: Path) -> Path:
    if sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("v51 source SHA differs")
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise BuildError(f"v51 source CRC failed at {bad}")
        roots: set[str] = set()
        seen: set[str] = set()
        for info in archive.infolist():
            path = PurePosixPath(info.filename)
            if (
                path.is_absolute()
                or ".." in path.parts
                or "\\" in info.filename
                or info.filename in seen
            ):
                raise BuildError(f"unsafe/duplicate member: {info.filename}")
            seen.add(info.filename)
            if path.parts:
                roots.add(path.parts[0])
        if roots != {SOURCE_NAME}:
            raise BuildError(f"v51 root differs: {sorted(roots)}")
        archive.extractall(destination)
    return destination / SOURCE_NAME


def replace_identity(package: Path) -> None:
    for path in package.rglob("*"):
        if not path.is_file() or path.suffix.lower() == ".bin":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if SOURCE_NAME in text:
            path.write_text(
                text.replace(SOURCE_NAME, INSTALL_NAME),
                encoding="utf-8",
                newline="\n",
            )


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise BuildError(f"{label} anchor count={text.count(old)}")
    return text.replace(old, new, 1)


def patch_base_runtime(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    helpers = r'''

def root_snapshot(server_root: Path) -> dict[str, Any]:
    root = server_root.resolve()
    if not root.is_dir() or root.is_symlink():
        raise DiagnosticRuntimeError("NDP root must be a real directory")
    entries: list[dict[str, str]] = []
    for child in sorted(root.iterdir(), key=lambda item: item.name):
        if child.is_symlink():
            kind = "symlink"
        elif child.is_dir():
            kind = "directory"
        elif child.is_file():
            kind = "file"
        else:
            kind = "other"
        entries.append({"name": child.name, "type": kind})
    canonical = json.dumps(
        entries, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return {
        "schema": "ndp-root-toplevel-exact-set-v1",
        "server_root": str(root),
        "entry_count": len(entries),
        "entries": entries,
        "exact_set_sha256": hashlib.sha256(canonical).hexdigest(),
    }


def compare_root_snapshots(
    pre_path: Path, post_path: Path, contract_path: Path
) -> dict[str, Any]:
    pre = load_json(pre_path)
    post = load_json(post_path)
    contract = load_json(contract_path)
    declared_parents = contract.get("existing_first_level_parents", [])
    pre_dirs = {
        entry.get("name")
        for entry in pre.get("entries", [])
        if entry.get("type") == "directory"
    }
    missing_parents = sorted(set(declared_parents) - pre_dirs)
    same_root = pre.get("server_root") == post.get("server_root")
    same_entries = pre.get("entries") == post.get("entries")
    same_sha = (
        pre.get("exact_set_sha256") == post.get("exact_set_sha256")
    )
    unchanged = same_root and same_entries and same_sha and not missing_parents
    return {
        "schema": "ndp-root-toplevel-gate-v1",
        "server_root": pre.get("server_root"),
        "pre_exact_set_sha256": pre.get("exact_set_sha256"),
        "post_exact_set_sha256": post.get("exact_set_sha256"),
        "pre_entry_count": pre.get("entry_count"),
        "post_entry_count": post.get("entry_count"),
        "ndp_root_toplevel_unchanged": unchanged,
        "missing_declared_existing_parents": missing_parents,
        "root_internal_write_targets": contract.get(
            "root_internal_write_targets", []
        ),
        "existing_first_level_parents": declared_parents,
        "result_root": contract.get("result_root"),
        "valid": unchanged,
        "failure_class": (
            None
            if unchanged
            else "SERVER_NDP_ROOT_TOPLEVEL_ENTRY_CREATED_OR_CHANGED"
        ),
    }
'''
    text = replace_once(
        text,
        "\ndef collect(\n",
        helpers + "\n\ndef collect(\n",
        "base runtime root helpers",
    )
    text = replace_once(
        text,
        "def collect(\n"
        "    server_root: Path,\n"
        "    install_name: str,\n"
        "    evidence_root: Path,\n"
        "    run_root: Path,\n"
        ") -> dict[str, Any]:",
        "def collect(\n"
        "    server_root: Path,\n"
        "    ndp_root: Path,\n"
        "    install_name: str,\n"
        "    evidence_root: Path,\n"
        "    run_root: Path,\n"
        ") -> dict[str, Any]:",
        "base collect signature",
    )
    text = replace_once(
        text,
        '        (evidence_root / "publication_preflight.json", "evidence/publication_preflight.json", True),\n',
        '        (evidence_root / "publication_preflight.json", "evidence/publication_preflight.json", True),\n'
        '        (evidence_root / "ndp_root_toplevel_pre.json", "evidence/ndp_root_toplevel_pre.json", True),\n'
        '        (evidence_root / "ndp_root_toplevel_post.json", "evidence/ndp_root_toplevel_post.json", True),\n'
        '        (evidence_root / "ndp_root_write_contract.json", "evidence/ndp_root_write_contract.json", True),\n'
        '        (evidence_root / "ndp_root_toplevel_gate.json", "evidence/ndp_root_toplevel_gate.json", True),\n',
        "base return items",
    )
    text = replace_once(
        text,
        "    records.sort(key=lambda item: item[\"path\"])\n"
        "    publication_contract = {",
        "    root_gate = load_json(evidence_root / \"ndp_root_toplevel_gate.json\")\n"
        "    if (\n"
        "        root_gate.get(\"schema\") != \"ndp-root-toplevel-gate-v1\"\n"
        "        or root_gate.get(\"server_root\") != str(ndp_root.resolve())\n"
        "    ):\n"
        "        raise DiagnosticRuntimeError(\"NDP root top-level receipt differs\")\n"
        "    records.sort(key=lambda item: item[\"path\"])\n"
        "    publication_contract = {",
        "base root gate load",
    )
    text = replace_once(
        text,
        '        "launch_cwd_duplicate_absent": True,\n'
        "    }\n"
        "    allowlist = {",
        '        "launch_cwd_duplicate_absent": True,\n'
        '        "ndp_root_toplevel": {\n'
        '            "server_root": root_gate["server_root"],\n'
        '            "pre_exact_set_sha256": root_gate["pre_exact_set_sha256"],\n'
        '            "post_exact_set_sha256": root_gate["post_exact_set_sha256"],\n'
        '            "ndp_root_toplevel_unchanged": root_gate["ndp_root_toplevel_unchanged"],\n'
        '            "existing_first_level_parents": root_gate["existing_first_level_parents"],\n'
        '            "root_internal_write_targets": root_gate["root_internal_write_targets"],\n'
        '        },\n'
        "    }\n"
        "    allowlist = {",
        "base publication contract",
    )
    text = text.replace(
        '"node0004-hang-localization-return-allowlist-v8"',
        '"node0004-hang-localization-return-allowlist-v9"',
    )
    text = text.replace(
        '"node0004-return-manifest-v25"',
        '"node0004-return-manifest-v26"',
    )
    text = replace_once(
        text,
        '    col.add_argument("--server-root", type=Path, required=True)\n'
        '    col.add_argument("--install-name", required=True)',
        '    snap = sub.add_parser("root-snapshot")\n'
        '    snap.add_argument("--server-root", type=Path, required=True)\n'
        '    cmp_root = sub.add_parser("root-compare")\n'
        '    cmp_root.add_argument("--pre", type=Path, required=True)\n'
        '    cmp_root.add_argument("--post", type=Path, required=True)\n'
        '    cmp_root.add_argument("--contract", type=Path, required=True)\n'
        '    col.add_argument("--server-root", type=Path, required=True)\n'
        '    col.add_argument("--ndp-root", type=Path, required=True)\n'
        '    col.add_argument("--install-name", required=True)',
        "base CLI parsers",
    )
    text = replace_once(
        text,
        '    elif args.command == "verify-install":\n'
        "        value = verify_install(args.package_root, args.cfg_root)\n"
        "    elif args.command == \"analyze\":\n"
        "        value = analyze(args.package_root, args.evidence_root, args.run_root)\n"
        "    else:\n"
        "        value = collect(\n"
        "            args.server_root,\n"
        "            args.install_name,\n"
        "            args.evidence_root,\n"
        "            args.run_root,\n"
        "        )\n"
        "    print(json.dumps(value, ensure_ascii=False))\n"
        "    return 0",
        '    elif args.command == "verify-install":\n'
        "        value = verify_install(args.package_root, args.cfg_root)\n"
        '    elif args.command == "analyze":\n'
        "        value = analyze(args.package_root, args.evidence_root, args.run_root)\n"
        '    elif args.command == "root-snapshot":\n'
        "        value = root_snapshot(args.server_root)\n"
        '    elif args.command == "root-compare":\n'
        "        value = compare_root_snapshots(args.pre, args.post, args.contract)\n"
        "    else:\n"
        "        value = collect(\n"
        "            args.server_root,\n"
        "            args.ndp_root,\n"
        "            args.install_name,\n"
        "            args.evidence_root,\n"
        "            args.run_root,\n"
        "        )\n"
        "    print(json.dumps(value, ensure_ascii=False, sort_keys=True))\n"
        '    return 0 if value.get("valid", True) is True else 96',
        "base CLI dispatch",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_wrapper_runtime(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        '"node0004-return-manifest-v25"',
        '"node0004-return-manifest-v26"',
    )
    text = replace_once(
        text,
        "def collect(\n"
        "    server_root: Path,\n"
        "    install_name: str,\n"
        "    evidence_root: Path,\n"
        "    run_root: Path,\n"
        ") -> dict[str, Any]:\n"
        "    result = _base_collect(server_root, install_name, evidence_root, run_root)",
        "def collect(\n"
        "    server_root: Path,\n"
        "    ndp_root: Path,\n"
        "    install_name: str,\n"
        "    evidence_root: Path,\n"
        "    run_root: Path,\n"
        ") -> dict[str, Any]:\n"
        "    result = _base_collect(\n"
        "        server_root, ndp_root, install_name, evidence_root, run_root\n"
        "    )",
        "wrapper collect",
    )
    text = replace_once(
        text,
        '    write_json(evidence_root / "SERVER_RESULT_GATE.json", value)\n'
        "    return value",
        '    root_gate_path = evidence_root / "ndp_root_toplevel_gate.json"\n'
        "    if root_gate_path.is_file():\n"
        "        root_gate = json.loads(root_gate_path.read_text(encoding=\"utf-8\"))\n"
        "        value[\"ndp_root_toplevel\"] = root_gate\n"
        "        if root_gate.get(\"ndp_root_toplevel_unchanged\") is not True:\n"
        "            value[\"status\"] = \"SERVER_NDP_ROOT_TOPLEVEL_ENTRY_CREATED_OR_CHANGED\"\n"
        '    write_json(evidence_root / "SERVER_RESULT_GATE.json", value)\n'
        "    return value",
        "wrapper result gate",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_runner(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        'launch_cwd="$(pwd -P)"\n'
        'mkdir -p -- "$result_root" || exit 9',
        'launch_cwd="$(pwd -P)"\n'
        'for tool in python3 timeout make; do command -v "$tool" >/dev/null 2>&1 || exit 3; done\n'
        'ndp_pre_snapshot="$(python3 "$runtime" root-snapshot --server-root "$server_root")" || exit 12\n'
        'mkdir -p -- "$result_root" || exit 9',
        "runner pre snapshot",
    )
    text = replace_once(
        text,
        'for tool in python3 timeout make; do command -v "$tool" >/dev/null 2>&1 || exit 3; done\n'
        'python3 "$runtime" path-budget',
        'python3 "$runtime" path-budget',
        "runner duplicate tool gate",
    )
    text = replace_once(
        text,
        'mkdir -p "$cfg_root" "$run_root/compile/sim_results" "$run_root/c0" "$evidence_root"\n'
        'cat > "$evidence_root/publication_preflight.json"',
        'mkdir -p "$cfg_root" "$run_root/compile/sim_results" "$run_root/c0" "$evidence_root"\n'
        'printf \'%s\\n\' "$ndp_pre_snapshot" > "$evidence_root/ndp_root_toplevel_pre.json"\n'
        'cat > "$evidence_root/ndp_root_write_contract.json" <<EOF\n'
        '{\n'
        '  "schema": "ndp-root-write-contract-v1",\n'
        '  "server_root": "${server_root}",\n'
        '  "result_root": "/home/panqs/ndp/simresult",\n'
        '  "root_internal_write_targets": [],\n'
        '  "existing_first_level_parents": [],\n'
        '  "external_write_targets": [\n'
        '    "/home/panqs/ndp/simresult/.${install_name}.run.<pid>",\n'
        '    "/home/panqs/ndp/simresult/${install_name}_return.zip",\n'
        '    "/home/panqs/ndp/simresult/${install_name}_return.zip.sha256"\n'
        '  ]\n'
        '}\n'
        'EOF\n'
        'cat > "$evidence_root/publication_preflight.json"',
        "runner pre receipt",
    )
    text = replace_once(
        text,
        '  printf \'%s\\n\' "$signal_status" > "$evidence_root/signal_status.txt"\n'
        '  python3 "$runtime" analyze',
        '  printf \'%s\\n\' "$signal_status" > "$evidence_root/signal_status.txt"\n'
        '  python3 "$runtime" root-snapshot --server-root "$server_root" > "$evidence_root/ndp_root_toplevel_post.json"\n'
        '  post_snapshot=$?\n'
        '  root_gate=96\n'
        '  if [ "$post_snapshot" -eq 0 ]; then\n'
        '    python3 "$runtime" root-compare \\\n'
        '      --pre "$evidence_root/ndp_root_toplevel_pre.json" \\\n'
        '      --post "$evidence_root/ndp_root_toplevel_post.json" \\\n'
        '      --contract "$evidence_root/ndp_root_write_contract.json" \\\n'
        '      > "$evidence_root/ndp_root_toplevel_gate.json"\n'
        '    root_gate=$?\n'
        '  fi\n'
        '  python3 "$runtime" analyze',
        "runner post compare",
    )
    text = replace_once(
        text,
        '  python3 "$runtime" collect --server-root "$result_root"     --install-name "$install_name"',
        '  python3 "$runtime" collect --server-root "$result_root" --ndp-root "$server_root"     --install-name "$install_name"',
        "runner collect root bind",
    )
    text = replace_once(
        text,
        '  [ "$final" -ne 0 ] || [ "$collection" -eq 0 ] || final="$collection"\n'
        '  exit "$final"',
        '  [ "$final" -ne 0 ] || [ "$collection" -eq 0 ] || final="$collection"\n'
        '  [ "$final" -ne 0 ] || [ "$root_gate" -eq 0 ] || final="$root_gate"\n'
        '  exit "$final"',
        "runner root fail closed",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def update_manifest(package: Path) -> None:
    path = package / "package_manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["install_name"] = INSTALL_NAME
    receipts = manifest.setdefault("active_receipts", {})
    receipts["generation_index_sha256"] = INDEX_SHA256
    receipts["server_package_rule_sha256"] = SERVER_RULE_SHA256
    rules = receipts.setdefault("rules", [])
    rule_id = "CDA-SERVER-NDP-ROOT-TOPLEVEL-NO-NEW-ENTRY-001"
    if rule_id not in rules:
        rules.append(rule_id)
    manifest["ndp_root_toplevel_contract"] = {
        "schema": "ndp-root-toplevel-contract-v1",
        "rule_id": rule_id,
        "server_root_source": "single absolute runner argument",
        "snapshot_before_any_write": True,
        "direct_child_fields": ["name", "type"],
        "canonical_order": "UTF-8 name ascending",
        "root_internal_write_targets": [],
        "existing_first_level_parents": [],
        "work_root": (
            f"/home/panqs/ndp/simresult/.{INSTALL_NAME}.run.<pid>"
        ),
        "result_root": "/home/panqs/ndp/simresult",
        "post_snapshot_in_shared_finalizer": True,
        "return_receipts": [
            "evidence/ndp_root_toplevel_pre.json",
            "evidence/ndp_root_toplevel_post.json",
            "evidence/ndp_root_write_contract.json",
            "evidence/ndp_root_toplevel_gate.json",
        ],
        "failure_class": "SERVER_NDP_ROOT_TOPLEVEL_ENTRY_CREATED_OR_CHANGED",
        "failure_exit_code": 96,
    }
    manifest["v51_hold_adjudication"] = {
        "source_zip_sha256": SOURCE_SHA256,
        "status": "PACKAGE_HELD_NDP_ROOT_TOPLEVEL_GATE_REQUIRED",
        "replacement": INSTALL_NAME,
        "numeric_or_config_change": False,
    }
    matrix = manifest.setdefault("release_gate_matrix", [])
    matrix.append(
        {
            "gate_id": "NDP_ROOT_TOPLEVEL_EXACT_SET",
            "applicability": "blocking_applicable",
            "reason": "v52 adds the user-required exact final-runner root gate",
            "changed_surface": [
                "PREPARE_AND_RUN.sh pre/post snapshot and fail-closed finalizer",
                "runtime root snapshot/compare and return receipts",
            ],
            "evidence": [
                "normal/compile-fail/HUP/INT/TERM isolated exact-runner controls",
                "root-directory/root-file/missing-parent/unblocked-drift negatives",
            ],
            "blocking": True,
        }
    )
    manifest["files"] = package_records(package)
    write_json(path, manifest)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["files"] = package_records(package)
    write_json(path, manifest)


def deterministic_zip(package: Path, target: Path) -> None:
    with zipfile.ZipFile(
        target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(item for item in package.rglob("*") if item.is_file()):
            relative = (
                PurePosixPath(package.name)
                / PurePosixPath(path.relative_to(package).as_posix())
            ).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100644 & 0xFFFF) << 16
            if path.name == "PREPARE_AND_RUN.sh":
                info.external_attr = (0o100755 & 0xFFFF) << 16
            archive.writestr(info, path.read_bytes(), compresslevel=9)


def build_directory(output: Path) -> Path:
    package = output / INSTALL_NAME
    if package.exists():
        raise BuildError(f"refusing to overwrite: {package}")
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="node0004-v51-source-") as temp:
        shutil.copytree(extract(Path(temp)), package)
    replace_identity(package)
    patch_base_runtime(
        package / "package_tools/node0004_hang_localization_runtime_v7.py"
    )
    patch_wrapper_runtime(
        package / "package_tools/node0004_hang_localization_runtime.py"
    )
    patch_runner(package / "PREPARE_AND_RUN.sh")
    provenance = {
        "schema": "node0004-v51-to-v52-ndp-root-gate-v1",
        "source_v51_sha256": SOURCE_SHA256,
        "classification": "RUNNER_ONLY_RULE_COMPLIANCE_REPLACEMENT",
        "numeric_frozen": True,
        "workload_frozen": True,
        "configuration_frozen": True,
        "golden_frozen": True,
        "observer_frozen": True,
        "timeout_frozen": True,
        "functional_rtl_modified": False,
        "changed_surface": [
            "PREPARE_AND_RUN.sh",
            "package_tools/node0004_hang_localization_runtime.py",
            "package_tools/node0004_hang_localization_runtime_v7.py",
            "package_manifest.json",
            "README.md",
        ],
    }
    write_json(
        package / "provenance/v51_to_v52_ndp_root_gate.json",
        provenance,
    )
    (package / "README.md").write_text(
        "# node0004 v52 NDP-root top-level gate\n\n"
        "Classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`.\n\n"
        "This is a runner-only compliance replacement for held v51. It keeps "
        "the LC13/LC14 diagnostic, numeric payload, workload, config, golden, "
        "observer, timeout, backpressure and functional RTL frozen. Before "
        "any write, the exact runner records the NDP root direct-child "
        "name/type set. The shared normal/compile-fail/HUP/INT/TERM finalizer "
        "records the post set, returns both receipts, and fails closed on any "
        "difference. Work and final return remain under the fixed server "
        "`/home/panqs/ndp/simresult` root.\n\n"
        f"Run: `bash {INSTALL_NAME}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy`\n\n"
        f"Expected return: `/home/panqs/ndp/simresult/{INSTALL_NAME}_return.zip`.\n",
        encoding="utf-8",
        newline="\n",
    )
    update_manifest(package)
    return package


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output_root.resolve()
    targets = [
        output / INSTALL_NAME,
        output / f"{INSTALL_NAME}.zip",
        output / f"{INSTALL_NAME}.zip.sha256",
        output / f"{INSTALL_NAME}.validation.json",
    ]
    if any(path.exists() for path in targets):
        raise BuildError("refusing to overwrite existing v52 target")
    package = build_directory(output)
    zip_path = output / f"{INSTALL_NAME}.zip"
    deterministic_zip(package, zip_path)
    digest = sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix="node0004-v52-repeat-") as temp:
        repeat = build_directory(Path(temp))
        repeat_zip = Path(temp) / f"{INSTALL_NAME}.zip"
        deterministic_zip(repeat, repeat_zip)
        deterministic = sha256(repeat_zip) == digest
    if not deterministic:
        raise BuildError("v52 deterministic rebuild differs")
    sidecar = output / f"{INSTALL_NAME}.zip.sha256"
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    report = {
        "schema": "node0004-v51-to-v52-ndp-root-gate-build-v1",
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "deterministic_rebuild_equal": deterministic,
        "source_v51_sha256": SOURCE_SHA256,
        "current_server_rule_sha256": SERVER_RULE_SHA256,
        "current_generation_index_sha256": INDEX_SHA256,
        "builder_plan_mutable_provenance_sha256": PLAN_SHA256,
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": False,
        "observer_rebuilt": False,
        "functional_rtl_modified": False,
        "server_action": False,
    }
    write_json(output / f"{INSTALL_NAME}.validation.json", report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
