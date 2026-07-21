from __future__ import annotations

import hashlib
import json
import re
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping


class HardwareServerTraceError(RuntimeError):
    """A server trace archive cannot support a trustworthy comparison."""


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise HardwareServerTraceError(f"JSON root is not an object: {path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize_hex128(value: str) -> str:
    text = value.strip().lower().removeprefix("0x")
    if not text or len(text) > 32 or set(text) - set("0123456789abcdef"):
        raise HardwareServerTraceError(f"invalid 128-bit hex value: {value!r}")
    return text.zfill(32)


def _normalize_trace_hex128(value: str) -> str:
    text = value.strip().lower().removeprefix("0x")
    if not text or len(text) > 32 or set(text) - set("0123456789abcdefxz"):
        raise HardwareServerTraceError(f"invalid trace 128-bit value: {value!r}")
    return text.zfill(32)


def _zip_text(
    archive: zipfile.ZipFile,
    name: str,
    *,
    required: bool = True,
    archive_prefix: str = "",
) -> str:
    archive_name = f"{archive_prefix}{name}"
    try:
        with archive.open(archive_name) as stream:
            return stream.read().decode("utf-8", errors="replace")
    except KeyError:
        if required:
            raise HardwareServerTraceError(
                f"trace archive entry is missing: {archive_name}"
            )
        return ""


_POST_RUN_BANK_RE = re.compile(
    r"(?:^|/)slice(?P<slice>\d{2})_Bank(?P<bank>\d{2})_data\.(?P<format>bin|txt)$"
)


def _inspect_post_run_bank_dump(
    archive: zipfile.ZipFile,
    archive_name: str,
    logical_name: str,
) -> dict[str, Any]:
    """Return structural facts about one full-bank dump without claiming numeric validity."""
    match = _POST_RUN_BANK_RE.search(logical_name)
    if match is None:  # pragma: no cover - caller filters with the same expression
        raise HardwareServerTraceError(f"invalid post-run bank dump name: {logical_name}")
    dump_format = match.group("format")
    info = archive.getinfo(archive_name)
    format_valid = True
    invalid_line_count = 0
    represented_bytes = info.file_size
    line_count: int | None = None
    if dump_format == "txt":
        line_count = 0
        represented_bytes = 0
        with archive.open(info) as stream:
            for raw_line in stream:
                bits = raw_line.strip()
                if len(bits) != 32 or set(bits) - {ord("0"), ord("1")}:
                    invalid_line_count += 1
                    format_valid = False
                    continue
                line_count += 1
                represented_bytes += 4
    return {
        "path": logical_name,
        "slice_id": int(match.group("slice")),
        "bank_id": int(match.group("bank")),
        "format": dump_format,
        "archive_size_bytes": info.file_size,
        "represented_bytes": represented_bytes,
        "line_count": line_count,
        "format_valid": format_valid,
        "invalid_line_count": invalid_line_count,
    }


def _parse_exit_status_text(text: str) -> int | None:
    stripped = text.strip()
    if not re.fullmatch(r"[+-]?\d+", stripped):
        return None
    return int(stripped)


def _detect_archive_prefix(entry_names: Iterable[str]) -> str:
    """Locate a rooted or once-wrapped return, including pre-runtime aborts.

    ``gexec2slice.log`` does not exist when the simulator stalls during SCA
    preload.  Prefix detection must therefore use files that the runner can
    archive before runtime starts as well as the normal runtime trace.
    """

    anchors = (
        "sim_results/gexec2slice/slice_all/gexec2slice.log",
        "sim_results/local_summary/slice_all/local_summary.log",
        "run_metadata.json",
        "config/sca_cfg.json",
    )
    names = set(entry_names)
    prefixes: set[str] = set()
    for anchor in anchors:
        if anchor in names:
            prefixes.add("")
        prefixes.update(
            name[: -len(anchor)]
            for name in names
            if name.endswith(anchor) and name != anchor
        )
    for name in names:
        marker = "run_sim_results/"
        if name.startswith(marker):
            prefixes.add("")
        elif marker in name:
            prefixes.add(name[: name.index(marker)])
    if len(prefixes) != 1:
        raise HardwareServerTraceError(
            "could not determine a unique archive prefix from pre-runtime/runtime "
            f"anchors; candidates={sorted(prefixes)}"
        )
    return next(iter(prefixes))


def _frame_events(lines: Iterable[str]) -> Iterable[tuple[int, int, str, str]]:
    """Yield time, local 128-bit line address, R/W marker, and data hex."""
    for line in lines:
        parts = [part.strip() for part in line.split("|")]
        if len(parts) != 9 or not parts[0].isdigit() or parts[4] not in {"0(R)", "1(W)"}:
            continue
        try:
            yield (
                int(parts[0]),
                int(parts[8], 16),
                parts[4][0],
                _normalize_trace_hex128(parts[7]),
            )
        except ValueError as exc:
            raise HardwareServerTraceError(f"invalid bank-frame line: {line}") from exc


def _mc_read_events(lines: Iterable[str]) -> Iterable[tuple[int, str]]:
    for line in lines:
        parts = [part.strip() for part in line.split("|")]
        if len(parts) != 7 or not parts[0].isdigit() or parts[4] != "0(R)":
            continue
        try:
            yield int(parts[0]), _normalize_trace_hex128(parts[6])
        except ValueError as exc:
            raise HardwareServerTraceError(f"invalid MC read-data line: {line}") from exc


def _slice_start_time(text: str) -> int | None:
    match = re.search(r"\[(\d+)\]\s+INFO:\s+slice start", text)
    return int(match.group(1)) if match is not None else None


def _local_request_events(text: str) -> list[dict[str, int]]:
    events: list[dict[str, int]] = []
    for line in text.splitlines():
        parts = [part.strip() for part in line.split("|")]
        if len(parts) != 8 or not parts[0].isdigit():
            continue
        events.append(
            {
                "time_ns": int(parts[0]),
                "channel": int(parts[1]),
                "local_line": int(parts[2], 16),
                "rw": int(parts[6]),
            }
        )
    return events


def _local_read_events(text: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in text.splitlines():
        parts = [part.strip() for part in line.split("|")]
        if len(parts) != 5 or not parts[0].isdigit():
            continue
        value = _normalize_trace_hex128(parts[4])
        events.append(
            {
                "return_time_ns": int(parts[0]),
                "return_channel": int(parts[1]),
                "issue_channel": int(parts[2]),
                "issue_time_ns": int(parts[3]),
                "value_128bit": "0x" + value.upper(),
                "contains_unknown": bool(set(value) & {"x", "z"}),
            }
        )
    return events


def _local_write_data_count(text: str) -> int:
    return sum(
        1
        for line in text.splitlines()
        if len(line.split("|")) == 3 and line.split("|", 1)[0].strip().isdigit()
    )


def _gexec_events(text: str) -> list[dict[str, int]]:
    events: list[dict[str, int]] = []
    for line in text.splitlines():
        parts = [part.strip() for part in line.split("|")]
        if len(parts) != 3 or not parts[0].isdigit():
            continue
        value = int(parts[2], 16)
        events.append(
            {
                "time_ns": int(parts[0]),
                "slice_id": int(parts[1]),
                "value": value,
                "opcode": value & 7,
            }
        )
    return events


def _bank_data_word(
    package: Path,
    slice_id: int,
    bank_id: int,
    local_line: int,
) -> str | None:
    path = package / "Bank_data" / f"slice{slice_id:02d}_Bank{bank_id:02d}_data.txt"
    if not path.is_file():
        return None
    first_u32 = local_line * 4
    words: list[str] = []
    with path.open("r", encoding="ascii") as stream:
        for index, raw in enumerate(stream):
            if index < first_u32:
                continue
            if index >= first_u32 + 4:
                break
            bits = raw.strip()
            if len(bits) != 32 or set(bits) - {"0", "1"}:
                raise HardwareServerTraceError(
                    f"invalid 32-bit Bank_data line at {path}:{index + 1}"
                )
            words.append(bits)
    if len(words) != 4:
        return None
    return "0x" + "".join(f"{int(bits, 2):08X}" for bits in reversed(words))


def _find_full_operator(preflight: Mapping[str, Any]) -> Mapping[str, Any]:
    ndp = preflight.get("ndp_target_config_comparison")
    if not isinstance(ndp, Mapping):
        raise HardwareServerTraceError("preflight NDP comparison is missing")
    ordered = ndp.get("ordered_comparisons")
    if not isinstance(ordered, list):
        raise HardwareServerTraceError("preflight ordered NDP comparisons are missing")
    for item in ordered:
        if isinstance(item, Mapping) and item.get("name") == "full_operator":
            return item
    raise HardwareServerTraceError("preflight full_operator comparison is missing")


def _ndp_side(full_operator: Mapping[str, Any]) -> dict[str, Any]:
    tensors: dict[str, Any] = {}
    passed = True
    for name in ("P", "D"):
        raw = full_operator.get(name)
        if not isinstance(raw, Mapping):
            raise HardwareServerTraceError(f"preflight full_operator {name} is missing")
        mismatch_count = int(raw.get("mismatch_count", -1))
        actual_sha = str(raw.get("actual_sha256", ""))
        golden_sha = str(raw.get("golden_sha256", ""))
        tensor_passed = mismatch_count == 0 and bool(actual_sha) and actual_sha == golden_sha
        passed = passed and tensor_passed
        tensors[name] = {
            "status": "passed" if tensor_passed else "failed",
            "dtype": raw.get("dtype"),
            "element_count": int(raw.get("element_count", 0)),
            "mismatch_count": mismatch_count,
            "actual_sha256": actual_sha,
            "golden_sha256": golden_sha,
            "first_mismatch": raw.get("first_mismatch"),
        }
    return {"status": "passed" if passed else "failed", "tensors": tensors}


def analyze_hardware_server_trace_zip(
    archive_path: Path,
    package_root: Path,
    preflight_path: Path,
) -> tuple[dict[str, Any], dict[str, str]]:
    archive_file = archive_path.resolve()
    package = package_root.resolve()
    preflight_file = preflight_path.resolve()
    runner = _read_json(package / "runner_contract.json")
    dump_contract = _read_json(package / "dump_contract.json")
    package_manifest = _read_json(package / "manifest.json")
    preflight = _read_json(preflight_file)
    ndp_comparison = _ndp_side(_find_full_operator(preflight))

    preload = runner.get("preload")
    execution = runner.get("execution")
    if not isinstance(preload, Mapping) or not isinstance(execution, Mapping):
        raise HardwareServerTraceError("runner preload/execution contract is missing")
    readback_gate = preload.get("readback_gate")
    completion_gate = execution.get("completion_gate")
    if not isinstance(readback_gate, Mapping) or not isinstance(completion_gate, Mapping):
        raise HardwareServerTraceError("runner readback/completion gate is missing")
    raw_probes = readback_gate.get("probes")
    if not isinstance(raw_probes, list) or not raw_probes:
        raise HardwareServerTraceError("runner readback probes are missing")

    probes: list[dict[str, Any]] = []
    probe_by_location: dict[tuple[int, int, int], list[int]] = defaultdict(list)
    for index, raw in enumerate(raw_probes):
        if not isinstance(raw, Mapping):
            raise HardwareServerTraceError(f"readback probe {index} is invalid")
        address = int(str(raw["base_addr"]).replace("_", ""), 16)
        slice_id = (address >> 25) & 0x1F
        bank_id = (address >> 23) & 0x03
        local_line = (address & ((1 << 23) - 1)) // 16
        probe = {
            "index": index,
            "kind": raw.get("kind"),
            "port": raw.get("port"),
            "base_addr": f"0x{address:08X}",
            "slice_id": slice_id,
            "bank_id": bank_id,
            "local_line_addr": f"0x{local_line:06X}",
            "expected_128bit": "0x" + _normalize_hex128(str(raw["expected_128bit"])).upper(),
            "source_path": raw.get("source_path"),
            "last_preload_write_time_ns": None,
            "last_preload_write_128bit": None,
            "preload_write_status": "missing",
            "matching_mc_read_time_ns": None,
            "mc_read_value_status": "not_observed",
        }
        probes.append(probe)
        probe_by_location[(slice_id, bank_id, local_line)].append(index)

    region_by_bank: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    for group in ("P", "staged_D"):
        raw_entries = dump_contract.get(group)
        if not isinstance(raw_entries, list):
            raise HardwareServerTraceError(f"dump contract {group} entries are missing")
        for raw in raw_entries:
            if not isinstance(raw, Mapping):
                raise HardwareServerTraceError(f"dump contract {group} entry is invalid")
            address = int(str(raw["base_addr"]).replace("_", ""), 16)
            slice_id = int(raw["slice_id"])
            bank_id = (address >> 23) & 0x03
            local_offset = address & ((1 << 23) - 1)
            start_line = local_offset // 16
            end_line = (local_offset + int(raw["size_bytes"]) + 15) // 16
            name = group if group == "P" else f"staged_D_{int(raw['local_half'])}"
            region_by_bank[(slice_id, bank_id)].append(
                {
                    "name": name,
                    "slice_id": slice_id,
                    "bank_id": bank_id,
                    "base_addr": f"0x{address:08X}",
                    "start_line": start_line,
                    "end_line": end_line,
                    "size_bytes": int(raw["size_bytes"]),
                    "read_transactions": 0,
                    "write_transactions": 0,
                    "pre_runtime_read_transactions": 0,
                    "pre_runtime_write_transactions": 0,
                    "runtime_read_transactions": 0,
                    "runtime_write_transactions": 0,
                }
            )

    terminal_text = ""
    gexec_text = ""
    direct_dump_entries: list[str] = []
    direct_dump_records: list[dict[str, Any]] = []
    return_metadata: dict[str, Any] | None = None
    return_metadata_entry: str | None = None
    return_metadata_error: str | None = None
    terminal_entry: str | None = None
    terminal_selection_error: str | None = None
    exit_status: int | None = None
    exit_status_entry: str | None = None
    exit_status_error: str | None = None
    archive_namespaces: set[str] = set()
    frame_file_count = 0
    mc_file_count = 0
    with zipfile.ZipFile(archive_file) as archive:
        entry_names = [entry.filename for entry in archive.infolist() if not entry.is_dir()]
        archive_prefix = _detect_archive_prefix(entry_names)
        logical_entries = [
            (name, name[len(archive_prefix) :])
            for name in entry_names
            if name.startswith(archive_prefix)
        ]
        logical_entry_names = [logical_name for _archive_name, logical_name in logical_entries]
        terminal_candidates: list[str] = []
        if "terminal_output.txt" in logical_entry_names:
            terminal_candidates = ["terminal_output.txt"]
        else:
            console_candidates = sorted(
                name
                for name in logical_entry_names
                if re.fullmatch(r"run_sim_results/[^/]+_console\.log", name)
            )
            if len(console_candidates) == 1:
                terminal_candidates = console_candidates
            elif len(console_candidates) > 1:
                terminal_selection_error = (
                    "multiple console logs are ambiguous: "
                    + ", ".join(console_candidates)
                )
            elif "run_sim_results/sim.log" in logical_entry_names:
                terminal_candidates = ["run_sim_results/sim.log"]
        for terminal_name in terminal_candidates:
            terminal_text = _zip_text(
                archive,
                terminal_name,
                required=False,
                archive_prefix=archive_prefix,
            )
            if terminal_text:
                terminal_entry = terminal_name
                break
        gexec_name = "sim_results/gexec2slice/slice_all/gexec2slice.log"
        gexec_text = _zip_text(
            archive,
            gexec_name,
            required=False,
            archive_prefix=archive_prefix,
        )
        gexec_rows = _gexec_events(gexec_text)
        start_rows = [row for row in gexec_rows if row["opcode"] == 5]
        start_times = sorted({row["time_ns"] for row in start_rows})
        first_runtime_time = start_times[0] if start_times else None
        for archive_name, name in logical_entries:
            parts = name.split("/")
            if parts and parts[0] == "sim_results" and len(parts) > 1:
                archive_namespaces.add(parts[1])
            if _POST_RUN_BANK_RE.search(name):
                direct_dump_entries.append(name)
                direct_dump_records.append(
                    _inspect_post_run_bank_dump(archive, archive_name, name)
                )

        metadata_candidates = [
            name
            for name in logical_entry_names
            if name.rsplit("/", 1)[-1]
            in {"return_metadata.json", "run_metadata.json", "run_report.json"}
        ]
        if len(metadata_candidates) == 1:
            return_metadata_entry = metadata_candidates[0]
            try:
                parsed = json.loads(
                    _zip_text(
                        archive,
                        return_metadata_entry,
                        archive_prefix=archive_prefix,
                    )
                )
                if not isinstance(parsed, dict):
                    return_metadata_error = "return metadata JSON root is not an object"
                else:
                    return_metadata = parsed
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                return_metadata_error = f"invalid return metadata JSON: {exc}"
        elif len(metadata_candidates) > 1:
            return_metadata_error = (
                "multiple return metadata files are ambiguous: "
                + ", ".join(sorted(metadata_candidates))
            )

        exit_status_candidates = [
            name
            for name in logical_entry_names
            if re.search(r"(?:^|/)(?:[^/]+_)?exit_status\.txt$", name)
        ]
        parsed_exit_statuses: list[tuple[str, int]] = []
        for candidate in exit_status_candidates:
            parsed_status = _parse_exit_status_text(
                _zip_text(archive, candidate, archive_prefix=archive_prefix)
            )
            if parsed_status is None:
                exit_status_error = f"invalid simulator exit status file: {candidate}"
            else:
                parsed_exit_statuses.append((candidate, parsed_status))
        distinct_exit_statuses = {status for _name, status in parsed_exit_statuses}
        if len(distinct_exit_statuses) == 1:
            exit_status = next(iter(distinct_exit_statuses))
            exit_status_entry = ", ".join(name for name, _status in parsed_exit_statuses)
        elif len(distinct_exit_statuses) > 1:
            exit_status_error = "conflicting simulator exit status files"

        keys = sorted(set(probe_by_location) | set(region_by_bank))
        bank_keys = sorted({(key[0], key[1]) for key in keys})
        for slice_id, bank_id in bank_keys:
            frame_name = f"sim_results/bank_frame/slice{slice_id}/bank{bank_id}_frame.log"
            frame_text = _zip_text(
                archive,
                frame_name,
                required=False,
                archive_prefix=archive_prefix,
            )
            frame_file_count += bool(frame_text)
            for time_ns, local_line, rw, data_hex in _frame_events(frame_text.splitlines()):
                for probe_index in probe_by_location.get((slice_id, bank_id, local_line), []):
                    if rw == "1" and (
                        first_runtime_time is None or time_ns < first_runtime_time
                    ):
                        probe = probes[probe_index]
                        probe["last_preload_write_time_ns"] = time_ns
                        probe["last_preload_write_128bit"] = "0x" + data_hex.upper()
                for region in region_by_bank.get((slice_id, bank_id), []):
                    if region["start_line"] <= local_line < region["end_line"]:
                        key = "write_transactions" if rw == "1" else "read_transactions"
                        region[key] += 1
                        phase = (
                            "runtime"
                            if first_runtime_time is not None and time_ns >= first_runtime_time
                            else "pre_runtime"
                        )
                        region[f"{phase}_{key}"] += 1

            mc_name = f"sim_results/bank_frame/slice{slice_id}/bank{bank_id}_mc_rdata.log"
            mc_text = _zip_text(
                archive,
                mc_name,
                required=False,
                archive_prefix=archive_prefix,
            )
            mc_file_count += bool(mc_text)
            mc_events = list(_mc_read_events(mc_text.splitlines()))
            for probe_index in {
                index
                for (probe_slice, probe_bank, _line), indexes in probe_by_location.items()
                if probe_slice == slice_id and probe_bank == bank_id
                for index in indexes
            }:
                probe = probes[probe_index]
                expected = _normalize_hex128(str(probe["expected_128bit"]))
                write_time = probe["last_preload_write_time_ns"]
                times = [
                    time_ns
                    for time_ns, data_hex in mc_events
                    if data_hex == expected and (write_time is None or time_ns >= write_time)
                ]
                if times:
                    probe["matching_mc_read_time_ns"] = min(times)
                    probe["mc_read_value_status"] = "observed_after_preload_write"

        for probe in probes:
            expected = _normalize_hex128(str(probe["expected_128bit"]))
            observed = probe["last_preload_write_128bit"]
            if observed is not None and _normalize_hex128(str(observed)) == expected:
                probe["preload_write_status"] = "passed"
            elif observed is not None:
                probe["preload_write_status"] = "failed"

    expected_stage_count = int(completion_gate.get("expected_runtime_stage_count", 0))
    expected_start_count = int(completion_gate.get("expected_start_comp_count", 0))
    actual_stage_count = len(start_times)

    sca_payload_count: int | None = None
    sca_payload_count_source: str | None = None
    sca_payload_contract_error: str | None = None
    sca_path = package / "sca_cfg.json"
    if sca_path.is_file():
        sca = _read_json(sca_path)
        top_level_payload_count = sum(
            isinstance(value, Mapping)
            and isinstance(value.get("base_addr"), str)
            and isinstance(value.get("path"), str)
            for value in sca.values()
        )
        parser_abi = preload.get("sca_cfg", {})
        parser_abi = (
            parser_abi.get("immutable_tb_parser_abi", {})
            if isinstance(parser_abi, Mapping)
            else {}
        )
        raw_validated_transfer_count = (
            parser_abi.get("validated_transfer_count")
            if isinstance(parser_abi, Mapping)
            else None
        )
        if raw_validated_transfer_count is None:
            sca_payload_count = top_level_payload_count
            sca_payload_count_source = "legacy_top_level_sca_entries"
        else:
            try:
                validated_transfer_count = int(raw_validated_transfer_count)
            except (TypeError, ValueError):
                sca_payload_contract_error = (
                    "immutable-TB parser ABI validated_transfer_count is not an integer"
                )
            else:
                if (
                    isinstance(raw_validated_transfer_count, bool)
                    or validated_transfer_count <= 0
                ):
                    sca_payload_contract_error = (
                        "immutable-TB parser ABI validated_transfer_count must be positive"
                    )
                else:
                    sca_payload_count = validated_transfer_count
                    sca_payload_count_source = "immutable_tb_parser_abi"
    loaded_matrix_match = re.search(r"JSON config:\s*(\d+)\s+matrices loaded", terminal_text)
    loaded_matrix_count = (
        int(loaded_matrix_match.group(1)) if loaded_matrix_match is not None else None
    )
    loading_matrix_indexes = [
        int(match)
        for match in re.findall(r"JSON:\s*Loading matrix\[(\d+)\]", terminal_text)
    ]
    started_matrix_count = max(loading_matrix_indexes) + 1 if loading_matrix_indexes else 0

    local_runtime: dict[str, Any] = {
        "status": "not_observed",
        "namespace": None,
        "slice_start_time_ns": None,
        "start_comp_to_slice_start_ns": None,
        "slice_count": 0,
        "completed_slice_count": 0,
        "slices_with_unknown_output_reads": 0,
        "output_read_return_count": 0,
        "unknown_output_read_return_count": 0,
        "output_write_request_count": 0,
        "output_write_data_handshake_count": 0,
        "slices": [],
    }
    if start_times:
        first_start = start_times[0]
        with zipfile.ZipFile(archive_file) as archive:
            candidates: list[tuple[int, str, int]] = []
            for namespace in sorted(archive_namespaces):
                name = f"sim_results/{namespace}/slice0/local_mse4_req.log"
                text = _zip_text(
                    archive,
                    name,
                    required=False,
                    archive_prefix=archive_prefix,
                )
                start_time = _slice_start_time(text)
                if start_time is not None and start_time >= first_start:
                    candidates.append((start_time - first_start, namespace, start_time))
            if candidates:
                delta, namespace, slice_start = min(candidates)
                local_runtime.update(
                    {
                        "namespace": namespace,
                        "slice_start_time_ns": slice_start,
                        "start_comp_to_slice_start_ns": delta,
                    }
                )
                slice_reports: list[dict[str, Any]] = []
                for slice_id in range(int(dump_contract.get("slice_count", 0)) or 28):
                    prefix = f"sim_results/{namespace}/slice{slice_id}"
                    request_text = _zip_text(
                        archive,
                        f"{prefix}/local_mse4_req.log",
                        required=False,
                        archive_prefix=archive_prefix,
                    )
                    read_text = _zip_text(
                        archive,
                        f"{prefix}/local_mse4_rdata.log",
                        required=False,
                        archive_prefix=archive_prefix,
                    )
                    write_text = _zip_text(
                        archive,
                        f"{prefix}/local_mse4_wdata.log",
                        required=False,
                        archive_prefix=archive_prefix,
                    )
                    requests = _local_request_events(request_text)
                    request_by_issue = {
                        (item["time_ns"], item["channel"]): item for item in requests
                    }
                    output_intervals = region_by_bank.get((slice_id, 0), [])
                    p_intervals = [item for item in output_intervals if item["name"] == "P"]
                    reads = _local_read_events(read_text)
                    output_reads: list[dict[str, Any]] = []
                    for item in reads:
                        request = request_by_issue.get(
                            (item["issue_time_ns"], item["issue_channel"])
                        )
                        if request is None:
                            continue
                        local_line = request["local_line"]
                        if not any(
                            region["start_line"] <= local_line < region["end_line"]
                            for region in p_intervals
                        ):
                            continue
                        output_reads.append(
                            {
                                **item,
                                "local_line_addr": f"0x{local_line:06X}",
                                "expected_bank_data_128bit": _bank_data_word(
                                    package, slice_id, 0, local_line
                                ),
                            }
                        )
                    output_write_requests = [
                        item
                        for item in requests
                        if item["rw"] == 1
                        and any(
                            region["start_line"] <= item["local_line"] < region["end_line"]
                            for region in p_intervals
                        )
                    ]
                    completed = any(
                        "slice completed" in text
                        for text in (request_text, read_text, write_text)
                    )
                    slice_reports.append(
                        {
                            "slice_id": slice_id,
                            "completed": completed,
                            "output_read_returns": output_reads,
                            "unknown_output_read_return_count": sum(
                                item["contains_unknown"] for item in output_reads
                            ),
                            "output_write_request_count": len(output_write_requests),
                            "output_write_data_handshake_count": _local_write_data_count(
                                write_text
                            ),
                        }
                    )
                local_runtime["slice_count"] = len(slice_reports)
                local_runtime["completed_slice_count"] = sum(
                    item["completed"] for item in slice_reports
                )
                local_runtime["slices_with_unknown_output_reads"] = sum(
                    item["unknown_output_read_return_count"] > 0 for item in slice_reports
                )
                local_runtime["output_read_return_count"] = sum(
                    len(item["output_read_returns"]) for item in slice_reports
                )
                local_runtime["unknown_output_read_return_count"] = sum(
                    item["unknown_output_read_return_count"] for item in slice_reports
                )
                local_runtime["output_write_request_count"] = sum(
                    item["output_write_request_count"] for item in slice_reports
                )
                local_runtime["output_write_data_handshake_count"] = sum(
                    item["output_write_data_handshake_count"] for item in slice_reports
                )
                local_runtime["slices"] = slice_reports
                if (
                    slice_reports
                    and local_runtime["completed_slice_count"] == 0
                    and local_runtime["slices_with_unknown_output_reads"] == len(slice_reports)
                    and local_runtime["output_write_request_count"] > 0
                    and local_runtime["output_write_data_handshake_count"] == 0
                ):
                    local_runtime["status"] = "stalled_on_unknown_output_read_modify_write"
                elif (
                    slice_reports
                    and local_runtime["completed_slice_count"] == 0
                    and local_runtime["unknown_output_read_return_count"] == 0
                    and local_runtime["output_read_return_count"] > 0
                    and local_runtime["output_write_request_count"] > 0
                    and local_runtime["output_write_data_handshake_count"] == 0
                ):
                    local_runtime["status"] = (
                        "trace_ends_after_clean_output_rmw_before_write_data"
                    )
                else:
                    local_runtime["status"] = "observed"

    output_regions = [
        {
            key: value
            for key, value in region.items()
            if key not in {"start_line", "end_line"}
        }
        for regions in region_by_bank.values()
        for region in regions
    ]
    p_writes_all = sum(
        item["write_transactions"] for item in output_regions if item["name"] == "P"
    )
    d_writes_all = sum(
        item["write_transactions"]
        for item in output_regions
        if item["name"].startswith("staged_D_")
    )
    p_writes = sum(
        item["runtime_write_transactions"]
        for item in output_regions
        if item["name"] == "P"
    )
    d_writes = sum(
        item["runtime_write_transactions"]
        for item in output_regions
        if item["name"].startswith("staged_D_")
    )
    write_passed = sum(item["preload_write_status"] == "passed" for item in probes)
    read_seen = sum(
        item["mc_read_value_status"] == "observed_after_preload_write" for item in probes
    )
    strict_readback_ok = write_passed == len(probes) and read_seen == len(probes)
    raw_required_markers = completion_gate.get("required_markers", [])
    marker_contract_error: str | None = None
    if not isinstance(raw_required_markers, list) or not all(
        isinstance(marker, str) and marker for marker in raw_required_markers
    ):
        required_markers: list[str] = []
        marker_contract_error = "completion required_markers contract is invalid"
    else:
        required_markers = list(raw_required_markers)
    marker_names = {
        "Start_Comp",
        "slice completed",
        "Total handshakes",
        "timeout",
        "ERROR",
        "FAIL",
        *required_markers,
    }
    terminal_markers = {
        marker: len(re.findall(re.escape(marker), terminal_text, flags=re.IGNORECASE))
        for marker in sorted(marker_names)
    }
    missing_required_markers = [
        marker for marker in required_markers if terminal_markers.get(marker, 0) == 0
    ]
    fatal_terminal_markers = {
        marker: terminal_markers.get(marker, 0) for marker in ("timeout", "ERROR", "FAIL")
        if terminal_markers.get(marker, 0) > 0
    }

    raw_post_run_dump = runner.get("post_run_dump", {})
    post_run_dump_contract_error: str | None = None
    if not isinstance(raw_post_run_dump, Mapping):
        post_run_dump: Mapping[str, Any] = {}
        post_run_dump_contract_error = "runner post_run_dump contract is invalid"
    else:
        post_run_dump = raw_post_run_dump
    raw_required_slices = post_run_dump.get("required_slices")
    if raw_required_slices is None:
        required_slice_count = int(dump_contract.get("slice_count", 0))
        required_dump_slices = list(range(required_slice_count))
    elif isinstance(raw_required_slices, list) and all(
        isinstance(slice_id, int) and slice_id >= 0 for slice_id in raw_required_slices
    ):
        required_dump_slices = sorted(set(raw_required_slices))
    else:
        required_dump_slices = []
        post_run_dump_contract_error = "runner post_run_dump required_slices is invalid"
    try:
        minimum_dump_bytes = int(post_run_dump.get("minimum_bytes_per_slice", 0))
    except (TypeError, ValueError):
        minimum_dump_bytes = 0
        post_run_dump_contract_error = "runner post_run_dump minimum_bytes_per_slice is invalid"
    if minimum_dump_bytes < 0:
        minimum_dump_bytes = 0
        post_run_dump_contract_error = "runner post_run_dump minimum_bytes_per_slice is invalid"

    qualifying_dump_slices: set[int] = set()
    for record in direct_dump_records:
        record["meets_contract"] = (
            record["bank_id"] == 0
            and record["format_valid"]
            and record["represented_bytes"] >= minimum_dump_bytes
            and record["represented_bytes"] > 0
        )
        if record["meets_contract"]:
            qualifying_dump_slices.add(int(record["slice_id"]))
    missing_dump_slices = sorted(set(required_dump_slices) - qualifying_dump_slices)
    invalid_dump_entries = sorted(
        record["path"] for record in direct_dump_records if not record["meets_contract"]
    )
    dump_structure_ok = (
        post_run_dump_contract_error is None
        and bool(direct_dump_records)
        and not missing_dump_slices
        and (bool(required_dump_slices) or bool(qualifying_dump_slices))
    )

    raw_required_metadata = runner.get("required_return_metadata", [])
    metadata_contract_error: str | None = None
    if not isinstance(raw_required_metadata, list) or not all(
        isinstance(key, str) and key for key in raw_required_metadata
    ):
        required_metadata: list[str] = []
        metadata_contract_error = "required_return_metadata contract is invalid"
    else:
        required_metadata = list(raw_required_metadata)
    metadata_values = dict(return_metadata or {})
    metadata_exit_status = metadata_values.get("exit_status")
    if metadata_exit_status is not None:
        try:
            parsed_metadata_exit_status = int(metadata_exit_status)
        except (TypeError, ValueError):
            return_metadata_error = "return metadata exit_status is not an integer"
        else:
            if exit_status is None:
                exit_status = parsed_metadata_exit_status
                exit_status_entry = return_metadata_entry
            elif exit_status != parsed_metadata_exit_status:
                return_metadata_error = "return metadata and exit-status file disagree"

    metadata_present_keys = {
        key
        for key, value in metadata_values.items()
        if value is not None and value != "" and value != [] and value != {}
    }
    if exit_status is not None:
        metadata_present_keys.add("exit_status")
    missing_metadata = sorted(set(required_metadata) - metadata_present_keys)
    invalid_metadata: list[str] = []
    expected_identity_values = {
        "freeze_id": package_manifest.get("freeze_id"),
        "freeze_manifest_sha256": package_manifest.get("freeze_manifest_sha256"),
        "package_manifest_sha256": _sha256(package / "manifest.json"),
    }
    for key, expected_value in expected_identity_values.items():
        if key in metadata_present_keys and metadata_values.get(key) != expected_value:
            invalid_metadata.append(f"{key} does not match the analyzed package")
    if "completed_runtime_stage_count" in metadata_present_keys:
        try:
            returned_stage_count = int(metadata_values["completed_runtime_stage_count"])
        except (TypeError, ValueError):
            invalid_metadata.append("completed_runtime_stage_count is not an integer")
        else:
            if (
                returned_stage_count != actual_stage_count
                or returned_stage_count != expected_stage_count
            ):
                invalid_metadata.append(
                    "completed_runtime_stage_count does not match the observed/expected stage count"
                )

    structural_reasons: list[str] = []
    run_failed = bool(fatal_terminal_markers) or exit_status_error is not None or (
        exit_status is not None and exit_status != 0
    )
    if actual_stage_count != expected_stage_count:
        structural_reasons.append(
            f"only {actual_stage_count}/{expected_stage_count} runtime Start_Comp stages "
            "were observed"
        )
    if terminal_selection_error is not None:
        structural_reasons.append(terminal_selection_error)
    if not terminal_text:
        structural_reasons.append("no terminal/console output exists in the return archive")
    if sca_payload_contract_error is not None:
        structural_reasons.append(sca_payload_contract_error)
    if sca_payload_count is not None and loaded_matrix_count != sca_payload_count:
        structural_reasons.append(
            "SCA preload did not complete: "
            f"completed_summary={loaded_matrix_count!r}, expected={sca_payload_count}, "
            f"started_entries={started_matrix_count}"
        )
    if expected_start_count != expected_stage_count:
        structural_reasons.append(
            "runner expected_start_comp_count does not match expected_runtime_stage_count"
        )
    if marker_contract_error is not None:
        structural_reasons.append(marker_contract_error)
    if missing_required_markers:
        structural_reasons.append(
            "required completion markers are missing: " + ", ".join(missing_required_markers)
        )
    if fatal_terminal_markers:
        structural_reasons.append(
            "terminal output contains failure markers: "
            + ", ".join(
                f"{marker}={count}" for marker, count in fatal_terminal_markers.items()
            )
        )
    if exit_status_error is not None:
        structural_reasons.append(exit_status_error)
    if exit_status is not None and exit_status != 0:
        structural_reasons.append(f"simulator exit status is non-zero: {exit_status}")
    if metadata_contract_error is not None:
        structural_reasons.append(metadata_contract_error)
    if return_metadata_error is not None:
        structural_reasons.append(return_metadata_error)
    if missing_metadata:
        structural_reasons.append(
            "required return metadata is missing: " + ", ".join(missing_metadata)
        )
    if invalid_metadata:
        structural_reasons.extend(invalid_metadata)
    if not strict_readback_ok:
        structural_reasons.append(
            f"strict preload readback is incomplete: writes={write_passed}/{len(probes)}, "
            f"MC reads={read_seen}/{len(probes)}"
        )
    if post_run_dump_contract_error is not None:
        structural_reasons.append(post_run_dump_contract_error)
    if not direct_dump_records:
        structural_reasons.append(
            "no post-run sliceXX_Bank00_data.bin/.txt dump exists in the archive"
        )
    elif missing_dump_slices:
        structural_reasons.append(
            "complete post-run Bank00 dumps are missing or undersized for slices: "
            + ", ".join(str(slice_id) for slice_id in missing_dump_slices)
        )
    if invalid_dump_entries:
        structural_reasons.append(
            "post-run bank dumps fail bank/format/size validation: "
            + ", ".join(invalid_dump_entries)
        )
    if p_writes == 0:
        structural_reasons.append(
            "no P-region write transaction was observed in bank-frame traces"
        )
    if d_writes == 0:
        structural_reasons.append(
            "no staged-D-region write transaction was observed in bank-frame traces"
        )
    if local_runtime["status"] == "stalled_on_unknown_output_read_modify_write":
        structural_reasons.insert(
            0,
            "all runtime slices read unknown data from P during the first output read-modify-write, "
            "issued output write requests, observed zero output write-data handshakes, and never completed",
        )
    elif local_runtime["status"] == "trace_ends_after_clean_output_rmw_before_write_data":
        structural_reasons.insert(
            0,
            "all observed runtime slices returned deterministic P data and issued output write requests, "
            "but the trace ended before any output write-data handshake or slice completion was observed",
        )

    structural_ok = not structural_reasons and dump_structure_ok
    numeric_comparison_reason = (
        "hardware dump values were not inverse-mapped and compared with frozen Golden/NDP tensors; "
        "run the package comparison_command on the complete post-run Bank dumps"
    )
    reasons = [*structural_reasons, numeric_comparison_reason]
    hardware_status = "not_comparable"
    report_status = (
        "returned_failed"
        if run_failed
        else ("returned_uncompared" if structural_ok else "returned_incomplete")
    )

    local_trace_namespaces = sorted(
        namespace
        for namespace in archive_namespaces
        if namespace == "local" or namespace.startswith("local_")
    )
    selected_local_namespace = local_runtime.get("namespace")
    other_local_namespaces = [
        namespace for namespace in local_trace_namespaces if namespace != selected_local_namespace
    ]
    first_failure_stage = (
        "slice_output_read_modify_write"
        if local_runtime["status"] == "stalled_on_unknown_output_read_modify_write"
        else (
            "slice_output_write_data"
            if local_runtime["status"] == "trace_ends_after_clean_output_rmw_before_write_data"
            else (
                "server_run"
                if run_failed
                else ("return_evidence" if structural_reasons else "hardware_numeric_comparison")
            )
        )
    )

    report: dict[str, Any] = {
        "schema_version": "resnet50-hardware-server-trace-comparison-0.2",
        "status": report_status,
        "comparison_verdict": "three_way_not_comparable",
        "archive": {
            "path": str(archive_file),
            "size_bytes": archive_file.stat().st_size,
            "sha256": _sha256(archive_file),
            "entry_count": len(entry_names),
            "archive_prefix": archive_prefix,
            "trace_namespaces": sorted(archive_namespaces),
            "selected_local_trace_namespace": selected_local_namespace,
            "other_local_trace_namespaces": other_local_namespaces,
            "terminal_output_present": bool(terminal_text),
            "terminal_output_entry": terminal_entry,
            "terminal_selection_error": terminal_selection_error,
            "gexec_trace_present": bool(gexec_text),
            "direct_post_run_bank_dumps": sorted(direct_dump_entries),
            "return_metadata": {
                "entry": return_metadata_entry,
                "required_keys": required_metadata,
                "present_keys": sorted(metadata_present_keys),
                "missing_keys": missing_metadata,
                "invalid_reasons": invalid_metadata,
                "parse_error": return_metadata_error,
            },
            "simulator_exit_status": {
                "entry": exit_status_entry,
                "value": exit_status,
                "parse_error": exit_status_error,
            },
        },
        "identity": {
            "package_root": str(package),
            "package_manifest_sha256": _sha256(package / "manifest.json"),
            "source_freeze_id": package_manifest.get("freeze_id"),
            "source_freeze_manifest_sha256": package_manifest.get("freeze_manifest_sha256"),
            "preflight_path": str(preflight_file),
            "preflight_sha256": _sha256(preflight_file),
        },
        "preload": {
            "probe_count": len(probes),
            "matching_preload_write_count": write_passed,
            "matching_mc_read_value_count": read_seen,
            "strict_readback_status": "passed" if strict_readback_ok else "incomplete",
            "terminal_loaded_matrix_count": loaded_matrix_count,
            "terminal_started_matrix_count": started_matrix_count,
            "sca_cfg_payload_count": sca_payload_count,
            "sca_cfg_payload_count_source": sca_payload_count_source,
            "sca_cfg_payload_contract_error": sca_payload_contract_error,
            "matrix_load_completion_status": (
                "passed"
                if sca_payload_count is not None
                and loaded_matrix_count == sca_payload_count
                else "incomplete"
            ),
            "loaded_source_inference": (
                "sca_cfg_sparse_payloads"
                if loaded_matrix_count is not None
                and sca_payload_count is not None
                and loaded_matrix_count == sca_payload_count
                else "not_determined"
            ),
            "note": (
                "MC logs expose returned values but not an unambiguous full address; the write address and "
                "post-write returned value are recorded separately."
            ),
            "probes": probes,
        },
        "runtime": {
            "timestamp_note": (
                "Legacy JSON field names end in _ns, but the current VCS testbench prints %0t with "
                "a 1ns/1ps timescale; returned trace integers are therefore ps-scaled raw timestamps."
            ),
            "expected_runtime_stage_count": expected_stage_count,
            "expected_start_comp_count": expected_start_count,
            "observed_start_comp_stage_count": actual_stage_count,
            "observed_start_comp_broadcast_count": len(start_rows),
            "observed_start_comp_times_ns": start_times,
            "gexec_row_count": len(gexec_rows),
            "terminal_markers": terminal_markers,
            "required_markers": required_markers,
            "missing_required_markers": missing_required_markers,
            "fatal_terminal_markers": fatal_terminal_markers,
            "status": (
                "failed"
                if run_failed
                else (
                    "passed"
                    if actual_stage_count == expected_stage_count and not missing_required_markers
                    else "incomplete"
                )
            ),
            "local_slice_execution": local_runtime,
        },
        "hardware_outputs": {
            "status": hardware_status,
            "structural_evidence_status": "passed" if structural_ok else "incomplete",
            "P_bank_write_transactions": p_writes,
            "staged_D_bank_write_transactions": d_writes,
            "P_bank_write_transactions_all_phases": p_writes_all,
            "staged_D_bank_write_transactions_all_phases": d_writes_all,
            "transaction_count_note": (
                "The unqualified P/staged-D counters include runtime transactions only; "
                "all_phases and per-region legacy counters also include preload/scratch initialization."
            ),
            "frame_file_count": frame_file_count,
            "mc_read_file_count": mc_file_count,
            "regions": output_regions,
            "post_run_bank_dump_validation": {
                "status": "passed" if dump_structure_ok else "incomplete",
                "minimum_bytes_per_slice": minimum_dump_bytes,
                "required_slices": required_dump_slices,
                "qualifying_slices": sorted(qualifying_dump_slices),
                "missing_or_undersized_slices": missing_dump_slices,
                "invalid_entries": invalid_dump_entries,
                "entries": sorted(direct_dump_records, key=lambda item: item["path"]),
            },
            "incomplete_reasons": reasons,
        },
        "numeric_hardware_comparison": {
            "status": "not_run",
            "required_command": runner.get("comparison_command"),
            "reason": numeric_comparison_reason,
        },
        "three_way_comparison": {
            "golden_vs_config_bound_ndp": ndp_comparison,
            "golden_vs_hardware": {"status": hardware_status, "reasons": reasons},
            "config_bound_ndp_vs_hardware": {"status": hardware_status, "reasons": reasons},
        },
        "first_failure": (
            {
                "stage": first_failure_stage,
                "expected_runtime_stage_count": expected_stage_count,
                "observed_runtime_stage_count": actual_stage_count,
                "detail": reasons[0] if reasons else None,
            }
        ),
    }
    extracted = {
        "terminal_output.txt": terminal_text,
        "gexec2slice.log": gexec_text,
    }
    return report, extracted
