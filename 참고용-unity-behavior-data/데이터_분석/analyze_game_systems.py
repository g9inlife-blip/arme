#!/usr/bin/env python3
"""Unity JSON의 2차 의미 분석기.

1차 build_data_graph.py가 만든 ID/Reference 결과와 원본 JSON을 함께 사용해
게임 시스템 후보를 찾는다. 이 단계에서도 의미를 확정하지 않고 후보/근거를 저장한다.
"""

from __future__ import annotations
import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

SYSTEM_PATTERNS = {
    "gacha": ["drawrecord", "drawpreviewrecord", "draw", "gacha", "summon", "banner", "probability", "pool"],
    "item_package": ["itempackage", "package", "itempack"],
    "shop": ["shoprecord", "shop", "store", "purchase", "price", "currency"],
    "reward": ["reward", "rewardrecord", "rewardgroup", "drop"],
    "daily_login": ["daily", "login", "attendance", "checkin", "streak"],
    "achievement": ["achievement", "mission", "quest", "condition"],
    "event": ["event", "limited", "season", "period"],
    "character": ["character", "hero", "actor", "unit"],
    "equipment": ["equipment", "weapon", "armor", "accessory"],
    "skill": ["skill", "passive", "ability"],
    "stage": ["stage", "chapter", "wave", "level"],
    "monster": ["monster", "enemy", "boss", "spawn"],
    "currency": ["currency", "gold", "gem", "coin", "point"],
}

ID_KEY_RE = re.compile(r"(?:^|_)(?:m_)?[a-z0-9]*(?:id|ids)(?:$|_)", re.I)
CODE_VALUE_RE = re.compile(r"^[^|*\s]+\*[^|*\s]+(?:\|[^|*\s]+\*[^|*\s]+)+$")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def norm(s: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(s).lower())


def find_id(obj: dict[str, Any]) -> str | None:
    for k in ("id", "m_id", "_id", "recordid", "record_id"):
        if k in obj:
            v = obj[k]
            if isinstance(v, (int, float, str)) and str(v).strip():
                return str(v).strip()
    return None


def classify_text(text: str) -> list[str]:
    n = norm(text)
    hits = []
    for system, words in SYSTEM_PATTERNS.items():
        if any(norm(w) in n for w in words):
            hits.append(system)
    return hits


def flatten_fields(obj: Any, prefix: str = "$", out: list[tuple[str, Any]] | None = None):
    if out is None:
        out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{prefix}.{k}"
            out.append((p, v))
            flatten_fields(v, p, out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            flatten_fields(v, f"{prefix}[{i}]", out)
    return out


def collect_records(obj: Any, path: str = "$"):
    if isinstance(obj, dict):
        rid = find_id(obj)
        if rid is not None:
            yield path, rid, obj
        for k, v in obj.items():
            yield from collect_records(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from collect_records(v, f"{path}[{i}]")


def candidate_for_record(path: str, rid: str, obj: dict[str, Any], source_file: str):
    field_names = [str(k) for k in obj.keys()]
    text = " ".join(field_names + [path, source_file])
    systems = classify_text(text)
    code_values = []
    pipe_lists = []
    id_refs = []
    for fp, value in flatten_fields(obj):
        if isinstance(value, str):
            if CODE_VALUE_RE.fullmatch(value.strip()):
                code_values.append({"field": fp, "raw_value": value})
            if "|" in value and "*" not in value:
                parts = [x.strip() for x in value.split("|") if x.strip()]
                if len(parts) >= 2:
                    pipe_lists.append({"field": fp, "items": parts})
        key = fp.rsplit(".", 1)[-1]
        if ID_KEY_RE.search(key.lower()) and key.lower() not in {"id", "m_id", "_id", "recordid", "record_id"}:
            id_refs.append({"field": fp, "value": value})
    return {
        "id": rid,
        "source_file": source_file,
        "path": path,
        "systems": systems,
        "field_names": field_names,
        "reference_like_fields": id_refs,
        "code_value_fields": code_values,
        "pipe_id_fields": pipe_lists,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", type=Path, required=True)
    ap.add_argument("--output", type=Path, default=None)
    args = ap.parse_args()
    root = args.data_root.resolve()
    out = (args.output or Path(__file__).resolve().parent / "output").resolve()
    out.mkdir(parents=True, exist_ok=True)
    work = out / "_work"
    work.mkdir(parents=True, exist_ok=True)

    inventory = []
    system_counts = Counter()
    field_counts = Counter()
    candidate_counts = Counter()
    gacha_candidates = []
    structured_candidates = []

    files = sorted(root.rglob("*.json"))
    for fp in files:
        rel = fp.relative_to(root).as_posix()
        try:
            data = load_json(fp)
        except Exception:
            continue
        for path, rid, record in collect_records(data):
            item = candidate_for_record(path, rid, record, rel)
            inventory.append(item)
            for s in item["systems"]:
                system_counts[s] += 1
                candidate_counts[s] += 1
                if s == "gacha":
                    gacha_candidates.append(item)
            for x in item["field_names"]:
                field_counts[x] += 1
            if item["code_value_fields"] or item["pipe_id_fields"]:
                structured_candidates.append(item)

    with (work / "record_system_candidates.ndjson").open("w", encoding="utf-8") as f:
        for x in inventory:
            f.write(json.dumps(x, ensure_ascii=False, separators=(",", ":")) + "\n")

    with (work / "gacha_candidates.ndjson").open("w", encoding="utf-8") as f:
        for x in gacha_candidates:
            f.write(json.dumps(x, ensure_ascii=False, separators=(",", ":")) + "\n")

    with (work / "structured_system_candidates.ndjson").open("w", encoding="utf-8") as f:
        for x in structured_candidates:
            f.write(json.dumps(x, ensure_ascii=False, separators=(",", ":")) + "\n")

    summary = {
        "json_file_count": len(files),
        "record_count": len(inventory),
        "system_candidate_counts": dict(system_counts),
        "top_fields": field_counts.most_common(100),
        "notes": [
            "분류는 필드명/경로/파일명의 문자열 패턴 기반 후보 탐색이다.",
            "후보 분류만으로 게임 의미를 확정하지 않는다.",
            "gacha_candidates는 Draw/Pool/Probability/Banner 등 가챠 관련 후보를 우선 추출한다.",
        ],
    }
    (out / "02_record_type_inventory.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    system_md = ["# 게임 시스템 후보 분석", "", "## 현재 결과", ""]
    for s, n in system_counts.most_common():
        system_md.append(f"- {s}: {n}")
    system_md += ["", "## 다음 분석 우선순위", "",
                   "1. gacha", "2. item_package", "3. reward", "4. shop",
                   "5. daily_login", "6. achievement", "7. event",
                   "8. character / equipment / skill", "9. stage / monster", ""]
    system_md.append("분류 결과는 후보이며, Reference와 반복 구조를 확인한 뒤 의미를 확정한다.")
    (out / "07_system_candidates.md").write_text("\n".join(system_md) + "\n", encoding="utf-8")

    print(f"JSON: {len(files)}")
    print(f"Record: {len(inventory)}")
    for s, n in system_counts.most_common():
        print(f"{s}: {n}")
    print(f"[결과] {out}")


if __name__ == "__main__":
    main()
