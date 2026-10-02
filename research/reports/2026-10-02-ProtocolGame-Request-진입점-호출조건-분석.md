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
- 호출자 Listing: `research/Ghidra_Listing_txt/AL/01693710_AliothEngine.GUIScreenLoaderS1__IsSendRequest.txt` 및 `HomePanelMono.Start` 근거 문서. 참고: `research/Ghidra_Listing_txt/PR.txt`는 Git main 기준 2,796,159 bytes이며 Request 함수 본문은 13.9에서 직접 분석했다.

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
- `015aac7c OpInfo.get_ReturnCode`: `ldr w0,[x0,#0x18]`
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
Tube 수신 / OpInfo 구성
  → NetworkCenter.TryHandleResponse
  → DataCenter.ProccessRequestRes(response OpInfo) [공유 데이터 병합 경로]
  → Queue.Peek로 대기 Request 확인
  → Request.ID(+0x10) == response.SerialNumber(+0x10) 비교
  → 일치 시 Queue.Dequeue
  → Request.SetResponse(request, response OpInfo)
  → Request에 등록된 callback delegate
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
- `ShopNewPanelMono.OnGetShopBack @ 0102593c`는 `RefreshUI_Item @ 01025b3c`를 호출한다. 다만 Calls IN에 `ShopNewPanelMono.OnClickBtn @ 01029a60`가 확인되므로, 현재는 상점 UI 갱신 루틴으로만 분류한다. GetShops의 네트워크 응답 callback으로 등록되는 지점은 아직 확인되지 않았다.

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

- Git main의 `research/Ghidra_Listing_txt/PR.txt`는 2,796,159 bytes이며, Git blob endpoint에서 본문을 확보해 Request 함수 Listing을 직접 확인했다.
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


### 11.7 우편/상점 후속 UI 경로와 통신 계층 구분

#### 우편 보상 후 갱신

- `MailMono.GetRewardBack @ 00f9cb40`는 `Ali.ShowReward`, `MailMono.InitMailData @ 00f9bb14`, `MailMono.RefreshMailBtn @ 00f9c3b8`를 호출한다.
- `InitMailData`는 메일 목록을 다시 구성하며, Calls OUT에 `ProtocolGame_HttpRequest.POST_GetMailDescAll @ 00dda4c0`가 포함된다.
- 따라서 우편 화면에는 게임 프로토콜 요청(`GetMails`, `MailGetReward`)과 별도로 메일 설명/본문 데이터를 가져오는 HTTP 요청(`POST_GetMailDescAll`)이 공존한다.
- 이 HTTP 요청을 게임 서버의 `MailGetReward` 또는 `GetMails`와 같은 Opcode 요청으로 취급하면 안 된다.
- `GetRewardBack`의 네트워크 callback 등록부는 아직 직접 확인하지 않았으므로, 함수명과 후속 갱신 동작을 근거로 callback 연결을 확정하지 않는다.

#### 상점 UI 갱신

- `ShopNewPanelMono.OnClickBtn @ 01029a60`의 Calls OUT에 `ShopNewPanelMono.OnGetShopBack @ 0102593c`가 직접 포함된다.
- `OnGetShopBack`은 `RefreshUI_Item @ 01025b3c`를 호출한다.
- 이 관계는 상점 버튼 처리 중 내부 UI 갱신 경로가 존재한다는 뜻이다. GetShops 응답이 이 함수로 직접 callback된다는 등록 증거는 아직 없으므로, 네트워크 response handler로 분류하지 않는다.
- `ShopNewPanelMono.OnShoppingCallback @ 0102ac50`는 `Ali.ShowReward`, 상품 UI 갱신 함수를 호출하지만, 이번 단계에서는 Shopping 요청과 해당 callback을 연결하는 delegate 등록 지점을 확인하지 못했다. 별도 추적 대상으로 남긴다.


## 12. 2026-10-02 응답 처리 순서 재검증

### 12.1 NetworkCenter.TryHandleResponse의 실제 순서

Listing: `research/Ghidra_Listing_txt/AL/015b41e0_Alioth.S1.Net.NetworkCenter__TryHandleResponse.txt`

Calls OUT 및 본문에서 확인한 순서:

1. Tube 응답 목록을 순회하고 응답 OpInfo를 얻는다.
2. 유효한 응답 객체가 확보된 경로에서 `DataCenter.ProccessRequestRes(response)`를 호출한다. 이 호출은 응답 Queue의 Request ID 대조보다 앞선다. 해당 분기에는 `w20 < 5` 조건이 있으나, w20의 의미는 아직 확정하지 않는다.
3. 대기 Request Queue에서 `Peek`로 선두 Request를 확인한다.
4. 응답 OpInfo의 `+0x10` SerialNumber와 Request의 `get_ID` 값을 비교한다.
5. 두 값이 일치하면 Queue에서 Request를 `Dequeue`한다.
6. `Request.SetResponse(request, response OpInfo)`를 호출한다.
7. Request 객체에 보관된 callback delegate를 호출하고 마지막 활성 시간을 갱신한다.

### 12.2 SerialNumber 비교의 근거

- 응답: `TryHandleResponse`에서 response 객체의 `+0x10` 값을 읽는다.
- Request: `Request.get_ID @ 015b45b4`는 `ldr w0,[x19,#0x10]`으로 ID를 반환한다.
- 비교: `TryHandleResponse @ 015b4460-015b4470`에서 두 값을 비교하고 불일치하면 Dequeue/SetResponse로 진행하지 않는다.
- 일치한 경우에만 Queue.Dequeue 후 `Request.SetResponse @ 015b461c`가 실행된다.

즉 SerialNumber는 응답과 요청을 연결하는 상관관계 값이며, Queue 선두 Request와 일치해야 해당 Request의 완료 callback이 실행된다.

### 12.3 Request.SetResponse의 역할

Listing: `research/Ghidra_Listing_txt/AL/015b461c_Alioth.S1.Net.Request__SetResponse.txt`

- `Request.SetResponse(request, OpInfo)`는 Request의 `Res`에 응답 OpInfo를 설정한다.
- 이어서 현재 시간을 얻어 `FinishAt`을 설정한다.
- `Request.SetResponse` 자체는 Res와 FinishAt을 설정한다.
- 그 다음 `NetworkCenter.TryHandleResponse`는 NetworkCenter 인스턴스의 `+0x38`에 보관된 delegate 구조체를 통해 간접 callback을 호출한다. Listing상 이 필드는 TryHandleResponse의 `x19`(NetworkCenter) 기준으로 읽힌다.
- 따라서 이를 "Request 객체 내부 callback"이라고 부르면 안 된다.
- 이 delegate의 실제 target이 `DataCenter.RequestCallback`인지, 다른 중계 함수인지 직접 delegate 생성/대입 지점을 추가 확인해야 한다. 현재 `DataCenter.RequestCallback`은 응답 Request의 IsClientProccessed 설정 및 `Ali.DataProccessCallBack` 호출을 수행하는 별도 확인된 dispatcher다.

### 12.4 DataCenter.ProccessRequestRes의 역할

Listing: `research/Ghidra_Listing_txt/DA.txt`, `DataCenter.ProccessRequestRes @ 016e203c`

- 첫 번째 인자(OpInfo)를 x26에 보관하고 여러 응답 필드/컬렉션을 처리한다.
- Calls OUT에 다음 데이터 병합/갱신 함수가 포함된다.
  - `UserInfo.MergeVaryData`
  - `DataCenter.MergeItem`
  - `DataCenter.MergeEquip`
  - `DataCenter.MergeWeapon`
  - `DataCenter.MergeSections`
  - `DataCenter.MergeSectionSnapShot`
  - `DataCenter.UpdateHeroInfo`
  - `DataCenter.Merge<int,object>`, `Merge<object,object>`, `Merge<long,object>`
- 따라서 이 함수는 개별 UI 버튼의 완료 callback이라기보다 응답 OpInfo에 담긴 공통/도메인 데이터를 전역 DataCenter 및 UserInfo 상태에 반영하는 중앙 병합 단계로 분류한다.
- 응답의 모든 필드가 매번 존재한다고 가정하지 않는다. 실제 함수에는 null/length/타입 조건 분기가 다수 존재한다.

### 12.5 전역 완료 callback 등록 API

Listing: `DataCenter.RegisterDataProccessCallBack @ 016e68b0`

- 이 함수는 `DataCenter.add_OnProccessRequestFinish`를 호출해 전역 완료 이벤트에 delegate를 추가한다.
- Calls IN에는 XLua wrapper가 표시된다. 현재 정적 Listing만으로 실제 Lua 코드의 등록 시점이나 등록 delegate의 의미는 알 수 없다.
- 따라서 이 전역 이벤트와 개별 Request 객체의 callback delegate는 별도 개념으로 유지한다. 실제 연결 여부는 후속 추적 대상이다.

### 12.6 서버 구현에 반영할 순서

```text
응답 수신
  → OpInfo 복원
  → DataCenter 공통 데이터 병합
  → 대기 Request 선두의 ID와 SerialNumber 비교
  → 일치 시 Dequeue
  → Request.Res / FinishAt 설정
  → Request별 callback 실행
```

이 순서는 기존 9.2 절의 응답 흐름을 대체한다. 특히 DataCenter 병합이 Request별 callback보다 먼저 실행된다는 점을 서버 구현 순서에 반영한다.


## 13. 2026-10-02 Opcode별 응답 callback 등록부 추적

이번 단계에서는 Request 본문(PR Listing)이 비어 있는 상태에서, UI가 등록하는 응답 callback의 opcode key를 추적했다. 이는 응답 dispatch key를 확인하는 근거이며, Request 함수 내부의 `OpInfo +0x14` 대입 명령을 직접 확인한 것과는 증거 수준을 구분한다.

### 13.1 공통 callback registry

#### BaseMono → Ali.RegisterDataProccessCallBack

- 화면별 `BaseMono.RegisterDataProccessCallBack @ 00e1a5c0` 호출은 `Ali.RegisterDataProccessCallBack @ 00e03ac8`로 연결된다.
- `Ali.RegisterDataProccessCallBack`은 두 번째 인자 `w1`을 `Int16Enum` key로 사용해 `Dictionary<Int16Enum, object>`에 `NetEvent` 객체를 등록한다.
- 이미 key가 존재하면 해당 항목을 가져와 callback을 추가하는 분기가 있다. 새 key면 `NetEvent::.ctor`를 만든 뒤 dictionary에 넣는다.
- 따라서 UI 함수의 `RegisterDataProccessCallBack(code, delegate)`에서 code는 응답 이벤트를 찾는 opcode key로 기능한다.

#### 응답 처리 dispatcher

- `DataCenter.RequestCallback @ 016e1f44`는 Request의 `IsClientProccessed`를 true로 설정한 뒤 `Ali.DataProccessCallBack`을 호출한다.
- `Ali.DataProccessCallBack @ 00e03dd4`는 Request의 `Res`를 얻고, 응답 OpInfo의 `+0x14`에서 opcode를 읽는 경로를 가진다.
- 이 opcode로 `Ali.RegisterDataProccessCallBack`이 구성한 Dictionary를 조회하고, 해당 `NetEvent.callBack`을 호출한다.
- 일부 opcode는 `GUIScreenManager.RequsetBack` 분기로도 처리된다.
- 이 구조는 UI callback이 Request 함수마다 개별 등록되는 방식만 있는 것이 아니라, **응답 OpCode를 key로 한 공용 callback registry**를 사용한다는 근거다.

### 13.2 우편 callback key

Listing: `MailMono.RegisterCallBack @ 00f99e2c` (`MA.txt`)

- `Ali.OnProccessRequestFinish::.ctor`로 delegate를 만든 뒤 `BaseMono.RegisterDataProccessCallBack`을 호출한다.
- 첫 번째 등록 key: `0x2E`
- 두 번째 등록 key: `0x68`
- 별도로 `BaseMono.RegisterHttpRequestCallBack` 및 `Ali.OnHttpRequestFinish::.ctor`도 호출한다. 우편 화면의 게임 프로토콜 응답과 HTTP 응답 callback 등록은 구분해야 한다.
- 우편 UI의 직접 Request caller는 `MailMono.ClickGetMail / ClickAllMail → MailGetReward @ 00de01c4`로 확인돼 있다.
- 따라서 `0x2E`는 MailGetReward 응답 callback key와 대응하는 유력 후보로 분류한다.
- 동일 클래스의 `MailMono.GetRewardBack @ 00f9cb40`는 `Ali.ShowReward`, `InitMailData`, `RefreshMailBtn`을 호출하는 응답 후처리 후보 함수다. `0x2E` 등록 delegate의 실제 method pointer와 이 함수 주소를 직접 대조하지는 못했으므로 handler 연결은 강한 후보로 남긴다.
- `0x68`은 우편 화면의 별도 응답 key다. Request inventory에 `GetMailOlds @ 00de2ae4`가 있으나, callback delegate target을 직접 대조하기 전에는 이 함수와의 매핑을 확정하지 않는다.

### 13.3 퀘스트 보상 callback key

#### TaskNewPanelMono

Listing: `TaskNewPanelMono.Start @ 00f7a170` (`TA.txt`)

- `Ali.OnProccessRequestFinish::.ctor`로 delegate 생성
- `BaseMono.RegisterDataProccessCallBack(0x30, delegate)` 호출
- 같은 TaskNewPanelMono의 `OnClickRecive @ 00f7d768`는 `QuestGetReward @ 00ddfc10`를 직접 호출한다.
- 같은 클래스의 `NetGetQuestReward @ 00f7d01c`는 `Ali.ShowReward`, `RefreshData`, `RefreshUI`, 완료 팁 갱신을 수행하는 응답 후처리 후보 함수다.

#### TrainingCampPanelMono

Listing: `TrainingCampPanelMono.RegisterCallBack @ 0103bbfc` (`TR.txt`)

- `Ali.OnProccessRequestFinish::.ctor`로 delegate 생성
- `BaseMono.RegisterDataProccessCallBack(0x30, delegate)` 호출
- 같은 화면의 `OnClickReceive @ 0103d508`는 조건 검사 후 `QuestGetReward @ 00ddfc10`를 직접 호출한다.
- 같은 클래스의 `QuestGetRewardBack @ 0103bd3c`는 `Ali.ShowReward`와 `RefreshUI`를 호출한다. 메서드 이름, 동일 화면의 0x30 등록, 보상 Request 직접 caller가 함께 존재하므로 QuestGetReward 응답 handler 후보로 강하게 연결된다.

#### TaoFaPanelMono

Listing: `TaoFaPanelMono.RegisterCallBack @ 01035d28` (`TA.txt`)

- 응답 key `0x7D`, `0x7C`, `0x30`에 대해 각각 callback 등록
- 같은 화면의 `OnClickRecive @ 01039ef8`는 `QuestGetReward @ 00ddfc10`를 직접 호출한다.
- 같은 클래스의 `NetGetQuestReward @ 01038118`는 `Ali.ShowReward`, `RefreshTask`, `RefreshItemShow`, `RefreshMainData` 등을 수행하는 응답 후처리 후보 함수다.

#### Opcode 판정 수준

- 세 화면이 공통으로 등록하는 key `0x30`과 각 화면의 QuestGetReward 직접 호출 관계를 함께 보면, QuestGetReward의 응답 opcode는 `0x30`일 가능성이 높다.
- 다만 callback target의 함수 포인터를 Request 응답과 직접 결합하거나 Request 본문의 `OpInfo +0x14` 대입을 확인하지 못했으므로 현재는 **유력 후보**로 기록한다.

### 13.4 상점 구매 callback key

Listing: `ShopNewPanelMono.Awake @ 010285d4` (`SH.txt`)

- `BaseMono.RegisterDataProccessCallBack(0x34, delegate)`
- `BaseMono.RegisterDataProccessCallBack(0x5C, delegate)`
- 같은 화면의 구매 확인 함수 `ShopConfirmTipsMono.OnClickOK @ 0102408c`는 `Shopping @ 00de1e80`을 직접 호출한다.
- 기존 2026-09-29 Request 분석에서 Shopping의 Opcode는 `0x34`, payload는 u32 3개(`OpInfo +0x30/+0x34/+0x38`)로 확인돼 있다.
- 따라서 ShopNewPanelMono의 `0x34` callback 등록은 Shopping 응답 경로와 일치한다.
- `ShopNewPanelMono.OnShoppingCallback @ 0102ac50`는 `Ali.ShowReward`, `RefreshUI_Item`, `RefreshUI_Recharge`를 수행하는 구매 응답 후처리 후보 함수다. 동일 화면이 0x34 callback을 등록하고 Shopping Request가 0x34인 점과 기능 흐름이 맞지만, delegate의 실제 method pointer를 직접 확인하지 못했으므로 target 연결은 강한 후보로만 둔다.
- `0x5C`는 별도 상점 화면 응답 key이며, 현재는 특정 Request 함수에 매핑하지 않는다.

### 13.5 현재까지의 Opcode / payload 판정표

| Request | 직접 UI caller | 응답 callback key | Request payload |
|---|---|---:|---|
| MailGetReward | MailMono.ClickGetMail / ClickAllMail | 0x2E 직접 확인 | 관리 객체 참조: OpInfo +0x28 |
| QuestGetReward | TrainingCamp / TaskNew / TaoFa 보상 클릭 | 0x30 직접 확인 | int32: OpInfo +0x30 |
| Shopping | ShopConfirmTipsMono.OnClickOK / BoxShopMonoNew.SendBuyBox | 0x34 직접 확인 | int32 3개: +0x30/+0x34/+0x38 |
| GetMails | 화면 로더 자동 요청 | 별도 화면/공용 callback 경로 추가 확인 필요 | 무인자 요청으로 기존 분류, 본문 재검증은 보류 |
| GetShops | 화면 로더 자동 요청 | 0x34/0x5C와 별개인지 확인 필요 | 무인자 요청으로 기존 분류, 본문 재검증은 보류 |

### 13.6 Request callback과 UI opcode callback은 구분

현재 확인된 레이어:

```text
NetworkCenter.TryHandleResponse
  → Request.SetResponse(Res, FinishAt 설정)
  → NetworkCenter 인스턴스 +0x38 delegate 간접 호출
      [delegate target은 아직 미확정]

별도 확인된 DataCenter 응답 dispatch:
DataCenter.RequestCallback
  → Request.IsClientProccessed = true
  → Ali.DataProccessCallBack
  → response OpInfo +0x14 opcode 읽기
  → opcode key로 NetEvent Dictionary 조회
  → 등록된 UI callback 실행
```

두 경로의 연결 delegate target은 아직 확정하지 않는다. NetworkCenter의 `+0x38` delegate 생성/대입 지점을 추가 확인해야 한다.

### 13.7 Request payload 미확정 사유와 다음 단계

- PR Listing에서 `MailGetReward`, `QuestGetReward`, `Shopping`의 opcode 및 payload 대입 offset을 확인했다(13.9 참조).
- UI caller에서 얻는 값은 다음과 같다.
  - Mail 단건: `BaseMono.GetUIData` → `UIData.get_data` → data 객체의 `+0x10`에서 포인터 크기 참조를 읽어 Request 인자로 전달
  - Mail 전체: Mail 관련 전역 객체 참조를 첫 인자로 전달
  - Quest/Task/TaoFa: UIData payload 객체의 첫 32-bit 값을 Request 인자로 전달
  - TrainingCamp: UserInfo Dictionary의 key를 조건 충족 시 Request 인자로 전달
- Request 본문에서 저장 슬롯은 13.9에 따라 확인됐다. Mail 인자의 내부 의미는 객체 구조를 추가 확인해야 한다.
- 후속 작업은 각 caller가 전달하는 인자의 의미를 복구하고, 응답 callback delegate의 실제 target pointer를 연결하는 것이다.


### 13.8 응답 후처리 함수 후보 추가 확인

응답 key 등록부와 동일 화면 클래스의 보상/갱신 메서드를 대조했다.

| 응답 key 후보 | 화면/클래스 | 후처리 메서드 | 근거 |
|---:|---|---|---|
| 0x2E | MailMono | `GetRewardBack @ 00f9cb40` | ShowReward + InitMailData + RefreshMailBtn |
| 0x30 | TrainingCampPanelMono | `QuestGetRewardBack @ 0103bd3c` | ShowReward + RefreshUI |
| 0x30 | TaskNewPanelMono | `NetGetQuestReward @ 00f7d01c` | ShowReward + RefreshData + RefreshUI + 완료 팁 |
| 0x30 | TaoFaPanelMono | `NetGetQuestReward @ 01038118` | ShowReward + RefreshTask + RefreshItemShow + RefreshMainData |
| 0x34 | ShopNewPanelMono | `OnShoppingCallback @ 0102ac50` | ShowReward + RefreshUI_Item + RefreshUI_Recharge |

- 이 함수들은 각 화면의 callback 등록 key와 직접 Request caller의 기능이 일치하는 응답 후처리 후보들이다.
- Ghidra Calls IN은 delegate 기반 호출을 누락할 수 있으므로 Calls IN이 비어 있다는 사실만으로 callback이 아니라고 판단하지 않는다.
- 반대로 callback key와 같은 클래스에 있다는 사실만으로 delegate target이 확정되는 것도 아니다. 정확한 delegate method pointer가 복원되기 전까지는 "후처리 후보"로 기록한다.
- 특히 TrainingCampPanelMono의 `QuestGetRewardBack`은 함수명과 보상 표시/화면 갱신 동작이 0x30 등록 및 QuestGetReward 호출과 일관된다.


### 13.9 PR.txt 본문 재확보 및 Request payload 확정 (2026-10-03)

#### 파일 확인 정정
- GitHub main의 `research/Ghidra_Listing_txt/PR.txt` 크기: **2,796,159 bytes**. Blob SHA: `67cdea09bf6a252864b6e6a7b7d4eb270167c111`.
- 일반 fetch는 대용량 본문을 빈 문자열로 반환했으나 Git blob endpoint에서 Listing 원문을 확보했다. 과거의 “PR.txt 0 byte” 기록은 폐기한다.

#### MailGetReward @ 00de01c4
- `mov x19,x0`로 첫 인자 보존, `OpInfo::.ctor` 호출 후 `str x19,[x0,#0x28]!`로 OpInfo `+0x28`에 저장.
- `mov w8,#0x2e`와 `sturh w8,[x0,#-0x14]`의 주소 계산 결과 OpInfo `+0x14`에 opcode `0x2E` 저장.
- 따라서 payload는 32-bit ID가 아니라 첫 번째 관리 객체 참조 1개다. 객체 내부 식별자의 의미는 caller/객체 구조 추가 확인이 필요하다.

#### QuestGetReward @ 00ddfc10
- `mov w19,w0`로 첫 인자 32-bit 값을 보존.
- `strh w8,[x20,#0x14]` (w8=`0x30`)으로 opcode `0x30` 저장.
- `str w19,[x20,#0x30]`으로 int32 payload 1개를 OpInfo `+0x30`에 저장.

#### Shopping @ 00de1e80
- `mov w21,w0`, `mov w20,w1`, `mov w19,w2`로 인자 3개를 각각 32-bit로 보존.
- `strh w8,[x22,#0x14]` (w8=`0x34`)으로 opcode `0x34` 저장.
- `stp w21,w20,[x22,#0x30]` 및 `str w19,[x22,#0x38]`로 int32 3개를 `+0x30/+0x34/+0x38`에 저장.
- Calls IN에는 `ShopConfirmTipsMono.OnClickOK @ 0102408c` 외에 `BoxShopMonoNew.SendBuyBox @ 00e9a0a0`도 있다.

#### 확정된 Request 계약
| Request | Opcode | OpInfo payload | 타입/개수 |
|---|---:|---|---|
| MailGetReward | `0x2E` | `+0x28` | 관리 객체 참조 1개 |
| QuestGetReward | `0x30` | `+0x30` | int32 1개 |
| Shopping | `0x34` | `+0x30/+0x34/+0x38` | int32 3개 |

위 opcode와 저장 offset은 PR Listing 직접 근거로 확정했다. Mail 객체 참조의 내부 의미 및 응답 delegate target pointer는 후속 분석 대상이다.


### 13.10 NetworkCenter +0x38 delegate 생성 및 호출 인자 재검증

대상 Listing: `Alioth.S1.Net.NetworkCenter::.ctor @ 015b2f70`, `NetworkCenter.TryHandleResponse @ 015b41e0` (Git `research/Ghidra_Listing_txt/AL.txt`).

- Constructor Calls OUT에 `System.Action<Int32Enum, ByteEnum, object>::.ctor @ 01911170`가 나타난다.
- Constructor의 `015b3208–015b3234` 구간에서 Action delegate를 생성하고, `015b3240–015b324c`의 pre-index store로 NetworkCenter 인스턴스 `+0x38`에 delegate 객체를 저장한다.
- `TryHandleResponse`의 `015b4498–015b44b8` 구간은 NetworkCenter `+0x38` delegate에서 method pointer/target을 읽어 간접 호출한다.
- 호출 인자는 `w1=2`, `w2=[sp+0x44]`의 byte 값, `x3=x20`의 Request 객체다. 따라서 `+0x38`은 Request 하나만 받는 단순 callback이 아니라 `Action<Int32Enum, ByteEnum, object>` 형태의 3인자 delegate다.
- 이 시그니처만으로 `DataCenter.RequestCallback(Request)`와 동일한 메서드라고 볼 수 없다. delegate target과 method pointer가 가리키는 실제 메서드 본문을 별도로 추적해야 한다.

**정정:** `NetworkCenter +0x38` delegate와 `DataCenter.RequestCallback` / `Ali.DataProccessCallBack` 사이의 직접 연결은 확인되지 않았다. 현재는 NetworkCenter의 3인자 응답 이벤트 delegate와 opcode 기반 UI callback dispatcher를 별도 레이어로 유지한다.


### 13.11 MailGetReward caller 인자 타입 재확인

대상 Listing: `MailMono.ClickGetMail @ 00f9c9e0`, `MailMono.ClickAllMail @ 00f9caac` (`MA.txt`).

- 단건 수령은 `BaseMono.GetUIData` 호출 후 `UIData.get_data @ 00eace88`를 호출한다. 반환 객체의 `+0x10`에서 `ldr x0`로 64-bit 포인터 크기 값을 읽어 `MailGetReward` 첫 번째 인자로 전달한다.
- 전체 수령은 전역 정적 참조에서 객체 포인터를 `ldr x0,[x8]`로 읽어 `MailGetReward` 첫 번째 인자로 전달한다.
- `MailGetReward @ 00de01c4`는 그 첫 인자를 `str x19,[x0,#0x28]!`로 OpInfo `+0x28`에 그대로 저장한다.

**정정:** 단건 우편의 `UIData.data +0x10` 값은 Listing상 `ldr x0`로 읽는 포인터 크기 값이다. 이전의 “32-bit 값” 표기는 잘못됐으므로 폐기한다. 현재 근거로는 Mail 객체 참조로 판단하지만, 참조 대상의 구체 클래스명과 내부 ID 필드는 별도 확인이 필요하다.


### 13.12 OnProccessRequestFinish delegate wrapper 구조 확인 (2026-10-03)

대상 Listing:
- `Ali.OnProccessRequestFinish::.ctor @ 00e110fc`
- `Ali.OnProccessRequestFinish::Invoke @ 00e111e0`
- 등록부: `MailMono.RegisterCallBack @ 00f99e2c`, `TaskNewPanelMono.Start @ 00f7a170`, `TrainingCampPanelMono.RegisterCallBack @ 0103bbfc`, `TaoFaPanelMono.RegisterCallBack @ 01035d28`, `ShopNewPanelMono.Awake @ 010285d4`.

#### 공통 delegate wrapper

`OnProccessRequestFinish::.ctor`는 호출 인자를 다음처럼 보관한다.
- 생성자 x1: callback target 객체 → wrapper `+0x20`
- 생성자 x2: callback method metadata/pointer → wrapper `+0x28`
- `+0x18`: Invoke에서 사용할 실제 호출 thunk 주소
- `+0x40`: 호출 target 객체 참조

`OnProccessRequestFinish::Invoke` Listing:
- `ldr x8,[x0,#0x40]`: target 객체 로드
- `ldr x3,[x0,#0x18]`: 호출 thunk 로드
- `ldr x2,[x0,#0x28]`: 등록된 method metadata/pointer 로드
- `mov x0,x8`; `br x3`: target 및 method 정보를 사용해 간접 호출

즉, 각 UI 클래스의 등록 callback은 일반 함수 주소를 직접 Dictionary에 넣는 구조가 아니라, target 객체와 method metadata를 감싼 `OnProccessRequestFinish` wrapper를 생성해 등록하는 형태다.

#### 화면별 등록 key 확인

| 화면 | 등록 key | 생성 wrapper target | method metadata |
|---|---:|---|---|
| MailMono | 0x2E, 0x68 | MailMono 인스턴스 | 정적 메타데이터 슬롯에서 로드 |
| TaskNewPanelMono | 0x30 | TaskNewPanelMono 인스턴스 | 정적 메타데이터 슬롯에서 로드 |
| TrainingCampPanelMono | 0x30 | TrainingCampPanelMono 인스턴스 | 정적 메타데이터 슬롯에서 로드 |
| TaoFaPanelMono | 0x7D, 0x7C, 0x30 | TaoFaPanelMono 인스턴스 | 각 등록마다 별도 정적 메타데이터 슬롯 |
| ShopNewPanelMono | 0x34, 0x5C | ShopNewPanelMono 인스턴스 | 각 등록마다 별도 정적 메타데이터 슬롯 |

각 등록부에서 `OnProccessRequestFinish::.ctor`에 화면 인스턴스(x1)와 정적 데이터 슬롯에서 읽은 method metadata(x2)를 전달하는 것은 직접 확인했다. 그러나 현재 Listing에는 해당 정적 슬롯의 최종 값이 함수 주소/메서드명으로 해석되어 있지 않으므로, 아래 함수들과 wrapper를 직접 연결하는 것은 아직 불가능하다.
- `MailMono.GetRewardBack @ 00f9cb40`
- `TrainingCampPanelMono.QuestGetRewardBack @ 0103bd3c`
- `TaskNewPanelMono.NetGetQuestReward @ 00f7d01c`
- `TaoFaPanelMono.NetGetQuestReward @ 01038118`
- `ShopNewPanelMono.OnShoppingCallback @ 0102ac50`

따라서 이 함수들은 등록 key와 기능이 일치하는 **응답 후처리 후보**로 유지한다. 이번 단계에서 wrapper의 동적 호출 구조는 확인했지만, 실제 method pointer가 위 후보 중 하나라는 점까지 확정한 것은 아니다.

#### NetworkCenter +0x38과의 관계

- `NetworkCenter::.ctor @ 015b2f70`은 `Action<Int32Enum, ByteEnum, object>` delegate를 생성해 인스턴스 `+0x38`에 저장한다.
- `TryHandleResponse @ 015b41e0`는 응답 Request 처리 완료 후 이 delegate를 간접 호출한다. 인자는 `w1=2`, `w2=response 상태 byte`, `x3=Request 객체`.
- 이 delegate는 `OnProccessRequestFinish`와 별도 타입/호출 규약이다. 현재 근거로는 UI opcode callback wrapper와 동일한 delegate라고 볼 수 없다.
- `DataCenter.RequestCallback @ 016e1f44` → `Ali.DataProccessCallBack @ 00e03dd4` 경로는 별도 opcode 기반 UI callback dispatcher로 유지한다. NetworkCenter `+0x38`에서 이 dispatcher로 이어지는 직접 연결은 아직 확인되지 않았다.

**이번 단계 결론:** callback wrapper의 target/method metadata 저장 방식과 화면별 opcode 등록은 확인했다. 실제 target method 주소를 확정하려면 정적 메타데이터 슬롯이 가리키는 IL2CPP MethodInfo/함수 포인터를 해석할 수 있는 메타데이터 또는 런타임 delegate dump가 추가로 필요하다.


### 13.13 NetworkCenter 생성 delegate의 람다 후보 (2026-10-03)

#### 생성자에서 확인한 구성

Listing: `NetworkCenter::.ctor @ 015b2f70`

- `015b3208`: static metadata slot 주소를 구성하고 `ldr x2,[x8]`로 delegate method metadata 인자를 읽는다.
- `015b3210`: `x1=x24`로 target 객체를 전달한다.
- `015b321c`: `x2`에 method metadata, `x3=0`을 둔 뒤 `System.Action<Int32Enum, ByteEnum, object>::.ctor @ 01911170` 호출.
- 생성된 delegate 객체는 `015b3240–015b324c`에서 NetworkCenter 인스턴스 `+0x38`에 저장된다.

#### 클래스의 생성 람다

Listing: `NetworkCenter.<>c$$<.ctor>b__26_0 @ 015b484c`

```asm
015b484c  ret
```

- 클래스 내부에서 확인되는 생성 람다 `b__26_0`은 본문이 `ret` 한 줄이다.
- 생성자 delegate 구성부의 target 객체가 `NetworkCenter.<>c` singleton 경로를 거치는 점과 시그니처/생성 흐름은 이 람다와 부합한다.
- 다만 `015b3208`에서 읽는 static metadata slot의 런타임 값과 `b__26_0`의 MethodInfo 주소를 직접 대조하지 못했다. 따라서 이 람다가 `+0x38` delegate의 실제 target method라고 확정하지 않는다.

#### 응답 완료 시 호출

Listing: `NetworkCenter.TryHandleResponse @ 015b41e0`

- `015b4498–015b44b8`: NetworkCenter `+0x38` delegate의 method pointer/target을 읽어 간접 호출.
- 정상 완료 분기의 인자: `w1=2`, `w2=[sp+0x44]`의 응답 상태 byte, `x3=x20`의 Request 객체.
- 연결 종료/실패 분기는 별도 호출 경로에서 `w1=1`을 전달한다.
- 이 callback이 빈 람다라면 현재 Listing상 응답 완료 알림 자체는 UI 후처리를 수행하지 않는다. 다만 위 메서드 포인터 대조가 끝나기 전까지는 조건부 해석으로 남긴다.

#### UI callback wrapper와의 구분

- UI 등록부는 `Ali.OnProccessRequestFinish::.ctor @ 00e110fc`를 호출한다.
- wrapper는 target 객체를 `+0x20`, method metadata/pointer를 `+0x28`에 보관하고, `Invoke @ 00e111e0`에서 `br x3`로 동적 호출한다.
- 화면별 등록 key는 `Mail 0x2E`, `TaskNew/TrainingCamp/TaoFa 0x30`, `Shop 0x34`로 Request opcode와 대응한다.
- 따라서 NetworkCenter `+0x38` Action과 화면별 `OnProccessRequestFinish` wrapper는 서로 다른 callback 계층이다. UI 후처리 target을 확정하려면 각 등록부가 읽는 static metadata slot의 실제 MethodInfo를 복원해야 한다.

**이번 단계 판정:** NetworkCenter `+0x38` delegate의 생성/저장/호출 시그니처는 확인했다. 클래스 내 no-op 람다 후보도 찾았으나 method metadata slot과의 직접 대조는 미완료다. UI opcode callback wrapper의 실제 target method 역시 미확정으로 유지한다.


### 13.14 Request 생성/응답 설정 시 별도 XLua hook 확인 (2026-10-03)

대상 Listing:
- `Request::.ctor @ 015b3c1c`
- `Request.SetResponse @ 015b461c`
- 두 함수 모두 `AL.txt`에서 확인.

#### Request 생성 hook

`Request::.ctor`는 OpInfo를 받아 ID(`OpInfo +0x10`)와 Req를 설정한 뒤, 별도 static/singleton 경로에서 `+0x80` callback slot을 읽는다.

- callback slot이 null이면 생성자 기본 경로로 종료한다.
- null이 아니면 `XLua.DelegateBridge.__Gen_Delegate_Imp14`로 tail-call하며 인자로 Request 객체와 원본 OpInfo를 전달한다.
- 따라서 런타임에서 hook이 설정된 경우 Request 생성 후처리는 XLua delegate에 위임될 수 있다.

#### 응답 설정 hook

`Request.SetResponse`도 유사한 구조다.

- 별도 static/singleton 경로에서 `+0x88` callback slot을 확인한다.
- null이 아니면 `XLua.DelegateBridge.__Gen_Delegate_Imp14`로 Request 객체와 응답 OpInfo를 전달하고 tail-call한다.
- null인 경우에만 기본 경로에서 `Request.set_Res(response)`와 `Request.set_FinishAt(DateTime.Now)`를 수행한다.

**주의:** 두 callback slot이 속한 singleton의 구체 타입 및 런타임 등록 주체는 아직 식별하지 못했다. 따라서 이 hook을 `DataCenter.RequestCallback` 또는 NetworkCenter `+0x38` delegate와 동일시하지 않는다. 다만 Request 생성/응답 설정 단계에 별도의 XLua 확장 지점이 존재한다는 점은 확인됐다.

#### 응답 처리 흐름에 대한 영향

현재 정적 근거로는 아래 계층을 분리해야 한다.

```text
NetworkCenter.TryHandleResponse
  ├─ DataCenter.ProccessRequestRes(response)
  │    └─ 공통 데이터 병합 / Notify 등
  ├─ SerialNumber 대조 후 Queue.Dequeue
  ├─ Request.SetResponse(response)
  │    ├─ hook 설정 시 XLua delegate에 위임
  │    └─ hook 미설정 시 Res / FinishAt 기본 저장
  └─ NetworkCenter +0x38 Action<Int32Enum, ByteEnum, object>
       └─ 응답 완료 이벤트 호출

DataCenter.RequestCallback(request)
  └─ Request.IsClientProccessed = true
  └─ Ali.DataProccessCallBack(request.Res의 opcode 기준 UI callback dispatch)
```

- `DataCenter.ProccessRequestRes`의 Calls OUT에는 `Ali.DataProccessCallBack` 또는 `DataCenter.RequestCallback` 호출이 없다. 확인된 주 기능은 응답 데이터의 공통 병합/갱신이다.
- 따라서 `ProccessRequestRes`가 곧바로 화면별 opcode callback을 실행한다고 쓰면 안 된다.
- Request hook의 런타임 설정 여부를 확인하기 전까지, `DataCenter.RequestCallback`이 어느 지점에서 호출되는지는 미확정으로 유지한다.

**다음 조사 지점:** static callback slot `+0x80/+0x88`의 선언/대입 위치와 XLua delegate 등록 경로를 추적해 Request lifecycle hook의 실제 target을 식별한다.


### 13.15 Opcode callback registry 교차검증 (2026-10-03)

#### 화면별 등록 key 직접 확인

각 화면 Listing에서 `Ali.OnProccessRequestFinish::.ctor @ 00e110fc`로 delegate wrapper를 생성한 다음 `BaseMono.RegisterDataProccessCallBack @ 00e1a5c0`에 opcode key와 delegate를 전달한다.

| 화면 | 등록 key | 근거 주소 |
|---|---:|---|
| MailMono | `0x2E`, `0x68` | `00f99f7c–00f99fd4` |
| TaskNewPanelMono | `0x30` | `00f7a238–00f7a24c` |
| TrainingCampPanelMono | `0x30` | `0103bc84–0103bc98` |
| TaoFaPanelMono | `0x7D`, `0x7C`, `0x30` | `01035ea8–01035f34` |
| ShopNewPanelMono | `0x34`, `0x5C` | `010286d8–01028730` |

Request Listing의 직접 opcode 대입(`MailGetReward=0x2E`, `QuestGetReward=0x30`, `Shopping=0x34`)과 화면 등록 key가 일치한다. 다만 delegate constructor의 method metadata는 각 정적 슬롯에서 읽으므로 key 일치만으로 실제 handler 함수 포인터까지 확정하지 않는다.

#### Quest 보상 요청 caller 보강

PR Listing의 `QuestGetReward @ 00ddfc10` Calls IN에는 아래 네 직접 caller가 있다.
- `TaskNewPanelMono.OnClickRecive @ 00f7d768`
- `TrainingCampPanelMono.OnClickReceive @ 0103d508`
- `TaoFaPanelMono.OnClickRecive @ 01039ef8`
- `ActiveShowPanelMono.OnClickRecive @ 010206f4`

기존 세 화면 외에 ActiveShowPanel도 QuestGetReward를 호출한다. 해당 화면의 callback key 및 응답 후처리 연결은 별도 확인 대상으로 둔다.

#### DataCenter → UI registry dispatch

- `DataCenter.RequestCallback @ 016e1f44`는 Request의 `IsClientProccessed`를 true로 설정한 다음 `Ali.DataProccessCallBack @ 00e03dd4`를 호출한다.
- `Ali.DataProccessCallBack`은 `Request.get_Res()`로 응답 OpInfo를 얻고 ReturnCode(`+0x18`) 및 OpCode(`+0x14`)를 검사한다.
- 일반 callback 경로는 응답 opcode를 key로 Dictionary `ContainsKey → get_Item`을 수행한 뒤 `NetEvent.callBack`을 실행한다. 일부 opcode는 `GUIScreenManager.RequsetBack` 등 별도 분기를 탄다.

**미확정:** `DataCenter.RequestCallback`의 Calls IN에는 정적 Listing상 직접 호출자가 없다. `NetworkCenter.TryHandleResponse`에서도 이 메서드로 직접 이어지는 호출은 확인되지 않았다. 따라서 NetworkCenter `+0x38 Action`, Request.SetResponse의 XLua hook(`+0x88`), DataCenter.RequestCallback을 하나의 callback으로 합쳐 설명하지 않는다. 런타임 연결은 hook slot 대입 또는 delegate MethodInfo 복원이 필요하다.

**판정:** 화면별 opcode 등록 key와 Request opcode 대응을 직접 재확인했고 QuestGetReward의 ActiveShowPanel caller를 추가했다. Dictionary 기반 UI dispatch는 확인했으나, dispatch를 시작시키는 Request lifecycle 연결은 미확정이다.



### 13.16 +0x80/+0x88 callback 보유 주체 재판정 (2026-10-03)

앞선 13.14에서는 두 slot이 속한 singleton의 구체 타입을 미확정으로 기록했다. 이번에는 Request의 다른 프로퍼티 accessor Listing과 동일한 전역 class metadata 참조를 비교했다.

#### 동일 Request class static-fields 영역 확인

다음 함수들은 공통으로 전역 참조 `0x3374000 + 0x470`을 읽고, 그 결과의 `+0xB8`을 static-fields 영역처럼 사용한다.

| Request 함수 | static-fields offset | 동작 |
|---|---:|---|
| get_ID | +0x00 | delegate 있으면 XLua 호출, 없으면 Request +0x10 읽기 |
| set_ID | +0x08 | delegate 있으면 XLua 호출, 없으면 Request +0x10 쓰기 |
| get_Req | +0x50 | delegate 있으면 XLua 호출, 없으면 Request +0x30 읽기 |
| set_Req | +0x58 | delegate 있으면 XLua 호출, 없으면 Request +0x30 쓰기 |
| get_Res | +0x60 | delegate 있으면 XLua 호출, 없으면 Request +0x38 읽기 |
| set_Res | +0x68 | delegate 있으면 XLua 호출, 없으면 Request +0x38 쓰기 |
| Request::.ctor | +0x80 | delegate 있으면 생성 hook으로 위임 |
| Request.SetResponse | +0x88 | delegate 있으면 응답 설정 hook으로 위임 |

근거 Listing:
- `015b45b4 Request.get_ID`: static-fields `+0x00`, fallback `[Request +0x10]`
- `015b4ae4 Request.set_ID`: static-fields `+0x08`, fallback `[Request +0x10]`
- `015b3bb4 Request.get_Req`: static-fields `+0x50`, fallback `[Request +0x30]`
- `015b4e8c Request.set_Req`: static-fields `+0x58`, fallback `[Request +0x30]`
- `015b4f10 Request.get_Res`: static-fields `+0x60`, fallback `[Request +0x38]`
- `015b4f78 Request.set_Res`: static-fields `+0x68`, fallback `[Request +0x38]`
- `015b3c1c Request::.ctor`: static-fields `+0x80`
- `015b461c Request.SetResponse`: static-fields `+0x88`

#### 판정 수정

이제 +0x80/+0x88을 별도 singleton의 callback이라고 볼 근거는 없다. 두 slot은 Request의 다른 프로퍼티 XLua delegate slot들과 같은 class metadata/static-fields 참조 경로를 사용한다.

따라서 현 단계의 가장 정확한 설명은 다음과 같다.

- callback 보유 주체: `Alioth.S1.Net.Request` 클래스의 static-fields 영역으로 판정.
- +0x80: Request 생성 lifecycle hook.
- +0x88: Request 응답 설정 lifecycle hook.
- 실제 callback 값은 해당 slot에 delegate가 설정된 경우에만 실행된다.
- 이 delegate를 등록하는 XLua/Hotfix 초기화 주체 및 Lua측 함수는 아직 미확정이다.

이는 13.14의 “별도 static/singleton 경로”를 더 구체화한 결과이며, NetworkCenter의 `+0x38 Action` 또는 화면별 `OnProccessRequestFinish` 등록 Dictionary와 동일한 callback이라는 뜻은 아니다.

#### 다음 추적

1. Request class static-fields에 delegate를 기록하는 XLua Hotfix/Delegate 등록 경로를 찾는다.
2. `Request::.ctor`와 `Request.SetResponse`에 해당하는 delegate 생성/대입 코드가 Listing에 존재하는지 확인한다.
3. 등록 코드가 없으면 LuaEnv 초기화 및 Hotfix 패치/등록 함수의 runtime hook 후보를 좁힌다.
4. runtime에서 +0x80/+0x88의 null 여부와 delegate target을 확인해 실제 실행 경로를 확정한다.



### 13.17 Request callback 등록 경로 추가 추적 (2026-10-03)

이번 단계에서는 Request lifecycle hook의 호출 조건과 일반 XLua wrapper 경로를 대조했다.

#### 1) 생성 hook의 실제 실행 위치

`Request::.ctor @ 015b3c1c`:
- OpInfo가 null이 아니면 `set_ID(OpInfo +0x10)`, `set_Req(OpInfo)`를 먼저 수행한다.
- 이후 Request static-fields `+0x80`을 읽는다.
- slot이 non-null이면 `DelegateBridge.__Gen_Delegate_Imp14(Request, OpInfo)`로 tail-call하고 생성자 기본 return 경로로 돌아오지 않는다.
- OpInfo가 null인 경우에도 동일 slot을 확인하며, 이때 두 번째 인자는 null이다.

즉, hook은 Request 필드가 기본 초기화된 다음 실행되는 후처리라기보다, 생성자의 남은 기본 경로를 대체/위임할 수 있는 확장 지점이다. 날짜 필드(CreateAt/FinishAt)의 기본 설정은 hook이 없을 때만 수행되는 흐름으로 해석해야 한다.

#### 2) 응답 hook의 실제 실행 위치

`Request.SetResponse @ 015b461c`:
- Request static-fields `+0x88`을 먼저 검사한다.
- non-null이면 `DelegateBridge.__Gen_Delegate_Imp14(Request, responseOpInfo)`로 tail-call한다.
- null일 때만 기본 경로에서 `set_Res(responseOpInfo)`와 `set_FinishAt(DateTime.Now)`를 수행한다.

따라서 +0x88 hook이 활성화된 런타임에서는 기본 Res 저장 및 FinishAt 갱신이 생략될 수 있다. hook 내부에서 이를 직접 처리하는지 확인해야 한다.

#### 3) 일반 XLua C# wrapper와의 구분

Listing에서 확인되는 일반 wrapper 진입은 다음과 같다.
- `XLua.CSObjectWrap.AliothS1NetRequestWrap.__CreateInstance @ 011716a0` → Request::.ctor
- `AliothS1NetRequestWrap._m_SetResponse @ 0117193c` → Request.SetResponse

이 wrapper는 Lua에서 Request 인스턴스를 생성하거나 SetResponse를 호출하는 진입점이다. 그러나 현재 확인한 wrapper의 Calls IN 관계만으로는 Request static-fields `+0x80/+0x88`에 delegate를 대입하는 등록 코드가 드러나지 않는다.

또한 `Ali.set_luaenv @ 00dff65c`는 Ali 객체의 LuaEnv 필드(`+0x10`)를 설정하는 별도 XLua 위임 프로퍼티다. Request static-fields의 +0x80/+0x88 등록을 직접 수행한다는 근거는 없다.

#### 4) 등록 주체 판정

현재 저장소의 Listing 검색에서 `XLua.Hotfix`, `HotfixAttribute`, Request 전용 static delegate setter 또는 +0x80/+0x88을 기록하는 명시적 등록 함수는 확인하지 못했다.

따라서 확정 가능한 사실과 미확정 항목을 분리한다.

- 확정: 두 slot은 Request class static-fields의 lifecycle delegate slot이다.
- 확정: 생성자/SetResponse는 slot이 non-null이면 DelegateBridge Imp14로 실행을 위임한다.
- 확정: 일반 CSObjectWrap의 생성/메서드 wrapper는 hook 호출 진입점이지, 현재 확인 범위에서 hook 등록 주체는 아니다.
- 미확정: delegate를 최초 대입하는 코드, Lua 함수명, target object 및 등록 시점.
- 미확정: 실제 런타임에서 두 slot이 null인지 여부.

#### 5) 다음 단계의 추적 방법

정적 Listing만으로 등록 코드를 더 찾기 어려우므로 다음은 런타임 검증을 우선한다.

1. `Request` class metadata에서 static_fields 포인터를 확인한다.
2. static_fields `+0x80`, `+0x88` 값을 Lua 초기화 전/후로 각각 읽는다.
3. non-null이면 delegate object의 target/method 또는 XLua DelegateBridge의 Lua function reference를 확인한다.
4. 두 slot에 대한 write watchpoint 또는 메모리 write 추적을 걸어 최초 대입 call stack을 수집한다.
5. 생성/응답 시점에 실제 hook 진입 여부와 Res/FinishAt 기본 저장 여부를 함께 기록한다.

이 단계에서 등록 주체를 임의로 XLua Hotfix 시스템 또는 특정 Lua 파일로 단정하지 않는다.



### 13.18 Response 처리 후 완료 이벤트 연결 추적 (2026-10-03)

이번 단계에서는 callback 등록 주체를 더 파지 않고, 실제 응답이 Request 완료 이벤트까지 도달하는 정적 순서를 확인했다.

#### 1) NetworkCenter.TryHandleResponse의 실제 순서

Listing: `015b41e0_Alioth.S1.Net.NetworkCenter__TryHandleResponse.txt`

정상 처리 경로의 핵심 순서는 다음과 같다.

```text
NetworkCenter.TryHandleResponse(response)
  → DataCenter.ProccessRequestRes(response)
  → pending Request Queue.Peek()
  → Request.get_ID()
  → Request.ID와 response.SerialNumber(+0x10) 비교
  → 일치하면 Queue.Dequeue()
  → Request.SetResponse(request, response)
  → NetworkCenter instance +0x38 Action 호출(해당 delegate가 non-null인 경우)
```

- `DataCenter.ProccessRequestRes`는 대기 Request의 SerialNumber 매칭보다 먼저 호출된다.
- SerialNumber가 일치한 경우에만 해당 Request를 Queue에서 제거하고 `SetResponse`를 호출한다.
- `SetResponse` 호출 뒤 NetworkCenter 인스턴스의 `+0x38` delegate를 검사하고, non-null이면 간접 호출한다.
- 이 `+0x38`은 NetworkCenter 인스턴스 필드다. Request static-fields의 `+0x80/+0x88`, DataCenter의 opcode callback Dictionary와 동일한 slot으로 취급하지 않는다.
- 함수 진입 초기에 별도로 NetworkCenter class static-fields `+0x80` delegate를 검사하는 경로도 존재한다. 이 delegate가 non-null이면 DelegateBridge Imp11로 위임하고 정상 기본 처리 경로를 건너뛴다. 이 역시 Request의 +0x80과는 보유 클래스가 다르다.

#### 2) CSBehaviour 완료 이벤트 등록 경로

Listing: `016dd854_CSBehaviour__RegisterRequestCallBack.txt`, `CS.txt`

- `CSBehaviour.RegisterRequestCallBack(callback)`는 CSBehaviour singleton을 얻은 뒤 `CSBehaviour.add_OnRequestFinish(callback)`를 호출한다.
- `add_OnRequestFinish`는 CSBehaviour 인스턴스의 `+0x38` 이벤트 delegate에 전달된 callback을 Combine하는 구조다.
- `DataCenter.OnEnable @ 016e8a7c`가 `CSBehaviour.RegisterRequestCallBack`의 Calls IN에 나타난다.
- 반대로 `DataCenter.OnDisable @ 016e8b30`은 `CSBehaviour.UnRegisterRequestCallBack`의 Calls IN에 나타난다.

따라서 DataCenter가 활성화/비활성화될 때 CSBehaviour의 Request 완료 이벤트를 등록/해제하는 생명주기 구조는 확인된다. 다만 현재 확보한 OnEnable Listing 본문에서 전달 callback의 생성/대상 method를 직접 읽지 못했으므로, 이것이 정확히 `DataCenter.RequestCallback`이라고 단정하지 않는다.

#### 3) UI dispatch와의 현재 연결 상태

이미 확인된 별도 경로:

```text
DataCenter.RequestCallback(request)
  → Request.IsClientProccessed = true
  → Ali.DataProccessCallBack(request)
  → Request.Res의 OpCode(+0x14) 확인
  → Ali의 opcode callback Dictionary 조회
  → NetEvent.callBack / 특수 화면 분기
```

이번 단계에서 확정된 것은:
- NetworkCenter는 응답 데이터 병합 후 SerialNumber로 원래 Request를 찾는다.
- 일치한 Request에 SetResponse를 실행한다.
- SetResponse 직후 NetworkCenter의 +0x38 완료 Action 호출 지점이 있다.
- CSBehaviour에는 OnRequestFinish 이벤트와 등록/해제 API가 있고 DataCenter의 OnEnable/OnDisable이 이를 사용한다.

아직 미확정:
- NetworkCenter +0x38 Action의 실제 delegate target/method.
- CSBehaviour.OnRequestFinish와 NetworkCenter +0x38 Action의 런타임 연결 방식.
- DataCenter.OnEnable이 RegisterRequestCallBack에 전달하는 정확한 delegate method가 RequestCallback인지 여부.
- Request.SetResponse의 XLua hook(+0x88)이 실제 런타임에서 활성화되어 있는지 여부.

#### 4) Local Server 관점의 의미 및 다음 단계

서버 응답 계약을 검증할 때 단순히 응답 OpInfo를 Deserialize하는 것으로 끝나지 않는다. 최소한 다음 순서를 만족해야 한다.

1. 응답의 SerialNumber가 pending Request와 일치해야 한다.
2. Client가 응답을 공통 State에 병합한다.
3. 원래 Request의 Res가 설정되고 완료 이벤트가 실행된다.
4. 응답 OpCode에 맞는 화면 callback이 실행되어야 한다.

다음 분석은 callback 등록 주체를 더 추측하지 않고, 실제 구현에 직접 필요한 **응답 OpInfo 필드별 DataCenter 병합 순서와 Bootstrap OpCode=2의 필수 필드**를 추적한다. UI dispatch 연결은 위 완료 이벤트의 런타임 target이 확인될 때만 추가 확정한다.



### 13.19 Bootstrap 응답 필드 → DataCenter 상태 병합 순서 (2026-10-03)

기준 Listing: `research/Ghidra_Listing_txt/DA.txt`

#### 1) ProccessRequestRes의 직접 병합 순서

`DataCenter.ProccessRequestRes @ 016e203c`의 `0x016e29dc~0x016e2aec` 구간에서 response 필드를 읽어 아래 순서로 호출한다.

| 순서 | OpInfo offset | 필드(기존 OpInfo 구조 기준) | 처리 | DataCenter 상태 |
|---:|---:|---|---|---|
| 1 | +0xA0 | Weapons | MergeWeapon @ 016e414c | +0x40 |
| 2 | +0xA8 | Equiments | MergeEquip @ 016e4348 | +0x38 |
| 3 | +0x98 | Items | MergeItem @ 016e4700 | Item/category cache |
| 4 | 전체 response | User/Heros 및 보조 상태 | UpdateHeroInfo @ 016e4ba4 | 복수 상태 |
| 5 | +0xC0 | Chapters | Merge<int,object> @ 017704a0 | +0x48 |
| 6 | +0xC8 | Sections | MergeSections @ 016e55dc | +0x50 |
| 7 | +0xD0 | Teams | Merge<int,object> @ 017704a0 | +0x58 |
| 8 | +0xE8 | Quests | Merge<int,object> @ 017704a0 | +0x80 |
| 9 | +0xB0 | Mails | Merge<long,object> @ 01770ce4 | +0x88 |
| 10 | +0xF0 | Shops | Merge<int,object> @ 017704a0 | +0x68 |
| 11 | +0xF8 | Charges | Merge<int,object> @ 017704a0 | +0x70 |
| 12 | +0x130 | 별도 상태 필드 | non-null일 때 직접 저장 | +0x100 |
| 13 | +0x80 | 별도 상태 필드 | non-null일 때 직접 저장 | +0x108 |
| 14 | +0x100 | 조건부 별도 merge | OpCode 0x3C/0x41 제외 시 Merge<long,object> | +0x98 |
| 15 | +0x148 | 별도 long-key 데이터 | Merge<long,object> | +0xA0 |
| 16 | +0x138 | AIStrategy 관련 | non-null일 때 set_AIStrategy | 관련 상태 |

중요: 위 표는 Listing에서 확인한 처리 호출 순서다. 모든 필드가 모든 OpCode에서 필수라는 의미는 아니며, 각 merge 함수 내부의 null/empty 처리 및 업무별 조건을 구분해야 한다.

#### 2) User 필드 처리

`ProccessRequestRes`의 `0x016e2580` 부근에서 response `+0x88`을 읽는다.

- null이면 UserInfo 생성/갱신 경로를 건너뛴다.
- non-null이면 `UserInfo::.ctor @ 00dd2f44`를 호출한다.
- 생성한 객체를 DataCenter 인스턴스 `+0x28`에 저장한다.

따라서 `OpInfo.User (+0x88) → UserInfo → DataCenter +0x28`은 정적 Listing으로 직접 확인된다.

#### 3) Hero 및 보조 정보 처리

`UpdateHeroInfo @ 016e4ba4`는 response 전체를 인자로 받는다. 본문에서 확인한 response 필드 접근은:

- `+0x90`: Hero dictionary를 순회하고, DataManager 조회 후 `HeroInfo.InitHero @ 016e5fd4`를 호출한다. 추가로 Hero state 및 ConfirmCallHero 관련 처리가 이어진다.
- `+0xA0`: Weapon dictionary를 순회하며 관련 ID 집합/상태를 갱신한다.
- `+0xA8`: Equipment dictionary를 순회하며 관련 ID 집합/상태를 갱신한다.
- `+0xE0`: Fashion dictionary를 순회해 관련 ID 상태를 갱신한다.

따라서 UpdateHeroInfo는 단순히 User/Heros 두 필드만 처리하는 함수가 아니다. User(+0x88)는 ProccessRequestRes 앞부분에서 UserInfo로 별도 저장되고, UpdateHeroInfo는 Hero(+0x90)와 Weapon/Equipment/Fashion 보조 상태를 함께 처리한다.

#### 4) Local Server 구현에 반영할 점

- Bootstrap 응답은 기존 관측 envelope를 유지한다.
- User(+0x88)는 UserInfo 생성의 직접 입력이므로 실제 관측 객체 구조를 보존한다.
- Heros(+0x90)는 HeroInfo 초기화 루프에 들어가므로 빈 객체/누락을 임의로 동일 취급하지 않는다.
- Weapons(+0xA0), Equiments(+0xA8)는 전용 merge와 UpdateHeroInfo의 보조 처리가 중복 수행된다. 단일 처리로 합치지 않는다.
- Fashions(+0xE0)는 UpdateHeroInfo 내부에서 별도로 읽힌다. 별도 cache offset 및 화면 필수 여부는 아직 확정하지 않는다.
- 나머지 필드도 실제 OpCode별 조건을 확인하기 전까지 임의 제거하지 않는다.

#### 5) 미확정 및 다음 단계

- Bootstrap OpCode=2에서 위 각 필드가 전부 실제로 소비되는지 runtime hook으로 대조.
- UserInfo 필드별 초기화 결과와 HomePanel 재화/레벨 표시 소비처 연결.
- HeroInfo.InitHero 입력 ProtoHero와 최종 HeroInfo/DataManager key의 대응 확인.
- MergeEquip/MergeWeapon 내부의 삭제/갱신/생성 규칙 및 key 의미 확인.
- Chapters/Sections/Teams/Quests/Shops/Charges의 실제 cache 소비처 중 Main 진입 필수 여부 추가 검증.

이번 단계는 서버 응답 envelope의 필드-상태 변환 규칙을 정리한 정적 분석이며, 최소 응답 계약을 확정한 것은 아니다.
