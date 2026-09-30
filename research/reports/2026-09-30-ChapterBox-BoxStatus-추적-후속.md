# 2026-09-30 인게임 네트워크 Chapter Box 후속 분석

## 14. Chapter BoxStatus 직접 write 추적 결과

이번 단계에서는 `ProtoChapter.BoxStatus`의 실제 변경 지점을 찾는 것을 우선했다.

### 14.1 setter 자체는 단순 field write

`ProtoChapter$$set_BoxStatus @ 015acf8c`는 다음 한 줄이다.

```text
015acf8c  str w1,[x0, #0x1c]
015acf90  ret
```

즉:

```text
ProtoChapter + 0x1C = BoxStatus
```

가 확정된다.

### 14.2 현재 Listing 인덱스의 한계

현재 GitHub의 Ghidra Listing 검색에서는 `set_BoxStatus`의 Calls IN이 비어 있고, `[x0,#0x1c]` 문자열 검색도 setter/getter 및 다른 unrelated property setter가 주로 반환된다.

따라서 현재 자료만으로는:

```text
어떤 response/merge 함수
    ↓
ProtoChapter.BoxStatus 변경
```

의 직접 caller를 아직 확정할 수 없다.

특히 `DataCenter.ProccessRequestRes @ 016e203c`가 opcode `0x14` 처리 후 setter를 호출한다고 현재 단계에서 단정하면 안 된다.

### 14.3 오히려 확정된 중요한 연결

```text
ChapBoxMono.LayBoxItem @ 00e55c80
BattleMapMono.LayChapterItem @ 00e4f918
BattleSectionMono.SetStageBoxAndBar @ 00e53380
        ↓
ProtoChapter.IsBoxReceived @ 015acfe8
        ↓
BoxStatus & mask
```

이 세 UI 경로가 동일한 `BoxStatus` bitmask를 읽는다.

따라서 수령 여부의 실제 상태 저장값은 UI별 별도 flag가 아니라 `ProtoChapter.BoxStatus`로 보는 것이 확정적이다.

## 15. 다음 추적 방향 변경

직접 setter caller 검색이 막혀 있으므로 다음은 setter가 아니라 **BoxStatus를 입력으로 받는 상태 병합 경로**를 역으로 좁힌다.

우선순위:

1. `MergeSectionSnapShot @ 016e5908`
2. `MergeItem @ 016e4700`
3. `MergeEquip @ 016e4348`
4. `MergeWeapon @ 016e5be4`
5. `DataCenter.ProccessRequestRes @ 016e203c` 주변 호출/분기
6. `ProtoChapter` 객체를 생성/갱신하는 함수 검색

특히 Chapter snapshot 또는 protobuf deserialize 결과에서 `ProtoChapter`의 `+0x1C`가 복사되는 지점을 찾는 것이 핵심이다.

## 16. 현재 Chapter Box 분석 확정/미확정

### 확정

- Chapter reward 데이터는 `ChapterRecord.m_chapterReward`의 threshold → reward ID 구조를 사용한다.
- `ChapBoxMono.TransferChapterData`가 이를 dictionary/list 형태로 분해한다.
- `GetChapterBoxReward`는 opcode `0x14`를 사용한다.
- `ProtoChapter.BoxStatus`는 `+0x1C`이다.
- `IsBoxReceived(mask)`는 `BoxStatus & mask`를 검사한다.
- Box UI들이 이 상태값을 공통 사용한다.

### 미확정

- `LayBoxItem`의 KeyValuePair Key/Value 방향
- reward threshold와 box index의 정확한 매핑
- Box index → BoxStatus bit 위치
- opcode `0x14` response가 `BoxStatus`를 갱신하는 정확한 함수
- 실제 PCAP에서 opcode `0x14` response와 상태 변경의 대응

## 17. 다음 실행 작업

다음 단계에서는 `DataCenter.ProccessRequestRes` 주변의 Chapter/Section 상태 merge를 더 좁히고, 동시에 `ProtoChapter` 관련 함수 목록에서 snapshot/update 계열을 검색한다.

목표는:

```text
GetChapterBoxReward(0x14)
        ↓
TCP response
        ↓
Decrypt / Deserialize
        ↓
OpInfo
        ↓
ProccessRequestRes
        ↓
Chapter state merge
        ↓
ProtoChapter.BoxStatus (+0x1C)
        ↓
IsBoxReceived(mask)
```

까지 직접 연결하는 것이다.

현재 단계에서는 위 chain 중 `0x14 → BoxStatus write` 구간만 미확정으로 유지한다.
