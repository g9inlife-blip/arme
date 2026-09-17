# Research Start Here

> 이 문서는 Codex가 작업을 시작할 때 가장 먼저 읽는 현재 프로젝트 기준 문서다.

## 1. 현재 방향

**Local Private Server / API Emulation**을 1차 개발 방향으로 사용한다.

완전 Client Local화는 기본 방향이 아니다. 다만 특정 기능을 Client 기존 로직으로 처리하는 것이 더 단순하면 Hybrid 방식으로 허용한다.

전체 설계: `research/ARCHITECTURE_DIRECTION.md`

참고 구현: `research/REFERENCE_ANOTHER_APP.md`

## 2. 참고용 King Bug Castle 자료

`참고용-another_app/` 폴더에는 다른 게임인 **King Bug Castle(KBC) Private Server / Reverse Engineering 프로젝트**가 참고용으로 포함되어 있다.

이 자료는 **서버 구축 방식·구조·기술·개발 workflow를 참고하기 위한 것**이다. KBC의 게임 자체 데이터는 현재 대상 게임과 다르므로 그대로 사용하지 않는다.

### 참고 가능
- Private Server / API Emulation 구조
- FastAPI 및 route 모듈화 방식
- SQLite Player State / persistence 구조
- Action → Validate → State Mutation → Commit → Response 패턴
- JSON 정적 데이터와 DB 상태 분리
- Local CDN / Asset 제공 구조
- ARM64 client adaptation 및 build automation의 구조적 아이디어
- 서버/데이터/패치/운영 도구를 분리하는 프로젝트 구조

### 반드시 현재 게임에서 다시 검증
- 네트워크 주소, 도메인, IP, 포트
- API endpoint 및 request/response schema
- 로그인/인증/토큰 규칙
- 암호화/서명/프로토콜 값
- 아이템/캐릭터/스테이지/재화/보상 데이터
- RNG/확률/pity/duplicate 규칙
- 게임 밸런스 및 게임 규칙
- TLS/certificate pinning 및 anti-cheat 패치 대상
- CDN/asset 주소 및 경로
- 바이너리 offset, 함수 주소, hook 대상
- 기타 KBC에만 존재하는 게임 고유 데이터

**기준:** KBC에서는 "어떻게 만들었는가"를 배우고, 현재 게임에서는 "무엇을 넣어야 하는가"를 실제 분석으로 결정한다. 자세한 규칙은 `research/REFERENCE_ANOTHER_APP.md`를 따른다.

## 3. 역할

```text
GPT
 → 분석 / 판단 / TASK 지정 / 패치 방향

Codex
 → Ghidra / tracing / Local Server / SQLite / APK / runtime / Git 기록

사용자
 → 실제 화면 및 게임 동작 확인
```

상세 규칙: `research/CODEX_PROTOCOL.md`, `research/RUNTIME_PROTOCOL.md`

## 4. 개발 원칙

### Client
가능하면 기존 Client의:
- Request/Response model
- Decode/Deserialize
- Manager
- Result handler
- UI
- Gameplay

를 재사용한다.

### Local Server
서버 authoritative 역할을:
- API
- Player State
- Game State
- RNG/Reward authority
- Transaction
- SQLite persistence

로 재현한다.

### State
Response를 개별적으로 패치하지 않는다.

```text
Request
 → Local Server
 → Action/Transaction
 → State Mutation
 → SQLite
 → Response
 → Existing Client Handler
```

## 5. 첫 번째 목표

**Login → Main Menu**다.

현재 오프라인에서는 로그인 무한 로딩이 최초 확실한 실패 지점이다.

먼저 실제 로그인 Request/Response contract를 증명하고 최소 Local Server로 Main Menu 진입을 만든다.

## 6. 이후 진행

```text
Login
 ↓
Main Bootstrap
 ↓
Player State
 ↓
Dungeon/Battle
 ↓
Gacha
 ↓
Shop
 ↓
Mission/Achievement/Event/Mail
 ↓
Persistence
 ↓
Asset/CDN
 ↓
Full Runtime
```

## 7. 중요한 사실

### Dungeon
- 화면의 보상 목록은 후보 목록이다.
- 실제 보상은 보통 2~3개의 기본 + 랜덤 조합이다.
- 실제 보상 결정 시점은 **Dungeon Enter**다.
- Battle Victory에서 다시 랜덤을 실행하지 않는다.

### Gacha
- Banner와 실행 결과는 서버 의존성이 있다.
- 실행 시 서버가 count/RNG/result/state를 처리하는 구조를 기준으로 한다.
- 결과 UI와 persistent Player State를 분리해서 검증한다.

## 8. 분석 포맷

모든 핵심 API는:

```text
Request Creator
 → Serialize/Encrypt
 → Network Send
 → Receive
 → Decode/Decrypt
 → Deserialize
 → Response Object
 → Client Handler
 → State Effect
 → Persistence Effect
```

을 추적한다.

## 9. Codex 작업 규칙

- GPT가 지정한 TASK 외의 새로운 방향을 독자적으로 확정하지 않는다.
- 조사 단계에서는 수정하지 않는다.
- 주소/함수 의미를 이름만으로 단정하지 않는다.
- 증거는 XREF + decompile + assembly + runtime을 함께 기록한다.
- Local Server 구현 시 실제 확인된 API contract를 우선한다.
- `참고용-another_app/`은 구조/기술 참고용으로 사용할 수 있으나 게임 고유 데이터는 복사하지 않는다.
- KBC와 현재 게임의 정보가 충돌하면 현재 게임에서 확인된 증거를 우선한다.
- 사용자는 ADB/logcat/터미널 작업을 하지 않는다.
- 결과는 `research/reports/TASK-xxx-result.md`에 기록한다.
- 작업 완료 후 Git에 push하고 GPT의 다음 지시를 기다린다.

## 10. 문서 우선순위

1. `START_HERE.md`
2. `ARCHITECTURE_DIRECTION.md`
3. `CURRENT_STATE.md`
4. `REFERENCE_ANOTHER_APP.md`
5. `CODEX_PROTOCOL.md`
6. `RUNTIME_PROTOCOL.md`
7. `OFFLINE_TEST_MATRIX.md`
8. `DUNGEON_REWARD_AND_GACHA_AUTHORITY.md`
9. `reports/`
10. `runtime/`

오래된 문서의 완전 Client Local화 문구는 현재 방향과 충돌할 경우 참고용으로만 취급한다.
