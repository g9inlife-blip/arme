# 2026-10-02 Bootstrap OpCode=2 Response 계약 초안

## 1. 목적

Local Private Server 구현을 위해 로그인 직후 메인 화면으로 전달되는 Bootstrap `OpCode=2` Response를 **최소 필드가 아니라 현재 관측된 전체 응답 envelope부터 재현하는 방향**으로 정리한다.

메인 화면은 User/Inventory뿐 아니라 Chapter, Hero, Weapon, Equipment, Quest, Shop, Activity 등의 상태를 여러 UI가 공유할 가능성이 있으므로, 현재 단계에서는 필드를 임의로 제거하지 않는다.

## 2. 현재 확정된 통신 경계

```
Login 완료
  ↓
KCPTube.Send
  ↓
OpInfo
  SerialNumber=<request id>
  OpCode=2
  ReturnCode=0
  ↓
KCP response
  ↓
Deserialize<object>
  ↓
NetworkCenter.TryHandleResponse
  ↓
DataCenter.ProccessRequestRes
  ↓
Main State / UI
```

실제 최신 runtime에서 Bootstrap 요청/응답의 SerialNumber가 동일하게 연결되는 것이 확인됐다.

## 3. 관측된 OpInfo Response envelope

현재 runtime에서 확인된 주요 필드:

| Offset | Field | Type | 현재 관측 |
|---|---|---|---|
| +0x88 | User | ProtoUser | non-null |
| +0x90 | Heros | Dictionary<int, ProtoHero> | non-null |
| +0x98 | Items | Dictionary<int, ProtoItem> | non-null, 98개 |
| +0xA0 | Weapons | Dictionary<int, ProtoWeapon> | non-null |
| +0xA8 | Equiments | Dictionary<string, ProtoEquipment> | non-null |
| +0xB0 | Mails | Dictionary<string, ProtoMail> | null |
| +0xC0 | Chapters | Dictionary<int, ProtoChapter> | non-null, 61개 |
| +0xC8 | Sections | Dictionary<int, ProtoSection> | non-null |
| +0xD0 | Teams | Dictionary<int, ProtoTeam> | non-null |
| +0xD8 | ViewItems | List<ProtoViewItem> | null |
| +0xE0 | Fashions | Dictionary<int, ProtoFashion> | non-null |
| +0xE8 | Quests | Dictionary<int, ProtoQuest> | non-null |
| +0xF0 | Shops | Dictionary<int, ProtoShop> | non-null |
| +0xF8 | Charges | Dictionary<int, ProtoCharge> | non-null |
| +0x100 | Friends | Dictionary<long, ProtoFriend> | null |
| +0x108 | Exam | ProtoRank | null |
| +0x118 | Ranks | Dictionary<long, ProtoRank> | null |
| +0x120 | Activities | Dictionary<int, ProtoActivity> | non-null |
| +0x128 | Msgs | List<ProtoMsg> | null |

추가적으로 +0x70 DictI32, +0x78 BattleReslut, +0x80 FC 등의 필드가 존재하며 Bootstrap에서는 null 또는 non-null 여부를 별도로 확인할 필요가 있다.

## 4. 현재 구현 전략

사용자 판단을 반영해 다음 순서로 진행한다.

### Phase A — Full Bootstrap envelope

현재 실기기에서 관측된 Response 구조를 기준으로 Local Server의 첫 응답 계약을 작성한다.

- ReturnCode=0
- OpCode=2
- SerialNumber request correlation
- User
- Heros
- Items
- Weapons
- Equiments
- Chapters
- Sections
- Teams
- Fashions
- Quests
- Shops
- Charges
- Activities
- 기타 OpInfo 필드는 null/empty를 포함해 envelope 형태를 유지

### Phase B — Client 처리 순서 확인

`DataCenter.ProccessRequestRes`에서 실제로 어떤 필드를 읽고 Merge하는지 정적 분석한다.

목표는 다음과 같다.

```
OpInfo field
 ↓
Merge/State mutation
 ↓
DataCenter cache
 ↓
Main UI
```

필드가 Response에 존재하는 것과 Client가 반드시 사용하는 것은 구분한다.

### Phase C — Local Server 연결

Full envelope를 먼저 반환하고 실제 클라이언트에서:

- 로그인 완료
- Main 진입
- User 정보 표시
- 재화 표시
- Hero/Weapon/Equipment 표시
- Chapter/Section 표시
- Quest/Shop/Activity 초기화
- Warehouse 표시

를 순서대로 확인한다.

### Phase D — 최소화

Full envelope가 정상 동작한 뒤에만 필드를 하나씩 제거하면서 실패 지점을 확인한다.

따라서 '절대 최소 Response'는 구현 전에 추측하지 않는다.

## 5. Items는 이미 효과가 확인됨

최신 runtime:

```
Items Dictionary = 98
  ↓
DataCenter.MergeItem
  ↓
DataCenter category cache
  ↓
WareHousePanelMono.InitData
  ↓
List 76 / 10 / 23 / 11
  ↓
ShowGoods
  ↓
ProtoItem UI
```

따라서 Items는 단순 Response 존재 확인을 넘어 실제 Main 이후 UI 상태에 영향을 주는 것이 확정됐다.

## 6. Chapters도 초기 상태 데이터로 유지

Chapters Dictionary는 61개이며:

```
OpInfo +0xC0
 → Dictionary<int, ProtoChapter>
 → ProtoChapter.BoxStatus
 → Chapter UI
```

가 runtime/static 분석으로 연결되어 있다.

따라서 초기 Bootstrap 구현에서 Chapters를 제외하지 않는다.

## 7. 주의사항

- 'non-null'은 '메인 진입 필수'라는 뜻이 아니다.
- 현재 관측값을 그대로 구현하고 이후 테스트로 필수 여부를 좁힌다.
- null인 필드는 임의의 가짜 데이터를 채우지 않는다.
- Items/Chapters처럼 실제 UI 효과가 확인된 필드는 우선 구현 대상으로 취급한다.
- 아이템 이름/Record 전체 복원은 Bootstrap 계약에 필요한 경우에만 추가한다.

## 8. 다음 작업

1. `DataCenter.ProccessRequestRes` Ghidra Listing에서 Response field 처리 순서를 확정
2. Merge 대상별 Client State cache 위치를 정리
3. Local Server가 반환할 Bootstrap JSON/객체 계약 초안 작성
4. KCP Response serializer에 연결할 최소 데이터 구조 설계
5. 실제 Client 연결 테스트

현재 단계에서는 **Full Bootstrap Response → 실제 Client 진입 검증 → 필요 시 최소화** 순서를 적용한다.


## 9. 2026-10-02 Ghidra Listing 재확인 — ProccessRequestRes 본문 부재

Git의 `research/Ghidra_Listing_txt`를 함수명 기준으로 재검색했다.

### 확인
- `DataCenter.ProccessRequestRes @ 016e203c` 자체 Listing 본문은 현재 저장소에 별도 파일로 존재하지 않는다.
- 따라서 현재 단계에서 `ProccessRequestRes` 내부의 정확한 field 처리 순서를 Assembly로 확정할 수 없다.
- 대신 Calls IN/기존 분석으로 다음 merge 함수 주소는 확인된다.

| 대상 | RVA | 현재 근거 |
|---|---:|---|
| ProccessRequestRes | 016e203c | response 진입점, 본문 미확보 |
| MergeEquip | 016e4348 | Bootstrap Equiments 관련 후보 |
| MergeItem | 016e4700 | Items → DataCenter category cache 확정 |
| UpdateHeroInfo | 016e4ba4 | Hero/User 상태 갱신 후보 |
| MergeSections | 016e55dc | Section 상태 merge 관련 |
| MergeSectionSnapShot | 016e5908 | Section snapshot merge 관련 |
| MergeWeapon | 016e5be4 | Weapons 상태 merge 후보 |

### 현재 확정 수준
```
OpInfo.Items
  → ProccessRequestRes
  → MergeItem
  → DataCenter +0x78 category cache
  → Warehouse UI
```

위 Items 경로는 정적+runtime으로 확정했다.

반면 아래는 **응답 field → merge 함수의 직접 호출 순서까지는 미확정**이다.
```
User       → ?
Heros      → UpdateHeroInfo ?
Weapons    → MergeWeapon ?
Equiments  → MergeEquip ?
Sections   → MergeSections / MergeSectionSnapShot ?
Chapters   → ?
Teams      → ?
Fashions   → ?
Quests     → ?
Charges    → ?
Activities → ?
```

따라서 Local Server 구현을 지금 시작할 때는 위 필드들을 제거하지 않고 Full Bootstrap envelope로 유지한다.

### 다음 조사 방향 변경

원본 `ProccessRequestRes` 본문을 억지로 추정하지 않는다. 다음 순서로 실제 계약을 좁힌다.

1. 각 merge 함수의 Listing/인자 타입/field access 확보
2. OpInfo getter(`get_User`, `get_Heros`, `get_Weapons` 등)와 merge 함수의 연결 확인
3. runtime hook에서 merge 함수 호출 여부를 Bootstrap 한 건으로 대조
4. 실제 Client Main 진입을 기준으로 필수 field를 검증

이 단계에서 **Full Bootstrap → Client 검증 → 필요 시 최소화** 원칙은 유지한다.
