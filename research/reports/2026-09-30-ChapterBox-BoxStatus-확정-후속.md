# 2026-09-30 Chapter BoxStatus 확정 후속 분석

## 1. 신규 PCAP 3세트 결과
Git에 추가된 3개 Box 실험의 복호화 결과를 기준으로 BoxStatus 의미를 재검증했다.

| 실험 | boxIndex | 오픈 결과 | response f4 |
|---|---:|---|---:|
| box1 | 0 | 첫 번째 Box 오픈 | 1 (0b001) |
| box3 | 2 | 1번 + 3번 오픈, 2번 미오픈 | 5 (0b101) |
| box2 | 1 | 1번 + 2번 + 3번 오픈 | 7 (0b111) |

핵심 증거는 box3 실험이다. 2개 Box가 오픈된 상태에서 f4가 2가 아니라 5 (101b)이다. 따라서 f4는 단순 개수(count)가 아니라 각 Box의 획득 여부를 나타내는 bitmask로 확정한다.

매핑: boxIndex 0 → bit 0 → 0x01 / boxIndex 1 → bit 1 → 0x02 / boxIndex 2 → bit 2 → 0x04

누적 상태: 1번 오픈 = 001b = 0x01 / 1+3번 오픈 = 101b = 0x05 / 1+2+3번 오픈 = 111b = 0x07

## 2. f7(boxIndex)와 f4(BoxStatus) 관계
신규 PCAP에서 0x14 요청의 f7은 0-based Box index로 확인된다. f7=0은 첫 번째, f7=1은 두 번째, f7=2는 세 번째 Box이다. protobuf varint의 default value가 0이므로 f7=0은 직렬화 시 생략될 수 있다.

## 3. 정적 분석과 교차검증
ProtoChapter$$IsBoxReceived @ 015acfe8는 +0x1C를 읽고 mask와 AND 검사한다. 즉 (BoxStatus & mask) != 0 이 실제 구현이다.
ProtoChapter$$get_BoxStatus @ 015acf84는 +0x1C를 읽고, ProtoChapter$$set_BoxStatus @ 015acf8c는 +0x1C에 쓴다. 따라서 ProtoChapter + 0x1C = BoxStatus는 확정이다.

이번 PCAP의 f4=1 → 5 → 7과 UI의 bit 검사 방식이 실제 Box 획득 순서와 정확히 대응한다.

## 4. 기존 boxIndex=5 사례의 의미 수정
기존 캡처의 chapterId=20000100, boxIndex=5는 이번 3개 Box 실험에서 확립된 실제 Box index 0~2와 직접 대응시키는 근거로 사용하지 않는다.
UI의 1 << boxIndex 계산 자체는 맞지만, 해당 요청의 f7=5가 실제 3개 Chapter Box 중 하나였다는 해석은 보류한다.

## 5. 현재 확정된 전체 관계
Box UI index → 0-based boxIndex → GetChapterBoxReward(chapterId, boxIndex) → opcode 0x14 → server → Chapter snapshot f4 → ProtoChapter.BoxStatus (+0x1C) → IsBoxReceived(1 << boxIndex)

PCAP 복호화와 Ghidra 정적 분석이 서로 독립적으로 같은 관계를 가리킨다.

## 6. 아직 남은 정적 분석 과제
BoxStatus의 의미 자체는 더 이상 미확정으로 두지 않는다. 남은 것은 데이터가 실제 메모리 객체에 들어가는 코드 경로다.

확정: ProtoChapter +0x1C = BoxStatus / IsBoxReceived = (BoxStatus & mask) != 0 / mask = 1 << boxIndex / 0x14 request에 chapterId + boxIndex 전달 / 신규 PCAP에서 f4가 Box 획득 bitmask로 동작 / f7은 0-based boxIndex

미확정: 0x14 response → protobuf Deserialize → OpInfo.Chapters (+0xC0) → ProtoChapter object → +0x1C BoxStatus write

ProtoChapter getter/setter의 직접 caller는 현재 Listing index에서 확인되지 않는다. ProccessRequestRes @ 016e203c의 확보된 구간에서는 OpInfo +0x98 Items, +0xA0 Weapons, +0xA8 Equipments, +0xC8 Sections 접근은 확인되지만 +0xC0 Chapters 직접 접근은 아직 확인되지 않았다.

## 7. 다음 우선순위
1. 017cec0c ProtoBuf.Serializer.Deserialize<object>의 Calls OUT 확인
2. ProtoBuf metadata에서 ProtoChapter 타입/field population 연결 확인
3. BattleMapMono.InitChapters @ 00e4e080 주변 FUN_00E* helper 확보
4. BattleMapMono.LayChapterItem @ 00e4f918 실제 Listing 확보 여부 확인
5. Chapter Id와 ProtoChapter 객체를 연결하는 collection/cache 확인
6. 필요하면 runtime에서 get_BoxStatus/set_BoxStatus를 hook하여 실제 object 주소와 값 변화 확인

## 8. 현재 결론
f4 = ProtoChapter.BoxStatus bitmask는 확정한다.
특히 신규 box3 캡처의 f4=5 (101b)가 결정적인 교차검증이다.
이제 분석 목표는 f4의 의미가 아니라 0x14 response의 Chapter snapshot이 ProtoChapter +0x1C에 저장되는 실제 코드 경로를 찾는 것이다.