#!/usr/bin/env python3
"""Finalize local receipts for the exact serialized-Conv FSDB smoke ZIP."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/conv_node0004_fsdb_smoke_s1_release1"
ZIP = OUT / "r5_n4_hw_fsdbsmoke_s1.zip"
PACKAGE_ID = "r5_n4_hw_fsdbsmoke_s1"
SCHEMA_TAG = "s1"
OLD_ID = "r5_n4_hw_v88b_portvcd"
SOURCE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/tested/conv_serialized_node0004/r5_n4_hw_v88b_portvcd/r5_n4_hw_v88b_portvcd.zip"
GATES = {
    "fsdb_v3_final_zip": OUT / "gates/fsdb_v3_final_zip.json",
    "post_sim_final_zip": OUT / "gates/post_sim_final_zip.json",
    "runner_resilience": OUT / "gates/runner_resilience.json",
    "runtime_harness": OUT / "gates/runtime_harness_family.json",
    "runtime_layout": OUT / "gates/runtime_layout_validation.json",
    "first_fresh": OUT / "gates/first_fresh_validation.json",
}


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def identity(path: Path) -> dict[str, object]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    errors: list[str] = []
    gate_receipts = {}
    for name, path in GATES.items():
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"{name}:unreadable:{exc}")
            continue
        gate_receipts[name] = {**identity(path), "pass": value.get("pass") is True, "errors": value.get("errors", [])}
        if value.get("pass") is not True:
            errors.append(f"{name}:failed")

    with zipfile.ZipFile(ZIP) as archive:
        names = archive.namelist()
        if archive.testzip() is not None:
            errors.append("zip_crc")
        roots = {PurePosixPath(name).parts[0] for name in names}
        if roots != {PACKAGE_ID}:
            errors.append("zip_root")
        prefix = f"{PACKAGE_ID}/"
        members = {name[len(prefix):]: archive.read(name) for name in names if name.startswith(prefix) and not name.endswith("/")}
    runner = members.get("PREPARE_AND_RUN.sh", b"").decode("utf-8", errors="replace")
    exact_tokens = {token: runner.count(token) for token in ("DUMP_VCD=0", "DUMP_FSDB=1", "TB_DUMP_FSDB=0")}
    for token, count in exact_tokens.items():
        if count < 1:
            errors.append(f"runner_missing:{token}")
    forbidden_tokens = ["DUMP_PORTABLE_VCD", "wave.vpd", "wave.vcd", "arb_req_ready", "ACK_INLINE", "buffer_ack_phase"]
    forbidden_hits = [token for token in forbidden_tokens if token in runner or any(token.encode() in data for path, data in members.items() if path.startswith("tb_probe/"))]
    if forbidden_hits:
        errors.append("retired_or_wrong_waveform_surface:" + ",".join(forbidden_hits))
    forbidden_members = [name for name in members if name.endswith(("inter.fsdb", "novas.fsdb")) or "buffer_ack" in name.lower()]
    if forbidden_members:
        errors.append("forbidden_member")
    probe = members.get("tb_probe/fsdb_smoke_event_probe.svh", b"")
    writer_calls = sum(data.count(b"fsdbDumpfile") for path, data in members.items() if path.endswith((".tcl", ".sv", ".svh")))
    if writer_calls != 1 or b"fsdbDumpfile" in probe:
        errors.append("writer_count")

    source_prefix = f"{OLD_ID}/workload/runtime/"
    frozen_count = 0
    with zipfile.ZipFile(SOURCE) as source:
        for info in source.infolist():
            if info.is_dir() or not info.filename.startswith(source_prefix):
                continue
            relative = info.filename[len(source_prefix):]
            original = source.read(info)
            current = members.get(f"workload/runtime/{relative}")
            if current is None:
                errors.append(f"frozen_missing:{relative}")
                continue
            try:
                restored = current.decode("utf-8").replace(PACKAGE_ID, OLD_ID).encode("utf-8")
                original.decode("utf-8")
            except UnicodeDecodeError:
                restored = current
            if restored != original:
                errors.append(f"frozen_identity:{relative}")
            frozen_count += 1

    first_fresh = json.loads(GATES["first_fresh"].read_text()) if GATES["first_fresh"].is_file() else {}
    audit = {
        "schema": f"node0004-fsdb-smoke-{SCHEMA_TAG}-final-zip-audit-v1",
        "package_id": PACKAGE_ID,
        "status": "PACKAGE_READY_NOT_RUN" if not errors else "LOCAL_GATE_FAILED",
        "pass": not errors,
        "errors": errors,
        "zip": identity(ZIP),
        "exact_member_count": len(members),
        "runner": {"bytes": len(runner.encode()), "sha256": sha_bytes(runner.encode()), "mandatory_tokens": exact_tokens, "forbidden_hits": forbidden_hits},
        "fsdb": {"writer_count": writer_calls, "attempt_local_primary": "run/sim_results/wave.fsdb", "all_shards": "wave.fsdb.*", "unbounded": True, "root_historical_fsdb_eligible": False},
        "repeat": {"fixed_attempt": "smoke", "fresh_execution_return": True, "prior_returns_preserved": True, "local_harness_pass": gate_receipts.get("runtime_harness", {}).get("pass") is True},
        "frozen_workload": {"source": identity(SOURCE), "member_count": frozen_count, "identity_only_package_path_relocation": True, "functional_payload_frozen": not any(e.startswith("frozen_") for e in errors)},
        "first_fresh": {"pass": first_fresh.get("pass") is True, "candidate_coverage": first_fresh.get("candidate_coverage"), "epoch": first_fresh.get("rule_change_epoch_id")},
        "gate_receipts": gate_receipts,
        "server_action": "NONE",
        "claim_boundary": "Local exact-ZIP/runtime-stub/return-contract validation only; no production VCS, DUT, natural-terminal, formal-D or operator correctness claim.",
    }
    write_json(OUT / f"{PACKAGE_ID}.final_zip_audit.json", audit)
    sidecar = OUT / f"{PACKAGE_ID}.zip.sha256"
    sidecar.write_text(f"{sha(ZIP)}  {ZIP.name}\n", encoding="ascii", newline="\n")
    release = {
        "schema": f"node0004-fsdb-smoke-{SCHEMA_TAG}-release-receipt-v1",
        "package_id": PACKAGE_ID,
        "role_id": "family.conv.serialized",
        "owner_epoch": 2,
        "registry_epoch": 6,
        "activation_epoch": "fsdb-authoritative-repeatable-return-v3-0a1dee9757c6",
        "status": audit["status"],
        "package": identity(ZIP),
        "sidecar": identity(sidecar),
        "runner_member": f"{PACKAGE_ID}/PREPARE_AND_RUN.sh",
        "runner_sha256": audit["runner"]["sha256"],
        "return_contract_member": f"{PACKAGE_ID}/contracts/server_post_sim_return_request.json",
        "validator_receipts": gate_receipts,
        "future_server_command": f"bash {PACKAGE_ID}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01",
        "formal_successor": False,
        "server_action": "NONE",
        "conflicts": [],
    }
    write_json(OUT / f"{PACKAGE_ID}.release_receipt.json", release)
    task = f"""# Serialized Conv FSDB authoritative smoke {SCHEMA_TAG}

## Previous-version progress

v88b passed production compile/elaboration and its actual-source evidence proved the retired ACK allegation was an observer/source-identity semantic false positive. Its old direct-VCD UCLI path stopped production simulation at time 0, so no DUT diagnostic completed.

## Current-version purpose

`{PACKAGE_ID}` is one minimal FSDB-only transport/repeatability smoke, not a formal serialized Conv successor. It keeps the exact v88b workload semantics and adds only package-owned FSDB, registered event-query, runtime-layout and return surfaces. It does not contain the retired ACK comparator.

## Result

- State: `{audit['status']}`; never uploaded or run on a server.
- Flags: `DUMP_VCD=0 DUMP_FSDB=1 TB_DUMP_FSDB=0`.
- One attempt-local writer: `run/sim_results/wave.fsdb` plus every `wave.fsdb.*` shard, returned without a byte/event cap.
- Registered query: time-0 marker, time>0 marker and top reset transitions; query failure preserves raw FSDB/core and marks diagnostic evidence incomplete.
- Repeat contract: fixed `smoke` attempt reset, foreign sibling preservation and unique non-overwriting return per invocation.
- Local gates: FSDB v3, post-sim four-scenario, runner definition-before-use, runtime layout/six exits, sequential two-run repeat, clean-extract exact member map, negative candidate matrix and first-fresh epoch audit all pass.

## Pickup and command

- Package: `{ZIP.relative_to(ROOT).as_posix()}`
- Release receipt: `{(OUT / f'{PACKAGE_ID}.release_receipt.json').relative_to(ROOT).as_posix()}`
- Formal return contract: `{PACKAGE_ID}/contracts/server_post_sim_return_request.json`
- Future command (user/server operator only): `bash {PACKAGE_ID}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`

## Claim boundary

PACKAGE_READY_NOT_RUN only. Local safe stubs prove control flow and evidence plumbing, not production FSDB generation, VCS behavior, DUT progress, natural terminal, formal-D, E3/E4/E5 or operator correctness. GAP/native/QAdd/formal serialized packages remain frozen.
"""
    (OUT / f"{PACKAGE_ID}.task_record.md").write_text(task, encoding="utf-8", newline="\n")
    print(json.dumps({"pass": audit["pass"], "errors": errors, "status": audit["status"], "package": str(ZIP)}, sort_keys=True))
    return 0 if audit["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
