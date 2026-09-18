# Python 분석 스크립트 운영 문서

## 1. 목적

이 문서는 `참고용-unity-behavior-data/데이터_분석/` 아래 Python 분석 스크립트의 역할, 현재 구현 규칙, 실행 방법 및 다음 분석 단계의 기준을 기록한다.

현재 핵심 스크립트:
- `build_data_graph.py`

목표는 Unity MonoBehaviour JSON 원본을 기계적으로 분석하여 Record ID와 Record 간 Reference를 추출하고, 이후 가챠/상점/보상/출석/업적/이벤트 등의 의미 분석에 사용할 기반 데이터를 만드는 것이다.

## 2. 이전 문제와 원인

초기 분석에서 원본 JSON 81개, 약 166MB에 대해 `records.ndjson`은 약 13MB였지만 `references.ndjson`이 약 14.4GB까지 증가했다.

주원인은 Reference 추출 단계의 폭증으로 판단했다.

기존의 넓은 ID 판정 방식:
```python
normalized.endswith("_id") or normalized.endswith("id")
```

이 방식은 `m_itemPackageId`, `m_skillId`, `m_nameId` 등을 Record 자체의 ID처럼 취급할 수 있었다. 또한 `m_id` 자기참조와 중첩 Record의 반복 탐색 가능성이 있었다.

## 3. 현재 Record ID 규칙

Record ID는 다음 키만 인정한다.

```text
id
m_id
_id
recordid
record_id
```

예:
```json
{
  "m_id": 12345,
  "m_itemPackageId": 67890,
  "m_skillId": 11111
}
```

결과:
```text
Record ID
  12345

Reference 후보
  m_itemPackageId -> 67890
  m_skillId       -> 11111
```

## 4. Reference 추출 규칙

Reference 후보는 Record ID 규칙과 별도로 판단한다.

대표적인 후보:
- `m_itemPackageId`
- `m_skillId`
- `m_actorId`
- `m_rewardId`
- `m_shopId`
- `m_stageId`
- `m_eventId`
- `m_characterId`
- `m_equipmentId`

Reference 후보라고 해서 게임 의미가 확정되는 것은 아니다. 실제 ID inventory와 대조하여 검증된 Reference와 미해결 Reference로 분리한다.

## 5. Reference에서 제외하는 필드

Unity/직렬화 메타데이터 및 Record 자기 ID는 Reference로 취급하지 않는다.

```text
id
m_id
_id
recordid
record_id
fileid
m_fileid
pathid
m_pathid
```

특히 `m_id -> 자기 자신` 같은 Reference가 대량 생성되지 않도록 한다.

## 6. 중첩 Record 처리

중첩 객체가 실제 Record ID를 가지고 있으면 별도의 Record 경계로 본다.

부모 Record 분석에서 자식 Record 내부까지 다시 Reference를 탐색하지 않는다. 이를 통해 동일 Reference가 부모/자식 탐색 과정에서 반복 생성되는 것을 방지한다.

## 7. 중복 Reference 방지

동일 Record에서 동일한 field path, candidate ID, raw value 조합이 반복되면 중복 Reference로 기록하지 않는다.

Reference 결과는 NDJSON으로 순차 기록하여 전체 데이터를 메모리에 누적하지 않는다.

## 8. 폭증 방지 안전장치

Record 하나에서 기본적으로 100,000 Reference를 초과하면 중단한다.

실행 시:
```bash
python build_data_graph.py --max-refs-per-record 50000
```

하나의 JSON 파일에서 2,000,000 Reference를 초과하면 파일 단위 폭증으로 판단하여 중단한다.

목적은 잘못된 로직으로 `references.ndjson`이 수 GB 이상 증가하는 상황을 즉시 차단하는 것이다.

## 9. 출력 구조

기본 결과:
```text
데이터_분석/output/
```

작업용:
```text
output/_work/records.ndjson
output/_work/references.ndjson
output/_work/unresolved.ndjson
output/_work/parse_errors.ndjson
```

주요 결과:
```text
01_record_inventory.json
04_duplicate_ids.json
05_reference_summary.json
06_data_graph.md
```

### records.ndjson
Record ID, 원본 파일, JSON path를 저장한다.

### references.ndjson
ID inventory에서 실제 대상을 찾은 Reference를 저장한다.

### unresolved.ndjson
Reference 후보이지만 현재 ID inventory에서 대상을 찾지 못한 항목을 저장한다. 미해결이라고 해서 반드시 오류는 아니다.

### parse_errors.ndjson
JSON 파싱 실패 파일을 기록한다.

## 10. 실행 방법

데이터 경로 지정:
```bash
python build_data_graph.py --data-root "JSON_데이터_경로"
```

출력 경로 지정:
```bash
python build_data_graph.py --data-root "JSON_데이터_경로" --output "결과_경로"
```

처음에는 기본 제한값으로 실행한다.

## 11. 이번 재분석 원칙

기존 14GB 수준의 `references.ndjson`은 정상 결과로 간주하지 않는다.

수정된 스크립트로 81개 JSON을 처음부터 다시 분석한다. 기존 결과에 이어서 append하지 않는다.

분석 시작 전 기존 `output/_work/` 결과를 별도 보관하거나 삭제하고 새 결과를 생성한다.

확인 항목:
```text
JSON 파일 수       = 81개
parse_errors       = 0 또는 실제 오류만 존재
records             = 기존 약 13MB와 유사한 규모
references          = 기존 14.4GB보다 크게 감소해야 함
unresolved          = 별도 검토
```

Reference 수가 다시 비정상적으로 증가하면 즉시 중단하고 특정 파일/필드 발생량을 조사한다.

## 12. 다음 분석 단계

Reference 그래프가 정상적으로 생성된 후 다음 영역을 우선 분석한다.

1. DrawRecord
2. DrawpreviewRecord
3. ItemPackage
4. ShopRecord
5. Reward 관련 Record
6. Daily Login / 출석 보상
7. Achievement / 업적
8. Event / 기간 이벤트
9. Limited Draw / 한정 가챠
10. 일반 상점 및 패키지
11. 캐릭터/장비/스킬
12. 스테이지/몬스터/보스
13. 재화 및 소비 구조

가챠 분석에서는 단일 Record만 보지 않고 Reference를 따라가야 한다.

```text
DrawRecord
   |
   +-- DrawpreviewRecord
   |
   +-- ItemPackage
          |
          +-- Item
          |
          +-- Reward
   |
   +-- 확률/등급/Pool 정보
```

최종적으로 가챠 목록, 일반/한정 여부, 기간, 비용, 확률표, 등급별 Pool, 획득 아이템, 패키지 구성, 상점 가격 및 보상 구조를 재구성한다.

## 13. 중요한 분석 원칙

Python 단계에서는 의미를 임의로 확정하지 않는다.

예를 들어 `m_rewardId`가 있다고 해서 무조건 게임상 '보상 ID'라고 확정하지 않는다.

Python은 필드명, 값, 원본 위치, Reference 대상 등 사실 데이터를 정확하게 보존한다. 게임 의미는 연결된 Record를 확인한 뒤 판단한다.

## 14. 현재 기준 파일

```text
참고용-unity-behavior-data/
└─ 데이터_분석/
   ├─ README.md
   ├─ build_data_graph.py
   └─ PYTHON_ANALYSIS.md
```

Python 스크립트를 변경할 경우 이 문서의 규칙과 실제 코드가 일치하도록 유지한다.
