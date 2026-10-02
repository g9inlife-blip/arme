# 2026-10-02 Bootstrap 응답 → Client State → Main UI 연결 분석

## 1. 분석 기준과 현재 상태

서버 구현 진행과 분리해, 클라이언트가 실제 Bootstrap 응답을 어떤 객체와 cache로 바꾸고 어느 UI에서 소비하는지 연결한다.

- 기준 응답: `research/PCAP/로그인_출석_퀘스트_우편_토벌_던전_상자_무기제작_강화_kcp/plaintext/000192_s2c.bin`
- 기준 runtime: `research/reports/Log/frida_log_static_신규로갱신되므로기존데이터없이최종본만.txt`
- 기준 정적 분석: `research/Ghidra_Listing_txt/DA.txt`
- 성공 기준선: 운영 Bootstrap Replay로 Main 진입, Gold surgical patch로 999,999 표시 성공(서버 진행상황 문서 기준).

주의: OpInfo 메모리 offset(+0x70, +0x88 등)과 protobuf field 번호(21, 35 등)는 서로 다른 체계다. 아래 연결은 실측 payload와 Ghidra/runtime 근거를 합친 것이다.

## 2. Bootstrap wire field → OpInfo → Client State

| Protobuf field | OpInfo member / offset | 처리 경로 | 현재 연결 상태 |
|---:|---|---|---|
| 21 | DictI32 / +0x70 | UserInfo.MergeVaryData → DataCenter.UserInfo(+0x28) | 정적 Listing으로 확정 |
| 35 | User / +0x88 | UserInfo.ctor → DataCenter(+0x28) | 정적 Listing으로 확정 |
| 37 | Heros / +0x90 | UpdateHeroInfo → HeroInfo.InitHero → FinalUpgradeHero / UpdateAIStrategy | 정적 Listing으로 확정 |
| 38 | Items / +0x98 | MergeItem → DataCenter item category cache(+0x78 계열) | 정적+runtime 확정 |
| 39 | Weapons / +0xA0 | MergeWeapon(상위) → cache(+0x40) | 정적 확정 |
| 40 | Equiments / +0xA8 | MergeEquip → cache(+0x38) | 정적 확정 |
| 43 | Chapters / +0xC0 | generic Merge → cache(+0x48) | 정적 확정 |
| 44 | Sections / +0xC8 | MergeSections → cache(+0x50) | 정적 확정 |
| 45 | Teams / +0xD0 | generic Merge → cache(+0x58) | 정적 확정 |
| 48 | ViewItems 후보 / +0xD8 | 직접 병합 cache 미확정 | 후보 |
| 49 | Fashions 후보 / +0xE0 | 직접 병합 cache 미확정 | 후보 |
| 51 | Quests 후보 / +0xE8 | generic Merge → cache(+0x80) | 정적 연결 |
| 56 | Activities / +0x120 | 실제 ProtoActivity signature와 일치 | payload 타입 연결, 소비처 추가 확인 필요 |

추가로 +0xB0 Mails → cache(+0x88), +0xF0 Shops → cache(+0x68), +0xF8 Charges → cache(+0x70) 처리가 Listing에 존재한다. 다만 이 운영 캡처에서 해당 field의 serialized occurrence가 확인되지 않는 항목은 기본 dictionary 생성 여부와 구분한다.

## 3. 핵심 연결 A — User 기본 정보와 vary data는 별도 입력

```
field 35 User
  → OpInfo +0x88
  → UserInfo.ctor
  → DataCenter +0x28
      ├─ Id / Name
      └─ 기본 User 정보

field 21 DictI32
  → OpInfo +0x70
  → UserInfo.MergeVaryData
  → 동일 UserInfo 갱신
      ├─ Level / Exp
      ├─ EquipMax
      ├─ FCTimes
      ├─ SignInDays / SignInRewardDay
      ├─ StepId
      └─ 기타 vary key
```

UserInfoPanelMono.Start는 UserInfo의 Id, Name, Level, Exp getter를 직접 읽는다. 따라서 User 필드만 분석해서 Level/Exp를 모두 설명하면 안 된다. field 21의 vary data까지 함께 봐야 한다.

## 4. 핵심 연결 B — Items와 재화 표시

```
field 38 Items
  → OpInfo +0x98
  → DataCenter.MergeItem
  → BaseData.type별 item category cache(+0x78 계열)
      ├─ WareHousePanelMono.InitData → 창고 List/UI
      └─ DataCenter.GetXCount(itemId)
           ├─ UserInfo.get_Coins    (43000001)
           ├─ UserInfo.get_Crystals (43000002)
           └─ UserInfo.get_Energy   (43000003)
```

- MergeItem runtime 입력 Dictionary는 98개로 관측됐다.
- MergeItem은 BaseData를 조회하고 type 분류를 수행한다.
- GetXCount도 BaseData.type을 기준으로 수량 조회 경로를 분기한다.
- Coins/Crystals/Energy getter는 UserInfo 고정 수치가 아니라 GetXCount를 호출한다.
- 서버 진행상황 문서의 Gold 변경 성공은 field 38의 currency entry 중 ID 43000001의 nested field 3(amount)을 변경한 결과다. 즉 이 변경은 Client의 Items → MergeItem/GetXCount → 재화 UI 경로와 연결되는 것으로 해석된다.

field 38의 entry는 map key/value 외에 ProtoItem 내부 값이 있으므로, 단순히 map key만 바꾸는 것과 실제 표시 수량을 바꾸는 것은 다르다. 정확한 테스트 시에는 ID와 amount가 함께 일치하는지 확인한다.

## 5. 핵심 연결 C — Hero와 무기

```
field 37 Heros
  → OpInfo +0x90
  → DataCenter.UpdateHeroInfo
  → HeroInfo.InitHero
  → FinalUpgradeHero
  → UpdateAIStrategy
  → HeroInfo state

field 39 Weapons
  → OpInfo +0xA0
  → MergeWeapon @ 016e414c
  → DataCenter cache +0x40
  → HeroInfo.get_Weapon / get_WeaponInfomation
  → HeroPartEquipMono.RefreshWeapon / Weapon UI
```

runtime에서 ProtoHero → HeroInfo 변환이 관측됐다. ProtoHero의 Id/Level/Exp/Star/Weapon/FashionId/Stigmata ID 등이 HeroInfo 생성에 입력되고, HeroInfo에는 WeaponInfomation 객체가 생성된다.

확인된 HeroInfo 소비 함수:
- get_Weapon
- get_WeaponInfomation
- HeroPartEquipMono.RefreshWeapon
- WeaponPanelMono.Init / RefreshWeaponInfoBoard

단, 각 화면이 DataCenter +0x40을 직접 읽는 offset-level 연결은 아직 미확정이다.

## 6. 핵심 연결 D — Equipment / Chapter / Section

### Equipment

```
field 40 Equiments
  → OpInfo +0xA8
  → MergeEquip
  → DataCenter cache +0x38
  → EquipMax 계열 getter
  → HomePanelMono.Start / Warehouse 계열
```

HomePanelMono.Start가 EquipMax, NextEquipMax, CurrentEquipMax 계열 getter를 호출한다. 따라서 Equipment 응답은 단순 상세 메뉴 전용으로 볼 수 없다. 단, 각 getter와 cache +0x38의 직접 1:1 연결은 추가 Listing 확인 대상이다.

### Chapter

```
field 43 Chapters
  → OpInfo +0xC0
  → generic Merge
  → DataCenter cache +0x48
  → BattleMapMono.LayChapterItem
  → ProtoChapter / Chapter UI
```

runtime Chapter Dictionary 61개와 ProtoChapter.BoxStatus가 확인됐다. ProtoChapter의 +0x10 Id, +0x14 Status, +0x18 Progress, +0x1C BoxStatus를 소비한다.

### Section과 Section snapshot

```
field 44 Sections
  → OpInfo +0xC8
  → MergeSections
  → DataCenter cache +0x50

Section snapshot
  → MergeSectionSnapShot
  → DataCenter +0x90 (Dictionary<int,int>)
  → IsSectionClear
```

Section collection과 Section snapshot은 별도 상태다. DataCenter +0x90을 ProtoChapter.BoxStatus와 혼동하지 않는다.

## 7. 현재 Main UI 연결 요약

| 화면/소비처 | 읽는 상태 | 증거 수준 |
|---|---|---|
| UserInfoPanelMono.Start | UserInfo Id/Name/Level/Exp | 정적 Listing |
| HomePanelMono.Start | EquipMax 계열, Hero 관련 상태 등 | 정적 호출 관계 |
| HomePanelMono.RefreshUIBanner | Main 배너/활동 상태 후보 | 함수 진입 runtime 확인, 개별 field 매핑 미확정 |
| HomePanelMono.RefreshWareHouse_Supply | Warehouse/Item 관련 상태 | 함수 진입 runtime 확인 |
| WareHousePanelMono.InitData | MergeItem category cache | 정적+runtime |
| BattleMapMono.LayChapterItem | Chapters / ProtoChapter | 정적 |
| HeroPartEquipMono.RefreshWeapon | HeroInfo WeaponInformation | 정적 |

Main 진입 성공은 전체 UI 데이터가 모두 완전히 연결됐다는 뜻은 아니다. 각 데이터가 response에 존재하는 것, DataCenter에 병합되는 것, UI가 실제 읽는 것은 별도 증거로 유지한다.

## 8. 다음 클라이언트 분석 순서

1. **Currency chain 마무리**: field 38 → MergeItem → GetXCount의 BaseData.type별 실제 bucket을 연결하고, 재화 UI가 어느 시점에 getter를 호출하는지 정리한다.
2. **UserInfo vary data 검증**: field 21의 실제 key/value와 UserInfo.MergeVaryData의 key 분기를 대조해 Level/Exp/EquipMax 등 표시값의 출처를 확정한다.
3. **Hero main 소비처**: HeroInfo.InitHero 결과 중 HomePanelMono.Start가 실제 접근하는 getter만 추려 field 37의 필수 속성을 정리한다.
4. **Weapon/Equipment 직접 cache 소비**: cache +0x40/+0x38의 getter 및 UI 호출자를 연결한다.
5. **Chapter/Section UI 경계**: Chapter UI와 Section snapshot의 별도 state가 어떤 화면/요청에 쓰이는지 연결한다.
6. **나머지 응답 그룹**: field 49/51/56(Fashions/Quests/Activities) 및 Shops/Charges/Mails는 Main UI에서 실제 소비가 확인되는 항목만 추가 추적한다.

## 9. 분석 범위 원칙

- 서버 raw payload 생성/수정은 별도 작업 흐름에서 담당한다.
- 본 분석은 Client의 Deserialize 이후 처리, State cache, UI 소비처 연결에 집중한다.
- 운영 데이터의 인증/세션/기기 식별값은 재현용 문서에 복사하지 않는다.
- 각 연결은 CONFIRMED / STATIC / RUNTIME / CANDIDATE로 구분하고, 추정 매핑을 확정처럼 쓰지 않는다.
- Main 화면 진입이 성공한 현재는 KCP/암복호화 재분석을 반복하지 않는다. 클라이언트에서 막히는 구체적 기능이 생길 때만 해당 경계를 다시 조사한다.

## 10. Field 21 DictI32 → UserInfo 속성 매핑 확정

`UserInfo$$MergeVaryData @ 00dd3030`의 Ghidra Listing(`research/Ghidra_Listing_txt/US.txt`)을 다시 확인했다.

이 함수는 전달된 Dictionary<int,int>에서 정수 key를 `ContainsKey → get_Item`으로 조회하고, 값이 없으면 기존 UserInfo getter 값을 유지한 뒤 대응 setter를 호출한다. 따라서 field 21은 단순 보조 데이터가 아니라 UserInfo의 일부 런타임 속성을 갱신하는 key-value patch다.

| DictI32 key | UserInfo property | Getter fallback | Setter |
|---:|---|---|---|
| -9 | StigmataTimes | get_StigmataTimes | set_StigmataTimes |
| -10 | MetaphysicsTimes | get_MetaphysicsTimes | set_MetaphysicsTimes |
| -11 | Exp | get_Exp | set_Exp |
| -12 | Level | get_Level | set_Level |
| -15 | FCTimes | get_FCTimes | set_FCTimes |
| -13 | SignInDays | get_SignInDays | set_SignInDays |
| -14 | SignInRewardDay | get_SignInRewardDay | set_SignInRewardDay |
| -16 | StepId | get_StepId | set_StepId |
| -18 | ExamTimes | get_ExamTimes | set_ExamTimes |
| -30 | EquipMax | get_EquipMax | set_EquipMax |
| -31 | ChargeTotalPerMonth | get_ChargeTotalPerMonth | set_ChargeTotalPerMonth |
| -32 | Age | get_Age | set_Age |
| -34 | ChatChannel | get_ChatChannel | set_ChatChannel |

### 10.1 Main/Profile 표시와 연결

`UserInfoPanelMono.Start @ 00f7e92c`의 Calls OUT 및 Listing에서 다음 직접 소비를 확인했다.

- `UserInfo.get_Id` → `lbl_userId`
- `UserInfo.get_Name` → `lbl_nickName`
- `UserInfo.get_Level` → `lbl_lv`
- `UserInfo.get_Exp` → `lbl_userexpshow`, 경험치 bar 계산
- `DataCenter.get_HeadData` → 프로필 이미지
- `ShowHeadPanel` → 프로필 머리 장식 목록 구성

따라서 프로필의 Level/Exp는 field 35 User 객체만으로 설명할 수 없고, field 21의 key -12/-11 값이 UserInfo에 적용되는 경로까지 연결해야 한다.

### 10.2 재화 상단 표시 경로

`UserInfoPanelMono.RefreshTopInfos @ 00f7f914`는 `ShowCoin @ 00f7e524`를 호출한다.

`ShowCoin`은 설정된 재화 ID 목록을 순회하면서 각 항목에 대해:
- `DataCenter.GetXCount(itemId)`로 현재 수량 조회
- `Ali.GetBaseData(itemId)`로 이름/아이콘 기준 데이터 조회
- `BaseData.get_icon`, `get_NameByQualityWord`로 표시 요소 구성
- CoinGrid에 아이콘/이름/수량 반영

즉 재화 UI는 field 21의 숫자를 직접 표시하는 구조가 아니라, field 38 Items가 MergeItem으로 반영된 뒤 GetXCount를 통해 조회하는 별도 경로다. 앞서 Gold 변경 성공은 이 경로의 실제 표시값이 바뀐 runtime 검증으로 볼 수 있다.

### 10.3 분석 판정과 남은 검증

- **STATIC 확정:** field 21 → DictI32 → MergeVaryData → 위 UserInfo property setter.
- **STATIC 확정:** UserInfoPanelMono.Start의 Id/Name/Level/Exp UI 연결.
- **STATIC 확정:** RefreshTopInfos → ShowCoin → GetXCount 재화 UI 연결.
- **미확정:** 운영 payload에서 위 key 각각의 실제 값 및 생략 여부. 현재 확인한 Listing은 key 처리 규칙을 증명하지만, payload별 값의 의미/표시 결과까지 모두 증명하지는 않는다.
- **미확정:** UserInfoPanelMono.Start/RefreshTopInfos가 메인화면 첫 진입 시 자동 호출되는지 여부. 함수 구현의 소비 관계와 실제 실행 시점은 구분한다.

### 10.4 다음 클라이언트 분석

1. 실제 Bootstrap field 21의 key 분포를 추출해 위 13개 key의 존재/생략/값을 대조한다.
2. HomePanelMono.Start의 직접 Calls OUT 중 EquipMax 계열과 Hero getter를 분리해 실제 Main 초기화 의존성을 확정한다.
3. ProtoActivity field 56 → ToDictonary → RefreshUIBanner 경로에서 어떤 Activity property를 배너 표시가 읽는지 후속 추적한다.
4. 각 UI 소비처를 Main 최초 표시 / 프로필 패널 열기 / 별도 메뉴 진입으로 분류한다.

## 11. 운영 PCAP의 Field 21 실제 key 분포 대조

대상은 `research/PCAP/로그인_출석_퀘스트_우편_토벌_던전_상자_무기제작_강화_kcp/messages.json`의 packet 192~201 응답 `gzip_protobuf` tree다. 민감한 계정/세션 데이터는 제외하고 field 21의 key/value만 집계했다.

- Field 21 occurrence: **276개**
- Map entry key: **276개 모두 확인**
- 음수 key: 13종
- `UserInfo.MergeVaryData`가 처리하는 key 중 이 캡처에 실제 등장한 항목: -18, -30, -31, -32, -34 (5개)
- 해당 함수가 처리하지만 이 캡처에 없는 항목: -9, -10, -11, -12, -13, -14, -15, -16 (8개)

| key | MergeVaryData 대상 | 이 PCAP 값 | 해석 |
|---:|---|---:|---|
| -18 | ExamTimes | 15 | field 21에서 UserInfo로 반영 |
| -30 | EquipMax | 0 | field 21에서 UserInfo로 반영 |
| -31 | ChargeTotalPerMonth | 0 | field 21에서 UserInfo로 반영 |
| -32 | Age | 27 | field 21에서 UserInfo로 반영 |
| -34 | ChatChannel | 1 | field 21에서 UserInfo로 반영 |

그 외 음수 key(-29, -28, -27, -23, -22, -20, -33, -36)는 이 `MergeVaryData` 함수의 Listing에서 처리하는 key로 확인되지 않았다. 의미를 임의로 UserInfo property에 연결하지 않고 별도 미분류 key로 둔다. 양수 key는 263개이며, 상당수가 진행/콘텐츠 ID 형태이므로 동일 DictI32를 여러 시스템이 공유하는 구조일 가능성이 있지만, 개별 소비처는 추가 확인이 필요하다.

### 11.1 중요한 수정 사항

이 PCAP에서는 Level(-12)과 Exp(-11) key가 field 21에 없다. `MergeVaryData`는 key가 없으면 기존 UserInfo getter 값을 읽어 setter에 다시 넣는 방식이므로, 이 두 값은 이 응답에서 field 21로 덮어쓰이지 않는다.

따라서 Level/Exp 경로는 다음처럼 구분한다.

```text
field 35 User (ProtoUser)
  → UserInfo.ctor
  → DataTool.CopyTo<ProtoUser, UserInfo>
  → UserInfo 기본 상태

field 21 DictI32
  → UserInfo.MergeVaryData
  → key가 존재하는 일부 속성만 덮어쓰기
  → key가 없으면 기존 값 유지
```

`UserInfo.ctor @ 00dd2f44`에서 `DataTool.CopyTo` 호출은 확인했지만, ProtoUser의 protobuf tag와 Level/Exp property를 연결하는 직렬화 tag mapping은 아직 확정하지 않았다. 따라서 이 캡처의 Level/Exp 값은 **field 21에서 오지 않는다**는 점까지만 확정하고, field 35 내부 tag 대응은 별도 분석 대상으로 남긴다.

### 11.2 다음 확인

1. ProtoUser의 serialized tag ↔ Id/Name/Level/Exp/HeadIcon property mapping을 확인한다.
2. DictI32 양수 key 중 Main UI에서 참조하는 항목을 Ghidra Calls IN 및 getter와 대조한다.
3. 다른 운영 Frida 로그의 UserInfo 실제 getter 값은 해당 로그의 Bootstrap payload와 같은 실행인 경우에만 직접 대조한다.

## 12. Field 56 Activities → Main 배너 연결

`research/Ghidra_Listing_txt/HO.txt`의 `HomePanelMono.Start @ 00f67adc`와 `HomePanelMono.RefreshUIBanner @ 00f6ca94`, ProtoActivity 개별 Listing을 교차 확인했다.

### 12.1 Bootstrap Activity가 Main 진입 직후 사용되는 조건

`HomePanelMono.Start`는 `DataCenter.IsActivityOver` 결과를 확인한다.

- Activity가 만료되지 않은 경우: `HomePanelMono.Banner @ 00f6ab98` 호출 → `RefreshUIBanner @ 00f6ca94`로 이어지는 경로.
- Activity가 만료된 경우: `ProtocolGame_SendRequest.GetActivities @ 00de1f68`를 호출해 별도 갱신 요청.

따라서 Bootstrap field 56 Activities는 단순 메뉴 데이터가 아니라, **Main 진입 시 기존 Activity 상태로 배너를 바로 구성할 수 있는 초기 cache 데이터**다. 단, 만료 판정에 따라 후속 GetActivities 요청이 발생할 수 있다.

### 12.2 ProtoActivity 실제 속성 offset

| Field 56 nested tag | ProtoActivity property | 메모리 offset | wire 구조 |
|---:|---|---:|---|
| 1 | Id | +0x10 | varint |
| 2 | Status | +0x14 | varint |
| 3 | Data | +0x48 | nested map |
| 4 | Expire | +0x38 | nested time object |
| 5 | OpenTime | +0x18 | nested time object |
| 6 | CloseTime | +0x20 | nested time object |
| 7 | PreOpenTime | +0x28 | nested time object |
| 8 | PreCloseTime | +0x30 | nested time object |
| 9 | RechargeID | +0x5C | varint |
| 10 | I320 | 별도 getter 확인 대상 | varint |
| 11 | I321 | 별도 getter 확인 대상 | varint |
| 13 | I640 | 별도 getter 확인 대상 | varint |

근거 getter: `get_Id @ 015ac230`, `get_Status @ 015ac240`, `get_Data @ 015ac2b0`, `get_Expire @ 015ac290`, `get_OpenTime @ 015ac250`, `get_CloseTime @ 015ac260`, `get_PreOpenTime @ 015ac270`, `get_PreCloseTime @ 015ac280`, `get_RechargeID @ 015ac2f0`.

### 12.3 Data nested map 변환

`ProtoActivity.ToDictonary @ 015ac300` Listing은 다음을 확인해 준다.

1. ProtoActivity의 `Data` 객체(+0x48)를 가져온다.
2. `Dictionary<int, object>` enumerator로 Data 항목을 순회한다.
3. 각 항목의 key를 유지하고 value 객체의 `+0x14` 정수값을 읽는다.
4. 이를 `Dictionary<int, int>`에 `set_Item`으로 복사해 반환한다.

운영 PCAP의 field 56에서는 Data(tag 3)가 length-delimited이고, 그 내부는 map entry `field 1 key (varint) + field 2 value (varint)` 구조로 확인됐다. 따라서 wire의 Data는 ProtoActivity 내부의 key-value 설정값이며, 클라이언트는 이를 `Dictionary<int,int>`로 변환해 UI 로직에서 사용한다.

### 12.4 RefreshUIBanner 소비 확인

`HomePanelMono.RefreshUIBanner`의 Calls OUT에 다음이 함께 존재한다.
- `ProtoActivity.ToDictonary`
- `DataCenter.IsActivityOver` 관련 cache/상태 접근
- `Ali.GetExcelDic` 및 `BaseData` ID/icon/describe 조회
- `HomepanelNode.spr_activityBanner`, `point_activity`, `lbl_activityTime`
- `DateTime` 차감 및 `TimeSpan` 시간 단위 계산
- `AutoSnapBanner` 및 배너 목록/토글 구성

이로써 field 56 → ProtoActivity.Data → Dictionary<int,int> 변환 → Excel 설정/시간 상태와 결합 → Main 배너 UI 구성 흐름이 정적 Listing으로 연결된다. Data의 각 key가 어떤 배너 설정 의미인지, 특정 key별 UI 동작은 아직 확정하지 않았다.

### 12.5 Main Start에서 함께 호출되는 별도 기능

`HomePanelMono.Start` Calls OUT 및 Listing에서 다음이 확인된다.
- `RefreshPoint_TaoFa @ 00f69924`
- `RefreshPoint_Mail @ 00f69fd0`
- `RefreshPoint_Task @ 00f6a1dc`
- `RefreshWareHouse_Supply @ 00f6a2ec`
- `UIRefreshCamp @ 00f6ac08`
- 조건부 `GetActivities @ 00de1f68` 또는 `Banner @ 00f6ab98`

따라서 Home Start를 하나의 Bootstrap field에 대응시키면 안 된다. Activity/Quest/Mail/Item/기타 UI cache와 Excel Master Data가 병렬로 결합된다. 특히 Task 배지는 `DataCenter.QuestHaveFinished`를 호출하며, Camp 갱신은 `DataCenter.CheckTaskStateByID`를 호출한다.

### 12.6 현재 판정

- **RUNTIME:** 실제 Main 실행에서 `RefreshUIBanner` 진입 확인(기존 v4.9 Frida 기준 로그).
- **STATIC:** Home Start의 Activity 만료 분기 → Banner 또는 GetActivities 요청.
- **STATIC:** Field 56 → ProtoActivity.Data(+0x48) → ToDictonary → Main 배너 구성.
- **미확정:** Data map 내부 key별 업무 의미와 어떤 배너 항목이 어떤 key를 소비하는지.
- **미확정:** 각 시간 객체의 내부 field 1/2가 seconds/nanos 등 어떤 단위 표현인지.

다음은 field 56 Data key를 Activity Excel config와 연결하고, Banner에서 key별 조건을 읽는 지점을 확인한다. 이후 Quest/Mail/Supply/Camp의 Main 배지 소비 경로를 별도 표로 정리한다.

## 13. Main 배지: Quest / Mail / Supply / Camp 데이터 연결

`HomePanelMono.Start`에서 호출되는 배지 갱신 함수와 DataCenter의 실제 cache 참조를 대조했다.

### 13.1 Task / TaoFa / Camp — Quests cache

```text
Bootstrap field 51 Quests
  → OpInfo +0xE8
  → DataCenter.Merge<int, ProtoQuest>
  → DataCenter Quests cache +0x80
  → DataCenter.CheckTaskState / CheckTaskStateByID
  → Main Task / TaoFa / Camp point
```

근거:
- `DataCenter.ProccessRequestRes @ 016e203c`에서 OpInfo `+0xE8`을 DataCenter `+0x80`에 generic Merge한다.
- `DataCenter.CheckTaskState @ 016e75cc`는 `this +0x80` Dictionary에서 Excel task record의 ID로 ProtoQuest를 조회하고, ProtoQuest `+0x1C` 상태를 비교한다.
- `DataCenter.QuestHaveFinished @ 016e7a28`는 Excel task 목록을 순회해 `CheckTaskState`를 호출한다.
- `HomePanelMono.RefreshPoint_Task @ 00f6a1dc`는 `QuestHaveFinished` 결과로 Task 배지를 갱신한다.
- `HomePanelMono.UIRefreshCamp @ 00f6ac08` 및 `RefreshPoint_TaoFa @ 00f69924`는 `CheckTaskStateByID`를 호출한다.

따라서 Quests는 별도 Quest 화면에서만 쓰이는 데이터가 아니라 Main의 Task/TaoFa/Camp 상태 점검에도 연결된다. 단, 세 배지의 task ID 목록은 Excel 설정에서 결정되므로 Quest dictionary만으로 배지 결과를 설명할 수는 없다.

### 13.2 Mail — DictI32 key -27

```text
Bootstrap field 21 DictI32
  → OpInfo +0x70
  → ProccessRequestRes에서 key -27 복사
  → DataCenter Dictionary<int,int> +0xC0
  → HomePanelMono.RefreshPoint_Mail
  → point_mail / lbl_mailNum
```

운영 PCAP field 21에는 key `-27 = 1`이 실제로 존재한다. `ProccessRequestRes`는 OpInfo DictI32(+0x70)에서 key -27을 조회해 DataCenter `+0xC0` dictionary에 같은 key/value를 반영한다.

`HomePanelMono.RefreshPoint_Mail @ 00f69fd0`는 DataCenter `+0xC0`에서 key -27을 조회한다. 값이 0보다 크면 `point_mail`을 활성화하고, 메일 버튼이 활성 상태일 때 `lbl_mailNum`에 해당 수량을 표시한다.

즉 Mail 배지는 Bootstrap의 Mails collection(+0xB0 / cache +0x88)과 별개로, **DictI32 key -27의 unread count**를 읽는 구조다. 실제 PCAP에서 Mails collection이 직렬화되지 않은 점과 모순되지 않는다.

### 13.3 Warehouse Supply — Items에서 Box 목록 계산

```text
Bootstrap field 38 Items
  → DataCenter.MergeItem
  → item category cache +0x78
  → DataCenter.RefreshBoxList
  → isBoxItem 필터 + 그룹 정렬
  → DataCenter BoxSupplyList(+0xE8)
  → get_BoxSupplyTotalCount
  → HomePanelMono.RefreshWareHouse_Supply
```

`DataCenter.RefreshBoxList @ 016e6c64`는 DataCenter Items cache(+0x78)를 입력으로 사용하고 `AliothExtensions.isBoxItem` predicate로 box item을 필터링한 뒤 `DataTool.ToListByGroup` / 정렬 결과를 BoxSupplyList(+0xE8)에 저장한다. `get_BoxSupplyTotalCount @ 016e6b58`는 이 목록 각 항목의 수량(+0x18)을 합산한다.

`HomePanelMono.RefreshWareHouse_Supply @ 00f6a2ec`는 `get_BoxSupplyTotalCount` 결과를 `lbl_wareHouseBoxNum`에 표시하고 `point_wareHouse` 상태를 갱신한다.

따라서 Main 창고 보급 배지는 field 38 Items가 실제 소비되는 또 하나의 직접 경로다. Chapter BoxStatus와는 별도인 **인벤토리 내 box item 보유 수량**이다.

### 13.4 Main 배지 데이터 계약 요약

| Main UI | Bootstrap 원천 | Client cache / 처리 | 표시 결과 |
|---|---|---|---|
| Activity banner | field 56 Activities | Activity cache → ProtoActivity.ToDictonary | banner / 시간 / activity point |
| Task point | field 51 Quests | cache +0x80 → QuestHaveFinished / CheckTaskState | point_task |
| TaoFa / Camp point | field 51 Quests + Excel task config | CheckTaskStateByID | point_TaoFa / point_camp |
| Mail point/count | field 21 DictI32 key -27 | cache +0xC0 Dictionary<int,int> | point_mail / lbl_mailNum |
| Warehouse supply | field 38 Items | cache +0x78 → RefreshBoxList → BoxSupplyList | lbl_wareHouseBoxNum / point_wareHouse |

이 표는 Main 초기화에서 확인된 연결만 정리한 것이다. 별도 응답으로 갱신되는 값이나 사용자가 메뉴를 열었을 때만 필요한 데이터는 계속 분리해서 기록한다.

### 13.5 다음 확인

1. Field 21의 다른 음수 key가 DataCenter의 어느 cache에 복사되고 어떤 Main UI에서 소비되는지 계속 연결한다.
2. `isBoxItem`이 참조하는 BaseData/Excel 조건과 BoxSupplyList grouping 기준을 확인한다.
3. Task/TaoFa/Camp 각각이 참조하는 Excel task ID 집합을 분리해 Quests cache의 필요한 상태와 대조한다.

## 14. Warehouse Supply의 ItemRecord / ItemboxRecord 구분

Unity 관련 기준 문서(`참고용-unity-behavior-data/데이터_파일_역할_및_계층.md`, `게임_보상_업적_출석_이벤트_가챠_구조_분석.md`)를 먼저 확인한 뒤, data_catalog의 구조 요약/Record sample과 원본 `MonoBehaviour/ItemRecord.json`, `ItemboxRecord.json`을 대조했다.

### 14.1 isBoxItem의 실제 필터 조건

`AliothExtensions.isBoxItem @ 00e166ac`는 `BaseData.get_type` 값을 확인한다.
- type 8 → true
- type 1 → true
- type 9 → true
- 그 외 → false

따라서 `DataCenter.RefreshBoxList`는 이름이 Box인 Record를 직접 찾는 게 아니라, **Item BaseData의 type이 1/8/9인 인벤토리 항목**을 box item으로 분류한다.

### 14.2 원본 ItemRecord type 분포

`MonoBehaviour/ItemRecord.json`에서 확인한 952개 레코드의 m_type 분포:

| m_type | 레코드 수 | isBoxItem 결과 |
|---:|---:|---|
| 0 | 26 | 제외 |
| 1 | 27 | 포함 |
| 2 | 87 | 제외 |
| 4 | 4 | 제외 |
| 6 | 4 | 제외 |
| 7 | 1 | 제외 |
| 8 | 119 | 포함 |
| 9 | 174 | 포함 |
| 10 | 505 | 제외 |
| 11 | 1 | 제외 |
| 12 | 4 | 제외 |

즉 현재 원본 데이터 기준 box item 후보는 **type 1/8/9, 총 320개**다. 이는 코드 필터와 실제 ItemRecord 분포를 대조한 결과이며, 각 type의 게임 내 표시 명칭은 별도 Word/실행 코드 확인 전까지 붙이지 않는다.

### 14.3 ItemboxRecord의 역할은 별도

`MonoBehaviour/ItemboxRecord.json`은 3,242개이며, 이 테이블의 m_type은 전부 0이다. 대신 `m_itemId`에 `ID*수량|ID*수량` 형식으로 실제 구성품을 저장한다.

예시 구조: `43000001*5000|43200003*2|40000100*1`

따라서 데이터 계층은 다음과 같이 구분된다.

```text
ItemRecord
  └─ m_type 1 / 8 / 9
       └─ 클라이언트 isBoxItem 필터 통과
            └─ Inventory box supply list

ItemboxRecord
  └─ m_itemId (ID*수량 목록)
       └─ 박스/패키지에 실제 포함된 구성품 정의
```

**중요:** Main의 `lbl_wareHouseBoxNum`은 ItemboxRecord의 정의 개수(3,242)를 표시하는 것이 아니다. 런타임 Items cache에서 `isBoxItem`을 통과한 항목들을 `RefreshBoxList`가 목록화하고, `get_BoxSupplyTotalCount`가 각 보유 수량을 합산한 결과다.

### 14.4 연결 판정

- **STATIC:** `isBoxItem`은 BaseData.type 1/8/9만 통과.
- **DATA:** ItemRecord 952개 중 해당 type은 320개.
- **DATA:** ItemboxRecord 3,242개는 m_itemId로 구성품 ID/수량을 정의하고, m_type은 전부 0.
- **STATIC:** Main Warehouse Supply 숫자는 Item cache → RefreshBoxList → BoxSupplyList → 수량 합계 경로.
- **미확정:** type 1/8/9 각각의 한국어 분류명 및 `DataTool.ToListByGroup` 내부 group key의 표시 의미.

다음은 type 1/8/9 항목의 실제 ID와 ItemboxRecord/ItempackageRecord 참조 관계를 연결하고, Main 화면에 표시되는 수량이 어떤 항목을 합산하는지 세부적으로 좁힌다.

### 14.5 type별 실제 참조 Record 교차 확인

원본 ItemRecord의 m_id는 currentCryptoKey와 hiddenValue를 대조해 실제 ID로 복원한 뒤, ItemboxRecord/ItempackageRecord의 실제 ID 집합과 교차했다.

| ItemRecord m_type | 개수 | m_itemPackageId 참조 결과 |
|---:|---:|---|
| 1 | 27 | 27개 전부 ItempackageRecord ID(451xxxxx)와 일치 |
| 8 | 119 | 119개 전부 현재 Itembox/Itempackage ID 집합과 불일치. `1*1`, `200*5` 등 별도 ID 체계로 남김 |
| 9 | 174 | 174개 전부 ItemboxRecord ID(443xxxxx)와 일치 |

이 결과로 box item 세부 경로를 나눌 수 있다.

```text
ItemRecord(type=1)
  → m_itemPackageId
  → ItempackageRecord

ItemRecord(type=9)
  → m_itemPackageId
  → ItemboxRecord

ItemRecord(type=8)
  → m_itemPackageId (소형 ID*수량 목록)
  → 현재 Itembox/Itempackage와는 불일치
  → 별도 ID namespace 확인 필요
```

따라서 Main supply count는 서로 다른 개봉/구성 정의를 가진 type 1/8/9 항목을 하나의 보유 목록으로 집계한다. type 8의 참조 대상이 확인되기 전까지 이를 Itempackage 또는 Itembox로 통일해서 처리하면 안 된다.


## 15. UserInfo 생성·초기화와 프로필 UI 진입 경로 (2026-10-03)

기준 Listing: `research/Ghidra_Listing_txt/US.txt`

### 15.1 UserInfo.ctor의 실제 동작

`UserInfo::.ctor @ 00dd2f44` 본문에서 확인한 순서:

1. Object 기본 생성자를 호출한다.
2. `UserInfo.get_PropertyInfoCache`로 복사 메타데이터를 얻는다.
3. `DataTool.CopyTo<object,object> @ 01771ddc`에 입력 객체와 새 UserInfo 객체를 전달한다.
4. 이후 UserInfo class static-fields의 `+0x170` delegate를 검사한다.
5. delegate가 non-null이면 `XLua.DelegateBridge.__Gen_Delegate_Imp14`로 위임하고, null이면 기본 return한다.

따라서 앞서 확인한 `OpInfo.User(+0x88) → UserInfo.ctor → DataCenter(+0x28)`에서 ctor는 ProtoUser 입력의 속성을 PropertyInfo 기반 복사 함수로 UserInfo에 옮기는 역할을 한다. 다만 CopyTo 내부의 실제 property별 복사 목록과 protobuf tag 번호는 이 ctor Listing만으로 확인되지 않는다.

**중요:** UserInfo ctor에도 별도 static delegate 경로가 있다. 이 경로를 Request의 +0x80/+0x88 또는 NetworkCenter의 delegate와 같은 것으로 취급하지 않는다. 런타임에서 +0x170의 null 여부 및 위임 실행 여부는 아직 미확정이다.

### 15.2 DictI32 vary data 적용 규칙 재확인

`UserInfo.MergeVaryData @ 00dd3030`은 field 21의 Dictionary<int,int>를 받아 key별로 기존 값을 유지하거나 새 값으로 덮어쓴다.

- key가 존재하면 Dictionary의 값을 읽는다.
- key가 없으면 대응 UserInfo getter로 기존 값을 읽는다.
- 그 값을 대응 setter에 전달한다.

확인된 key/property 대응은 10절 표와 같다. 이 구조에서 field 21은 UserInfo 전체를 대체하는 객체가 아니라 일부 속성을 선택적으로 갱신하는 patch다. 실제 운영 PCAP에서는 MergeVaryData 대상 13개 중 -18/-30/-31/-32/-34만 확인됐고, -11 Exp 및 -12 Level은 존재하지 않았다.

따라서 해당 캡처에서 Level/Exp는 field 21로 갱신되지 않는다. 두 값의 입력은 field 35 User의 ProtoUser→UserInfo 복사 경로 또는 그 외 초기화 경로에서 확인해야 하며, ProtoUser tag mapping은 아직 미확정이다.

### 15.3 UserInfoPanelMono.Start의 화면 초기화

`UserInfoPanelMono.Start @ 00f7e92c`의 Calls OUT 및 Listing에서 확인:

- 초기에 UserInfoPanelMono class static-fields `+0x40` delegate를 검사한다. non-null이면 DelegateBridge Imp11로 위임하고 기본 Start 경로를 건너뛴다.
- 기본 경로에서는 `Ali.OnProccessRequestFinish` delegate를 생성하고 `BaseMono.RegisterDataProccessCallBack`에 전달한다. 이 호출의 인자는 `7`이다.
- 별도 NotifyDelegate를 생성해 `BaseMono.AddNotifyListener`에 등록한다. 해당 호출 인자는 `0x31`이다.
- 이후 HeadData 조회 및 프로필 이미지 설정, UserInfo getter를 이용한 화면 텍스트/경험치 표시 초기화가 이어진다.
- 직접 호출되는 getter와 UI node:
  - `UserInfo.get_Id` → `lbl_userId`
  - `UserInfo.get_Name` → `lbl_nickName`
  - `UserInfo.get_Level` → `lbl_lv`
  - `UserInfo.get_Exp` → `lbl_userexpshow` 및 경험치 bar 계산
  - `DataCenter.get_HeadData` → 프로필 이미지
  - `ShowHeadPanel` → 머리 장식 목록

이 화면의 Start는 단순 표시 함수가 아니라 DataProcess callback 및 Notify listener도 등록한다. 다만 callback 7과 notify 0x31의 업무 의미 및 실제 호출 시점은 해당 dispatch 경로를 추가 확인해야 한다.

### 15.4 재화 UI와 프로필 기본 정보의 분리

`UserInfoPanelMono.RefreshTopInfos @ 00f7f914`는 class static-fields `+0x50` delegate가 non-null이면 위임하고, 기본 경로에서는 `ShowCoin @ 00f7e524`를 호출한다.

`ShowCoin`은 설정된 CoinGrid 항목을 순회하며 각 ID에 대해:
- `DataCenter.GetXCount(itemId)`로 수량 조회
- `Ali.GetBaseData(itemId)`로 표시용 BaseData 조회
- icon/name/count를 CoinGrid child node에 설정

따라서 프로필 화면의 Id/Name/Level/Exp 표시와 재화 표시의 데이터 원천은 분리된다.

```text
OpInfo.User(+0x88)
  → UserInfo.ctor
  → PropertyInfo 기반 DataTool.CopyTo
  → DataCenter.UserInfo(+0x28)
  → UserInfoPanelMono.Start
  → Id / Name / Level / Exp 표시

OpInfo.Items(+0x98)
  → DataCenter.MergeItem
  → GetXCount(itemId)
  → UserInfoPanelMono.ShowCoin
  → CoinGrid 수량 표시
```

### 15.5 현재 판정 및 미확정

- **STATIC 확정:** UserInfo.ctor는 PropertyInfoCache + DataTool.CopyTo 경로로 입력 객체의 속성을 복사한다.
- **STATIC 확정:** UserInfoPanelMono.Start는 Id/Name/Level/Exp를 UI node에 연결하고 callback/notify 등록을 수행한다.
- **STATIC 확정:** RefreshTopInfos → ShowCoin → GetXCount로 재화 수량을 표시한다.
- **미확정:** DataTool.CopyTo 내부에서 ProtoUser의 어떤 property가 어떤 UserInfo property로 복사되는지, 그리고 protobuf tag 번호가 무엇인지.
- **미확정:** UserInfo ctor static delegate(+0x170), UserInfoPanelMono Start(+0x40), RefreshTopInfos(+0x50)의 런타임 활성 여부.
- **미확정:** UserInfoPanelMono.Start가 메인 진입 직후 자동 호출되는지, 사용자가 프로필 패널을 열 때 호출되는지. 현재 Listing은 Start 내부 동작만 증명한다.

### 15.6 다음 분석

1. `DataTool.CopyTo @ 01771ddc`의 실제 property enumeration/copy 조건을 확인해 ProtoUser→UserInfo 필드 매핑을 좁힌다.
2. ProtoUser property getter와 serialized tag metadata를 대조해 Id/Name/Level/Exp/HeadIcon의 wire tag를 확인한다.
3. `UserInfoPanelMono.Start`가 등록한 callback 7 및 notify 0x31의 dispatch consumer를 추적한다.
4. 이후 HeroInfo.InitHero의 ProtoHero 입력과 DataManager key 관계로 진행한다.


## 16. ProtoHero → HeroInfo.InitHero 런타임 대조 (2026-10-03)

### 16.1 기준 자료

- Static Listing: `research/Ghidra_Listing_txt/DA.txt`의 `DataCenter.UpdateHeroInfo @ 016e4ba4` 호출 경로
- ProtoHero getter: `research/Ghidra_Listing_txt/AL/015ad30c_Alioth.S1.Common.ProtoHero__get_Id.txt`
- Runtime: `research/reports/Log/frida_log_static_신규로갱신되므로기존데이터없이최종본만.txt`
- Hook 정의: `research/justice_hook.js`의 `HeroInfo.InitHero` source/result field dump

### 16.2 호출 구조

기존 정적 분석과 런타임 hook을 합치면 다음 경로가 확인된다.

```text
OpInfo.Heros (+0x90)
  → Dictionary<int, ProtoHero> 순회
  → HeroInfo 인스턴스 생성/선택
  → HeroInfo.InitHero(this, ProtoHero, ...)
  → HeroInfo 상태 초기화
```

Runtime hook은 실제로 `HeroInfo.InitHero`에 진입했고 첫 번째 인자가 HeroInfo(this), 두 번째 인자가 ProtoHero(source)임을 출력했다. 즉 메서드 인자 배치는 로그에서 직접 확인됐다.

### 16.3 ProtoHero 입력과 HeroInfo 결과의 일치

동일 실행의 runtime dump에서 다음 대응을 확인했다.

| ProtoHero.Id | ProtoHero Level | ProtoHero Exp | ProtoHero Star | ProtoHero Weapon | HeroInfo 결과 |
|---:|---:|---:|---:|---:|---|
| 10000000 | 50 | 845 | 3 | 40000004 | Id=10000000, Level=50, Exp=845, Star=3, Weapon=40000004 |
| 10000001 | 40 | 475 | 2 | 40000101 | Id=10000001, Level=40, Exp=475, Star=2, Weapon=40000101 |
| 10000002 | 40 | 0 | 2 | 40000201 | Id=10000002, Level=40, Exp=0, Star=2, Weapon=40000201 |

추가로 FashionId도 입력과 결과에서 동일한 값으로 관측됐다. 첫 번째 항목은 ProtoHero.FashionId=49000000이며 HeroInfo.FashionId=49000000이다.

ProtoHero 객체 필드 offset은 runtime dump 기준 Id +0x10, Status +0x14, Level +0x18, Exp +0x1C, Star +0x20, Weapon +0x24, Armor +0x28, Belt +0x30, Emblem +0x38, Talent +0x40, Suit +0x44, FashionId +0x48, Strategy +0x4C, Hole1~6StigmataId +0x50~+0x64다. 이는 managed object field offset이며 protobuf wire tag가 아니다.

HeroInfo 결과 객체에서는 Id +0x18, Level +0x1C, Exp +0x20, Star +0x24, Weapon +0x2C, Armor +0x30, Belt +0x38, Emblem +0x40, FashionId +0x48 등이 관측됐다. ProtoHero와 HeroInfo의 객체 offset은 다르므로 단순 memcpy나 동일 offset 복사로 설명하면 안 된다.

### 16.4 InitHero 이후 생성/보강되는 상태

Runtime 결과에서 입력 ProtoHero에 없거나 직접 대응하지 않는 HeroInfo 상태도 확인된다.

- Prototype: ActorData 참조가 생성/설정됨
- State: HeroState 객체 참조
- StigmataInfo: 별도 객체 참조
- WeaponInfomation: WeaponInfo 객체 참조
- Suits: List<int> 참조
- dic_property: PROPERTY → ObscuredFloat Dictionary
- noInit, LastExp, LastLevel 등 초기화 보조 필드

따라서 InitHero는 단순 ProtoHero 복사가 아니라 원본 필드를 HeroInfo에 반영하면서 정적 ActorData/무기/성흔/속성 관련 상태를 구성하는 초기화 단계로 볼 수 있다. 각 보조 객체의 구체적인 생성·lookup 함수는 별도 추적 대상이다.

### 16.5 DataManager key 판정

현재 정적 경로에서는 UpdateHeroInfo가 Hero dictionary를 순회하고 DataManager 조회를 수행한 뒤 HeroInfo.InitHero를 호출하는 사실이 확인되어 있다. Runtime에서는 ProtoHero.Id와 결과 HeroInfo.Id가 동일한 여러 샘플이 확인됐다.

다만 이번 로그에는 **원본 Dictionary의 key와 ProtoHero.Id를 같은 행에 출력한 기록이 없다.** 따라서 다음 관계는 아직 완전 확정하지 않는다.

```text
Heros Dictionary key == ProtoHero.Id == HeroInfo.Id
```

현재 확정 범위는 `ProtoHero.Id == HeroInfo.Id`이며, Dictionary key가 같은 값인지는 UpdateHeroInfo loop에서 key/value pair를 함께 출력하거나 Dictionary 조회 인자를 계측해 확인해야 한다.

또한 DataManager 조회 대상이 HeroInfo 자체인지, HeroInfo.Prototype에 대응하는 ActorData인지, 별도의 BaseData인지 호출부 인자/반환값을 추가 대조해야 한다.

### 16.6 판정 및 다음 추적

- **RUNTIME 확정:** InitHero의 this=HeroInfo, source=ProtoHero.
- **RUNTIME 확정:** 관측된 3개 이상 Hero에서 Id/Level/Exp/Star/Weapon이 ProtoHero 입력과 HeroInfo 결과에 동일하게 반영됨.
- **RUNTIME 확정:** FashionId도 입력/결과 일치 사례 확인.
- **STATIC+RUNTIME:** HeroInfo 초기화 과정에서 Prototype(ActorData), State, StigmataInfo, WeaponInfomation 등 추가 상태가 설정됨.
- **미확정:** Heros Dictionary key와 ProtoHero.Id의 동일성.
- **미확정:** UpdateHeroInfo 내부 DataManager.TryGet의 정확한 key 및 반환 객체 종류.
- **미확정:** ProtoHero 내부 field의 protobuf wire tag 전체 매핑.

다음은 UpdateHeroInfo의 Dictionary enumerator에서 key와 value를 동시에 출력하도록 hook을 보강하고, DataManager.TryGet 호출 인자 및 반환 class를 기록해 key 관계를 확정한다. 이후 HeroInfo.Prototype/ActorData와 HeroInfo.Id의 역할을 분리한다.


## 17. UpdateHeroInfo의 Hero Dictionary key 및 DataManager 조회 위치 (2026-10-03)

기준 Listing: `research/Ghidra_Listing_txt/DA.txt`

### 17.1 Heros key의 정적 조회 경로

`DataCenter.UpdateHeroInfo @ 016e4ba4`의 Hero 처리 구간(`016e5120~016e51a4`)을 확인했다.

1. `OpInfo.Heros(+0x90)`에 대해 Dictionary enumerator를 생성한다.
2. Enumerator의 현재 항목에서 정수 key를 읽어 `w22`에 보관한다(`016e514c`).
3. 같은 key(`w22`)로 DataCenter 인스턴스 `+0x30` Dictionary에 `TryGetValue`를 호출한다(`016e5164`, 결과 위치 `sp+0x48`).
4. 다시 같은 key(`w22`)로 `OpInfo.Heros(+0x90)`에 `TryGetValue`를 호출한다(`016e5190`, 결과 위치 `sp+0x40`).
5. 두 조회가 성공하면 기존 객체와 응답 객체를 각각 인자로 `HeroInfo.InitHero @ 016e5fd4`에 전달한다(`016e5198~016e51a4`).

따라서 **기존 DataCenter +0x30 Dictionary와 응답 OpInfo.Heros는 동일한 정수 key로 대응 항목을 찾는다**는 점이 정적으로 확인된다. 이는 두 Dictionary 사이의 key 계약을 보여준다.

다만 현재 확보한 runtime log에는 Enumerator의 key와 ProtoHero.Id를 같은 행에서 출력한 자료가 없다. 따라서 `Dictionary key == ProtoHero.Id`는 아직 런타임 확정으로 올리지 않는다. 앞서 관측한 `ProtoHero.Id == HeroInfo.Id` 사례와 결합해도 Dictionary key의 실제 값이 로그로 확인된 것은 아니다.

### 17.2 DataManager.TryGet 호출 위치 재분류

같은 `UpdateHeroInfo`의 Calls OUT에는 `DataManager.TryGet<object> @ 0177142c`가 나타난다. Listing에서 실제 호출은 `016e4f1c`, `016e4fe4`에 있다.

- 첫 호출은 `OpInfo +0xE0` Dictionary를 순회하는 루프 안에 있다.
- 두 번째 호출은 `OpInfo +0xA0` Dictionary를 순회하는 루프 안에 있다.
- 각 호출 직전 Enumerator에서 읽은 정수 key(`w22`)가 TryGet의 key 인자로 전달된다.
- 반환된 out object의 서로 다른 필드(+0x74 또는 +0x7C)를 읽어 HashSet에 추가한다.

중요하게도 이 두 TryGet 호출은 **Hero 본체인 OpInfo +0x90 순회 구간(+0x5120 이후)이 아니라, 앞서 실행되는 +0xE0/+0xA0 보조 Dictionary 처리 구간**에 위치한다. 따라서 Calls OUT 목록만 보고 DataManager.TryGet이 HeroInfo.Prototype(ActorData)을 찾는 함수라고 해석하면 안 된다.

`DataManager.TryGet<object>` 본문(`0177142c`)은 DataCache에서 key를 조회하고, generic type과 반환 객체의 runtime type을 비교하는 경로를 포함한다. 그러나 현재 호출부 Listing만으로 generic type 인자 및 out object의 실제 class를 확정할 수 없다.

### 17.3 현재 판정

- **STATIC 확정:** OpInfo.Heros enumerator에서 추출한 하나의 key를 DataCenter +0x30 및 OpInfo +0x90 양쪽 Dictionary 조회에 재사용한다.
- **STATIC 확정:** 두 조회가 성공하면 기존 객체와 응답 ProtoHero를 `HeroInfo.InitHero`에 전달한다.
- **STATIC 확정:** UpdateHeroInfo의 DataManager.TryGet 두 호출은 OpInfo +0xE0/+0xA0 보조 Dictionary 루프에 속하며, Hero +0x90 순회 구간과 구분된다.
- **미확정:** 해당 Hero Dictionary key와 ProtoHero.Id의 수치 동일성.
- **미확정:** DataManager.TryGet 두 호출의 generic type 및 반환 객체 실제 class.
- **미확정:** HeroInfo.Prototype(ActorData)을 설정하는 정확한 lookup 경로.

### 17.4 다음 계측 항목

1. `DataCenter.UpdateHeroInfo` 진입 시 OpInfo +0x90 Dictionary의 key/value를 함께 출력한다.
2. 각 value의 ProtoHero.Id를 함께 출력해 `key == ProtoHero.Id`를 직접 비교한다.
3. `DataManager.TryGet<object> @ 0177142c`는 호출 인자(key, generic type handle), bool 반환, out object class를 기록하되 +0xE0/+0xA0 호출을 구분한다.
4. 별도로 `HeroInfo.InitHero` 전후의 Prototype 참조와 ActorData.Id(또는 해당 식별 getter)를 기록해 Prototype 설정 경로를 찾는다.

현재 hook에는 `HeroInfo.InitHero`와 `DataManager.TryGetBaseData`는 있으나, 위의 `DataCenter.UpdateHeroInfo` Dictionary pair 및 generic `DataManager.TryGet<object>` 인자/반환을 직접 기록하는 계측은 확인되지 않았다.
