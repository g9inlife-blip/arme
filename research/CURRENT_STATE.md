# Current State

## Game
- Package: `com.thumbage.heroes.google`
- Engine: Unity / IL2CPP
- Architecture investigated: ARM64

## Runtime status (latest verified)
현재까지의 실제 실행 결과를 기준으로 다음 상태를 확정한다.

### 1. 업데이트 우회
- 기존 업데이트 진입/실패를 일으키는 온라인 업데이트 경로에 대한 우회 패치가 적용된 상태다.
- 따라서 **업데이트 우회 자체는 현재 성공(O)** 으로 기록한다.
- 단, 이것은 로그인/게임 서비스 전체의 온라인 의존성을 제거한 것이 아니다.

### 2. 네트워크 연결 상태에서의 로그인
- Wi-Fi/모바일 데이터 등 네트워크가 연결되어 있으면, **업데이트 우회가 적용된 상태에서도 기존 정상 로그인 경로가 그대로 실행된다.**
- 즉, 현재 패치는 로그인 네트워크 요청을 차단하거나 로컬 로그인으로 대체한 것이 아니다.
- 등록되어 있는 계정정보를 이용한 **실제 서버 로그인/인증 및 이후 데이터 처리**가 계속 수행된다.
- 따라서 현재 빌드에서는 `업데이트 우회 후에도 서버를 통한 정상 로그인 경로가 살아 있다`고 기록한다.

### 3. 네트워크가 완전히 끊긴 상태에서의 로그인
- Wi-Fi/모바일 데이터 등 네트워크를 전부 차단한 상태에서는 로그인 화면에서 **무한 로딩**이 발생한다.
- 즉, 오프라인 상태에서 로그인 실패 화면으로 명확하게 종료되는 것이 아니라, **로그인 완료를 위해 필요한 네트워크 응답/콜백/상태 전이가 끝나지 않는 상태**로 남는다.
- 따라서 현재 상태에서는 **오프라인 로그인 자체가 성립하지 않는다.**

### 4. 현재 런타임 상태의 정확한 표현
```text
업데이트 우회 O
    ↓
로그인 화면
    ↓
┌──────────────────────┬────────────────────────┐
│ 네트워크 연결 O       │ 네트워크 완전 차단 X   │
│                      │                        │
│ 서버 정상 로그인 O   │ 로그인 무한 로딩 X     │
│      ↓               │      ↓                 │
│ 메인 메뉴 진입 가능   │ 로그인 완료 안 됨      │
└──────────────────────┴────────────────────────┘
```

현재 오프라인 실패의 최초 확실한 지점은 **메인 메뉴가 아니라 로그인 단계의 무한 로딩**이다.

---

## 핵심 아키텍처 가설
온라인 상태에서 관찰되는 패턴:

`로그인 → 네트워크 로딩 → 메인 화면 → 네트워크 로딩 → 상점 → 네트워크 로딩 → 맵 → 네트워크 로딩 → 맵 상세 → 네트워크 로딩 → 전투 → 네트워크 로딩 → 전투 결과 → 네트워크 로딩 → 특가상점 → 네트워크 로딩 → 뽑기 ...`

메뉴가 표시된 이후에도 기능 진입과 행동 결과의 경계에서 서버 통신이 반복되는 구조로 보인다.

로컬에서 보이는 재화 값을 변경해도 결과 처리 시 서버 상태가 기준이 되는 현상이 관찰되므로, 단순 메모리 값 변경만으로 서버 authoritative state를 대체할 수 없다고 판단한다.

로컬 Save 파일의 존재 여부는 아직 미확정이며, 존재한다고 가정하지 않는다.

---

# Offline Result / State Architecture

## 핵심 원칙
오프라인화는 단순히 `Network Request → 항상 성공` 또는 `Server Response → 고정된 성공값`으로 바꾸는 작업으로 정의하지 않는다.

서버가 기존에 담당하던 역할을 가능한 한 **기존 게임의 Data Model / Result Object / Game Logic을 재사용하면서 로컬에서 재현**하는 방향을 우선한다.

```text
기존 온라인

Input
 ↓
Request
 ↓
Server Logic
 ├─ 인증
 ├─ 상태 조회
 ├─ RNG
 ├─ 보상 판정
 ├─ 재화 차감
 ├─ 인벤토리 변경
 └─ 저장
 ↓
Response
 ↓
Parser / Deserialize
 ↓
Data Object
 ↓
Manager / Game Logic
 ↓
UI / Gameplay
```

목표 오프라인 구조:

```text
Input
 ↓
Local Logic / Local State
 ├─ 인증 대체
 ├─ 상태 조회 대체
 ├─ RNG
 ├─ 보상 판정
 ├─ 재화 차감
 ├─ 인벤토리 변경
 └─ 저장
 ↓
기존 Result / Data Object 가능하면 재사용
 ↓
기존 Manager / Game Logic
 ↓
기존 UI / Gameplay
```

가능한 경우 서버 응답의 데이터 구조를 유지하고, **서버가 만들던 결과만 로컬에서 생성하여 기존 callback/data path에 공급**하는 것을 1순위 전략으로 한다.

## 처리 대상 후보

### 1. 뽑기
뽑기는 단순 랜덤값 생성이 아니라 다음 상태 전이가 필요할 수 있다.

```text
뽑기 실행
 ↓
현재 뽑기 대상 / 배너
 ↓
비용 확인
 ↓
로컬 재화 확인
 ↓
등급/대상 RNG
 ↓
캐릭터/아이템 결정
 ↓
중복 여부 판정
 ↓
최종 결과
 ↓
재화 차감
 ↓
캐릭터/인벤토리 갱신
```

우선 조사할 것:
- 뽑기 대상/배너 데이터가 클라이언트에 존재하는가
- 등급/대상 선택 테이블이 존재하는가
- 확률 또는 가중치가 클라이언트에 존재하는가
- 기존 RNG/Weighted Choice 로직이 존재하는가
- 중복 캐릭터/아이템 처리 규칙이 존재하는가
- 중복 시 별도 보상으로 변환되는가, 아니면 후보에서 제거되는가

### 2. 한정/특정 뽑기
```text
현재 활성 배너
 ↓
대상 테이블
 ↓
기간/상태 조건
 ↓
RNG
 ↓
결과
```

배너와 대상 정보가 서버에서만 공급되는지, AssetBundle/ScriptableObject/기타 클라이언트 데이터에 이미 포함되는지 확인한다.

### 3. 전투 결과 보상
사용자가 실제 게임 화면에서 전투별 보상 리스트를 확인할 수 있다는 점을 중요한 단서로 기록한다.

가능한 구조:

```text
Stage ID
 ↓
Stage Data
 ↓
Reward List
 ↓
확률/가중치 또는 보상 선택 규칙
 ↓
Local RNG
 ↓
Battle Result
 ↓
Reward Apply
 ↓
Player State 갱신
```

단, **보상 리스트가 화면에 존재한다는 사실만으로 확률까지 클라이언트에 존재한다고 단정하지 않는다.** 리스트와 실제 선택 로직을 함께 추적해야 한다.

맵별 보상이 다르다면 Stage ID 또는 Stage Data를 기준으로 로컬 보상 테이블을 선택해야 한다.

### 4. 로그인 보상 / 일일 보상
```text
로그인
 ↓
현재 날짜/접속 상태
 ↓
보상 조건
 ↓
보상 테이블
 ↓
보상 결정
 ↓
Player State 갱신
```

온라인 서버의 날짜/접속 기록을 그대로 대체해야 하므로, 실제 게임의 기존 일일 보상 데이터와 상태 필드를 우선 조사한다.

---

# Random / Duplicate / State Mutation 원칙

## 랜덤
각 기능마다 임의의 RNG를 새로 만드는 것보다 기존 게임의 Random/Weighted Selection 로직이 있는지 먼저 찾는다.

기존 로직을 찾지 못해 별도 구현이 필요한 경우에만 개념적으로 다음과 같이 통합한다.

```text
LocalRandomService
 ├─ NextInt
 ├─ NextFloat
 ├─ WeightedChoice
 └─ Shuffle
```

뽑기/전투 보상/드랍 등은 동일한 로컬 랜덤 계층을 사용할 수 있다.

## 중복 처리
'한 번 나온 캐릭터가 다시 나오지 않는다'는 규칙은 아직 확정하지 않는다.

가능한 두 형태:

```text
A. 진짜 중복 불가
전체 후보 - 보유 목록 = 추첨 후보
```

또는

```text
B. 중복 가능 + 중복 보상 변환
RNG → 이미 보유한 캐릭터
    → 조각/재화/기타 중복 보상으로 변환
```

실제 게임 코드/데이터에서 규칙을 증명한 뒤 구현한다.

## 결과 적용
결과를 UI에 표시하는 것만으로는 부족하다.

예:

```text
Gold 10000
 ↓ 뽑기 비용 1000
Gold 9000
 ↓
Character A 획득
 ↓
OwnedCharacterIDs에 A 추가
```

다음 뽑기에서는 변경된 보유 상태를 다시 사용해야 한다.

따라서 각 기능은 최소한 다음 세 단계를 함께 본다.

`결과 생성 → 결과 적용 → 다음 행동에서 변경된 상태 사용`

---

# Local State 설계 원칙

최종적으로는 다음과 같은 상태가 필요할 가능성이 있다.

```text
LocalPlayerState
 ├─ Account / LoginState
 ├─ Currency
 ├─ Characters
 ├─ Inventory
 ├─ Progress
 ├─ Gacha State
 └─ Daily / Login Reward State
```

하지만 이것을 처음부터 새로 만드는 것은 금지한다.

실제 게임에 이미 `PlayerData`, `UserData`, `Inventory`, `CharacterManager`, `GameManager` 등의 구조가 존재한다면 이를 재사용하는 것이 우선이다.

즉:

**기존 데이터 모델 발견 → 기존 로직 재사용 → 부족한 부분만 로컬 상태로 보완**

순서를 따른다.

---

# 네트워크 요청-응답 구조의 오프라인화 가능성

현재 관찰상 게임의 네트워크 구조가 `요청 ↔ 응답`을 기능별로 빈번하게 수행하는 비교적 단순한 구조라면, 이것은 오히려 오프라인화에 **유리한 요소일 가능성이 있다.**

중요한 것은 요청 횟수가 많다는 사실 자체가 아니라, 각 요청이 무엇을 입력으로 받고 어떤 응답을 반환하며 응답 이후 어떤 상태를 변경하는지다.

예를 들어:

```text
ShopRequest
 → ShopResponse
 → ShopData
 → Shop UI
```

```text
GachaRequest
 → GachaResponse
 → GachaResult
 → Inventory Update
```

```text
BattleResultRequest
 → RewardResponse
 → RewardData
 → Player State Update
```

처럼 **각 요청/응답이 독립적인 단위에 가까울수록**, 해당 요청을 로컬 함수/로컬 데이터 공급으로 치환하기가 상대적으로 쉽다.

반대로 다음과 같은 구조라면 난도가 올라간다.

- 여러 요청 사이에 강한 세션 상태 의존성이 있음
- 서버가 모든 랜덤/전투 판정을 수행하고 클라이언트에는 결과만 전달
- 응답에 서버 생성 토큰/nonce/서명 등이 필요함
- 요청 순서나 서버 timestamp가 엄격하게 검증됨
- 여러 기능이 하나의 authoritative transaction에 강하게 묶여 있음

따라서 현재 단계에서는 **'요청이 많다 = 오프라인화가 어렵다'고 판단하지 않는다.** 오히려 현재 관찰된 단순 request/response 패턴은 기능별로 하나씩 로컬 provider로 치환할 수 있는 구조일 가능성이 있다.

---

# 오프라인화 가능성 1차 판단

현재 정보만으로는 **가능성이 높다고 판단한다.** 단, 아직 '확정'은 아니다.

가장 긍정적인 근거:
1. 업데이트 게이트는 이미 우회 가능함.
2. 온라인 상태에서 게임의 각 기능이 실제로 동작함.
3. 게임 화면에 보상 리스트/메뉴 데이터 등 클라이언트가 이미 가지고 있을 가능성이 있는 데이터가 존재함.
4. 네트워크가 기능별 request/response 형태로 반복되는 것으로 관찰됨.
5. 강화 확률 등 복잡한 서버 계산 요소가 많지 않은 것으로 파악됨.
6. 핵심 문제는 서버가 제공하던 상태와 결과를 로컬에서 재현하는 것으로 좁혀질 가능성이 있음.

가장 큰 불확실성:
- 로그인 응답이 공급하는 초기 Player State의 범위
- 뽑기 확률/중복 규칙의 위치
- 전투 결과 판정이 클라이언트인지 서버인지
- 상점/이벤트/한정 뽑기 데이터의 서버 의존성
- 서버가 발급하는 세션/검증 값의 존재 여부
- 기존 클라이언트에 실제로 어느 정도의 Static Data와 Game Logic이 남아 있는지

따라서 현재 목표는 '모든 네트워크를 한 번에 제거'가 아니라 **기능별 request/response를 하나씩 local provider로 대체할 수 있는지 증명하는 것**이다.

---

## Revised development plan
### Phase 1 — Update gate
Status: **O / bypass patched**

### Phase 2 — Login / Online Data Flow Discovery
Status: **NEXT**

`Login Request → Network → Login Response/Callback → Deserialize/Parser → Account/Player Data → Manager/Singleton → Login Complete → Main Menu Entry`

오프라인 무한 로딩의 정확한 대기 지점을 증명한다.

### Phase 3 — Local Login / State Bootstrap
서버 로그인 결과를 대체할 최소 상태를 기존 Data Model에 공급한다.

### Phase 4 — Menu Data Providers
메인 메뉴/상점/맵/맵 상세 등 기능별 request/response를 로컬 provider로 치환한다.

### Phase 5 — Result Logic / State Mutation
뽑기/전투 보상/로그인 보상/구매 등 서버가 수행하던 결과 생성과 상태 변경을 로컬에서 재현한다.

### Phase 6 — Duplicate / RNG / Rule Verification
뽑기/드랍/보상에서 RNG, 가중치, 중복, 변환 규칙을 기존 데이터/코드에서 증명하고 구현한다.

### Phase 7 — Persistence
확인된 Player State를 로컬에 저장/복원한다.

### Phase 8 — Runtime Validation
사용자는 화면 결과만 확인하고, Codex가 ADB/logcat/build/install/자동 검사를 담당한다.

---

## Immediate next target
**TASK-003 — 로그인 → 메인 메뉴 데이터 흐름 및 네트워크 의존성 증명**

이번 단계에서는 수정하지 않는다.

핵심 질문:
1. 로그인 요청을 생성하는 함수는 무엇인가?
2. 요청의 계정/세션/토큰/식별자는 무엇인가?
3. 성공 callback은 무엇인가?
4. 응답 타입과 parser/deserializer는 무엇인가?
5. 응답 데이터는 어느 Manager/Data Model에 저장되는가?
6. 로그인 완료 후 메인 메뉴 진입 전에 추가 요청이 있는가?
7. 오프라인에서 정확히 어느 요청 이후 callback/state transition이 멈추는가?
8. timeout/failure가 존재하는가?
9. 로그인/초기 상태를 대체할 기존 로컬 데이터가 있는가?
10. 서버 응답을 로컬에서 공급하기 위한 최소 데이터 세트는 무엇인가?

**수정 금지. 먼저 로그인 데이터 흐름과 오프라인 무한 로딩의 실제 원인을 증명한다.**
