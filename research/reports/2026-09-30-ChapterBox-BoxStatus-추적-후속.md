# 2026-09-30 인게임 네트워크 Chapter Box 후속 분석

## 14. Chapter BoxStatus 직접 write 추적 결과

이번 단계에서는 `ProtoChapter.BoxStatus`의 실제 변경 지점을 찾는 것을 우선했다.

### 14.1 setter 자체는 단순 field write

`ProtoChapter$$set_BoxStatus @ 015acf8c`:

```text
015acf8c  str w1,[x0, #0x1c]
015acf90  ret
```

즉 `ProtoChapter + 0x1C = BoxStatus`가 확정된다.

### 14.2 setter caller는 현재 Listing에서 직접 확보되지 않음

GitHub Ghidra Listing 검색에서는 `set_BoxStatus`의 Calls IN이 비어 있다. 따라서 현재 자료만으로 특정 response/merge 함수가 setter를 직접 호출한다고 단정할 수 없다.

특히 `DataCenter.ProccessRequestRes @ 016e203c`가 opcode `0x14` 처리 후 `set_BoxStatus`를 호출한다고 아직 확정하지 않는다.

### 14.3 BoxStatus 읽기 경로는 확정

```text
ChapBoxMono.LayBoxItem @ 00e55c80
BattleMapMono.LayChapterItem @ 00e4f918
BattleSectionMono.SetStageBoxAndBar @ 00e53380
        ↓
ProtoChapter.IsBoxReceived @ 015acfe8
        ↓
BoxStatus & mask
```

Chapter Box UI와 Section Box UI가 동일한 `BoxStatus` bitmask를 사용한다.

## 15. Chapter 상태 merge 후보 재추적

### 15.1 MergeSectionSnapShot

`DataCenter.MergeSectionSnapShot @ 016e5908`는 실제 함수 주소가 여러 Listing의 Calls IN에서 확인되지만, 현재 저장소에는 이 함수의 독립 Function Listing 본문이 없다.

따라서 현재 확인 가능한 것은 **함수 존재 및 DataManager 관련 참조**까지이며, 내부에서 `ProtoChapter +0x1C`를 쓰는지는 미확정이다.

### 15.2 MergeSections

`DataCenter.MergeSections @ 016e55dc`도 존재가 확인된다.

검색 결과에서는 `Dictionary<int, object>` 계열 입력을 순회하는 구조라는 기존 분석 기록이 있으나, 현재 검색 결과만으로 `ProtoChapter.BoxStatus`와 직접 연결되는 field write는 확인되지 않았다.

따라서:

```text
GetSections(0x13)
 → MergeSections
 → ProtoChapter
```

의 전체 연결은 아직 가설 단계로 유지한다.

### 15.3 MergeItem / MergeEquip / MergeWeapon

다음 함수들의 존재 및 DataManager 관계는 확인된다.

```text
MergeItem  @ 016e4700
MergeEquip @ 016e4348
MergeWeapon @ 016e5be4
```

하지만 현재 Listing 인덱스에는 독립 본문이 없어 Chapter BoxStatus와의 직접 관계는 확인되지 않았다.

특히 `MergeItem`은 Chapter Box 수령 후 실제 아이템 보상이 추가되는 경로와 연결될 가능성은 있으나, 현재 증거만으로 opcode `0x14`의 보상 처리 함수라고 확정하지 않는다.

## 16. ProccessRequestRes 주변의 현재 결론

`NetworkCenter.TryHandleResponse @ 015b41e0`에서:

```text
Request.SetResponse(OpInfo)
        ↓
callback
        ↓
DataCenter.ProccessRequestRes @ 016e203c
```

호출은 확정되어 있다.

그러나 `ProccessRequestRes`의 독립 Listing 본문이 현재 저장소에 없기 때문에 opcode `0x14` 분기와 `BoxStatus` 갱신을 직접 확인하지 못했다.

따라서 현재 가장 안전한 모델은:

```text
GetChapterBoxReward
  opcode 0x14
        ↓
NetworkCenter / TCPTube
        ↓
Deserialize → OpInfo
        ↓
ProccessRequestRes
        ↓
[Chapter state merge 지점 미확정]
        ↓
ProtoChapter.BoxStatus +0x1C
```

이다.

## 17. 추가로 확인된 Section 상태 경로

`GetSections @ 00ddea78`는 opcode `0x13`이고 u32 인자 1개를 전달한다.

현재 `MergeSections @ 016e55dc`가 별도로 존재하므로 Section 목록 응답을 DataCenter 상태로 병합하는 후보로 볼 수 있다.

다만 `MergeSections`와 `MergeSectionSnapShot` 중 어느 것이 특정 response opcode를 처리하는지는 현재 증거만으로 결정하지 않는다.

## 18. 다음 작업

다음 단계는 함수 이름 추정이 아니라 **ProtoChapter 타입/필드 자체를 역으로 추적**한다.

우선순위:

1. `ProtoChapter` 생성자/초기화 함수 검색
2. `ProtoChapter.Id/Status/Progress/BoxStatus` setter의 Calls IN 비교
3. `set_Progress`, `set_Status`, `set_Id`가 같은 함수에서 연속 호출되는지 검색
4. 그 함수가 `MergeSections`, `MergeSectionSnapShot`, `ProccessRequestRes`와 연결되는지 확인
5. 가능하면 원본 Ghidra Listing에서 `str w?,[x?,#0x1c]` 직접 검색
6. 마지막으로 opcode `0x14` response와 BoxStatus bit 변경을 PCAP/runtime에서 검증

현재는 `0x14 → BoxStatus`를 아직 미확정으로 유지한다.
