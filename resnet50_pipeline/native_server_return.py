from __future__ import annotations

import hashlib
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping

from .hashing import sha256_file


REPORT_SCHEMA = "native-ndp-server-return-report-v1"
PROFILE_SCHEMA = "native-ndp-server-return-profile-v1"

CHECKPOINTS = (
    "invocation",
    "sca_binding",
    "preload",
    "execplan",
    "dispatch",
    "slice_start",
    "read_request",
    "read_return",
    "compute_finish",
    "write_address",
    "write_data",
    "global_complete",
    "readback",
    "numeric_compare",
)

_LOCAL_LOG_RE = re.compile(
    r"(?:^|/)local/slice(?P<slice>\d+)/"
    r"local_mse(?P<mse>\d+)_(?P<kind>req|rdata|wdata)\.log$"
)
_SEM_LOG_RE = re.compile(
    r"(?:^|/)sem_events/slice(?P<slice>\d+)/sem_events\.log$"
)
_SLICE_FROM_KEY_RE = re.compile(r"slice(?P<slice>\d+)$")
_PLUSARG_RE = re.compile(r"\+(?P<name>SCA_CFG(?:_D)?)=(?P<value>\S+)")


class NativeServerReturnError(ValueError):
    pass


@dataclass(frozen=True)
class _Entry:
    name: str
    size: int


class _Evidence:
    def __init__(self, path: Path):
        self.path = path.resolve()
        self.kind: str
        self._entries: dict[str, _Entry] = {}
        self._directory_paths: dict[str, Path] = {}
        if self.path.is_dir():
            self.kind = "directory"
            for item in sorted(self.path.rglob("*")):
                if not item.is_file():
                    continue
                if item.is_symlink():
                    raise NativeServerReturnError(
                        f"return directory contains a symlink: {item}"
                    )
                name = item.relative_to(self.path).as_posix()
                self._entries[name] = _Entry(name=name, size=item.stat().st_size)
                self._directory_paths[name] = item
        elif self.path.is_file() and self.path.suffix.lower() == ".zip":
            self.kind = "zip"
            with zipfile.ZipFile(self.path) as archive:
                for info in archive.infolist():
                    if info.is_dir():
                        continue
                    name = info.filename.replace("\\", "/")
                    pure = PurePosixPath(name)
                    if pure.is_absolute() or ".." in pure.parts:
                        raise NativeServerReturnError(
                            f"unsafe return ZIP entry: {info.filename}"
                        )
                    normalized = pure.as_posix()
                    if normalized in self._entries:
                        raise NativeServerReturnError(
                            f"duplicate return ZIP entry: {normalized}"
                        )
                    self._entries[normalized] = _Entry(
                        name=normalized, size=info.file_size
                    )
        else:
            raise NativeServerReturnError(
                f"return evidence must be a directory or ZIP: {self.path}"
            )
        if not self._entries:
            raise NativeServerReturnError(f"return evidence is empty: {self.path}")

    @property
    def names(self) -> list[str]:
        return sorted(self._entries)

    def read_bytes(self, name: str) -> bytes:
        if name not in self._entries:
            raise NativeServerReturnError(f"return entry is missing: {name}")
        if self.kind == "directory":
            return self._directory_paths[name].read_bytes()
        with zipfile.ZipFile(self.path) as archive:
            return archive.read(name)

    def read_text(self, name: str) -> str:
        return self.read_bytes(name).decode("utf-8", errors="replace")

    def sha256(self) -> str:
        if self.kind == "zip":
            return sha256_file(self.path)
        digest = hashlib.sha256()
        for name in self.names:
            payload = self.read_bytes(name)
            digest.update(name.encode("utf-8"))
            digest.update(b"\0")
            digest.update(str(len(payload)).encode("ascii"))
            digest.update(b"\0")
            digest.update(hashlib.sha256(payload).hexdigest().encode("ascii"))
            digest.update(b"\n")
        return digest.hexdigest()

    def find_suffixes(self, suffixes: Iterable[str]) -> list[str]:
        normalized = [item.replace("\\", "/").lstrip("/") for item in suffixes]
        return [
            name
            for name in self.names
            if any(name == suffix or name.endswith("/" + suffix) for suffix in normalized)
        ]

    def select_sim_log(self) -> str:
        candidates = [
            name for name in self.names if name == "sim.log" or name.endswith("/sim.log")
        ]
        if not candidates:
            raise NativeServerReturnError("server return has no sim.log")

        def rank(name: str) -> tuple[int, int, int, str]:
            preferred = 0 if name == "sim.log" else 1 if name.endswith("sim_results/sim.log") else 2
            return (preferred, name.count("/"), -self._entries[name].size, name)

        return min(candidates, key=rank)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise NativeServerReturnError(f"cannot parse JSON: {path}: {error}") from error
    if not isinstance(value, dict):
        raise NativeServerReturnError(f"JSON root must be an object: {path}")
    return value


def _discover_unique(root: Path, name: str) -> Path:
    direct = root / name
    if direct.is_file():
        return direct
    candidates = sorted(root.rglob(name))
    if len(candidates) != 1:
        raise NativeServerReturnError(
            f"workload must contain exactly one {name}, found {len(candidates)}"
        )
    return candidates[0]


def _path_entries(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for key, raw in config.items():
        if not isinstance(raw, Mapping) or not isinstance(raw.get("path"), str):
            continue
        item = {"key": str(key), "path": str(raw["path"])}
        if "base_addr" in raw:
            item["base_addr"] = str(raw["base_addr"])
        if "length" in raw:
            item["length"] = int(raw["length"])
        match = _SLICE_FROM_KEY_RE.search(str(key))
        if match:
            item["slice_id"] = int(match.group("slice"))
        entries.append(item)
    return entries


def _workload_file_manifest(
    root: Path, *, excluded: set[str] | None = None
) -> dict[str, dict[str, Any]]:
    excluded = excluded or set()
    result: dict[str, dict[str, Any]] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if relative in excluded:
            continue
        if path.is_symlink():
            raise NativeServerReturnError(
                f"workload directory contains a symlink: {relative}"
            )
        result[relative] = {
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    return result


def _tree_sha256(files: Mapping[str, Mapping[str, Any]]) -> str:
    digest = hashlib.sha256()
    for relative, item in sorted(files.items()):
        digest.update(
            f"{relative}\0{item['size_bytes']}\0{item['sha256']}\n".encode(
                "utf-8"
            )
        )
    return digest.hexdigest()


def _workload_contract(workload_root: Path) -> dict[str, Any]:
    root = workload_root.resolve()
    if not root.is_dir():
        raise NativeServerReturnError(f"workload directory is missing: {root}")
    sca_path = _discover_unique(root, "sca_cfg.json")
    sca_d_path = _discover_unique(root, "sca_cfg_D.json")
    sca = _load_json(sca_path)
    sca_d = _load_json(sca_d_path)
    main_entries = _path_entries(sca)
    d_entries = _path_entries(sca_d)
    if not main_entries or not d_entries:
        raise NativeServerReturnError("workload SCA path entries are incomplete")
    for entry in main_entries + d_entries:
        target = root / str(entry["path"])
        try:
            target.resolve().relative_to(root)
        except ValueError as error:
            raise NativeServerReturnError(
                f"workload SCA path escapes root: {entry['path']}"
            ) from error
        if not target.is_file():
            raise NativeServerReturnError(
                f"workload SCA payload is missing: {entry['path']}"
            )

    manifests = sorted(
        path
        for path in root.glob("*manifest.json")
        if path.name not in {"sca_cfg.json", "sca_cfg_D.json"}
    )
    manifest_path = manifests[0] if len(manifests) == 1 else None
    manifest = _load_json(manifest_path) if manifest_path else {}
    excluded = (
        {manifest_path.relative_to(root).as_posix()} if manifest_path else set()
    )
    workload_files = _workload_file_manifest(root, excluded=excluded)
    workload_tree_sha256 = _tree_sha256(workload_files)
    declared_files = manifest.get("files")
    if isinstance(declared_files, Mapping):
        if declared_files != workload_files:
            raise NativeServerReturnError(
                "workload files differ from the package manifest"
            )
        if manifest.get("file_count") != len(workload_files):
            raise NativeServerReturnError(
                "workload file_count differs from the package manifest"
            )
        if manifest.get("tree_sha256") != workload_tree_sha256:
            raise NativeServerReturnError(
                "workload tree_sha256 differs from the package manifest"
            )
    active_slices = sorted(
        {
            int(entry["slice_id"])
            for entry in d_entries
            if isinstance(entry.get("slice_id"), int)
        }
    )
    return {
        "root": root,
        "root_name": root.name,
        "sca_path": sca_path,
        "sca_d_path": sca_d_path,
        "sca": sca,
        "sca_d": sca_d,
        "main_entries": main_entries,
        "d_entries": d_entries,
        "active_slices": active_slices,
        "exec_length": int(sca.get("Exec_Length", -1)),
        "preload_object_count": len(main_entries),
        "readback_matrix_count": len(d_entries),
        "manifest_path": manifest_path,
        "manifest": manifest,
        "workload_tree_sha256": workload_tree_sha256,
    }


def _validate_profile(
    profile_path: Path | None, contract: Mapping[str, Any]
) -> dict[str, Any]:
    if profile_path is None:
        return {
            "schema": PROFILE_SCHEMA,
            "profile_id": f"auto:{contract['root_name']}",
            "workload_binding": {},
            "expected": {},
            "diagnostics": {},
        }
    profile = _load_json(profile_path.resolve())
    if profile.get("schema") != PROFILE_SCHEMA:
        raise NativeServerReturnError("server return profile schema differs")
    binding = profile.get("workload_binding")
    if not isinstance(binding, Mapping):
        raise NativeServerReturnError("server return profile workload binding is missing")
    expected_hashes = {
        "sca_cfg_sha256": sha256_file(contract["sca_path"]),
        "sca_cfg_D_sha256": sha256_file(contract["sca_d_path"]),
        "payload_tree_sha256": contract["workload_tree_sha256"],
    }
    manifest_path = contract.get("manifest_path")
    if isinstance(manifest_path, Path):
        expected_hashes["manifest_sha256"] = sha256_file(manifest_path)
    for key, actual in expected_hashes.items():
        declared = binding.get(key)
        if declared is not None and declared != actual:
            raise NativeServerReturnError(
                f"server return profile {key} differs from workload"
            )
    expected = profile.get("expected")
    if not isinstance(expected, Mapping):
        raise NativeServerReturnError("server return profile expected block is missing")
    checks = {
        "exec_length": contract["exec_length"],
        "preload_object_count": contract["preload_object_count"],
        "readback_matrix_count": contract["readback_matrix_count"],
        "active_slices": contract["active_slices"],
    }
    for key, actual in checks.items():
        if key in expected and expected[key] != actual:
            raise NativeServerReturnError(
                f"server return profile {key} differs from workload"
            )
    return profile


def _last_int(pattern: str, text: str) -> int | None:
    matches = re.findall(pattern, text, flags=re.MULTILINE)
    return int(matches[-1]) if matches else None


def _using_path(label: str, text: str) -> str | None:
    pattern = rf"Using SCA cfg{label} file:\s*(?P<path>\S+)"
    matches = re.findall(pattern, text)
    return matches[-1] if matches else None


def _parse_sim_log(text: str) -> dict[str, Any]:
    command_lines = re.findall(r"^Command:\s*(.+)$", text, flags=re.MULTILINE)
    command = command_lines[-1] if command_lines else None
    plusargs: dict[str, str] = {}
    if command:
        for match in _PLUSARG_RE.finditer(command):
            plusargs[match.group("name")] = match.group("value")
    using_sca = _using_path("", text)
    using_sca_d = _using_path(" D", text)
    preload_count = _last_int(r"JSON config:\s*(\d+)\s+matrices loaded", text)
    exec_length = _last_int(r"JSON:\s*Exec_Length\s*=\s*(\d+)", text)
    readback_count = _last_int(r"JSON_D config:\s*(\d+)\s+matrices dumped", text)
    completion_cycles = [
        int(value)
        for value in re.findall(
            r"slice completed(?: after)?\s*(\d+)\s*cycles", text, flags=re.IGNORECASE
        )
    ]
    error_patterns = {
        "cannot_open": r"Cannot open",
        "readback_skipped": r"skip matrix readback",
        "softmax_fallback": r"sca_cfg_D_softmax\.json",
        "external_termination": r"\b(?:SIGHUP|SIGTERM|SIGKILL|killed|terminated)\b",
        "fatal": r"(?:^|\n)\s*(?:Fatal|FATAL|\$fatal|Error-\[)",
    }
    errors = {
        key: len(re.findall(pattern, text, flags=re.IGNORECASE))
        for key, pattern in error_patterns.items()
    }
    return {
        "command": command,
        "command_plusargs": plusargs,
        "using_sca_cfg": using_sca,
        "using_sca_cfg_D": using_sca_d,
        "preload_object_count": preload_count,
        "exec_length": exec_length,
        "slice_start_count": len(
            re.findall(r"INFO:\s*slice start", text, flags=re.IGNORECASE)
        ),
        "completion_cycles": completion_cycles,
        "readback_matrix_count": readback_count,
        "simulation_success_marker": "Simulation completed successfully!" in text,
        "errors": errors,
    }


def _data_lines(text: str) -> list[str]:
    return [
        line
        for line in text.splitlines()
        if re.match(r"^\s*\d+\s*\|", line)
    ]


def _parse_auxiliary_logs(evidence: _Evidence) -> dict[str, Any]:
    per_slice: dict[int, dict[int, dict[str, int]]] = {}
    for name in evidence.names:
        match = _LOCAL_LOG_RE.search(name)
        if not match:
            continue
        slice_id = int(match.group("slice"))
        mse = int(match.group("mse"))
        kind = match.group("kind")
        lines = _data_lines(evidence.read_text(name))
        item = per_slice.setdefault(slice_id, {}).setdefault(
            mse,
            {
                "request": 0,
                "read_address": 0,
                "write_address": 0,
                "read_data": 0,
                "write_data": 0,
            },
        )
        if kind == "req":
            item["request"] += len(lines)
            for line in lines:
                fields = [field.strip() for field in line.split("|")]
                if len(fields) >= 7 and fields[6] == "1":
                    item["write_address"] += 1
                elif len(fields) >= 7 and fields[6] == "0":
                    item["read_address"] += 1
        elif kind == "rdata":
            item["read_data"] += len(lines)
        else:
            item["write_data"] += len(lines)

    sem_events: dict[int, list[str]] = {}
    for name in evidence.names:
        match = _SEM_LOG_RE.search(name)
        if not match:
            continue
        slice_id = int(match.group("slice"))
        events = []
        for line in _data_lines(evidence.read_text(name)):
            fields = [field.strip() for field in line.split("|")]
            if len(fields) >= 2:
                events.append(fields[1])
        sem_events[slice_id] = events

    gexec_candidates = evidence.find_suffixes(
        ["gexec2slice/slice_all/gexec2slice.log"]
    )
    gexec_count = 0
    gexec_entry = None
    if gexec_candidates:
        gexec_entry = min(gexec_candidates, key=lambda value: (value.count("/"), value))
        gexec_count = len(_data_lines(evidence.read_text(gexec_entry)))

    observer_candidates = evidence.find_suffixes(
        ["return_observer/return_observer.log"]
    )
    observer_entry = (
        min(observer_candidates, key=lambda value: (value.count("/"), value))
        if observer_candidates
        else None
    )
    observer_text = evidence.read_text(observer_entry) if observer_entry else ""
    observer_stalls = [
        line
        for line in observer_text.splitlines()
        if "| STALL |" in line or "| DEADLOCK_SUSPECT |" in line
    ]
    observer_heartbeats = [
        line for line in observer_text.splitlines() if "| HEARTBEAT |" in line
    ]
    observer_internal_states = [
        line
        for line in observer_text.splitlines()
        if "| INTERNAL_STATE |" in line
    ]
    observer_data_lines = [
        line for line in observer_text.splitlines() if "|" in line
    ]
    return {
        "gexec_entry": gexec_entry,
        "gexec_handshake_count": gexec_count,
        "per_slice_mse": {
            str(slice_id): {
                str(mse): values for mse, values in sorted(mse_map.items())
            }
            for slice_id, mse_map in sorted(per_slice.items())
        },
        "sem_events": {
            str(slice_id): events for slice_id, events in sorted(sem_events.items())
        },
        "return_observer_entry": observer_entry,
        "return_observer_stalls": observer_stalls,
        "return_observer_heartbeat_count": len(observer_heartbeats),
        "return_observer_internal_state_count": len(observer_internal_states),
        "return_observer_last_internal_state": (
            observer_internal_states[-1] if observer_internal_states else None
        ),
        "return_observer_tail": observer_data_lines[-32:],
    }


def _aggregate_activity(auxiliary: Mapping[str, Any]) -> dict[str, int]:
    result = {
        "request": 0,
        "read_address": 0,
        "write_address": 0,
        "read_data": 0,
        "write_data": 0,
    }
    per_slice = auxiliary.get("per_slice_mse")
    if not isinstance(per_slice, Mapping):
        return result
    for raw_mse_map in per_slice.values():
        if not isinstance(raw_mse_map, Mapping):
            continue
        for raw in raw_mse_map.values():
            if not isinstance(raw, Mapping):
                continue
            for key in result:
                result[key] += int(raw.get(key, 0))
    return result


def _decode_128bit_text(payload: bytes, *, label: str) -> tuple[list[bytes], bytes]:
    lines = payload.splitlines()
    if not lines:
        raise NativeServerReturnError(f"128-bit readback is empty: {label}")
    for index, line in enumerate(lines, start=1):
        if len(line) != 128 or set(line) - {ord("0"), ord("1")}:
            raise NativeServerReturnError(
                f"invalid 128-bit readback line: {label}:{index}"
            )
    raw = b"".join(
        int(line, 2).to_bytes(16, byteorder="little") for line in lines
    )
    return lines, raw


def _golden_binary_path(workload: Path, relative_txt: str) -> Path:
    txt = workload / relative_txt
    binary = txt.with_suffix(".bin")
    if binary.is_file():
        return binary
    _, raw = _decode_128bit_text(txt.read_bytes(), label=str(txt))
    fallback = txt
    if not raw:
        raise NativeServerReturnError(f"golden payload is empty: {fallback}")
    return fallback


def _compare_readbacks(
    evidence: _Evidence, contract: Mapping[str, Any]
) -> dict[str, Any]:
    workload = contract["root"]
    matrices: list[dict[str, Any]] = []
    total_mismatch_bytes = 0
    missing_count = 0
    format_error_count = 0
    for entry in contract["d_entries"]:
        relative = str(entry["path"]).replace("\\", "/")
        candidates = evidence.find_suffixes([relative])
        if not candidates:
            shorter = "/".join(PurePosixPath(relative).parts[-3:])
            candidates = evidence.find_suffixes([shorter])
        if len(candidates) > 1:
            candidates = sorted(candidates, key=lambda value: (value.count("/"), value))
            if (
                len(candidates) > 1
                and candidates[0].count("/") == candidates[1].count("/")
            ):
                raise NativeServerReturnError(
                    f"ambiguous returned matrix path: {relative}: {candidates[:2]}"
                )
        returned_name = candidates[0] if candidates else None
        record: dict[str, Any] = {
            "key": entry["key"],
            "slice_id": entry.get("slice_id"),
            "path": relative,
            "expected_length_128bit": entry.get("length"),
            "returned_entry": returned_name,
        }
        if returned_name is None:
            record["status"] = "missing"
            missing_count += 1
            matrices.append(record)
            continue
        try:
            returned_lines, returned_raw = _decode_128bit_text(
                evidence.read_bytes(returned_name), label=returned_name
            )
        except NativeServerReturnError as error:
            record["status"] = "format_error"
            record["error"] = str(error)
            format_error_count += 1
            matrices.append(record)
            continue
        binary_path = _golden_binary_path(workload, relative)
        if binary_path.suffix == ".bin":
            golden_raw = binary_path.read_bytes()
        else:
            _, golden_raw = _decode_128bit_text(
                binary_path.read_bytes(), label=str(binary_path)
            )
        mismatch_offsets = [
            index
            for index, (actual, expected) in enumerate(zip(returned_raw, golden_raw))
            if actual != expected
        ]
        size_delta = abs(len(returned_raw) - len(golden_raw))
        mismatch_count = len(mismatch_offsets) + size_delta
        total_mismatch_bytes += mismatch_count
        expected_length = entry.get("length")
        length_ok = (
            expected_length is None or len(returned_lines) == int(expected_length)
        )
        if not length_ok:
            format_error_count += 1
        record.update(
            {
                "status": (
                    "passed"
                    if mismatch_count == 0 and length_ok
                    else "length_error"
                    if not length_ok
                    else "mismatch"
                ),
                "returned_line_count_128bit": len(returned_lines),
                "returned_sha256": hashlib.sha256(
                    evidence.read_bytes(returned_name)
                ).hexdigest(),
                "golden_binary_path": binary_path.relative_to(workload).as_posix(),
                "golden_binary_sha256": sha256_file(binary_path),
                "mismatch_byte_count": mismatch_count,
                "first_mismatch_byte_offset": (
                    mismatch_offsets[0]
                    if mismatch_offsets
                    else min(len(returned_raw), len(golden_raw))
                    if size_delta
                    else None
                ),
            }
        )
        matrices.append(record)
    passed_count = sum(item.get("status") == "passed" for item in matrices)
    return {
        "expected_matrix_count": len(contract["d_entries"]),
        "returned_matrix_count": len(contract["d_entries"]) - missing_count,
        "passed_matrix_count": passed_count,
        "missing_matrix_count": missing_count,
        "format_error_count": format_error_count,
        "total_mismatch_byte_count": total_mismatch_bytes,
        "matrices": matrices,
    }


def _issue(
    code: str, checkpoint: str, message: str, *, severity: str = "error"
) -> dict[str, str]:
    return {
        "code": code,
        "severity": severity,
        "checkpoint": checkpoint,
        "message": message,
    }


def _classify(
    runtime: Mapping[str, Any],
    auxiliary: Mapping[str, Any],
    numeric: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> tuple[str, str, list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    errors = runtime["errors"]
    sca = runtime.get("using_sca_cfg")
    sca_d = runtime.get("using_sca_cfg_D")
    plusargs = runtime.get("command_plusargs", {})
    if not sca:
        issues.append(
            _issue("SCA_BINDING_NOT_ECHOED", "sca_binding", "main SCA binding was not echoed")
        )
    if not sca_d:
        issues.append(
            _issue("SCA_D_BINDING_NOT_ECHOED", "sca_binding", "D SCA binding was not echoed")
        )
    if "SCA_CFG" not in plusargs:
        issues.append(
            _issue(
                "SCA_PLUSARG_MISSING",
                "invocation",
                "server command did not explicitly pass +SCA_CFG",
            )
        )
    if "SCA_CFG_D" not in plusargs:
        issues.append(
            _issue(
                "SCA_D_PLUSARG_MISSING",
                "invocation",
                "server command did not explicitly pass +SCA_CFG_D",
            )
        )
    if sca and plusargs.get("SCA_CFG") != sca:
        issues.append(
            _issue(
                "SCA_COMMAND_ECHO_MISMATCH",
                "sca_binding",
                "+SCA_CFG differs from the testbench SCA echo",
            )
        )
    if sca_d and plusargs.get("SCA_CFG_D") != sca_d:
        issues.append(
            _issue(
                "SCA_D_COMMAND_ECHO_MISMATCH",
                "sca_binding",
                "+SCA_CFG_D differs from the testbench SCA_D echo",
            )
        )
    if sca and sca_d:
        sca_parent = PurePosixPath(sca.replace("\\", "/")).parent
        sca_d_parent = PurePosixPath(sca_d.replace("\\", "/")).parent
        if sca_parent != sca_d_parent:
            issues.append(
                _issue(
                    "SCA_PACKAGE_DIRECTORY_MISMATCH",
                    "sca_binding",
                    "main and D SCA files were loaded from different directories",
                )
            )
    if errors.get("softmax_fallback", 0):
        issues.append(
            _issue(
                "SCA_D_SOFTMAX_FALLBACK",
                "sca_binding",
                "testbench selected sca_cfg_D_softmax.json",
            )
        )
    if errors.get("cannot_open", 0):
        issues.append(
            _issue(
                "SERVER_FILE_OPEN_FAILED",
                "preload",
                "server log contains Cannot open",
            )
        )
    if errors.get("fatal", 0):
        issues.append(
            _issue(
                "SERVER_FATAL",
                "invocation",
                "server log contains a fatal simulator error",
            )
        )
    if runtime.get("preload_object_count") != contract["preload_object_count"]:
        issues.append(
            _issue(
                "PRELOAD_COUNT_MISMATCH",
                "preload",
                f"expected {contract['preload_object_count']} loaded objects, "
                f"observed {runtime.get('preload_object_count')}",
            )
        )
    if runtime.get("exec_length") != contract["exec_length"]:
        issues.append(
            _issue(
                "EXEC_LENGTH_MISMATCH",
                "execplan",
                f"expected Exec_Length {contract['exec_length']}, "
                f"observed {runtime.get('exec_length')}",
            )
        )

    activity = _aggregate_activity(auxiliary)
    gexec_count = int(auxiliary.get("gexec_handshake_count", 0))
    started = int(runtime.get("slice_start_count", 0)) > 0
    completed = bool(runtime.get("completion_cycles"))
    global_complete = bool(runtime.get("simulation_success_marker"))
    readback_count = runtime.get("readback_matrix_count")
    if started and activity["read_address"] > 0 and activity["read_data"] == 0:
        issues.append(
            _issue(
                "READ_REQUEST_WITHOUT_RETURN",
                "read_return",
                "memory read requests were observed but no read data returned",
            )
        )
    if (
        started
        and activity["write_address"] > 0
        and activity["write_data"] == 0
        and not completed
    ):
        issues.append(
            _issue(
                "WRITE_ADDRESS_WITHOUT_WRITE_DATA",
                "write_data",
                "write addresses were issued but no write-data handshake was observed",
            )
        )
    if auxiliary.get("return_observer_stalls"):
        issues.append(
            _issue(
                "RETURN_OBSERVER_STALL",
                "write_data",
                "the optional return observer reported a sustained internal stall",
            )
        )
    if errors.get("external_termination", 0) and not global_complete:
        issues.append(
            _issue(
                "EXTERNAL_TERMINATION",
                "global_complete",
                "simulation was externally terminated before natural completion",
            )
        )
    if errors.get("readback_skipped", 0):
        issues.append(
            _issue(
                "READBACK_SKIPPED",
                "readback",
                "testbench skipped matrix readback",
            )
        )
    if readback_count != contract["readback_matrix_count"]:
        issues.append(
            _issue(
                "READBACK_COUNT_MISMATCH",
                "readback",
                f"expected {contract['readback_matrix_count']} dumped matrices, "
                f"observed {readback_count}",
            )
        )
    if numeric["missing_matrix_count"]:
        issues.append(
            _issue(
                "RETURNED_MATRIX_MISSING",
                "numeric_compare",
                f"{numeric['missing_matrix_count']} returned D matrices are missing",
                severity="warning" if global_complete else "error",
            )
        )
    if numeric["format_error_count"]:
        issues.append(
            _issue(
                "RETURNED_MATRIX_FORMAT_ERROR",
                "numeric_compare",
                f"{numeric['format_error_count']} returned D matrices have invalid format/length",
            )
        )
    if numeric["total_mismatch_byte_count"]:
        issues.append(
            _issue(
                "NUMERIC_MISMATCH",
                "numeric_compare",
                f"{numeric['total_mismatch_byte_count']} returned bytes differ from Golden",
            )
        )

    binding_fatal = any(
        item["code"]
        in {
            "SCA_BINDING_NOT_ECHOED",
            "SCA_D_BINDING_NOT_ECHOED",
            "SCA_PLUSARG_MISSING",
            "SCA_D_PLUSARG_MISSING",
            "SCA_COMMAND_ECHO_MISMATCH",
            "SCA_D_COMMAND_ECHO_MISMATCH",
            "SCA_PACKAGE_DIRECTORY_MISMATCH",
            "SCA_D_SOFTMAX_FALLBACK",
            "SERVER_FILE_OPEN_FAILED",
            "SERVER_FATAL",
            "PRELOAD_COUNT_MISMATCH",
            "EXEC_LENGTH_MISMATCH",
        }
        for item in issues
    )
    numeric_pass = (
        numeric["returned_matrix_count"] == numeric["expected_matrix_count"]
        and numeric["passed_matrix_count"] == numeric["expected_matrix_count"]
        and numeric["format_error_count"] == 0
        and numeric["total_mismatch_byte_count"] == 0
    )
    runtime_pass = (
        not binding_fatal
        and not auxiliary.get("return_observer_stalls")
        and completed
        and global_complete
        and readback_count == contract["readback_matrix_count"]
        and not errors.get("readback_skipped", 0)
    )
    if runtime_pass and numeric_pass:
        return "passed", "numeric_readback_pass_e4_candidate", issues
    if runtime_pass and numeric["missing_matrix_count"] == numeric["expected_matrix_count"]:
        return "incomplete", "runtime_and_readback_logged_return_payload_missing", issues
    if any(item["code"] == "NUMERIC_MISMATCH" for item in issues):
        return "failed", "numeric_mismatch", issues
    if binding_fatal:
        return "failed", "setup_or_binding_failure", issues
    if auxiliary.get("return_observer_stalls"):
        return "stalled", "internal_pipeline_stall_observed", issues
    if any(item["code"] == "WRITE_ADDRESS_WITHOUT_WRITE_DATA" for item in issues):
        return "stalled", "write_address_without_write_data", issues
    if any(item["code"] == "READ_REQUEST_WITHOUT_RETURN" for item in issues):
        return "stalled", "read_request_without_return", issues
    if started and not completed:
        return "stalled", "compute_started_not_completed", issues
    if gexec_count > 0 and not started:
        return "stalled", "dispatch_observed_slice_not_started", issues
    return "incomplete", "insufficient_return_evidence", issues


def _checkpoint_report(
    runtime: Mapping[str, Any],
    auxiliary: Mapping[str, Any],
    numeric: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    activity = _aggregate_activity(auxiliary)
    direct = {
        "invocation": bool(runtime.get("command")),
        "sca_binding": bool(
            runtime.get("using_sca_cfg") and runtime.get("using_sca_cfg_D")
        ),
        "preload": runtime.get("preload_object_count")
        == contract["preload_object_count"],
        "execplan": runtime.get("exec_length") == contract["exec_length"],
        "dispatch": int(auxiliary.get("gexec_handshake_count", 0)) > 0,
        "slice_start": int(runtime.get("slice_start_count", 0)) > 0,
        "read_request": activity["read_address"] > 0,
        "read_return": activity["read_data"] > 0,
        "compute_finish": bool(runtime.get("completion_cycles")),
        "write_address": activity["write_address"] > 0,
        "write_data": activity["write_data"] > 0,
        "global_complete": bool(runtime.get("simulation_success_marker")),
        "readback": runtime.get("readback_matrix_count")
        == contract["readback_matrix_count"],
        "numeric_compare": numeric["passed_matrix_count"]
        == numeric["expected_matrix_count"],
    }
    strongest_index = max(
        (index for index, name in enumerate(CHECKPOINTS) if direct[name]),
        default=-1,
    )
    return {
        "furthest_direct_checkpoint": (
            CHECKPOINTS[strongest_index] if strongest_index >= 0 else None
        ),
        "checkpoints": [
            {"name": name, "directly_observed": direct[name]} for name in CHECKPOINTS
        ],
        "aggregate_memory_activity": activity,
    }


def analyze_native_server_return(
    return_path: Path,
    workload_root: Path,
    *,
    profile_path: Path | None = None,
    run_id: str = "run1",
) -> dict[str, Any]:
    if run_id not in {"run1", "run2", "diagnostic"}:
        raise NativeServerReturnError("run_id must be run1, run2, or diagnostic")
    evidence = _Evidence(return_path)
    contract = _workload_contract(workload_root)
    profile = _validate_profile(profile_path, contract)
    sim_entry = evidence.select_sim_log()
    sim_bytes = evidence.read_bytes(sim_entry)
    sim_text = sim_bytes.decode("utf-8", errors="replace")
    runtime = _parse_sim_log(sim_text)
    auxiliary = _parse_auxiliary_logs(evidence)
    numeric = _compare_readbacks(evidence, contract)
    status, classification, issues = _classify(
        runtime, auxiliary, numeric, contract
    )
    checkpoints = _checkpoint_report(runtime, auxiliary, numeric, contract)
    profile_expected = profile.get("expected", {})
    profile_diagnostics = profile.get("diagnostics", {})
    return {
        "schema": REPORT_SCHEMA,
        "status": status,
        "classification": classification,
        "claim_boundary": (
            "numeric_readback_pass is an E4 candidate only; formal E4 additionally "
            "requires the approved server/RTL environment receipt"
        ),
        "run_id": run_id,
        "profile": {
            "profile_id": profile.get("profile_id"),
            "path": str(profile_path.resolve()) if profile_path else None,
            "expected": profile_expected,
            "diagnostics": profile_diagnostics,
        },
        "inputs": {
            "return_path": str(evidence.path),
            "return_kind": evidence.kind,
            "return_sha256": evidence.sha256(),
            "return_entry_count": len(evidence.names),
            "sim_log_entry": sim_entry,
            "sim_log_sha256": hashlib.sha256(sim_bytes).hexdigest(),
            "workload_root": str(contract["root"]),
            "sca_cfg_sha256": sha256_file(contract["sca_path"]),
            "sca_cfg_D_sha256": sha256_file(contract["sca_d_path"]),
            "workload_manifest": (
                contract["manifest_path"].name
                if isinstance(contract.get("manifest_path"), Path)
                else None
            ),
            "workload_manifest_sha256": (
                sha256_file(contract["manifest_path"])
                if isinstance(contract.get("manifest_path"), Path)
                else None
            ),
            "workload_tree_sha256": contract["workload_tree_sha256"],
        },
        "workload_expectation": {
            "exec_length": contract["exec_length"],
            "preload_object_count": contract["preload_object_count"],
            "readback_matrix_count": contract["readback_matrix_count"],
            "active_slices": contract["active_slices"],
        },
        "runtime": runtime,
        "auxiliary": auxiliary,
        "checkpoint_analysis": checkpoints,
        "numeric": numeric,
        "issues": issues,
    }


__all__ = [
    "NativeServerReturnError",
    "analyze_native_server_return",
]
