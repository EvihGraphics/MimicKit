#!/usr/bin/env python3
"""Build the final MimicKit -> EvihAnimation visual bridge closure manifest."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from visual_bridge_validation import sha256_file, write_json


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def parse_case_spec(text: str) -> dict[str, Path | str]:
    fields: dict[str, str] = {}
    for token in text.split(","):
        key, sep, value = token.partition("=")
        if sep:
            fields[key.strip()] = value.strip()
    if not fields.get("label") or not fields.get("mimic") or not fields.get("evih") or not fields.get("review"):
        raise ValueError("--case requires label=...,mimic=...,evih=...,review=...")
    return {key: (Path(value).resolve() if key != "label" else value) for key, value in fields.items()}


def case_report(spec: dict[str, Path | str]) -> dict[str, Any]:
    mimic_path = Path(spec["mimic"])
    evih_path = Path(spec["evih"])
    review_path = Path(spec["review"])
    mimic = read_json(mimic_path)
    evih = read_json(evih_path)
    review = read_json(review_path)
    checks = {
        "mimic_manifest_exists": mimic_path.exists(),
        "mimic_mesh_reference_pass": bool(mimic.get("mesh_reference_pass")),
        "mimic_blocker_empty": not bool(str(mimic.get("blocker", "")).strip()),
        "evih_manifest_exists": evih_path.exists(),
        "evih_mesh_replay_pass": bool(evih.get("evih_mesh_replay_pass")),
        "mesh_binding_pass": bool(evih.get("mesh_binding_pass")),
        "scene_contract_compare_pass": bool(evih.get("scene_contract_compare_pass")),
        "visual_metric_pass": bool(evih.get("visual_metric_pass")),
        "evih_blocker_empty": not bool(str(evih.get("blocker", "")).strip()),
        "visual_review_exists": review_path.exists(),
        "visual_review_pass": bool(review.get("visual_review_pass")),
    }
    return {
        "label": spec["label"],
        "pass": all(checks.values()),
        "checks": checks,
        "mimic_manifest": str(mimic_path),
        "mimic_manifest_sha256": sha256_file(mimic_path),
        "evih_manifest": str(evih_path),
        "evih_manifest_sha256": sha256_file(evih_path),
        "visual_review": str(review_path),
        "visual_review_sha256": sha256_file(review_path),
        "blockers": [
            blocker
            for blocker in [str(mimic.get("blocker", "")).strip(), str(evih.get("blocker", "")).strip()]
            if blocker
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", action="append", default=[], help="label=...,mimic=...,evih=...,review=...")
    parser.add_argument("--baseline-snapshot", default="")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    cases = [case_report(parse_case_spec(text)) for text in args.case]
    baseline_path = Path(args.baseline_snapshot).resolve() if args.baseline_snapshot else None
    baseline = read_json(baseline_path) if baseline_path else {}
    manifest = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "cases": cases,
        "baseline_snapshot": str(baseline_path) if baseline_path else "",
        "baseline_snapshot_sha256": sha256_file(baseline_path) if baseline_path else "",
        "baseline_protection_pass": bool(baseline.get("baseline_protection_pass")) if baseline_path else False,
        "full_chain_bridge_pass": bool(cases) and all(item["pass"] for item in cases) and bool(baseline.get("baseline_protection_pass")),
    }
    manifest["blocker"] = "" if manifest["full_chain_bridge_pass"] else "full_chain_bridge_gate_failed"
    write_json(Path(args.out).resolve(), manifest)
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0 if manifest["full_chain_bridge_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
