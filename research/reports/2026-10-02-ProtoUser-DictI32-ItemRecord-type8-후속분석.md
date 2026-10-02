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


## 2026-10-02 PCAP wire 실측 추가

### OpInfo field 35 — ProtoUser tag

Git의 PCAP JSON 변환 원본에서 패킷 192~201 묶음(서버 → 클라이언트, 13,313 bytes)을 다시 파싱했다. 최상위 protobuf field 35의 nested field는 아래와 같다.

| tag | wire | 관측값 | 연결 |
|---:|---:|---|---|
| 1 | varint | 871047 | ProtoUser.Id |
| 3 | varint | 4 | ProtoUser.Level |
| 4 | varint | 250 | ProtoUser.Exp |
| 7 | varint | 18100000 | ProtoUser.HeadIcon |
| 14 | length-delimited | `6739696e32` → `g9in2` | ProtoUser.Name |
| 20 | varint | 3 | 미확정 |
| 21 | varint | 3 | 미확정 |
| 22 | varint | 10 | 미확정 |
| 24 | varint | 1 | 미확정 |

이로써 기본 속성 5개의 protobuf wire tag는 **Id=1, Level=3, Exp=4, HeadIcon=7, Name=14**로 확정한다. Ghidra getter에서 확인한 객체 내부 offset(+0x10/+0x1C/+0x20/+0x2C/+0x30)은 wire tag와 별개다. field 35의 나머지 tag 20/21/22/24는 의미를 추정하지 않는다.

### OpInfo field 21 — 동일 캡처의 음수 key

field 21 entry 중 signed int32 음수 key 13개를 varint 원시 바이트에서 부호 복원했다.

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

이는 해당 PCAP 응답 한 건의 관측값이다. 다른 시점의 캡처와 값이 다를 수 있고, 16을 곧바로 UI 카운트로 해석하지 않는다. UserInfo.MergeVaryData에서 소비되는 -18/-30/-31/-32/-34 외의 8개(-29/-28/-27/-23/-22/-20/-33/-36)는 아직 직접 소비처가 확인되지 않았다. HomePanelMono의 -27 mail badge는 별도 DataCenter 캐시 Dictionary(+0xC0) 조회이므로 field 21과 동일한 저장소라고 단정하지 않는다.

### 현재 미해결 경계

- ProtoUser 기본 5개 속성의 wire tag 확정 완료. 추가 tag 4개는 이름 미확정.
- DictI32 미분류 음수 key 8개는 실제 수신 값 확인 완료, 소비 함수 미확정.
- ItemRecord type 8의 73 CODE가 XLua/Lua에서 어느 테이블을 조회하는지는 아직 확인 전. ItemData.get_itemPackageId(+0x90)와 XLua ItemDataWrap 노출까지가 정적 근거의 끝이다.
- ItemRecord/ItempackageRecord/ItemboxRecord의 ObscuredInt 논리 ID는 hiddenValue에서 상수 차감이 아니라 XOR crypto key 복원이다. type 8 logical ID는 43100014~43300003이며, CODE 1~425와 Record ID를 동일시하지 않는다.


## 2026-10-02 정정 — Mail key -27의 Bootstrap → Main 소비 경로

기존 후속분석의 "HomePanelMono -27은 OpInfo field 21과 다른 cache 경로이며 동일 source라고 단정할 수 없다"는 문장은 이후 확인된 Bootstrap 보고서의 DataCenter merge 경로를 반영하지 못한 설명이다. 다음과 같이 정정한다.

```text
OpInfo field 21 DictI32
  → DataCenter.ProccessRequestRes @ 016e203c
  → DataCenter cache Dictionary<int,int> (+0xC0)
  → HomePanelMono.RefreshPoint_Mail @ 00f69fd0
  → point_mail / lbl_mailNum
```

기준 자료 `research/reports/2026-10-02-Bootstrap-Client-State-MainUI-연결분석.md`의 13.2절은 ProccessRequestRes가 OpInfo DictI32(+0x70)에서 -27을 읽어 DataCenter +0xC0 Dictionary에 반영하고, HomePanelMono가 같은 cache key를 읽는다고 정리한다. 따라서 **field 21의 -27은 Mail unread count로 Main UI까지 연결된 key**로 취급한다. PCAP별 값은 달라질 수 있으며, 이번 192~201 캡처의 value 16은 그 시점의 관측값이다.

이전 설명에서 "별도 cache라 동일 source로 단정 불가"라고 쓴 부분은 폐기한다. 다만 -29/-28/-23/-22/-20/-33/-36의 소비처는 여전히 미확정이다.

## 2026-10-02 type 8 참조체계 재확인 — 다른 type과 혼동 금지

`2026-10-02-Bootstrap-Client-State-MainUI-연결분석.md` 14.5절과 대조했다.

- ItemRecord type 1의 m_itemPackageId는 ItempackageRecord ID(451xxxxx)로 연결된다.
- ItemRecord type 9의 m_itemPackageId는 ItemboxRecord ID(443xxxxx)로 연결된다.
- ItemRecord type 8의 119개 m_itemPackageId는 현재 Itembox/Itempackage ID 집합과 불일치하며, `1*1`, `200*5` 같은 소형 CODE*VALUE 체계다.

따라서 type 8의 CODE 1~425를 type 1/9와 같은 패키지/박스 ID로 해석하면 안 된다. ItemData.get_itemPackageId(+0x90)와 ItemDataWrap 노출 경계는 확인했지만, wrapper의 해당 property getter 및 Lua에서 CODE를 조회하는 collection은 아직 listing에서 찾지 못했다. 현재는 **별도 소형 코드 lookup 단계**로만 기록한다.


## 2026-10-02 PCAP 재검증 정정

원본 messages.json blob 5a9f8f12466c2a14fb3769b376f96b6eebc8dfc4의 packet group 192~201에서 OpInfo field 21 map entry를 다시 파싱했다. 음수 signed int32 key는 원시 varint에서 복원했고, field 2(value)가 생략된 map entry는 protobuf 기본값 0으로 처리했다.

| key | value |
|---:|---:|
| -29 | 79 |
| -28 | 94 |
| -27 | 1 |
| -23 | 0 |
| -22 | 0 |
| -20 | 0 |
| -18 | 15 |
| -33 | 0 |
| -34 | 1 |
| -36 | 3 |
| -30 | 0 |
| -31 | 0 |
| -32 | 27 |

이 표는 이번 PCAP group에 대한 직접 재파싱 결과로, 같은 캡처의 이전 표에 기재된 값(예: -29/-28/-27=16)을 대체한다. -27은 Bootstrap 보고서에서 Mail unread count까지 연결되어 있다. -29/-28/-23/-22/-20/-33/-36은 직접 소비처가 아직 확인되지 않았다.

## 2026-10-02 ItemData XLua 경계 재확인

IT.txt에서 ItemData.get_itemPackageId @ 00df09a8은 객체 +0x90 참조를 반환하며, ItemData.ctor @ 00df09c8의 Calls IN에 XLua.CSObjectWrap.ItemDataWrap.__CreateInstance @ 012cedf8가 나타난다. ItempackageData.get_itemWeight @ 00df09cc는 +0x78 참조를 반환하고, 생성자는 ItempackageDataWrap.__CreateInstance @ 012d05dc에서 참조된다. 현재 Listing에서는 _g_get_itemPackageId wrapper getter 본문과 두 getter의 직접 Calls IN이 확인되지 않는다. type 8 CODE lookup collection은 미확정으로 유지한다.

다음 추적 대상은 미분류 key의 실제 Dictionary 소비처와 ItemDataWrap의 Lua property access이다.


## 2026-10-02 DataCenter.ProccessRequestRes의 미분류 음수 key 소비 경로 추가 확인

기준 Listing: research/Ghidra_Listing_txt/DA.txt, DataCenter.ProccessRequestRes @ 016e203c. OpInfo의 DictI32는 x26+0x70에서 순회되며, key별 분기에서 다음 소비가 확인된다.

| DictI32 key | 클라이언트 소비 | 근거 |
|---:|---|---|
| -27 | DataCenter Dictionary<int,int> +0xC0에 같은 key/value 저장 → HomePanelMono.RefreshPoint_Mail | ProccessRequestRes 016e2ff4~016e3034 + Bootstrap 보고서 13.2절 |
| -28 | 초 단위 값으로 DateTime.AddSeconds 처리 후 DataCenter.set_EnergyNextTime | 016e30bc~016e30fc |
| -29 | GamePlayerInfomation.set_CheckAssetsRandomInt_New 호출 | 016e34a8~016e34d0 |
| -34 | DataCenter.set_ChatChannel 호출 | 016e34dc~016e3508 |
| -36 | DataCenter.set_SupportCVTimes 호출 | 016e3510~016e3540 |
| -23 | key 존재 여부 분기 후 Ali.Notify 호출 | 016e2f54~016e2fdc. Notify의 이벤트 이름/의미는 아직 미확정 |
| -22 | 현재 이 함수의 별도 key 전용 소비 분기 미확인 | 미확정 |
| -20 | 현재 이 함수의 별도 key 전용 소비 분기 미확인 | 미확정 |
| -33 | 현재 이 함수의 별도 key 전용 소비 분기 미확인 | 미확정 |

정정: 기존 미분류 key 7개(-29/-28/-23/-22/-20/-33/-36) 중 -29/-28/-36은 이제 소비 경로가 확인됐다. -27/-34도 기존에 확인한 Mail/ChatChannel 소비가 유지된다. 남은 직접 미확정은 -22/-20/-33과 -23의 Notify 이벤트 의미다. PCAP 값만으로 의미를 부여하지 않고 Listing의 실제 분기를 근거로 기록한다.



## 2026-10-02 ProccessRequestRes의 음수 상수 분기 전체 대조

DataCenter.ProccessRequestRes @ 016e203c 함수 본문에서 음수 key 상수 분기를 전수 확인했다. 명시적 key 상수는 -11, -12, -23, -27, -28, -29, -34, -36이다. 이 중 -11/-12는 UserInfo.MergeVaryData의 Exp/Level key와 겹치며, response 처리 중 추가 알림/level-up 상태 처리도 수행한다. -22/-20/-33은 이 함수 안에서 별도 상수 분기로 나타나지 않는다.

- -11: UserInfo.get_Exp를 읽어 DataCache.m_lastUserExp에 저장한 뒤 UserInfo.MergeVaryData로 이어진다.
- -12: DataCache.levelisup를 1로 설정하는 경로 확인. 실제 Level 상승 UI 소비처는 아직 직접 연결 전.
- -23: key 존재 시 Ali.Notify 호출. 알림 이벤트 이름/의미 미확정.
- -27: DataCenter +0xC0 dictionary에 key/value 복사.
- -28: EnergyNextTime 계산/설정.
- -29: GamePlayerInfomation.CheckAssetsRandomInt_New 설정.
- -34: DataCenter.ChatChannel 설정.
- -36: DataCenter.SupportCVTimes 설정.

이 함수 본문에서 -22/-20/-33의 전용 분기가 없다는 사실은 확인했지만, 다른 함수 또는 Lua 측에서 소비하지 않는다는 뜻은 아니다.

## 2026-10-02 ItemRecord type 8의 box 분류 연결

Bootstrap Main UI 분석 보고서 14.1절의 AliothExtensions.isBoxItem @ 00e166ac Listing에서 BaseData.type이 8, 1, 9일 때 true를 반환한다. 따라서 ItemRecord type 8은 클라이언트의 box item 분류에 포함된다. 다만 이는 UI/인벤토리 분류 판정이며, m_itemPackageId의 CODE*VALUE가 어느 보상 테이블을 조회하는지까지 입증하지 않는다. CODE lookup은 별도 미확정으로 유지한다.


## 2026-10-02 PCAP 실측 — OpCode 2 응답의 field 21 / field 35

원본 Git PCAP JSON `research/PCAP/로그인_출석_퀘스트_우편_토벌_던전_상자_무기제작_강화_kcp/messages.json`의 blob을 직접 파싱했다. packet 묶음 192~201, 서버 `182.92.62.79` → 클라이언트 `10.215.173.1`, 13,313 bytes 응답에서 protobuf 최상위 field 21 반복 엔트리 276개와 field 35 중첩 메시지 1개를 확인했다.

### field 21 — DictI32 음수 key 실측

field 21의 각 map 엔트리는 중첩 field 1=key, field 2=value 구조다. 음수 key는 int64 varint의 2의 보수 값을 signed 64-bit로 해석했다. 이 응답에서 확인된 음수 key는 정확히 13개이며, 기존 `UserInfo.MergeVaryData` 분석 대상과 일치한다.

| key | PCAP value | 기존 클라이언트 소비처/해석 |
|---:|---:|---|
| -29 | 79 | CheckAssetsRandomInt_New 설정 경로 |
| -28 | 94 | EnergyNextTime 계산/설정 경로 |
| -27 | 1 | DataCenter +0xC0 캐시 dictionary 복사 (메일 badge 소비처 확인됨) |
| -23 | 없음 | Ali.Notify 분기, 이벤트 의미 미확정 |
| -22 | 없음 | 직접 소비처 미확정 |
| -20 | 없음 | 직접 소비처 미확정 |
| -18 | 15 | ExamTimes |
| -33 | 없음 | 직접 소비처 미확정 |
| -34 | 1 | ChatChannel |
| -36 | 3 | SupportCVTimes |
| -30 | 없음 | EquipMax |
| -31 | 없음 | ChargeTotalPerMonth |
| -32 | 27 | Age |

정정: 이 특정 OpCode 2 응답에서 확인된 음수 key 13개는 위 표의 -29/-28/-27/-23/-22/-20/-18/-33/-34/-36/-30/-31/-32다. `UserInfo.MergeVaryData`가 소비하는 -9/-10/-11/-12/-13/-14/-15/-16 key 목록과는 다르다. field 21이라는 동일 최상위 번호만으로 서로 다른 Dictionary 인스턴스/응답 구간을 하나로 합치지 않는다. field 2가 생략된 엔트리는 0으로 단정하지 않고 '없음'으로 표기했다.

### field 35 — ProtoUser 중첩 메시지 실측

동일 응답의 최상위 field 35는 wire type 2, offset 2520, length 33인 중첩 메시지다. 내부 protobuf 필드와 값은 다음과 같다.

| ProtoUser wire field | wire type | 실측값 | 현재 해석 |
|---:|---:|---|---|
| 1 | 0 | 871047 | Id로 대응 |
| 3 | 0 | 4 | Level 후보 |
| 4 | 0 | 250 | Exp 후보 |
| 7 | 0 | 18100000 | HeadIcon 후보 |
| 14 | 2 | `g9in2` | Name 후보 |
| 20 | 0 | 3 | 미매핑 |
| 21 | 0 | 3 | 미매핑 |
| 22 | 0 | 10 | 미매핑 |
| 24 | 0 | 1 | 미매핑 |

이 결과로 field 35가 실제 ProtoUser 중첩 payload라는 점과 nested wire field 번호를 확보했다. 다만 3/4/7/14의 속성 대응은 현재 Getter의 객체 offset 및 값 형태와 교차한 후보이며, 생성 protobuf parser/serializer 또는 필드 setter에서 최종 확인해야 한다. 특히 객체 offset(+0x10 등)을 wire tag로 오인하지 않는다.

### 다음 추적 순서

- ProtoUser의 wire field 3/4/7/14 및 20/21/22/24를 Ghidra Listing의 생성 parser/setter 또는 XLua 메타데이터와 대조한다.
- field 21의 276개 전체 엔트리에서 양수 key의 의미를 추측하지 않고, Main UI 소비 함수의 Dictionary 조회 key와 대조한다.
- ItemRecord type 8의 73개 CODE는 아직 lookup 구현을 찾지 못했으므로 box 분류(type 8)와 보상 테이블 조회 의미를 분리해 유지한다.


## 2026-10-02 PCAP field 21/35 재파싱 정정 (이전 표 오류 수정)

앞 절의 field 21 음수 key 표는 protobuf map 중첩 엔트리의 key/value를 잘못 읽어 잘못 기재했다. 아래 표로 대체한다. 원본 blob `5a9f8f12466c2a14fb3769b376f96b6eebc8dfc4`를 hex varint 단위로 재파싱했으며, 이 응답의 field 21 map 엔트리는 276개다.

| 음수 key | field 2 값 | 소비 경로(별도 Listing 근거) |
|---:|---:|---|
| -29 | 79 | GamePlayerInfomation.CheckAssetsRandomInt_New |
| -28 | 94 | DataCenter.EnergyNextTime |
| -27 | 1 | DataCenter +0xC0 dictionary (HomePanel mail badge) |
| -23 | field 2 생략 | key 존재 여부로 Ali.Notify 분기 |
| -22 | field 2 생략 | 전용 소비 분기 미확인 |
| -20 | field 2 생략 | 전용 소비 분기 미확인 |
| -18 | 15 | UserInfo.ExamTimes |
| -33 | field 2 생략 | 전용 소비 분기 미확인 |
| -34 | 1 | DataCenter.ChatChannel |
| -36 | 3 | DataCenter.SupportCVTimes |
| -30 | field 2 생략 | UserInfo.EquipMax |
| -31 | field 2 생략 | UserInfo.ChargeTotalPerMonth |
| -32 | 27 | UserInfo.Age |

field 2가 생략된 것은 wire상 값이 없다는 뜻이다. protobuf map의 기본값 처리 여부는 디코더/런타임 경로를 확인하기 전까지 별도 의미를 부여하지 않는다. 이전 절의 -9/-10/-11/-12/-13/-14/-15/-16 값 표기는 이 packet 192~201 응답의 field 21 목록이 아니므로 이 PCAP 결과 표에서 제거한다. 기존 다른 캡처의 관측값과 혼합하지 않는다.

### ProtoUser wire tag 교차 확인

Ghidra Listing getter의 객체 offset:
- `ProtoUser.get_Id @ 015adb0c` → +0x10
- `get_Level @ 015adb2c` → +0x1C
- `get_Exp @ 015adb3c` → +0x20
- `get_HeadIcon @ 015adb6c` → +0x2C
- `get_Name @ 015adb7c` → +0x30

PCAP field 35의 실제 nested 값/형태를 위 속성과 대조하면 다음 대응이 성립한다.
- wire field 1 → Id = 871047
- wire field 3 → Level = 4
- wire field 4 → Exp = 250
- wire field 7 → HeadIcon = 18100000
- wire field 14 (length-delimited UTF-8) → Name = `g9in2`

이는 서로 다른 증거 두 가지(실제 nested protobuf payload와 해당 속성 getter의 객체 offset/타입)를 교차한 결과다. 따라서 기본 5개 속성의 wire tag는 위와 같이 확정 기록한다. wire field 20/21/22/24는 현재 ProtoUser 속성명에 연결할 증거가 없어 미매핑으로 둔다. getter의 객체 offset은 wire tag가 아니며, tag 대응은 PCAP nested payload로부터 확인했다.


## 2026-10-02 ItemRecord type 8의 Main 창고 UI 소비 경로 확정

기준 Listing: `research/Ghidra_Listing_txt/DA.txt`, `WA.txt`, `AL/00e166ac_AliothExtensions__isBoxItem.txt`.

- `AliothExtensions.isBoxItem @ 00e166ac`는 `BaseData.get_type`이 8, 1, 9인 경우 true.
- `DataCenter.RefreshBoxList @ 016e6c64`는 DataCenter Items cache(+0x78)를 입력으로 받고, XLua delegate predicate(`DataCenter.<>c.<RefreshBoxList>b__89_0 @ 016ea0d4`)에서 `isBoxItem`을 적용한다.
- 필터 결과는 `DataTool.ToListByGroup @ 016e6ecc` 및 OrderBy/ToList를 거쳐 DataCenter BoxSupplyList(+0xE8)에 저장된다.
- `DataCenter.get_BoxSupplyTotalCount @ 016e6b58`는 BoxSupplyList 각 항목의 수량(+0x18)을 합산한다.
- 호출자는 `HomePanelMono.RefreshWareHouse_Supply @ 00f6a2ec`, `WareHousePanelMono.RefreshPoint_Supply @ 0104d2b8`, `OpenBoxMono.RefreshUI @ 00e9b8dc`다.
- `WareHousePanelMono.OnClickOpenBox @ 0104cd6c`는 선택 item을 가져와 ItemData를 조회하고 `isBoxItem` 재검사 후 OpenBox 화면을 연다.

따라서 type 8은 단순히 분류 조건에만 들어가는 것이 아니라, 실제 Items cache → BoxSupplyList → Main Warehouse Supply 숫자 및 OpenBox 화면 진입 경로에 포함된다. 단, 이 경로는 type 8의 보유/표시를 설명할 뿐, `m_itemPackageId`의 소형 CODE를 해석하는 보상 데이터 lookup까지 증명하지 않는다.

### 현재 type 8 연결 상태

```text
Bootstrap field 38 Items
  → DataCenter Items cache (+0x78)
  → RefreshBoxList
  → isBoxItem(type 1 / 8 / 9)
  → BoxSupplyList (+0xE8)
  → get_BoxSupplyTotalCount (sum item quantity)
  → HomePanelMono.RefreshWareHouse_Supply
  → lbl_wareHouseBoxNum / point_wareHouse

WareHousePanelMono.OnClickOpenBox
  → selected ItemData
  → isBoxItem 재검사
  → OpenBox 화면
```

미확정: OpenBox 화면 내부에서 type 8의 `m_itemPackageId` CODE*VALUE를 실제 구성품/보상으로 변환하는 resolver. 다음은 `OpenBoxMono.RefreshUI @ 00e9b8dc`와 그 하위 Lua delegate 및 ItemDataWrap property 접근을 추적한다.


## 2026-10-02 OpenBox UI 소비 경로 추가 추적

기준: `research/Ghidra_Listing_txt/OP.txt` (Git blob SHA `b759fbf4bf1c43a02fde5e47cbd74c940fb0cb7d`).

### 보유 상자 목록 → UI

- `OpenBoxMono.RefreshUI @ 00e9b8dc`에서 `DataCenter.RefreshBoxList @ 016e6c64` 호출 후 `ConfigBoxWidget @ 00e9ba1c`, `ConfigCurrentBoxWiget @ 00e9be08` 호출.
- `ConfigBoxWidget`은 OpenBoxMono의 목록(+0xD0)을 순회하고, 각 항목의 +0x10 값을 item ID로 사용해 `Ali.GetExcelData<ItemData>` 조회.
- 조회한 ItemData의 표시 데이터(아이콘/텍스트)를 UI node에 연결하고 클릭 이벤트를 구성한다.
- 이는 type 8이 Items cache → BoxSupplyList에 들어온 뒤, 상자 ID 기반으로 ItemData를 조회해 선택 UI를 만드는 경로다. 여기서 `m_itemPackageId`를 직접 읽거나 CODE를 해석하는 동작은 확인되지 않았다.

### 개봉 요청 응답 → 결과 연출

- `OpenBoxMono.OnOpenBox @ 00e9c81c`는 요청의 `Res`를 확인하고, `Res +0xD8` 목록이 비어 있지 않으면 OpenBoxShowPanel 화면을 연다.
- `OpenBoxShowPanelMono.DemandOpen @ 00e9cdbc`는 같은 응답 `Res +0xD8` 목록을 패널 `+0xD0`에 보관한다. 각 결과 항목의 `+0x10` 값을 item ID로 `Ali.GetBaseData`에 전달하고 star 값을 확인해 결과 연출 상태(+0xE8)를 갱신한다.
- `NormalShowEff @ 00e9e5f4` / `WeaponShowEff @ 00e9e540`는 결과 목록의 현재 index 항목에서 `+0x10` item ID를 읽어 각각 `ItemShowNormalMono.SetItem` / `ItemShowWeaponMono.SetItem`으로 전달한다.
- `ShowFinish @ 00e9e6a8`는 최종적으로 `Ali.ShowReward`에 응답 결과 목록(`+0xD0`)을 전달한다.

### 이번 단계 판정

```
보유 type 8 item
  → DataCenter.RefreshBoxList / BoxSupplyList
  → OpenBoxMono.ConfigBoxWidget
  → ItemData 조회 및 상자 선택 UI

OpenBox 요청
  → Request.Res (+0xD8 result list)
  → OpenBoxShowPanelMono.DemandOpen
  → 각 result entry +0x10 = concrete item ID
  → NormalShowEff / WeaponShowEff
  → Ali.ShowReward
```

이 UI/연출 경로에서는 `m_itemPackageId`의 CODE*VALUE를 클라이언트가 직접 구성품 ID로 변환하는 동작이 확인되지 않았다. 오히려 개봉 응답 목록에 이미 구체적인 보상 item ID가 들어와 UI가 이를 조회/표시하는 흐름이다. 따라서 type 8 CODE의 해석은 이 화면 경로가 아니라 ItemData의 다른 사용처 또는 요청/서버 응답 생성 전 단계에 남아 있다. 서버 구현은 분석 범위에서 제외한다.

다음 추적은 `ItemData.get_itemPackageId @ 00df09a8`의 실제 동적 호출처와 XLua property getter 노출 여부다. OpenBox의 보유/개봉 UI는 CODE resolver의 직접 근거로 사용하지 않는다.


### 2026-10-02 OpenBox 처리 상세 — 보유목록과 개봉결과 분리

추가 기준 Listing: `research/Ghidra_Listing_txt/OP.txt`, blob SHA `b759fbf4bf1c43a02fde5e47cbd74c940fb0cb7d`.

- `OpenBoxMono.ConfigBoxWidget @ 00e9ba1c`: BoxSupplyList 기반 상자 보유목록을 표시한다. 목록 항목의 `+0x10`은 보유 상자 Item ID로 사용되며 `Ali.GetExcelData<ItemData>` 조회로 이름/아이콘 UI를 구성한다.
- `OpenBoxMono.OnOpenBox @ 00e9c81c`: 요청 결과 `Request.Res +0xD8` 목록이 존재하고 1개 이상일 때 OpenBoxShowPanel 화면으로 이동한다.
- `OpenBoxShowPanelMono.DemandOpen @ 00e9cdbc`: 응답 목록을 패널 `+0xD0`에 저장하고, 각 결과 entry의 `+0x10` ID로 `Ali.GetBaseData`를 조회한다. star 값 등을 검사해 연출 상태를 설정한다.
- `NormalShowEff @ 00e9e5f4`와 `WeaponShowEff @ 00e9e540`: 같은 결과 목록의 현재 index entry에서 `+0x10` ID를 읽어 각각 ItemShowNormalMono/ItemShowWeaponMono의 SetItem으로 전달한다.
- `ShowFinish @ 00e9e6a8`: 결과 목록(`+0xD0`)을 `Ali.ShowReward`에 전달한다.

**경로 분리 결론:** 보유 상자 UI는 클라이언트 ItemRecord/ItemData를 통해 상자 아이콘과 목록을 만든다. 반면 개봉 연출은 응답에 포함된 구체적인 보상 item ID 목록을 조회해 보여준다. 확인한 OpenBox 경로 어디에도 `ItemData.get_itemPackageId` 또는 type 8 CODE*VALUE를 직접 읽는 호출은 없다. 따라서 type 8의 소형 CODE lookup은 아직 다른 소비 경로에 남아 있으며, OpenBox 화면만으로 해당 CODE가 어떤 패키지/보상 테이블인지 확정할 수 없다.


### 2026-10-02 PCAP 실측 추가 — OpInfo field 21 / ProtoUser field 35

기준 원본: `research/PCAP/로그인_출석_퀘스트_우편_토벌_던전_상자_무기제작_강화_kcp/messages.json` (blob SHA `5a9f8f12466c2a14fb3769b376f96b6eebc8dfc4`). 이 파일은 65개 레코드이며, 대상 응답은 패킷 192~201 묶음이다. protobuf 트리에서 field 21의 map entry 276개와 field 35의 nested message 1개를 확인했다.

#### field 21 map 실측

- 276개 entry 중 양수 key 263개, 음수 key 13개.
- 음수 key와 값: `-29=79`, `-27=1`, `-28=94`, `-23=0`, `-22=0`, `-18=15`, `-20=0`, `-33=0`, `-34=1`, `-36=3`, `-30=0`, `-31=0`, `-32=27`.
- 음수 key는 protobuf int64 varint를 signed 64-bit로 해석해 복원했다. 기존 JSON 변환본의 숫자 필드는 64-bit 정밀도를 잃을 수 있어, 원본 `prefix_hex`의 varint 바이트를 기준으로 판정했다.
- 양수 key 대부분은 21xxxxxx / 218xxxxx / 948xxxxx / 982xxxxx 계열이다. 따라서 이 field 21은 음수 상태 key뿐 아니라 다수의 양수 ID key도 담는 map 구조다.
- 앞선 정적 분석에서 확인한 `UserInfo.MergeVaryData` 소비 key 중 이번 응답에 실제로 나타난 것은 `-18,-30,-31,-32,-34`다. 이번 값은 기존 PCAP 기록의 값(ExamTimes 15, EquipMax 0, ChargeTotalPerMonth 0, Age 27, ChatChannel 1)과 일치한다.
- `-27=1`은 HomePanelMono의 메일 뱃지 소비와 수치상 연결 후보지만, 해당 UI 경로가 읽는 DataCenter 캐시 Dictionary(+0xC0)와 OpInfo field21의 동일 객체 여부는 아직 입증되지 않았다. `-28=94`, `-29=79`, `-36=3`도 소비처 미확정이다.

#### field 35 nested ProtoUser 실측

field 35 payload (offset 2520, length 33):
`08879535180420fa0138a0ded00872056739696e32a00103a80103b0010ac00101`

nested protobuf tag:
- tag 1 / wire 0 = 871047
- tag 3 / wire 0 = 4
- tag 4 / wire 0 = 250
- tag 7 / wire 0 = 18100000
- tag 14 / wire 2 = UTF-8 문자열 `g9in2`
- tag 20 / wire 0 = 3
- tag 21 / wire 0 = 3
- tag 22 / wire 0 = 10
- tag 24 / wire 0 = 1

ProtoUser native property 접근자는 별도 Listing에서 확인:
- Id: getter/setter 모두 객체 +0x10
- Level: +0x1C
- Exp: +0x20
- HeadIcon: +0x2C
- Name: +0x30

tag 1의 871047은 User 식별자 형태이며 tag 14의 문자열은 Name 속성 후보로 볼 수 있다. 다만 tag 3/4/7/20/21/22/24와 Level/Exp/HeadIcon의 대응은 아직 확정하지 않았다. 객체 메모리 offset(+0x1C 등)은 protobuf wire tag가 아니므로 offset 숫자만으로 tag를 매핑하지 않는다. 실제 ProtoUser parser/serializer의 tag 처리 또는 런타임 setter 추적이 다음 확인 대상이다.

#### 다음 추적

1. ProtoUser의 생성/역직렬화 parser에서 tag 3/4/7/20/21/22/24가 쓰는 setter 확인.
2. DictI32의 미확정 key -29/-28/-27/-23/-22/-20/-33/-36 소비처를 UI 및 XLua 경로에서 역추적. 특히 HomePanel의 -27은 객체 출처를 분리 검증.
3. ItemData.get_itemPackageId(+0x90)의 XLua wrapper 및 동적 호출처 검색은 별도 유지. 이번 PCAP은 ItemRecord type 8 CODE resolver를 직접 입증하지 않는다.


### 2026-10-02 교차 문서 대조 — Bootstrap field 21 / ProtoUser 속성 후보

서버 작업 진행 문서 `research/reports/서버쪽작업진행상황/2026-10-02-Bootstrap-실측-protobuf-구조_lina.md` 및 `2026-10-02-개발-핸드오프_lina.md`와 PCAP 원본을 대조했다.

- 서버측 문서에서는 최상위 field 21을 Items(276개)로 분류하고, field 35를 User, field 43을 Chapters(61개)로 분류한다.
- 이번 PCAP 원본의 field 21에는 실제로 양수 ID key 263개와 음수 key 13개가 함께 들어 있다. 따라서 field 21을 "아이템 수량 전용"으로만 해석하면 안 된다. 양수 key는 아이템 ID/count map 패턴이며, 음수 key는 클라이언트 `UserInfo.MergeVaryData`가 읽는 상태값 계열이 섞인 형태다.
- 원본 JSON 변환 과정에서 64-bit unsigned varint가 JavaScript Number 정밀도를 잃을 수 있다. `-29`의 경우 변환 JSON의 숫자값 대신 원본 hex `08e3ffffffffffffffff01104f`를 varint로 복원해 signed int64 -29, value 79로 확인했다. 향후 signed key 분석은 hex를 기준으로 한다.

ProtoUser tag와 native 속성의 후보 대응:
| protobuf tag | 실측 값 | native 속성 후보 | 판단 |
|---|---:|---|---|
| 1 | 871047 | Id | 강한 후보: User ID 값 및 Id getter/setter 존재 |
| 3 | 4 | Level | 후보: 정수 레벨 형태 |
| 4 | 250 | Exp | 후보: 정수 경험치 형태 |
| 7 | 18100000 | HeadIcon | 후보: 숫자형 아이콘 식별자 형태 |
| 14 | `g9in2` | Name | 강한 후보: 문자열 username |
| 20 | 3 | 미확정 | 미확정 |
| 21 | 3 | 미확정 | 미확정 |
| 22 | 10 | 미확정 | 미확정 |
| 24 | 1 | 미확정 | 미확정 |

위 표의 tag 3/4/7은 값의 형태와 알려진 ProtoUser 속성 목록에 따른 후보일 뿐, 현재 PCAP만으로 직접 매핑을 확정하지 않았다. 객체 offset은 Id +0x10, Level +0x1C, Exp +0x20, HeadIcon +0x2C, Name +0x30으로 확인되지만 이 offset은 wire tag를 뜻하지 않는다. ProtoUser 생성자는 System.Object 생성자만 호출하며, 별도의 ProtoUser 전용 parser/serializer는 현재 Listing 검색에서 발견하지 못했다. `KCPTube.TryRead`의 `ProtoBuf.Serializer.Deserialize<object>`가 역직렬화 진입점이므로, 실제 tag→setter 대응은 generic protobuf runtime 또는 런타임 setter hook으로 확인해야 한다.

### 소비처 추적 현재 판정

- `-18,-30,-31,-32,-34`는 UserInfo.MergeVaryData에서 직접 속성으로 변환되는 것을 정적으로 확인했고, PCAP 값도 일치한다.
- `-27`은 HomePanel 메일 뱃지에서 동일한 숫자 key가 보이지만, 해당 함수가 읽는 대상은 DataCenter cache +0xC0 Dictionary다. OpInfo field21의 map 객체와 동일하다는 증거가 없으므로 연결하지 않는다.
- `-29,-28,-23,-22,-20,-33,-36`은 이번 응답의 실제 값만 확인했다. 정적 Listing에서 직접 소비하는 메서드가 아직 특정되지 않아 의미를 부여하지 않는다.
- 다음 단계는 field21을 역직렬화한 직후 실제 Dictionary 객체와 DataCenter cache +0xC0 객체의 주소를 Frida에서 비교하고, 미확정 key에 대한 `ContainsKey/get_Item` 호출 스택을 수집하는 것이다. 이는 서버 응답 생성이 아니라 클라이언트 수신/저장/소비 경로 검증이다.


## 2026-10-02 후속 작업 — 소비처/XLua 경계 재확인

### ProtoUser wire tag 확정

PCAP JSON packet group 192~201의 OpInfo 최상위 field 35(length 33)를 재확인했다. nested field와 Ghidra ProtoUser getter를 대조한 기본 속성 매핑은 다음과 같다.

| wire tag | 속성 | PCAP 값 |
|---:|---|---:|
| 1 | Id | 871047 |
| 3 | Level | 4 |
| 4 | Exp | 250 |
| 7 | HeadIcon | 18100000 |
| 14 | Name | `g9in2` |

tag 20/21/22/24는 값 3/3/10/1이 관측되지만 아직 속성 미확정이다. getter에서 확인한 객체 offset(+0x10/+0x1C/+0x20/+0x2C/+0x30)은 wire tag가 아니다. 현재 근거 수준에서 기본 5개 tag는 확정하고 나머지는 보류한다.

### DictI32 field 21 — ProccessRequestRes 분기 대조

DA.txt의 `DataCenter.ProccessRequestRes @ 016e203c` 본문을 다시 읽어 signed key 상수와 실제 동작을 대조했다.

| key | 분기/동작 | 현재 의미 |
|---:|---|---|
| -29 | `GamePlayerInfomation.set_CheckAssetsRandomInt_New` | random asset seed/state |
| -28 | `DateTime.AddSeconds` → `DataCenter.set_EnergyNextTime` | 에너지 회복 시각 |
| -27 | DataCenter cache Dictionary(+0xC0)에 key/value 저장 → HomePanel mail badge | 메일 unread count |
| -23 | key 존재 검사 후 `Ali.Notify` | 이벤트 이름/의미 미확정 |
| -22 | 이 함수에서 전용 key 비교/소비 분기 미발견 | 다른 경로 소비 여부 미확정 |
| -20 | 이 함수에서 전용 key 비교/소비 분기 미발견 | 다른 경로 소비 여부 미확정 |
| -18 | `UserInfo.MergeVaryData`에서 ExamTimes | 시험 횟수 |
| -34 | `DataCenter.set_ChatChannel` | 채팅 채널 |
| -36 | `DataCenter.set_SupportCVTimes` | Support CV 횟수 |
| -30/-31/-32 | `UserInfo.MergeVaryData`에서 EquipMax/ChargeTotalPerMonth/Age | UserInfo 속성 |

주의: -22/-20/-33은 이 함수의 해당 구간에서 전용 key 분기가 보이지 않는다는 뜻이다. 프로젝트 전체에서 읽히지 않는다는 결론은 아니다. -33도 마찬가지로 이 함수의 전용 분기는 찾지 못했다. -23은 Notify 호출 자체는 확인됐으나 Notify 인자에 대응하는 이벤트 명칭을 아직 풀지 못했다.

이번 packet group 192~201에서 field 21은 276개 map entry이며, 양수 key 263개와 음수 key 13개다. 음수 key 값은 -29=79, -28=94, -27=1, -23=0, -22=0, -20=0, -18=15, -33=0, -34=1, -36=3, -30=0, -31=0, -32=27이다. 생략된 map value는 protobuf 기본값 0으로 처리했다. 이는 이 캡처의 값이며 고정 상수가 아니다.

### ItemDataWrap / type 8 CODE lookup 경계

Git Listing 검색을 재수행했다.

- `ItemData.get_itemPackageId @ 00df09a8`: `ldr x0,[x0,#0x90]` 후 반환. 즉 ItemData 객체의 +0x90 참조를 제공한다.
- `ItemData.ctor @ 00df09c8`의 Calls IN에는 `XLua.CSObjectWrap.ItemDataWrap.__CreateInstance @ 012cedf8`가 있다.
- `ItempackageData.ctor @ 00df09d4`도 `ItempackageDataWrap.__CreateInstance @ 012d05dc`에서 생성된다.
- IT.txt에는 ItemDataWrap의 생성자 참조만 있고 wrapper getter 본문은 없다. XL/CS/XU/WR listing 및 Git 코드 검색에서도 `_g_get_itemPackageId` 구현은 확인되지 않았다.
- 따라서 ItemData의 C# getter 존재 및 XLua 타입 노출은 확인됐지만, Lua에서 이 속성을 실제 읽는 스크립트와 type 8의 CODE 1~425를 해석하는 lookup collection은 아직 연결되지 않았다.

OpenBox 경로는 type 8 보유/표시 및 응답의 구체 item ID 연출을 설명하지만, CODE*VALUE를 구성품 ID로 해석하는 resolver는 포함하지 않는다는 기존 판정을 유지한다.

### 다음 실행 작업

1. 런타임에서 `ItemData.get_itemPackageId` 반환 객체와 Lua property getter 호출 stack을 기록하고 CODE 문자열을 소비하는 호출자를 찾는다.
2. `Dictionary<int,int>.ContainsKey/get_Item`에서 key -22/-20/-33 및 -23 Notify 분기의 호출 stack을 수집한다.
3. 양수 key 263개는 Main UI getter의 실제 key 목록과 교차할 때만 의미를 부여한다. 숫자 ID 패턴만으로 명칭을 추정하지 않는다.


## 2026-10-02 후속 실측 — PCAP protobuf 원문 재확인

대상: `research/PCAP/로그인_출석_퀘스트_우편_토벌_던전_상자_무기제작_강화_kcp/messages.json`의 Git blob을 기준으로 확인. `packets` 배열에 192가 포함된 메시지 레코드 1건을 추출했다.

### OpInfo field 21 (DictI32)

- field 21의 map entry 276건을 확인했다.
- key는 protobuf varint를 signed int32로 해석했다. 이때 10바이트 음수 varint를 JavaScript Number로 먼저 변환하면 정밀도가 깨지므로, 원본 `prefix_hex` 바이트에서 BigInt로 직접 디코딩했다.
- 해당 캡처에서 관측된 음수 key와 값:
  - `-29=79`, `-28=94`, `-27=1`
  - `-23=0`, `-22=0`, `-20=0`
  - `-18=15`
  - `-33=0`, `-34=1`, `-36=3`
  - `-30=0`, `-31=0`, `-32=27`
- 따라서 기존에 정리한 13개 음수 key 목록과 일치한다. 이번에는 그중 미확인 소비처 후보인 `-29/-28/-27/-23/-22/-20/-33/-36`의 실제 캡처 값도 확보했다.
- 값의 의미는 별도 소비 코드 연결 전까지 추정하지 않는다. 특히 `-27=1`은 앞서 확인한 HomePanel 메일 배지의 DataCenter 캐시 key `-27`과 숫자만 같으며, 이 PCAP DictI32가 해당 UI 캐시로 직접 연결된다는 증거는 아직 없다.

### OpInfo field 35 (ProtoUser 후보 payload)

같은 메시지의 field 35 length-delimited payload는 33바이트이며, 내부 protobuf 필드는 다음과 같이 파싱된다.

| wire field | wire type | 관측값 |
|---|---:|---|
| 1 | varint | 871047 |
| 3 | varint | 4 |
| 4 | varint | 250 |
| 7 | varint | 18100000 |
| 14 | length-delimited | `g9in2` |
| 20 | varint | 3 |
| 21 | varint | 3 |
| 22 | varint | 10 |
| 24 | varint | 1 |

- field 35가 ProtoUser payload라는 기존 OpInfo 구조와 부합하는 중첩 protobuf 구조를 확인했다.
- field 1의 871047 및 field 14의 문자열 `g9in2`는 이 캡처에서 확인된 원시 필드값이다.
- 현재 확인한 Ghidra의 ProtoUser getter 객체 오프셋(+0x10, +0x1C, +0x20, +0x2C, +0x30)은 protobuf wire field 번호가 아니다. 따라서 field 1=Id, field 14=Name 같은 매핑은 parser/serializer 또는 런타임 대조 전까지 확정하지 않는다.
- 이 샘플에서 field 2(Level 후보), field 5(Exp 후보), field 11(HeadIcon 후보)는 나타나지 않았다. ProtoUser의 실제 필드 번호 전체를 확정할 자료는 아직 부족하다.

### 다음 작업 — 한 단계씩

1. `ProtoUser`의 생성/역직렬화 경로에서 field 번호와 객체 멤버 offset의 대응을 찾는다. 우선 generated parser/serializer 및 setter 참조를 조사한다.
2. 음수 key의 소비처는 `-29/-28/-27/-23/-22/-20/-33/-36` 각각에 대해 Ghidra 상수 참조와 Dictionary 접근 호출자를 좁혀 추적한다.
3. type 8 CODE는 XLua getter가 노출된 사실까지만 확인됐다. Lua lookup 구현이 확보되기 전에는 코드 의미를 부여하지 않는다.


### 2026-10-02 후속 실측 — ProtoUser 실제 protobuf nested field

PCAP 변환 JSON의 packet group `192~201`에서 OpInfo field 35를 다시 분리했다. field 35는 wire type 2, offset 2520, length 33이며 nested protobuf field 9개가 확인된다.

| protobuf tag | wire | 관측값 |
|---:|---:|---|
| 1 | 0 | 871047 |
| 3 | 0 | 4 |
| 4 | 0 | 250 |
| 7 | 0 | 18100000 |
| 14 | 2 | `g9in2` |
| 20 | 0 | 3 |
| 21 | 0 | 3 |
| 22 | 0 | 10 |
| 24 | 0 | 1 |

이 캡처에서는 tag 1/3/4의 값이 각각 Id/Level/Exp의 자료형·값 패턴과 일치하고, tag 14는 문자열로서 Name 후보에 해당한다. 다만 현재 Listing에서 확인한 ProtoUser getter의 객체 offset(+0x10/+0x1C/+0x20/+0x2C/+0x30)은 메모리 배치이지 protobuf tag 선언이 아니다. 따라서 tag 1=Id, 3=Level, 4=Exp, 14=Name은 강한 실측 후보로 기록하되, generated parser 또는 setter 호출에서 최종 대조 전까지 확정 매핑으로 승격하지 않는다. tag 7 및 20/21/22/24는 속성명을 아직 연결하지 않는다.

중요: 이 캡처의 ProtoUser 값은 이전 Frida 로그의 계정(871053, Level 53, Exp 1100)과 다른 사용자/시점의 값(871047, Level 4, Exp 250)이다. 값 자체를 동일 세션 데이터처럼 합치지 않는다.

### 다음 단계 — ProtoUser 필드명 확정

1. `ProtoUser.set_*` 전체 Listing에서 필드별 객체 offset을 수집한다.
2. protobuf parser가 nested tag 7/14/20/21/22/24를 처리할 때 호출하는 setter 또는 backing-field offset을 찾는다.
3. 확인된 매핑만 UserInfo 속성 및 Main UI 소비처 표에 반영한다.


### 2026-10-02 후속 실측 — ProtoUser backing field 전체 offset

ProtoUser setter Listing을 개별 확인해 getter offset을 교차 검증했다. setter는 아래 offset에 직접 저장한다.

| ProtoUser 속성 | 객체 offset |
|---|---:|
| Id | +0x10 |
| Status | +0x18 |
| Level | +0x1C |
| Exp | +0x20 |
| VIPLevel | +0x24 |
| VIPExp | +0x28 |
| HeadIcon | +0x2C |
| Name | +0x30 |
| SId | +0x38 |
| StigmataTimes | +0x40 |
| MetaphysicsTimes | +0x44 |
| SignInDays | +0x48 |
| SignInRewardDay | +0x4C |
| FCTimes | +0x50 |
| StepId | +0x54 |
| Belt | +0x58 |

이 결과로 ProtoUser의 실제 속성/메모리 배치는 구체화됐다. 다만 protobuf nested payload에서 관측한 tag 7, 20, 21, 22, 24를 위 속성 중 어느 것에 대응시키는지는 아직 증명되지 않았다. 객체 offset 순서와 protobuf tag 번호를 같은 것으로 간주하지 않는다.


## 2026-10-02 후속 실측 — ProtoUser setter 및 PCAP 표본 범위

- Ghidra 개별 Listing에서 ProtoUser setter를 확인했다.
  - `ProtoUser.set_Id @ 015adb14`: `str x1,[x0,#0x10]`
  - `ProtoUser.set_Level @ 015adb34`: `str w1,[x0,#0x1c]`
  - `ProtoUser.set_Exp @ 015adb44`: `str w1,[x0,#0x20]`
  - `ProtoUser.set_Name @ 015adb84`: `str x1,[x0,#0x30]!` 후 문자열 write barrier 호출
  - `ProtoUser.ctor @ 015adc0c`는 기본 Object 생성자 호출만 확인된다.
- 따라서 앞서 정리한 +0x10/+0x1C/+0x20/+0x30은 getter뿐 아니라 setter에서도 교차 확인된다. 하지만 setter에는 protobuf wire field 번호가 나타나지 않는다.
- 동일 PCAP JSON 전체 65개 메시지 레코드를 확인한 결과, field 35 중첩 payload는 1건뿐이다. 따라서 현재 캡처만으로는 field 번호와 Id/Level/Exp/Name을 값 대조하는 다중 표본 분석이 불가능하다.
- 현재 field35 payload에서 확인되는 건 field1=871047, field14=`g9in2` 등 wire 원시값뿐이다. field1=Id 또는 field14=Name이라는 가설은 유력 후보로만 두고 확정하지 않는다.


### 2026-10-02 후속 실측 — DictI32 음수 key 실제 분기 상수 재수집

`DataCenter.ProccessRequestRes @ 016e203c`의 전체 Listing에서 `mov w1,#...` 상수를 추출해 signed 32-bit로 변환했다. 이 함수에서 확인된 key 상수는 `-11, -12, -23, -27, -28, -29, -34, -36`이다. 이 함수에서 -22/-20/-33은 직접 key 상수로 사용되지 않는다.

추가로 분기 본문을 확인한 내용:

- **-11**: key 존재 시 UserInfo.get_Exp를 읽어 DataCache.set_m_lastUserExp에 저장한 뒤 UserInfo.MergeVaryData를 실행한다.
- **-12**: key 존재 시 DataCache.set_levelisup(1)을 호출한다. 이후 UserInfo.Level 값에 따라 UI/기능 분기가 이어진다. 해당 key의 정수 value 자체를 읽는 코드는 이 분기 초입에서 확인되지 않아 존재 여부 기반 trigger로 기록한다.
- **-23**: key 존재 검사를 통과하면 후속 알림 처리 분기로 이어진다. 현재 Listing Calls OUT에 Ali.Notify가 존재하나, 호출 인자와 이벤트 이름의 정확한 대응은 추가 추적 대상이다.
- **-27**: key/value를 DataCenter 객체 +0xC0의 Dictionary에 기록하는 분기다. HomePanel mail badge 소비와 연결된다.
- **-28**: key value를 초 단위로 DateTime.AddSeconds 처리한 뒤 DataCenter.set_EnergyNextTime에 전달한다.
- **-29**: GamePlayerInfomation.set_CheckAssetsRandomInt_New 분기로 이어진다.
- **-34**: DataCenter.set_ChatChannel.
- **-36**: DataCenter.set_SupportCVTimes.

주의: 이 함수에 key 상수로 나타나는지와 프로젝트 전체에서 사용되는지는 별개다. -22/-20/-33은 이 함수에 상수가 없다는 사실만 확인했으며, 전체 미사용으로 결론내리지 않는다.


### 2026-10-02 후속 실측 — 미분류 DictI32 key 정적 상수 검색

Ghidra Listing 전체 Git 검색에서 signed key의 32-bit 상수 표기를 교차 검색했다.

- -22 (0xffffffea): 검색 결과는 BrotliDecoderDecompressStream 내부 상태/오류 처리 상수뿐이다. Dictionary key 인자나 DataCenter 접근이 없어 DictI32 소비 근거가 아니다.
- -20 (0xffffffec): 동일하게 Brotli decoder의 반환/상태 경로에서만 확인되며 DictI32 소비 근거가 아니다.
- -33 (0xffffffdf): 현재 Listing 검색 결과 없음.

따라서 현재까지 -22/-20/-33을 field 21 DictI32 key로 직접 읽는 클라이언트 함수는 발견하지 못했다. 숫자 상수만 일치하는 Brotli 내부 코드를 소비처로 잘못 연결하지 않는다. 다음 확인은 런타임에서 해당 key의 Dictionary ContainsKey/get_Item 호출 stack을 수집하는 것이다.


### ProtoUser wire tag 7 교차 검증 — HeadiconRecord

PCAP field 35 내부 tag 7의 값 18100000은 Git 원본 HeadiconRecord.json의 실제 레코드 ID와 일치한다. 해당 레코드는 m_id.hiddenValue=18016060, currentCryptoKey=444444이며 XOR 복원값은 18100000이고, m_icon은 headIcon_18100000이다. ProtoUser.set_HeadIcon은 객체 +0x2C에 저장한다.

따라서 tag 7 → ProtoUser.HeadIcon은 단순 값 형태 추정이 아니라 원본 HeadiconRecord ID 및 setter와 교차 확인된 매핑으로 확정한다. tag 3/4는 Level/Exp 후보로 유지하며, tag 20/21/22/24는 미매핑이다.
