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
