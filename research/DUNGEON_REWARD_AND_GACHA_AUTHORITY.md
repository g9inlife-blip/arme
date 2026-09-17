# 던전 보상 및 가챠 랜덤값 권한 구조 정리

## 목적

기존 분석에서 확인한 던전 보상 및 가챠의 서버 권한 구조를 오프라인화 작업의 기준으로 기록한다.

> 이 문서는 현재까지 사용자가 확인한 게임 동작을 기준으로 한 분석 메모다. 버전 차이가 있을 수 있으므로 실제 패치 대상에서는 최신 APK의 코드/XREF/런타임 결과로 재검증한다.

---

## 1. 던전 보상 구조

### 1.1 보상 후보 목록과 실제 획득 보상은 서로 다르다

던전 화면에 표시되는 보상 목록은 **실제로 모두 획득하는 목록이 아니다.**

예를 들어 전체 보상 후보가 10개라면:

```text
보상 후보 목록
A B C D E F G H I J
```

이 10개는 해당 던전에서 나올 수 있는 보상 후보 목록이다.

실제 획득 보상은 이 중 일부이며, 기본 보상과 랜덤 보상이 조합되어 보통 2~3개 정도가 될 수 있고 매 입장마다 달라질 수 있다.

```text
보상 후보 10개
        ↓
던전 입장
        ↓
서버가 실제 보상 결정
        ↓
기본 보상 + 랜덤 보상
        ↓
실제 획득 예정 보상 2~3개
```

### 1.2 실제 보상 결정 시점

중요한 기준은 **전투 승리 시점이 아니라 던전 진입 시점**이다.

현재 확인된 흐름:

```text
서버
 ↓
유저가 진입 가능한 던전/클리어 정보
 ↓
클라이언트 던전 화면
 ↓
보상 후보 목록 표시
 ↓
[던전 입장]
 ↓
던전 코드 + 유저 정보 등 서버 전송
 ↓
서버가 실제 보상 결정
 ↓
클라이언트에 해당 던전의 실제 보상 정보 전달
 ↓
전투 진행
 ↓
승리
 ↓
이미 결정된 보상 목록 표시/획득 처리
```

따라서 오프라인화 시에도 다음 순서를 보존해야 한다.

```text
DungeonEnter
 ↓
Local Reward Generation
 ↓
실제 보상 확정
 ↓
Battle
 ↓
Success
 ↓
확정된 보상 사용
```

**전투 승리 시점에 다시 랜덤을 실행하는 구조로 임의 변경하지 않는다.**

### 1.3 패배 처리

전투 실패 시에는 서버로 실패 정보가 전달되고 해당 진행이 초기화되는 기존 흐름을 기준으로 한다.

오프라인화에서는 이 서버 권한을 로컬 상태 처리로 대체할 필요가 있다.

```text
Battle Fail
 ↓
Local Failure Handling
 ↓
Dungeon/Battle State Reset
```

### 1.4 오프라인화에서 필요한 것

던전 오프라인화의 핵심은 전투 로직을 새로 만드는 것이 아니라 다음 서버 권한을 로컬로 이전하는 것이다.

- 던전 입장 검증에 필요한 최소 상태
- 던전 보상 후보 목록
- 기본 보상 규칙
- 랜덤 보상 선택 규칙/확률
- 던전 입장 시 실제 보상 확정
- 확정 보상의 전투 성공 후 표시
- 보상 획득에 따른 Player State 변경
- 필요 시 스테이지/클리어 상태 변경

특히 **보상 생성 시점은 Dungeon Enter**로 유지한다.

---

## 2. 가챠 구조

### 2.1 가챠 목록

가챠는 여러 종류가 존재할 수 있으며, 상시/기간한정/특수 등의 가챠 목록 자체를 서버에서 받아오는 경우가 있다.

```text
Server
 ↓
Gacha/Banner List
 ├─ 상시
 ├─ 기간한정
 └─ 특수
 ↓
Client Gacha Menu
```

따라서 오프라인화에서는 가챠 목록 및 배너의 정적/기간성 데이터를 로컬에서 제공할 수 있어야 한다.

### 2.2 가챠 실행

현재 확인한 구조는 다음과 같다.

```text
가챠 선택
 ↓
1회 / 10회 선택
 ↓
서버 요청
 ├─ 유저 정보
 └─ 선택한 가챠 정보
 ↓
서버
 ├─ 가챠 카운트 처리
 ├─ 랜덤 결정
 ├─ 뽑기 결과 결정
 └─ 서버 상태에 결과 저장
 ↓
클라이언트
 └─ 결과 정보 Response 수신
 ↓
가챠 결과 화면 표시
```

가챠 결과는 클라이언트가 즉석에서 결정하는 것이 아니라 **서버에서 랜덤 및 결과 처리를 완료한 뒤 결과 정보만 클라이언트에 전달하는 구조**를 기준으로 한다.

### 2.3 가챠 결과와 영구 상태의 차이

가챠 직후 화면에 표시되는 결과와 실제 보유 상태는 별도로 취급해야 한다.

```text
Gacha Response
 ↓
가챠 결과 화면
```

이후 아이템 관리/캐릭터 화면 등에서는 다시 현재 보유 데이터를 읽어 표시한다.

따라서 오프라인화 시:

```text
Local Gacha Result
 ↓
Result UI
 ↓
Local Inventory / Character State
 ↓
Local Save
```

까지 일관되게 처리해야 한다.

가챠 결과 화면에만 획득 결과를 표시하고 Local Player State를 갱신하지 않으면, 이후 아이템/캐릭터 화면에서 획득 결과가 사라지는 문제가 발생할 수 있다.

---

## 3. 던전과 가챠의 공통점

둘 다 원본 온라인 구조에서는 **서버가 결과 결정 권한을 가진다.**

```text
원본

Client Action
 ↓
Server Authority
 ↓
Random / Result Decision
 ↓
Server State
 ↓
Response
 ↓
Client UI
```

오프라인화의 목표는 서버 자체를 반드시 재현하는 것이 아니라, 필요한 경우 서버 권한을 로컬 권한으로 이전하는 것이다.

```text
오프라인

Client Action
 ↓
Local Authority
 ↓
Random / Result Decision
 ↓
Local Player State
 ↓
Existing Result/UI Processing
```

---

## 4. 던전과 가챠의 중요한 차이

| 항목 | 던전 | 가챠 |
|---|---|---|
| 후보 목록 | 던전 화면에서 보상 후보 표시 | 가챠 배너/목록 표시 |
| 실제 결과 결정 | **던전 입장 시** | **가챠 실행 시** |
| 랜덤 권한 | 서버 | 서버 |
| 전투 필요 | 있음 | 없음 |
| 결과 표시 | 전투 성공 후 확정 보상 표시 | 가챠 실행 직후 결과 표시 |
| 결과 재조회 | Player/Inventory 등에서 상태 재조회 가능 | Item/Character 등에서 상태 재조회 |
| 오프라인 핵심 | 입장 시 보상 확정 | 실행 시 결과 확정 |
| 영구 상태 | 보상/EXP/재화/진행도 등 | 아이템/캐릭터/재화/가챠 카운트 등 |

---

## 5. 오프라인화 조사 시 확인해야 할 실제 코드 지점

### 던전

다음 흐름을 증명해야 한다.

```text
던전 화면
 ↓
보상 후보 생성/수신
 ↓
Dungeon Enter 버튼
 ↓
Enter Request
 ↓
Enter Response
 ↓
실제 보상 2~3개가 어느 Response/Data Object에 들어가는가
 ↓
전투 시작
 ↓
승리
 ↓
확정 보상 객체를 어디에서 읽는가
 ↓
보상 표시
 ↓
Inventory/Player State 반영
```

특히 **Dungeon Enter Response 안에 실제 획득 예정 보상이 들어 있는지**를 우선 확인한다.

### 가챠

```text
Gacha List/Banner
 ↓
Gacha Button
 ↓
1회/10회 Request
 ↓
Response Decode/Decrypt
 ↓
Deserialize
 ↓
Gacha Result Object
 ↓
Result UI
 ↓
Inventory/Character State 갱신
```

그리고 다음을 확인한다.

- 가챠 후보/확률 테이블의 위치
- 기본 확률
- 천장/보정 카운트
- 중복 처리
- 소비 재화 차감
- 가챠 카운트 증가
- 결과 Response 필드
- Inventory/Character 데이터 갱신 위치
- Local Save 연결 위치

---

## 6. 랜덤값 분석의 핵심

단순히 `Random()` 호출을 찾는 것만으로는 충분하지 않다.

확인해야 할 것은:

```text
어떤 후보 테이블을 사용하는가?
 ↓
어떤 확률/조건을 사용하는가?
 ↓
언제 랜덤을 실행하는가?
 ↓
결과를 어떤 객체에 저장하는가?
 ↓
Player State를 어떻게 변경하는가?
 ↓
UI에는 어떤 Response/Data를 전달하는가?
```

특히 던전에서는 **Random 실행 시점이 Dungeon Enter**라는 점을 유지해야 한다.

---

## 7. 현재 오프라인화 설계 방향

현재 단계에서는 별도의 Local Server를 먼저 구현하지 않는다.

우선 다음 우선순위로 조사한다.

1. 기존 Client의 Request/Response 처리 구조 확인
2. Response가 실제로 어떤 Data Object를 생성하는지 확인
3. 던전 입장 시 실제 보상 확정 데이터의 생성/저장 위치 확인
4. 가챠 결과의 생성/처리 및 Player State 갱신 위치 확인
5. 클라이언트/Asset에 보상 및 가챠 테이블이 존재하는지 확인
6. 기존 Result/UI/Inventory 처리 코드를 최대한 재사용할 수 있는지 확인
7. 서버 권한 부분을 Local Authority로 이동할 최소 패치 범위 결정
8. 클라이언트에 존재하지 않는 서버 로직이 확인되는 경우에만 Local Server/Emulator 필요성을 재검토

---

## 8. 오프라인화 목표 구조

### 던전

```text
Dungeon Data
 ↓
Reward Candidate List
 ↓
Dungeon Enter
 ↓
Local Reward Generator
 ↓
Actual Reward Result 확정
 ↓
Battle
 ↓
Success
 ↓
Existing Reward Result Handler
 ↓
Local Player State
 ↓
Local Save
```

### 가챠

```text
Gacha/Banner Data
 ↓
Gacha Execute
 ↓
Local Gacha Generator
 ↓
Actual Gacha Result 확정
 ↓
Existing Gacha Result Handler
 ↓
Local Inventory / Character State
 ↓
Local Save
```

---

## 9. 주의사항

- 던전 화면의 보상 후보 목록을 실제 획득 보상으로 취급하지 않는다.
- 던전 보상 랜덤 시점을 전투 승리 시점으로 가정하지 않는다.
- 던전 실제 보상은 입장 시 서버에서 결정된다는 현재 분석을 기준으로 한다.
- 가챠 결과를 단순히 UI에 표시하는 것만으로 오프라인화를 완료했다고 판단하지 않는다.
- 결과가 Local Player State/Inventory/Character State에 반영되고 저장되는지 확인해야 한다.
- 서버 Response가 암호화되어 있는 경우 `Network Receive → Decode/Decrypt → Deserialize → Response Object`를 추적하여 실제 필드 의미를 증명한다.
- 버전 차이가 있으므로 본 문서의 구조는 현재 분석의 기준이며 실제 대상 APK에서는 XREF와 런타임으로 재검증한다.
