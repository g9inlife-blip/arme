# TASK-006 — Login API Contract / Local Server Bootstrap 조사

## 목적

아키텍처 방향을 **Local Private Server / API Emulation**으로 전환한 후 첫 구현 단위다.

목표는 로그인 기능을 패치로 강제 성공시키는 것이 아니라, **원본 Client가 로그인 시 보내는 Request와 기대하는 Response를 증거로 규격화하고 최소 Local Server Response로 Main Menu까지 연결할 수 있는지 확인하는 것**이다.

## 범위

```text
Login UI
 ↓
Login Request 생성
 ↓
Serialize / Encrypt
 ↓
Network Send
 ↓
Response Receive
 ↓
Decode / Decrypt
 ↓
Deserialize
 ↓
Login Response Object
 ↓
Login Complete / Callback
 ↓
Initial Player State
 ↓
Main Menu Bootstrap
```

## 반드시 조사할 것

### 1. Request
- 로그인 버튼/자동 로그인 진입점
- Request 생성 함수
- Request type / DTO
- 주요 field
- Account ID / user identifier
- device/app/version 정보
- session/token 관련 값
- serializer
- encryptor
- 실제 endpoint/command

### 2. Response
- Response type
- raw response 구조
- decode/decrypt 함수
- deserialize 함수
- result/status code
- 성공 callback
- 실패 callback
- token/session 생성값

### 3. Initial State
Login Response 또는 후속 bootstrap Response가 생성/갱신하는 객체를 추적한다.

후보:
- Account
- Player
- Currency
- Character
- Inventory
- Stage/Progress
- Mail
- Mission
- Event
- Shop
- Gacha/Banner

각 항목은 실제 코드/XREF로 확인하고 추측하지 않는다.

### 4. Main Menu
- Login Complete 이후 호출되는 함수
- 추가 bootstrap API
- Main Menu 진입 조건
- 특정 Response가 없으면 어디에서 대기/실패하는지

## Local Server 설계에 필요한 결과

보고서에 다음 표를 작성한다.

| 항목 | 결과 |
|---|---|
| API/Command | |
| Endpoint | |
| Request Type | |
| Required Request Fields | |
| Response Type | |
| Required Response Fields | |
| Result Code | |
| Client Handler | |
| State Effect | |
| Persistence Effect | |
| Next API | |

## 최소 Response 실험

조사 단계에서 임의 패치를 하지 않는다.

분석이 끝난 뒤 별도 구현 TASK에서 다음을 목표로 한다.

```text
Client Login Request
       ↓
Local Server
       ↓
Minimum Valid Login Response
       ↓
Existing Client Parser
       ↓
Login Complete
       ↓
Main Menu
```

Main Menu까지 가지 못하면 **어느 Response/State/bootstrap 단계에서 멈추는지** 다음 조사 대상으로 기록한다.

## 중요 원칙

1. 서버의 전체 로그인 시스템을 복제하지 않는다.
2. Client가 실제로 요구하는 필드부터 확정한다.
3. Response가 State를 변경하는지 별도로 추적한다.
4. Client에 이미 존재하는 Player/Data Object는 Local Server에서 중복 구현하지 않는다.
5. 암호화 패킷을 수동 해독하는 것이 목적이 아니다. Client의 Decode → Decrypt → Deserialize path를 찾는다.
6. 조사 중에는 APK/서버 코드를 수정하지 않는다.
7. 결과는 `research/reports/TASK-006-result.md`에 기록한다.

## 완료 조건

다음 중 하나로 종료한다.

- Login Request/Response contract와 Main Menu bootstrap이 증거로 확인됨
- 특정 Response/State 의존성이 확인되어 다음 TASK가 명확함
- 추가 분석 없이는 확인할 수 없는 이유가 명확함

Codex는 결과를 기록하고 GPT의 다음 구현/조사 판단을 기다린다.
