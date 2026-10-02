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
- 호출자 Listing: `research/Ghidra_Listing_txt/AL/01693710_AliothEngine.GUIScreenLoaderS1__IsSendRequest.txt` 및 `HomePanelMono.Start` 근거 문서. 참고: `research/Ghidra_Listing_txt/PR.txt`는 현재 Git에서 0 byte이므로 Request 함수 본문 근거로 사용하지 않는다.

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

### 10.2 개별 기능 caller 추적 상태

현재 이 단계에서 개별 caller와 요청 함수의 직접 연결을 확정한 항목은 `HomePanelMono.Start → GetActivities`다. 다른 Request 함수에 대해서는 다음 구분을 유지한다.

- `GUIScreenLoaderS1.IsSendRequest`가 호출하는 7개는 화면 자동 요청으로 확인.
- `CSBehaviour.RequestOp` Calls IN은 Request 함수들이 전송 경계에 도달하는 사실을 보여주지만, 각 Request 함수의 상위 UI caller를 알려주지는 않는다.
- `OpInfo::.ctor` 또는 `SingletonBehaviour.get_Instance`의 Calls IN에 특정 Request 함수가 보인다는 사실만으로, 그 함수의 UI caller가 동일 Request를 호출한다고 연결해서는 안 된다.
- 개별 UI caller는 해당 UI 함수의 Listing에서 Request 함수 주소로 직접 연결되는 호출 또는 delegate 체인을 확인한 뒤 확정한다.

### 10.3 호출자 분류의 진행 상태

- OpInfo 생성자 Calls IN에서 Request 함수 98개를 확인했다.
- CSBehaviour.RequestOp Calls IN에서도 해당 Request 함수들이 직접 진입하는 구조를 재확인했다.
- 이 중 7개는 IsSendRequest 화면 자동 요청 분기에서 정적 확인했다.
- GetActivities는 Main 상태 만료에 따른 직접 호출도 확인했다.
- 나머지 Request는 기능명만 보고 사용자 액션이라고 확정하지 않는다. 각각의 Calls IN 및 callback/delegate 체인을 따라가야 한다.
- XLua wrapper는 Lua에 노출된 증거이지 실제 Lua script에서 호출된 증거는 아니다.

다음 단계는 우편/상점/던전/재화·아이템/퀘스트 등 Local Server 범위에서 중요한 API를 먼저 골라 실제 caller와 payload 인자를 연결하는 것이다.


## 11. 2026-10-02 UI 직접 호출 경로 2차 확인

이번 단계는 우편/상점/퀘스트 보상 요청을 대상으로, Request 함수의 Calls IN 또는 UI 함수의 Calls OUT에서 **실제 Request 함수 주소를 호출하는 직접 연결**을 확인했다.

### 11.1 우편 목록과 보상

#### GetMails

- Request: `ProtocolGame_SendRequest.GetMails @ 00de0298`
- 화면 진입: `GUIScreenLoaderS1.IsSendRequest @ 01693710`
- hash `0xB32DDEAC` 뒤 문자열 비교가 통과하면 `AddCodeParamDic(0x2D,...)` 후 `GetMails()` 호출.
- 따라서 현재 Listing에서 확인되는 GetMails의 진입 조건은 우편 관련 화면 assetName의 화면 로딩이다.
- assetName의 실제 문자열은 아직 복원하지 않았으므로 화면 표시명은 확정하지 않는다.

#### MailGetReward

Request: `ProtocolGame_SendRequest.MailGetReward @ 00de01c4`

직접 caller 두 개:

| UI 함수 | RVA | 확인된 호출 동작 |
|---|---:|---|
| `MailMono.ClickGetMail` | 00f9c9e0 | `UIData.data`를 가져와 런타임 타입을 확인한 뒤 객체의 `+0x10` 값을 인자로 전달 |
| `MailMono.ClickAllMail` | 00f9caac | 전역 Mail 관련 객체를 가져와 인자로 전달 |

- `ClickGetMail`은 UIData가 유효하고 기대한 타입일 때만 Request 호출로 이어진다.
- `ClickAllMail`은 별도 동적 UIData 인자를 읽지 않고 전역 객체 참조를 전달한다.
- 두 함수 모두 Listing Calls OUT에 `MailGetReward @ 00de01c4`가 직접 표시된다.
- 현재 확인한 UI Listing만으로 `+0x10` 필드의 정확한 데이터 의미나 전체 수령 요청의 wire payload를 단정하지 않는다.

### 11.2 퀘스트/미션 보상

Request: `ProtocolGame_SendRequest.QuestGetReward @ 00ddfc10`

직접 caller 세 개:

| UI 함수 | RVA | 조건 / 인자 전달 |
|---|---:|---|
| `TrainingCampPanelMono.OnClickReceive` | 0103d508 | `UIData.m_int_1`을 key로 사용. UserInfo의 Dictionary에 key가 존재하고 해당 객체 `+0x1C == 1`일 때 key를 Request 인자로 전달 |
| `TaskNewPanelMono.OnClickRecive` | 00f7d768 | `UIData.data`의 런타임 타입 확인 후 객체 첫 32-bit 값(`ldr w0,[x0]`)을 인자로 전달 |
| `TaoFaPanelMono.OnClickRecive` | 01039ef8 | `TaskNewPanelMono`와 같은 형태로 UIData 객체 타입을 확인한 뒤 첫 32-bit 값을 인자로 전달 |

- 세 함수 모두 Calls OUT에 QuestGetReward 함수 주소가 직접 연결된다.
- TrainingCamp 경로는 Dictionary 존재 여부와 상태값 `1`을 확인한 뒤 요청하므로 단순 버튼 클릭만으로 항상 전송되는 구조는 아니다.
- Task/TaoFa의 첫 32-bit 값이 어떤 도메인 ID인지는 UIData 생성부 및 Request 본문과 추가 대조가 필요하다.

### 11.3 상점 목록과 구매

#### GetShops

- Request: `ProtocolGame_SendRequest.GetShops @ 00de1dc4`
- 화면 로딩 시 `GUIScreenLoaderS1.IsSendRequest`의 hash `0xA8A5DFAC` 및 문자열 비교가 통과하면 `AddCodeParamDic(0x33,...)` 후 GetShops 호출.
- 응답 후처리 함수 후보로 `ShopNewPanelMono.OnGetShopBack @ 0102593c`가 확인되며, 이 함수는 `RefreshUI_Item @ 01025b3c`를 호출한다. 이 연결은 목록 응답 후 UI 갱신 경로의 근거이며, 별도 callback 등록 지점은 추가 확인 대상이다.

#### Shopping

Request: `ProtocolGame_SendRequest.Shopping @ 00de1e80`

직접 caller:
- `ShopConfirmTipsMono.OnClickOK @ 0102408c`

호출 직전 인자 구성:
- 첫 번째 인자: `ShopConfirmTipsMono.get_m_shopId @ 010235ec` 반환값
- 두 번째 인자: `ShopConfirmTipsMono.get_m_shopcommodityData @ 0102324c` 반환 객체의 `+0x78` 32-bit 값
- 세 번째 인자: `ShopConfirmTipsMono.get_m_currentCount @ 01023508` 반환값

최종 호출:
`Shopping(shopId, commodityData[+0x78], currentCount)`

따라서 구매 요청은 상품을 눌렀을 때 즉시 발생하는 것이 아니라, `ShopNewPanelMono.ClickShopItem @ 01026f40`에서 구매 가능/매진/보유량 등의 조건을 검사하고 확인 UI 경로로 진행한 뒤, `ShopConfirmTipsMono.OnClickOK`에서 확인을 누를 때 직접 발생하는 구조다. 두 번째 인자 `commodityData +0x78`의 필드명/도메인 의미는 데이터 클래스 Listing과 대조 전까지 확정하지 않는다.

### 11.4 Request 본문 Listing의 공백과 opcode 판정 주의

- 현재 Git의 `research/Ghidra_Listing_txt/PR.txt`는 실제로 0 byte다.
- 따라서 Request 함수 본문에서 Opcode와 OpInfo payload offset을 재검증할 수 없는 상태다.
- GetMails `0x2D`, GetShops `0x33`, Shopping `0x34` 및 Shopping의 `+0x30/+0x34/+0x38` 계약은 2026-09-29 보고서에 기재된 기존 결과를 참조한다. 이번 단계에서 새로 확인한 직접 근거는 UI caller 및 호출 인자 구성이다.
- MailGetReward와 QuestGetReward의 Opcode 및 Request payload offset은 아직 확인하지 않았다. 이름이나 caller 인자만으로 추정하지 않는다.
- PR Listing 재추출 또는 다른 정확한 Listing 산출물이 Git에 등록되면 Request 함수 본문을 다시 검증한다.

### 11.5 현재 확인된 호출 흐름 요약

```text
우편 목록:
GUIScreenManager._ShowScreen
  → GUIScreenLoaderS1.IsSendRequest
  → GetMails()

우편 보상:
MailMono.ClickGetMail / ClickAllMail
  → MailGetReward(...)

상점 목록:
GUIScreenManager._ShowScreen
  → GUIScreenLoaderS1.IsSendRequest
  → GetShops()
  → ShopNewPanelMono.OnGetShopBack
  → RefreshUI_Item

상점 구매:
ShopNewPanelMono.ClickShopItem
  → 구매 가능 여부 / 매진 등 확인
  → ShopConfirmTipsMono 확인 화면
  → ShopConfirmTipsMono.OnClickOK
  → Shopping(shopId, commodityData[+0x78], currentCount)

퀘스트 보상:
TrainingCampPanelMono.OnClickReceive
TaskNewPanelMono.OnClickRecive
TaoFaPanelMono.OnClickRecive
  → QuestGetReward(...)
```

### 11.6 다음 확인 작업

1. `MailGetReward`, `QuestGetReward` Request 본문 Listing 확보 후 Opcode와 payload offset 확인.
2. `ShopNewPanelMono.OnClickBtn` 및 callback 등록부를 확인해 GetShops / Shopping 응답 handler 연결을 확정.
3. `MailMono`의 UIData 생성 및 응답 callback 등록부를 추적해 단건/전체 수령 인자 구조를 확정.
4. 각 API의 `DataCenter.ProccessRequestRes` opcode 분기와 callback 실행 순서를 연결한다.
