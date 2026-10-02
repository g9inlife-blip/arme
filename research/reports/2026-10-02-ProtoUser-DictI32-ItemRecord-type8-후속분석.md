# 2026-10-02 ProtoUser / DictI32 / ItemRecord 후속 분석

## 범위
- 서버 데이터 생성/수정 제외
- 클라이언트의 Deserialize 이후 객체 변환, 상태 저장, Main UI 소비 경로만 분석
- 기준 Git 자료: `research/reports/2026-10-02-Bootstrap-Client-State-MainUI-연결분석.md`, `research/reports/2026-10-02-Bootstrap-OpCode2-Response-계약-초안.md`, `research/Ghidra_Listing_txt/AL`, `research/Ghidra_Listing_txt/US.txt`

## A. ProtoUser → UserInfo

### 확인된 ProtoUser getter / 객체 offset
| ProtoUser property | getter RVA | object offset |
|---|---:|---:|
| Id | 015adb0c | +0x10 |
| Level | 015adb2c | +0x1C |
| Exp | 015adb3c | +0x20 |
| HeadIcon | 015adb6c | +0x2C |
| Name | 015adb7c | +0x30 |

각 getter Listing은 해당 객체의 offset에서 값을 읽어 반환한다.

### 변환 경로
```
OpInfo +0x88 (field 35 User / ProtoUser)
  → UserInfo.ctor @ 00dd2f44
  → DataTool.CopyTo<ProtoUser, UserInfo>
  → DataCenter +0x28 (UserInfo)
```

UserInfo 기본 속성과 DictI32 vary 값은 같은 UserInfo 객체에 서로 다른 경로로 반영된다.

- ProtoUser 기본 필드: CopyTo 경로
- DictI32: UserInfo.MergeVaryData @ 00dd3030 경로

**미확정:** 위 ProtoUser 객체 offset은 C# 객체 메모리 배치다. protobuf wire tag 번호와 동일하지 않다. 현재 확보한 getter Listing만으로 ProtoUser의 tag 번호를 단정하지 않는다. 다음 단계는 ProtoUser의 generated serializer/parser 또는 protobuf metadata에서 tag ↔ property 대응을 찾는 것이다.

## B. DictI32 음수 Key 및 Main UI 소비처

운영 PCAP 기준 field 21 DictI32 음수 key 13종:
- MergeVaryData 처리 key: -9, -10, -11, -12, -13, -14, -15, -16, -18, -30, -31, -32, -34
- PCAP에서 실제 확인된 MergeVaryData 대상: -18=ExamTimes(15), -30=EquipMax(0), -31=ChargeTotalPerMonth(0), -32=Age(27), -34=ChatChannel(1)
- MergeVaryData 대상이지만 해당 캡처에 없는 key: -9, -10, -11, -12, -13, -14, -15, -16
- 그 외 field 21 음수 key: -29, -28, -27, -23, -22, -20, -33, -36. 이들은 MergeVaryData Listing에서 처리되지 않으므로 UserInfo 속성으로 연결하지 않는다.

### Main UI에서 확인된 유사 key 소비 사례
`HomePanelMono.Start @ 00f67adc` → `RefreshPoint_Mail` 경로에서 DataCenter cache +0xC0 Dictionary의 key -27 검사 및 메일 숫자 표시가 확인된다.

주의: 이 DataCenter +0xC0 Dictionary는 OpInfo +0x70 DictI32와 다른 저장 객체/offset 문맥이다. key 숫자가 -27로 같다는 이유만으로 field 21 DictI32의 -27이 Mail badge로 직접 연결된다고 결론 내리지 않는다.

그 외 field 21의 미분류 음수 key 7종(-29, -28, -23, -22, -20, -33, -36)의 Main UI 소비처는 아직 미확정이다. 양수 key도 263개이며, 개별 소비처는 추가 추적 대상이다.

## C. ItemRecord type 8 참조 ID

현재 Git의 `10_record_type_inventory.md`에서는 ItemRecord가 952개이고 필드에 `m_id`, `m_itemPackageId`, `m_type` 등이 존재하는 것까지 확인된다.

기존 원본 Record 재검증 보고서의 Chapter Box 표본은 다음과 같다.
| Item ID | m_type | m_itemPackageId |
|---:|---:|---|
| 43000001 | 0 | empty |
| 43000002 | 0 | empty |
| 43001000 | 7 | empty |
| 43100002 | 1 | 45100020\|45100021\|45100022 |
| 43200003 | 4 | empty |

이 표본에는 m_type=8인 ItemRecord가 없다. 따라서 type 8의 의미나 참조 ID namespace를 현재 표본으로 추정하지 않는다.

다음에는 Git에 등록된 원본 ItemRecord JSON의 blob SHA를 확보해 m_type=8 레코드 전체를 추출하고, 해당 레코드의 m_id / m_itemPackageId / m_location / m_nameId / m_describeId를 교차 확인한다. 이후 참조 대상 ID가 ItempackageRecord, ItemboxRecord 또는 다른 Record인지 실제 ID 일치로 판정한다.

## 다음 작업
1. ProtoUser의 generated protobuf tag metadata/parser를 찾아 Id/Level/Exp/HeadIcon/Name의 wire tag 확정.
2. field 21의 미분류 음수 key와 양수 key 중 Main UI getter/Calls IN에 연결되는 항목만 추적.
3. HomePanel의 Mail badge key -27은 field 21과 분리된 DataCenter cache 입력/생성 경로를 확인.
4. ItemRecord 원본 blob에서 m_type=8 전체 레코드와 참조 ID를 추출하고 대상 Record type까지 닫는다.

## 판정 원칙
- 객체 offset ≠ protobuf tag
- 동일한 숫자 key라도 서로 다른 Dictionary/cache이면 별도 경로로 취급
- Record의 필드명만으로 참조 의미를 확정하지 않고 실제 ID join 및 호출/소비 증거를 요구
- 서버 데이터 생성/수정은 분석 범위에서 제외


## 2026-10-02 후속 실측 — ItemRecord type 8 원본 전체 대조

### 원본 범위
Git 원본:
`참고용-unity-behavior-data/MonoBehaviour/ItemRecord.json`
- blob SHA: `497667d9c1b130bc9aaa09a3522fb38e633dab49`
- ItemTable: 952개
- `m_type == 8`: **119개**
- `m_itemPackageId` 빈 값: 0개
- 고유 `m_itemPackageId` 문자열: 96종
- 분해된 고유 CODE: 73종

### type 8 레코드 구조
모든 119개 레코드에서 확인:
- `m_location = 0`
- `m_max = 9999`
- `m_parameter = 0`
- `m_jump = 0`
- `m_itemPackageId`는 CODE*VALUE 형식
- `m_nameId` / `m_describeId`는 개별 레코드마다 별도 존재

ObscuredInt ID는 `hiddenValue XOR currentCryptoKey`로 복원한다. 119개 type 8의 논리 ID 범위는 **43100014~43300003**이다. 첫 표본은 hiddenValue 43478898 XOR 444444 = 논리 ID 43100014이며, m_nameId 143100014, m_itemPackageId `200*5`다. 기존 ItemRecord 43000001 ↔ hiddenValue 43444445 대조와 동일한 XOR 규칙이다.

### CODE 분포
73개 CODE는 다음 그룹으로 나타난다.
- 1~30 일부: 1, 2, 10~27, 30
- 100, 200, 201
- 300~305
- 310~315
- 320~338
- 400~405
- 410~415
- 420~425

대표 예:
| Logical Item ID | hiddenValue | m_nameId | icon | m_itemPackageId |
|---:|---:|---:|---|---|
| 43100014 | 43478898 | 143100014 | item_43100014 | 200*5 |
| 43101000 | 43475796 | 143101000 | item_43101000 | 1*1 |
| 43101090 | 43475902 | 143101090 | item_43101090 | 10*5 |
| 43101300 | 43476072 | 143101300 | item_43101300 | 300*1 |
| 43300000 | 43154620 | 143300000 | item_43300000 | 100*2 |

### 참조 namespace 검증
원본 `ItempackageRecord.json` (2,028개) 및 `ItemboxRecord.json` (3,242개)를 blob으로 읽어 대조했다.
- ItempackageRecord 논리 ID 범위(XOR 복원): 45000000~45513357
- ItemboxRecord 논리 ID 범위(XOR 복원): 44000000~44300199
- type 8의 `m_itemPackageId` CODE 값은 1~425 범위의 작은 숫자이며, 두 테이블의 논리 Record ID와 일치하지 않는다.

따라서 현재 근거로는 type 8의 `m_itemPackageId` CODE를 ItempackageRecord ID 또는 ItemboxRecord ID로 직접 취급할 수 없다. **별도의 소형 코드 namespace / lookup 단계가 존재할 가능성**까지가 현재 결론이며, namespace 명칭과 실제 해석 테이블은 미확정이다.

### Ghidra 측 연결
`research/Ghidra_Listing_txt/IT.txt`:
- `ItemData.get_itemPackageId @ 00df09a8`: `ldr x0,[x0,#0x90]` — ItemData 객체의 +0x90 참조 반환
- `ItempackageData.get_itemWeight @ 00df09cc`: `ldr x0,[x0,#0x78]` — ItempackageData 객체의 +0x78 참조 반환

현재 Listing의 해당 getter Calls IN은 비어 있어, 이 두 getter만으로 ItemRecord type 8의 CODE 해석 경로를 확정할 수 없다. Lua/XLua 또는 다른 동적 호출 계층까지 확인해야 한다.

## 2026-10-02 후속 실측 — ProtoUser / DictI32 재확인

### ProtoUser
`ProtoUser` getter Listing에서 확인된 메모리 offset:
- Id +0x10
- Level +0x1C
- Exp +0x20
- HeadIcon +0x2C
- Name +0x30

이는 C# 객체 속성 위치다. OpInfo의 field 35가 User(ProtoUser)라는 상위 메시지 field 번호는 확인됐지만, ProtoUser 내부 Id/Level/Exp/HeadIcon/Name의 protobuf wire tag는 여전히 미확정이다. getter/ctor Listing에는 generated protobuf parser나 tag metadata가 나타나지 않는다. 따라서 offset을 wire tag로 바꾸어 기록하지 않는다.

### DictI32
`UserInfo.MergeVaryData @ 00dd3030` Listing을 재확인했다. 함수는 입력 Dictionary에 key가 존재하면 해당 값을 읽고, 없으면 현재 UserInfo getter 값을 유지하는 방식으로 각 setter를 호출한다.

실제 Listing의 key 상수:
- -9 → StigmataTimes
- -10 → MetaphysicsTimes
- -11 → Exp
- -12 → Level
- -15 → FCTimes
- -13 → SignInDays
- -14 → SignInRewardDay
- -16 → StepId
- -18 → ExamTimes
- -30 → EquipMax
- -31 → ChargeTotalPerMonth
- -32 → Age
- -34 → ChatChannel

따라서 기존 요약의 key 처리 목록 중 -17 등은 포함하지 않으며, 위 13개가 Listing에서 확인된 실제 처리 key다.

field 21 DictI32에서 발견된 미분류 key -29, -28, -27, -23, -22, -20, -33, -36은 MergeVaryData의 분기에서 읽히지 않는다. Mail badge의 -27은 기존 확인처럼 HomePanel의 별도 DataCenter cache +0xC0 문맥에 존재하므로, field 21의 -27과 합치지 않는다.

## 다음 추적 우선순위 업데이트
1. ItemRecord type 8의 소형 CODE(1~425)가 사용되는 Lua/XLua 호출처와 실제 lookup 테이블 찾기.
2. ItemData.get_itemPackageId 및 ItempackageData.get_itemWeight의 호출 경로를 XLua wrapper/스크립트에서 역추적.
3. ProtoUser 내부 protobuf wire tag는 serializer/parser 구현 또는 실제 nested User payload byte offset과 대조해 확인. 객체 offset으로 추정하지 않음.
4. DictI32 미분류 key 8종은 Main UI getter/consumer에서 직접 조회되는지 계속 추적하되, Mail cache의 -27과 별개로 유지.


## 2026-10-02 후속 실측 — ProtoUser wire tag / DictI32 소비처 / XLua 노출 경로

### 1. ProtoUser 실제 wire tag

Git PCAP 원본 변환:
- `research/PCAP/로그인_출석_퀘스트_우편_토벌_던전_상자_무기제작_강화_kcp/messages.json`
- blob SHA: `5a9f8f12466c2a14fb3769b376f96b6eebc8dfc4`
- packet 192~201 S→C Bootstrap 응답, `gzip_protobuf`의 outer field 35는 1개
- field 35 nested message 길이 33 bytes

실제 nested payload:
| ProtoUser wire tag | wire | 값 | 판정 |
|---:|---:|---|---|
| 1 | varint | 871047 | Id — PCAP 분석 handoff에서도 User ID로 확인 |
| 3 | varint | 4 | Level 후보 — 값/필드 타입상 대응 가능, 동일 실행의 런타임 getter 대조는 미완료 |
| 4 | varint | 250 | Exp 후보 — 값/필드 타입상 대응 가능, 동일 실행의 런타임 getter 대조는 미완료 |
| 7 | varint | 18100000 | HeadIcon — HeadiconRecord의 ID 및 `headIcon_18100000`와 일치 |
| 14 | string | g9in2 | Name — 문자열 및 기존 PCAP handoff의 Username 설명과 일치 |
| 20 | varint | 3 | 미매핑 |
| 21 | varint | 3 | 미매핑 |
| 22 | varint | 10 | 미매핑 |
| 24 | varint | 1 | 미매핑 |

ProtoUser getter Listing은 Id +0x10, Status +0x18, Level +0x1C, Exp +0x20, VIPLevel +0x24, VIPExp +0x28, HeadIcon +0x2C, Name +0x30 등을 보여준다. 이들은 C# 객체 offset이며 wire tag와 동일한 값으로 취급하지 않는다.

**현재 판정:** Id/tag 1, HeadIcon/tag 7, Name/tag 14는 payload 값과 Record/PCAP 설명으로 확인했다. tag 3=Level 및 tag 4=Exp는 강한 후보지만, 같은 Bootstrap 실행에서 ProtoUser getter 값을 출력한 runtime log가 없으므로 완전 확정 대신 후보로 남긴다. tag 20/21/22/24도 속성 연결을 보류한다.

### 2. DictI32 음수 key의 실제 집합과 소비 범위

동일 PCAP의 outer field 21에서 음수 key는 총 13종이며 각 1회 관측:
- MergeVaryData 처리: `-9, -10, -11, -12, -13, -14, -15, -16, -18, -30, -31, -32, -34`
- 미분류: `-20, -22, -23, -27, -28, -29, -33, -36`

`UserInfo.MergeVaryData @ 00dd3030`은 첫 번째 그룹 13개만 검사하고 대응 UserInfo getter/fallback → setter로 반영한다. 두 번째 그룹 8개는 해당 함수에서 조회되지 않는다.

Main UI 소비 경로에서 확인된 `HomePanelMono.RefreshPoint_Mail @ 00f69fd0`의 key -27은 DataCenter cache +0xC0 Dictionary를 읽는다. 이는 OpInfo +0x70 DictI32와 다른 객체/offset이다. 따라서 field 21의 -27을 Mail badge 값으로 연결하지 않는다.

일반 Dictionary<int,int> get_Item 호출처 중 `Ali.isSysconfOn`, `RewardPanelMono.Demand`, `BaseMono.IsSectionClear` 계열도 확인했지만 각각 DataCache functionSwitcher, Reward 계산용 로컬 Dictionary, Section snapshot 경로다. 현재 근거로는 field 21의 미분류 8개 key와 직접 연결할 수 없다. 미분류 key의 Main UI 의미는 미확정으로 유지한다.

### 3. ItemRecord type 8의 XLua 노출 경계

Ghidra `research/Ghidra_Listing_txt/IT.txt`에서:
- `ItemData.get_itemPackageId @ 00df09a8`: 객체 +0x90 참조 반환
- `ItempackageData.get_itemWeight @ 00df09cc`: 객체 +0x78 참조 반환
- `ItemData.ctor @ 00df09c8`의 Calls IN에 `XLua.CSObjectWrap.ItemDataWrap.__CreateInstance @ 012cedf8`
- `ItempackageData.ctor @ 00df09d4`의 Calls IN에 `XLua.CSObjectWrap.ItempackageDataWrap.__CreateInstance @ 012d05dc`

현재 Listing에서 두 getter의 정적 Calls IN은 비어 있다. 즉 C# 네이티브 코드에서 getter를 직접 호출하는 체인은 확인되지 않았고, XLua wrapper를 통해 Lua에 타입/속성이 노출되는 지점까지만 확인된다. type 8의 CODE(1~425)를 해석하는 lookup 함수/테이블은 아직 특정되지 않았다.

다음 추적은 Lua 실행 중 `ItemData.itemPackageId` property read와 split 결과, CODE로 조회하는 table/dictionary 및 `ItempackageData.itemWeight` 접근을 함께 기록하는 runtime hook으로 진행한다. CODE를 ItempackageRecord ID로 가정하지 않는다.

### 4. 다음 작업
1. 같은 PCAP 계정/동일 응답에서 ProtoUser Id/Level/Exp/HeadIcon/Name getter를 runtime dump해 tag 3/4 후보 확정.
2. XLua Lua property read hook으로 type 8 CODE lookup의 실제 호출과 대상 collection 확인.
3. 미분류 음수 key 8종은 field 21 소비 함수에서 직접 연결되는 근거가 나올 때까지 의미 부여 보류.



## 2026-10-02 정정 — ObscuredInt ID 복원 규칙

기존 type 8 분석 문단에서 `hiddenValue - 444444`를 사용한 것은 계산 규칙 오류다. 이 저장소의 ObscuredInt `m_id`는 `hiddenValue XOR currentCryptoKey`로 복원한다. 따라서 type 8의 논리 ID는 42710176~43034455가 아니라 **43100014~43300003**이며, 예시 raw hiddenValue 43478898은 논리 ID 43100014다.

같은 규칙을 ItempackageRecord/ItemboxRecord에 적용하면 각각 45000000~45513357, 44000000~44300199다. type 8 `m_itemPackageId` CODE(1~425)는 여전히 이 Record ID 범위와 일치하지 않는다.



## 2026-10-02 추가 실측 — PCAP OpCode 2의 ProtoUser wire tag 확정

대상은 Git의 `research/PCAP/로그인_출석_퀘스트_토벌_던전_상자_무기제작_강화_kcp/messages.json` 원본 변환 데이터다. 메시지 레코드의 패킷 묶음 `192~201` (서버 `182.92.62.79 → 10.215.173.1`, 13,313 bytes)에서 최상위 protobuf field 35를 직접 확인했다.

### ProtoUser wire tag ↔ 속성

field 35의 nested protobuf는 다음과 같이 실제 tag를 제공한다.

| Wire tag | wire type | 관측값 | 속성 연결 |
|---:|---:|---|---|
| 1 | varint | 871047 | ProtoUser.Id |
| 3 | varint | 4 | ProtoUser.Level |
| 4 | varint | 250 | ProtoUser.Exp |
| 7 | varint | 18100000 | ProtoUser.HeadIcon |
| 14 | length-delimited | UTF-8 hex `6739696e32` = `g9in2` | ProtoUser.Name |
| 20 | varint | 3 | 미확정 |
| 21 | varint | 3 | 미확정 |
| 22 | varint | 10 | 미확정 |
| 24 | varint | 1 | 미확정 |

앞서 Listing에서 확인한 ProtoUser 객체 offset(Id +0x10, Level +0x1C, Exp +0x20, HeadIcon +0x2C, Name +0x30)과 runtime getter 의미를 대조해 tag 연결했다. 즉 **객체 필드 offset과 protobuf wire tag는 별개**이며, 이번 PCAP에서는 nested field tag 1/3/4/7/14로 확정된다. 나머지 tag 20/21/22/24는 속성 이름을 붙이지 않고 보류한다.

### 동일 OpInfo field 21 DictI32 음수 key 재확인

같은 메시지의 field 21 반복 entry 중 음수 key는 13개가 관측됐다. signed int32로 복원한 key와 value는 다음과 같다.

| key | value |
|---:|---:|
| -29 | 16 |
| -28 | 16 |
| -27 | 16 |
| -23 | 0 |
| -22 | 0 |
| -20 | 0 |
| -18 | 16 |
| -33 | 0 |
| -34 | 16 |
| -36 | 16 |
| -30 | 0 |
| -31 | 0 |
| -32 | 16 |

주의: 이 값들은 해당 PCAP 응답에서 관측한 원시 DictI32 값이다. 이전 세션에서 본 다른 캡처의 값과 달라질 수 있으므로 고정 상수나 UI 표시값으로 해석하지 않는다. 기존 UserInfo.MergeVaryData가 읽는 key 목록과 대조하면 -18, -30, -31, -32, -34는 알려진 속성 소비 경로가 있다. -29, -28, -27, -23, -22, -20, -33, -36은 여전히 소비처 미확정이다. 특히 HomePanelMono의 -27 mail badge 읽기는 DataCenter 캐시 Dictionary(+0xC0) 경로여서, OpInfo field 21의 -27과 동일한 저장소라고 단정할 수 없다.

### 정정/보류 사항

- 기존 보고서의 `hiddenValue - 444444` ID 복원식은 잘못된 것으로 정정했다. ObscuredInt는 `hiddenValue XOR currentCryptoKey` 방식이다. type 8의 logical ID 범위는 43100014~43300003이며 CODE 값 1~425는 ItempackageRecord/ItemboxRecord ID와 일치하지 않는다.
- 이번 PCAP field 35에서 ProtoUser의 기본 5개 wire tag를 확정했으나, 모든 ProtoUser 필드/태그의 전체 스키마를 확정한 것은 아니다.
- 다음은 Lua/XLua에서 ItemData.itemPackageId property를 읽는 실제 함수와 CODE lookup collection을 연결하고, DictI32 미분류 8개 key의 직접 소비처를 찾는 것이다.
