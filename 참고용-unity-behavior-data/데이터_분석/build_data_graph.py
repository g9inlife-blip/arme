#!/usr/bin/env python3
"""
참고용-unity-behavior-data 자동 참조 그래프 분석기.

Python은 사실 추출/검증을 담당하고, 의미 해석은 별도 단계에서 수행한다.
API/Response/Research 구조는 생성하지 않는다.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

# 로컬 개발 PC의 Unity 데이터 JSON 기본 경로
DEFAULT_DATA_ROOT = Path(r"C:\Users\USER\Documents\GitHub\arme\참고용-unity-behavior-data\MonoBehaviour")

ID_KEYS = {"id", "m_id", "_id", "recordid", "record_id"}

REFERENCE_KEY_RE = re.compile(
    r"(?:^|_)(?:m_)?[a-z0-9]*?(?:id|ids)(?:$|_)",
    re.IGNORECASE,
)

MULTI_VALUE_RE = re.compile(
    r"(?P<id>[A-Za-z0-9_:\\-.]+)\s*[xX*]\s*(?P<count>\d+)"
)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def is_id_key(key: str) -> bool:
    return key.lower() in ID_KEYS


def looks_like_reference_key(key: str) -> bool:
    return bool(REFERENCE_KEY_RE.search(key))


def scalar_candidates(value: Any) -> list[str]:
    if value is None or isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [str(value)]
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return []
        match = MULTI_VALUE_RE.fullmatch(value)
        if match:
            return [match.group("id")]
        if "," in value or ";" in value:
            return [x.strip() for x in re.split(r"[,;]", value) if x.strip()]
        return [value]
    return []


def find_id_in_record(obj: dict[str, Any]) -> str | None:
    for key, value in obj.items():
        if is_id_key(str(key)):
            candidates = scalar_candidates(value)
            if candidates:
                return candidates[0]
    return None


def iter_records(obj: Any, path: str = "$"):
    if isinstance(obj, dict):
        record_id = find_id_in_record(obj)
        if record_id is not None:
            yield path, obj, record_id
        for key, value in obj.items():
            yield from iter_records(value, f"{path}.{key}")
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            yield from iter_records(value, f"{path}[{i}]")


def extract_references(record: dict[str, Any], source_file: str, record_path: str):
    refs = []

    def walk(obj: Any, field_path: str):
        if isinstance(obj, dict):
            for key, value in obj.items():
                key_s = str(key)
                next_path = f"{field_path}.{key_s}"

                if looks_like_reference_key(key_s):
                    values = value if isinstance(value, list) else [value]
                    for raw in values:
                        candidates = scalar_candidates(raw)
                        if not candidates and isinstance(raw, dict):
                            nested_id = find_id_in_record(raw)
                            if nested_id:
                                candidates = [nested_id]

                        for candidate in candidates:
                            refs.append({
                                "source_file": source_file,
                                "source_record_id": record.get("m_id", record.get("id")),
                                "source_path": record_path,
                                "field": next_path,
                                "raw_value": raw,
                                "candidate_id": candidate,
                            })

                walk(value, next_path)

        elif isinstance(obj, list):
            for i, child in enumerate(obj):
                walk(child, f"{field_path}[{i}]")

    walk(record, "$")
    return refs


def json_rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def write_json(path: Path, data: Any):
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def write_graph_md(path: Path, data_root: Path, summary: dict[str, Any],
                   refs: list[dict[str, Any]],
                   unresolved: list[dict[str, Any]],
                   duplicates: list[dict[str, Any]]):
    edge_counts = Counter((r["source_file"], r["target_file"]) for r in refs)

    lines = [
        "# 실제 데이터 참조 그래프 분석 결과",
        "",
        f"- 분석 대상: {data_root}",
        f"- JSON: {summary['json_file_count']}개",
        f"- Record: {summary['record_count']}개",
        f"- 검증된 참조: {summary['validated_reference_count']}개",
        f"- 미해결 참조: {summary['unresolved_reference_count']}개",
        f"- 중복 ID: {summary['duplicate_id_count']}개",
        "",
        "## 파일 간 주요 연결",
        "",
    ]

    for (source, target), count in edge_counts.most_common():
        lines.append(f"- {source} -> {target} : {count}")

    lines += [
        "",
        "## 미해결 참조",
        "",
        "참조 후보 필드이지만 현재 분석 대상 JSON의 ID inventory에서 대상을 찾지 못한 항목이다.",
        "오류라고 단정하지 않는다.",
        "",
    ]

    for r in unresolved[:500]:
        lines.append(
            f"- {r['source_file']} / {r['source_record_id']} "
            f"{r['field']} -> {r['candidate_id']}"
        )

    lines += ["", "## 중복 ID", ""]
    for item in duplicates[:500]:
        locations = ", ".join(
            f"{x['file']}:{x['path']}" for x in item["locations"]
        )
        lines.append(f"- {item['id']} -> {locations}")

    lines += [
        "",
        "## 해석 주의",
        "",
        "- Python이 JSON 원본에서 기계적으로 추출한 관계다.",
        "- 필드명이 ID처럼 보여도 게임 의미가 확정되는 것은 아니다.",
        "- 배열, 문자열, 중첩 구조의 원본 표현을 최대한 보존한다.",
        "- 다음 단계에서 이 결과를 LLM으로 의미적으로 분류한다.",
        "- Response/API/Research 구조는 이 단계에서 생성하지 않는다.",
    ]

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-root",
        type=Path,
        default=None,
        help="분석할 데이터 루트. 기본값은 이 스크립트의 상위 폴더.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="결과 폴더. 기본값은 데이터_분석/output.",
    )
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    data_root = args.data_root.resolve()
    output_dir = (args.output or script_dir / "output").resolve()

    if not data_root.exists():
        raise SystemExit(
            "[오류] JSON 데이터 경로를 찾을 수 없습니다:\n"
            f"{data_root}\n\n"
            "필요하면 --data-root 옵션으로 경로를 지정하세요."
        )
    output_dir.mkdir(parents=True, exist_ok=True)

    inventory = []
    id_index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    all_refs = []
    parse_errors = []

    json_files = sorted(
        p for p in data_root.rglob("*.json")
        if output_dir not in p.parents
    )

    for path in json_files:
        rel = json_rel(path, data_root)
        try:
            data = load_json(path)
        except Exception as exc:
            parse_errors.append({"file": rel, "error": repr(exc)})
            continue

        records = list(iter_records(data))
        file_info = {
            "file": rel,
            "json_type": type(data).__name__,
            "record_count": len(records),
            "records": [],
        }

        for record_path, record, record_id in records:
            file_info["records"].append({
                "id": record_id,
                "path": record_path,
            })
            id_index[str(record_id)].append({
                "file": rel,
                "path": record_path,
            })
            all_refs.extend(extract_references(record, rel, record_path))

        inventory.append(file_info)

    valid_refs = []
    unresolved_refs = []

    for ref in all_refs:
        matches = id_index.get(str(ref["candidate_id"]), [])
        item = dict(ref)
        item["target_matches"] = matches

        if matches:
            for target in matches:
                valid_refs.append({
                    **{k: ref[k] for k in (
                        "source_file", "source_record_id",
                        "source_path", "field", "raw_value",
                        "candidate_id"
                    )},
                    "target_file": target["file"],
                    "target_path": target["path"],
                })
        else:
            unresolved_refs.append(item)

    duplicate_ids = [
        {"id": key, "locations": locations}
        for key, locations in sorted(id_index.items())
        if len(locations) > 1
    ]

    file_stats = Counter()
    target_stats = Counter()
    field_stats = Counter()

    for ref in valid_refs:
        file_stats[ref["source_file"]] += 1
        target_stats[ref["target_file"]] += 1
        field_stats[ref["field"].split(".")[-1]] += 1

    summary = {
        "data_root": str(data_root),
        "json_file_count": len(json_files),
        "parsed_file_count": len(inventory),
        "parse_error_count": len(parse_errors),
        "record_count": sum(x["record_count"] for x in inventory),
        "unique_id_count": len(id_index),
        "duplicate_id_count": len(duplicate_ids),
        "reference_candidate_count": len(all_refs),
        "validated_reference_count": len(valid_refs),
        "unresolved_reference_count": len(unresolved_refs),
        "top_source_files": file_stats.most_common(30),
        "top_target_files": target_stats.most_common(30),
        "top_reference_fields": field_stats.most_common(50),
    }

    write_json(output_dir / "01_record_inventory.json", {
        "summary": summary,
        "files": inventory,
        "parse_errors": parse_errors,
    })
    write_json(output_dir / "02_reference_graph.json", valid_refs)
    write_json(output_dir / "03_unresolved_references.json", unresolved_refs)
    write_json(output_dir / "04_duplicate_ids.json", duplicate_ids)
    write_json(output_dir / "05_reference_summary.json", summary)
    write_graph_md(
        output_dir / "06_data_graph.md",
        data_root, summary, valid_refs, unresolved_refs, duplicate_ids
    )

    print(f"[완료] JSON 파일: {len(json_files)}")
    print(f"[완료] Record: {summary['record_count']}")
    print(f"[완료] 검증된 참조: {len(valid_refs)}")
    print(f"[확인 필요] 미해결 참조: {len(unresolved_refs)}")
    print(f"[확인 필요] 중복 ID: {len(duplicate_ids)}")
    print(f"[결과] {output_dir}")


if __name__ == "__main__":
    main()
