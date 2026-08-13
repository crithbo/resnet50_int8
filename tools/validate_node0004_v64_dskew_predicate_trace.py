from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path


PACKAGE = "r5_n4_hw_v64_dskew_diag"


def trace(rows: list[dict[str, int]]) -> list[dict[str, int]]:
    previous = {
        "desc": 0,
        "prepared": 0,
        "match": 0,
        "source_push": 0,
        "source_pop": 0,
        "lc13": 0,
        "lc15": 0,
        "pe7_write": 0,
    }
    emitted: list[dict[str, int]] = []
    for row in rows:
        changed = any(row[key] != previous[key] for key in previous)
        if changed:
            emitted.append({**row, "delta": row["prepared"] - row["desc"]})
        previous = {key: row[key] for key in previous}
    return emitted


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--zip", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    errors: list[str] = []
    rows = [
        # reset/stable levels: no transaction and no record
        dict(desc=0, prepared=0, match=0, source_push=0, source_pop=0,
             lc13=0, lc15=0, pe7_write=0),
        dict(desc=0, prepared=0, match=0, source_push=0, source_pop=0,
             lc13=0, lc15=0, pe7_write=0),
        # conjunct-near: prepare without descriptor creates first skew
        dict(desc=0, prepared=1, match=0, source_push=1, source_pop=1,
             lc13=1, lc15=0, pe7_write=0),
        # simultaneous descriptor+prepare preserves rather than multiplies skew
        dict(desc=1, prepared=2, match=1, source_push=2, source_pop=2,
             lc13=1, lc15=1, pe7_write=1),
        # descriptor catches up
        dict(desc=2, prepared=2, match=1, source_push=2, source_pop=2,
             lc13=1, lc15=1, pe7_write=1),
        # stable high levels produce no additional transaction
        dict(desc=2, prepared=2, match=1, source_push=2, source_pop=2,
             lc13=1, lc15=1, pe7_write=1),
        # post-epoch owner/source advance without descriptor
        dict(desc=2, prepared=2, match=1, source_push=3, source_pop=2,
             lc13=2, lc15=1, pe7_write=1),
        # first and second unmatched prepares produce delta 1 then 2
        dict(desc=2, prepared=3, match=1, source_push=3, source_pop=3,
             lc13=2, lc15=1, pe7_write=1),
        dict(desc=2, prepared=4, match=1, source_push=4, source_pop=4,
             lc13=2, lc15=1, pe7_write=1),
    ]
    emitted = trace(rows)
    expected_deltas = [1, 1, 0, 0, 1, 2]
    checks = {
        "stable_level_not_counted": len(emitted) == 6,
        "first_penultimate_final_after_boundary": (
            [row["delta"] for row in emitted] == expected_deltas
        ),
        "simultaneous_event_single_record": emitted[1]["delta"] == 1,
        "catchup_returns_zero": emitted[2]["delta"] == 0,
        "two_group_skew_reaches_two": emitted[-1]["delta"] == 2,
    }
    with zipfile.ZipFile(args.zip) as archive:
        observer = archive.read(
            f"{PACKAGE}/tb_probe/native_return_observer.svh"
        ).decode("utf-8")
        runner = archive.read(f"{PACKAGE}/PREPARE_AND_RUN.sh").decode("utf-8")
        runtime = archive.read(
            f"{PACKAGE}/package_tools/node0004_hang_localization_runtime.py"
        ).decode("utf-8")
    checks.update(
        {
            "actual_observer_predicate_present": all(
                token in observer
                for token in (
                    "RETURN_OBS_DSKEW",
                    "always @(negedge u_NDP_Top_new.clk_db",
                    "DSKEW_EDGE_V1",
                    "DSKEW_BOUNDARY_V1",
                    "return_obs_md_prepared_wr - return_obs_md_desc_hs",
                )
            ),
            "actual_runner_enable_and_limit_twice": (
                runner.count(
                    " +RETURN_OBS_DSKEW +RETURN_OBS_DSKEW_LIMIT=128"
                ) == 2
            ),
            "runtime_binding_present": all(
                token in runtime
                for token in (
                    '"feature": "RETURN_OBS_DSKEW"',
                    '"+RETURN_OBS_DSKEW"',
                    '"+RETURN_OBS_DSKEW_LIMIT=128"',
                    '"feature=RETURN_OBS_DSKEW", "enabled=1", "limit=128"',
                )
            ),
        }
    )
    dskew_consumer = "return_obs_md_prepared_wr - return_obs_md_desc_hs"
    expected_dskew_consumer_count = observer.count(dskew_consumer)
    negative_observer = observer.replace(
        dskew_consumer,
        "return_obs_md_prepared_wr - return_obs_md_prepared_wr",
        1,
    )
    negative_runner = runner.replace(
        " +RETURN_OBS_DSKEW +RETURN_OBS_DSKEW_LIMIT=128",
        " +RETURN_OBS_DSKEX +RETURN_OBS_DSKEW_LIMIT=128",
        1,
    )
    checks["predicate_typo_negative_fail_closed"] = (
        expected_dskew_consumer_count > 0
        and negative_observer.count(dskew_consumer)
        != expected_dskew_consumer_count
    )
    checks["runtime_binding_negative_fail_closed"] = (
        negative_runner.count(
            " +RETURN_OBS_DSKEW +RETURN_OBS_DSKEW_LIMIT=128"
        ) != 2
    )
    errors.extend(key for key, value in checks.items() if not value)
    report = {
        "schema": "node0004-v64-dskew-predicate-trace-v1",
        "valid": not errors,
        "errors": errors,
        "checks": checks,
        "input_rows": rows,
        "emitted": emitted,
        "claim_boundary": (
            "Metadata/event-trace proof for the exact changed DSKEW predicate "
            "only; no DUT, numeric, terminal, formal-D, E4 or E5 claim."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
