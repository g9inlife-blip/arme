# 2026-10-02 ProtocolGame Request 진입점 및 호출 조건 분석

## 1. 목적 / 범위

Local Private Server 구현에 필요한 클라이언트 요청 경계를 확인한다.

이번 범위:
- ProtocolGame_SendRequest 함수 inventory
- Request 함수의 실제 caller 분류
- 화면 로딩 시 자동 요청이 발생하는 공통 진입점
- 요청 발생 조건과 OpCode / 인자 연결

제외:
- ChatChannel, SendWorldChat 등 채팅 기능
- 이미 별도 분석 중인 Bootstrap 데이터 의미 및 UI 데이터 소비 상세
- 서버 구현 및 코드 수정

## 2. Request 생성 함수 전체 후보

Git Listing `research/Ghidra_Listing_txt/AL/015ab228_Alioth.S1.Common.OpInfo__.ctor.txt`의 Calls IN을 확인했다.

- `ProtocolGame_SendRequest$$...` 형태의 OpInfo 생성 caller: **98개**
- 이는 정적 Listing에서 OpInfo 생성자를 호출하는 Request 생성 함수의 개수다.
- 실제 실행 빈도나 현재 서비스에서 활성화된 API 수를 뜻하지 않는다.
- XLua wrapper가 연결된 함수도 다수이므로 Lua에서 호출 가능한 경로가 포함된다.
- Chat 관련 함수는 inventory에는 남기되 Local Server 우선 분석 대상에서 제외한다.

이 98개를 기준으로 API 후보 목록을 만들고, 각 함수의 Calls IN을 따라 UI/Manager/자동 호출/XLua 경로를 분류한다.

## 3. 화면 진입 공통 요청 Dispatcher

대상 Listing:
- `research/Ghidra_Listing_txt/AL/01693710_AliothEngine.GUIScreenLoaderS1__IsSendRequest.txt`
- 함수: `AliothEngine.GUIScreenLoaderS1.IsSendRequest @ 01693710`

Calls IN:
- `AliothEngine.GUIScreenManager._ShowScreen @ 0167a6fc`
- `XLua.CSObjectWrap.AliothEngineGUIScreenLoaderS1Wrap._m_IsSendRequest_xlua_st_ @ 01148158`

Calls OUT:
- `GUIScreenParam.get_assetName`
- `<PrivateImplementationDetails>.ComputeStringHash`
- `System.String.op_Equality`
- `GUIScreenManager.GetScreenFromName`
- `GUIScreenManager.AddCodeParamDic`
- 아래 화면별 ProtocolGame_SendRequest 함수들

### 처리 구조

```text
GUIScreenManager._ShowScreen
  → GUIScreenLoaderS1.IsSendRequest(screen/param)
  → GUIScreenParam.assetName 읽기
  → ComputeStringHash(assetName)
  → hash 분기
  → String.op_Equality로 실제 문자열 재비교
  → AddCodeParamDic(code, param, ...)
  → ProtocolGame_SendRequest.<API>()
```

즉 일부 API는 버튼 클릭 함수에서 직접 요청하는 것이 아니라 **화면을 열고 로더가 assetName을 판정하는 단계에서 자동 요청**된다.

Hash만으로 화면 이름을 확정하지 않는다. 현재 Listing에서 String.op_Equality가 참조하는 문자열 literal의 실제 텍스트는 아직 복원하지 못했으므로 아래 표는 hash와 호출 API를 기준으로 기록한다.

### 화면 로딩에 따른 자동 요청 분기

| assetName hash (32-bit) | AddCodeParamDic code | Request 함수 | OpCode |
|---:|---:|---|---:|
| 0xE0E5AAE0 | 0x06 | GetActivities | 0x06 |
| 0xB32DDEAC | 0x2D | GetMails | 0x2D |
| 0xA8A5DFAC | 0x33 | GetShops | 0x33 |
| 0xF98C8D69 | 0x5E | ExploreFloorGet | 0x5E |
| 0x2884B966 | 0x69 | SpaceBaseGet | 0x69 |
| 0x2CD83D14 | 0x7F | GetBattleReport | 0x7F |
| 0xB9F06410 | 0x45 | GetExam | 0x45 |

각 분기는 hash 비교 후 별도 String.op_Equality를 통과해야 요청으로 이어진다. 따라서 hash 일치만으로 요청이 실행되는 것은 아니다.

## 4. GetActivities 요청의 실제 호출 경로

대상:
- `ProtocolGame_SendRequest.GetActivities @ 00de1f68`
- Listing: `research/Ghidra_Listing_txt/PR.txt`

Calls IN:
- `HomePanelMono.Start @ 00f67adc`
- `AliothEngine.GUIScreenLoaderS1.IsSendRequest @ 01693710`
- `XLua.CSObjectWrap.ProtocolGame_SendRequestWrap._m_GetActivities_xlua_st_ @ 013412e4`

Request 생성:
- `OpInfo::.ctor @ 015ab228`
- `OpInfo +0x14 = 0x06`
- 별도 Request payload field assignment는 Listing에서 확인되지 않음
- `CSBehaviour.RequestOp @ 016dcafc`로 전달

호출 조건은 서로 다른 두 경로다.

### A. Main 진입 시 상태 만료 분기

기존 `2026-10-02-Bootstrap-Client-State-MainUI-연결분석.md`에서 확인한 `HomePanelMono.Start` 경로:
- `DataCenter.IsActivityOver` 결과가 만료 상태이면 `GetActivities()` 호출
- 만료되지 않았으면 기존 Activity cache를 이용해 Banner 초기화 경로로 진행

따라서 GetActivities는 화면 진입 자동 요청 외에 Main 진입 시 Activity cache의 만료 여부에 따라 직접 호출되는 갱신 요청이기도 하다.

### B. 화면 로더 자동 요청

`GUIScreenLoaderS1.IsSendRequest`의 assetName hash/문자열 비교 분기에서:
- code 0x06을 `AddCodeParamDic`에 전달
- `GetActivities()` 호출

이 경로는 특정 화면 assetName에 대한 로딩 시점 요청이다. 현재 문자열 literal 텍스트와 해당 화면의 표시 이름은 미확정이다.

## 5. GetExam의 인자 조건

`IsSendRequest`의 GetExam 분기에서 확인된 동작:
- assetName hash 0xB9F06410 및 실제 문자열 비교 통과
- `AddCodeParamDic(0x45, ...)`
- `Ali.get_dataCache` → `DataCache.get_m_queryRankID` 확인
- queryRankID가 1 이상이면 그 값을 `GetExam(arg)`에 전달한 뒤 queryRankID를 0으로 초기화하는 경로
- queryRankID가 1 미만이면 `UserInfo.get_Id` 값을 `GetExam(arg)`에 전달하는 경로

`GetExam @ 00de1638` Listing에서:
- OpCode = 0x45
- 인자 값은 `OpInfo +0x48`에 저장
- 이후 `CSBehaviour.RequestOp`로 전달

이 함수는 단순 무인자 화면 조회가 아니며, 호출 문맥에 따라 조회 대상 ID가 달라진다. 다만 queryRankID의 의미와 각 assetName의 텍스트는 추가 확인 대상이다.

## 6. 이번 단계에서 확인된 분류

| 요청 | 호출 유형 | 확인된 caller / trigger | 현재 판정 |
|---|---|---|---|
| GetActivities | Main 상태 갱신 + 화면 자동 요청 | HomePanelMono.Start / IsSendRequest | 정적 확인 |
| GetMails | 화면 자동 요청 | IsSendRequest | 정적 확인 |
| GetShops | 화면 자동 요청 | IsSendRequest | 정적 확인 |
| ExploreFloorGet | 화면 자동 요청 | IsSendRequest | 정적 확인 |
| SpaceBaseGet | 화면 자동 요청 | IsSendRequest 및 SupportPanelMono.OnClickSupportTotal | 정적 확인 |
| GetBattleReport | 화면 자동 요청 | IsSendRequest | 정적 확인 |
| GetExam | 화면 자동 요청 + 결과 화면 복귀 | IsSendRequest / BattleEndTwoBtnGroupMono.OnClickBackExam | 정적 확인 |

이 표는 Listing의 caller 관계를 뜻하며, 각 경로가 현재 실행에서 실제로 발생하는지는 runtime RequestOp 로그와 대조해야 한다.

## 7. 다음 작업

1. IsSendRequest의 hash 비교 대상 문자열 literal을 복원해 실제 화면 assetName을 확정한다.
2. 나머지 Request 생성 함수 98개를 대상으로 Calls IN을 수집해 화면 진입 자동 요청 / 사용자 액션 / 주기성 요청 / XLua 호출로 분류한다.
3. Local Server 범위에 필요한 비채팅 API를 우선 추린다.
4. 주요 요청마다 OpCode, 인자 offset, serializer, response handler를 연결한다.
5. runtime RequestOp 로그의 opcode/순서와 정적 caller를 대조한다.

## 8. 증거 원칙

- OpInfo::.ctor Calls IN 98개는 정적 Request 생성 후보 수이며 실제 API 활성도와 동일하지 않다.
- IsSendRequest의 hash는 문자열 후보 선택용이며 String.op_Equality 재검증이 존재한다.
- 화면 진입 요청과 사용자의 기능 실행 요청을 구분한다.
- XLua wrapper Calls IN은 Lua 노출 근거이지, 특정 Lua 스크립트에서 실제 호출했다는 증거는 아니다.
- 요청 생성 함수의 존재만으로 서버 구현 우선순위를 확정하지 않고, caller 및 사용자 기능 흐름을 확인한다.


## 부록 A. OpInfo::.ctor Calls IN에서 확인한 Request 생성 함수 98개

아래는 Listing에 나타난 함수명과 RVA 원문 인벤토리다. 이름만으로 실제 활성 API나 호출 조건을 판정하지 않는다.

```text
FriendDelete @ 00de0e58
UnlockFashion @ 00ddf484
UpgradeWeapon @ 00ddf614
WeaponLevelUp @ 00de304c
SpaceBaseGetReward @ 00de1228
WeaponReset @ 00de27cc
MailGetReward @ 00de01c4
GetBattleReport @ 00de1ab8
Login @ 00dde818
CreateBatle4Friend @ 00de17bc
CreateBattle @ 00dded04
GetSupportHeroRank @ 00de3890
CreateBattle4SpaceBase @ 00de12e4
SupportHeroShow @ 00de37d4
GetShop4Box @ 00de1d08
SwitchWeapon @ 00ddf058
BuyCrusadeLevel @ 00de2dec
GetExamMyGroupRank @ 00de1884
GetExam @ 00de1638
EquipUpgrade @ 00ddfe74
GetActivities @ 00de1f68
UnlockHero @ 00ddf120
SpaceBaseGet @ 00de10b0
EquipSplit @ 00ddfda0
GetActivitySubReward @ 00de21b4
GetCrusadeAward @ 00de2eb4
ExploreFloorSwapLocation @ 00de2634
GetShops @ 00de1dc4
SweepBattle @ 00ddede0
FriendFind @ 00de0b2c
FriendRecommend @ 00de0f20
SpaceBaseRefresh @ 00de116c
Reported @ 00de33b8
StigmaLoadAndUnload @ 00ddf890
Logout @ 00de3ac4
ExploreFloorGet @ 00de227c
AutoSignIn @ 00de08ec
FriendReject @ 00de0d90
SupportHeroByFree @ 00de3548
LevelUpHero @ 00ddf7a4
GetChapterBoxReward @ 00ddeea8
CloseBattle @ 00ddef84
GetExamTotalRank @ 00de1940
EquipExpand @ 00de2ba0
GetSupportUserHeroRank @ 00de3a08
WearFashion @ 00ddf3bc
StarUpHero @ 00ddf6dc
SupportHeroByItem @ 00de3684
SaveTeam @ 00ddeb40
Equip @ 00ddf1e8
UpgradeStigma @ 00ddfb34
RaiseEquip @ 00de00f0
GetSections @ 00ddea78
AgreeCharge @ 00de156c
DestroyKey @ 00de2d24
OpenMisBox @ 00de05c4
GetMailOlds @ 00de2ae4
GetSupportUserRank @ 00de394c
StigmataCompound @ 00ddf97c
GetTotalReward @ 00de09a8
GetFriends @ 00de0a70
CreateChargeOrder @ 00de0824
CreateBatle4Exam @ 00de1700
FriendAgree @ 00de0cc8
SignInHolidays @ 00de2024
ForgeEquip @ 00ddfcd8
ChangeChatChannle @ 00de3480
SendWorldChat @ 00de3138
WeaponForge @ 00ddf54c
ShopRefresh @ 00de20ec
GetExamFriendRank @ 00de19fc
ShieldAdd @ 00de3228
ExploreFloorReward @ 00de2578
FriendChallenge @ 00de0fe8
CodeExchange @ 00de0428
SetHeadIcon @ 00de04fc
Ping @ 00dde904
GetTeam @ 00ddec48
ChargeEnergy @ 00de06a0
ExploreFloorRefresh @ 00de2710
FriendRequest @ 00de0c00
EquipBatchSplit @ 00ddff48
StigmataSplit @ 00ddfa58
ShieldDel @ 00de32f0
QuestGetReward @ 00ddfc10
CreateBattle4FC @ 00de143c
CreateBattle4ExploreFloor @ 00de24bc
HeroSaveAIStrategy @ 00de2894
ExploreFloorEnter @ 00de2338
CostAKey @ 00de2c5c
GetRecharges @ 00de0768
GetMails @ 00de0298
ExploreFloorChoose @ 00de23f4
SetNickName @ 00de0354
SaveGuideNovice @ 00de1b74
ChapterRead @ 00de2a1c
EquipLockUnlock @ 00de001c
Shopping @ 00de1e80
```

### 부록 판정

- 위 목록은 Request 함수 후보 inventory이며, 기능명 기준의 임시 분류만 가능하다.
- Chat 관련 `ChangeChatChannle`, `SendWorldChat`는 현재 Local Server 조사 우선순위에서 제외한다.
- 다음 단계에서 각 함수의 Calls IN을 따라 실제 진입 화면/버튼/콜백/XLua 경로를 분류한다.


## 9. OpInfo 구조 재확인 — 요청 번호와 데이터 봉투

사용자 질문에 대한 구조적 답변을 위해 Listing getter와 NetworkCenter 송신부를 대조했다.

### 9.1 OpInfo는 단순 Opcode가 아니라 공통 메시지 객체

확인된 getter의 실제 메모리 offset:

| 속성 | offset | 역할에 대한 현재 해석 |
|---|---:|---|
| SerialNumber | +0x10 | 요청/응답 상관관계 식별값 |
| OpCode | +0x14 | 작업 종류 식별자 |
| ReturnCode | +0x18 | 처리 결과 코드 |
| Time | +0x20 | 시간/요청 시각 관련 필드 |
| S_0 | +0x28 | 문자열 슬롯 |
| Int32_0 | +0x30 | 정수 인자 슬롯 |
| Int32_1 | +0x34 | 정수 인자 슬롯 |
| Int32_2 | +0x38 | 정수 인자 슬롯 |
| Int32_3 | +0x3C | 정수 인자 슬롯 |
| Int32_4 | +0x40 | 정수 인자 슬롯 |
| Int64_0 | +0x48 | 64-bit 정수 슬롯 |
| DictI32 | +0x70 | int→int Dictionary |
| User | +0x88 | UserInfo 데이터 |
| Items | +0x98 | Item 데이터 |
| Activities | +0x120 | Activity 데이터 |
| BattleReport | +0x140 | 전투 보고 데이터 |

근거 Listing:
- `015aac5c OpInfo.get_SerialNumber`: `ldr w0,[x0,#0x10]`
- `015aac6c OpInfo.get_OpCode`: `ldrh w0,[x0,#0x14]`
- `015aac7c OpInfo.get_ReturnCode`: getter 주소/offset 목록에서 확인 필요
- `015aad4c OpInfo.get_DictI32`: `ldr x0,[x0,#0x70]`
- `015aad7c OpInfo.get_User`: `ldr x0,[x0,#0x88]`
- `015aad9c OpInfo.get_Items`: `ldr x0,[x0,#0x98]`
- `015aaecc OpInfo.get_Activities`: `ldr x0,[x0,#0x120]`
- `015aaf2c OpInfo.get_BattleReport`: `ldr x0,[x0,#0x140]`

※ 정수/문자열 슬롯의 이름은 IL2CPP에 남아있는 일반화된 속성명이다. 모든 API가 모든 슬롯을 사용하는 것은 아니다. 실제 의미는 개별 Request 함수의 assignment와 응답 소비처로 결정한다.

### 9.2 요청/응답이 같은 OpInfo 형식을 재사용

기존 Listing에서 확인한 연결:

```text
Client Request:
ProtocolGame_SendRequest.<API>
  → OpInfo 생성 및 필드 설정
  → CSBehaviour.RequestOp(OpInfo)
  → NetworkCenter.Send(OpInfo)
  → Request.Req = OpInfo
  → Tube 송신

Server Response:
Tube 수신
  → Request.SetResponse(OpInfo)
  → CSBehaviour.Response(Commands, OpInfo)
  → 등록 callback
  → DataCenter.ProccessRequestRes(OpInfo)
```

따라서 OpInfo는 요청에만 쓰이는 단순 인자 묶음이 아니다. 요청과 응답 양쪽에서 쓰이는 공통 프로토콜 메시지/데이터 봉투에 가깝다. 응답에서는 ReturnCode와 User, Items, Activities, DictI32 등 결과 데이터 필드가 채워질 수 있다.

### 9.3 SerialNumber와 OpCode의 역할 구분

- OpCode: 어떤 명령/기능인지 식별한다.
- SerialNumber: 여러 요청이 오가는 상황에서 특정 응답을 원래 요청과 연결하기 위한 값이다.
- ReturnCode: 처리 결과 상태를 전달하는 필드다.
- 나머지 슬롯/객체 필드: 해당 명령의 입력 인자 또는 응답 데이터다.

기존 PCAP에서 CreateBattle 요청과 응답이 동일 SerialNumber 및 Opcode로 짝지어졌던 관측과 일치한다.

### 9.4 NetworkCenter.Send의 중복 Opcode 처리

`NetworkCenter.Send @ 015b3764` Listing에서:
- 대기 Queue의 Request들을 순회
- 각 Request의 OpInfo를 가져와 +0x14 Opcode 비교
- 동일 Opcode가 발견되면 해당 Request 객체의 virtual method를 호출하는 별도 분기로 진입
- 동일 Opcode가 없으면 SerialNumber counter를 증가시키고 새 OpInfo +0x10에 값을 기록
- Request::.ctor(OpInfo)를 생성한 뒤 Queue에 Enqueue

따라서 NetworkCenter는 요청을 무조건 Queue에 추가하지 않는다. 동일 Opcode가 이미 대기 중일 때의 중복 처리 분기가 있다. 다만 해당 virtual method의 의미(기존 요청 교체/콜백 병합/무시 등)는 아직 함수 포인터 대상을 확인하지 않았으므로 확정하지 않는다.

### 9.5 질문에 대한 결론

사용자 설명 중 “규격화된 정보를 번호로 매핑해 전달한다”는 부분은 맞는 방향이다. 다만 구조를 정확히 표현하면:

- 클라이언트가 Opcode로 요청 종류를 선택한다.
- OpInfo 객체에 SerialNumber, Opcode, 필요한 인자 슬롯을 채운다.
- 서버는 Opcode에 대응하는 요청 규격으로 나머지 payload를 해석한다.
- 서버 응답도 SerialNumber/Opcode 및 결과 필드를 갖춘 OpInfo 구조로 반환된다.
- 클라이언트는 응답의 Opcode와 SerialNumber를 기준으로 대기 중인 Request를 찾아 callback 및 DataCenter 처리로 넘긴다.

즉 **Opcode는 API 라우팅 번호, OpInfo는 공통 메시지 봉투, 각 슬롯은 API별 payload/result**로 이해하는 것이 가장 정확하다. 다만 실제 wire format의 field number와 byte encoding은 protobuf/Commands 계층에서 별도로 확정해야 한다.

## 10. 요청 caller 분류 — 1차 확인

### 10.1 화면 로딩 자동 요청으로 확인된 항목

`GUIScreenLoaderS1.IsSendRequest @ 01693710`의 Calls OUT와 Listing 분기에서 다음 7개가 확인된다.

| Request | Opcode | 진입 조건/경로 |
|---|---:|---|
| GetActivities | 0x06 | 특정 assetName 분기에서 자동 요청 |
| GetMails | 0x2D | 특정 assetName 분기에서 자동 요청 |
| GetShops | 0x33 | 특정 assetName 분기에서 자동 요청 |
| ExploreFloorGet | 0x5E | 특정 assetName 분기에서 자동 요청 |
| SpaceBaseGet | 0x69 | 특정 assetName 분기에서 자동 요청 |
| GetBattleReport | 0x7F | 특정 assetName 분기에서 자동 요청 |
| GetExam | 0x45 | 특정 assetName 분기에서 자동 요청; queryRankID 또는 UserInfo.Id 인자 |

각 분기는 hash 비교만 하는 것이 아니라 `System.String.op_Equality`를 추가로 거친다. 따라서 화면 assetName의 문자열 literal 복원 전에는 화면 이름을 확정하지 않는다.

### 10.2 별도 화면/기능 caller 확인

| Request | 확인된 caller | 분류 |
|---|---|---|
| GetActivities | HomePanelMono.Start | Main 진입 시 Activity 만료 상태일 때 갱신 |
| CreateBattle | HeroBreakMono.HeroBreakBack 및 기존 던전 경로 추적 | 전투/화면 callback 경로 후보. 실제 일반 던전 진입 caller는 별도 추적 중 |
| MailGetReward | XLua/기능 호출 참조 및 메일 기능 흐름 | 사용자 보상 수령 액션 후보; 직접 caller 체인은 추가 확인 |
| GetSections | XLua wrapper 및 여러 기능 함수에서 참조 | 스테이지/Section 조회; 직접 호출 조건은 추가 분류 |
| Shopping | XLua wrapper 및 BattleValueTools.Add 참조 | 구매 동작 후보; 실제 상점 UI caller는 추가 확인 |

### 10.3 호출자 분류의 진행 상태

- OpInfo 생성자 Calls IN에서 Request 함수 98개를 확인했다.
- CSBehaviour.RequestOp Calls IN에서도 해당 Request 함수들이 직접 진입하는 구조를 재확인했다.
- 이 중 7개는 IsSendRequest 화면 자동 요청 분기에서 정적 확인했다.
- GetActivities는 Main 상태 만료에 따른 직접 호출도 확인했다.
- 나머지 Request는 기능명만 보고 사용자 액션이라고 확정하지 않는다. 각각의 Calls IN 및 callback/delegate 체인을 따라가야 한다.
- XLua wrapper는 Lua에 노출된 증거이지 실제 Lua script에서 호출된 증거는 아니다.

다음 단계는 우편/상점/던전/재화·아이템/퀘스트 등 Local Server 범위에서 중요한 API를 먼저 골라 실제 caller와 payload 인자를 연결하는 것이다.
