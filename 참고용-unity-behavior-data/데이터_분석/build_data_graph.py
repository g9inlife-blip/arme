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
    r"(?P<id>[A-Za-z0-9_:.\\-]+)\s*[xX*]\s*(?P<count>\d+)"
)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def safe_load_json(path: Path, parse_errors: list[dict[str, str]]) -> Any | None:
    try:
        return load_json(path)
    except Exception as exc:
        parse_errors.append({
            "file": str(path),
            "error_type": type(exc).__name__,
            "error": str(exc),
        })
        return None




def decode_obscured_int(value: Any) -> int | None:
    """Unity ObscuredInt 형태(currentCryptoKey/hiddenValue)를 복원한다."""
    if not isinstance(value, dict):
        return None
    if "hiddenValue" not in value or "currentCryptoKey" not in value:
        return None
    hidden = value.get("hiddenValue")
    key = value.get("currentCryptoKey")
    if isinstance(hidden, int) and isinstance(key, int):
        return hidden ^ key
    return None

def is_id_key(key: str) -> bool:
    normalized = key.lower()
    return normalized in ID_KEYS or normalized.endswith("_id") or normalized.endswith("id")


def looks_like_reference_key(key: str) -> bool:
    return bool(REFERENCE_KEY_RE.search(key))


def scalar_candidates(value: Any) -> list[str]:
    if value is None or isinstance(value, bool):
        return []

    decoded = decode_obscured_int(value)
    if decoded is not None:
        return [str(decoded)]

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


def append_jsonl(handle, obj: Any):
    handle.write(json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n")


def read_jsonl_ids(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=None,
                        help="분석할 데이터 루트. 기본값은 로컬 Unity JSON 경로.")
    parser.add_argument("--output", type=Path, default=None,
                        help="결과 폴더. 기본값은 데이터_분석/output.")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    data_root = (args.data_root or DEFAULT_DATA_ROOT).resolve()
    output_dir = (args.output or script_dir / "output").resolve()

    if not data_root.exists():
        raise SystemExit(
            "[오류] JSON 데이터 경로를 찾을 수 없습니다:\n"
            f"{data_root}\n\n"
            "필요하면 --data-root 옵션으로 경로를 지정하세요."
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    work_dir = output_dir / "_work"
    work_dir.mkdir(parents=True, exist_ok=True)

    json_files = sorted(data_root.rglob("*.json"))
    json_files = [p for p in json_files if output_dir not in p.parents]

    record_file = work_dir / "records.ndjson"
    ref_file = work_dir / "references.ndjson"
    unresolved_file = work_dir / "unresolved.ndjson"
    parse_error_file = work_dir / "parse_errors.ndjson"

    record_count = 0
    parse_error_count = 0
    file_inventory = []

    print(f"[시작] JSON 파일: {len(json_files)}")
    print(f"[경로] {data_root}")
    print("[1/2] Record ID 추출 중...")

    with record_file.open("w", encoding="utf-8") as records_out, \
         parse_error_file.open("w", encoding="utf-8") as errors_out:
        for index, path in enumerate(json_files, 1):
            rel = json_rel(path, data_root)
            local_errors = []
            data = safe_load_json(path, local_errors)
            if data is None:
                parse_error_count += len(local_errors)
                for err in local_errors:
                    append_jsonl(errors_out, err)
                print(f"[{index}/{len(json_files)}] SKIP {rel} (JSON 오류)")
                continue

            records = 0
            for record_path, record, record_id in iter_records(data):
                append_jsonl(records_out, {
                    "id": str(record_id),
                    "file": rel,
                    "path": record_path,
                })
                records += 1
                record_count += 1

            file_inventory.append({
                "file": rel,
                "json_type": type(data).__name__,
                "record_count": records,
            })
            print(f"[{index}/{len(json_files)}] {rel} | Record {records}")
            del data

    id_index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in read_jsonl_ids(record_file):
        id_index[item["id"]].append({
            "file": item["file"],
            "path": item["path"],
        })

    duplicate_ids = [
        {"id": key, "locations": locations}
        for key, locations in sorted(id_index.items())
        if len(locations) > 1
    ]

    print(f"[중간] 고유 ID: {len(id_index)} / 중복 ID: {len(duplicate_ids)}")
    print("[2/2] 참조 추출 및 검증 중...")

    valid_count = 0
    unresolved_count = 0
    field_stats = Counter()
    source_stats = Counter()
    target_stats = Counter()

    with ref_file.open("w", encoding="utf-8") as refs_out, \
         unresolved_file.open("w", encoding="utf-8") as unresolved_out, \
         parse_error_file.open("a", encoding="utf-8") as errors_out:
        for index, path in enumerate(json_files, 1):
            rel = json_rel(path, data_root)
            local_errors = []
            data = safe_load_json(path, local_errors)

            if data is None:
                parse_error_count += len(local_errors)
                for err in local_errors:
                    append_jsonl(errors_out, err)
                continue

            file_refs = 0
            file_valid = 0
            file_unresolved = 0

            for record_path, record, record_id in iter_records(data):
                for ref in extract_references(record, rel, record_path):
                    file_refs += 1
                    matches = id_index.get(str(ref["candidate_id"]), [])

                    if matches:
                        for target in matches:
                            append_jsonl(refs_out, {
                                **ref,
                                "target_file": target["file"],
                                "target_path": target["path"],
                            })
                            valid_count += 1
                            file_valid += 1
                            source_stats[rel] += 1
                            target_stats[target["file"]] += 1
                            field_stats[ref["field"].split(".")[-1]] += 1
                    else:
                        append_jsonl(unresolved_out, {
                            **ref,
                            "target_matches": [],
                        })
                        unresolved_count += 1
                        file_unresolved += 1

            print(f"[{index}/{len(json_files)}] {rel} | Ref {file_refs} / OK {file_valid} / 미해결 {file_unresolved}")
            del data

    summary = {
        "data_root": str(data_root),
        "json_file_count": len(json_files),
        "parsed_file_count": len(file_inventory),
        "parse_error_count": parse_error_count,
        "record_count": record_count,
        "unique_id_count": len(id_index),
        "duplicate_id_count": len(duplicate_ids),
        "reference_candidate_count": valid_count + unresolved_count,
        "validated_reference_count": valid_count,
        "unresolved_reference_count": unresolved_count,
        "top_source_files": source_stats.most_common(30),
        "top_target_files": target_stats.most_common(30),
        "top_reference_fields": field_stats.most_common(50),
    }

    write_json(output_dir / "04_duplicate_ids.json", duplicate_ids)
    write_json(output_dir / "05_reference_summary.json", summary)

    with (output_dir / "01_record_inventory.json").open("w", encoding="utf-8") as f:
        json.dump({
            "summary": summary,
            "files": file_inventory,
            "record_data_file": str(record_file),
            "reference_data_file": str(ref_file),
            "unresolved_data_file": str(unresolved_file),
            "parse_errors_file": str(parse_error_file),
        }, f, ensure_ascii=False, indent=2)

    graph_md = output_dir / "06_data_graph.md"
    lines = [
        "# 실제 데이터 참조 그래프 분석 결과", "",
        f"- 분석 대상: {data_root}",
        f"- JSON: {summary['json_file_count']}개",
        f"- Record: {summary['record_count']}개",
        f"- 고유 ID: {summary['unique_id_count']}개",
        f"- 검증된 참조: {summary['validated_reference_count']}개",
        f"- 미해결 참조: {summary['unresolved_reference_count']}개",
        f"- 중복 ID: {summary['duplicate_id_count']}개",
        f"- JSON 파싱 오류: {summary['parse_error_count']}개", "",
        "## 대용량 원본 결과", "",
        "- _work/records.ndjson: Record ID 목록",
        "- _work/references.ndjson: 검증된 참조",
        "- _work/unresolved.ndjson: 미해결 참조",
        "- _work/parse_errors.ndjson: 파일별 파싱 오류", "",
        "## 주요 참조 필드", "",
    ]
    for field, count in field_stats.most_common(50):
        lines.append(f"- {field} : {count}")

    lines += ["", "## 주요 출발 파일", ""]
    for file_name, count in source_stats.most_common(30):
        lines.append(f"- {file_name} : {count}")

    lines += ["", "## 주요 대상 파일", ""]
    for file_name, count in target_stats.most_common(30):
        lines.append(f"- {file_name} : {count}")

    lines += [
        "", "## 해석 주의", "",
        "- Python은 JSON 원본에서 기계적으로 ID와 참조를 추출한다.",
        "- 대용량 참조는 메모리에 누적하지 않고 NDJSON 파일에 순차 기록한다.",
        "- 필드명이 ID처럼 보여도 게임 의미가 확정되는 것은 아니다.",
        "- Response/API/Research 구조는 이 단계에서 생성하지 않는다.",
    ]
    graph_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("")
    print("[완료]")
    print(f"  JSON: {len(json_files)}")
    print(f"  Record: {record_count}")
    print(f"  고유 ID: {len(id_index)}")
    print(f"  검증된 참조: {valid_count}")
    print(f"  미해결 참조: {unresolved_count}")
    print(f"  중복 ID: {len(duplicate_ids)}")
    print(f"  JSON 오류: {parse_error_count}")
    print(f"[결과] {output_dir}")


if __name__ == "__main__":
    main()
