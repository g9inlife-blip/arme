# Offlineization Stage / Response Test Matrix

## 1. 목적

이 문서는 온라인 게임을 오프라인 구조로 전환할 때 **각 기능의 어느 단계에서 무엇을 분석하고, 어떤 응답을 테스트하며, 어떤 상태 변화까지 확인해야 하는지**를 정의한다.

핵심 원칙은 `네트워크 요청을 무조건 성공 처리`하는 것이 아니다.

각 기능에 대해 다음 전체 흐름을 증명한다.

```text
[입력]
  ↓
[Request 생성]
  ↓
[Network 전송]
  ↓
[Server Response]
  ↓
[Parser / Deserialize]
  ↓
[Result / Data Object]
  ↓
[State Mutation]
  ↓
[UI / Gameplay 반영]
  ↓
[다음 요청에서 변경된 State 사용]
```

오프라인 전환 후에는 가능한 경우 다음과 같이 바꾼다.

```text
[입력]
  ↓
[Local Request / Local Logic]
  ↓
[Local Response 생성]
  ↓
[기존 Parser / Result Object 재사용]
  ↓
[기존 State Mutation 재사용]
  ↓
[기존 UI / Gameplay]
  ↓
[Local State 재사용]
```

---

# 2. 공통 테스트 단계

모든 기능은 가능한 한 아래 단계 번호를 동일하게 사용한다.

## Stage 0 — 진입 조건

확인:
- 어떤 화면/버튼/이벤트에서 시작하는가
- 필요한 Player State가 무엇인가
- 필요한 ID/초기값/변수가 무엇인가
- 선행 네트워크 요청이 있는가
- 선행 데이터가 로컬 Asset/Data에 존재하는가

테스트:
- 정상 진입
- 필요한 데이터가 없는 상태
- 재진입
- 이전 기능을 수행한 직후 진입

---

## Stage 1 — Request 생성

확인:
- 실제 Request 객체/DTO/JSON/parameter 구조
- 입력값
- 계정 ID/session 값
- stage ID / banner ID / item ID 등 기능별 식별자
- 클라이언트가 직접 계산하는 값
- 서버가 계산해야 할 것으로 보이는 값

테스트:
- 정상 입력
- 경계값
- 동일 요청 반복
- 상태가 변경된 뒤 동일 요청

기록:
- Request 타입
- 생성 함수
- 전송 함수
- 주요 field
- caller/callee

---

## Stage 2 — Network 전송 경계

확인:
- 실제 HTTP/API/RPC 전송 함수
- endpoint 또는 command 식별
- 성공 callback
- 실패 callback
- timeout/retry
- 응답이 도착하지 않을 때 기다리는 지점

테스트:
- 정상 네트워크
- 응답 지연
- 응답 없음
- 실패 응답
- 중복 요청

오프라인 전환 시에는 이 단계 자체를 제거하거나 Local Provider로 우회할 후보를 결정한다.

---

## Stage 3 — Response 수신

확인:
- Response 타입
- raw response 구조
- 성공/실패 코드
- result code
- 서버에서 새로 생성한 값
- 랜덤 결과
- 보상 목록
- 재화 변경량
- inventory 변경값
- 서버 timestamp / token / nonce / signature 존재 여부

테스트:
- 성공 Response
- 실패 Response
- 빈 Response
- 일부 field가 없는 Response
- 동일 Response 재처리

중요:
- **Response를 받았다는 것과 State가 변경됐다는 것은 별개의 테스트 항목이다.**

---

## Stage 4 — Parser / Deserialize

확인:
- JSON/Binary/Protocol parser
- Deserialize 함수
- Response → Data Object 변환
- nullable/default field
- enum/result code 변환
- 중첩 객체
- 배열/list 처리

테스트:
- 정상 Response → 정상 Data Object
- 각 성공 code
- 각 실패 code
- 빈 list
- 여러 결과 list
- 알 수 없는/추가 field

목표:
- **로컬에서 생성한 Response가 기존 parser를 그대로 통과할 수 있는지 확인**한다.

---

## Stage 5 — Result / Data Object

확인:
- 최종 Result 객체
- Result가 저장되는 Manager/Singleton
- 임시 데이터와 영구 데이터 구분
- UI용 데이터와 실제 State 구분

테스트:
- 결과가 실제 객체에 들어가는가
- 객체가 다음 화면에서도 유지되는가
- 화면 전환 후 다시 서버/로컬 데이터로 덮어쓰이지 않는가

---

## Stage 6 — State Mutation

가장 중요하게 테스트한다.

확인:
- Currency 차감/증가
- Inventory 추가/삭제
- Character 보유 상태
- EXP/Level
- Stage Progress
- Gacha history/state
- Daily/Login reward state

테스트:

```text
Before State
 → Action
 → Result
 → After State
```

반드시 숫자/목록 변화가 실제로 발생하는지 확인한다.

예:

```text
Gold 10000
 ↓
Gacha Cost 1000
 ↓
Gold 9000
```

그리고:

```text
Character A 미보유
 ↓
Gacha Result = A
 ↓
Character A 보유
```

---

## Stage 7 — UI / Gameplay 반영

확인:
- 결과 화면
- 보상 팝업
- 재화 표시
- 캐릭터 목록
- 아이템 목록
- 전투 결과
- 다음 화면 진입

테스트:
- 결과 화면이 정상 표시되는가
- 표시값이 State와 일치하는가
- 화면을 나갔다 다시 들어와도 값이 유지되는가

UI 표시만 성공하고 State가 변경되지 않으면 **실패로 기록한다.**

---

## Stage 8 — 다음 행동에서 State 재사용

오프라인화에서 매우 중요한 검증 단계.

예:

```text
Gacha
 ↓
Character A 획득
 ↓
다시 Gacha
 ↓
Character A 보유 상태가 두 번째 요청의 입력/판정에 반영되는가?
```

또는:

```text
Battle
 ↓
Gold +100
 ↓
Shop
 ↓
Gold 100 증가 상태가 Shop의 구매 가능 여부에 반영되는가?
```

또는:

```text
Stage 1 Clear
 ↓
Progress 저장
 ↓
Map 재진입
 ↓
Stage 1 Clear 상태가 유지되는가?
```

---

## Stage 9 — 재실행 / Persistence

확인:
- 앱 종료
- 앱 재실행
- Player State 복원
- 마지막 결과 복원
- 중복 보유 상태 복원
- 재화 복원
- 진행도 복원

초기에는 Persistence 구현을 서두르지 않는다.
먼저 기존 게임의 저장 구조가 있는지 조사한다.

---

# 3. 로그인 테스트

## 목표

`Login Request → Login Response → Player State → Main Menu` 전체를 증명한다.

현재 네트워크 차단 시 최초 확실한 실패 지점이 로그인 무한 로딩이므로 최우선 대상이다.

## 확인 항목

- Login Request
- 인증/세션 응답
- Account ID
- Player ID
- Player Data
- Currency
- Character 목록
- Inventory
- Progress
- 서버 timestamp
- token/session 값
- Login Complete callback
- Main Menu Entry callback

## 응답 테스트

### 정상 로그인
```text
Login Request
 → 정상 Response
 → Player Data 생성/갱신
 → Login Complete
 → Main Menu
```

### 응답 없음
```text
Login Request
 → Response 없음
 → 무한 로딩/timeout/fail
```

실제 대기 지점을 기록한다.

### 로컬 로그인 후보

서버 Response를 완전히 제거했을 때 최소한 어떤 Data Object가 있어야 Login Complete가 발생하는지 확인한다.

**주의:** 임의의 dummy 성공값을 먼저 넣지 않는다. 실제 parser/data path를 먼저 증명한다.

---

# 4. 메인 메뉴 / 초기 데이터 테스트

## 목표

로그인 직후 서버가 내려주는 데이터 중 어떤 것이 Main Menu에 필수인지 분리한다.

확인:
- Currency
- Character
- Inventory
- Mail
- Quest
- Event
- Shop
- Gacha banner
- Stage/Map progress
- 기타 초기화 API

각 데이터마다:

```text
Request
 → Response
 → Parser
 → Manager
 → Main Menu
```

을 기록한다.

## 테스트

- 로그인 직후 정상 메뉴
- 특정 초기 Response 제거
- 특정 Response 지연
- 빈 list Response
- 초기 State만으로 메뉴 진입

목표는 **메인 메뉴 최소 Bootstrap State**를 확정하는 것이다.

---

# 5. 상점 테스트

## 흐름

```text
Shop Open
 ↓
Shop Request
 ↓
Shop Response
 ↓
Shop Data
 ↓
Shop UI
```

구매:

```text
Buy Button
 ↓
Purchase Request
 ↓
Purchase Response
 ↓
Currency Mutation
 ↓
Inventory Mutation
 ↓
UI Update
```

## 테스트

1. 상점 진입 Response
2. 상품 목록 Response
3. 구매 가능 여부
4. 구매 비용
5. 구매 성공
6. 재화 차감
7. 아이템 지급
8. 동일 상품 재구매
9. 재화 부족
10. 구매 후 상점 재진입

특히 **구매 성공 Response만 UI에 표시하고 State가 실제로 바뀌는지**를 확인한다.

---

# 6. 뽑기 테스트 — 최우선 대표 기능

## 흐름

```text
Gacha Button
 ↓
Gacha Request
 ↓
Server Gacha Result
 ↓
Gacha Response
 ↓
Result Parse
 ↓
Character / Item Result
 ↓
Currency Mutation
 ↓
Inventory / Character Mutation
 ↓
Gacha Result UI
```

## 반드시 확인할 데이터

- Banner ID
- Gacha type
- Cost
- Current currency
- Candidate list
- Grade table
- Probability / weight
- RNG 결과
- Character/Item ID
- Duplicate 여부
- Duplicate conversion reward
- Gacha history
- Pity/guarantee counter가 있는지

## 응답 테스트

### 단일 뽑기
- 정상 결과
- 각 등급 결과
- 캐릭터 결과
- 아이템 결과
- 중복 결과
- 재화 차감 결과

### 연속/10회 뽑기
- 결과 개수
- 개별 결과
- 비용 계산
- 중복 처리
- 최종 재화

### 뽑기 직후 앱 종료
사용자가 관찰한 중요한 현상에 따라 반드시 테스트한다.

```text
Gacha Button
 ↓
Request 전송
 ↓
결과가 서버/계정에 반영되는 시점 확인
 ↓
즉시 앱 종료
 ↓
재실행/계정 재조회
 ↓
결과가 이미 저장되었는가?
```

이 테스트는 **뽑기 결과가 UI보다 먼저 authoritative state에 기록되는지** 확인하기 위한 것이다.

### 동일 캐릭터 중복 테스트
- 이미 보유한 캐릭터가 다시 나올 수 있는가
- 나오면 무엇으로 변환되는가
- 후보에서 제외되는가

규칙은 실제 코드/데이터로 증명한다.

---

# 7. 한정 뽑기 / 이벤트 뽑기 테스트

확인:
- Banner ID
- 기간
- 활성/비활성 조건
- 대상 Character/Item list
- 확률/weight
- 보장 규칙
- 서버 timestamp 의존성

테스트:
- 활성 배너
- 비활성 배너
- 기간 경계
- 여러 배너 동시 존재
- 배너 변경 후 요청

목표:

```text
Server Banner State
 → Local Banner State
```

로 대체할 수 있는지 판단한다.

---

# 8. 전투 시작 테스트

전투는 **시작 요청과 종료 결과 요청을 분리해서 테스트**한다.

## 전투 시작

```text
Stage Select
 ↓
BattleStart Request
 ↓
Server acknowledgement/state
 ↓
Local Battle
```

확인:
- Stage ID
- Character IDs
- 초기 HP/MP/상태
- 입장 비용
- 횟수 제한
- 입장 가능 여부
- 서버가 생성하는 battle/session ID

테스트:
- 정상 시작
- 시작 실패
- 동일 Stage 재시작
- 시작 직후 앱 종료
- 시작 후 네트워크 차단

핵심 질문:

**전투 시작을 서버에 기록하는 목적이 무엇인가?**

---

# 9. 전투 진행 테스트

중간 진행은 우선 로컬 영역으로 분류한다.

확인:
- 전투 계산이 전부 클라이언트에 있는가
- 서버 통신 없이 전투가 끝까지 진행되는가
- battle session/state가 로컬에 존재하는가
- 전투 결과에 필요한 값이 무엇인가

테스트:
- 정상 클리어
- 실패
- 전투 중 종료
- 일시정지/재개
- 비정상 종료

목표는 **전투 중간 로직을 서버와 분리할 수 있는지** 증명하는 것이다.

---

# 10. 전투 완료 / 결과 보상 테스트 — 최우선 대표 기능

## 흐름

```text
Battle End
 ↓
Battle Result 생성
 ↓
Battle Complete Request
 ↓
Server Result / Reward
 ↓
Reward Response
 ↓
Reward Apply
 ↓
Currency / EXP / Inventory / Progress Mutation
 ↓
Result UI
```

## Request 테스트

확인:
- Stage ID
- 승패
- 남은 HP
- 사용 캐릭터
- 전투 시간
- 전투 횟수
- 기타 결과 변수

## Response 테스트

확인:
- Gold
- EXP
- Item
- Character/fragment
- Stage progress
- 기타 보상
- 서버가 새로 계산한 RNG 값

## 반드시 수행할 테스트

### 정상 클리어
```text
Before State
 → Battle
 → Complete Request
 → Reward Response
 → After State
```

### 전투 중 종료
- 서버에는 시작 기록이 남는가
- 완료 요청이 전송되지 않으면 보상은 없는가
- 재진입 시 상태는 어떻게 되는가

### 완료 직후 종료
```text
Battle Complete
 ↓
앱 즉시 종료
 ↓
재실행
 ↓
Reward/Progress가 이미 저장되어 있는가?
```

### 결과 위조 가능성 분석
수정 구현을 하기 전에 서버가 어떤 결과 필드를 검증하는지 확인한다.

목표는 서버 보안 우회가 아니라 **오프라인에서 동일한 결과 처리 구조를 재현하기 위한 권한 경계 확인**이다.

---

# 11. 맵 / 스테이지 보상 테스트

맵마다 보상이 다르므로 반드시 Stage ID를 기준으로 테스트한다.

```text
Map ID
 ↓
Stage ID
 ↓
Stage Data
 ↓
Reward List
 ↓
Reward Selection Rule
 ↓
Result
```

테스트:
- Stage A
- Stage B
- 같은 맵 다른 Stage
- 최초 클리어
- 반복 클리어
- 클리어 횟수에 따른 보상 변화
- 확률형 드랍
- 확정 보상

보상 리스트가 클라이언트에 보인다는 사실만으로 실제 보상 RNG가 클라이언트에 있다고 결론내리지 않는다.

---

# 12. 로그인/일일 보상 테스트

```text
Login
 ↓
Date / Login State
 ↓
Reward Condition
 ↓
Reward Table
 ↓
Reward Result
 ↓
Player State Mutation
```

테스트:
- 최초 로그인
- 같은 날 재로그인
- 다음 날 로그인
- 연속 로그인
- 보상 수령 전 종료
- 보상 수령 후 종료
- 이미 수령한 보상 재요청

확인:
- 서버 날짜 의존성
- 마지막 로그인 날짜
- 수령 여부
- 연속 출석 카운트
- 보상 중복 지급 방지

---

# 13. 화면 전환 / 재동기화 테스트

이 게임은 화면 전환 또는 기능 진입 시 서버 데이터가 다시 내려오는 구조일 가능성이 있으므로 별도 테스트한다.

## 기본 테스트

```text
화면 A
 ↓
Action
 ↓
State Mutation
 ↓
화면 B
 ↓
Data Refresh
 ↓
화면 B의 표시값
```

확인:
- 화면 전환 시 어떤 Request가 발생하는가
- Response가 어떤 State를 덮어쓰는가
- 로컬 임시값이 서버값으로 교체되는가
- 오프라인에서는 해당 Refresh를 Local State Read로 대체할 수 있는가

특히:

```text
Local Gold 변경
 ↓
화면 전환
 ↓
Server Gold 재수신
```

현상이 실제로 존재한다면 이것은 **Server Authority의 직접적인 증거**로 기록한다.

---

# 14. 공통 응답 테스트 표준

각 Response는 최소한 아래 테스트를 기록한다.

| 테스트 | 목적 |
|---|---|
| 정상 성공 | 정상 callback/data path 확인 |
| 실패 code | 실패 분기 확인 |
| 응답 없음 | loading/timeout 지점 확인 |
| 빈 데이터 | 기본값/예외 처리 확인 |
| 단일 결과 | 최소 정상 데이터 확인 |
| 복수 결과 | list 처리 확인 |
| 상태 변경 결과 | State Mutation 확인 |
| 동일 요청 반복 | idempotency/중복 처리 확인 |
| 앱 즉시 종료 | 서버/로컬 저장 시점 확인 |
| 재실행 후 조회 | Persistence 확인 |
| 화면 재진입 | 재동기화/덮어쓰기 확인 |

---

# 15. 기능별 오프라인 전환 판정 기준

각 기능은 다음 상태 중 하나로 판정한다.

### A — Local Replacement Proven

```text
Request
 → Local Request
 → Local Response
 → Existing Parser
 → Existing State Mutation
 → Existing UI
```

전체 흐름이 확인됨.

### B — Local Result Generation Proven

서버가 만들던 결과를 로컬에서 생성할 수 있지만 State/Persistence 연결이 아직 미완료.

### C — Client Data Exists, Server Logic Unknown

필요한 데이터는 클라이언트에 있으나 실제 서버 계산 규칙이 아직 확인되지 않음.

### D — Server Authority Not Yet Reproduced

결과 생성/검증에 서버 전용 상태 또는 로직이 필요해 보임.

### E — Unknown

Request/Response 또는 데이터 흐름 자체가 아직 추적되지 않음.

---

# 16. 우선순위

현재는 아래 순서로 테스트한다.

```text
1. Login
   ↓
2. Main Menu Bootstrap
   ↓
3. Gacha
   ↓
4. Battle Start
   ↓
5. Battle Complete / Reward
   ↓
6. Shop Purchase
   ↓
7. Stage / Map Reward
   ↓
8. Login / Daily Reward
   ↓
9. Event / Limited Content
   ↓
10. Persistence / Full Offline Regression
```

특히 **Gacha와 Battle Complete는 서버가 핵심 결과 데이터를 생성하는 대표 사례**이므로, 두 기능을 완전히 추적하면 다른 기능의 구조를 분류하기 쉬워진다.

---

# 17. Codex 작업 규칙

조사 단계에서는 수정하지 않는다.

각 기능마다 다음 형식으로 결과를 기록한다.

```text
Feature:

Entry:
Request:
Network Boundary:
Response:
Parser:
Result Object:
State Mutation:
UI Update:
Next-State Dependency:
Persistence:

Server Authority:
Local Data Available:
Local Logic Available:

Runtime Test:
- 정상:
- 실패:
- 즉시 종료:
- 재실행:
- 재진입:

Offline Replacement Verdict:
A / B / C / D / E

Evidence:
- address/function
- caller/callee
- string/XREF
- runtime observation
```

Codex는 ADB/logcat/build/install/자동 체크를 수행한다.
사용자는 화면에서 요청된 결과만 확인한다.

사용자에게 ADB 명령, logcat 명령, APK 설치 명령 등을 직접 요청하지 않는다.

---

# 18. 완료 조건

기능 하나를 '오프라인화 완료'로 표시하려면 최소한 다음을 모두 만족해야 한다.

```text
[O] 정상 입력
[O] Local Request/Logic
[O] Local Response
[O] Existing Parser/Result Path
[O] State Mutation
[O] UI/Gameplay 반영
[O] 다음 행동에서 변경 State 사용
[O] 화면 재진입 시 유지
[O] 앱 재실행 후 유지
```

단순히 화면에 성공 메시지가 뜨는 것은 완료 조건이 아니다.

최종 기준은:

> **서버가 사라져도 동일한 기능적 상태 전이가 로컬에서 계속되는가?**

이다.
